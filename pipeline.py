"""
Multi-signal detection pipeline v5.

ARCHITECTURAL CHANGE FROM v4: STEP 0 no longer gates on word count.
Per the updated diagram, Step 0 checks whether the text is COHERENT --
not how long it is -- and even incoherent text still proceeds to full
analysis, just with a +1 uncertainty modifier applied afterward
(matching the diagram's "+1 FOR UNCERTAINTY, CONTINUE FOR ANALYSIS"
path, rather than the old dead-end "LOW CONFIDENCE CEILING" box that
implicitly discouraged further analysis).

Coherence is checked with lightweight heuristics (no external NLP
dependency): does the text have real sentence structure (function
words, sentence-ending punctuation, reasonable word-length
distribution) rather than gibberish, keyword soup, or degenerate
input. This replaces word count as the Step 0 gate entirely --
length plays NO role in Step 0 anymore.
"""

import re
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


# ---------------------------------------------------------------------------
# Shared types
# ---------------------------------------------------------------------------
class Direction(str, Enum):
    AI = "ai"
    HUMAN = "human"
    NEUTRAL = "neutral"


class Weight(int, Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3


class ConfidenceBand(str, Enum):
    STRONG_AI = "strong_ai"
    LEAN_AI = "lean_ai"
    INDETERMINATE = "indeterminate"
    LEAN_HUMAN = "lean_human"
    STRONG_HUMAN = "strong_human"


BAND_ORDER = [
    ConfidenceBand.STRONG_AI,
    ConfidenceBand.LEAN_AI,
    ConfidenceBand.INDETERMINATE,
    ConfidenceBand.LEAN_HUMAN,
    ConfidenceBand.STRONG_HUMAN,
]

HIGH_CONFIDENCE_BANDS = {ConfidenceBand.STRONG_AI, ConfidenceBand.STRONG_HUMAN}

BAND_TO_LABEL = {
    ConfidenceBand.STRONG_AI: "Likely AI-generated",
    ConfidenceBand.LEAN_AI: "Likely AI-generated",
    ConfidenceBand.INDETERMINATE: "Uncertain",
    ConfidenceBand.LEAN_HUMAN: "Likely human-written",
    ConfidenceBand.STRONG_HUMAN: "Likely human-written",
}

# ---------------------------------------------------------------------------
# TRANSPARENCY LABELS -- full spec, 3 categories with supporting pattern
# reasoning. "High confidence" is reserved for strong_ai/strong_human only,
# per the naming itself -- lean_* and indeterminate all fall under
# "uncertain", since they reflect real but non-decisive evidence.
# ---------------------------------------------------------------------------
TRANSPARENCY_LABELS = {
    "high-confidence-ai": {
        "label": "High Confidence: AI-Generated",
        "patterns": {
            "stylistic": [
                "Use of transitional words such as \"Furthermore\", \"However\", \"In conclusion\"",
                "Uniformity in sentence length and rhythm; paragraphs share the same pattern and weight",
                "Em dash overuse",
            ],
            "structural": [
                "Predictable essay structure",
                "Generic and even coverage of topics; no added insight or emphasis on specific topics",
                "Headers that restate the obvious",
            ],
            "content_level": [
                "Confident tone applied uniformly, even to opinionated or uncertain claims",
                "Plausible-sounding errors rather than careless mistakes",
                "Surface-level synthesis",
            ],
        },
    },
    "high-confidence-human": {
        "label": "High Confidence: Human-Written",
        "patterns": {
            "general": [
                "Genuine asymmetry: the writer spends a lot of time on the topic they genuinely "
                "care about and less effort on the rest",
                "Recurring verbal tics, specific slang, inside references",
                "Errors that are careless rather than plausible (typos, wrong words used)",
                "Precise but contextually weird details",
            ],
        },
    },
    "uncertain": {
        "label": "Uncertain",
        "patterns": {
            "general": [
                "Integrated generative AI content that has been heavily edited by a human",
                "Concise and specific prompting -- a user feeds a system an extremely detailed, precise prompt",
                "Short-form content -- captions, tweets, comments are too short to pinpoint origin exactly",
                "Detection tools being unreliable -- many AI detection models lack sufficient data to "
                "assess newer models and paraphrased text",
            ],
        },
    },
}


def get_transparency_label(band: ConfidenceBand) -> dict:
    """
    Maps a confidence band to one of exactly 3 transparency label
    categories, per spec. Only strong_ai/strong_human reach a
    "high-confidence" label -- lean_* and indeterminate all report as
    "uncertain", since the underlying evidence at those bands is real
    but not decisive enough to warrant a confident public label.
    """
    if band == ConfidenceBand.STRONG_AI:
        key = "high-confidence-ai"
    elif band == ConfidenceBand.STRONG_HUMAN:
        key = "high-confidence-human"
    else:
        key = "uncertain"

    return {
        "key": key,
        "label": TRANSPARENCY_LABELS[key]["label"],
        "patterns": TRANSPARENCY_LABELS[key]["patterns"],
    }


@dataclass
class SignalResult:
    name: str
    direction: Direction
    weight: Weight
    detail: str = ""

    def score(self) -> int:
        if self.direction == Direction.NEUTRAL:
            return 0
        sign = 1 if self.direction == Direction.AI else -1
        return sign * self.weight.value


@dataclass
class PipelineResult:
    confidence_band: ConfidenceBand
    net_score: int
    signals: list = field(default_factory=list)
    modifiers: list = field(default_factory=list)
    word_count: int = 0
    is_coherent: bool = True
    overridden_by_cross_reference: bool = False

    @property
    def label(self) -> str:
        return BAND_TO_LABEL[self.confidence_band]

    def to_log_entry(self, case_id: str, actor: str = "system") -> dict:
        return {
            "caseId": case_id,
            "action": "classification",
            "confidenceBand": self.confidence_band.value,
            "label": self.label,
            "combinedScore": self.net_score,
            "signals": [
                {
                    "name": s.name,
                    "direction": s.direction.value,
                    "weight": s.weight.name,
                    "score": s.score(),  # individual signal's contribution to the combined score
                    "detail": s.detail,
                }
                for s in self.signals
            ],
            "modifiers": self.modifiers,
            "wordCount": self.word_count,       # informational only
            "isCoherent": self.is_coherent,      # STEP 0 result
            "overriddenByCrossReference": self.overridden_by_cross_reference,
            "actor": actor,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "notes": f"net_score={self.net_score}",
        }


# ---------------------------------------------------------------------------
# STEP 0 — Coherence check (replaces word-count gate entirely)
# ---------------------------------------------------------------------------
COMMON_FUNCTION_WORDS = {
    "the", "a", "an", "is", "are", "was", "were", "and", "or", "but",
    "to", "of", "in", "on", "for", "with", "this", "that", "it", "i",
    "you", "we", "they", "he", "she", "not", "be", "have", "has",
}


def detect_coherence(text: str) -> tuple:
    """
    Lightweight heuristic coherence check -- no external NLP dependency.
    Returns (is_coherent: bool, detail: str).

    Checks:
      1. Has at least one function word (real language structure,
         not keyword soup or random tokens).
      2. Has at least one sentence-ending punctuation mark OR is long
         enough that punctuation isn't strictly required to judge intent.
      3. Words have a plausible average length (catches gibberish like
         "asdkjf aslkdj qwoieru" which has no real words).
    """
    words = re.findall(r"[a-zA-Z']+", text.lower())

    if len(words) < 2:
        return False, "too little text to assess coherence (fewer than 2 words)"

    has_function_word = any(w in COMMON_FUNCTION_WORDS for w in words)
    has_sentence_punctuation = bool(re.search(r'[.!?]', text))
    avg_word_length = sum(len(w) for w in words) / len(words)
    plausible_word_length = 2 <= avg_word_length <= 12

    if not plausible_word_length:
        return False, f"average word length ({avg_word_length:.1f}) outside plausible range -- possible gibberish"

    if not has_function_word:
        return False, "no common function words found -- possible keyword soup or non-sentence input"

    if not has_sentence_punctuation and len(words) < 8:
        return False, "no sentence punctuation and very short -- possible fragment, not a real sentence"

    return True, "text has function words, plausible word lengths, and sentence-like structure"


# ---------------------------------------------------------------------------
# SIGNAL 1 — Lexical tics (LOW weight)
# ---------------------------------------------------------------------------
TICS = [
    "moreover", "furthermore", "it's worth noting", "it is worth noting",
    "it is important to note", "it's important to note",
    "in conclusion", "on the other hand", "not only", "but also",
]


def detect_lexical_tics(text: str) -> SignalResult:
    lowered = text.lower()
    hits = sum(lowered.count(t) for t in TICS)
    word_count = max(len(text.split()), 1)
    density = hits / word_count

    if hits == 0:
        return SignalResult("lexical_tics", Direction.NEUTRAL, Weight.LOW,
                             f"no tic phrases found in {word_count} words")

    # Weight scales with hit count -- a single incidental tic phrase is
    # weak evidence (LOW), but 2+ tic phrases in the same sample is a
    # much stronger, harder-to-coincidentally-produce pattern (MEDIUM).
    weight = Weight.MEDIUM if hits >= 2 else Weight.LOW
    return SignalResult("lexical_tics", Direction.AI, weight,
                         f"{hits} tic phrases in {word_count} words (density={density:.3f})")


# ---------------------------------------------------------------------------
# SIGNAL 2 — Structural symmetry (MEDIUM weight)
# ---------------------------------------------------------------------------
def detect_structural_symmetry(text: str) -> SignalResult:
    paragraphs = [p for p in text.split("\n\n") if p.strip()]

    if len(paragraphs) < 3:
        return SignalResult("structural_symmetry", Direction.NEUTRAL, Weight.MEDIUM,
                             f"too few paragraphs to assess ({len(paragraphs)} found)")

    lengths = [len(p.split()) for p in paragraphs]
    mean_len = statistics.mean(lengths)
    stdev_len = statistics.pstdev(lengths)
    cv = stdev_len / mean_len if mean_len else 0

    if cv < 0.25:
        return SignalResult("structural_symmetry", Direction.AI, Weight.MEDIUM,
                             f"low paragraph-length variance, cv={cv:.2f} (even coverage)")
    return SignalResult("structural_symmetry", Direction.HUMAN, Weight.MEDIUM,
                         f"high paragraph-length variance, cv={cv:.2f} (asymmetric attention)")


# ---------------------------------------------------------------------------
# SIGNAL 3 — Sentence rhythm (weight SCALES with sample size, addressing
# the small-n noise problem found in v4 testing)
# ---------------------------------------------------------------------------
def detect_sentence_rhythm(text: str) -> SignalResult:
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    lengths = [len(s.split()) for s in sentences if s.strip()]

    # Raised from 3 to 5: testing showed 3-sentence samples produce
    # confidently-wrong contradictions (e.g. a genuinely AI-generated
    # sample with naturally varied sentence length got misread as
    # "human" on n=3, canceling out a correct lexical_tics detection).
    # Below 5 sentences, this signal stays neutral rather than guessing.
    if len(lengths) < 5:
        return SignalResult("sentence_rhythm", Direction.NEUTRAL, Weight.MEDIUM,
                             f"too few sentences to assess reliably ({len(lengths)} found, need 5+)")

    stdev_len = statistics.pstdev(lengths)
    if stdev_len < 4:
        return SignalResult("sentence_rhythm", Direction.AI, Weight.MEDIUM,
                             f"low sentence-length variance, stdev={stdev_len:.1f} on {len(lengths)} sentences (uniform rhythm)")
    return SignalResult("sentence_rhythm", Direction.HUMAN, Weight.MEDIUM,
                         f"high sentence-length variance, stdev={stdev_len:.1f} on {len(lengths)} sentences (irregular rhythm)")


# ---------------------------------------------------------------------------
# SIGNAL 4 — Cross-reference (HIGH weight, stub, override behavior)
# ---------------------------------------------------------------------------
def detect_cross_reference(text: str, reference_corpus: list = None) -> SignalResult:
    if not reference_corpus:
        return SignalResult("cross_reference", Direction.NEUTRAL, Weight.HIGH,
                             "no reference corpus available -- signal inactive")
    raise NotImplementedError("Plug in embedding/stylometric comparison against reference_corpus")


# ---------------------------------------------------------------------------
# AGGREGATION
# ---------------------------------------------------------------------------
def score_to_band(net_score: int) -> ConfidenceBand:
    if net_score >= 5:
        return ConfidenceBand.STRONG_AI
    if net_score >= 2:
        return ConfidenceBand.LEAN_AI
    if net_score >= -1:
        return ConfidenceBand.INDETERMINATE
    if net_score >= -4:
        return ConfidenceBand.LEAN_HUMAN
    return ConfidenceBand.STRONG_HUMAN


# ---------------------------------------------------------------------------
# Modifiers -- blur-zone (Step 6) + incoherence (Step 0), same mechanism
# ---------------------------------------------------------------------------
def detect_modifiers(text: str, domain: str = None, possible_esl: bool = False,
                      possible_ai_edited: bool = False) -> list:
    modifiers = []
    if domain in {"legal", "technical", "academic"}:
        modifiers.append("formulaic_domain")
    if possible_esl:
        modifiers.append("possible_esl")
    if possible_ai_edited:
        modifiers.append("possible_ai_edited")
    return modifiers


def apply_modifier_cap(band: ConfidenceBand, modifiers: list) -> ConfidenceBand:
    if not modifiers:
        return band
    index = BAND_ORDER.index(band)
    center = BAND_ORDER.index(ConfidenceBand.INDETERMINATE)
    steps = min(len(modifiers), abs(index - center))
    if index < center:
        index += steps
    elif index > center:
        index -= steps
    return BAND_ORDER[index]


# ---------------------------------------------------------------------------
# PIPELINE ENTRY POINT
# ---------------------------------------------------------------------------
def run_pipeline(text: str, *, domain: str = None, possible_esl: bool = False,
                  possible_ai_edited: bool = False, reference_corpus: list = None) -> PipelineResult:

    word_count = len(text.split())  # informational only

    # STEP 0 — coherence check, NOT a word-count gate. Per diagram:
    # incoherent text still proceeds to full analysis, it just picks up
    # a +1 uncertainty modifier along the way.
    is_coherent, coherence_detail = detect_coherence(text)

    lexical = detect_lexical_tics(text)
    structural = detect_structural_symmetry(text)
    rhythm = detect_sentence_rhythm(text)
    cross_ref = detect_cross_reference(text, reference_corpus=reference_corpus)
    signals = [lexical, structural, rhythm, cross_ref]

    overridden = False
    if cross_ref.direction != Direction.NEUTRAL:
        overridden = True
        band = ConfidenceBand.STRONG_AI if cross_ref.direction == Direction.AI else ConfidenceBand.STRONG_HUMAN
        net_score = cross_ref.score()
    else:
        net_score = lexical.score() + structural.score() + rhythm.score()
        band = score_to_band(net_score)

    modifiers = detect_modifiers(text, domain=domain, possible_esl=possible_esl,
                                  possible_ai_edited=possible_ai_edited)
    if not is_coherent:
        # "+1 FOR UNCERTAINTY" per diagram -- pulls the band one step
        # toward indeterminate, same mechanism as blur-zone modifiers,
        # but analysis still ran in full above regardless.
        modifiers = modifiers + ["incoherent_input"]

    final_band = apply_modifier_cap(band, modifiers)

    return PipelineResult(
        confidence_band=final_band,
        net_score=net_score,
        signals=signals,
        modifiers=modifiers,
        word_count=word_count,
        is_coherent=is_coherent,
        overridden_by_cross_reference=overridden,
    )


def triage_appeal(original_band: ConfidenceBand) -> str:
    if original_band in HIGH_CONFIDENCE_BANDS:
        return "full_review"
    return "fast_track"