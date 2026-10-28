# -*- coding: utf-8 -*-
"""Diagnostico web publico de Converte.

Adaptacion segura de las reglas de Revisar Metricas Web:
sin credenciales de Google, sin acceso a redes privadas y sin almacenar leads.
"""
import ipaddress
import os
import re
import socket
import threading
import time
from collections import defaultdict, deque
from urllib.parse import urljoin, urlsplit, urlunsplit, urlencode, quote

import urllib3
from bs4 import BeautifulSoup
from flask import Blueprint, abort, current_app, redirect, render_template, request, make_response
from werkzeug.exceptions import HTTPException

bp = Blueprint("diagnostico_web", __name__, url_prefix="/diagnostico-web")
GOALS = {
    "contactos": "Conseguir mensajes y llamadas",
    "ventas": "Facilitar compras y pedidos",
    "reservas": "Conseguir citas o reservas",
    "informacion": "Presentar la empresa y generar confianza",
}
MAX_HTML = 5_000_000
_lock = threading.Lock()
_by_ip = defaultdict(deque)
_global = deque()
_cache = {}
_slots = threading.BoundedSemaphore(3)


def public_url(raw):
    raw = (raw or "").strip()
    if not raw or len(raw) > 350 or any(ord(ch) < 32 for ch in raw):
        raise ValueError("Escribe una direccion valida de hasta 350 caracteres.")
    if "://" not in raw:
        raw = "https://" + raw
    try:
        parsed = urlsplit(raw)
        host = (parsed.hostname or "").rstrip(".").lower().encode("idna").decode("ascii")
        port = parsed.port
    except (ValueError, UnicodeError, AttributeError):
        raise ValueError("No se reconoce el dominio.") from None
    if parsed.scheme not in ("https", "http") or parsed.username or parsed.password:
        raise ValueError("Solo se admiten paginas publicas HTTP o HTTPS.")
    if port not in (None, 443 if parsed.scheme == "https" else 80):
        raise ValueError("No se admiten puertos especiales.")
    if (not host or "." not in host or ".." in host or not re.fullmatch(r"[a-z0-9.-]+", host)
        or host.endswith((".local", ".localhost", ".internal", ".test", ".invalid", ".onion"))
        or host == "metadata.google.internal"):
        raise ValueError("Introduce un dominio publico.")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError("Utiliza un dominio, no una direccion IP.")
    return urlunsplit((parsed.scheme, host, parsed.path or "/", "", ""))


def verified_address(host, port):
    try:
        addresses = {part[4][0] for part in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)}
    except socket.gaierror:
        raise ValueError("No encontramos ese dominio. Revisa la direccion.") from None
    if not addresses or any(not ipaddress.ip_address(ip).is_global for ip in addresses):
        raise ValueError("La direccion apunta a una red no publica.")
    return sorted(addresses, key=lambda ip: (":" in ip, ip))[0]


def fetch_html(url):
    target = public_url(url)
    for _ in range(4):
        p = urlsplit(target)
        port = 443 if p.scheme == "https" else 80
        ip = verified_address(p.hostname, port)
        cls = urllib3.HTTPSConnectionPool if p.scheme == "https" else urllib3.HTTPConnectionPool
        opts = dict(host=ip, port=port, maxsize=1, block=True,
                    timeout=urllib3.Timeout(connect=3, read=7, total=12), retries=False)
        if p.scheme == "https":
            opts.update(server_hostname=p.hostname, assert_hostname=p.hostname, cert_reqs="CERT_REQUIRED")
        pool = cls(**opts)
        response = None
        try:
            response = pool.urlopen("GET", p.path or "/", redirect=False, preload_content=False,
                headers={"Host": p.hostname, "Accept": "text/html,application/xhtml+xml",
                         "Accept-Encoding": "identity",
                         "User-Agent": "ConverteDiagnosticoWeb/1.0 (+https://converte.uno/diagnostico-web/)"})
            if response.status in (301, 302, 303, 307, 308):
                location = response.headers.get("Location", "")
                if not location:
                    raise ValueError("La pagina redirige sin una direccion valida.")
                target = public_url(urljoin(target, location))
                continue
            if response.status != 200:
                raise ValueError("Esta pagina respondio HTTP " + str(response.status) + ".")
            content_type = response.headers.get("Content-Type", "").lower()
            if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
                raise ValueError("Esa direccion no devuelve una pagina HTML.")
            length = response.headers.get("Content-Length", "")
            if length.isdigit() and int(length) > MAX_HTML:
                raise ValueError("La pagina es demasiado grande para la auditoria gratuita.")
            data = response.read(MAX_HTML + 1, decode_content=True)
            if len(data) > MAX_HTML:
                raise ValueError("La pagina es demasiado grande para la auditoria gratuita.")
            return target, data.decode("utf-8", errors="replace"), response.headers
        finally:
            if response is not None:
                response.release_conn()
            pool.close()
    raise ValueError("La pagina tiene demasiadas redirecciones.")


