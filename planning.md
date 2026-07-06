## Detection Signals 
Signals are tiered by reliability, not treated as equal votes.

High weight: cross-reference mismatch vs. known prior writing,
verifiable fabrication (fake citation/quote). Hard to fake, rare.

Medium weight: structural symmetry (even coverage, no real
emphasis), specificity gap (generic vs. costly-to-invent detail),
error profile (plausible/consistent errors vs. careless ones).

Low weight: lexical tics (transitions, triplets, hedge-balance),
uniform confident tone. Common, easy to spot, easy to fake away.


Why tiered: low-weight signals are the most numerous, so a flat
tally lets noise dominate. Weighting keeps rare strong evidence
decisive over common weak evidence.

Modifiers cap confidence regardless of tally: short sample length,
formulaic domain, possible ESL authorship, possible AI-drafted-then-
edited content.

Output is a confidence band, not a point score — matches what the
signals can actually support.



## Multi Signal Detection Pipeline


                    ┌─────────────────────────┐
                    │      TEXT SAMPLE         │
                    └────────────┬─────────────┘
                                 │
                 ┌───────────────┼───────────────┐
                 ▼               ▼               ▼
    ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────────┐
    │ SIGNAL 1         │ │ SIGNAL 2         │ │ SIGNAL 3             │
    │ Lexical tics     │ │ Structural       │ │ Cross-reference       │
    │                  │ │ symmetry         │ │                       │
    │ Transition-phrase│ │ Paragraph-length │ │ Voice match vs. known │
    │ density          │ │ variance         │ │ prior writing         │
    │                  │ │                  │ │ (stub until reference │
    │ WEIGHT: LOW (1)  │ │ WEIGHT: MED (2)  │ │  corpus is wired in)  │
    └────────┬─────────┘ └────────┬─────────┘ │ WEIGHT: HIGH (3)      │
             │                    │            └──────────┬────────────┘
             ▼                    ▼                       ▼
    direction: ai/human/   direction: ai/human/   direction: ai/human/
    neutral                neutral                neutral (default)
             │                    │                       │
             └────────────────────┼───────────────────────┘
                                  ▼
                   ┌─────────────────────────────┐
                   │ AGGREGATION                  │
                   │ net_score = Σ (weight ×       │
                   │   direction_sign)             │
                   │                                │
                   │  +1 = AI, -1 = HUMAN,          │
                   │   0 = NEUTRAL, per signal       │
                   └────────────────┬───────────────┘
                                    ▼
                   ┌─────────────────────────────┐
                   │ MAP SCORE -> RAW BAND          │
                   │                                │
                   │  >= +5  strong_ai              │
                   │  +2..+4 lean_ai                │
                   │  -1..+1 indeterminate          │
                   │  -4..-2 lean_human              │
                   │  <= -5  strong_human            │
                   └────────────────┬───────────────┘
                                    ▼
                   ┌─────────────────────────────┐
                   │ APPLY MODIFIERS (CAP, NOT ADD) │
                   │  - short_sample                 │
                   │  - formulaic_domain              │
                   │  - possible_esl                  │
                   │  - possible_ai_edited             │
                   │                                    │
                   │ each modifier present pulls the    │
                   │ band ONE STEP toward indeterminate │
                   └────────────────┬───────────────────┘
                                    ▼
                   ┌─────────────────────────────┐
                   │ FINAL CONFIDENCE BAND          │
                   │ (strong_ai / lean_ai /          │
                   │  indeterminate / lean_human /    │
                   │  strong_human)                    │
                   └────────────────┬───────────────────┘
                                    ▼
                   ┌─────────────────────────────┐
                   │ AUDIT LOG ENTRY                 │
                   │  - confidenceBand                │
                   │  - signals[] (name, weight,       │
                   │    direction)                       │
                   │  - modifiers[]                       │
                   │  - actor, timestamp, notes             │
                   └─────────────────────────────────────┘


## Architecture

