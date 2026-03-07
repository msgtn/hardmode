from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

_model = None


def _get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def most_similar(query: str, candidates: list[str]) -> tuple[int, float]:
    """
    Returns the index and cosine similarity score of the most similar
    candidate to the query.
    """
    model = _get_model()
    embeddings = model.encode([query] + candidates)
    query_vec = embeddings[0:1]
    candidate_vecs = embeddings[1:]
    scores = cosine_similarity(query_vec, candidate_vecs)[0]
    best_idx = int(scores.argmax())
    return best_idx, float(scores[best_idx])
