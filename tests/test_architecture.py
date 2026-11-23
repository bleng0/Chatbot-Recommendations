"""Configurations tab: per-config architecture steps (owner request 2026-11-23)."""
from pome.app.views import architecture_steps
from pome.registry.loader import load_registry

REG = {c.config_id: c for c in load_registry()}


def test_every_config_gets_four_to_six_numbered_steps_with_one_line_titles():
    for cid, cfg in REG.items():
        steps = architecture_steps(cfg)
        assert 4 <= len(steps) <= 6, cid
        assert all(t and len(t.split()) <= 6 and d for t, d in steps), cid


def test_api_steps_name_the_provider_and_model_selfhost_steps_name_vllm_and_the_gpu():
    api = " ".join(d for _, d in architecture_steps(REG["gpt54mini-api-global"]))
    assert "OpenAI" in api and "gpt-5.4-mini" in api
    sh = " ".join(d for _, d in architecture_steps(REG["qwen38-27b-vllm-in-bf16"], gpu="1x H100"))
    assert "vLLM" in sh and "Qwen/Qwen3.8-27B" in sh and "1x H100" in sh and "India" in sh


def test_config_fan_renders_a_card_and_a_hidden_steps_panel_per_config_escaped():
    from pome.app.render import config_fan
    items = [{"config": "a<b", "model": "m", "host": "h", "status": "rejected", "cost": "₹1",
              "steps": [("Do x", "detail <y>")]},
             {"config": "c", "model": "m2", "host": "h2", "status": "eligible_modeled",
              "cost": "₹2", "steps": [("Do z", "d")]}]
    html = config_fan(items, focus="c")
    assert html.count('class="fan-card') == 2 and html.count('class="fan-steps') == 2
    assert "a&lt;b" in html and "detail &lt;y&gt;" in html and "<y>" not in html
    assert 'data-cid="c" aria-current="true"' in html
    assert 'aria-live="polite"' in html and "fan-prev" in html and "fan-next" in html
