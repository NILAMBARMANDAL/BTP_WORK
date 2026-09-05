# Data Pipeline

## Status: dataset research done, nothing downloaded/used yet

This document records real research into candidate Bengali speech datasets
(section 15 of the project spec: this is the implementer's responsibility, not
something to wait on the user for). **No dataset has been downloaded, and no
data has been used for anything beyond the synthetic gTTS smoke-test clips in
`ml-service/tests/fixtures/`** (see `RESEARCH.md`) as of this writing. Numbers
below are from web research (sources linked) — not independently verified by
downloading and inspecting the data ourselves yet. Treat them as reported, not
confirmed, until Stage 1 (below) actually happens.

## Candidate datasets

### 1. OpenSLR SLR53 — Large Bengali ASR training data set
- **Source:** https://www.openslr.org/53/ (also mirrored on Hugging Face as
  `openslr/openslr`)
- **License:** CC-BY-SA-4.0
- **Size:** ~196K utterances, ~204,905 audio files (WAV/FLAC), ~45,653 unique
  words, 70 unique characters in transcripts
- **Format:** WAV/FLAC audio + TSV transcription (FileID, UserID, transcription)
- **Speaker diversity:** multiple speakers/accents (crowdsourced), not
  independently verified by us yet
- **Suitability:** Good candidate for **Stage 1 baseline** (large volume,
  transcribed, permissive-ish license). CC-BY-SA-4.0's share-alike clause
  needs checking against how we plan to publish/use derived data before
  Stage 2 use — flagging as a licensing question, not deciding it here.
- **Limitations:** No documented dialect/regional breakdown found yet; quality
  of a crowdsourced/read-speech corpus for the kind of natural
  errors we care about (which is where Whisper actually makes mistakes) is
  unverified.

### 2. Mozilla Common Voice — Bengali
- **Source:** https://commonvoice.mozilla.org/ (Hugging Face:
  `mozilla-foundation/common_voice_17_0` or later, per-version datasets)
- **License:** CC0 (public domain dedication) — most permissive option found
- **Size:** ~399 hours total (v9.0 figure found), only ~56 hours (~14%)
  validated by community review at that snapshot; exact numbers grow with
  each Common Voice release, so re-check current version before use
- **Format:** MP3 clips + per-clip sentence + metadata (age, gender, accent,
  up/down votes)
- **Speaker diversity:** large number of distinct contributors (19,817 at the
  v9.0 snapshot), self-reported demographics available
- **Suitability:** Strong candidate for both Stage 1 baseline AND held-out
  evaluation, specifically because it has real (not synthetic) diverse
  speaker recordings with community-validated subsets, and CC0 avoids any
  share-alike complications for Stage 2 derived/published data.
- **Limitations:** Only the "validated" subset should be trusted for
  evaluation ground truth; the majority-unvalidated portion needs its own
  quality filtering before use.

### 3. AI4Bharat IndicVoices / IndicVoices-R — Bengali subset
- **Source:** https://ai4bharat.iitm.ac.in/datasets/indicvoices/,
  https://huggingface.co/datasets/ai4bharat/IndicVoices,
  https://huggingface.co/datasets/ai4bharat/indicvoices_r
- **License:** CC-BY-4.0 (permissive, commercial-use-friendly, per IndicVoices-R)
- **Size (Bengali, IndicVoices-R):** 111.99 hours (4.63 hours read speech +
  107.37 hours extempore/spontaneous speech), 1,979 speakers
