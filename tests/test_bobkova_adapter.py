from adapters.bobkova import load


def test_maps_rows_to_records():
    recs = load("tests/fixtures/bobkova_sample.csv")
    assert len(recs) == 2                      # empty-text row skipped
    r = recs[0]
    assert r.text == "Горе тільки рака красить."
    assert r.keyword == ""
    assert r.annotations[0].source == "Bobkova"
    assert r.annotations[0].ref == "005"
    assert r.normalized_text == ""
