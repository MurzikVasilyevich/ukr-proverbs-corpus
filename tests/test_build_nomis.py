import os, csv
from core.schema import CanonicalRecord, Annotation
from core.normalize import normalize
from core.dedup import merge_exact


def test_nomis_dup_adds_source_and_netnew_appended():
    # one existing Franko proverb + a Nomis duplicate of it + a Nomis net-new
    existing = CanonicalRecord(text="Без труда нема плода",
                               annotations=[Annotation(source="Franko1901", ref="100")])
    nomis_dup = CanonicalRecord(text="Без труда нема плода",
                                annotations=[Annotation(source="Nomis1864", ref="1")])
    nomis_new = CanonicalRecord(text="Цілком нова приказка від Номиса",
                                annotations=[Annotation(source="Nomis1864", ref="2")])
    recs = [existing, nomis_dup, nomis_new]
    for r in recs:
        r.normalized_text = normalize(r.text)
    merged = merge_exact(recs)
    by_text = {r.text: r for r in merged}
    assert len(merged) == 2                                         # dup folded
    assert set(by_text["Без труда нема плода"].sources()) == {"Franko1901", "Nomis1864"}
    assert by_text["Цілком нова приказка від Номиса"].sources() == ["Nomis1864"]
