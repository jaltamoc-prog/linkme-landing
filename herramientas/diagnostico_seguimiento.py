# -*- coding: utf-8 -*-
"""Seguimiento web: comparaciones verificables y pequeñas instantáneas en Stripe.

No hay base de datos ni tareas ocultas. La persona ejecuta una revisión desde su panel.
Se guardan como máximo los últimos doce meses en metadata de SU propia suscripción.
"""
import base64
import datetime as dt
import json
import re
import zlib

PRICE_ID = "price_1UVcyeFHNcj4CFU195mIQ9kE"
AMOUNT = 34900
PORTAL = "https://billing.stripe.com/p/login/28EaEXfqN1xc0r120L6J200"
FIELDS = ("checked", "title", "description", "canonical", "h1", "noalt",
          "noindex", "viewport", "jsonld", "contact", "booking", "purchase", "forms")
LABELS = {
    "title": "Título de la página",
    "description": "Descripción para buscadores",
    "canonical": "URL canónica",
    "h1": "Encabezados H1",
    "noalt": "Imágenes sin texto alternativo",
    "noindex": "Directiva noindex",
    "viewport": "Configuración para celulares",
    "jsonld": "Bloques de datos estructurados",
    "contact": "Enlaces de contacto detectables",
    "booking": "Enlaces de reserva detectables",
    "purchase": "Enlaces de compra detectables",
    "forms": "Formularios HTML",
}
BOOL_FIELDS = {"noindex", "viewport", "contact", "booking", "purchase"}


def encode(a):
    """Una cadena de hasta 2 metadatos de 420 caracteres cada uno."""
    values = {k: (str(a.get(k, ""))[:180] if k in
                  ("title", "description", "canonical", "checked")
                  else a.get(k))
              for k in FIELDS}
    data = json.dumps(values, ensure_ascii=False, separators=(",", ":")).encode()
    compressed = base64.urlsafe_b64encode(zlib.compress(data, 9)).decode()
    if len(compressed) > 800:
        raise ValueError("El resumen de esta página excede el límite permitido.")
    return compressed


def decode(raw):
    if not isinstance(raw, str) or not 1 <= len(raw) <= 800:
        raise ValueError("Resumen inválido.")
    try:
        packed = base64.urlsafe_b64decode(raw)
        obj = zlib.decompressobj()
        uncompressed = obj.decompress(packed, 4000)
        if obj.unconsumed_tail or len(uncompressed) >= 4000:
            raise ValueError("Datos demasiado grandes")
        data = json.loads(uncompressed + obj.flush())
        if not isinstance(data, dict) or any(k not in data for k in FIELDS):
            raise ValueError("Datos incompletos")
        return data
    except (ValueError, TypeError, KeyError, zlib.error, json.JSONDecodeError,
            base64.binascii.Error):
        raise ValueError("No fue posible interpretar la revisión guardada.") from None


def baseline_metadata(a):
    raw = encode(a)
    return {"monitor_base0": raw[:420], "monitor_base1": raw[420:],
            "monitor_url": str(a["url"])[:350], "monitor_goal": str(a.get("goal", "contactos")),
            "monitor_service": "diagnostico-web-seguimiento"}


def read_baseline(meta):
    return decode((meta.get("monitor_base0") or "") + (meta.get("monitor_base1") or ""))


def month_key(date=None):
    date = date or dt.datetime.now(dt.timezone.utc)
    return "monitor_m" + date.strftime("%Y%m")


def history(meta):
    rows = []
    for key in sorted(meta):
        if re.fullmatch(r"monitor_m\d{6}_0", key):
            prefix = key[:-2]
            try:
                item = decode(meta[key] + meta.get(prefix + "_1", ""))
                rows.append({"month": key[9:15], "audit": item})
            except ValueError:
                continue
    return rows[-12:]


def differences(previous, current):
    rows = []
    for key, label in LABELS.items():
        before = previous.get(key)
        after = current.get(key)
        if before != after:
            if key in BOOL_FIELDS:
                fmt = lambda x: "Sí" if x else "No"
            else:
                fmt = lambda x: str(x)[:110] if x not in (None, "") else "Ausente"
            rows.append({"field":label, "previous":fmt(before), "current":fmt(after)})
    return rows


def month_updates(meta, current, now=None):
    """Solo guarda un registro por mes. Preserva como máximo doce meses."""
    prefix = month_key(now)
    raw = encode(current)
    changes = {prefix + "_0": raw[:420], prefix + "_1": raw[420:]}
    existing = sorted(k[:-2] for k in meta if re.fullmatch(r"monitor_m\d{6}_0", k))
    if prefix not in existing:
        existing.append(prefix)
    for obsolete in existing[:-12]:
        changes[obsolete + "_0"] = ""
        changes[obsolete + "_1"] = ""
    return changes


def customer_visible_status(subscription):
    status = subscription.get("status", "unknown")
    canceled = bool(subscription.get("cancel_at_period_end"))
    if status == "active" and canceled:
        return "Activa, sin renovación automática"
    if status == "active":
        return "Activa, con renovación mensual"
    return {"past_due": "Pago pendiente; acceso temporalmente suspendido",
            "canceled": "Cancelada", "unpaid": "Sin pago",
            "incomplete": "Pendiente de primer pago"}.get(status, status)
