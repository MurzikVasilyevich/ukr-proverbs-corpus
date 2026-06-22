import pytest
from enrich.schema import (
    load_taxonomy, TAXONOMY_KEYS, validate_categories,
    validate_pass_a_record, validate_pass_b_record,
)


def test_taxonomy_has_27_keys():
    tax = load_taxonomy()
    assert len(tax) == 27
    assert tax["work_labor"] == "Праця і ремесло"
    assert "idiom_expressive" in TAXONOMY_KEYS


def test_validate_categories_ok():
    assert validate_categories(["work_labor", "animals"], TAXONOMY_KEYS) == ["work_labor", "animals"]


@pytest.mark.parametrize("cats", [[], ["a", "b", "c", "d"], ["not_a_theme"]])
def test_validate_categories_rejects(cats):
    with pytest.raises(ValueError):
        validate_categories(cats, TAXONOMY_KEYS)


def test_pass_a_record_ok_and_bad():
    validate_pass_a_record({"id": "p000001", "categories": ["animals"], "explanation_clean": "x"}, TAXONOMY_KEYS)
    with pytest.raises(ValueError):
        validate_pass_a_record({"id": "", "categories": ["animals"], "explanation_clean": "x"}, TAXONOMY_KEYS)
    with pytest.raises(ValueError):
        validate_pass_a_record({"id": "p1", "categories": ["nope"], "explanation_clean": "x"}, TAXONOMY_KEYS)


def test_pass_b_record_ok_and_bad():
    validate_pass_b_record({"id": "p1", "modern_text": "сучасний текст"})
    with pytest.raises(ValueError):
        validate_pass_b_record({"id": "p1", "modern_text": ""})
