import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from pome.app.views import USD_INR, ApiCostComparison, api_cost_comparisons
from tests.test_selection import ev


def test_api_comparisons_use_ticket_pricing_and_rank_crossovers():
    def modeled(value, formula):
        return ev(value, "modeled", "usd_per_month").model_copy(update={"formula": formula})

    costs = {
        "cheap-api": modeled(5, "tickets * token rates | proxy price"),
        "self-hosted": modeled(1_000, "instances * gpu_hourly * 730"),
        "local-proxy": modeled(1_000, "proxy: cost of self-hosted, instances * gpu_hourly"),
        "expensive-api": modeled(100, "tickets * token rates"),
        "zero-api": modeled(0, "tickets * token rates"),
    }

    assert api_cost_comparisons(costs, volume=100_000, selfhost_monthly=1_000) == [
        ApiCostComparison("expensive-api", 0.001, 1_000_000),
        ApiCostComparison("cheap-api", 0.00005, 20_000_000),
        ApiCostComparison("zero-api", 0, None),
    ]


def _cost_tab(app):
    assert not app.exception
    return next(tab for tab in app.tabs if tab.label == "Cost")


def _plots(container):
    return [json.loads(chart.proto.spec) for chart in container.get("plotly_chart")]


def test_cost_tab_updates_comparison_when_scenario_changes():
    home = Path(__file__).resolve().parents[1] / "pome/app/home.py"
    app = AppTest.from_file(home, default_timeout=15).run()
    tab = _cost_tab(app)
    monthly, thresholds, curves = _plots(tab)
    assert monthly["data"][0]["type"] == "bar"
    assert any("self-host is cheaper above" in item.value for item in tab.markdown)
    ranked = thresholds["data"][0]
    assert list(ranked["x"]) == sorted(ranked["x"])
    assert tab.selectbox[0].value == ranked["y"][0]
    assert "gemma4-31b-vllm-in-bf16" not in ranked["y"]
    assert "gemma4-12b-ollama-local-q4" not in ranked["y"]
    assert [expander.label for expander in tab.expander] == [
        "API versus self-hosted details", "Cost at other volumes (table)",
    ]
    assert list(tab.dataframe[0].value["API configuration"]) == ranked["y"]
    assert curves["data"][2]["name"] == "Break-even"

    selected = "sarvam105b-api-in"
    tab.selectbox[0].select(selected).run()
    curves = _plots(_cost_tab(app))[2]
    crossing = curves["data"][2]["x"][0]
    assert crossing > 10_000_000
    assert curves["layout"]["xaxis"]["range"][1] > crossing
    api_trace = curves["data"][0]
    old_api = api_trace["y"][api_trace["x"].index(100_000)]

    app.sidebar.select_slider[0].set_value(500_000)
    app.sidebar.selectbox[0].select("e2e-l40s")
    for field in app.sidebar.number_input:
        if field.label.startswith("GPUs"):
            field.set_value(2)
        if field.label.startswith("Self-host ops cost"):
            field.set_value(10_000)
    app.run()

    tab = _cost_tab(app)
    assert tab.selectbox[0].value == selected
    _, thresholds, curves = _plots(tab)
    for chart in [thresholds, curves]:
        assert chart["layout"]["shapes"][0]["x0"] == 500_000
    api, selfhost, marker = curves["data"]
    expected_fixed_inr = 2 * 1.2 * 730 * float(USD_INR.value) + 10_000
    assert selfhost["y"] == pytest.approx([expected_fixed_inr] * len(selfhost["y"]))
    assert api["y"][api["x"].index(500_000)] == pytest.approx(5 * old_api, rel=1e-6)
    assert marker["y"][0] == pytest.approx(api["y"][api["x"].index(marker["x"][0])])
    assert marker["x"][0] < crossing


def _comparison_app(case):
    from pome.app.cost_charts import show_api_comparison
    from pome.app.scenario import SELFHOST
    from tests.test_selection import ev

    costs = {}
    if case != "missing-baseline":
        costs[SELFHOST] = ev(1_000, "modeled", "usd_per_month")
    if case == "zero-api":
        costs["free-api"] = ev(0, "modeled", "usd_per_month").model_copy(
            update={"formula": "tickets * 0"},
        )
    show_api_comparison(costs, volume=100_000)


@pytest.mark.parametrize(("case", "message"), [
    ("missing-baseline", "No modeled self-hosted cost is available for this scenario."),
    ("missing-api", "No API configurations have a modeled cost per ticket."),
])
def test_comparison_explains_missing_costs(case, message):
    app = AppTest.from_function(_comparison_app, args=(case,)).run()
    assert not app.exception
    assert app.markdown[0].value == message
    assert not _plots(app)


def test_zero_cost_api_has_a_cost_curve_without_a_break_even():
    app = AppTest.from_function(_comparison_app, args=("zero-api",)).run()
    assert not app.exception
    line, = _plots(app)
    assert [trace["name"] for trace in line["data"]] == ["API", "Self-hosted"]
    assert set(line["data"][0]["y"]) == {0}
    assert app.dataframe[0].value["Approx. break-even tickets per month"].iloc[0] == "No break-even"
