"""Image preparation for reading and for the viewer (docs/AI_SPEC.md 6, docs/API.md uploads).

- `sniff` decides the type from magic bytes, never from a file name.
- `prepare` decodes (HEIC through pillow-heif, PDF page 1 through pypdfium2) with a pixel limit
  against decompression bombs, applies the EXIF orientation and the user's rotation, fits the
  long edge within 1568 px and writes a JPEG at quality 90 with no metadata (so no GPS).
  Boxes the model returns refer to this prepared image, and crops are cut from it.
- `quality` measures brightness and sharpness so the UI can warn before reading.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Literal

from PIL import Image, ImageFilter, ImageOps, ImageStat, UnidentifiedImageError

__all__ = [
    "LONG_EDGE",
    "MAX_PIXELS",
    "ImageError",
    "Prepared",
    "Quality",
    "UnsupportedType",
    "crop",
    "prepare",
    "quality",
    "sniff",
    "to_grid",
    "to_pixels",
]

LONG_EDGE = 1568
JPEG_QUALITY = 90
MAX_PIXELS = 50_000_000
PDF_SCALE = 2.0  # 144 dpi: enough for small print, well under the pixel limit for A4
CROP_EXPAND = 0.08
CROP_MIN = 64
DARK_MEAN = 60.0
BLUR_EDGE_MEAN = 4.0
Image.MAX_IMAGE_PIXELS = MAX_PIXELS

FileType = Literal["jpeg", "png", "webp", "heic", "pdf"]


class ImageError(ValueError):
    """The bytes are not an image Munim can use. `message_key` names the UI message."""

    message_key = "paper.err.corrupt"


class UnsupportedType(ImageError):
    message_key = "paper.err.type"


@dataclass(frozen=True)
class Prepared:
    jpeg: bytes
    width: int
    height: int
    file_type: FileType


@dataclass(frozen=True)
class Quality:
    brightness: float
    sharpness: float
    dark: bool
    blurred: bool


def sniff(data: bytes) -> FileType:
    """The file type from its first bytes. Raise UnsupportedType for anything else."""
    head = data[:32]
    if head.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    if head[4:8] == b"ftyp" and head[8:12] in {
        b"heic",
        b"heix",
        b"hevc",
        b"hevx",
        b"mif1",
        b"msf1",
    }:
        return "heic"
    if head.startswith(b"%PDF-"):
        return "pdf"
    raise UnsupportedType("not a JPEG, PNG, WebP, HEIC or PDF file")


def _decode(data: bytes, kind: FileType) -> Image.Image:
    if kind == "pdf":
        return _pdf_first_page(data)
    if kind == "heic":
        import pillow_heif

        pillow_heif.register_heif_opener()
    try:
        image = Image.open(io.BytesIO(data))
        # Pillow only refuses images above twice its limit; refuse anything above it, before
        # any pixel is decoded.
        if image.width * image.height > MAX_PIXELS:
            raise ImageError("the image has too many pixels")
        image.load()
    except Image.DecompressionBombError as exc:
        raise ImageError("the image has too many pixels") from exc
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError) as exc:
        raise ImageError("the image cannot be decoded") from exc
    return image


def _pdf_first_page(data: bytes) -> Image.Image:
    import pypdfium2 as pdfium

    try:
        document = pdfium.PdfDocument(data)
    except pdfium.PdfiumError as exc:
        raise ImageError("the PDF cannot be opened") from exc
    try:
        if len(document) == 0:
            raise ImageError("the PDF has no pages")
        page = document[0]
        width, height = page.get_size()
        if width * height * PDF_SCALE * PDF_SCALE > MAX_PIXELS:
            raise ImageError("the PDF page is too large")
        image: Image.Image = page.render(scale=PDF_SCALE).to_pil()
        return image
    finally:
        document.close()


def prepare(data: bytes, rotation: int = 0) -> Prepared:
    """Decode, orient, rotate (a multiple of 90, clockwise), fit and re-encode as a clean JPEG."""
    if rotation % 90:
        raise ValueError("rotation must be a multiple of 90 degrees")
    kind = sniff(data)
    image = _decode(data, kind)
    image = ImageOps.exif_transpose(image) or image
    if rotation % 360:
        image = image.rotate(-(rotation % 360), expand=True)
    image = image.convert("RGB")
    image.thumbnail((LONG_EDGE, LONG_EDGE), Image.Resampling.LANCZOS)
    out = io.BytesIO()
    image.save(out, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return Prepared(jpeg=out.getvalue(), width=image.width, height=image.height, file_type=kind)


def to_pixels(box: tuple[int, int, int, int], width: int, height: int) -> tuple[int, int, int, int]:
    """[y1, x1, y2, x2] on the 0-1000 grid to (left, top, right, bottom) pixels."""
    y1, x1, y2, x2 = box
    return (
        round(x1 / 1000 * width),
        round(y1 / 1000 * height),
        round(x2 / 1000 * width),
        round(y2 / 1000 * height),
    )


def to_grid(
    pixels: tuple[int, int, int, int], width: int, height: int
) -> tuple[int, int, int, int]:
    """(left, top, right, bottom) pixels to [y1, x1, y2, x2] on the 0-1000 grid."""
    left, top, right, bottom = pixels
    return (
        round(top / height * 1000),
        round(left / width * 1000),
        round(bottom / height * 1000),
        round(right / width * 1000),
    )


def crop(prepared_jpeg: bytes, box: tuple[int, int, int, int]) -> bytes:
    """Cut a box from the prepared image, grown by 8% and to at least 64 px a side, as JPEG."""
    image = Image.open(io.BytesIO(prepared_jpeg))
    width, height = image.size
    left, top, right, bottom = to_pixels(box, width, height)
    grow_x = max(round((right - left) * CROP_EXPAND), (CROP_MIN - (right - left) + 1) // 2, 0)
    grow_y = max(round((bottom - top) * CROP_EXPAND), (CROP_MIN - (bottom - top) + 1) // 2, 0)
    area = (
        max(0, left - grow_x),
        max(0, top - grow_y),
        min(width, right + grow_x),
        min(height, bottom + grow_y),
    )
    out = io.BytesIO()
    image.crop(area).convert("RGB").save(out, format="JPEG", quality=JPEG_QUALITY)
    return out.getvalue()


def quality(prepared_jpeg: bytes) -> Quality:
    """Mean brightness (0-255) and mean edge strength; flags a dark or blurred photo."""
    gray = Image.open(io.BytesIO(prepared_jpeg)).convert("L")
    brightness = float(ImageStat.Stat(gray).mean[0])
    edges = gray.filter(ImageFilter.FIND_EDGES)
    sharpness = float(ImageStat.Stat(edges).mean[0])
    return Quality(
        brightness=brightness,
        sharpness=sharpness,
        dark=brightness < DARK_MEAN,
        blurred=sharpness < BLUR_EDGE_MEAN,
    )
