from __future__ import annotations

import math
import re
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse

import qrcode
from PIL import Image, ImageColor, ImageDraw, ImageOps, UnidentifiedImageError
from qrcode.constants import ERROR_CORRECT_H
from qrcode.util import pattern_position


Image.MAX_IMAGE_PIXELS = 25_000_000

PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
STYLE_LABELS = {
    "estrellas": "Estrellas",
    "corazones": "Corazones",
    "palomitas": "Palomitas",
    "circulos": "Círculos",
    "cuadritos": "Cuadritos",
    "clasico": "QR típico",
    "personalizado": "Figura personalizada",
}


@dataclass(frozen=True)
class UploadedImage:
    filename: str
    content: bytes


def read_url_file(content: bytes) -> list[str]:
    text = None
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            text = content.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise ValueError("No se pudo leer el archivo URL origen.txt.")
    urls = [line.strip() for line in text.splitlines() if line.strip()]
    if not urls:
        raise ValueError("URL origen.txt está vacío.")
    return urls


def is_valid_url(value: str) -> bool:
    if len(value) > 2048:
        return False
    parsed = urlparse(value)
    return parsed.scheme.lower() in {"http", "https"} and bool(parsed.netloc)


def validate_color(value: str) -> tuple[int, int, int]:
    try:
        rgb = tuple(ImageColor.getrgb(value)[:3])
    except ValueError as exc:
        raise ValueError("El color seleccionado no es válido.") from exc
    luminance = relative_luminance(rgb)
    contrast = 1.05 / (luminance + 0.05)
    if contrast < 2.5:
        raise ValueError("El color es demasiado claro para leerse sobre fondo blanco.")
    return rgb


def relative_luminance(rgb: tuple[int, int, int]) -> float:
    values = []
    for channel in rgb:
        value = channel / 255.0
        values.append(value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4)
    return 0.2126 * values[0] + 0.7152 * values[1] + 0.0722 * values[2]


def photo_number_score(filename: str, number: int) -> tuple[int, str] | None:
    path = Path(filename)
    if path.suffix.lower() not in PHOTO_EXTENSIONS:
        return None
    stem = path.stem.strip()
    exact_forms = {str(number), f"{number:02d}", f"{number:03d}", f"{number:04d}"}
    if stem in exact_forms:
        return (0, filename.casefold())
    match = re.match(r"^(\d+)(?:[ _.-].*)?$", stem)
    if match and int(match.group(1)) == number:
        return (1, filename.casefold())
    return None


def find_photo(photos: list[UploadedImage], number: int) -> tuple[UploadedImage | None, list[UploadedImage]]:
    candidates: list[tuple[tuple[int, str], UploadedImage]] = []
    for photo in photos:
        score = photo_number_score(photo.filename, number)
        if score is not None:
            candidates.append((score, photo))
    candidates.sort(key=lambda item: item[0])
    matches = [item[1] for item in candidates]
    return (matches[0] if matches else None, matches)


def verify_image(content: bytes, filename: str, require_png: bool = False) -> None:
    if not content:
        raise ValueError(f'El archivo "{filename}" está vacío.')
    try:
        with Image.open(BytesIO(content)) as image:
            image.verify()
            image_format = (image.format or "").upper()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError(f'"{filename}" no es una imagen válida.') from exc
    if require_png and image_format != "PNG":
        raise ValueError("La figura personalizada debe ser un archivo PNG.")


