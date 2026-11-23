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


def test_both_themes_define_the_same_tokens():
    assert TOKENS["dark"].keys() == TOKENS["light"].keys()


def test_motion_loader_points_at_self_hosted_files_that_exist():
    from pathlib import Path

    from pome.app.render import MOTION
    static = Path("pome/app/static/js")
    for name in ("anime.umd.min.js", "motion.js"):
        assert f"app/static/js/{name}" in MOTION and (static / name).is_file()
    js = (static / "motion.js").read_text(encoding="utf-8")
    assert "prefers-reduced-motion" in js and "window.anime" in js
