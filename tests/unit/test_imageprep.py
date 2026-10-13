"""Image preparation (docs/AI_SPEC.md 3 and 6, docs/SECURITY_PRIVACY.md uploads, TESTING 3.7)."""

from __future__ import annotations

import io
import struct
import zlib

import pytest
from hypothesis import given
from hypothesis import strategies as st
from PIL import Image, ImageDraw, ImageFilter

from munim_ai import imageprep
from munim_ai.imageprep import ImageError, UnsupportedType

pytestmark = pytest.mark.unit


def image_bytes(img: Image.Image, fmt: str = "JPEG", **kw: object) -> bytes:
    out = io.BytesIO()
    img.save(out, format=fmt, **kw)
    return out.getvalue()


def page(width: int = 800, height: int = 600) -> Image.Image:
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    for y in range(40, height - 40, 30):
        draw.text((40, y), "TAX INVOICE 1,200 x 250.00 = 3,00,000.00", fill="black", font_size=18)
    return img


# ---------------------------------------------------------------- sniff
@pytest.mark.parametrize(
    ("fmt", "kind"), [("JPEG", "jpeg"), ("PNG", "png"), ("WEBP", "webp"), ("PDF", "pdf")]
)
def test_sniff_recognises_supported_types_by_content(fmt: str, kind: str) -> None:
    assert imageprep.sniff(image_bytes(page(100, 80), fmt)) == kind


@pytest.mark.parametrize(
    "data", [b"MZ\x90\x00" + b"\x00" * 60, b"hello, this is text", b"", b"GIF89a" + b"\x00" * 20]
)
def test_sniff_rejects_executables_text_and_other_types(data: bytes) -> None:
    with pytest.raises(UnsupportedType) as info:
        imageprep.sniff(data)
    assert info.value.message_key == "paper.err.type"


# ---------------------------------------------------------------- prepare
def test_prepare_fits_the_long_edge_and_outputs_jpeg() -> None:
    prepared = imageprep.prepare(image_bytes(page(3000, 2000), "PNG"))
    assert (prepared.width, prepared.height) == (1568, 1045)
    assert prepared.jpeg[:3] == b"\xff\xd8\xff"
    assert prepared.file_type == "png"


def test_prepare_never_upscales() -> None:
    prepared = imageprep.prepare(image_bytes(page(400, 300)))
    assert (prepared.width, prepared.height) == (400, 300)


def test_prepare_applies_exif_orientation() -> None:
    img = Image.new("RGB", (200, 100), "white")
    img.putpixel((0, 0), (255, 0, 0))
    exif = img.getexif()
    exif[0x0112] = 6  # rotate 90 clockwise to display
    prepared = imageprep.prepare(image_bytes(img, exif=exif))
    assert (prepared.width, prepared.height) == (100, 200)


def test_prepare_strips_exif_and_gps() -> None:
    img = page(300, 200)
    exif = img.getexif()
    exif[0x010F] = "Synthetic Camera"
    exif[0x8825] = {1: "N", 2: (18.0, 31.0, 0.0)}  # GPS IFD
    prepared = imageprep.prepare(image_bytes(img, exif=exif))
    out = Image.open(io.BytesIO(prepared.jpeg))
    assert dict(out.getexif()) == {}
    assert b"Synthetic Camera" not in prepared.jpeg


@pytest.mark.parametrize("mode", ["CMYK", "LA", "P", "RGBA", "L"])
def test_prepare_converts_any_mode_to_rgb(mode: str) -> None:
    fmt = "JPEG" if mode in ("CMYK", "L") else "PNG"
    prepared = imageprep.prepare(image_bytes(page(120, 90).convert(mode), fmt))
    assert Image.open(io.BytesIO(prepared.jpeg)).mode == "RGB"


@pytest.mark.parametrize("rotation", [90, 180, 270, 360])
def test_prepare_rotates_clockwise_in_quarter_turns(rotation: int) -> None:
    img = Image.new("RGB", (200, 100), "white")
    prepared = imageprep.prepare(image_bytes(img), rotation=rotation)
    expected = (100, 200) if rotation in (90, 270) else (200, 100)
    assert (prepared.width, prepared.height) == expected


def test_prepare_refuses_a_rotation_that_is_not_a_quarter_turn() -> None:
    with pytest.raises(ValueError):
        imageprep.prepare(image_bytes(page(100, 80)), rotation=45)