def create_custom_mask(content: bytes, size: int) -> Image.Image:
    source = Image.open(BytesIO(content)).convert("RGBA")
    alpha = source.getchannel("A")
    if alpha.getextrema()[0] < 255:
        mask = alpha
    else:
        mask = ImageOps.invert(ImageOps.grayscale(source.convert("RGB")))
    bbox = mask.getbbox()
    if bbox is None:
        raise ValueError("La figura personalizada es completamente transparente.")
    mask = mask.crop(bbox)
    maximum = max(1, int(size * 0.96))
    mask.thumbnail((maximum, maximum), Image.Resampling.LANCZOS)
    tile = Image.new("L", (size, size), 0)
    tile.paste(mask, ((size - mask.width) // 2, (size - mask.height) // 2))
    # El centro oscuro mantiene la muestra del módulo incluso con siluetas muy abiertas.
    draw = ImageDraw.Draw(tile)
    center_pad = max(1, int(size * 0.38))
    draw.ellipse((center_pad, center_pad, size - center_pad, size - center_pad), fill=255)
    return tile


def is_structural_module(row: int, col: int, core_size: int, version: int) -> bool:
    in_top = row <= 8
    in_bottom = row >= core_size - 9
    in_left = col <= 8
    in_right = col >= core_size - 9
    if (in_top and in_left) or (in_top and in_right) or (in_bottom and in_left):
        return True
    if row in {6, 8} or col in {6, 8}:
        return True
    positions = pattern_position(version)
    for center_row in positions:
        for center_col in positions:
            if abs(row - center_row) <= 2 and abs(col - center_col) <= 2:
                return True
    if version >= 7:
        if row <= 5 and core_size - 11 <= col <= core_size - 9:
            return True
        if col <= 5 and core_size - 11 <= row <= core_size - 9:
            return True
    return False


def draw_star(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], fill: tuple[int, int, int]) -> None:
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    outer = min(x1 - x0, y1 - y0) * 0.50
    inner = outer * 0.62
    points = []
    for index in range(10):
        radius = outer if index % 2 == 0 else inner
        angle = -math.pi / 2 + index * math.pi / 5
        points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    draw.polygon(points, fill=fill)


def draw_heart(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], fill: tuple[int, int, int]) -> None:
    x0, y0, x1, y1 = box
    width, height = x1 - x0, y1 - y0
    points = [
        (0.50, 0.95), (0.12, 0.59), (0.03, 0.35), (0.11, 0.13),
        (0.30, 0.03), (0.50, 0.23), (0.70, 0.03), (0.89, 0.13),
        (0.97, 0.35), (0.88, 0.59),
    ]
    draw.polygon([(x0 + px * width, y0 + py * height) for px, py in points], fill=fill)


def draw_check(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], fill: tuple[int, int, int]) -> None:
    x0, y0, x1, y1 = box
    width, height = x1 - x0, y1 - y0
    points = [
        (0.01, 0.45), (0.24, 0.22), (0.44, 0.44),
        (0.78, 0.03), (0.99, 0.25), (0.44, 0.97),
    ]
    draw.polygon([(x0 + px * width, y0 + py * height) for px, py in points], fill=fill)
    center = int(min(width, height) * 0.13)
    cx, cy = int((x0 + x1) / 2), int((y0 + y1) / 2)
    draw.ellipse((cx - center, cy - center, cx + center, cy + center), fill=fill)


