from core.dedup import merge_exact
from core.schema import Annotation, CanonicalRecord


def _rec(text, norm, source, ref="", expl="", keyword=""):
    return CanonicalRecord(
        text=text,
        normalized_text=norm,
        keyword=keyword,
        annotations=[Annotation(source=source, ref=ref, explanation=expl)],
    )


def test_merges_same_normalized_text():
    recs = [
        _rec("Аби болото, а жаби будуть.", "аби болото а жаби будуть", "Franko1901", "Б", "поясн", "болото"),
        _rec("Аби болото, а жаби будуть", "аби болото а жаби будуть", "Mlodzynskyi2009", "6"),
    ]
    merged = merge_exact(recs)
    assert len(merged) == 1
    m = merged[0]
    assert m.sources() == ["Franko1901", "Mlodzynskyi2009"]
    assert m.keyword == "болото"            # first non-empty
    assert m.text == "Аби болото, а жаби будуть"  # lexicographically smallest


def test_distinct_normalized_text_not_merged():
    recs = [
        _rec("a", "a", "Franko1901"),
        _rec("b", "b", "Franko1901"),
    ]
    assert len(merge_exact(recs)) == 2
