# Ceol Listen — design conversation (pre-spec)

Transcript of the meta-level design conversation on 2026-09-21 that preceded
[053-ceol-listen-lab.md](../053-ceol-listen-lab.md). Kept verbatim so the
reasoning behind the spec's decisions survives. Speakers: Ian, Claude.

---

## Ian

I'm going to begin a new subproject here called Ceol Listen, which I've been preparing for for a while. The idea is that you turn on a recorder in the app that streams the recording to cloud storage, and right behind it, other workers start trying to interpret the audio to figure out what tunes are playing.

There are a LOT of ways we could approach this, but I think the name of the game is going to be ensemble methods where different niche expert AI models can try to pull some sense out of the recording (things like "is this music playing", "what notes are they playing", etc) and then it can try to assemble knowledge about what tune is playing as fast as it can. There's probably a trade-off between speed and certainty, and we'll want both fast best-guess suggestions that land as provisional, as well as more certain guesses that can replace them. We'll also learn more as the tune goes along and get more chances to be certain.

Let's have an open conversation (no multiple choice) about how we might design a system like this that can just keep getting better and more robust over time as we sink more compute and intelligence into it. I've been segmenting recordings of our session as training data, but there's also a lot of prior art to consider (apps like TunePal for example). Don't start actually desining solutions yet, let's stay at the meta level of how we can construct a milieu in which to create solutions.

## Claude

I read the segmenter spec so I'm anchored to what exists: a resolved view that yields labelled audio slices, and a live logger that already accepts ops from multiple people. Here is how I'd think about the milieu.

**The eval harness is the actual product.** "Keeps getting better as we sink in compute" only holds if there is a fixed thing to get better *at*. Your segmented corpus is the seed of that, and I'd treat it as evaluation data first and training data second. Every candidate expert, every fusion strategy, every prior gets scored on the same held-out sessions with the same metrics. Without that, ensembling degenerates into adding models and hoping. The metrics should mirror the user experience rather than model accuracy in the abstract. Time to first correct guess. Time to confident guess. How often a provisional guess is wrong and gets shown anyway. Cost per minute of audio. That last one matters because the interesting design space is a curve of latency against certainty, and you want to see the whole curve, not one point.

**Replay is what turns compute into improvement.** Every live recording should be a replayable stream, and the live pipeline and the batch pipeline should be the same code with a different clock. New idea, replay the corpus at fifty times realtime, score, compare, ship or discard. This is also how you avoid the trap of experiments that only run in a notebook. If the replay harness is built first, everything after it is cheap to try.

**A blackboard, not a pipeline.** The old speech-recognition architecture fits this problem well. There is a shared board of timestamped evidence. Experts read from it and write typed observations back with confidence, provenance, and the input window they looked at. A hypothesis assembler reads the board and maintains a ranked set of tune hypotheses over time spans. The point is that experts only agree on the interface. Adding one, deleting one, or running two versions side by side is free. The fusion layer is where the hard work lives, and isolating it means you can iterate on it without touching the experts.

**Non-audio evidence is a first-class expert.** This is Ceol's real advantage over TunePal, which listens in isolation. You know which session this is, what its repertoire is, what has already been played tonight, that tunes come in sets of the same type, and who is sitting at the table. A prior that says "this session plays these four hundred tunes" collapses the search space before any audio is examined. If the milieu treats priors as just another writer to the board, they compose with the audio experts naturally.

**Hypotheses need a lifecycle contract.** Proposed, shown as provisional, confirmed, superseded, withdrawn. The live logger's op vocabulary from spec 024 already gives you a place for these to land. Fixing the contract early means the backend can change completely while the UI stays stable. It also lets you measure the thing users feel, which is provisional guesses flipping.

**The ground truth flywheel.** The segmenter is a bootstrap. The sustained feed is people at sessions confirming or correcting suggestions as a byproduct of logging, not as a chore. Design that loop now. But watch two failure modes. Tired humans accept whatever the model suggests, which poisons labels toward the model's own biases. And session recordings share room acoustics and players, so a corpus split by tune rather than by session will look far better than it is.

**Provenance everywhere.** Model version, feature extractor version, corpus snapshot, prior version, fusion strategy version. If a result cannot be attributed to a specific configuration, the improvement cannot be reproduced or trusted.