def analyse(url):
    final, html, headers = fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")
    meta = soup.find("meta", attrs={"name": re.compile("^description$", re.I)})
    robots = soup.find("meta", attrs={"name": re.compile("^robots$", re.I)})
    canonical = soup.find("link", rel=lambda val: val and "canonical" in val)
    links = [(a.get("href", "").lower(), a.get_text(" ", strip=True).lower()[:110])
             for a in soup.find_all("a", href=True)]
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    description = meta.get("content", "").strip() if meta else ""
    can = canonical.get("href", "").strip() if canonical else ""
    noindex = "noindex" in ((robots.get("content", "") if robots else "") +
                            " " + headers.get("X-Robots-Tag", "")).lower()
    contact = any(h.startswith(("tel:", "mailto:", "https://wa.me/", "https://api.whatsapp.com/", "whatsapp:"))
                  for h, _ in links)
    booking = any(any(word in h or word in label for word in
                      ("calendly.com", "cal.com", "reservar", "agendar", "cita", "booking"))
                  for h, label in links)
    purchase = any(any(word in h or word in label for word in
                       ("checkout", "comprar", "cotizar", "pedido", "wa.me/", "pagar"))
                   for h, label in links)
    imgs = soup.find_all("img")
    return {
        "url": final, "checked": time.strftime("%d/%m/%Y %H:%M UTC", time.gmtime()),
        "title": title, "description": description, "canonical": can,
        "noindex": noindex, "h1": len(soup.find_all("h1")), "noalt": sum(not x.has_attr("alt") for x in imgs),
        "viewport": bool(soup.find("meta", attrs={"name": re.compile("^viewport$", re.I)})),
        "jsonld": len(soup.find_all("script", type="application/ld+json")),
        "contact": contact, "booking": booking, "purchase": purchase,
        "forms": len(soup.find_all("form")), "headings": len(soup.find_all(["h2", "h3"])),
    }


def _finding(level, title, reason, action, evidence, effort="Facil"):
    return dict(level=level, title=title, reason=reason, action=action, evidence=evidence, effort=effort)


def report_for(a, goal):
    findings = []
    good = []
    def add(level, title, reason, action, evidence, effort="Facil"):
        findings.append(_finding(level, title, reason, action, evidence, effort))
    good.append("La pagina respondio correctamente y pudimos leer su HTML publico.")
    if a["noindex"]:
        add("Urgente", "Hay una indicacion para no aparecer en Google",
            "Los buscadores pueden excluir esta direccion.", "Confirma con tu desarrollador si noindex es intencional; si esta pagina es publica, revisa ese bloqueo.",
            "Se detecto noindex en HTML o encabezados.", "Moderado")
    else:
        good.append("No encontramos una orden noindex; esto no confirma que Google la haya indexado.")
    if not a["title"]:
        add("Alta", "Tu pagina no tiene un titulo para los buscadores",
            "A Google y a las personas les costara mas identificar su contenido.",
            "Anade un titulo unico que explique el servicio y la marca.",
            "No encontramos la etiqueta title.")
    else:
        good.append("La pagina tiene un titulo identificable.")
    if not a["description"]:
        add("Media", "Falta un resumen claro para buscadores",
            "Google podria mostrar un fragmento que no describa tu oferta.",
            "Escribe una descripcion breve del beneficio, el publico y la accion que deseas que realicen.",
            "No encontramos meta description.")
    if not a["canonical"]:
        add("Media", "Falta indicar la direccion preferida de esta pagina",
            "Las variantes del enlace pueden competir entre si.",
            "Pide a tu desarrollador declarar una URL canonica adecuada a esta pagina.",
            "No encontramos link rel=canonical.")
    if a["h1"] != 1:
        add("Media", "Revisa el encabezado principal",
            "El mensaje de entrada puede resultar menos claro para el visitante.",
            "Usa un encabezado principal descriptivo y evita varios encabezados H1 compitiendo.",
            "Encabezados H1 detectados: " + str(a["h1"]) + ".")
    if a["noalt"]:
        add("Media", "Hay imagenes sin texto alternativo",
            "Las imagenes informativas pueden resultar menos accesibles.",
            "Describe las imagenes informativas; deja alt vacio en las decorativas.",
            "Imagenes sin atributo alt: " + str(a["noalt"]) + ".", "Moderado")
    if not a["viewport"]:
        add("Alta", "No se encontro la configuracion basica para celulares",
            "La web podria no adaptarse bien a pantallas pequenas.",
            "Solicita a tu desarrollador revisar la etiqueta viewport y probar la pagina en un celular.",
            "No encontramos meta viewport.")
    if goal == "contactos" and not a["contact"]:
        add("Alta", "No identificamos contacto directo en el HTML",
            "Quien quiera hablar contigo podria necesitar buscar mas de lo necesario.",
            "Comprueba que WhatsApp, telefono o formulario sean faciles de encontrar, especialmente en celular.",
            "No detectamos enlaces reconocibles de contacto; JavaScript podria cargar otros.")
    if goal == "ventas" and not a["purchase"]:
        add("Alta", "No encontramos una ruta de compra claramente identificable",
            "Alguien interesado podria no saber como iniciar un pedido.",
            "Coloca un boton visible para comprar, pedir una cotizacion o comenzar un pedido.",
            "No encontramos enlaces de compra reconocibles; no se reviso el checkout.")
    if goal == "reservas" and not a["booking"]:
        add("Alta", "No detectamos un acceso reconocible para reservar",
            "Los interesados podrian no identificar el siguiente paso.",
            "Coloca un boton visible para reservar o solicitar una cita.",
            "No se encontraron enlaces de reserva reconocibles; JavaScript podria cargarlos.")
    if goal == "contactos" and a["contact"]:
        good.append("Detectamos un enlace de contacto; hay que comprobar que resulte visible.")
    if goal == "ventas" and a["purchase"]:
        good.append("Se detecto un enlace relacionado con compras o cotizaciones.")
    if goal == "reservas" and a["booking"]:
        good.append("Se detecto un enlace relacionado con reservas.")
    order = {"Urgente": 0, "Alta": 1, "Media": 2}
    findings.sort(key=lambda row: order.get(row["level"], 4))
    return {"findings": findings, "top": findings[:3], "positives": good[:3], "count": len(findings)}


