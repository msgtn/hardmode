import logging
import re
import time
from dataclasses import dataclass

log = logging.getLogger(__name__)

_toxicity_model = None

# Thresholds for detoxify scores (0-1). Lower = more sensitive.
_THRESHOLDS = {
    "toxicity": 0.6,
    "severe_toxicity": 0.4,
    "obscene": 0.6,
    "threat": 0.4,
    "insult": 0.7,
    "identity_attack": 0.5,
}

_LABEL_REASONS = {
    "toxicity": "Toxic or harmful content",
    "severe_toxicity": "Severely harmful content",
    "obscene": "Obscene content",
    "threat": "Contains a threat",
    "insult": "Insulting content",
    "identity_attack": "Hate speech",
}

_URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)

MAX_ANSWER_LENGTH = 500
RELEVANCE_THRESHOLD = 0.1


@dataclass
class ModerationResult:
    approved: bool
    reason: str = ""


def preload():
    """Warm up all models at app startup so the first request isn't slow."""
    _get_toxicity_model()
    import similarity
    similarity._get_model()
    log.info("[moderation] models ready")


def _get_toxicity_model():
    global _toxicity_model
    if _toxicity_model is None:
        log.info("[moderation] loading detoxify model...")
        from detoxify import Detoxify
        _toxicity_model = Detoxify("original")
        log.info("[moderation] detoxify loaded")
    return _toxicity_model


def moderate(question: str, answer: str) -> ModerationResult:
    t0 = time.monotonic()

    # 1. Basic rules
    answer_stripped = answer.strip()
    if not answer_stripped:
        return ModerationResult(approved=False, reason="Answer cannot be empty")
    if len(answer_stripped) > MAX_ANSWER_LENGTH:
        return ModerationResult(approved=False, reason="Answer is too long")
    if _URL_RE.search(answer_stripped):
        return ModerationResult(approved=False, reason="Links are not allowed")

    # 2. Profanity
    from better_profanity import profanity
    if profanity.contains_profanity(answer_stripped):
        return ModerationResult(approved=False, reason="Contains profanity")

    # 3. Toxicity (detoxify)
    scores = _get_toxicity_model().predict(answer_stripped)
    for label, threshold in _THRESHOLDS.items():
        score = scores.get(label, 0)
        if score >= threshold:
            reason = _LABEL_REASONS.get(label, "Inappropriate content")
            log.info(f"[moderation] rejected ({label}={score:.2f}): {answer_stripped!r}")
            return ModerationResult(approved=False, reason=reason)

    # 4. Relevance (sentence-transformers cosine similarity)
    import similarity as sim
    from sklearn.metrics.pairwise import cosine_similarity
    model = sim._get_model()
    embeddings = model.encode([question, answer_stripped])
    score = float(cosine_similarity(embeddings[0:1], embeddings[1:2])[0][0])
    if score < RELEVANCE_THRESHOLD:
        log.info(f"[moderation] rejected (relevance={score:.3f}): {answer_stripped!r}")
        return ModerationResult(approved=False, reason="Not relevant to the question")

    elapsed_ms = (time.monotonic() - t0) * 1000
    log.info(f"[moderation] approved in {elapsed_ms:.0f}ms (relevance={score:.3f})")
    return ModerationResult(approved=True)