**Compute tiering as a scheduling problem.** Cheap experts run on every chunk. Expensive ones run when triggered, on a boundary or when uncertainty stays high. The scheduler should reason about value of information rather than running everything always. This is where "more compute" actually plugs in.

**On prior art.** TunePal transcribes to a pitch sequence and does edit-distance search over the thesession.org ABC corpus. That works because trad is close to monophonic and the symbolic corpus is huge. Shazam-style fingerprinting fails because performances vary. The learned end of the spectrum is cover-song identification and audio embedding models, which need your labelled corpus and generalise differently. The meta point is that the symbolic route and the learned route make different mistakes, which is exactly why an ensemble is worth building. The milieu should make both routes equally easy to plug in.

**Where the code lives.** I'd keep a lab layer and a runtime layer separate. The lab layer is the replay harness, experiments, and scoring, in the spirit of the existing spike directory but with structure. The runtime layer is a worker that consumes the stream. Nothing should go into the runtime that has not been scored in the lab.

Questions I'd want answered before designing anything:

- How much labelled audio exists now, in hours and in distinct tunes? That decides whether the corpus is for evaluation only or also for training.
- What latency counts as useful at the table? Ten seconds and sixty seconds lead to different architectures.
- Does anything run on the phone, or is the phone purely a microphone?
- Is thesession.org's ABC corpus fully mirrored locally, or fetched per lookup?

## Ian

Love:
- My data is really EVAL set rather than training. (I will also add more to that data over time as I segment more sessions.)
- Replay harness is central to the whole thing
- Blackboard, yes. I assume this is DAG-like in some sense - for example, if one expert can find tunes based on ABC, it relies on another upstream expert to be able to produce ABC. Not a linear pipeline (there could be multiple ABC creators who disagree) but still dependencies. Right?
- Strong agree about extra-audio evidence. Another serious advantage over tunepal is that this thing keeps getting more evidence as the seconds tick by, rather than having to guess its best guess after 10 seconds and that's it. That's in two dimensions: we keep hearing more audio (people play tunes multiple times, usually), and the experts can keep working and weighing in. By the 3rd time through most tunes, I've got to imagine the "certainty needle" is pretty high. And the live logging screen expects this btw, new top-level best-guesses can stream in and replace older ones, with higher confidence each time, and you can watch it happen. (You can also shortcut it, and save some cycles & compute & money, if a human clicks "you got it".)
- Good observation about session recordings sharing players and acoustics. We may want to model in that the system "learns" things about the right ensemble methods to use, and their parameters, per session (or maybe even more fine grained - we sometimes do our session outside on the patio which has VERY different acoustics). It's OK for the things that work for one session to be different from another. Hell, things might even be learnable within a night compared to other nights ("man the flute is REALLY loud tonight and he sucks")
- YES provenance, first class support everywhere. I want to be able to go back and retry every pipeline we've ever run (if we feel like it) when a new better audio->ABC model turns up.
- I love what you say about reasoning about the value of information, yes. When we have high certainty that this is Father Kelly's after 10 seconds, we don't need to bring in the trans-dimensional warp audio quantum fixation.
- Thanks for clearly explaining that there's symbolic and neural alternatives, and yes, those both go in the ensemble. I have a STRONG hunch that symbolic always wins here, in part because Irish music is itself so varied, everyone plays the tune slightly differently on their own instrument and differently every night and different people come together. It's very unlike a beatles cover band trying to sound like the beatles. And there are many tunes that are SO similar, you really have to get the tone sequence to tell The Sligo Chorus from the Westport Chorus.
- Love the lab / runtime distinction.

For labeled audio now, just a few hours / few hundred tunes, but I'm working on adding more.
Latency: I really would like it to get it faster than a human can type it. I guess we'll see if that's reaonable, but I don't want to architecturally preclude very fast responses, nor do I want to rule out cases where it was still thinking about it and only figured it out the next day.
- Nothing on the phone I think, just a mic. Right? Should something run on the phone?
- Assume that we've got the ABC we need locally, yes.

## Claude

Taking your points in turn, with pushback where I have it.

