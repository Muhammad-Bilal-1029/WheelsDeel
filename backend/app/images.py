"""Car photos: upload ki jaanch, resize aur thumbnail.

Upload ki hui file ko Pillow se asli image ke taur par kholte aur dobara JPEG mai save karte hain:
  - sirf JPEG / PNG / WebP manzoor (file ka naam ya Content-Type par bharosa nahi, andar ka format dekha jata hay)
  - bohot bari (pixels) images reject (decompression bomb se bachao)
  - EXIF (location/camera ki info) hat jati hay, mobile photos sahi rukh par ghoom jati hain
  - bari photo max 1600px, thumbnail max 480px, dono JPEG
Dobara encode karne se file mai chhupa hua koi aur content (jaise script) bhi khatam ho jata hay.
"""
import uuid
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from . import config

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
FULL_SIZE = (1600, 1600)
THUMB_SIZE = (480, 480)

Image.MAX_IMAGE_PIXELS = config.MAX_IMAGE_PIXELS


class ImageError(ValueError):
    """User ko dikhane layak error (400)."""


def media_url(base: str, thumb: bool = False) -> str:
    return f"/media/cars/{base}{'_t' if thumb else ''}.jpg"


def process_upload(data: bytes, dest_dir: Path = config.UPLOAD_DIR) -> str:
    """Image verify + save. Naye file ka base naam (random) lautata hay."""
    try:
        image = Image.open(BytesIO(data))
        if image.format not in ALLOWED_FORMATS:
            raise ImageError("Only JPEG, PNG or WebP images are allowed.")
        if image.width * image.height > config.MAX_IMAGE_PIXELS:
            raise ImageError("This image is too large (dimensions). Please use a smaller photo.")
        image = ImageOps.exif_transpose(image)
        image.load()
    except ImageError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError, Image.DecompressionBombError):
        raise ImageError("This file is not a valid image.")

    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        rgba = image.convert("RGBA")
        flattened = Image.new("RGB", rgba.size, (255, 255, 255))
        flattened.paste(rgba, mask=rgba.getchannel("A"))
        image = flattened
    else:
        image = image.convert("RGB")

    base = uuid.uuid4().hex
    dest_dir.mkdir(parents=True, exist_ok=True)

    full = image.copy()
    full.thumbnail(FULL_SIZE)
    full.save(dest_dir / f"{base}.jpg", "JPEG", quality=85, optimize=True)

    thumb = image.copy()
    thumb.thumbnail(THUMB_SIZE)
    thumb.save(dest_dir / f"{base}_t.jpg", "JPEG", quality=80, optimize=True)
    return base


def delete_files(base: str, dest_dir: Path = config.UPLOAD_DIR) -> None:
    for name in (f"{base}.jpg", f"{base}_t.jpg"):
        try:
            (dest_dir / name).unlink()
        except FileNotFoundError:
            pass
        except OSError:
            pass
