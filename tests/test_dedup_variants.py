from core.dedup import link_variants
from core.schema import CanonicalRecord


def _rec(text, norm):
    return CanonicalRecord(text=text, normalized_text=norm)


def test_links_dialectal_variants():
    recs = [
        _rec("Як є – мине ся", "як є мине ся"),
        _rec("Як є мине сі", "як є мине сі"),
        _rec("Зовсім інша приповідка про море", "зовсім інша приповідка про море"),
    ]
    out = link_variants(recs, threshold=80)
    groups = {r.text: r.variant_group for r in out}
    assert groups["Як є – мине ся"] != ""
    assert groups["Як є – мине ся"] == groups["Як є мине сі"]
    assert groups["Зовсім інша приповідка про море"] == ""


def test_group_ids_are_deterministic_and_padded():
    recs = [
        _rec("баба з воза", "баба з воза"),
        _rec("баба із воза", "баба із воза"),
    ]
    out = link_variants(recs, threshold=80)
    assert out[0].variant_group == "v0001"
    assert out[1].variant_group == "v0001"
