from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from pome.evidence.schema import EvidenceValue

NOW = datetime(2026, 11, 22, 8, 0, tzinfo=UTC)


def ev(**over):
    base = {
        "value": 0.8,
        "unit": "ratio",
        "provenance": "measured",
        "source": "eval/run-001",
        "retrieved_at": NOW,
        "run_ids": ["run-001"],
    }
    base.update(over)
    return EvidenceValue(**base)


def test_valid_measured_value_is_accepted():
    e = ev()
    assert e.value == 0.8 and e.provenance == "measured"


def test_unknown_provenance_is_rejected():
    with pytest.raises(ValidationError):
        ev(provenance="estimated")


@pytest.mark.parametrize("field", ["value", "unit", "provenance", "source", "retrieved_at"])
def test_required_fields_cannot_be_omitted(field):
    data = {
        "value": 1, "unit": "usd", "provenance": "vendor-doc",
        "source": "https://example.com/p", "retrieved_at": NOW,
    }
    del data[field]
    with pytest.raises(ValidationError):
        EvidenceValue(**data)


def test_empty_source_is_rejected():
    with pytest.raises(ValidationError):
        ev(source="  ")


def test_naive_timestamp_is_rejected():
    with pytest.raises(ValidationError):
        ev(retrieved_at=datetime(2026, 11, 22, 8, 0))


def test_measured_requires_run_ids():
    with pytest.raises(ValidationError):
        ev(run_ids=[])


def test_vendor_doc_requires_url_source():
    with pytest.raises(ValidationError):
        ev(provenance="vendor-doc", run_ids=[], source="the pricing page")
    ok = ev(provenance="vendor-doc", run_ids=[], source="https://ai.google.dev/pricing")
    assert ok.provenance == "vendor-doc"


def test_modeled_requires_formula():
    with pytest.raises(ValidationError):
        ev(provenance="modeled", run_ids=[], formula=None)
    ok = ev(provenance="modeled", run_ids=[], formula="ceil(peak/rps)*gpu_hr*730")
    assert ok.formula


def test_extra_fields_are_forbidden():
    with pytest.raises(ValidationError):
        ev(surprise="x")
