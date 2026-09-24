from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from io import BytesIO
from urllib.parse import quote, urlsplit, urlunsplit

from flask import Blueprint, current_app, jsonify, render_template, request, send_file
from werkzeug.exceptions import RequestEntityTooLarge

from .qr_engine import STYLE_LABELS, generate_qr, validate_color, verify_image


APP_VERSION = "1.089"
MAX_FILE_BYTES = 15 * 1024 * 1024

generaqr_bp = Blueprint(
    "generaqr",
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/assets",
)


@generaqr_bp.record_once
def configure_upload_limit(state):
    if state.app.config.get("MAX_CONTENT_LENGTH") is None:
        state.app.config["MAX_CONTENT_LENGTH"] = int(os.environ.get("MAX_UPLOAD_MB", "35")) * 1024 * 1024


def render_page(message: str | None = None, status: int = 200):
    return render_template(
        "generaqr/index.html",
        error=message,
        style_labels=STYLE_LABELS,
        app_version=APP_VERSION,
    ), status


def api_error(message: str, status: int = 400):
    return jsonify({"error": message}), status


def normalize_website(value: str) -> str:
    website = (value or "").strip()
    if not website:
        raise ValueError("Escribe la página web que llevará el QR.")
    if len(website) > 2048:
        raise ValueError("La dirección web es demasiado larga.")
    if any(character.isspace() for character in website):
        raise ValueError("La página web no debe contener espacios.")
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", website):
        website = f"https://{website}"

    parsed = urlsplit(website)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Escribe una página web válida, por ejemplo: converte.uno.")
    if parsed.username or parsed.password:
        raise ValueError("La página web no puede incluir usuario ni contraseña.")

    try:
        hostname = parsed.hostname.encode("idna").decode("ascii")
        port = f":{parsed.port}" if parsed.port else ""
    except (UnicodeError, ValueError) as exc:
        raise ValueError("La página web contiene un dominio o puerto no válido.") from exc

    return urlunsplit(
        (parsed.scheme.lower(), f"{hostname}{port}", parsed.path or "", parsed.query, parsed.fragment)
    )


def safe_download_name(url: str) -> str:
    hostname = urlsplit(url).hostname or "pagina-web"
    hostname = hostname.removeprefix("www.")
    safe_host = re.sub(r"[^a-zA-Z0-9.-]+", "-", hostname).strip("-.") or "pagina-web"
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"QR_{safe_host}_{timestamp}.png"


@generaqr_bp.errorhandler(RequestEntityTooLarge)
def upload_too_large(_error):
    if request.path.endswith("/generar"):
        return api_error("La fotografía supera el límite permitido de 15 MB.", 413)
    return render_page("La carga supera el límite permitido.", 413)


@generaqr_bp.get("/")
def index():
    return render_page()


@generaqr_bp.post("/generar")
def generate():
    try:
        url = normalize_website(request.form.get("website_url", ""))
        style = request.form.get("style", "clasico")
        if style not in STYLE_LABELS:
            return api_error("Selecciona un diseño válido.")
        color = validate_color(request.form.get("qr_color", "#000000"))

        photo_upload = request.files.get("photo_file")
        camera_upload = request.files.get("photo_camera")
        upload = next(
            (item for item in (photo_upload, camera_upload) if item and item.filename),
            None,
        )
        if upload is None:
            return api_error("Selecciona una fotografía o toma una con la cámara.")

        photo_content = upload.read(MAX_FILE_BYTES + 1)
        if len(photo_content) > MAX_FILE_BYTES:
            return api_error("La fotografía supera 15 MB.")
        verify_image(photo_content, upload.filename or "fotografia")

        custom_content = None
        if style == "personalizado":
            custom_upload = request.files.get("custom_shape")
            if not custom_upload or not custom_upload.filename:
                return api_error("Elegiste figura personalizada; falta subir su PNG transparente.")
            custom_content = custom_upload.read(MAX_FILE_BYTES + 1)
            if len(custom_content) > MAX_FILE_BYTES:
                return api_error("La figura personalizada supera 15 MB.")
            verify_image(custom_content, custom_upload.filename, require_png=True)

        png = generate_qr(url, photo_content, style, color, custom_content)
        filename = safe_download_name(url)
        response = send_file(
            BytesIO(png),
            mimetype="image/png",
            as_attachment=False,
            download_name=filename,
            max_age=0,
        )
        response.headers["X-QR-Filename"] = filename
        response.headers["X-QR-Website"] = quote(url, safe=":/?&=#%.-_~")
        response.headers["Access-Control-Expose-Headers"] = "X-QR-Filename, X-QR-Website"
        return response
    except ValueError as exc:
        return api_error(str(exc))
    except Exception:
        current_app.logger.exception("Error inesperado durante la generación individual")
        return api_error("No fue posible generar el QR. Revisa los datos e inténtalo de nuevo.", 500)
