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
