import csv, os, shutil
from build import build_records


def _seed(dst):
    os.makedirs(dst, exist_ok=True)
    for f in ("franko.csv", "proverbs.csv", "proverbs_sources.csv"):
        shutil.copy(f"tests/fixtures/golden/{f}", os.path.join(dst, f))


def test_bobkova_included_when_present(tmp_path):
    d = tmp_path / "src"; _seed(str(d))
    with open(d / "bobkova.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["ref", "text"]); w.writeheader()
        w.writerow({"ref": "005", "text": "Унікальна бобковська приказка тут."})
    recs = build_records(str(d))
    texts = [r.text for r in recs]
    assert "Унікальна бобковська приказка тут." in texts
    assert any("Bobkova" in r.sources() for r in recs)


def test_bobkova_skipped_when_absent(tmp_path):
    d = tmp_path / "src"; _seed(str(d))
    recs = build_records(str(d))            # no bobkova.csv -> no error
    assert all("Bobkova" not in r.sources() for r in recs)
