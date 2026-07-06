# AI201 Project 4 — Provenance Guard

A backend system for creative-sharing platforms to classify submitted content as AI-generated or human-generated, with transparent reasoning, an appeals process, and a full audit trail.

---

## Detection Signals

The system uses three active signals plus one planned-but-stubbed signal:

- **`lexical_tics`** (LOW→MEDIUM weight) — density of AI-associated transition phrases ("moreover," "furthermore," "it is important to note"). Weight scales with hit count: a single incidental tic is weak evidence, but 2+ tics in one sample is a much harder pattern to produce by coincidence.
- **`structural_symmetry`** (MEDIUM weight) — paragraph-length variance. Even, uniform paragraph lengths across a sample suggest templated coverage; genuinely asymmetric attention (writing more about what you actually care about) suggests a human author.
- **`sentence_rhythm`** (MEDIUM weight) — sentence-length variance, requiring 5+ sentences to fire. This was raised from an initial threshold of 3 after testing showed small samples produced statistically meaningless, confidently-wrong results (see AI Usage section below).
- **`cross_reference`** (HIGH weight, stub) — intended to compare voice against known prior writing from the same author. Currently returns neutral in all cases, since no reference corpus is wired in yet.

**Why these signals, specifically:** the goal was to combine signals that fail in *different* ways, so no single blind spot dominates the result. `lexical_tics` is cheap and immediately actionable but easy to prompt away. `structural_symmetry` and `sentence_rhythm` catch different structural habits (paragraph-level vs. sentence-level) that are harder to consciously control while writing. `cross_reference` is the only signal that constitutes direct evidence rather than inference — everything else is a proxy.

**What I'd change for a real deployment:** `cross_reference` is the single biggest gap. Without it, the system structurally cannot reach `strong_human` confidence at all — the three additive signals cap out at -4, one short of the -5 threshold, because `lexical_tics` only ever votes AI or neutral, never human. A real deployment needs either a working reference-corpus comparison or an explicit acknowledgment that "high confidence human" is currently unreachable through text analysis alone.

---

## Confidence Scoring

**Approach:** signals are tiered by reliability (LOW/MEDIUM/HIGH) rather than voted equally, and the output is a **confidence band**, not a raw point score — "indeterminate," "lean_ai," "strong_ai," etc. This was a deliberate choice: a number like "73% AI" implies a precision the underlying signals don't actually support. The system can reliably distinguish "no real evidence" from "a real, if weak, lean" from "strong agreement across signals" — it cannot reliably distinguish 60% confidence from 65%.

**Why bands over a single score:** a flat numeric average lets many weak, noisy signals (like a single incidental transition word) silently outvote what should be treated as much stronger evidence. Bands force the weighting to be explicit and force the final label to reflect evidence *quality*, not just evidence *count*.

### Example: two submissions with meaningfully different scores

From Milestone 4 testing (see `test_pipeline.py` results):

**High-confidence case — `clearly_ai`:**
```
lexical_tics: ai (MEDIUM) — 2 tic phrases in 43 words
structural_symmetry: neutral — too few paragraphs to assess
sentence_rhythm: neutral — too few sentences to assess reliably
→ combined score: 2 | band: lean_ai | label: "Likely AI-generated"
```

**Lower-confidence case — `borderline_formal_human`:**
```
lexical_tics: neutral — no tic phrases found
structural_symmetry: neutral — too few paragraphs to assess
sentence_rhythm: neutral — too few sentences to assess reliably
→ combined score: 0 | band: indeterminate | label: "Uncertain"
```

These aren't cherry-picked to look different — they're the actual outputs from the same pipeline run against different inputs, which is the point: the score moves in response to actual detected evidence rather than staying constant.

---

## Transparency Label — All 3 Variants (Exact Text)

**`high-confidence-ai`** → displayed label: **"High Confidence: AI-Generated"**

Stylistic Patterns:
- Use of transitional words such as ("Furthermore", "However", "In conclusion")
- Uniformity in sentence length and rhythm; paragraphs share the same pattern and have the same weight
- Em dash overuse

Structural Patterns:
- Predictable essay structure
- Generic and even coverage of topics; no added insight or emphasis on specific topics
- Headers that restate the obvious

Content-level patterns:
- Confident tone applied uniformly, even to opinionated or uncertain claims
- Plausible-sounding errors rather than careless mistakes
- Surface-level synthesis

---

**`high-confidence-human`** → displayed label: **"High Confidence: Human-Written"**

- Genuine asymmetry: the writer spends a lot of time writing about the topic they genuinely care about and not putting as much effort on the rest
- Recurring verbal tics, specific slang, inside references
- Errors that are careless rather than plausible (typos, wrong words used)
- Precise but contextually weird details

---

**`uncertain`** → displayed label: **"Uncertain"**

