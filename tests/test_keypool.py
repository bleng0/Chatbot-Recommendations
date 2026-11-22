import asyncio
import logging
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import pytest

from pome.providers.keypool import AllKeysDisabled, KeyPool, Response, load_keys, read_dotenv

KEYS = {1: "sk-test-AAAA1111", 2: "sk-test-BBBB2222", 3: "sk-test-CCCC3333"}
OK = Response(200, {"ok": True})


class Clock:
    """Fake monotonic clock; sleeping advances time instantly."""

    def __init__(self):
        self.now = 1000.0
        self.sleeps = []

    def __call__(self):
        return self.now

    async def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


class FakeTransport:
    """Scripted responses per API key (default 200). Records which key each call used."""

    def __init__(self, script=None):
        self.script = {k: list(v) for k, v in (script or {}).items()}
        self.calls = []

    async def __call__(self, api_key, payload):
        self.calls.append(api_key)
        queue = self.script.get(api_key)
        return queue.pop(0) if queue else OK


def make_pool(n=3, **kw):
    clock = Clock()
    pool = KeyPool({i: KEYS[i] for i in range(1, n + 1)}, clock=clock, sleep=clock.sleep, **kw)
    return pool, clock


def run(coro):
    return asyncio.run(coro)


# ---- loading keys -------------------------------------------------------------------


def test_load_keys_indexes_by_suffix_and_skips_blanks_and_unrelated_vars():
    env = {
        "LLM_API_KEY": "a", "LLM_API_KEY_3": "c", "LLM_API_KEY_2": "",
        "LLM_API_KEY_5": "e", "OTHER": "x", "LLM_API_KEYS": "nope",
    }
    keys = load_keys(env)
    assert keys == {1: "a", 3: "c", 5: "e"}
    assert list(keys) == [1, 3, 5]


def test_read_dotenv_parses_comments_blanks_and_quotes(tmp_path):
    p = tmp_path / ".env"
    p.write_text('# comment\n\nLLM_API_KEY=abc\nLLM_API_KEY_2="quoted"\nEMPTY=\n')
    assert read_dotenv(p) == {"LLM_API_KEY": "abc", "LLM_API_KEY_2": "quoted", "EMPTY": ""}


def test_empty_pool_is_rejected_without_leaking_values():
    with pytest.raises(ValueError, match="no API keys"):
        KeyPool({})


# ---- round robin --------------------------------------------------------------------


def test_round_robin_sequential():
    pool, _ = make_pool()
    t = FakeTransport()
    got = [run(pool.request(t, "p")).key_index for _ in range(6)]
    assert got == [1, 2, 3, 1, 2, 3]
    assert t.calls == [KEYS[i] for i in got]


def test_round_robin_concurrent_is_balanced():
    pool, _ = make_pool()
    t = FakeTransport()

    async def go():
        return await asyncio.gather(*(pool.request(t, "p") for _ in range(6)))

    counts = Counter(r.key_index for r in run(go()))
    assert counts == {1: 2, 2: 2, 3: 2}


def test_try_acquire_is_thread_safe_and_balanced():
    pool, _ = make_pool()
    with ThreadPoolExecutor(8) as ex:
        leases = list(ex.map(lambda _: pool.try_acquire(), range(300)))
    assert Counter(lease.index for lease in leases) == {1: 100, 2: 100, 3: 100}


# ---- cooldown and failover ----------------------------------------------------------


def test_429_fails_over_to_next_key_and_honors_retry_after():
    pool, clock = make_pool(2)
    t = FakeTransport({KEYS[1]: [Response(429, None, {"Retry-After": "30"})]})
    first = run(pool.request(t, "p"))
    assert (first.key_index, first.retries, first.response.status) == (2, 1, 200)
    # key 1 is cooling for 30s: the next requests skip it
    assert [run(pool.request(t, "p")).key_index for _ in range(2)] == [2, 2]
    clock.now += 30
    assert run(pool.request(t, "p")).key_index == 1


def test_no_retry_after_uses_60s_then_doubles():
    pool, clock = make_pool(1)
    t = FakeTransport({KEYS[1]: [Response(429), Response(429), OK]})
    res = run(pool.request(t, "p"))
    assert clock.sleeps == [60.0, 120.0]
    assert (res.key_index, res.retries) == (1, 2)


