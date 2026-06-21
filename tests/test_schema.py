from core.schema import Annotation, CanonicalRecord


def test_sources_and_refs_derive_from_annotations():
    rec = CanonicalRecord(
        text="Аби болото, а жаби будуть",
        annotations=[
            Annotation(source="Mlodzynskyi2009", ref="6"),
            Annotation(source="Franko1901", ref="Б", explanation="пояснення"),
        ],
    )
    assert rec.sources() == ["Mlodzynskyi2009", "Franko1901"]
    assert rec.source_refs() == ["6", "Б"]


def test_csv_explanation_prefers_franko():
    rec = CanonicalRecord(
        text="x",
        annotations=[
            Annotation(source="Mlodzynskyi2009", explanation="млодз"),
            Annotation(source="Franko1901", explanation="франко"),
        ],
    )
    assert rec.csv_explanation() == "франко"


def test_csv_explanation_empty_when_none():
    rec = CanonicalRecord(text="x", annotations=[Annotation(source="Franko1901")])
    assert rec.csv_explanation() == ""
