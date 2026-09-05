# Bengali phonetics — current approach and limitations

**Update (2026-09-05): espeak-ng integrated as the primary G2P method**,
replacing the ITRANS-heuristic as the default when available. This is a real
upgrade, not just a config toggle — see "Validated finding" below.

## Current approach

`phonetics/similarity.py` tries, in order:

1. **espeak-ng** (`phonetics/espeak_g2p.py`) — a real, established open-source
   G2P/TTS engine with explicit Bengali (`bn`) language support. Produces an
   ASCII phoneme transcription; similarity is normalized Levenshtein distance
   over that transcription.
2. **ITRANS transliteration heuristic** (`phonetics/g2p.py`) — used only as a
   fallback if espeak-ng isn't installed/reachable in the current environment.

Call `phonetic_method()` to check which one is actually active — always log
this alongside any experiment result, since the two are not equivalent.

### Validated finding (not fabricated — reproduced 2026-09-05)

espeak-ng transcribes both **সোনার** ("golden") and **শোনার** ("of hearing")
to the *identical* phoneme string `S'onar`. This independently corroborates
the observation from Whisper smoke-testing (`RESEARCH.md`) that স and শ are
genuine near-homophones in standard Bengali pronunciation — this isn't a
Whisper quirk, it's a real phonological fact, now confirmed by a second,
independent, established resource rather than just inferred from one ASR
model's behavior. Practical implication: **pronunciation-only correction
cannot be expected to disambiguate this class of error**, because the
ambiguity exists in the pronunciation itself, not in recognition quality.
This is exactly the kind of case `RESEARCH.md`'s Mode B (meaning/context)
hypothesis needs to be tested against.

### Setup

- **Linux / Docker**: `apt-get install espeak-ng` (already in
  `docker/ml-service.Dockerfile`). `shutil.which("espeak-ng")` finds it
  automatically — no config needed.
- **Windows (local dev)**: espeak-ng ships only an `.msi` installer, which
  normally requires admin rights. `ml-service/scripts/setup_espeak.ps1`
  downloads it and performs an admin-free "administrative install"
  (`msiexec /a`, which just extracts files rather than installing
  system-wide) into `ml-service/vendor/` (gitignored — not committed, ~37MB).
  Then set `ESPEAK_NG_EXE` / `ESPEAK_NG_DATA_PATH` in `.env` to the printed
  paths.
- If neither is available, the ITRANS fallback is used automatically — no
  crash, but a materially different (and less validated) similarity measure.
  Check `phonetic_method()` if results look surprising.

## Known limitations (of espeak-ng too — not a solved problem)

- espeak-ng is a rule-based TTS front-end, not trained on real Bengali speech
  corpora — its phoneme predictions for rare words, loanwords, and proper
  nouns are unverified and may not match real speaker pronunciation.
- No accuracy benchmark of espeak-ng's Bengali G2P against a human-verified
  phoneme reference has been done. Treat `phonetic_score` as a useful,
  better-grounded heuristic than before — still not a scientifically
  validated metric until such a benchmark exists.
- Regional/dialect pronunciation variation is not modeled.

## Syllable segmentation

Unchanged from before — `syllables.py` implements a heuristic Bengali
syllabification based on vowel sign (matra) boundaries in the Unicode
grapheme stream, used only for user-facing instructions ("say this in N
syllables"). Not validated against a linguistic reference corpus; see the
code comments for the exact algorithm.

## What would still improve this

- A human-verified Bengali phoneme reference set, to actually benchmark
  espeak-ng's accuracy (and decide if it's good enough, vs. needing a
  trained Bengali G2P model).
- AI4Bharat's Indic NLP resources, if they expose a trained Bengali G2P —
  not yet investigated.
