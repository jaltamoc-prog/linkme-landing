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
BASE_FIELDS = ("checked", "title", "description", "canonical", "h1", "noalt",
               "noindex", "viewport", "jsonld", "contact", "booking", "purchase", "forms")
EXTRA_FIELDS = ("schema_version", "keyword", "city", "city_in_page",
                "analytics_signal", "google_profile_link", "internal_links",
                "sitemap_hint", "images_total", "modern_images",
                "images_without_dimensions")
FIELDS = BASE_FIELDS + EXTRA_FIELDS
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
                  ("title", "description", "canonical", "checked", "keyword", "city")
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
        if not isinstance(data, dict) or any(k not in data for k in BASE_FIELDS):
            raise ValueError("Datos incompletos")
        # Las compras y revisiones antiguas siguen pudiendo abrirse.
        for k in EXTRA_FIELDS:
            data.setdefault(k, None)
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



def comparison_pdf(url, goal_label, baseline, latest, previous, goal="contactos", history=None):
    """PDF comparativo de las señales publicas, sin atribuciones de ventas."""
    from io import BytesIO
    from herramientas import diagnostico_evaluacion as business
    from herramientas.diagnostico_pdf import progress_drawing
    from xml.sax.saxutils import escape
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable

    out = BytesIO()
    dark = colors.HexColor("#163b40")
    teal = colors.HexColor("#14767c")
    styles = getSampleStyleSheet()
    t = ParagraphStyle("MTitle", parent=styles["Title"], textColor=dark,
                       fontName="Helvetica-Bold", fontSize=20, leading=25, spaceAfter=15)
    h = ParagraphStyle("MHeading", parent=styles["Heading2"], textColor=teal,
                       fontName="Helvetica-Bold", fontSize=12, leading=16, spaceBefore=13)
    body = ParagraphStyle("MBody", parent=styles["Normal"], textColor=dark,
                          fontSize=9.5, leading=15, spaceAfter=6)
    doc = SimpleDocTemplate(out, pagesize=A4, topMargin=20*mm, bottomMargin=20*mm,
                            leftMargin=19*mm, rightMargin=19*mm,
                            title="Seguimiento Mensual Diagnostico Web",
                            author="Diagnostico Web por Converte")
    story = [
        Paragraph("Seguimiento mensual de tu página web", t),
        Paragraph("<b>Dirección:</b> " + escape(str(url)), body),
        Paragraph("<b>Objetivo:</b> " + escape(str(goal_label)), body),
        Paragraph("<b>Primera revisión:</b> " + escape(str(baseline["checked"])), body),
        Paragraph("<b>Revisión más reciente:</b> " + escape(str(latest["checked"])), body),
        HRFlowable(width="100%", thickness=1, color=teal),
        Paragraph("Cambios observables desde el primer diagnóstico", h),
    ]
    result = business.progress(baseline, latest, goal)
    story.append(Paragraph("Gráfica de avances verificables", h))
    if result["total"]:
        story.append(progress_drawing(result))
        story.append(Paragraph(
            str(result["start"])+"/"+str(result["total"])+" señales positivas al inicio; "+
            str(result["end"])+"/"+str(result["total"])+" en la última revisión.",
            body))
    else:
        story.append(Paragraph("Las dos revisiones no tienen señales equivalentes suficientes.",body))
    if history:
        from reportlab.graphics.shapes import Drawing, Rect, String
        values=business.history_progress(baseline, history, goal)
        history_chart=Drawing(460,115)
        barw=min(29, max(10, 398/max(1,len(values))))
        for idx, row in enumerate(values):
            x=23+idx*min(32, 418/max(1,len(values)))
            height=75*row["pct"]/100
            history_chart.add(Rect(x,28,barw,75,fillColor=colors.HexColor("#e5efec"),strokeColor=None))
            history_chart.add(Rect(x,28,barw,height,fillColor=teal,strokeColor=None))
            history_chart.add(String(x,16,str(row["month"][-2:] if row["month"]!="Inicio" else "Inicio"),
                                     fontName="Helvetica",fontSize=7,fillColor=dark))
        story.append(Paragraph("Revisiones disponibles mes por mes", h))
        story.append(history_chart)
        story.append(Paragraph(
            "La altura representa señales favorables entre las comprobables de esa fecha. "
            "No mide visitas, ventas ni posiciones.", note))
    changes = differences(baseline, latest)
    if changes:
        for item in changes:
            story.append(Paragraph("<b>" + escape(item["field"]) + "</b>", body))
            story.append(Paragraph("Antes: " + escape(item["previous"]), body))
            story.append(Paragraph("Ahora: " + escape(item["current"]), body))
    else:
        story.append(Paragraph(
            "No se detectaron cambios en los indicadores HTML que esta herramienta registra.", body))
    story.append(Paragraph("Cambios desde la última revisión guardada", h))
    recent = differences(previous, latest)
    if recent:
        for item in recent:
            story.append(Paragraph(
                "<b>" + escape(item["field"]) + "</b>: " +
                escape(item["previous"]) + " / " + escape(item["current"]), body))
    else:
        story.append(Paragraph("No se detectaron diferencias adicionales.", body))
    checked=business.overview(latest,goal)
    story.append(Paragraph("Acciones recomendadas para el próximo mes", h))
    for item in checked["actionable"][:8]:
        story.append(Paragraph("<b>"+escape(item["title"])+"</b> ("+
                               escape(item["status_label"])+")",body))
        story.append(Paragraph("<b>Evidencia:</b> "+escape(item["evidence"]),body))
        story.append(Paragraph("<b>Qué hacer:</b> "+escape(item["action"]),body))
    story.append(Paragraph("Los diez puntos de revisión", h))
    for item in checked["checks"][:10]:
        story.append(Paragraph("<b>"+escape(item["title"])+"</b>: "+
                               escape(item["status_label"]),body))
    story += [
        Paragraph("Alcance", h),
        Paragraph(
            "El seguimiento compara señales comprobables del HTML público. "
            "No demuestra cambios en posicionamiento, visitas, conversiones o ventas. "
            "Algunos componentes JavaScript no pueden detectarse; "
            "las mejoras deben comprobarse con el responsable web.",
            body,
        ),
        Spacer(1, 10),
        Paragraph("Diagnóstico Web · converte.uno/diagnostico-web/", body),
    ]
    doc.build(story)
    out.seek(0)
    return out