The submission flow categorized the submitted text based on it's length. If the submitted post is more than 150 words, the system analyzes the text based on 3 detection signals. The system uses a point system to tally up where the text stands in the AI detection band 
                           ┌─────────────────────────┐
                          │   TEXT SAMPLE RECEIVED   │
                          └────────────┬─────────────┘
                                       │
                                       ▼
                          ┌─────────────────────────┐
                          │  STEP 0: SAMPLE SIZE     │
                          │  CHECK                   │
                          │  Is there enough text?   │
                          └────────────┬─────────────┘
                                       │
                    ┌──────────────────┴──────────────────┐
                    ▼                                      ▼
            < ~150 words                              >= ~150 words
                    │                                      │
                    ▼                                      ▼
     ┌───────────────────────────┐          ┌───────────────────────────┐
     │ LOW CONFIDENCE CEILING    │          │  PROCEED TO FULL ANALYSIS  │
     │  +1 FOR UNCERTAINTY
        CONTINUE FOR ANALYSIS                └────────────┬──────────────┘
     │                            │                            │                       
                                                          │
     └───────────────────────────┘                         |
              |                                            |
              |                                            |
              |                                            |
              |                                            |
              |                                            │
              |                                            ▼
              |                         ┌─────────────────────────────────┐
              |                         │ STEP 1: VOICE CONSISTENCY CHECK  │
              |                         │ Does it sound like ONE person,   │
              |_>>                        │ or "good writing in general"?    │
                                       └────────────┬─────────────────────┘
                                                    │
                              ┌──────────────────────┴──────────────────────┐
                              ▼                                              ▼
                  Composite / generic voice                      Specific, recognizable voice
                              │                                              │
                              ▼                                              ▼
                  ┌───────────────────────┐                  ┌───────────────────────────┐
                  │ +1 toward AI-leaning   │                  │ +1 toward human-leaning   │
                  └───────────┬───────────┘                  └─────────────┬─────────────┘
                              │                                              │
                              └──────────────────┬───────────────────────────┘
                                                  ▼
                               ┌─────────────────────────────────────┐
                               │ STEP 2: STRUCTURAL ANALYSIS          │
                               │ - Even coverage across sections?     │
                               │ - Predictable architecture?          │
                               │ - Triplets / hedge-balance patterns? │
                               └────────────────┬──────────────────────┘
                                                │
                          ┌──────────────────────┴──────────────────────┐
                          ▼                                              ▼
              Symmetric, templated                          Asymmetric attention
              (equal weight everywhere)                 (cares more about some parts)
                          │                                              │
                          ▼                                              ▼
              ┌───────────────────────┐                    ┌───────────────────────────┐
              │ +1 toward AI-leaning   │                    │ +1 toward human-leaning   │
              └───────────┬───────────┘                    └─────────────┬─────────────┘
                          │                                              │
                          └──────────────────┬───────────────────────────┘
                                              ▼
                           ┌─────────────────────────────────────┐
                           │ STEP 3: SPECIFICITY TEST              │
                           │ Are there odd, costly-to-invent       │
                           │ details? (lived-experience markers,   │
                           │ inside references, messy facts)       │
                           └────────────────┬───────────────────────┘
                                            │
                      ┌──────────────────────┴──────────────────────┐
                      ▼                                              ▼
          Plausible but generic detail                  Idiosyncratic / "too specific
          (smooth synthesis)                             to make up" detail
                      │                                              │
                      ▼                                              ▼
          ┌───────────────────────┐                    ┌───────────────────────────┐
          │ +1 toward AI-leaning   │                    │ +1 toward human-leaning   │
          └───────────┬───────────┘                    └─────────────┬─────────────┘
                      │                                              │
                      └──────────────────┬───────────────────────────┘
                                          ▼
                       ┌─────────────────────────────────────┐
                       │ STEP 4: ERROR PROFILE                 │
                       │ Are errors PLAUSIBLE-sounding         │
                       │ (consistent fabrication) or           │
                       │ CARELESS (typos, dropped words,       │
                       │ broken logic mid-sentence)?           │
                       └────────────────┬───────────────────────┘
                                        │
                  ┌──────────────────────┴──────────────────────┐
                  ▼                                              ▼
        Plausible-sounding errors                      Careless / messy errors
        (confidently wrong)                            (sloppy, inconsistent)
                  │                                              │
                  ▼                                              ▼
      ┌───────────────────────┐                    ┌───────────────────────────┐
      │ +1 toward AI-leaning   │                    │ +1 toward human-leaning   │
      └───────────┬───────────┘                    └─────────────┬─────────────┘
                  │                                              │
                  └──────────────────┬───────────────────────────┘
                                      ▼
                   ┌─────────────────────────────────────┐
                   │ STEP 5: CROSS-REFERENCE (if possible) │
                   │ Compare against known prior samples   │
                   │ from the purported author             │
                   └────────────────┬───────────────────────┘
                                    │
                ┌────────────────────┴────────────────────┐
                ▼                                          ▼
       No reference material                    Reference material available
       available                                          │
                │                                          ▼
                │                            ┌───────────────────────────┐
                │                            │ Does voice/structure/error │
                │                            │ profile MATCH prior work?  │
                │                            └─────────────┬─────────────┘
                │                                          │
                │                       ┌───────────────────┴───────────────────┐
                │                       ▼                                       ▼
                │                  Matches well                          Doesn't match
                │                       │                                       │
                │                       ▼                                       ▼
                │           ┌───────────────────────┐             ┌───────────────────────────┐
                │           │ Strong +human evidence │             │ Strong +AI-origin evidence │
                │           │ (overrides weak signals)│             │ (overrides weak signals)   │
                │           └───────────┬───────────┘             └─────────────┬─────────────┘
                │                       │                                       │
                └───────────────────────┴───────────────────┬───────────────────┘
                                                              ▼
                                           ┌─────────────────────────────────────┐
                                           │ STEP 6: BLUR-ZONE CHECK               │
                                           │ Before concluding, ask:               │
                                           │ - Is this technical/legal/academic    │
                                           │   boilerplate? (naturally formulaic)  │
                                           │ - Is the author possibly ESL?         │
                                           │   (hedging ≠ AI signal here)          │
                                           │ - Could this be AI-drafted, then      │
                                           │   heavily human-edited?               │
                                           │ - Was the AI explicitly prompted to   │
                                           │   vary style / inject voice?          │
                                           └────────────────┬───────────────────────┘
                                                            │
                                  ┌──────────────────────────┴──────────────────────────┐
                                  ▼                                                      ▼
                       Any blur-zone factor applies                         No blur-zone factors apply
                                  │                                                      │
                                  ▼                                                      ▼
                  ┌───────────────────────────────┐                  ┌───────────────────────────────┐
                  │ CAP CONFIDENCE — report as     │                  │ TALLY SIGNALS FROM STEPS 1-5   │
                  │ "indeterminate" or "weak lean,"│                  │ → Net AI-leaning, human-leaning,│
                  │ state WHY explicitly           │                  │   or genuinely mixed            │
                  └───────────────────────────────┘                  └───────────────────────────────┘
                                                                                      │
                                                                                      ▼
                                                                       ┌───────────────────────────────┐
                                                                       │ FINAL OUTPUT:                  │
                                                                       │ State conclusion as a          │
                                                                       │ probability/lean, NOT a verdict│
                                                                       │ List which signals drove it    │
                                                                       └───────────────────────────────┘

