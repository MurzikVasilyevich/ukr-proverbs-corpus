from expand.apply_cleanup import apply_row
from core.normalize import normalize

BASE = {"id": "p000001", "text": "' По парі пізнати.", "normalized_text": "old",
        "modern_text": "' По парі пізнати.", "category": "wisdom_folly", "explanation": "нота"}

def test_apply_row_cleans_recomputes_and_preserves_enrichment():
    out = apply_row(dict(BASE), {})
    assert out["text"] == "По парі пізнати."                 # leading junk stripped
    assert out["modern_text"] == "По парі пізнати."
    assert out["normalized_text"] == normalize(out["text"])  # recomputed
    assert out["category"] == "wisdom_folly"                 # enrichment preserved
    assert out["explanation"] == "нота"

def test_apply_row_canonicalizes_punct_to_ascii():
    out = apply_row({"id": "p2", "text": "«А?» — «Б!»", "normalized_text": "x", "modern_text": "«А?» — «Б!»"}, {})
    assert out["text"] == '"А?" - "Б!"'

def test_corrections_override_by_id():
    out = apply_row(dict(BASE), {"p000001": {"text": "Тото має добрий ґуст.", "modern_text": ""}})
    assert out["text"] == "Тото має добрий ґуст."            # homoglyph repair from corrections.csv (then to_plain)
