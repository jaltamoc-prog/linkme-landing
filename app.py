# v1.089 Calculadora ISR y generaQR bajo converte.uno
# Integra generaQR en /generaqr/, conserva la calculadora en /calculadora-isr/,
# publica ads.txt y declara ambas herramientas en el sitemap.
# Base: v1.088 Landing sin referencias a Google Wallet
# v1.086 Identidad SEO inequívoca de CONVERTE para Google
# Define marca, sitio y aplicación; conserva sitemap, robots y redirecciones.
# v1.085 Sitemap y robots para indexación pública de converte.uno
# Añade exclusivamente /sitemap.xml y /robots.txt para Google Search Console.
# v1.084 Redirección pública garantizada de linkme.life en el navegador
# Conserva el intento de redirección HTTP y añade respaldo del lado del cliente
# porque Render oculta el host original antes de entregar algunas solicitudes.
# v1.083 Redirección reforzada de linkme.life a converte.uno detrás de Render
# Reconoce el dominio público original enviado por el proxy sin cambiar rutas,
# plantillas, DNS ni la arquitectura de la landing.
# v1.082 CONVERTE™ en converte.uno, favicon y accesos móviles actualizados
# Cambia exclusivamente la marca y los accesos públicos; conserva la arquitectura.
# Base: v1.079 CTA clicable del chat y cero friccion
# Convierte la liga oficial de creacion en el boton "Crear mi CONVERTE".
# Base: v1.078 Chat CONVERTE colaborador comercial
# Actualiza el saludo visible y la marca del chat; conserva su sesion y endpoint.
# Base: v1.077 Landing CONVERTE™ - sustitución exclusiva de marca visible
# Base: v1.076 Landing linkme.life® - contenido, navegación audiovisual, legal e identidad
# v1.058 Landing LinkMe - chat compacto, minimizable y sesión controlada
# v1.057 Landing LinkMe - chat movil compacto y cierre siempre accesible
# v1.056 Landing LinkMe - burbuja flotante de LinkMe contigo siempre visible
# v1.055 Landing LinkMe - LinkMe contigo conversacional
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
from herramientas.generaqr import generaqr_bp

app = Flask(__name__)
app.register_blueprint(calculadora_isr_bp, url_prefix="/calculadora-isr")
app.register_blueprint(generaqr_bp, url_prefix="/generaqr")

# v1.027 - Cache busting para que celular cargue última versión de CSS/JS
ASSET_VERSION = "1089"

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

APP_CREATE_URL = os.getenv("LINKME_APP_CREATE_URL", "https://app.converte.uno/nuevo").strip()
LINKME_CHAT_API_URL = os.getenv(
    "LINKME_CHAT_API_URL",
    "https://app.converte.uno/s/linkme-contigo",
).strip()

@app.before_request
def redirigir_dominio_publico_anterior():
    """Mantiene las URLs antiguas, pero presenta converte.uno como puerta de entrada."""
    hosts = {
        (request.host or "").split(":", 1)[0].strip().lower(),
        (request.headers.get("X-Forwarded-Host") or "").split(",", 1)[0].split(":", 1)[0].strip().lower(),
        (request.headers.get("X-Original-Host") or "").split(",", 1)[0].split(":", 1)[0].strip().lower(),
    }

    forwarded = request.headers.get("Forwarded") or ""
    for item in forwarded.split(";"):
        key, separator, value = item.strip().partition("=")
        if separator and key.lower() == "host":
            hosts.add(value.strip().strip('"').split(":", 1)[0].lower())

    if request.method in {"GET", "HEAD"} and hosts.intersection({"linkme.life", "www.linkme.life"}):
        query = f"?{request.query_string.decode('utf-8')}" if request.query_string else ""
        return redirect(f"https://converte.uno{request.path}{query}", code=301)

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
    return render_template(
        "index.html",
        login_url="https://app.converte.uno/s/in",
        create_url="/nuevo",
        market=detectar_mercado(),
        chat_api_url=LINKME_CHAT_API_URL,
    )

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


@app.route("/generaQR")
@app.route("/generaQR/")
def generaqr_compatibilidad():
    return redirect("/generaqr/", code=301)


@app.route("/ads.txt")
def ads_txt():
    contenido = "google.com, pub-5139860234831712, DIRECT, f08c47fec0942fa0\n"
    return Response(contenido, status=200, mimetype="text/plain")


@app.route("/sitemap.xml")
def sitemap():
    contenido = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://converte.uno/</loc>
    <changefreq>weekly</changefreq>
    <priority>1.0</priority>
  </url>
  <url>
    <loc>https://converte.uno/privacidad</loc>
    <changefreq>monthly</changefreq>
    <priority>0.3</priority>
  </url>
  <url>
    <loc>https://converte.uno/terminos</loc>
    <changefreq>monthly</changefreq>
    <priority>0.3</priority>
  </url>
  <url>
    <loc>https://converte.uno/calculadora-isr/</loc>
    <changefreq>monthly</changefreq>
    <priority>0.7</priority>
  </url>
  <url>
    <loc>https://converte.uno/generaqr/</loc>
    <changefreq>monthly</changefreq>
    <priority>0.7</priority>
  </url>
</urlset>
"""
    return Response(contenido, status=200, mimetype="application/xml")


@app.route("/robots.txt")
def robots():
    contenido = """User-agent: *
Allow: /

Sitemap: https://converte.uno/sitemap.xml
"""
    return Response(contenido, status=200, mimetype="text/plain")


@app.route("/favicon.ico")
def favicon():
    return app.send_static_file("img/converte-uno-icon.png")

@app.route("/health")
def health():
    return Response("OK", status=200, mimetype="text/plain")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
