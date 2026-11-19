from app.ai.model_loader import ModelManager
from app.ai.preprocessor import load_and_preprocess_image
from app.ai.feature_extractor import extract_features
from app.ai.matcher import (
    calculate_cosine_similarity,
    get_or_compute_reference_embedding,
    sync_all_reference_embeddings,
    match_query_image,
)

__all__ = [
    "ModelManager",
    "load_and_preprocess_image",
    "extract_features",
    "calculate_cosine_similarity",
    "get_or_compute_reference_embedding",
    "sync_all_reference_embeddings",
    "match_query_image",
]