- Integrated generative AI content that has been heavily edited by a human
- Concise and specific prompting — a user feeds a system a prompt that is extremely detailed and precise
- Short-form content — things like captions, tweets, comments are too short to pinpoint where it originates exactly
- Detection tools being unreliable — many AI detection models are not equipped with sufficient data to assess newer models and paraphrased text

---

## Rate Limiting

`/submit` is limited to **10 requests per minute, 100 per day** per client (by IP), via Flask-Limiter with in-memory storage.

**Reasoning:** a real writer submitting their own work rarely submits more than a handful of pieces per sitting — 10/minute comfortably covers legitimate iteration without feeling restrictive. 100/day caps sustained single-source usage without blocking a prolific user, while making a scripted flood immediately visible and blocked well before it could affect system load.

**Verified evidence (live run, 12 rapid requests against the real server):**
```
200
200
200
200
200
200
200
200
200
200
429
429
```
First 10 succeed, remaining 2 correctly rejected — confirms the limit is enforced, not just configured.

**Open questions**, not yet resolved:
- Fail-open or fail-closed if the rate-limit store goes down? (Currently assuming fail-open.)
- Should limits scale with the original classification's confidence level?
- These thresholds are starting estimates, not measured against real traffic — revisit after observing actual usage.

---

## Audit Log

Every classification and appeal is recorded as an append-only, structured entry (JSON), exposed via `GET /log` and persisted to `audit_log.jsonl` on disk.

**Each entry captures:** timestamp, content ID, the attribution result (confidence band + label), the combined score, each individual signal's own score/direction/weight, any modifiers applied, and whether an appeal has been filed against that case.

**Why append-only:** corrections become new entries rather than overwriting old ones, so a case's full history — original flag, appeal, any reversal — stays reconstructable after the fact.

**Why individual signal scores are logged, not just the final band:** without them, "indeterminate" vs. "strong AI" looks arbitrary after the fact. Logging the breakdown is what makes the score auditable rather than just asserted.

---

## Known Limitations (Honest Assessment)

**Specific failure case: short, single-paragraph, casually-written prompts that happen to contain one incidental AI-associated phrase.**

Concretely: a genuinely human sentence like *"I finished the report, and honestly, on the other hand, I think it needs more work"* would register a `lexical_tics` hit for "on the other hand" — a completely ordinary human phrase that happens to be on the tic list. Because `structural_symmetry` needs 3+ paragraphs and `sentence_rhythm` needs 5+ sentences to fire at all, a short single-paragraph message has **no other active signal to counterbalance that one false positive.** The system would report a real, if weak, AI lean on a sentence a human plainly wrote.

This isn't a generic "needs more training data" problem — it's a direct, structural consequence of two of the three signals requiring a minimum sample size that short-form content (captions, comments, single-paragraph replies) will never reach. Short content is disproportionately dependent on the least reliable signal in the system.

---

## Spec Reflection

**How the spec helped:** the explicit requirement that "a 0.51 confidence should produce a meaningfully different transparency label than a 0.95" directly shaped the band-based design. Without that constraint, it would have been easy to ship a single blended numeric score and call it done — the spec forced a harder question: what does the system actually know versus merely compute?

**Where the implementation diverged, and why:** the original architecture diagram treated cross-reference as one more additive signal in the weighted sum. During implementation, re-reading the diagram's own language — "Strong +human/AI-origin evidence (**overrides** weak signals)" — made clear that treating it additively was a misreading. Cross-reference was rebuilt as an override mechanism: when active, it fully determines the band, ignoring the other signals' votes, rather than blending with them. This diverges from a literal "sum all signals" implementation but matches the spec's actual stated intent more faithfully.

---

## AI Usage

**Instance 1 — Cross-reference aggregation logic.**
I asked the AI to implement the confidence-scoring aggregation described in the architecture diagram. Its first version summed all signals, including cross-reference, as one more weighted vote in the total. On review against the diagram text specifically, this was wrong — the diagram states cross-reference should *override* the other signals, not combine with them. I had it rebuild the aggregation so that when `cross_reference` returns a non-neutral result, it determines the final band directly, and the other signals' scores are logged but don't factor into that decision.

**Instance 2 — `sentence_rhythm` signal calibration.**
The AI's first implementation of this signal used a minimum of 3 sentences before computing variance. When tested against real required test cases, this produced a confidently wrong result: a genuinely AI-generated sample's naturally varied 3-sentence lengths were read as "human" (high variance), directly canceling out a correct `lexical_tics` detection on the same text. I had the threshold raised to 5 sentences, and the weighting logic changed so the signal stays neutral rather than voting on statistically unreliable small samples. This was caught by feeding the pipeline the assignment's actual required test cases, not by inspecting the code.

---

## Portfolio Walkthrough

https://drive.google.com/file/d/13DxtUPz2oOgBTjqOLwA9RB7jZ5EI7BhB/view?usp=sharing
