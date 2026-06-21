import csv
import json

from core.export import finalize, write_csv, write_json
from core.schema import Annotation, CanonicalRecord


def _recs():
    return [
        CanonicalRecord(text="Ббб", normalized_text="ббб",
                        annotations=[Annotation("Franko1901", "Б", "поясн")]),
        CanonicalRecord(text="Ааа", normalized_text="ааа", keyword="к",
                        annotations=[Annotation("Mlodzynskyi2009", "1"),
                                     Annotation("Franko1901", "А", "ф")]),
    ]


def test_finalize_sorts_and_assigns_ids():
    out = finalize(_recs())
    assert [r.id for r in out] == ["p000001", "p000002"]
    assert out[0].text == "Ааа"   # sorted by normalized_text
    assert out[1].text == "Ббб"


def test_write_csv(tmp_path):
    out = finalize(_recs())
    p = tmp_path / "corpus.csv"
    write_csv(out, str(p))
    rows = list(csv.DictReader(p.open(encoding="utf-8")))
    assert rows[0]["id"] == "p000001"
    assert rows[0]["sources"] == "Mlodzynskyi2009;Franko1901"
    assert rows[0]["source_refs"] == "1;А"
    assert rows[0]["explanation"] == "ф"        # Franko preferred
    assert rows[1]["explanation"] == "поясн"


def test_write_json(tmp_path):
    out = finalize(_recs())
    p = tmp_path / "corpus.json"
    write_json(out, str(p))
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data[0]["annotations"][0]["source"] == "Mlodzynskyi2009"
    assert data[0]["annotations"][0]["explanation"] is None
    assert data[0]["category"] is None
    assert data[1]["annotations"][0]["explanation"] == "поясн"
