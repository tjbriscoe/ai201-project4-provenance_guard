# ai201-project4-provenance_guard

This project will serve as a backend system for any creative sharing platform to classify submitted content as AI generated or human generated. 

# Transparency Label 

high-confidence-AI: 

Stylistic Patterns:
- Use of transitional words such as ("Furthermore", "However", "In conclusion")
- Uniformity in sentence length and rhythm; paragraphs share the same pattern and have the same weight 
- Em dash overuse


Structural Patterns:
- Predictable essay structure 
- Generic and even coverage of topics; No added insight or emphasis on specific topics
- Headers that restate the obvious 

Content level patterns:
- Confident tone applied uniformally, even to opionated or uncertain claims 
- Plausible sounding errors rather than careless mistakes 
- Surfave level synthesis


high-confidence-human: 
- Genuine Assymetry: the writer spends alot of time writing about the topic they genuinely care about and not putting as much effort on the rest 
- Recurring verbal tics, specific slang, inside references 
- Errors that are careless rather than plausible(types, wrong words used)
- Precise but contexually weird details 


uncertain: 
- Integrated generative Ai content that has been heavily edited by a human 
- Concise and specific prompting - A user feeds a system a prompt that is extremely detailed and precise
- Short form content - things like captions, tweets, comments are too short to pinpoint where it originates exactly
- Detection tools being unreliable - many ai detection models are not equipped with sufficient data to assess newer models and paraphrased text 


# Confidence Scoring with uncertainty

1. The system must return a confidence score, not just a binary label 
2. The score should reflect genuine uncertainty
3. A .51 confidence should produce a meaningfully different transparency label than a 0.95

# Confidence Scoring Approach 
- Aiming for a calibrated range - Instead of merely using  a single point estimate approach, the validity of the confidence scoring increases when thinking in bands ie. Strong human/ Lean Human/ Uncertain \Lean AI\ Strong Ai
- Incorporating weight signals by reliability ; low_weight |  Signal type: factual fabrication that is verifiable | Why it's weighted : Hard to fake| 
- Confidence modifiers: 
1. Sample Length
2. Domain Formula 
3. AI draft then human edit
- Ask questions for reasoning ; How confident am I in this classification? How costly is being wrong and in which direction? Which modifier caps were applied and why ? Which signals contributed and their direction ?



# Rate Limiting 

Rate Limiting — Appeals Endpoint

Three independent limits, checked per request, reject on first breach:

Scope |________Catches________| Window | Limit| 
Creator| Spam across many cases | 24h | 5
Case  | Resubmission on same case| 7 days | 1
IP   |Unauthenticated/scripted backstop| 1h | 10

Why three, not one: IP-only limiting evades easily (NAT) and
false-positives on shared networks. Creator limit is the real abuse
control; IP is just a backstop.

Why moving window, not fixed: avoids boundary bursts (10 reqs at
11:59 + 10 at 12:01 both passing a fixed window).

Open questions:


Fail-open or closed if Redis is down? (assuming open for now)
Does adding evidence need a separate update path, or is resubmission
just blocked until decision?
Should limits scale with original classification confidence?
Thresholds above are starting guesses — revisit after real volume data.


# Audit Log 

Every attribution decision and appeal action gets logged as an
append-only entry. Purpose: transparency to creators, pattern audits
(e.g. ESL false-positive rates), and reconstructable dispute history.

What gets logged, per action:


The decision/outcome (confidence band, or appeal result)
Which signals drove it, and their weight/direction
Any confidence-capping modifiers applied (short sample, formulaic
domain, etc.)
Who/what acted (system vs. specific reviewer)
A short rationale


Why append-only, not editable: corrections become new entries
rather than overwriting old ones, so a case's full history — original
flag, appeal, reversal — stays reconstructable.

Why signals + modifiers are logged, not just the final band: the
score itself is reproducible later, scoring on confidence (band, not
point estimate) and the caps tied to it. Without the underlying signals
logged, "indeterminate" vs. "strong AI" looks arbitrary after the fact.

Access: exposed via GET /log, filterable by case or creator —
documented separately with full schema/examples.


TEST CASES RESULTS:

case                      words   sentences  score   band            label
----------------------------------------------------------------------------------------------------
clearly_ai                43                 2       lean_ai         Likely AI-generated
clearly_human             55                 -2      lean_human      Likely human-written
borderline_formal_human   43                 0       indeterminate   Uncertain
borderline_edited_ai      39                 0       indeterminate   Uncertain

Signal-level detail:
----------------------------------------------------------------------------------------------------

clearly_ai (expected: should score high (net_score > 0, band = lean_ai or strong_ai))
  lexical_tics: ai (MEDIUM) — 2 tic phrases in 43 words (density=0.047)
  structural_symmetry: neutral (MEDIUM) — too few paragraphs to assess (1 found)
  sentence_rhythm: neutral (MEDIUM) — too few sentences to assess reliably (3 found, need 5+)
  cross_reference: neutral (HIGH) — no reference corpus available -- signal inactive

clearly_human (expected: should score low (net_score < 0, band = lean_human or strong_human))
  lexical_tics: neutral (LOW) — no tic phrases found in 55 words
  structural_symmetry: neutral (MEDIUM) — too few paragraphs to assess (1 found)
  sentence_rhythm: human (MEDIUM) — high sentence-length variance, stdev=6.7 on 5 sentences (irregular rhythm)
  cross_reference: neutral (HIGH) — no reference corpus available -- signal inactive

borderline_formal_human (expected: may score mid-high on stylometrics -- formal but human)
  lexical_tics: neutral (LOW) — no tic phrases found in 43 words
  structural_symmetry: neutral (MEDIUM) — too few paragraphs to assess (1 found)
  sentence_rhythm: neutral (MEDIUM) — too few sentences to assess reliably (2 found, need 5+)
  cross_reference: neutral (HIGH) — no reference corpus available -- signal inactive

borderline_edited_ai (expected: should ideally score mid-range (indeterminate) -- lightly edited AI)
  lexical_tics: neutral (LOW) — no tic phrases found in 39 words
  structural_symmetry: neutral (MEDIUM) — too few paragraphs to assess (1 found)
  sentence_rhythm: neutral (MEDIUM) — too few sentences to assess reliably (3 found, need 5+)
  cross_reference: neutral (HIGH) — no reference corpus available -- signal inactive


