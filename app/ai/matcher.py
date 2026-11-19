import os
import time
import uuid
from pathlib import Path
import numpy as np
from flask import current_app
from app import db
from app.models.product import Product, ReferenceImage
from app.ai.feature_extractor import extract_features


# In-memory dictionary cache to prevent redundant disk I/O: {image_id: (embedding_vector, timestamp)}
_MEMORY_EMBEDDING_CACHE = {}


def calculate_cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    """
    Calculate the cosine similarity between two L2-normalized feature vectors.
    Since both vectors have unit norm (||v||_2 == 1.0), the cosine similarity simplifies
    to their inner dot product: S(a, b) = a . b.
    """
    dot_product = float(np.dot(vec_a, vec_b))
    # Bound to valid range [0.0, 1.0] for image similarity
    return max(0.0, min(1.0, dot_product))


def get_or_compute_reference_embedding(
    ref_image: ReferenceImage, uploads_folder: str
) -> np.ndarray:
    """
    Retrieve cached feature embedding for a verified reference image.
    If the embedding has not been calculated yet or the .npy file is missing,
    extracts the 1280-D vector, serializes it to .npy on disk, and updates the DB record.
    """
    global _MEMORY_EMBEDDING_CACHE

    # 1. Check in-memory cache first
    if ref_image.id in _MEMORY_EMBEDDING_CACHE:
        return _MEMORY_EMBEDDING_CACHE[ref_image.id]

    embeddings_dir = os.path.join(uploads_folder, "embeddings")
    os.makedirs(embeddings_dir, exist_ok=True)

    # 2. Check disk cache if embedding_path is recorded
    if ref_image.embedding_path:
        full_emb_path = os.path.join(uploads_folder, ref_image.embedding_path)
        if os.path.exists(full_emb_path):
            try:
                vector = np.load(full_emb_path).astype(np.float32)
                _MEMORY_EMBEDDING_CACHE[ref_image.id] = vector
                return vector
            except Exception:
                pass

    # 3. Compute new embedding from image file
    full_img_path = os.path.join(uploads_folder, ref_image.image_path)
    if not os.path.exists(full_img_path):
        raise FileNotFoundError(f"Reference image file not found on disk: {full_img_path}")

    vector = extract_features(full_img_path)

    # Save to disk as .npy
    unique_name = f"{uuid.uuid4().hex}.npy"
    save_path = os.path.join(embeddings_dir, unique_name)
    np.save(save_path, vector)

    # Update database record
    ref_image.embedding_path = f"embeddings/{unique_name}"
    db.session.commit()

    # Cache in memory
    _MEMORY_EMBEDDING_CACHE[ref_image.id] = vector
    return vector


def sync_all_reference_embeddings(app=None) -> int:
    """
    Scan all active ReferenceImage records in the database, compute missing embeddings,
    and persist them to disk. Returns count of newly generated embeddings.
    """
    uploads_dir = (
        app.config["UPLOAD_FOLDER"]
        if app
        else current_app.config["UPLOAD_FOLDER"]
    )

    query = ReferenceImage.query.filter_by(is_active=True).all()
    count = 0

    for ref in query:
        needs_computation = False
        if not ref.embedding_path:
            needs_computation = True
        else:
            p = os.path.join(uploads_dir, ref.embedding_path)
            if not os.path.exists(p):
                needs_computation = True

        if needs_computation:
            get_or_compute_reference_embedding(ref, uploads_dir)
            count += 1

    return count