## Appeals Workflow 

This appeal workflow classifies the submitted text and gives a reasoning for it. When the creator wants to appeal a classification, they must provide a statement and give supporting evidence to disprove the classification.
┌──────────────────────────────┐
│ STAGE 0: CLASSIFICATION       │
│ ISSUED                        │
│ - Confidence band recorded    │
│ - Signals/reasoning logged    │
│ - Creator notified w/ reasons │
└──────────────┬─────────────────┘
               │
               ▼
┌──────────────────────────────┐
│ STAGE 1: CREATOR NOTIFICATION │
│ Must include:                 │
│ - What was flagged            │
│ - Confidence band (not fake   │
│   precision)                  │
│ - WHICH signals drove it      │
│ - How to appeal + deadline    │
└──────────────┬─────────────────┘
               │
               ▼
┌──────────────────────────────┐
│ STAGE 2: APPEAL SUBMISSION    │
│ Creator provides:             │
│ - Statement of dispute        │
│ - Supporting evidence (see    │
│   evidence types below)       │
│ - Optional: process disclosure│
└──────────────┬─────────────────┘
               │
               ▼
┌──────────────────────────────┐
│ STAGE 3: TRIAGE               │
│ Route by original confidence: │
└──────────────┬─────────────────┘
               │
   ┌───────────┴───────────┐
   ▼                       ▼
