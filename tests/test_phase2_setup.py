import os
from pathlib import Path


def test_app_creation_and_config(app):
    """Test that application factory properly instantiates testing configuration."""
    assert app is not None
    assert app.testing is True
    assert app.config["WTF_CSRF_ENABLED"] is False
    assert "sqlite" in app.config["SQLALCHEMY_DATABASE_URI"]


def test_upload_directories_exist(app):
    """Verify that required storage folders are dynamically created."""
    assert os.path.exists(app.config["UPLOAD_FOLDER"])
    assert os.path.exists(app.config["REFERENCE_UPLOAD_DIR"])
    assert os.path.exists(app.config["SCAN_UPLOAD_DIR"])
    assert os.path.exists(app.config["EMBEDDING_DIR"])


def test_landing_page_route(client):
    """Verify that the landing page loads with HTTP 200 and ProductGuard branding."""
    response = client.get("/")
    assert response.status_code == 200
    html = response.data.decode("utf-8")
    assert "ProductGuard" in html
    assert "Detect. Verify. Protect." in html
    assert "MobileNetV2" in html
    assert "Supported Product Categories" in html


def test_about_page_route(client):
    """Verify that the about page renders methodology and mathematical formulas."""
    response = client.get("/about")
    assert response.status_code == 200
    html = response.data.decode("utf-8")
    assert "Computer Vision Pipeline Architecture" in html
    assert "Cosine Similarity Computation" in html
    assert "Decision Threshold Calibration" in html


def test_404_error_handler(client):
    """Verify that invalid routes trigger custom 404 template."""
    response = client.get("/non-existent-endpoint-xyz")
    assert response.status_code == 404
    html = response.data.decode("utf-8")
    assert "404" in html
    assert "Resource Not Found" in html


def test_ai_stack_availability():
    """Ensure computer vision and deep learning packages are loaded and functional."""
    import cv2
    import numpy as np
    import PIL
    import sklearn
    import tensorflow as tf

    assert cv2.__version__ is not None
    assert np.__version__.startswith("1.")
    assert PIL.__version__ is not None
    assert sklearn.__version__ is not None
    assert tf.__version__ is not None
