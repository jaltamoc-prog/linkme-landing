from flask import Flask, render_template, redirect, Response, request
import os

app = Flask(__name__)

# v1.007 Landing LinkMe - FAQ actualizado
# Dominio comercial: https://www.linkme.style
# La landing vende. La app operativa crea/edita LinkMe.

APP_CREATE_URL = os.environ.get(
    "LINKME_APP_CREATE_URL",
    "https://linkme-mvp.onrender.com/crear?v=154"
)

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
    return render_template("index.html", price_usd="29", create_url="https://www.linkme.style/nuevo")

@app.route("/nuevo")
def nuevo():
    return redirect(APP_CREATE_URL, code=302)

@app.route("/privacidad")
def privacidad():
    return render_template("privacidad.html", create_url="https://www.linkme.style/nuevo")

@app.route("/terminos")
def terminos():
    return render_template("terminos.html", create_url="https://www.linkme.style/nuevo")

@app.route("/reembolso")
def reembolso():
    return render_template("reembolso.html", create_url="https://www.linkme.style/nuevo")


@app.route("/favicon.ico")
def favicon():
    svg = """<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'><rect width='64' height='64' rx='16' fill='#76bb40'/><text x='32' y='40' text-anchor='middle' font-size='24' font-family='Arial, sans-serif' font-weight='800' fill='white'>LM</text></svg>"""
    return Response(svg, status=200, mimetype="image/svg+xml")

@app.route("/health")
def health():
    return Response("OK", status=200, mimetype="text/plain")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
