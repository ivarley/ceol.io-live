"""find_tunes, the listening service's background job: what can be checked
without the audio and the models."""

from lab.tools.find_tunes import with_key_allowance


def test_the_key_allowance_is_a_copy_and_leaves_live_listening_as_it_was():
    class Aligner:
        transpose = 0
        sequences = object()

    class Models:
        aligner = Aligner()
        popular = {1, 2}

    live = Models()
    job = with_key_allowance(live)
    assert job.aligner.transpose == "fifths" and live.aligner.transpose == 0
    assert job.aligner.sequences is live.aligner.sequences and job.popular is live.popular
    assert with_key_allowance(job) is job
