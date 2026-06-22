import json
import pytest
from enrich.merge import load_outputs, merge


def _corpus():
    return [
        {"id": "p000001", "text": "Т1", "normalized_text": "т1", "keyword": "k1",
         "explanation": "raw1", "category": "", "sources": "Franko1901", "source_refs": "А", "variant_group": ""},
        {"id": "p000002", "text": "Т2", "normalized_text": "т2", "keyword": "",
         "explanation": "raw2", "category": "", "sources": "Mlodzynskyi2009", "source_refs": "2", "variant_group": "v0001"},
    ]


def test_merge_sets_enriched_fields():
    a = {"p000001": {"id": "p000001", "categories": ["animals", "wisdom_folly"], "explanation_clean": "clean1"},
         "p000002": {"id": "p000002", "categories": ["food_hunger"], "explanation_clean": "clean2"}}
    b = {"p000001": {"id": "p000001", "modern_text": "Т1 модерн"},
         "p000002": {"id": "p000002", "modern_text": "Т2 модерн"}}
    out = merge(_corpus(), a, b)
    assert out[0]["modern_text"] == "Т1 модерн"
    assert out[0]["category"] == "animals;wisdom_folly"
    assert out[0]["explanation"] == "clean1"
    assert out[0]["text"] == "Т1"  # untouched
    # column order
    assert list(out[0].keys()) == ["id", "text", "normalized_text", "modern_text", "keyword",
                                   "explanation", "category", "sources", "source_refs", "variant_group"]


def test_merge_missing_id_raises():
    a = {"p000001": {"id": "p000001", "categories": ["animals"], "explanation_clean": "c"}}
    b = {"p000001": {"id": "p000001", "modern_text": "m"}}
    with pytest.raises(ValueError):
        merge(_corpus(), a, b)  # p000002 missing


def test_load_outputs_dup_id_raises(tmp_path):
    (tmp_path / "a.json").write_text(json.dumps([{"id": "p1", "x": 1}]), encoding="utf-8")
    (tmp_path / "b.json").write_text(json.dumps([{"id": "p1", "x": 2}]), encoding="utf-8")
    with pytest.raises(ValueError):
        load_outputs(str(tmp_path))