def match_query_image(
    image_input,
    category: str = None,
    uploads_folder: str = None,
    threshold_high: float = 0.82,
    threshold_mod: float = 0.65,
    threshold_min: float = 0.40,
) -> dict:
    """
    Core AI inference comparison engine.

    Workflow:
    1. Extracts high-dimensional 1280-D MobileNetV2 embedding from query packaging image.
    2. Queries eligible verified genuine reference images from the database.
    3. Calculates vectorized cosine similarity across all candidate embeddings.
    4. Finds the closest matching reference product.
    5. Classifies assessment status using calibrated thresholds.

    Returns:
        dict: Complete comparison metrics, matched product metadata, and recommendation.
    """
    start_time = time.time()

    if uploads_folder is None:
        uploads_folder = current_app.config["UPLOAD_FOLDER"]

    # 1. Extract feature embedding from query image
    query_embedding = extract_features(image_input)

    # 2. Query eligible reference images
    ref_query = ReferenceImage.query.join(Product).filter(ReferenceImage.is_active == True)
    if category:
        ref_query = ref_query.filter(Product.category == category)

    eligible_refs = ref_query.all()

    # Case: No reference images exist in the category
    if not eligible_refs:
        elapsed_ms = int((time.time() - start_time) * 1000)
        return {
            "status": "insufficient_data",
            "matched_product": None,
            "matched_product_id": None,
            "matched_reference_image_id": None,
            "matched_reference_image_path": None,
            "similarity_score": 0.0,
            "similarity_percentage": 0.0,
            "assessment_status": "INSUFFICIENT_DATA",
            "assessment_title": "Insufficient Reference Data",
            "assessment_description": (
                f"No verified reference products are currently registered in the '{category}' category. "
                "Unable to assess this product."
            ),
            "recommendation": "Administrator must ingest genuine manufacturer samples for this category.",
            "processing_time_ms": elapsed_ms,
            "total_references_compared": 0,
        }

    # 3. Build candidate embedding matrix
    candidate_vectors = []
    valid_refs = []

    for ref in eligible_refs:
        try:
            vec = get_or_compute_reference_embedding(ref, uploads_folder)
            candidate_vectors.append(vec)
            valid_refs.append(ref)
        except Exception:
            continue

    if not candidate_vectors:
        elapsed_ms = int((time.time() - start_time) * 1000)
        return {
            "status": "error",
            "message": "Failed to load candidate reference embeddings.",
            "assessment_status": "INSUFFICIENT_DATA",
            "similarity_score": 0.0,
            "processing_time_ms": elapsed_ms,
        }

    # Matrix multiplication: (N, 1280) dot (1280,) -> (N,)
    ref_matrix = np.array(candidate_vectors, dtype=np.float32)
    scores = np.dot(ref_matrix, query_embedding)
    scores = np.clip(scores, 0.0, 1.0)

    # 4. Identify best match
    best_idx = int(np.argmax(scores))
    best_score = float(scores[best_idx])
    best_ref = valid_refs[best_idx]
    best_product = best_ref.product

    elapsed_ms = int((time.time() - start_time) * 1000)

    # 5. Classify visual similarity status
    if best_score < threshold_min and not category:
        assessment_status = "INSUFFICIENT_DATA"
        assessment_title = "Insufficient Reference Data"
        assessment_desc = (
            "The packaging does not sufficiently correlate with any registered reference category."
        )
        recommendation = "Verify the product category and check for genuine manufacturer reference availability."
    elif best_score >= threshold_high:
        assessment_status = "HIGH_SIMILARITY"
        assessment_title = "High Visual Similarity"
        assessment_desc = (
            f"The uploaded packaging exhibits high visual correlation ({round(best_score * 100, 1)}%) "
            f"with verified manufacturer packaging for '{best_product.brand} {best_product.product_name}'."
        )
        recommendation = "Packaging visual verification passed. Advisory: Ensure physical seals and barcodes are intact."
    elif best_score >= threshold_mod:
        assessment_status = "MODERATE_SIMILARITY"
        assessment_title = "Moderate Visual Similarity"
        assessment_desc = (
            f"Moderate visual similarity detected ({round(best_score * 100, 1)}%). "
            "General layout matches genuine reference, but measurable variances in fonts, hues, or aspect ratios exist."
        )
        recommendation = (
            "Additional verification required. Inspect batch codes, expiration typography, and holograms carefully."
        )
    else:
        assessment_status = "LOW_SIMILARITY"
        assessment_title = "Low Visual Similarity"
        assessment_desc = (
            f"Significant visual divergence detected ({round(best_score * 100, 1)}%). "
            "Key packaging features do not match verified manufacturer standards."
        )
        recommendation = "High suspicion of counterfeit packaging or unauthorized replica. Caution advised."

    return {
        "status": "success",
        "matched_product": best_product.to_dict(include_images=False),
        "matched_product_id": best_product.id,
        "matched_reference_image_id": best_ref.id,
        "matched_reference_image_path": best_ref.image_path,
        "similarity_score": round(best_score, 4),
        "similarity_percentage": round(best_score * 100, 2),
        "assessment_status": assessment_status,
        "assessment_title": assessment_title,
        "assessment_description": assessment_desc,
        "recommendation": recommendation,
        "processing_time_ms": elapsed_ms,
        "total_references_compared": len(candidate_vectors),
    }
