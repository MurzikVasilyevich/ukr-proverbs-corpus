from adapters.nomis import load


def test_load_nomis(tmp_path):
    p = tmp_path / "nomis.csv"
    p.write_text("ref,text\n12,Без труда нема плода\n13,\n", encoding="utf-8")
    recs = load(str(p))
    assert len(recs) == 1                     # blank-text row skipped
    assert recs[0].text == "Без труда нема плода"
    assert recs[0].annotations[0].source == "Nomis1864"
    assert recs[0].annotations[0].ref == "12"
