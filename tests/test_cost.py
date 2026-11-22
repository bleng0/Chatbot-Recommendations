"""Cost model (PLAN F5). Expected numbers are computed by hand in the comments."""
import math
from datetime import UTC, datetime

import pytest

from pome.cost.model import (
    api_monthly_cost,
    cost_evidence,
    cost_per_ticket,
    selfhost_monthly_cost,
)
from pome.selection.engine import METRIC_SPEC

NOW = datetime(2026, 11, 22, 8, 0, tzinfo=UTC)

API = {
    "tickets": 100_000, "in_tokens_per_ticket": 1000, "out_tokens_per_ticket": 200,
    "in_price_per_1m": 0.10, "out_price_per_1m": 0.40,
}


def items(b):
    return dict(b.items)


# ---- API cost ---------------------------------------------------------------------------

def test_api_cost_hand_computed():
    # input  = 100000 * 1000 * 0.10 / 1e6 = 10.0
    # output = 100000 *  200 * 0.40 / 1e6 =  8.0
    b = api_monthly_cost(**API)
    assert items(b) == {"input_tokens": 10.0, "output_tokens": 8.0, "retry_overhead": 0.0}
    assert b.total == 18.0


def test_api_cost_with_retry_overhead():
    # overhead = (10 + 8) * 0.05 = 0.9
    b = api_monthly_cost(**API, retry_rate=0.05)
    assert items(b)["retry_overhead"] == pytest.approx(0.9)
    assert b.total == pytest.approx(18.9)


def test_api_cost_for_the_higher_tier():
    # Argon 2.00 / 10.00: input 200.0 + output 200.0
    b = api_monthly_cost(**{**API, "in_price_per_1m": 2.0, "out_price_per_1m": 10.0})
    assert b.total == 400.0


def test_api_cost_scales_linearly_with_tickets_and_zero_tickets_is_free():
    assert api_monthly_cost(**{**API, "tickets": 200_000}).total == 36.0
    assert api_monthly_cost(**{**API, "tickets": 0}).total == 0.0


def test_breakdown_items_sum_to_total():
    b = api_monthly_cost(**API, retry_rate=0.137)
    assert sum(v for _, v in b.items) == pytest.approx(b.total, abs=1e-6)


def test_formula_states_the_inputs():
    f = api_monthly_cost(**API, retry_rate=0.05).formula
    for token in ("100000", "1000", "200", "0.1", "0.4", "0.05"):
        assert token in f


# ---- self-host cost ---------------------------------------------------------------------

def test_selfhost_cost_hand_computed():
    # instances = ceil(8 / 3) = 3 ; gpu = 3 * 2.50 * 730 = 5475 ; + ops 800 = 6275
    b = selfhost_monthly_cost(peak_rps=8, sustainable_rps_per_instance=3,
                              gpu_hourly_usd=2.5, ops_monthly_usd=800)
    assert b.instances == 3
    assert items(b) == {"gpu": 5475.0, "ops": 800.0}
    assert b.total == 6275.0


def test_selfhost_exact_division_does_not_add_an_instance():
    b = selfhost_monthly_cost(peak_rps=8, sustainable_rps_per_instance=4,
                              gpu_hourly_usd=1, ops_monthly_usd=0)
    assert b.instances == 2


def test_selfhost_float_noise_does_not_add_an_instance():
    # 1.1 / 0.1 == 11.000000000000002 in floating point, but it is exactly 11 instances
    b = selfhost_monthly_cost(peak_rps=1.1, sustainable_rps_per_instance=0.1,
                              gpu_hourly_usd=1, ops_monthly_usd=0)
    assert b.instances == 11


@pytest.mark.parametrize("peak,per,expected", [(4e-10, 1, 1), (7.0000000004, 1, 8), (7, 1, 7)])
def test_selfhost_has_no_tolerance_hack_tiny_excess_still_needs_an_instance(peak, per, expected):
    b = selfhost_monthly_cost(peak_rps=peak, sustainable_rps_per_instance=per,
                              gpu_hourly_usd=3, ops_monthly_usd=0)
    assert b.instances == expected


def test_selfhost_cost_does_not_depend_on_volume_but_has_a_one_instance_floor():
    b = selfhost_monthly_cost(peak_rps=0.5, sustainable_rps_per_instance=10,
                              gpu_hourly_usd=2, ops_monthly_usd=0)
    assert b.instances == 1 and b.total == 1460.0


def test_selfhost_ops_cost_is_explicit_and_defaults_to_nothing_hidden():
    with pytest.raises(TypeError):
        selfhost_monthly_cost(peak_rps=8, sustainable_rps_per_instance=3, gpu_hourly_usd=2.5)


# ---- cost per ticket --------------------------------------------------------------------

def test_cost_per_ticket():
    assert cost_per_ticket(18.9, 100_000) == pytest.approx(0.000189)


