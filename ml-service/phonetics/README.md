# Bengali phonetics — current approach and limitations

**Status: no validated, Bengali-specific pronunciation-dictionary or G2P
resource has been identified and evaluated yet.** This is a documented gap,
not an oversight — see `RESEARCH.md` "Known limitations".

## Current (interim) approach

We use `indic_transliteration`'s Bengali → ITRANS transliteration as an
approximate phonetic representation, and compute similarity between two Bengali
words as normalized Levenshtein distance over their transliterated forms
(`similarity.py`). This is a **defensible but unvalidated proxy**:

- It captures gross phonetic structure (consonant/vowel sequence) reasonably
  well because ITRANS is a phonemic (not purely orthographic) romanization
  scheme.
- It does **not** model Bengali-specific phonological phenomena precisely
  (e.g., inherent vowel deletion/realization rules, consonant cluster
  simplification in casual speech, regional pronunciation variation).
- It has not been benchmarked against human judgments of phonetic similarity
  for Bengali. Treat `phonetic_score` in ranking output as a heuristic signal,
  not a validated metric, until such an evaluation exists.

## Syllable segmentation

`syllables.py` implements a heuristic Bengali syllabification based on vowel
sign (matra) boundaries in the Unicode grapheme stream: a syllable boundary is
placed after each vowel nucleus (independent vowel, or consonant + dependent
vowel sign / inherent vowel), with conjunct consonants (via hasant/virama)
kept attached to the following consonant. This is a standard simplified
approach for Indic scripts, but it is **not** validated against a Bengali
linguistic reference corpus. It is used only to give the user instructions
("say it in N syllables") and to segment a user's syllable-by-syllable
recording for internal candidate generation — not as a scientific claim about
Bengali phonology.

## What would improve this

Candidate resources to evaluate before trusting phonetic scoring for
publication-quality results (not yet done):
- A Bengali pronunciation lexicon (e.g., from a Bengali TTS/ASR project with
  published G2P rules)
- AI4Bharat's Indic NLP resources, if they expose Bengali G2P
- A validated Bengali phoneme inventory cross-checked against these outputs

Until one of these is evaluated, this module's output must not be described in
any report as a validated phonetic distance — only as an engineering heuristic.
