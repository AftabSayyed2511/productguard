import io
import os
import pytest
import numpy as np
from PIL import Image
from app import create_app, db
from app.models.product import Product, ReferenceImage
from app.ai.preprocessor import load_and_preprocess_image
from app.ai.feature_extractor import extract_features
from app.ai.matcher import (
    calculate_cosine_similarity,
    get_or_compute_reference_embedding,
    match_query_image,
)


def make_test_image(color=(0, 210, 255), size=(180, 180)):
    """Generate in-memory RGB image."""
    img = Image.new("RGB", size, color=color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    return buf


@pytest.fixture
def app():
    """Create test application context."""
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def test_preprocessor_shape_and_normalization():
    """Verify input preprocessing produces (1, 224, 224, 3) tensor normalized to [-1, 1]."""
    test_img = make_test_image(color=(255, 0, 128), size=(150, 300))
    tensor = load_and_preprocess_image(test_img)

    assert isinstance(tensor, np.ndarray)
    assert tensor.shape == (1, 224, 224, 3)
    assert tensor.dtype == np.float32
    assert tensor.min() >= -1.0
    assert tensor.max() <= 1.0


def test_feature_extractor_output():
    """Verify feature extractor generates 1280-D vector with unit L2 norm."""
    test_img = make_test_image(color=(10, 20, 30))
    embedding = extract_features(test_img)

    assert isinstance(embedding, np.ndarray)
    assert embedding.shape == (1280,)
    assert embedding.dtype == np.float32

    # L2 norm should be ~ 1.0
    l2_norm = np.linalg.norm(embedding)
    assert pytest.approx(l2_norm, abs=1e-4) == 1.0


def test_cosine_similarity_identical_images():
    """Two identical images must produce cosine similarity score ~ 1.0 (100%)."""
    img1 = make_test_image(color=(50, 150, 250), size=(200, 200))
    img2 = make_test_image(color=(50, 150, 250), size=(200, 200))

    vec1 = extract_features(img1)
    vec2 = extract_features(img2)

    similarity = calculate_cosine_similarity(vec1, vec2)
    assert pytest.approx(similarity, abs=1e-3) == 1.0


def test_cosine_similarity_different_images():
    """Distinct images must produce lower cosine similarity than identical images."""
    img_blue = make_test_image(color=(0, 0, 255))
    img_red = make_test_image(color=(255, 0, 0))

    vec_blue = extract_features(img_blue)
    vec_red = extract_features(img_red)

    similarity = calculate_cosine_similarity(vec_blue, vec_red)
    assert similarity < 0.95


def test_embedding_disk_cache(app):
    """Verify embedding is saved to disk and loaded from cache on subsequent calls."""
    with app.app_context():
        # Setup test uploads directory and reference image
        uploads_dir = app.config["UPLOAD_FOLDER"]
        ref_dir = app.config["REFERENCE_UPLOAD_DIR"]
        os.makedirs(ref_dir, exist_ok=True)

        img_filename = "test_cache_target.jpg"
        img_path = os.path.join(ref_dir, img_filename)

        img = Image.new("RGB", (200, 200), color=(100, 200, 50))
        img.save(img_path, format="JPEG")

        prod = Product(
            product_name="Cache Test Product",
            brand="TestBrand",
            category="Electronics",
        )
        db.session.add(prod)
        db.session.flush()

        ref = ReferenceImage(
            product_id=prod.id,
            image_path=f"references/{img_filename}",
            angle_or_view="front",
        )
        db.session.add(ref)
        db.session.commit()

        # First call: computes and creates .npy file
        vec1 = get_or_compute_reference_embedding(ref, uploads_dir)
        assert ref.embedding_path is not None

        full_emb_path = os.path.join(uploads_dir, ref.embedding_path)
        assert os.path.exists(full_emb_path)

        # Second call: loads from cache
        vec2 = get_or_compute_reference_embedding(ref, uploads_dir)
        np.testing.assert_array_almost_equal(vec1, vec2)


def test_match_query_image_workflow(app):
    """Test full matching workflow: query image matched against database reference."""
    with app.app_context():
        uploads_dir = app.config["UPLOAD_FOLDER"]
        ref_dir = app.config["REFERENCE_UPLOAD_DIR"]
        os.makedirs(ref_dir, exist_ok=True)

        # Create genuine reference image
        ref_img_name = "genuine_packaging.jpg"
        ref_full_path = os.path.join(ref_dir, ref_img_name)
        Image.new("RGB", (224, 224), color=(0, 200, 100)).save(ref_full_path, format="JPEG")

        prod = Product(
            product_name="Ultra Serum 30ml",
            brand="GlowCosmetics",
            category="Cosmetics",
            sku_or_upc="GLOW-US-30",
        )
        db.session.add(prod)
        db.session.flush()

        ref = ReferenceImage(
            product_id=prod.id,
            image_path=f"references/{ref_img_name}",
            angle_or_view="front",
        )
        db.session.add(ref)
        db.session.commit()

        # Query image: exact same packaging image
        query_stream = make_test_image(color=(0, 200, 100), size=(224, 224))

        result = match_query_image(
            query_stream,
            category="Cosmetics",
            uploads_folder=uploads_dir,
        )

        assert result["status"] == "success"
        assert result["matched_product"]["product_name"] == "Ultra Serum 30ml"
        assert result["matched_product"]["brand"] == "GlowCosmetics"
        assert result["similarity_score"] >= 0.82
        assert result["assessment_status"] == "HIGH_SIMILARITY"
        assert result["processing_time_ms"] >= 0
        assert result["total_references_compared"] == 1


def test_match_query_image_insufficient_data(app):
    """Verify empty category returns INSUFFICIENT_DATA without crashing or fabricating a match."""
    with app.app_context():
        query_stream = make_test_image(color=(128, 128, 128))

        result = match_query_image(
            query_stream,
            category="NonExistentCategory",
            uploads_folder=app.config["UPLOAD_FOLDER"],
        )

        assert result["status"] == "insufficient_data"
        assert result["assessment_status"] == "INSUFFICIENT_DATA"
        assert result["matched_product"] is None
        assert result["similarity_score"] == 0.0
        assert "Unable to assess this product" in result["assessment_description"]
