from pome.app.render import TOKENS, badge, cell, evidence_table, gate_table

ROW = {"config": "a", "status": "rejected", "gates": {"G1": "fail", "G2": "pass"}}


def test_pass_is_a_bare_check_and_other_states_keep_their_word():
    assert ">pass<" not in cell("pass").replace('class="sr">pass<', "")
    assert "fail" in cell("fail") and "not tested" in cell("not_tested")


def test_switched_off_gate_columns_are_dimmed_but_keep_their_value():
    html = gate_table([ROW], ["G1", "G2"], off={"G1"})
    assert html.count('class="g off"') == 2  # header + cell
    assert "fail" in html  # the value stays visible


def test_registry_and_source_text_is_escaped():
    r = {"config": "<x>", "metric": "m", "value": "1", "unit": "u", "provenance": "MEASURED",
         "source": "<script>alert(1)</script>", "formula": "", "retrieved": "2026-11-22"}
    html = evidence_table([r])
    assert "<script>" not in html and "&lt;script&gt;" in html and "&lt;x&gt;" in html


def test_badge_shape_follows_provenance():
    assert "bdg-measured" in badge("MEASURED") and "bdg-modeled" in badge("MODELED")
    assert badge("") == ""


def _lum(h: str) -> float:
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def _ratio(a: str, b: str) -> float:
    hi, lo = sorted((_lum(a), _lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def test_gossamer_text_tokens_pass_aa_and_icon_tokens_pass_3_to_1():
    t = TOKENS["light"]
    assert set(TOKENS) == {"light"}
    for key in ("text", "muted", "accent", "coraltext"):
        assert _ratio(t[key], t["bg"]) >= 4.5 and _ratio(t[key], t["panel"]) >= 4.5, key
    assert _ratio(t["coral"], t["bg"]) >= 3


def test_stats_row_carries_count_targets_for_the_count_up():
    from pome.app.render import stats
    html = stats([("configurations", 20), ("rejected", 19)])
    assert 'data-count="20"' in html and 'data-count="19"' in html and "rejected" in html
    assert 'class="tally"' in html and "kp" not in html  # one inline sentence, no stat cards


def test_motion_loader_points_at_self_hosted_files_that_exist():
    from pathlib import Path

    from pome.app.render import MOTION
    static = Path("pome/app/static/js")
    for name in ("anime.umd.min.js", "motion.js"):
        assert f"app/static/js/{name}" in MOTION and (static / name).is_file()
    js = (static / "motion.js").read_text(encoding="utf-8")
    assert "prefers-reduced-motion" in js and "window.anime" in js


def test_status_cells_are_word_chips_coloured_by_status():
    html = gate_table([ROW], ["G1", "G2"], set(), {"a": "eligible_modeled"})
    assert '<span class="chip chip-rejected">Rejected</span>' in html
    assert '<span class="chip chip-eligible_modeled">Eligible (modeled)</span>' in html


def test_gate_table_can_show_a_monthly_cost_column_with_over_budget_marked():
    html = gate_table([ROW], ["G1", "G2"], set(), None,
                      cost={"a": ("₹1,500", True)})
    assert '<td class="num cost over">₹1,500 <span class="ob">over budget</span></td>' in html
    assert "Monthly cost" in html
