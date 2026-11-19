import numpy as np
import tensorflow as tf
from app.ai.model_loader import ModelManager
from app.ai.preprocessor import load_and_preprocess_image


def extract_features(image_input) -> np.ndarray:
    """
    Extract a high-dimensional, L2-normalized feature embedding vector from an image
    using the MobileNetV2 convolutional backbone.

    Args:
        image_input: File path, file-like object, or BytesIO buffer.

    Returns:
        np.ndarray: 1-D array of shape (1280,) with unit L2 norm (||e||_2 == 1.0).
    """
    # 1. Preprocess image tensor to (1, 224, 224, 3)
    tensor = load_and_preprocess_image(image_input)

    # 2. Forward pass through singleton MobileNetV2 model
    model = ModelManager().get_model()
    raw_embedding = model(tensor, training=False)

    # 3. Convert TensorFlow tensor to flat NumPy vector
    if hasattr(raw_embedding, "numpy"):
        features = raw_embedding.numpy().flatten()
    else:
        features = np.asarray(raw_embedding).flatten()

    # 4. L2 vector normalization: e = f / ||f||_2
    norm = np.linalg.norm(features)
    if norm > 0:
        normalized_features = features / norm
    else:
        normalized_features = features

    return normalized_features.astype(np.float32)
