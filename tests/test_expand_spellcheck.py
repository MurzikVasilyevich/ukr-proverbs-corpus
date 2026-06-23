from expand.spellcheck import tokens, load_vocab, flag_unknown, is_clean


def test_tokens():
    assert tokens("Горе, не задавить!") == ["горе", "не", "задавить"]


def test_vocab_and_flagging():
    v = load_vocab("tests/fixtures/spellcheck_corpus.csv")
    assert "горе" in v and "залізо" in v
    assert is_clean("Горе не задавить", v)
    # a fabricated OCR-mangled non-word is flagged
    assert flag_unknown("Горе ззазавить", v) == ["ззазавить"]
    assert not is_clean("Горе ззазавить", v)
