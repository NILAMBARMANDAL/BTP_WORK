# Data Pipeline

## Status (2026-09-07): Stage 1 real, in use; Stage 2 not started

This document records real research into candidate Bengali speech datasets
(section 15 of the project spec: this is the implementer's responsibility, not
something to wait on the user for), plus what actually happened once Stage 1
began. **OpenSLR SLR53 has been downloaded (a 200-sample subset, see below)
and is in active use** — the Whisper baseline (Experiment A), the
speaker-disjoint split, and Experiments B/C in `EXPERIMENTS.md` all run
against it. Every other candidate dataset below is still only web-researched,
not downloaded — those numbers are reported, not independently verified.
Stage 2 (real correction-attempt data from actual users) has not started; see
`PROGRESS.md`.

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

### 2. Mozilla Common Voice — Bengali — **ACCESS PATH CHANGED, re-verify before use**
**Update 2026-09-05:** Hugging Face's `mozilla-foundation/common_voice_*` dataset
pages now state *"Effective October 2025, Mozilla Common Voice datasets are
now exclusively available through Mozilla Data Collective"* — the HF mirror
this section originally described is no longer the access path. The
CC0-license and hours/speaker figures below are what was reported before that
move and have **not been re-verified against Mozilla Data Collective**. Before
relying on Common Voice Bengali, check its current terms on Mozilla Data
Collective directly — do not assume the CC0 license or these numbers still
apply unchanged.

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

## Actual acquisition attempt (2026-09-05)

Proceeded with OpenSLR SLR53 (CC-BY-SA-4.0, a clear license appropriate for
academic thesis use with attribution — not the kind of "unclear licensing"
that needs to block on user input) rather than waiting, per updated
instructions to take ownership of the data side. Real, verified facts from
this attempt:

- `data/raw/openslr_53/LICENSE` and `utt_spk_text.tsv` (15.8MB, 218,703
  transcript lines, real Bengali text) downloaded successfully and directly
  (no auth/gating) from openslr.org.
- The full audio is split into 16 zip shards (~900MB each, ~14.7GB total).
  **Downloading a full shard over this connection was too slow to be
  practical** (~5MB/min observed, i.e. ~3 hours for one shard) — this may be
  connection-specific, not necessarily a permanent constraint.
- The OpenSLR server supports HTTP range requests (`Accept-Ranges: bytes`
  confirmed via `curl -I`), so the plan is to fetch only the specific files
  needed for a small evaluation subset (e.g. via `remotezip`) rather than a
  full shard — avoiding a multi-hour download for what's meant to be a
  "scientifically defensible subset," not the full corpus.
- Mozilla Common Voice's Hugging Face access path changed in October 2025
  (see above) — not yet re-attempted through the new Mozilla Data Collective
  path.

**Acquisition completed (2026-09-06):** 200 samples fetched via `remotezip`
range requests (no full-shard download), built into a versioned manifest by
`scripts/build_manifest.py`, seed 42:
`data/processed/openslr_53_shard0_manifest.json`
(`manifest_sha256=ceb1f02c502b319e08e94bf474061b2e31c6fb503cb58583d344c2b0311f6b9`
— this hashes the exact sampled utterance-id/transcript/path selection, not
the full remote shard, which was never downloaded; see the script for why).
Total download for the 200 audio files: ~14MB (vs. ~900MB for the full
shard). This manifest was used for Experiment A in `EXPERIMENTS.md` — a real
Whisper baseline run, not a placeholder.

**Known limitations of this manifest, stated plainly:**
- Single shard (`asr_bengali_0.zip`) out of 16 — not a sample of the full
  SLR53 corpus, so speaker/dialect diversity claims can't be made from it.
- **Update (2026-09-06): now split.** `scripts/split_dataset.py` produced a
  speaker-disjoint train(140)/val(30)/test(30) split of this 168-speaker,
  200-sample pool (`data/processed/openslr_53_splits.json`, seed 42,
  greedy bin-packing by whole speaker group — see "Data splits" below). Any
  correction-method comparison should use the `test` split, not the full
  undivided manifest.
- A single random 200-sample draw; error-rate figures from it (see
  `EXPERIMENTS.md` Experiment A) are a real first measurement, not yet
  validated for stability across multiple draws or against a second dataset.

## Recommendation and what was actually done

Common Voice Bengali (CC0) would have been the strongest first choice on
licensing grounds alone. **Decision (2026-09-06, made autonomously per the
project's "proceed on routine dataset/engineering decisions" instruction):**
proceeded with OpenSLR SLR53 (CC-BY-SA-4.0) for Stage 1 instead, rather than
waiting further — a defensible research/eval use, not redistribution. This is
flagged explicitly, not silently decided: **if results or derived data from
this dataset are ever published, CC-BY-SA-4.0's share-alike/attribution terms
apply.** Common Voice Bengali remains a reasonable secondary/future source.

For **Stage 2** (targeted correction data, i.e. the actual research
contribution's data): none of these datasets contain what we need — they're
all read/spontaneous speech with ground truth, not "Whisper got this word
wrong + a human re-pronounced it slowly/syllable-by-syllable + optional
meaning + accepted correction." That data can only come from the application
itself being used (see "Human-in-the-loop data" below), which is why Stage 1
existing-dataset work and Stage 2 application-generated data are explicitly
separate stages in the spec.

Bengali.AI's OOD-Speech license remains unresolved and has not been used —
that decision (unlike the OpenSLR one above) is exactly the kind of "dataset
has unclear licensing" call that should be confirmed with the user before
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

## Versioning strategy (implemented for Stage 1)

DVC was not introduced — a plain versioned JSON manifest turned out to be
sufficient at this scale. `scripts/build_manifest.py` writes
`data/processed/openslr_53_shard0_manifest.json` (exact utterance IDs,
transcripts, source shard, and a `manifest_sha256` hash of the selection),
checked into `data/` metadata only (not the audio itself, gitignored per
`.gitignore`). Every experiment result in `EXPERIMENTS.md` records which
manifest (and its hash) it used. Revisit DVC if manifest files alone become
unwieldy at a larger scale (spec section 44).

## Data splits (implemented for Stage 1)

`scripts/split_dataset.py` implements the speaker-disjoint split spec section
32 requires: samples are grouped by `speaker_id`, then whole speaker groups
(largest first) are greedily assigned to whichever of train/val/test is
furthest below its target ratio — so no speaker's samples cross a split
boundary, verified by an in-script assertion. Applied to the 200-sample/
168-speaker OpenSLR SLR53 pool (seed 42): train 140/108 speakers, val 30/30,
test 30/30 — see `data/processed/openslr_53_splits.json` (gitignored,
reproducible from the manifest + seed) and `EXPERIMENTS.md` Experiments B/C,
which use the `test` split. This same script/method applies unchanged to any
future dataset addition (spec section 44 — no hardcoded dataset assumptions).