LOW/MED confidence    HIGH confidence
original flag          original flag
   │                       │
   ▼                       ▼
┌─────────────┐    ┌──────────────────┐
│ FAST TRACK   │    │ FULL REVIEW       │
│ Single human │    │ Second reviewer + │
│ reviewer,    │    │ original evidence │
│ short SLA    │    │ re-examined,      │
│              │    │ longer SLA        │
└──────┬───────┘    └─────────┬─────────┘
       │                      │
       └──────────┬───────────┘
                  ▼
┌──────────────────────────────┐
│ STAGE 4: DECISION              │
│ - Uphold / Overturn / Modify   │
│   confidence band              │
│ - Written rationale required   │
│   (mirrors original disclosure)│
└──────────────┬─────────────────┘
               │
   ┌────────────┴────────────┐
   ▼                          ▼
Creator accepts          Creator escalates
(or doesn't respond)     (if eligible — see below)
   │                          │
   ▼                          ▼
┌─────────────┐    ┌──────────────────┐
│ CASE CLOSED  │    │ STAGE 5: ESCALATION│
│ Logged for   │    │ Independent panel, │
│ pattern      │    │ no original        │
│ analysis     │    │ reviewers involved │
└──────────────┘    └─────────────────────┘

## EVIDENCE TYPES FOR CONTENT CLASSIFICATION APPEALS
STRONG EVIDENCE
1. Edit history / version history
   - Examples: Google Docs revision log, Word track changes, git commit history
   - Why strong: Hard to fabricate convincingly; shows genuine drafting process
   - Reviewer note: Check for revision timestamps and incremental changes,
     not a single paste event

2. Process recording
   - Examples: Screen recording of the writing session
   - Why strong: Increasingly common as proactive defense
   - Reviewer note: Verify timestamps aren't doctored; check for continuous
     recording vs. edited clips

3. Prior writing samples for voice cross-reference
   - Examples: Previously published or submitted work by the same creator
   - Why strong: Enables direct stylometric comparison, not just inference
   - Reviewer note: Confirm provenance of the comparison samples themselves


MEDIUM EVIDENCE
4. Drafts / outlines predating the final piece
   - Examples: Earlier versions, notes, bullet-point outlines
   - Why medium: Shows iterative process, but could be created after the fact
   - Reviewer note: Check file metadata/timestamps where possible

5. Disclosure of AI-assisted (not AI-generated) workflow
   - Examples: Creator states they used AI for brainstorming, editing, or
     grammar checking, not full generation
   - Why medium: Reframes the question — many policies distinguish
     "AI-assisted" from "AI-generated"
   - Reviewer note: Assess against the SPECIFIC policy being enforced,
     not the classification alone


WEAK EVIDENCE
6. Third-party detector counter-results
   - Examples: Output from a different AI-detection tool showing "human"
   - Why weak: Detectors disagree with each other; not authoritative
     in either direction
   - Reviewer note: Can be noted but should not independently overturn
     a decision

7. Character / context testimony
   - Examples: "I always write like this," statements from colleagues
     or collaborators
   - Why weak alone: Useful as corroboration, not standalone proof
   - Reviewer note: Weight only in combination with stronger evidence above




## Anticipated Edge Cases 

DETECTION / SCORING
- Very short samples (< ~150 words): signal scores carry little
  statistical weight. Handled by the short_sample modifier, which
  caps the band toward indeterminate regardless of signal tally.

- Formulaic domains (legal, technical, academic boilerplate): human
  writing here naturally looks "templated," producing false AI-leaning
  signals. Handled by formulaic_domain modifier.

- Possible ESL authorship: hedging language and more uniform sentence
  structure are common in non-native English writing and overlap with
  AI-associated lexical patterns. Handled by possible_esl modifier --
  but this requires a way to detect/flag ESL likelihood without
  itself being a biased guess. NOT YET SOLVED -- currently requires
  manual flag input, no automated detection.

- AI-drafted, then heavily human-edited content: the most likely
  false negative case. Surface signals may look fully human after
  editing even though origination wasn't. No reliable signal exists
  for this today; possible_ai_edited modifier exists but has no
  automated trigger -- relies on self-disclosure or appeal evidence.

- All signals return NEUTRAL (e.g. stub signals with no reference
  corpus/fact-check available): net score = 0, band defaults to
  indeterminate. This is correct behavior, not a bug -- but worth
  confirming downstream consumers don't treat "indeterminate" as an
  error state.

- Conflicting signals (e.g. lexical tics say AI, error profile says
  human): net score may land near zero even with strong individual
  signals. Worth surfacing the conflict itself in the audit log notes,
  not just the net result, so reviewers can see disagreement rather
  than a flattened average.


SUBMISSION FLOW
- Empty or whitespace-only text submitted: should be rejected before
  reaching signal detectors, not scored as "indeterminate."

- Duplicate submissions of the same content under different caseIds:
  not currently deduplicated. Could be used to "shop" for a more
  favorable classification on retry.

- Extremely long submissions: may need a max-length cap or chunking
  strategy -- current signal detectors (paragraph/sentence variance)
  haven't been tested at scale and cost may grow with length if an
  LLM-judge call is added for specificity.


APPEAL FLOW
- Appeal submitted on a case that was already overturned/closed:
  needs explicit handling -- silently accepting it risks reopening a
  resolved case indefinitely.

- Appeal evidence references external links that later go dead
  (e.g. a Google Doc revision history link, since access/permissions
  can change): evidence should be captured/archived at submission
  time, not re-fetched live at review time.

- Reviewer overturns a case but the original audit log entry is
  ambiguous about which signals were actually disputed: makes it hard
  to confirm the appeal addressed the right thing vs. just asserted
  innocence generically.

- Rate limit (1 appeal per case per 7 days) collides with a creator
  who has legitimate new evidence shortly after a decision: needs an
  "add evidence to existing appeal" path, not just a hard block (see
  open question in RATE_LIMITING.md).


AUDIT LOG
- High submission volume: append-only log grows unbounded. Needs a
  retention/archival policy, not addressed yet.

- Concurrent appeal decisions on related cases (e.g. same creator,
  same content reposted): log entries are per-case, so cross-case
  patterns (repeat offender vs. repeat false-positive) aren't visible
  without a separate aggregation step.


NOT YET ADDRESSED (flagged, not solved)
- Automated ESL likelihood detection
- Automated AI-edited-content detection
- Deduplication across resubmitted/reposted content
- Log retention/archival policy
- Cross-case pattern auditing (bias/error-rate monitoring by signal)

## AI Tool Plan

### M3 — Submission endpoint + first signal

**Spec sections provided:**
- Detection signals section (signal definitions, weights, rationale)
- Architecture diagram (submission flow, arrow labels)

**What I'll ask for:**
- A Flask app skeleton with a `POST /submit` route accepting raw text
- The first signal function (lexical tics), matching the
  `detect_lexical_tics(text) -> SignalResult` shape already defined

**How I'll verify before wiring in:**
- Run the signal function directly against 3-4 hand-picked inputs
  (one obviously AI-tic-heavy, one obviously plain human writing, one
  edge case like a short snippet) and manually confirm the
  direction/weight output matches expectation
- Only after that passes, wire it into the `/submit` route and confirm
  the endpoint returns the signal result in the expected shape
- Do NOT trust the AI tool's own claim that "this works" — run it
  myself against known inputs first

### M4 — Second signal + confidence scoring

**Spec sections provided:**
- Detection signals section
- Uncertainty representation (confidence bands, not point scores)
- Architecture diagram

**What I'll ask for:**
- The second signal function (structural symmetry)
- The scoring/aggregation logic: weighted net score → confidence band
  mapping (per the thresholds already defined)

**How I'll verify:**
- Run the combined pipeline against a clearly-AI sample and a
  clearly-human sample, side by side
- Check: do the two scores actually diverge in the expected direction
  and by a meaningful margin — not just technically different by 1
  point, but separated enough to land in different bands
- If they don't diverge meaningfully, that's a signal the weighting or
  the signal functions themselves need adjustment before moving on,
  not something to paper over with looser band thresholds

### M5 — Production layer (labels + appeals)

**Spec sections provided:**
- Label variants (confidence band → user-facing label text)
- Appeals workflow (evidence types, review stages, status transitions)
- Architecture diagram (appeal flow, arrow labels)

**What I'll ask for:**
- Label generation logic mapping each confidence band to its
  corresponding transparency label
- The `POST /appeal` endpoint: status update logic + audit log entry

**How I'll verify:**
- Manually trigger all band-to-label mappings and confirm all three
  label variants are reachable (not just the two extremes — confirm
  "indeterminate" actually renders correctly too, since it's the
  easiest one to forget in testing)
- Submit a test appeal against a known case and confirm: status
  changes correctly, the audit log records the appeal action, and the
  response reflects the updated state
- Re-check rate limiting and audit logging still fire correctly with
  the new endpoint wired in — regression check, not just new-feature
  check

 ## Uncertainty Representation 
Output is a confidence BAND, not a point score. A number like "73% AI"
implies precision the underlying signals don't support — the system
cannot reliably distinguish 60% from 65% confidence, but it can
reliably distinguish "indeterminate" from "strong lean."

### Bands

    STRONG_HUMAN | LEAN_HUMAN | INDETERMINATE | LEAN_AI | STRONG_AI

- **STRONG_AI / STRONG_HUMAN** — reserved for cases with high-weight
  evidence (cross-reference match/mismatch, confirmed fabrication),
  not just a pile of low-weight signals pointing the same direction.
- **LEAN_AI / LEAN_HUMAN** — moderate evidence, no high-weight signal
  available or decisive.
- **INDETERMINATE** — signals conflict, are mostly neutral, or a
  modifier has capped the result regardless of signal tally.

### Why a band instead of a score

- A flat tally of many weak signals can look confident by volume
  alone, even when no individual signal is trustworthy. Bands force
  the output to reflect evidence *quality*, not just evidence *count*.
- A single number invites false precision and gets treated as
  authoritative by downstream consumers (e.g. "the tool said 80%,
  so..."), even when the underlying signal quality doesn't support
  that level of confidence.
- Bands are user-facing and defensible in an appeal — "indeterminate"
  is an honest answer; "62%" is not something a person can meaningfully
  contest or a reviewer can meaningfully re-derive.

### How the band is produced

1. Each signal contributes a weighted, directional score
   (see Detection Signals).
2. Scores sum to a net value, mapped to a raw band via fixed
   thresholds.
3. Modifiers (short sample, formulaic domain, possible ESL, possible
   AI-drafted-then-edited) cap the band toward INDETERMINATE — they
   reduce confidence, they don't get averaged into the score.
4. The final band, plus which signals and modifiers drove it, is what
   gets logged and shown — never a bare number alone.

### What ships with every result

- The band itself
- Which signals contributed and their direction/weight
- Which modifiers were applied, if any
- A note on what would resolve the uncertainty further (e.g. "a prior
  writing sample from this author would allow cross-reference"),
  distinguishing resolvable uncertainty from fundamental ambiguity