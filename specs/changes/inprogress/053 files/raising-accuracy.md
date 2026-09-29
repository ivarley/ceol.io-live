# Raising accuracy: where the misses are, what the field does, and ten angles

2026-09-28. A survey and a proposal, not results. Written while another
session was building the Smith-Waterman aligner (`analysis/align.py`,
`bench.retrieval.Aligner`), so nothing here is measured on the bench; the two
measurements below are on the corpus and on the drawn tunes only. Every
number carries its scope. The three scratch scripts that produced them are
in the session's scratchpad and are described well enough here to redo.

## Revision, the same evening: the aligner changes the priorities

The other session's aligner landed after the note below was written, and it
solves the problem the note's framing keeps naming. Audio alone, first 30 s,
502 segments, three trackers fused, the aligner reading both eighths and
pitch changes in replace mode over a 300-tune shortlist
(`yin+basic_pitch+pesto-v1-9edcec6b`): **0.950 top-1, 0.968 top-5**, against
0.763 / 0.859 for the same trackers without it, +95/-1 paired. Against the
120 s headline with set decoding it is +26/-10 with a quarter of the audio
and no prior. Night 139, the worst, goes from 0.826 to 0.928. So the
"one error kills six phrases" arithmetic is now history: the index only has
to keep the tune in the shortlist, and the alignment does the judging.

The misses are redone on that result. 25 of 502:

| | count |
|---|---|
| reels | 17 of 25 (jigs 3, polkas 2, hornpipes 2, slip jig 1) |
| wrong answer is The Mason's Apron | 2 of 25 (was 19 of 41): the hubs are gone |
| truth ranked 2 to 8 | 10 of 25 |
| truth ranked 11 or worse but present | 7 of 25 |
| truth not in the shortlist at all | 8 of 25 |
| misses shared with the 120 s headline | 15 of 25 |
| misses whose tune is right elsewhere in the corpus | 13 of 25 |

What that does to the ten angles:

- **Angle 1, the hubs, is moot for ranking** and survives only as a
  question about shortlist recall: the 8 segments never shortlisted are the
  index's failures, not the aligner's, and a hub-free or lattice-fed index
  is how the generator's recall rises. `found_at_all` is 0.984.
- **Angles 2, 4 and 6 are now one project: the aligner's cost model.** It
  has flat costs today (match +2, mismatch -1, gap -1). Per-slot costs from a
  profile of the settings, the metrical weight from the notated slot, and
  fitted substitution and insertion costs are each a change to `local_align`'s
  scoring and are measured the same way. The 10 near misses at ranks 2 to 8
  are what they are for.
- **Angle 3, the lattice, becomes "give the aligner alternatives"**: a
  second-choice pitch at a doubtful eighth is an alignment column with two
  symbols, which is a small change to the aligner and a large one to the
  index.
- **Angle 5, the repeats, matters at 120 s and on the board**, where the
  second pass is the evidence that should shrink the short list.
- **Angle 7, the reranker and calibrator, stands.**
- **Angles 8, 9 and 10 drop to the bottom**: with 0.950 at 30 s, a better
  tracker or a new kind of evidence is worth less than closing the board gap.

**The board is now the gap.** The bench at 30 s is 0.950 and the board's
top-1 at the end of a tune is 0.819 with 14.7% right within 30 s. Putting the
aligner on the board, then the sequential-evidence assembler, is worth more
than anything else on this page.

**One thing to look at.** Set decoding over the aligner's scores at 120 s
(`yin+set_viterbi-v1-5b546c94`, yin alone) reads 0.733 top-1 against 0.980
top-5: the prior is dominating, which looks like a scale mismatch between the
aligner's 0..1 scores and the log-space combination in `rerank`, not a real
loss. The other session may already know.

## What the remaining misses look like

The headline bench (yin, Basic Pitch and PESTO fused, parser 2, key filter,
set decoding, first 120 s; `yin+basic_pitch+pesto+set_viterbi-v1-cc10dd96`)
misses 41 of 502 segments.

