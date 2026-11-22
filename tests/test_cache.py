from pome.eval.cache import ResponseCache


def test_put_then_get_survives_reopen(tmp_path):
    c = ResponseCache(tmp_path / "cache.jsonl")
    assert c.get("cfg", "h1", 0) is None
    c.put("cfg", "h1", 0, {"text": "x", "in_tokens": 5})
    assert ResponseCache(tmp_path / "cache.jsonl").get("cfg", "h1", 0) == {
        "text": "x", "in_tokens": 5}


def test_key_includes_config_prompt_and_run(tmp_path):
    c = ResponseCache(tmp_path / "cache.jsonl")
    c.put("cfg", "h1", 0, {"text": "a"})
    assert c.get("cfg", "h1", 1) is None
    assert c.get("other", "h1", 0) is None
    assert c.get("cfg", "h2", 0) is None