def bomb_png(width: int, height: int) -> bytes:
    """A PNG whose header claims width x height; the data is tiny and never decoded."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    header = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(b"\x00"))
        + chunk(b"IEND", b"")
    )


def test_prepare_refuses_more_pixels_than_the_limit_before_decoding() -> None:
    with pytest.raises(ImageError) as info:
        imageprep.prepare(bomb_png(10_000, 6_000))  # 60,000,000 pixels
    assert "too many pixels" in str(info.value)


def test_prepare_refuses_a_truncated_file() -> None:
    data = image_bytes(page(400, 300))
    with pytest.raises(ImageError) as info:
        imageprep.prepare(data[: len(data) // 3])
    assert info.value.message_key == "paper.err.corrupt"


def test_prepare_renders_only_the_first_pdf_page() -> None:
    first = Image.new("RGB", (300, 400), "white")
    second = Image.new("RGB", (600, 200), "black")
    pdf = io.BytesIO()
    first.save(pdf, format="PDF", save_all=True, append_images=[second])
    prepared = imageprep.prepare(pdf.getvalue())
    assert prepared.file_type == "pdf"
    assert prepared.height > prepared.width  # the portrait first page, not the landscape second
    out = Image.open(io.BytesIO(prepared.jpeg)).convert("L")
    assert out.getpixel((prepared.width // 2, prepared.height // 2)) > 200  # white, not black


def test_prepare_refuses_a_broken_pdf() -> None:
    with pytest.raises(ImageError):
        imageprep.prepare(b"%PDF-1.4\nnot really a pdf")


# ---------------------------------------------------------------- boxes and crops
def test_full_image_maps_to_the_whole_grid() -> None:
    assert imageprep.to_grid((0, 0, 800, 600), 800, 600) == (0, 0, 1000, 1000)
    assert imageprep.to_pixels((0, 0, 1000, 1000), 800, 600) == (0, 0, 800, 600)


@given(
    w=st.integers(50, 4000),
    h=st.integers(50, 4000),
    data=st.data(),
)
def test_box_round_trip_is_within_one_pixel(w: int, h: int, data: st.DataObject) -> None:
    left = data.draw(st.integers(0, w - 2))
    right = data.draw(st.integers(left + 1, w))
    top = data.draw(st.integers(0, h - 2))
    bottom = data.draw(st.integers(top + 1, h))
    back = imageprep.to_pixels(imageprep.to_grid((left, top, right, bottom), w, h), w, h)
    # The grid has 1000 steps, so on images wider than 1000 px a step is more than a pixel;
    # the round trip is exact to half a grid step.
    tol_x, tol_y = max(1, w / 2000 + 1), max(1, h / 2000 + 1)
    assert abs(back[0] - left) <= tol_x and abs(back[2] - right) <= tol_x
    assert abs(back[1] - top) <= tol_y and abs(back[3] - bottom) <= tol_y


def test_crop_grows_the_box_and_keeps_a_minimum_size() -> None:
    prepared = imageprep.prepare(image_bytes(page(1000, 1000))).jpeg
    big = Image.open(io.BytesIO(imageprep.crop(prepared, (100, 100, 300, 600))))
    assert big.size == (round(500 * 1.16), round(200 * 1.16))
    tiny = Image.open(io.BytesIO(imageprep.crop(prepared, (500, 500, 505, 510))))
    assert tiny.width >= 64 and tiny.height >= 64


def test_crop_is_clamped_to_the_image() -> None:
    prepared = imageprep.prepare(image_bytes(page(1000, 800))).jpeg
    edge = Image.open(io.BytesIO(imageprep.crop(prepared, (0, 0, 1000, 1000))))
    assert edge.size == (1000, 800)


# ---------------------------------------------------------------- quality
def test_quality_passes_a_clean_page() -> None:
    q = imageprep.quality(imageprep.prepare(image_bytes(page())).jpeg)
    assert not q.dark and not q.blurred


def test_quality_flags_a_dark_photo() -> None:
    dark = page().point(lambda v: v // 8)
    q = imageprep.quality(imageprep.prepare(image_bytes(dark)).jpeg)
    assert q.dark is True
    assert q.brightness < imageprep.DARK_MEAN


def test_quality_flags_a_blurred_photo() -> None:
    blurred = page().filter(ImageFilter.GaussianBlur(12))
    q = imageprep.quality(imageprep.prepare(image_bytes(blurred)).jpeg)
    assert q.blurred is True
    assert q.sharpness < imageprep.BLUR_EDGE_MEAN


def test_quality_flags_glare() -> None:
    # A photo page (~180-190 brightness) with a blown-out flash glare hotspot
    photo = page().point(lambda v: int(v * 0.75))
    draw = ImageDraw.Draw(photo)
    draw.rectangle([100, 100, 350, 350], fill="white")
    q = imageprep.quality(imageprep.prepare(image_bytes(photo)).jpeg)
    assert q.glare is True
    assert "paper.err.glare" in q.guidance_keys


def test_quality_flags_corner_fold() -> None:
    fold_img = page()
    draw = ImageDraw.Draw(fold_img)
    # Darken top-left corner (folded over dark shadow)
    draw.polygon([(0, 0), (60, 0), (0, 60)], fill="black")
    q = imageprep.quality(imageprep.prepare(image_bytes(fold_img)).jpeg)
    assert q.corner_fold is True
    assert "paper.err.corner_fold" in q.guidance_keys
