import os
from pathlib import Path

# Set KERAS_HOME inside the project workspace BEFORE tensorflow/keras is loaded
BASE_DIR = Path(__file__).resolve().parent.parent.parent
keras_cache = BASE_DIR / ".keras"
os.environ["KERAS_HOME"] = str(keras_cache)
os.makedirs(keras_cache, exist_ok=True)
os.makedirs(keras_cache / "models", exist_ok=True)

import threading
import numpy as np
import tensorflow as tf
from tensorflow.keras.applications.mobilenet_v2 import MobileNetV2


class ModelManager:
    """
    Thread-safe Singleton class managing the MobileNetV2 deep feature extraction model.
    Ensures the heavy neural network weights are loaded exactly once in memory and reused
    across all scanning and reference embedding requests.
    """

    _instance = None
    _lock = threading.Lock()
    _model = None

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(ModelManager, cls).__new__(cls)
        return cls._instance

    def get_model(self):
        """
        Returns the compiled MobileNetV2 feature extractor.
        Classification top is removed (include_top=False) with global average pooling (pooling='avg')
        to output a flat 1,280-dimensional feature vector.
        """
        if self._model is None:
            with self._lock:
                if self._model is None:
                    # Suppress verbose TensorFlow warnings
                    tf.get_logger().setLevel("ERROR")

                    # Instantiate MobileNetV2 backbone
                    base_model = MobileNetV2(
                        weights="imagenet",
                        include_top=False,
                        pooling="avg",
                        input_shape=(224, 224, 3),
                    )

                    # Warm-up inference pass to compile graph and kernel execution
                    warmup_tensor = tf.zeros((1, 224, 224, 3), dtype=tf.float32)
                    _ = base_model(warmup_tensor, training=False)

                    self._model = base_model
        return self._model

    def is_loaded(self) -> bool:
        """Check if model has already been loaded into memory."""
        return self._model is not None
