from lab.corpus.index import Index
from lab.corpus.tunes_csv import Setting


def setting(tune_id, setting_id, abc, name=None, mode="Dmajor", tune_type="reel"):
    return Setting(tune_id=tune_id, setting_id=setting_id, name=name or f"tune {tune_id}",
                   tune_type=tune_type, meter="4/4", mode=mode, abc=abc)


def test_self_lookup_ranks_own_tune_first():
    settings = [
        setting(1, 11, "DEFG ABcd | edcB AGFE |"),
        setting(2, 21, "GABc defg | agfe dcBA |"),
        setting(3, 31, "DDEF GGAB | ccdB AGFD |"),
    ]
    idx = Index.build(settings, n=3, progress_every=0)
    from lab.corpus import abc_pitch

    for s in settings:
        iv = abc_pitch.interval_sequence(abc_pitch.pitch_sequence(abc_pitch.parse_abc(s.abc, key=s.mode)))
        assert idx.lookup(iv, top_k=1)[0]["tune_id"] == s.tune_id


def test_a_tune_with_many_settings_does_not_win_on_popularity():
    """The bug this guards: postings list settings, so a tune transcribed
    twenty times used to score twenty times for one matching phrase, and
    popular tunes beat a tune's own notes."""
    from lab.corpus import abc_pitch

    shared = "DEFG ABcd |"
    popular = [setting(100, 1000 + i, shared + " GFED CBAG |") for i in range(20)]
    obscure = [setting(200, 2000, shared + " fedc BAGF |")]
    idx = Index.build(popular + obscure, n=3, progress_every=0)

    query = abc_pitch.interval_sequence(
        abc_pitch.pitch_sequence(abc_pitch.parse_abc(obscure[0].abc, key="Dmajor")))
    ranked = idx.lookup(query, top_k=5)
    assert ranked[0]["tune_id"] == 200, [(r["tune_id"], round(r["score"], 3)) for r in ranked]
    # and its hits cannot exceed the number of n-grams queried
    assert ranked[0]["hits"] <= ranked[0]["n_grams_queried"]


def test_df_counts_tunes_not_settings():
    settings = [setting(1, 11, "DEFG ABcd |"), setting(1, 12, "DEFG ABcd |"), setting(2, 21, "DEFG ABcd |")]
    idx = Index.build(settings, n=3, progress_every=0)
    for gram, df in idx.df.items():
        assert df == 2, (gram, df)


def test_score_is_bounded_and_coverage_reported():
    from lab.corpus import abc_pitch

    settings = [setting(1, 11, "DEFG ABcd | edcB AGFE |"), setting(2, 21, "cdec BGBd | gfge dBGB |")]
    idx = Index.build(settings, n=3, progress_every=0)
    iv = abc_pitch.interval_sequence(
        abc_pitch.pitch_sequence(abc_pitch.parse_abc(settings[0].abc, key="Dmajor")))
    top = idx.lookup(iv, top_k=2)[0]
    assert 0.0 < top["score"] <= 1.0 + 1e-9
    assert 0.0 < top["coverage"] <= 1.0 + 1e-9


def test_unknown_query_returns_nothing():
    idx = Index.build([setting(1, 11, "DEFG ABcd |")], n=3, progress_every=0)
    assert idx.lookup([], top_k=5) == []
    assert idx.lookup([11, -11, 11], top_k=5) == []