**The DAG is over evidence types, not over experts.** An expert declares what it consumes and what it produces. The ABC matcher consumes "symbolic transcription over a span" and doesn't care that three different transcribers wrote it. That's the dependency structure you're describing, and it's right. Two refinements. First, it's a reactive dataflow rather than a build graph. The matcher reruns whenever a new transcription lands on the board, and a transcription of the third pass through the tune is a new input, not a replacement. Second, don't make it strictly acyclic. Hearsay-II's key insight was that top-down flow matters too. A strong tune hypothesis can feed back to the transcriber as an expectation, which is how humans do it when they hear a garbled phrase and still know what tune it was. The way to keep feedback from becoming a mess is provenance. Every observation records exactly which upstream observations it depended on, so a loop is visible and re-computation is well-defined.

**Repeats are the whole game, and the board should treat them structurally.** You named two dimensions, more audio and more thinking. There's a third. Trad tunes are AABB played three times, so by the end you have six hearings of the A part. Those are six noisy transcriptions of the same melody, and aligning and voting over them is the same trick as consensus sequence assembly in genomics. The milieu should make "the same span heard n times" a natural aggregation rather than a special case. This is also why the human shortcut is more valuable than saving compute. When someone types the tune before the machine finds it, the machine switches from identify to verify and timestamp. Every live session with a human logger then auto-segments itself, and your corpus grows without you spending evenings on the waveform.

**Per-session learning needs shrinkage or it will lie to you.** With a few hundred labelled tunes, per-session ensemble weights overfit instantly. I'd split the idea in two. Context estimation is cheap and unsupervised. Gain, noise floor, dominant instrument, tempo, and room reverb get estimated fresh in the first few minutes of any night, no labels needed, and the patio just falls out of that. Learned weights are the expensive kind. Those should be hierarchical, global defaults with session-level and night-level adjustments that shrink hard toward the parent unless the evidence is strong. The loud flute is context estimation. Whether to trust transcriber A over transcriber B at this session is learned weights, and you'll need many nights before that's a real signal.

**Provenance implies a run is the unit of work.** A run is a named configuration applied to a recording, and every result is keyed by run. Re-running everything with a new transcription model is a new run id over the whole corpus, and the harness compares runs. The one honest caveat is that neural models on GPUs aren't bit-for-bit deterministic, so reproducible means within tolerance, and the harness should know that.

**Value of information is built on calibration, not accuracy.** Stopping early on a confident wrong answer is the failure mode that would make this feel broken. So the harness has to measure whether ninety percent confidence is right ninety percent of the time, per expert and for the fused output. Each expert declares its cost in latency and money. Early on the scheduler can be hand rules. The milieu just needs the hooks so the rules can be replaced by something learned later.

**Your symbolic hunch is mostly right, but I'd reframe it.** Symbolic matching wins at identification given a good transcription, and it's the only thing that scales to the long tail. End-to-end learned identification with a few hundred labelled tunes against forty thousand on thesession.org is impossible. It can only ever cover the repertoire it has heard. But the transcription step is where neural methods will do the heavy lifting, because a pub in full heterophony is not something rule-based pitch tracking handles well. So it isn't symbolic versus neural for the same job. It's neural front ends feeding symbolic back ends, and the symbolic layer is itself a family of experts with different intermediate representations. Interval sequences, contour, rhythm patterns, and absolute pitch each fail differently. Sligo Chorus versus Westport Chorus makes another point. The honest output is often "one of these two," and the hypothesis contract should carry a distribution, not a top-one, so the UI can show that state truthfully rather than flip-flopping.

**Latency has an upload problem before it has a model problem.** Faster than typing is plausible for a known tune with a repertoire prior. It requires streaming in small chunks and experts that emit over partial windows, and it requires that the board never closes, so the next-day answer is just a later run. What could kill it is a pub with bad cell coverage. Which brings me to the phone.

**Keep the phone dumb but make it a good mic.** Anything computed on the phone lives outside the lab, can't be replayed, and can't be re-run with provenance. So no models there for a long time. But the phone should be a durable buffer with resumable upload, and it should probably send two rates. A low-bitrate stream for speed and the master afterwards, kept apart exactly as spec 050 already insists. The live pipeline hears the proxy, and any run that matters is redone on the master. Multiple phones at one table is also a genuine input rather than a nuisance, because two microphones in different places hear different instruments.