def draw_module(
    canvas: Image.Image,
    draw: ImageDraw.ImageDraw,
    style: str,
    x: int,
    y: int,
    box_size: int,
    color: tuple[int, int, int],
    structural: bool,
    custom_mask: Image.Image | None,
) -> None:
    if structural or style == "clasico":
        draw.rectangle((x, y, x + box_size - 1, y + box_size - 1), fill=color)
        return
    pad_ratio = 0.02 if style in {"estrellas", "palomitas"} else 0.07
    if style == "cuadritos":
        pad_ratio = 0.13
    pad = max(1, int(box_size * pad_ratio))
    box = (x + pad, y + pad, x + box_size - pad, y + box_size - pad)
    if style == "circulos":
        draw.ellipse(box, fill=color)
    elif style == "cuadritos":
        draw.rounded_rectangle(box, radius=max(1, box_size // 10), fill=color)
    elif style == "estrellas":
        draw_star(draw, box, color)
    elif style == "corazones":
        draw_heart(draw, box, color)
    elif style == "palomitas":
        draw_check(draw, box, color)
    elif style == "personalizado":
        if custom_mask is None:
            raise ValueError("Falta la figura personalizada.")
        tile = Image.new("RGBA", (box_size, box_size), (*color, 255))
        tile.putalpha(custom_mask)
        canvas.alpha_composite(tile, (x, y))
    else:
        raise ValueError(f"Estilo desconocido: {style}")


def add_center_photo(qr_image: Image.Image, photo_content: bytes, core_size: int) -> Image.Image:
    photo = ImageOps.exif_transpose(Image.open(BytesIO(photo_content))).convert("RGB")
    canvas_size = qr_image.width
    ratio = 0.15 if core_size <= 25 else 0.16 if core_size <= 29 else 0.18
    photo_size = max(64, int(canvas_size * ratio))
    frame = max(6, int(photo_size * 0.08))
    inner_size = photo_size - frame * 2
    photo = ImageOps.fit(photo, (inner_size, inner_size), method=Image.Resampling.LANCZOS)

    photo_rgba = photo.convert("RGBA")
    photo_mask = Image.new("L", (inner_size, inner_size), 0)
    radius = max(8, int(inner_size * 0.16))
    ImageDraw.Draw(photo_mask).rounded_rectangle(
        (0, 0, inner_size - 1, inner_size - 1), radius=radius, fill=255
    )
    photo_rgba.putalpha(photo_mask)

    framed = Image.new("RGBA", (photo_size, photo_size), (255, 255, 255, 255))
    frame_mask = Image.new("L", (photo_size, photo_size), 0)
    ImageDraw.Draw(frame_mask).rounded_rectangle(
        (0, 0, photo_size - 1, photo_size - 1), radius=radius + frame, fill=255
    )
    framed.putalpha(frame_mask)
    framed.alpha_composite(photo_rgba, (frame, frame))

    result = qr_image.copy()
    position = ((canvas_size - photo_size) // 2, (canvas_size - photo_size) // 2)
    result.alpha_composite(framed, position)
    return result


def generate_qr(
    url: str,
    photo_content: bytes,
    style: str,
    color: tuple[int, int, int],
    custom_content: bytes | None = None,
) -> bytes:
    if style not in STYLE_LABELS:
        raise ValueError("El estilo solicitado no existe.")
    border = 4
    qr = qrcode.QRCode(version=None, error_correction=ERROR_CORRECT_H, box_size=1, border=border)
    qr.add_data(url)
    qr.make(fit=True)
    matrix = qr.get_matrix()
    matrix_size = len(matrix)
    core_size = matrix_size - border * 2
    box_size = max(12, min(30, 1440 // matrix_size))
    image_size = matrix_size * box_size
    canvas = Image.new("RGBA", (image_size, image_size), (255, 255, 255, 255))
    draw = ImageDraw.Draw(canvas)
    custom_mask = None
    if style == "personalizado":
        if not custom_content:
            raise ValueError("Debes subir el PNG de la figura personalizada.")
        custom_mask = create_custom_mask(custom_content, box_size)

    for matrix_row, row in enumerate(matrix):
        for matrix_col, dark in enumerate(row):
            if not dark:
                continue
            core_row = matrix_row - border
            core_col = matrix_col - border
            structural = (
                0 <= core_row < core_size
                and 0 <= core_col < core_size
                and is_structural_module(core_row, core_col, core_size, qr.version)
            )
            draw_module(
                canvas,
                draw,
                style,
                matrix_col * box_size,
                matrix_row * box_size,
                box_size,
                color,
                structural,
                custom_mask,
            )

    result = add_center_photo(canvas, photo_content, core_size).convert("RGB")
    output = BytesIO()
    result.save(output, "PNG", optimize=True)
    return output.getvalue()


def custom_style_filename(filename: str | None) -> str:
    if not filename:
        return "personalizado"
    name = re.sub(r"[^A-Za-z0-9_-]+", "_", Path(filename).stem).strip("_") or "figura"
    return f"personalizado_{name}"