- **Format:** speech + transcription; IndicVoices-R specifically targets
  ASR-quality transcripts intended to also support TTS
  **Suitability:** The extempore/spontaneous-speech majority is
  particularly relevant to us — spontaneous speech is exactly where Whisper
  errors (the thing we're correcting) are most likely to occur, more so than
  clean read-speech corpora like OpenSLR.
- **Limitations:** Smaller total hours than OpenSLR/Common Voice for Bengali
  specifically; dialect coverage not yet independently checked.

### 4. Bengali.AI / OOD-Speech
- **Source:** https://bengaliai.github.io/asr, arXiv:2305.09688
- **License:** Not confirmed from research so far — **must be checked before
  any use**, not assumed permissive.
- **Size:** ~1177.94 hours training (22,645 speakers) + 23.03 hours
  manually-annotated out-of-distribution test set (TV drama, audiobook, talk
  show, online class, religious sermons — 17 sources)
- **Suitability:** The OOD test set is exactly the kind of varied, real-world,
  non-clean-speech data useful for `EXPERIMENTS.md`'s "clean vs noisy vs
  fast/slow speech, dialect variation" analysis, if the license permits our use.
- **Limitations:** License unresolved (see above) — **do not use until this
  is checked and, if unclear, escalated per project rule "dataset has
  unclear licensing" (section 38).**

### 5. IndicSUPERB (AI4Bharat)
- **Source:** https://github.com/AI4Bharat/IndicSUPERB, arXiv:2208.11761
- **Note:** A benchmark suite (ASR + speaker verification + language ID +
  keyword spotting tasks) built partly on top of other Indic corpora rather
  than a single new raw-audio dataset. Worth checking later specifically for
  its **standardized evaluation splits**, which would help with the
  "protect evaluation data / speaker-disjoint splits" requirement
  (`RESEARCH.md`, spec section 32) rather than for training data itself.

## Recommendation (not yet decided — for user review before committing to Stage 2)

For **Stage 1** (baseline + error analysis, per spec section 16): Mozilla
Common Voice Bengali (CC0, real diverse speakers, validated subset available)
is the strongest first choice on licensing grounds alone; OpenSLR SLR53 as a
secondary/larger source once its CC-BY-SA-4.0 implications are confirmed
acceptable for our use.

For **Stage 2** (targeted correction data, i.e. the actual research
contribution's data): none of these datasets contain what we need — they're
all read/spontaneous speech with ground truth, not "Whisper got this word
wrong + a human re-pronounced it slowly/syllable-by-syllable + optional
meaning + accepted correction." That data can only come from the application
itself being used (see "Human-in-the-loop data" below), which is why Stage 1
existing-dataset work and Stage 2 application-generated data are explicitly
separate stages in the spec.

**This recommendation has not been acted on** — no download has happened.
Flagging per project rules: using any of these for real training/evaluation
work, and specifically the CC-BY-SA-4.0 share-alike question for OpenSLR and
the unresolved OOD-Speech license, are exactly the kind of "dataset has
unclear licensing" decisions that should be confirmed with the user before
proceeding, not decided unilaterally.

## Stage 2: human-in-the-loop correction data (from the app itself)

Captured per correction attempt (see `backend/src/models/CorrectionAttempt.js`
for the actual current schema — keep this section in sync with it):
session/speaker id, original audio reference, transcript, selected word +
index, original Whisper output, correction mode, attempt number, correction
audio reference, meaning/context (if given), model prediction, ranked
candidates + scores, accepted/rejected (user feedback), timestamp.

The critical distinction enforced in that schema — raw input vs. model
prediction vs. user feedback vs. validated correction vs. ground truth — is
detailed in `RESEARCH.md`.

**Not doing:** bulk/undirected recording of thousands of words before real
error patterns are known (explicitly against spec section 16). Stage 2 data
collection should be targeted at words Whisper actually gets wrong on Stage 1
data, once Stage 1 error analysis exists.

## Versioning strategy (planned, not yet implemented)

DVC is optional per spec; not introduced yet since there's no real dataset in
the repo to version. When Stage 1 begins, the plan is: a versioned dataset
manifest (JSON/CSV listing exact file hashes + source + license + split)
checked into `data/` metadata (not the audio itself, which stays gitignored
per `.gitignore`), so any experiment can record exactly which manifest version
it used. Revisit DVC if manifest files alone become unwieldy.

## Data splits (planned, not yet implemented)

Per spec section 32: speaker-disjoint splits are required once real data is in
use, to avoid the same or near-duplicate speaker/recording crossing between
train/validation/test/evaluation. Not yet implemented because no dataset has
been ingested. This section will be updated with the actual split methodology
used, once real.