**On eval data, two things.** A few hundred tunes gives wide confidence intervals. Two-point differences between runs will be noise, so the harness should report uncertainty and slice by instrument, conditions, and tune type. And you can build a much larger synthetic tier by rendering thesession.org ABC to audio with varied instruments, tempos, ornamentation, and room noise. It's untrustworthy as a final score but excellent for training transcribers and for testing the symbolic matcher in isolation. The milieu wants tiers of eval data with different trust levels, and the real corpus stays gold.

One framing I'd carry forward. The live logger already accepts ops from multiple humans. The recognizer is just another participant with its own identity and provenance, proposing and retracting. That keeps the whole listening system decoupled from the UI, which was the point of spec 024.

## Ian

Agree with all. OK, what's a meaningful way to get started? Maybe build a steel thread of the simplest group of experts that exercises all the concepts we've talked about here and try some actual runs of identifications against our eval set (which is in prod but you're welcome to copy it into the lab)? I wouldn't expect it to be right, but it should be runnable and then we can look at each part and ask if it's doing what we expect?

## Ian (2026-09-22, reviewing the plan)

First, something we didn't talk about it that it seems like a very first thing it'll need to be able to do is tell the difference between "a tune is being played" and not. Right? Is that in the plan? One simple thing it could try to do is closely reproduce the segments (regardless of what tune it is).

## Claude

Partly, and the part that's there is too thin. The plan has a `music_gate` expert that says "is anyone playing" from energy and onset density. It's used to close hypotheses on silence and to let the scheduler skip transcription. The eval never scores it. Nothing in the plan measures whether the system finds the *boundaries* the segments record.

Your framing is better, and it splits into two problems the ground truth distinguishes:

- **Music versus not.** Gaps between sets, chatter, tuning. Cheap features do a fair job here.
- **Tune boundaries inside a set.** Tunes change with no silence at all. This needs musical cues: key change, tempo change, the AABB repeat structure breaking, and eventually "the transcription stopped matching what it was matching". The assembler's biggest listed weakness is exactly that it has no boundary detection, so a three-tune set becomes one hypothesis superseded twice.

One data caveat matters here. An implicit end means "until the next segment starts", so an implicit end at the end of a set silently absorbs the chatter that follows. Inside a set, implicit ends are accurate tune boundaries. For music-versus-not, only explicit ends are trustworthy ground truth. The segmentation eval has to know the difference, and the manifest already carries `end_is_explicit`.

What I'd add to the plan:

- A `boundary` observation type and a first `boundary_energy` expert, so segmentation is a producer like any other and better ones plug in beside it. The assembler opens and closes hypothesis spans on boundaries, not only on silence.
- A segmentation eval that ignores tune identity: boundary recall and precision within a tolerance of a few seconds, false boundaries per hour, and frame-level music-activity accuracy scored only where ground truth is trustworthy.
- One more listed step, between the pitch experts and the matcher, so it can be checked in isolation with the timeline tool.

It is also the cheapest thing in the whole system to get good at, and it pays out everywhere: the identification eval gets cleaner windows, the scheduler gets a real trigger for expensive experts, and the live flywheel gets automatic timestamps when a human types the tune.

## Ian

Let's not assume you'll notice the boundary from energy; this happens in a noisy pub and somtimes there are big waveforms outside of the tune. Perhaps there's a new concept we need here for creating theoretical experts in the first place - we know a condition or output we want to get from input and we have a bunch of examples, now we just need to get creative and try lots of things to see which ones have most promise and might get included in our ensemble eventually if they work well. Like, I suspect there might have to be an actual neural analysis to tell the difference sometimes (but I guess we can find out)

You're totally right about how important intra-set boundaries will be, BTW. It has to expect that the tune it was confidently nailing will, at some point, stop being the tune that's being played.

Is there any concept of chunking the audio into time regions here? Should we? Should everyone agree on the same set of chunks? Is chunk length a variable we should experiment with in the lab?

## Claude

Three answers.

**Don't assume energy, agreed. The missing concept is a task bench.** Right now the plan has one loop: define an expert, wire it into the board, run the ensemble, read the eval. That loop is far too slow for "try twenty ideas and see which has promise". What you're describing is a second, faster loop:

- A **task** is a named target with a scorer, derived from the corpus. "Is music playing, per second." "Is there a tune boundary within three seconds of here." "Which of these two tunes is this." Each has a labelled dataset cut from the same eight nights.
- A **candidate** is any function from cached features over a window to a prediction. A rule on RMS, a self-similarity novelty curve, a key-change detector, a small classifier on mel spectrograms, a probe on a pretrained audio embedding, a "my transcription stopped matching" signal. Rule-based and learned candidates sit on the same bench and get the same score.
- **Features are cached once** per recording, so fifty candidates cost fifty cheap passes, not fifty decodes.
- A candidate that scores well **graduates** into an expert with a version number and joins the ensemble. The bench's score is its provenance for why it's there.

On neural: I think you'll need it for some of this, and the bench makes finding out cheap. One honesty point about your eval-only data. Training a small classifier on it and evaluating on it is fine only with leave-one-night-out splits, since nights share room and players. The bench should enforce that split rather than trust each candidate to do it.

**Intra-set boundaries.** Yes, the assembler must expect its confident tune to stop. Two cheap non-audio cues belong there from the start. Your median segment is 110 seconds, which is three times through AABB, so elapsed time since the span opened is itself evidence that a change is due, and the tune type sets the expected length. And a boundary observation from whatever detector wins the bench should open a new span directly rather than waiting for a rival's evidence to overtake the old one.

**Chunking.** The plan has it, but conflates two things that should be separate:

- **Arrival chunks** are how audio lands on the board and what advances the clock. In the lab that's a replay parameter. Live, it's the upload granularity and a hard floor on latency. Everyone shares these because they define "what has been heard so far".
- **Analysis windows** are what each expert reads, and experts should not be bound to arrival chunks. A pitch tracker wants a few seconds. A boundary detector wants thirty seconds of context on both sides. A matcher wants the last forty notes regardless of time. So each expert declares its own window length and hop, reads any range of audio up to the current clock, and stamps its observation with the window it actually used. That also fixes the "chunked pyin is worse than whole-file pyin" weakness in the plan, since pyin can read ten-second windows on a two-second hop.

Both are worth sweeping in the lab. Arrival chunk length is the latency-versus-quality curve you said you wanted to see. Window length and hop are per-expert parameters and belong in the run config. The one constraint is that windows should sit on a fixed grid so the cache hits across runs.

---

## Decisions taken during planning (2026-09-21 and 22)

Asked and answered before the plan was written:

- **ABC corpus**: the public thesession.org data dump (all tunes, all settings), not only the ABC already in Ceol's database. The long tail is needed as distractors; the session repertoire prior narrows it.
- **Lab location**: a `lab/` package in this repo, reusing `recording.py` and `database.py`, with its own requirements file and excluded from deploy, coverage, and root pytest collection.
- **Board store**: SQLite under `lab/data/`; the runtime version will be Postgres with the same schema.
- **Prod access**: read-only queries via Render for sizing; AWS credentials added to the local `.env` for pulling master audio.

Prod eval set as sized that day: 8 segmented recordings (ids 1, 2, 3, 4, 5, 138, 139, 140), 455 segments, 274 distinct tunes all with ABC, 15.6 labelled hours, median segment 110 s, one 5,475 s trailing implicit end. Session 1 repertoire 1,279 tunes.

Added 2026-09-22 after plan review:

- **Task bench**: a second, fast loop. Tasks (`music_activity`, `boundary`, later `tune_pair`) with labels cut from the corpus, candidates scored leave-one-night-out over cached features, graduation into experts. Nothing joins the ensemble without a bench score.
- **Boundaries are first-class**: a `boundary` observation type; the assembler closes and reopens spans on it and carries a duration hazard. The first producers are bench baselines, not assumptions.
- **Arrival chunks vs analysis windows**: chunks advance the clock; each expert declares its own grid-aligned window and hop and reads any audio up to the clock. Both are swept in the lab.
- **Implicit ends are not activity labels**: only explicit ends mark the end of music.
