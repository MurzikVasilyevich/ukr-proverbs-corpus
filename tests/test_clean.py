from core.clean import clean_text, to_plain
from core.normalize import normalize

def test_clean_text_strips_leading_junk_and_recaps():
    assert clean_text("' По парі пізнати, чим серце кипить.") == "По парі пізнати, чим серце кипить."
    assert clean_text("1 старі люде всього не знают.") == "Старі люде всього не знают."
    assert clean_text("(1 граб, і дуб.") == "Граб, і дуб."
    assert clean_text("| Якесь там.") == "Якесь там."

def test_clean_text_preserves_quotes_archaic_and_clean():
    assert clean_text("«А ви з віхті?» – «А здуло би ті!»") == "«А ви з віхті?» – «А здуло би ті!»"
    assert clean_text("Ѣсти хоче.") == "Ѣсти хоче."
    assert clean_text("Без труда нема плода.") == "Без труда нема плода."
    assert clean_text(clean_text("' По парі.")) == clean_text("' По парі.")  # idempotent

def test_to_plain_canonicalizes_punct():
    assert to_plain("«А?» — «Б!»") == '"А?" - "Б!"'
    assert to_plain('„цитата"') == '"цитата"'
    assert to_plain("нап'є") == "нап'є"        # U+2019 -> U+0027
    assert to_plain("будь-що") == "будь-що"          # word hyphen unchanged
    assert to_plain("ой…") == "ой..."
    assert to_plain(to_plain("«А?» — «Б!»")) == to_plain("«А?» — «Б!»")  # idempotent

def test_to_plain_is_normalized_text_invariant():
    for s in ["«А?» — «Б!»", "нап'є", "Не плюй у криницю — згодиться.", "„цит\""]:
        assert normalize(to_plain(s)) == normalize(s)
