# app/services/image_processor.py
import io
from PIL import Image
from fastapi import HTTPException


class ImageProcessor:
    """
    Service to preprocess images for VLM consumption.
    Ensures images are resized, compressed, and formatted correctly to prevent API crashes.
    """

    @staticmethod
    def resize_and_convert(
            image_bytes: bytes,
            max_dim: int = 1024,
            quality: int = 85
    ) -> bytes:
        """
        Takes raw image bytes, resizes to max_dim (maintaining aspect ratio),
        converts to JPEG (removing alpha channels), and compresses.

        Args:
            image_bytes: Raw bytes from the upload
            max_dim: Maximum width or height (default 1024 for most local VLMs)
            quality: JPEG quality (0-100)

        Returns:
            bytes: Processed JPEG image bytes

        Raises:
            HTTPException: If the image is corrupt or cannot be processed
        """
        try:
            # 1. Open image
            img = Image.open(io.BytesIO(image_bytes))

            # 2. Handle Animated GIFs/WebPs (take first frame only)
            if getattr(img, "is_animated", False):
                img.seek(0)

            # 3. Convert to RGB (Strips alpha channel from PNG/WebP)
            # This prevents errors when saving as JPEG
            if img.mode != "RGB":
                img = img.convert("RGB")

            # 4. Resize if necessary
            width, height = img.size
            if max(width, height) > max_dim:
                # Calculate new dimensions maintaining aspect ratio
                ratio = max_dim / max(width, height)
                new_width = int(width * ratio)
                new_height = int(height * ratio)

                # Use LANCZOS for high-quality downsampling
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

            # 5. Save to buffer as JPEG
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=quality, optimize=True)

            # 6. Return processed bytes
            return buffer.getvalue()

        except Exception as e:
            # Log the error here if you have logging configured
            print(f"Image Processing Error: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Unable to process image file. It may be corrupt or an unsupported format. Error: {str(e)}"
            )