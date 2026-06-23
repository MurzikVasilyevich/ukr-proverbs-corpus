from embed.compose import compose_embed_text, content_hash


def test_compose_all_fields():
    row = {"text": "А", "modern_text": "Б", "explanation": "Пояснення."}
    assert compose_embed_text(row) == "А\nБ\nПояснення."


def test_compose_skips_equal_modern_and_empty_explanation():
    row = {"text": "Сало", "modern_text": "Сало", "explanation": ""}
    assert compose_embed_text(row) == "Сало"


def test_compose_truncates_explanation():
    row = {"text": "Т", "modern_text": "Т", "explanation": "x" * 5000}
    out = compose_embed_text(row, max_expl=1000)
    assert out == "Т\n" + "x" * 1000


def test_hash_stable_and_changes():
    assert content_hash("a") == content_hash("a")
    assert content_hash("a") != content_hash("b")
    assert len(content_hash("a")) == 40
