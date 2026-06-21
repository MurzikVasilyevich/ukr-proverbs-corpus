from adapters.mlodzynskyi import load


def test_joins_proverbs_to_sources():
    recs = load(
        "tests/fixtures/proverbs_sample.csv",
        "tests/fixtures/proverbs_sources_sample.csv",
    )
    # proverb 3 has empty text → skipped
    assert len(recs) == 2

    by_text = {r.text: r for r in recs}
    assert by_text["Аби болото, а жаби будуть"].annotations[0].source == "Mlodzynskyi2009"
    assert by_text["Аби болото, а жаби будуть"].annotations[0].ref == "1"
    assert by_text["Аби душа сита та тіло не наго"].annotations[0].source == "Ilkevich1841"


def test_keyword_is_blank():
    recs = load(
        "tests/fixtures/proverbs_sample.csv",
        "tests/fixtures/proverbs_sources_sample.csv",
    )
    assert all(r.keyword == "" for r in recs)