| | count |
|---|---|
| misses that are reels | 30 of 41 (reels 0.874, jigs 0.978, polkas 1.000) |
| misses whose wrong answer is The Mason's Apron | 19 of 41 (29 of 55 audio alone at 120 s) |
| next two wrong answers: Star of Munster, Frieze Breeches | 6 and 2 |
| misses whose tune is right on another night | 16 of 41 |
| misses with the truth ranked below 10 | 23 of 41 |
| never found at any rank | 6 of 41 |
| worst night (139) against the best (138) | 0.826 against 0.973 |

**The hubs.** In the particalized repertoire index The Mason's Apron has 35
settings and 3,019 distinct phrases; Frieze Breeches 25 and 1,982; Star of
Munster 30 and 1,904; the median tune has 9 settings and 342 phrases.
`Index.lookup` normalises by the query's idf and uses a tune's size only as
a tie-breaker (`coverage`), so a tune that is the union of 35 settings soaks
up stray hits from any noisy transcription. The player's note: The Mason's
Apron is a tune players have improvised on and added sections to for decades,
which is why its notation is a mess; most of its settings are worthless for
this purpose, and its first and last settings are close enough that a merged
canonical setting would serve.

A synthetic check, no audio: each repertoire tune's own particalized
notation, 120 eighths from a random start, corrupted with i.i.d.
substitutions, insertions and deletions, looked up three ways. 400 tunes per
row.

| noise (sub / ins / del) | today (union per tune) | best single setting | BM25-style, b = 0.5 |
|---|---|---|---|
| 0.10 / 0.05 / 0.05 | 0.993 | 0.998 | 0.998 |
| 0.20 / 0.10 / 0.10 | 0.535 | 0.605 | 0.590 |
| 0.30 / 0.15 / 0.10 | 0.163 | 0.205 | 0.200 |