def visitor_ip():
    """Distingue visitantes detras del proxy confiable de Render.

    El ultimo salto X-Forwarded-For es el que agrega el proxy mas cercano.
    Nunca se confia en la primera IP enviada por un cliente.
    """
    if os.getenv("RENDER") == "true":
        forwarded = request.headers.get("X-Forwarded-For", "")
        if forwarded:
            candidate = forwarded.rsplit(",", 1)[-1].strip()
            try:
                address = ipaddress.ip_address(candidate)
                if address.is_global:
                    return address.compressed
            except ValueError:
                pass
    return request.remote_addr or "desconocido"


def cache_exists(url):
    with _lock:
        item = _cache.get(url)
        return bool(item and item[0] > time.monotonic())


def limited(remote_ip):
    """Limita solo auditorias nuevas; resultados en cache no cuestan otra consulta."""
    now = time.monotonic()
    with _lock:
        if len(_by_ip) > 2500:
            # El limite global sigue protegiendo el servicio.
            _by_ip.clear()
        q = _by_ip[remote_ip]
        while q and q[0] <= now - 600:
            q.popleft()
        while _global and _global[0] <= now - 3600:
            _global.popleft()
        if len(q) >= 20 or len(_global) >= 180:
            return True
        q.append(now)
        _global.append(now)
        return False


def cached(url):
    now = time.monotonic()
    with _lock:
        item = _cache.get(url)
        if item and item[0] > now:
            return item[1]
    if not _slots.acquire(blocking=False):
        raise ValueError("Hay varias revisiones simultaneas. Intentalo de nuevo.")
    try:
        result = analyse(url)
        with _lock:
            if len(_cache) > 150:
                _cache.clear()
            _cache[url] = (time.monotonic() + 600, result)
        return result
    finally:
        _slots.release()


def payments_enabled():
    """Los cobros solo se habilitan tras autorización explícita en Render."""
    return (os.getenv("DIAGNOSTICO_PAGOS_ACTIVOS", "") == "1"
            and os.getenv("DIAGNOSTICO_STRIPE_SECRET_KEY", "").startswith("sk_live_")
            and os.getenv("DIAGNOSTICO_STRIPE_PRICE_ID", "").startswith("price_")
            and bool(os.getenv("DIAGNOSTICO_PRICE_LABEL", "").strip()))


def contact_link(url):
    number = re.sub(r"\D", "", os.getenv("DIAGNOSTICO_CONTACT_WHATSAPP", ""))
    if not (10 <= len(number) <= 15):
        return ""
    message = "Hola, revise mi pagina " + url + " en Diagnostico Web y quiero ayuda con las mejoras."
    return "https://wa.me/" + number + "?" + urlencode({"text": message})


