import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import pytest

from pome.providers.spend import (
    SPEND_CAP_USD,
    SpendCapExceeded,
    SpendLedger,
    call_cost,
    estimate_run_cost,
)

T0 = datetime(2026, 11, 22, 9, 0, tzinfo=UTC)


def ledger(tmp_path, cap=1.0):
    return SpendLedger(tmp_path / "spend.jsonl", cap_usd=cap, clock=lambda: T0)


def rec(led, in_tok=1_000_000, out_tok=0, pin=0.10, pout=0.40, key_index=1):
    return led.record(config_id="gem25fl-api-global", run_id="r1", key_index=key_index,
                      in_tokens=in_tok, out_tokens=out_tok,
                      in_price_per_1m=pin, out_price_per_1m=pout)


def test_cap_matches_constraints():
    assert SPEND_CAP_USD == 20.00


def test_call_cost_is_tokens_times_price_per_million():
    # 1000 * 0.10/1e6 + 200 * 0.40/1e6 = 0.0001 + 0.00008
    assert call_cost(1000, 200, 0.10, 0.40) == pytest.approx(0.00018, abs=1e-12)


def test_estimate_run_cost_multiplies_calls():
    # 2820 calls, 1000 in / 40 out, flash: 2820*(1000*0.30 + 40*2.50)/1e6 = 1.128
    assert estimate_run_cost(2820, 1000, 40, 0.30, 2.50) == pytest.approx(1.128, abs=1e-9)


@pytest.mark.parametrize("bad", [-1, float("nan"), float("inf")])
def test_call_cost_rejects_bad_values(bad):
    with pytest.raises(ValueError):
        call_cost(bad, 0, 0.1, 0.4)


@pytest.mark.parametrize("bad", [True, "10", None])
def test_call_cost_rejects_bad_types(bad):
    with pytest.raises(TypeError):
        call_cost(bad, 0, 0.1, 0.4)


def test_new_ledger_has_spent_nothing(tmp_path):
    led = ledger(tmp_path)
    assert led.spent() == 0.0
    assert led.remaining() == 1.0


def test_record_adds_cost_and_persists_across_reopen(tmp_path):
    led = ledger(tmp_path)
    entry = rec(led)  # 1M input tokens at $0.10
    assert entry.cost_usd == pytest.approx(0.10)
    assert led.spent() == pytest.approx(0.10)
    again = ledger(tmp_path)
    assert again.spent() == pytest.approx(0.10)


def test_entry_stores_key_index_and_timestamp(tmp_path):
    led = ledger(tmp_path)
    rec(led, key_index=3)
    row = json.loads((tmp_path / "spend.jsonl").read_text().splitlines()[0])
    assert row["key_index"] == 3
    assert row["recorded_at"] == T0.isoformat()
    assert row["config_id"] == "gem25fl-api-global"
    assert row["unit"] == "usd"
    assert row["provenance"] == "measured"


def test_approve_refuses_when_estimate_plus_spent_exceeds_cap(tmp_path):
    led = ledger(tmp_path, cap=1.0)
    rec(led, in_tok=5_000_000)  # $0.50
    led.approve(0.50)  # exactly at cap is allowed
    with pytest.raises(SpendCapExceeded):
        led.approve(0.51)


def test_ensure_room_hard_stops_once_cap_reached(tmp_path):
    led = ledger(tmp_path, cap=0.20)
    led.ensure_room()
    rec(led, in_tok=2_000_000)  # $0.20 -> at cap
    with pytest.raises(SpendCapExceeded):
        led.ensure_room()


def test_record_still_persists_when_it_crosses_the_cap(tmp_path):
    # Money already spent must be recorded even if it overshoots.
    led = ledger(tmp_path, cap=0.05)
    rec(led)  # $0.10
    assert ledger(tmp_path, cap=0.05).spent() == pytest.approx(0.10)


def test_corrupt_ledger_raises_instead_of_reading_as_zero(tmp_path):
    (tmp_path / "spend.jsonl").write_text('{"cost_usd": 0.1}\nnot json\n')
    with pytest.raises(ValueError):
        ledger(tmp_path)


def test_concurrent_records_sum_exactly(tmp_path):
    led = ledger(tmp_path, cap=100.0)
    with ThreadPoolExecutor(8) as ex:
        list(ex.map(lambda _: rec(led, in_tok=1_000_000), range(200)))
    assert led.spent() == pytest.approx(20.0)
    assert len((tmp_path / "spend.jsonl").read_text().splitlines()) == 200
    assert ledger(tmp_path, cap=100.0).spent() == pytest.approx(20.0)


def test_missing_token_count_is_recorded_as_zero_not_dropped(tmp_path):
    # Gemini can return no candidates_token_count (e.g. safety block); input is still billed.
    led = ledger(tmp_path)
    entry = rec(led, out_tok=None)
    assert entry.out_tokens == 0 and entry.cost_usd == pytest.approx(0.10)


def test_fractional_token_count_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        rec(ledger(tmp_path), in_tok=1.9)


def test_spend_is_counted_even_if_the_write_fails(tmp_path, monkeypatch):
    led = ledger(tmp_path)
    monkeypatch.setattr("pome.providers.spend.os.fsync",
                        lambda fd: (_ for _ in ()).throw(OSError("disk full")))
    with pytest.raises(OSError):
        rec(led)
    assert led.spent() == pytest.approx(0.10)
    with pytest.raises(SpendCapExceeded):
        ledger(tmp_path, cap=0.10).ensure_room()


def test_ensure_room_tolerates_float_noise_at_the_cap(tmp_path):
    led = ledger(tmp_path, cap=0.3)
    for _ in range(3):
        rec(led, in_tok=1_000_000)  # 0.1 + 0.1 + 0.1 = 0.30000000000000004 or 0.2999...
    with pytest.raises(SpendCapExceeded):
        led.ensure_room()


def test_free_tier_calls_record_zero_charge_but_keep_tokens_and_list_price(tmp_path):
    led = ledger(tmp_path)
    entry = led.record(config_id="gem25f-api-global", run_id="r1", key_index=1,
                       in_tokens=1_000_000, out_tokens=0, in_price_per_1m=0.30,
                       out_price_per_1m=2.50, tier="free")
    assert entry.cost_usd == 0.0 and entry.tier == "free" and entry.in_tokens == 1_000_000
    assert entry.in_price_per_1m == 0.30  # list price kept for the cost model
    assert led.spent() == 0.0


def test_tier_must_be_free_or_paid(tmp_path):
    with pytest.raises(ValueError):
        ledger(tmp_path).record(config_id="c", run_id="r", key_index=1, in_tokens=1,
                                out_tokens=1, in_price_per_1m=0.1, out_price_per_1m=0.1,
                                tier="promo")
