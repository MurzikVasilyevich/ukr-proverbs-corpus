import json
from embed.manifest import load_manifest, save_manifest, diff


def test_load_missing_returns_empty(tmp_path):
    assert load_manifest(str(tmp_path / "nope.json")) == {}


def test_save_then_load_roundtrip(tmp_path):
    p = str(tmp_path / "m.json")
    save_manifest(p, {"p2": "h2", "p1": "h1"})
    assert load_manifest(p) == {"p1": "h1", "p2": "h2"}


def test_diff_detects_new_changed_removed_unchanged():
    current = {"p1": "h1", "p2": "H2new", "p3": "h3"}   # p1 same, p2 changed, p3 new
    previous = {"p1": "h1", "p2": "h2", "p9": "h9"}      # p9 removed
    d = diff(current, previous)
    assert d == {"to_upsert": ["p2", "p3"], "to_delete": ["p9"]}


def test_diff_empty_previous_upserts_all():
    assert diff({"p1": "h1"}, {}) == {"to_upsert": ["p1"], "to_delete": []}