def view(url="", goal="contactos", audit=None, summary=None, error="", paid=False, code=200):
    if goal not in GOALS:
        goal = "contactos"
    page = render_template("diagnostico_web.html", url=url, goal=goal, goals=GOALS,
        audit=audit, summary=summary, error=error, paid=paid,
        checkout_enabled=payments_enabled(),
        price_label=os.getenv("DIAGNOSTICO_PRICE_LABEL", "").strip()[:35],
        contact_url=contact_link(url) if audit else "")
    response = make_response(page, code)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Diagnostico-Revision"] = "2026-10-28-limites-v2"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'; img-src 'self' data:; form-action 'self'; base-uri 'none'; frame-ancestors 'self'"
    if audit or error or paid:
        response.headers["X-Robots-Tag"] = "noindex, nofollow"
        response.headers["Referrer-Policy"] = "no-referrer"
    return response


@bp.route("/", methods=["GET", "POST"])
def index():
    if request.method == "GET":
        return view()
    if len(request.get_data(cache=True)) > 4096:
        return view(error="La solicitud es demasiado grande.", code=413)
    raw = request.form.get("url", "")
    goal = request.form.get("objetivo", "contactos")
    try:
        url = public_url(raw)
        if not cache_exists(url) and limited(visitor_ip()):
            response = view(url, goal, error="Se alcanzó temporalmente el límite de sitios nuevos. Puedes volver a revisar una página analizada hace poco, o intentar con otra más tarde.", code=429)
            response.headers["Retry-After"] = "600"
            return response
        result = cached(url)
        return view(url, goal, result, report_for(result, goal))
    except (ValueError, urllib3.exceptions.HTTPError, TimeoutError, OSError) as exc:
        current_app.logger.info("Auditoria web no completada (%s)", type(exc).__name__)
        err = str(exc) if isinstance(exc, ValueError) else "No se pudo acceder a esa web en este momento."
        return view(raw[:350], goal, error=err, code=422)


@bp.route("/comprar", methods=["POST"])
def comprar():
    if not payments_enabled():
        abort(503)
    if limited(request.remote_addr or "desconocido"):
        abort(429)
    try:
        url = public_url(request.form.get("url", ""))
        goal = request.form.get("objetivo", "contactos")
        if goal not in GOALS:
            goal = "contactos"
        cached(url)
        import requests as http
        resp = http.post("https://api.stripe.com/v1/checkout/sessions", timeout=12,
            auth=(os.environ["DIAGNOSTICO_STRIPE_SECRET_KEY"], ""),
            data={"mode": "payment", "line_items[0][price]": os.environ["DIAGNOSTICO_STRIPE_PRICE_ID"],
                  "line_items[0][quantity]": "1",
                  "success_url": "https://converte.uno/diagnostico-web/informe?session_id={CHECKOUT_SESSION_ID}",
                  "cancel_url": "https://converte.uno/diagnostico-web/",
                  "metadata[url]": url, "metadata[goal]": goal})
        resp.raise_for_status()
        destination = resp.json().get("url", "")
        if not destination.startswith("https://checkout.stripe.com/"):
            raise ValueError("Stripe no devolvio un checkout valido.")
        return redirect(destination, code=303)
    except Exception:
        current_app.logger.exception("Fallo al iniciar Stripe Checkout")
        return view(error="No se pudo iniciar el pago; no se efectuo ningun cobro.", code=503)


@bp.route("/informe", methods=["GET"])
def informe():
    sid = request.args.get("session_id", "")
    if not payments_enabled() or not re.fullmatch(r"cs_(test|live)_[A-Za-z0-9]{15,250}", sid):
        abort(404)
    import requests as http
    try:
        response = http.get("https://api.stripe.com/v1/checkout/sessions/" + quote(sid),
            auth=(os.environ["DIAGNOSTICO_STRIPE_SECRET_KEY"], ""), timeout=12)
        response.raise_for_status()
        payment = response.json()
        if payment.get("payment_status") != "paid" or payment.get("status") != "complete":
            abort(403)
        if payment.get("mode") != "payment" or payment.get("amount_total", 0) <= 0:
            abort(403)
        expected_price = os.environ["DIAGNOSTICO_STRIPE_PRICE_ID"]
        items = http.get("https://api.stripe.com/v1/checkout/sessions/" + quote(sid) + "/line_items",
            auth=(os.environ["DIAGNOSTICO_STRIPE_SECRET_KEY"], ""), timeout=12)
        items.raise_for_status()
        line_items = items.json().get("data", [])
        if not any(item.get("price", {}).get("id") == expected_price for item in line_items):
            abort(403)
        meta = payment.get("metadata") or {}
        url = public_url(meta.get("url", ""))
        goal = meta.get("goal", "contactos")
        result = cached(url)
        return view(url, goal, result, report_for(result, goal), paid=True)
    except HTTPException:
        raise
    except Exception:
        current_app.logger.exception("Error al verificar informe de Stripe")
        return view(error="No se pudo recuperar el informe. Contactanos con tu comprobante.", code=503)