Under today's scoring the commonest wrong answers at the middle row are
Frieze Breeches and Jenny's Welcome to Charlie; under length normalisation
the hub names leave the list. The noise model is crude (real errors are
structured, and the synthetic query is the tune's own setting), so this sizes
the direction and not the gain. The real test is the paired bench.

**Two facts that frame everything else.** At 70% of intervals right, only
about one six-note phrase in six survives whole, so the n-gram stage is
starved by single-note errors rather than by wholesale failure. And choosing
per segment the best of the three trackers gives 0.922 against 0.918 fused,
so rank-level fusion has nearly exhausted what choosing between trackers can
do. The gains now have to come from combining trackers below the ranking,
from the tune's own repeats, and from matching that pays for one error
instead of six.

## What the field does

Verified from sources by two survey agents on 2026-09-28; the detail is in
those reports and summarised here.

**Tunepal / MATT2 (Duggan, TU Dublin).** Front end: per-frame harmonicity
pitch (five strongest spectral peaks, scored by the energy at their first ten
harmonics), pitch spelled to a diatonic scale on a user-chosen fundamental,
so no key invariance. Onsets in the thesis via comb filters (ODCF); the
shipped web transcriber starts a note whenever the spelled letter changes.
Ornaments and tempo drift handled by OFAH: a fuzzy histogram of inter-onset
durations picks the modal duration as the quaver, every note is rounded to
whole quavers, so cuts and rolls round to zero and vanish, and long notes
become repeated quavers. Corpus keys: ornament marks stripped, repeats
expanded, notes longer than a quaver written as repeated letters, folded to
one register. Matching: Navarro-Raffinot substring edit distance over the
whole corpus, `confidence = 1 - ed / len(query)`, ten shown. Reported 93%
top-1 on 100 clean queries in 2009; Beauguitte's independent 2,000-excerpt
evaluation gives MATT2's transcription 60.6% best-hit against 84.7% for
Silvet with the same matcher. No session context of any kind.

**FolkFriend (Wyllie).** The shipped app (Rust to WASM) has no neural
network; the CNN was a 2020 prototype. Front end: enhanced autocorrelation
(Tolonen-Klapuri), 3 bins per semitone over MIDI 48-95, octave fix, five
strongest bins per frame, a full Viterbi over 48 pitch states with an
interval log-probability table, tempo sweep 60-240 BPM choosing the
frames-per-quaver that minimises quantisation error, one character per
quaver of absolute pitch. Index: every thesession setting rendered through
abc2midi at a fixed tempo to the same alphabet. Query: quadgram Aho-Corasick
counts keep the top 2,000 settings, then semi-global Needleman-Wunsch (+2 /
-2 / gap -1), score = 0.5 * best / len(query). Not transposition invariant.
The author's own committed evaluation (6,790 slices, 2021) computes to 66.1%
top-1, 71.5% top-5, 24.7% not returned. The repository holds a working
synthetic-data pipeline: thesession ABC through abc2midi and fluidsynth with a
trad soundfont, one to four heterophonic melody voices, chordal
accompaniment from the ABC chords, random transposition and tempo. Background
noise was a TODO.

Both apps end in an alignment over a shortlist. Neither uses rhythm beyond
quaver quantisation, and neither uses any context.

**Others.** Beauguitte's key-invariant Tunepal (2019) aligns pitch-class
histograms to estimate transposition and adds rhythm classification to prune
the search; his ISMIR 2016 `tuneset` corpus has Comhaltas session recordings
with note annotations, the only annotated heterophonic trad audio found.
Alan Ng's CoverHunterMPS (irishtune.info) is a Conformer over the CQT trained
on 26,482 commercial performances of 6,606 Irish tunes, open source, mAP 0.97
on his easy reel test and 74% on the hard one; the largest labelled Irish
tune audio that exists, all studio recordings. van Kranenburg's Dutch folk
song work (ISMIR 2009): Needleman-Wunsch-Gotoh with substitution scores from
pitch, metric weight and phrase position, MAP 0.83 over 26 tune families.

**From the wider literature.** Posterior-weighted n-gram indexing from a
lattice instead of one best string (Chelba and Acero 2005, about 20% relative
in spoken document retrieval). ROVER voting over aligned hypotheses from
several recognisers (Fiscus 1997). A trainable noisy-channel error model for
sung queries (Meek and Birmingham 2004). CTC-trained chroma features learned
from weakly aligned pairs, only the piece and its rough start and end known
(Zalkow and Müller 2021, code public). Joint alignment of several versions
cutting alignment error by 14% against pairwise (Wang, Ewert and Dixon 2016).
Product-rule fusion of several matchers beating any one on the MIREX QBSH sets
(Nam et al. 2011). Evidence against separation before pitch tracking: the
RMVPE paper's CREPE-plus-Spleeter rows lose to end-to-end tracking, which
agrees with this lab's HPSS result.

## Two measurements made for this note

**Settings of one tune vary off the beat, not on it.** Each repertoire
setting's ABC was split on its bar lines, each bar parsed with the lab's
parser and its notes placed on eighth slots, and settings of the same tune
with the same mode and bar count compared bar by bar as scale degrees against
each setting's tonic (from the dump's mode column). Agreement is with the
per-cell majority. 485 reels, 349 jigs, 61 hornpipes, 72 polkas, 34 slides,
44 slip jigs with two or more comparable settings.

| type | disagreement on strong beats | on the other eighths | ratio |
|---|---|---|---|
| reel | 0.130 | 0.167 | 1.28 |
| jig | 0.120 | 0.157 | 1.31 |
| hornpipe | 0.089 | 0.141 | 1.58 |
| polka | 0.127 | 0.165 | 1.30 |
| slide | 0.113 | 0.134 | 1.19 |
| slip jig | 0.147 | 0.173 | 1.17 |

The first eighth of the bar is the most stable slot in every type (0.875 to
0.915 agreement). Strong beats as the player hears them, confirmed
2026-09-28: reel and hornpipe on 1 and 5 with 3 and 7 secondary; jig on 1 and
4; polka on 1 and 3; slide on 1, 4, 7 and 10; slip jig on 1, 4 and 7. The
splitting is crude (partial bars and endings skipped, pickups dropped), so
the ratios are a floor on the effect rather than its size.

