import io
from pathlib import Path
from PIL import Image
import numpy as np


def load_and_preprocess_image(
    image_input, target_size: tuple[int, int] = (224, 224)
) -> np.ndarray:
    """
    Load and preprocess an image for MobileNetV2 feature extraction.

    Steps:
    1. Reads image from filesystem path, file-like object, or byte stream.
    2. Converts to standard 3-channel RGB (removes alpha channels or converts grayscale).
    3. Resizes to target_size (224x224) using high-quality bilinear interpolation.
    4. Applies MobileNetV2 normalization: scale pixel intensities to [-1.0, 1.0].
    5. Adds batch dimension: shape (1, 224, 224, 3).

    Args:
        image_input: File path (str/Path), file-like object, or BytesIO buffer.
        target_size: Desired resolution (default 224x224).

    Returns:
        np.ndarray: Batch tensor of shape (1, target_size[0], target_size[1], 3) as float32.
    """
    if isinstance(image_input, (str, Path)):
        img = Image.open(str(image_input))
    elif isinstance(image_input, (io.BytesIO, bytes)):
        if isinstance(image_input, bytes):
            image_input = io.BytesIO(image_input)
        img = Image.open(image_input)
    elif hasattr(image_input, "read"):
        img = Image.open(image_input)
    else:
        raise ValueError(f"Unsupported image input type: {type(image_input)}")

    # Ensure 3-channel RGB
    if img.mode != "RGB":
        img = img.convert("RGB")

    # High-quality resize to 224x224
    if img.size != target_size:
        img = img.resize(target_size, Image.Resampling.BILINEAR)

    # Convert to float32 NumPy array
    img_array = np.asarray(img, dtype=np.float32)

    # MobileNetV2 normalization: scale from [0, 255] to [-1.0, 1.0]
    # Formula: (x / 127.5) - 1.0
    normalized_array = (img_array / 127.5) - 1.0

    # Expand dims for batch processing: (1, 224, 224, 3)
    batch_tensor = np.expand_dims(normalized_array, axis=0)

    return batch_tensor