def test_backoff_is_capped():
    pool, clock = make_pool(1, max_cooldown=100.0)
    t = FakeTransport({KEYS[1]: [Response(429)] * 3 + [OK]})
    run(pool.request(t, "p"))
    assert clock.sleeps == [60.0, 100.0, 100.0]


def test_success_resets_backoff():
    pool, clock = make_pool(1)
    t = FakeTransport({KEYS[1]: [Response(429), OK, Response(429), OK]})
    run(pool.request(t, "p"))
    run(pool.request(t, "p"))
    assert clock.sleeps == [60.0, 60.0]


def test_server_errors_also_cool_the_key_down():
    pool, clock = make_pool(1)
    t = FakeTransport({KEYS[1]: [Response(503), OK]})
    run(pool.request(t, "p"))
    assert clock.sleeps == [60.0]


def test_retry_after_is_capped_at_max_cooldown():
    pool, clock = make_pool(1, max_cooldown=600.0)
    t = FakeTransport({KEYS[1]: [Response(429, None, {"retry-after": "999999999"}), OK]})
    run(pool.request(t, "p"))
    assert clock.sleeps == [600.0]


@pytest.mark.parametrize("bad", ["abc", "-5", "nan", "inf", "Wed, 21 Oct 2026 07:28:00 GMT"])
def test_unusable_retry_after_falls_back_to_backoff(bad):
    pool, clock = make_pool(1)
    t = FakeTransport({KEYS[1]: [Response(429, None, {"Retry-After": bad}), OK]})
    run(pool.request(t, "p"))
    assert clock.sleeps == [60.0]


@pytest.mark.parametrize("status", [401, 403])
def test_auth_failure_disables_the_key_for_the_session(status):
    pool, clock = make_pool(2)
    t = FakeTransport({KEYS[1]: [Response(status)]})
    assert run(pool.request(t, "p")).key_index == 2
    clock.now += 10**6
    assert {run(pool.request(t, "p")).key_index for _ in range(4)} == {2}


def test_all_keys_cooling_waits_for_the_earliest_one():
    pool, clock = make_pool(2)
    t = FakeTransport({
        KEYS[1]: [Response(429, None, {"Retry-After": "30"})],
        KEYS[2]: [Response(429, None, {"Retry-After": "10"})],
    })
    res = run(pool.request(t, "p"))
    assert clock.sleeps == [10.0]
    assert (res.key_index, res.retries, res.response.status) == (2, 2, 200)


def test_all_keys_disabled_raises():
    pool, _ = make_pool(2)
    t = FakeTransport({KEYS[1]: [Response(401)], KEYS[2]: [Response(403)]})
    with pytest.raises(AllKeysDisabled):
        run(pool.request(t, "p"))


def test_client_error_is_returned_without_retry_or_cooldown():
    pool, _ = make_pool(2)
    t = FakeTransport({KEYS[1]: [Response(400, {"error": "bad"})]})
    res = run(pool.request(t, "p"))
    assert (res.response.status, res.retries, res.key_index) == (400, 0, 1)
    assert len(t.calls) == 1
    run(pool.request(t, "p"))
    assert run(pool.request(t, "p")).key_index == 1  # key 1 was never cooled


def test_gives_up_after_max_attempts_and_returns_the_last_failure():
    pool, _ = make_pool(2, max_attempts=3)
    t = FakeTransport({KEYS[1]: [Response(429), Response(429)], KEYS[2]: [Response(503)]})
    res = run(pool.request(t, "p"))
    assert (res.response.status, res.retries, res.key_index) == (429, 2, 1)
    assert not res.ok


# ---- secrets never leak ---------------------------------------------------------------


def test_keys_never_appear_in_repr_logs_or_errors(caplog):
    caplog.set_level(logging.DEBUG)
    pool, _ = make_pool(2)
    t = FakeTransport({KEYS[1]: [Response(401)], KEYS[2]: [Response(429), Response(403)]})
    with pytest.raises(AllKeysDisabled) as err:
        run(pool.request(t, "p"))
    fresh, _ = make_pool(2)
    blob = repr(pool) + str(pool) + caplog.text + str(err.value) + repr(fresh.try_acquire())
    for secret in KEYS.values():
        assert secret not in blob
    assert "#1" in caplog.text and "#2" in caplog.text  # the index is logged instead