**The trackers hear the strong beats better.** On the three drawn tunes
with bar-anchored beats and a bar length, each drawn eighth was given its
slot from the nearest preceding drawn downbeat and the annotated period, and
the tracker's pitch class at the eighth's middle compared with the label.
Share right, strong beats against the other eighths:

| tracker | The Bird in the Bush (reel, 221 eighths) | The Scholar (reel, 256) | Tom Sullivan's (polka, 159) |
|---|---|---|---|
| yin | 0.74 vs 0.62 | 0.50 vs 0.45 | 0.90 vs 0.80 |
| PESTO | 0.74 vs 0.49 | 0.44 vs 0.25 | 0.86 vs 0.65 |
| Basic Pitch | 0.88 vs 0.66 | 0.55 vs 0.34 | 0.96 vs 0.71 |

Phrase survival is per-note accuracy to the sixth power: at 0.66 a six-note
phrase survives 8% of the time, at 0.88, 46%. A reading built from the
strong-beat notes alone would be cleaner by that kind of factor, and it is
wrong in a different way from the plain and eighth readings.

## Ten angles, revised after the conversation

(Ordering superseded by the revision at the top; kept as written.)

Ordered by expected value against cost. The first three are days each; the
middle group is a week or two each and they compound; the last three are
research bets.

1. **Suppress the hubs in the index.** Score per setting and take the best
   setting for each tune, or divide by tune size BM25-style. Paired against
   the headline. Also check whether hubs distort set decoding, since a hub is
   hard for the prior to dislodge. Superseded in the long run by the profile
   (angle 4), which makes a tune one object rather than a union.

2. **Metrical weight in the matcher.** Two forms, not exclusive. In the
   aligner, scale the match and mismatch cost by the notated slot's weight;
   the weight comes from the notation's side, which is exact, so no beat
   phase is needed on the audio. As a third reading, a skeleton of the
   strong-beat notes only, two a bar on a reel, fused with the plain and
   eighth readings; this needs the bar phase, which the pulse estimator
   cannot find on reels, so the matcher tries every phase (two for a half-bar
   skeleton on a reel, three on a jig) and keeps the best, which also answers
   the open beat-phase question. Weights fitted from the disagreement rates
   above rather than hand-set; the player's list is the sanity check.

3. **A note lattice instead of one best transcription.** Align the three
   trackers' note strings ROVER-style; where they disagree keep both pitches
   with a weight; every n-gram path votes with its product of weights
   (PSPL). Attacks one-error-kills-six-phrases directly and can exceed the
   per-segment oracle because it combines within a segment.

