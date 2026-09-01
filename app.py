# v1.054 Landing LinkMe - videos visibles con texto legible
# v1.052 Landing LinkMe - reemplazo de videos 1 y 2
# v1.051 Landing LinkMe - autoplay compatible con iPhone y Android
# v1.050 Landing LinkMe - texto limpio visible sobre video
# v1.049 Landing LinkMe - videos full-screen por sección
# v1.048 Landing LinkMe - videos protagonistas y contraste editorial
# v1.047 Landing LinkMe - motion-first con videos originales de LinkMe
# v1.046 Landing LinkMe - diseño editorial inmersivo motion-first
# v1.045 Landing LinkMe - marco único responsivo sin SVG superpuesto
# v1.044 Landing LinkMe - pantalla ajustada detrás del notch
# v1.043 Landing LinkMe - encaje exacto dentro del contorno original
# v1.042 Landing LinkMe - medios ajustados a la pantalla del celular
# v1.041 Landing LinkMe - recorte inferior dentro del celular
# v1.040 Landing LinkMe - pantalla ajustada dentro del celular
# v1.039 Landing LinkMe - un solo contorno de celular
# v1.038 Landing LinkMe - pantallas dentro del contorno de celular
# v1.037 Landing LinkMe - contorno de celular en imagen y videos
# v1.036 Landing LinkMe - propuesta de valor centrada en el beneficio
# v1.035 Landing LinkMe - ajustes de redacción y estructura
# v1.034 Landing LinkMe - precios México/internacional
# Reemplaza la imagen principal y los videos de perfil privado y público.
# v1.032 Landing LinkMe - FAQ acceso desde cualquier dispositivo
from flask import Flask, render_template, redirect, Response, request
import os

from herramientas.calculadora_isr import calculadora_isr_bp

app = Flask(__name__)
app.register_blueprint(calculadora_isr_bp, url_prefix="/calculadora-isr")

# v1.027 - Cache busting para que celular cargue última versión de CSS/JS
ASSET_VERSION = "1054"

@app.context_processor
def inject_asset_version():
    return {"asset_version": ASSET_VERSION}


def detectar_mercado():
    pais = (
        request.headers.get("CF-IPCountry")
        or request.headers.get("CloudFront-Viewer-Country")
        or request.headers.get("X-Country-Code")
        or ""
    ).strip().upper()
    if pais:
        return "mxn" if pais == "MX" else "usd"
    return "mxn" if "ES-MX" in (request.headers.get("Accept-Language") or "").upper() else "usd"

@app.after_request
def add_cache_headers(response):
    content_type = response.headers.get("Content-Type", "")
    if "text/html" in content_type:
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


# v1.025 Landing LinkMe - header movil botones chips premium
# Dominio comercial: https://www.linkme.style
# La landing vende. La app operativa crea/edita LinkMe.

APP_CREATE_URL = "https://linkme-mvp.onrender.com/nuevo"  # temporal hasta activar DNS app.linkme.style

@app.after_request
def aplicar_headers_basicos(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if request.path.startswith("/static/"):
        response.headers["Cache-Control"] = "public, max-age=604800"
    else:
        response.headers["Cache-Control"] = "no-store"
    return response

@app.route("/")
def index():
    return render_template("index.html", login_url="https://linkme-mvp.onrender.com/s/in", create_url="/nuevo", market=detectar_mercado())

@app.route("/crearmilinkme")
def crearmilinkme():
    return redirect(APP_CREATE_URL, code=302)  # compatibilidad: ruta antigua

@app.route("/nuevo")
def nuevo():
    return redirect(APP_CREATE_URL, code=302)

@app.route("/privacidad")
def privacidad():
    return render_template("privacidad.html", create_url="/nuevo")

@app.route("/terminos")
def terminos():
    return render_template("terminos.html", create_url="/nuevo")

@app.route("/reembolso")
def reembolso():
    return render_template("reembolso.html", create_url="/nuevo")


@app.route("/favicon.ico")
def favicon():
    svg = """<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'><rect width='64' height='64' rx='16' fill='#76bb40'/><text x='32' y='40' text-anchor='middle' font-size='24' font-family='Arial, sans-serif' font-weight='800' fill='white'>LM</text></svg>"""
    return Response(svg, status=200, mimetype="image/svg+xml")

@app.route("/health")
def health():
    return Response("OK", status=200, mimetype="text/plain")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