def test_cost_per_ticket_needs_positive_tickets():
    with pytest.raises(ValueError):
        cost_per_ticket(18.9, 0)


# ---- input validation -------------------------------------------------------------------

@pytest.mark.parametrize("field,bad", [
    ("tickets", -1), ("tickets", 1.5), ("tickets", True),
    ("in_tokens_per_ticket", -1), ("out_tokens_per_ticket", float("nan")),
    ("in_price_per_1m", -0.1), ("out_price_per_1m", float("inf")),
    ("in_price_per_1m", "0.1"), ("in_price_per_1m", True),
])
def test_api_cost_rejects_bad_inputs(field, bad):
    with pytest.raises(ValueError):
        api_monthly_cost(**{**API, field: bad})


@pytest.mark.parametrize("bad", [-0.1, float("nan"), float("inf"), True])
def test_retry_rate_must_be_a_finite_non_negative_number(bad):
    with pytest.raises(ValueError):
        api_monthly_cost(**API, retry_rate=bad)


@pytest.mark.parametrize("field,bad", [
    ("peak_rps", 0), ("peak_rps", -1), ("sustainable_rps_per_instance", 0),
    ("sustainable_rps_per_instance", float("nan")), ("gpu_hourly_usd", -1),
    ("ops_monthly_usd", -1), ("ops_monthly_usd", float("inf")), ("gpu_hourly_usd", True),
])
def test_selfhost_cost_rejects_bad_inputs(field, bad):
    good = {"peak_rps": 8, "sustainable_rps_per_instance": 3,
            "gpu_hourly_usd": 2.5, "ops_monthly_usd": 800}
    with pytest.raises(ValueError):
        selfhost_monthly_cost(**{**good, field: bad})


# ---- evidence wrapper -------------------------------------------------------------------

def test_cost_evidence_is_modeled_and_matches_the_engines_expected_unit():
    b = api_monthly_cost(**API)
    e = cost_evidence(b, source="inputs: tokens from run r1, prices from pricing page",
                      retrieved_at=NOW)
    assert e.provenance == "modeled" and e.value == b.total
    assert e.unit == METRIC_SPEC["cost.monthly_usd"][0]
    assert e.formula == b.formula


def test_totals_are_rounded_so_float_noise_cannot_flip_the_budget_gate():
    b = api_monthly_cost(tickets=3, in_tokens_per_ticket=333, out_tokens_per_ticket=111,
                         in_price_per_1m=0.3, out_price_per_1m=2.5)
    assert b.total == round(b.total, 6) and math.isfinite(b.total)


# ---- adversarial review findings (2026-11-22) -------------------------------------------

def test_overflow_raises_value_error_not_nan_or_inf():
    with pytest.raises(ValueError):
        api_monthly_cost(tickets=10**300, in_tokens_per_ticket=1e300, out_tokens_per_ticket=0,
                         in_price_per_1m=1e300, out_price_per_1m=0)
    with pytest.raises(ValueError):
        selfhost_monthly_cost(peak_rps=1e300, sustainable_rps_per_instance=1,
                              gpu_hourly_usd=1e300, ops_monthly_usd=0)
    with pytest.raises(ValueError):
        selfhost_monthly_cost(peak_rps=1e308, sustainable_rps_per_instance=1e-10,
                              gpu_hourly_usd=1, ops_monthly_usd=0)


def test_huge_integer_inputs_raise_value_error_not_overflow_error():
    with pytest.raises(ValueError):
        api_monthly_cost(**{**API, "tickets": 10**400})


def test_formula_reproduces_the_inputs_exactly():
    b = api_monthly_cost(tickets=2**53 + 1, in_tokens_per_ticket=1234.5678,
                         out_tokens_per_ticket=1, in_price_per_1m=0.1234567,
                         out_price_per_1m=1, retry_rate=0.0)
    for token in ("9007199254740993", "1234.5678", "0.1234567"):
        assert token in b.formula


def test_retry_overhead_is_applied_before_rounding():
    # exact total = 1 * 1 * 1.4 / 1e6 * (1 + 1e6) = 1.4000014 -> rounds to 1.400001
    b = api_monthly_cost(tickets=1, in_tokens_per_ticket=1, out_tokens_per_ticket=0,
                         in_price_per_1m=1.4, out_price_per_1m=0, retry_rate=1e6)
    assert b.total == 1.400001
    assert sum(v for _, v in b.items) == pytest.approx(b.total, abs=1e-6)


@pytest.mark.parametrize("bad", [float("nan"), -5, True, "5", None])
def test_cost_per_ticket_validates_the_monthly_total(bad):
    with pytest.raises(ValueError):
        cost_per_ticket(bad, 100)


def test_only_python_int_and_float_are_accepted():
    from decimal import Decimal
    from fractions import Fraction
    for bad in (Decimal("0.1"), Fraction(1, 10)):
        with pytest.raises(ValueError, match="int or float"):
            api_monthly_cost(**{**API, "in_price_per_1m": bad})