4. **A profile per tune: the settings overlaid.** The player's idea, and
   the natural home for angles 1, 2 and the learned costs. Cluster a tune's
   settings by pairwise alignment (The Mason's Apron becomes two or three
   profiles, and a tune whose settings cluster badly is flagged for a person
   to name a canonical setting), align each cluster's settings to each other,
   and at every eighth slot of the form record the distribution of scale
   degrees relative to the tonic. A slot where 33 of 35 settings agree is a
   strong test; a three-way split is nearly free to miss. Score a
   transcription against the profile with insertions and deletions (a profile
   HMM, or the aligner with per-slot costs). Per-slot certainty, metrical
   weight and per-slot idf across tunes ("how many tunes have this degree at
   this structural position") multiply. Tunes with one setting get the
   per-type per-slot rates above as a smoothing prior. The n-gram index stays
   as the candidate generator; the profile scores the shortlist. Query side:
   the key estimate's tonic, or the aligner's twelve transpositions.

5. **A consensus query from the tune's own repeats.** Find the period by
   self-alignment of the interval string (8, 16 or 32 bar lag), align the
   passes jointly, vote per eighth; random tracker errors cancel and
   systematic ones survive, and the disagreements become the lattice weights
   for angle 3. The period gives form (part count and length), which the
   corpus holds and the reranker can use, and bar phase. This is "by the
   second time through" made mechanical.

6. **A learned error model in the aligner.** Meek and Birmingham's trainable
   noisy channel: substitution, insertion and deletion costs fitted from
   query and target pairs. The drawn tunes and the aligned confirmed
   performances are the training data. Concretely: a semitone substitution
   cheap, a fifth-low substitution cheap on whistle passages, a 60 to 80 ms
   insertion beside the same pitch nearly free because it is an ornament.
   Tunepal's OFAH rounding of ornaments to zero quavers is the same idea done
   on the audio side, and `particalize` half does it already.

7. **A learned reranker over the shortlist, which is also the calibrator.**
   Logistic over the top 25, fitted leave-one-night-out, over the signals that
   each measured within noise alone: type from the pulse, in-key fraction,
   coverage, aligner score, tracker agreement, form, tune-length fit, the
   transition prior. Its output is the maybe / probably / certainly promise.

8. **Match without transcribing, as a reranker.** Chroma from the audio
   against chroma rendered from each shortlisted setting, subsequence DTW or
   Serrà's cross-recurrence (librosa, Essentia). The stronger version is
   CTC-trained chroma from weakly aligned pairs, and the segment corpus, tune
   id plus rough start and end, is exactly that supervision.

9. **Give the trackers a session to hear.** PESTO is self-supervised, so it
   can be fine-tuned on unlabelled session audio with the test night held
   out. FolkFriend's synthetic pipeline, extended with pub noise and room
   responses, can fine-tune Basic Pitch. Beauguitte's tuneset is an
   independent check. Reels are the target. Separation before tracking is
   low on the list (see the RMVPE evidence and the HPSS result).

10. **CoverHunterMPS as a fourth expert.** Zero-shot first, as one more
    ranking in the fusion; then as a starting point for a cross-modal
    embedding fine-tuned on the segments. It has never heard a pub, but it is
    a different kind of evidence from a pitch tracker.

**Sequential evidence on the board** is outside the ten but larger than any
of them: the bench-to-board gap is 0.918 against 0.819. Accumulated
log-likelihood ratios per candidate over the span, the prior as a fixed
offset rather than one that fades as the temperature sharpens, and a
sequential test that commits when the margin between the top two clears a
bound. It is what lets the short list shrink as the second pass confirms the
first.

**Withdrawn: session-specific settings learned from confirmed
identifications.** Proposed, and the player declined it until consensus on
what is being played is very solid. Its evidence-gathering half survives as
the backlog item below.

## Backlog: "this session plays it differently" report

Not to be built now. A tune missed on several nights whose consensus
transcriptions (angle 5) agree with each other at slots where they disagree
with every setting is a repeatable variation, not tracker noise. The player
wants to see the same divergence from the notation on three nights before
believing it, shown as a notation diff against the nearest setting, and
delivered as a proposal to a session admin rather than as any change to the
index. If the admin agrees, the variant's natural home is a new setting on
thesession.org, which fixes it for everyone. The profile of angle 4 is what
makes "disagrees with every setting" a well-defined test.

## On fuzzy matching

The player asked whether `GGG GAB | ABA G` could be seen as a close match
for `GGG GAB | AGE G`. Under the n-gram index it cannot: every six-note
window spanning a changed note is a phrase the other tune lacks and never
votes, which is why phrase survival keeps coming up. Under alignment it is
two edits in ten, an 80% match, and the aligner already scores it so over
the shortlist. The profile makes the two changed notes cheap where settings
vary there, the metrical weight makes them cheap because they fall on
eighths 2 and 3 of the bar, and the lattice keeps the tracker's second
choice available at a doubtful eighth. Gapped n-grams with a wildcard slot
and shorter n with positional coherence are fuzzier index tricks, and belong
after the aligner because the aligner is where the fuzziness belongs; the
index only has to keep the right tune in the shortlist, which it does for
all but 6 of 502 segments today.
