from core.normalize import normalize


def test_lowercases_and_trims():
    assert normalize("  Аби Болото  ") == "аби болото"


def test_unifies_apostrophes():
    # right-single-quote, modifier-letter-apostrophe, backtick → straight '
    assert normalize("прислів'я") == "прислів'я"
    assert normalize("прислівʼя") == "прислів'я"


def test_punctuation_and_dashes_become_spaces():
    assert normalize("Аби болото, а жаби — будуть!") == "аби болото а жаби будуть"


def test_collapses_internal_whitespace():
    assert normalize("як   є –   мине  ся") == "як є мине ся"


def test_unifies_typographic_apostrophes():
    # U+2019 right-single-quotation-mark and U+2018 left-single-quotation-mark
    assert normalize("з’їв") == "з'їв"   # з'їв -> з'їв (apostrophe kept, NOT a space)
    assert normalize("прислів’я") == "прислів'я"  # прислів'я -> прислів'я


def test_preserves_dialectal_letters():
    assert normalize("Їжак ґедзь єдність і ліс") == "їжак ґедзь єдність і ліс"
