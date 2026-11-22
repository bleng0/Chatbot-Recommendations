"""Round-robin API key pool (PLAN F12).

Keys are used only through this module. Only the key INDEX (#1, #2, ...) is ever logged,
repr'd or put in an error message, never the key itself.
"""
import asyncio
import logging
import math
import re
import threading
import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger("pome.keypool")

_KEY_NAME = re.compile(r"^LLM_API_KEY(?:_(\d+))?$")


class AllKeysDisabled(RuntimeError):
    """Every key was rejected with 401/403 in this session."""


@dataclass(frozen=True)
class Response:
    status: int
    body: Any = None
    headers: Mapping[str, str] = field(default_factory=dict)


Transport = Callable[[str, Any], Awaitable[Response]]


@dataclass(frozen=True)
class Lease:
    index: int
    secret: str = field(repr=False)


@dataclass(frozen=True)
class PoolResult:
    response: Response
    key_index: int
    retries: int

    @property
    def ok(self) -> bool:
        return self.response.status < 300


@dataclass
class _Key:
    index: int
    secret: str = field(repr=False)
    cooldown_until: float = 0.0
    failures: int = 0
    disabled: bool = False


def read_dotenv(path: Path) -> dict[str, str]:
    """Minimal KEY=VALUE reader (comments, blanks and surrounding quotes handled)."""
    out: dict[str, str] = {}
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        out[name.strip()] = value.strip().strip('"').strip("'")
    return out


def load_keys(env: Mapping[str, str]) -> dict[int, str]:
    """LLM_API_KEY -> #1, LLM_API_KEY_N -> #N. Blank values are skipped."""
    found: dict[int, str] = {}
    for name, value in env.items():
        m = _KEY_NAME.match(name)
        if m and value.strip():
            found[int(m.group(1) or 1)] = value.strip()
    return dict(sorted(found.items()))


def _retry_after(resp: Response) -> float | None:
    """Seconds from a Retry-After header; None if absent or unusable (HTTP-dates unsupported)."""
    for name, value in resp.headers.items():
        if name.lower() == "retry-after":
            try:
                seconds = float(value)
            except (TypeError, ValueError):
                return None
            return seconds if math.isfinite(seconds) and seconds >= 0 else None
    return None


class KeyPool:
    def __init__(
        self,
        keys: Mapping[int, str],
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        base_cooldown: float = 60.0,
        max_cooldown: float = 600.0,
        max_attempts: int = 8,
    ):
        if not keys:
            raise ValueError("no API keys found (expected LLM_API_KEY, LLM_API_KEY_2, ...)")
        self._keys = [_Key(i, s) for i, s in sorted(keys.items())]
        self._clock, self._sleep = clock, sleep
        self._base, self._max, self._max_attempts = base_cooldown, max_cooldown, max_attempts
        self._cursor = 0
        self._lock = threading.Lock()

    def __repr__(self) -> str:
        healthy = sum(not k.disabled for k in self._keys)
        return f"KeyPool(keys={len(self._keys)}, not_disabled={healthy})"

    def _take(self) -> tuple[_Key | None, float]:
        """Next healthy key (round-robin), or (None, seconds until one is available)."""
        with self._lock:
            now = self._clock()
            n = len(self._keys)
            for step in range(n):
                key = self._keys[(self._cursor + step) % n]
                if not key.disabled and key.cooldown_until <= now:
                    self._cursor = (self._cursor + step + 1) % n
                    return key, 0.0
            live = [k for k in self._keys if not k.disabled]
            if not live:
                raise AllKeysDisabled("all API keys were rejected (401/403) this session")
            return None, min(k.cooldown_until for k in live) - now

    def try_acquire(self) -> Lease | None:
        key, _ = self._take()
        return Lease(key.index, key.secret) if key else None

    def _cool(self, key: _Key, status: int, retry_after: float | None) -> None:
        with self._lock:
            key.failures += 1
            backoff = min(self._base * 2 ** (key.failures - 1), self._max)
            seconds = backoff if retry_after is None else min(retry_after, self._max)
            key.cooldown_until = self._clock() + seconds
        log.warning("key #%d cooling down %.0fs (status %d)", key.index, seconds, status)

    def _disable(self, key: _Key, status: int) -> None:
        with self._lock:
            key.disabled = True
        log.warning("key #%d disabled for this session (status %d)", key.index, status)

    def _succeeded(self, key: _Key) -> None:
        with self._lock:
            key.failures = 0

    async def request(self, transport: Transport, payload: Any) -> PoolResult:
        """Send via the next healthy key; on 429/5xx cool it down and retry on another key."""
        for attempt in range(1, self._max_attempts + 1):
            key, wait = self._take()
            while key is None:
                await self._sleep(wait)
                key, wait = self._take()
            resp = await transport(key.secret, payload)
            status = resp.status
            if status in (401, 403):
                self._disable(key, status)
            elif status == 429 or status >= 500:
                self._cool(key, status, _retry_after(resp))
            else:
                if status < 300:
                    self._succeeded(key)
                return PoolResult(resp, key.index, attempt - 1)
        return PoolResult(resp, key.index, self._max_attempts - 1)
