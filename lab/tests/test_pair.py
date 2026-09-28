"""Pairing two saved bench results, which is how every retrieval change is judged.

A pooled difference under about a point on 500 segments is noise; the paired
count says so. Only segments both results scored are compared, and a segment
counts as right at k when the true tune is ranked k or better.
"""

from lab.bench.retrieval import pair_results


def row(seg, rank, tune_type="reel"):
    return {"segment_id": seg, "rank": rank, "tune_type": tune_type}


def test_counts_newly_right_and_newly_wrong():
    a = [row(1, 1), row(2, 2), row(3, None), row(4, 1, "jig")]
    b = [row(1, 1), row(2, 1), row(3, 4), row(4, 3, "jig")]
    out = pair_results(a, b)
    assert out["n"] == 4
    ra, rb, won, lost, p = out["top1"]
    assert (ra, rb, won, lost) == (0.5, 0.5, 1, 1)
    assert p == 1.0
    assert out["won"] == [2] and out["lost"] == [4]
    # at top-5, segment 3 came in and nothing dropped out
    assert out["top5"][2:4] == (1, 0)
    assert out["by_type"] == {"reel": (3, 1, 2), "jig": (1, 1, 0)}


def test_only_segments_in_both_are_compared():
    out = pair_results([row(1, 1), row(2, 1)], [row(2, None), row(3, 1)])
    assert out["n"] == 1
    assert out["lost"] == [2]
