# -*- coding: utf-8 -*-
"""Entrega de informes por correo, sin revelar la tarjeta ni almacenar datos del cliente.

Destinatario exclusivamente de customer_details.email en la sesión pagada de
Stripe. Resend por HTTPS (recomendado) o SMTP TLS. Sin credenciales activas no
se declara que se mandó correo. El usuario SIEMPRE conserva descarga directa.
"""
import base64
import hashlib
import hmac
import os
import re
import smtplib
import ssl
import time
from email.message import EmailMessage
from urllib.parse import quote

import requests

MAX_PDF = 8_000_000


def configured():
    sender = os.getenv("DIAGNOSTICO_CORREO_REMITENTE", "").strip()
    if not valid_email(sender):
        return False
    if os.getenv("DIAGNOSTICO_RESEND_API_KEY", "").startswith("re_"):
        return True
    return bool(os.getenv("DIAGNOSTICO_SMTP_HOST")
                and os.getenv("DIAGNOSTICO_SMTP_USER")
                and os.getenv("DIAGNOSTICO_SMTP_PASSWORD"))


def valid_email(value):
    return (isinstance(value, str) and 5 <= len(value) <= 254
            and re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_\x60{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", value)
            is not None and "\n" not in value and "\r" not in value)


def verified_stripe_signature(payload, header, secret, max_age=300):
    """Valida firma del cuerpo ORIGINAL y antigüedad del webhook Stripe."""
    if not isinstance(payload, bytes) or not payload or len(payload) > 65536:
        return False
    if not secret.startswith("whsec_") or not isinstance(header, str):
        return False
    parts = {}
    for entry in header.split(","):
        if "=" in entry:
            k, v = entry.strip().split("=", 1)
            parts.setdefault(k, []).append(v)
    try:
        ts = int(parts.get("t", [""])[0])
    except ValueError:
        return False
    if abs(int(time.time()) - ts) > max_age:
        return False
    signature = hmac.new(secret.encode("utf-8"),
                         str(ts).encode("ascii") + b"." + payload,
                         hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(signature, item) for item in parts.get("v1", []))


def mail_send(email, subject, content, filename, pdf, unique_key):
    """Envía el PDF como adjunto. Las credenciales solo viven en Render."""
    sender = os.getenv("DIAGNOSTICO_CORREO_REMITENTE", "").strip()
    if not (configured() and valid_email(email)):
        raise RuntimeError("El correo de entrega no está configurado o el destinatario no es válido.")
    if not isinstance(pdf, bytes) or not pdf.startswith(b"%PDF-") or len(pdf) > MAX_PDF:
        raise ValueError("El informe adjunto no es un PDF válido.")
    if os.getenv("DIAGNOSTICO_RESEND_API_KEY", "").startswith("re_"):
        data = {
            "from": sender, "to": [email], "subject": subject,
            "text": content,
            "attachments": [{"filename": filename,
                             "content": base64.b64encode(pdf).decode("ascii")}],
        }
        headers = {
            "Authorization": "Bearer " + os.environ["DIAGNOSTICO_RESEND_API_KEY"],
            "Content-Type": "application/json",
            "Idempotency-Key": ("diagnostico-" + unique_key)[:256],
        }
        response = requests.post("https://api.resend.com/emails", headers=headers,
                                 json=data, timeout=18)
        response.raise_for_status()
        if not response.json().get("id"):
            raise RuntimeError("El servicio de correo no confirmó la aceptación del mensaje.")
        return True
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = email
    msg["Subject"] = subject
    msg.set_content(content)
    msg.add_attachment(pdf, maintype="application", subtype="pdf", filename=filename)
    host = os.environ["DIAGNOSTICO_SMTP_HOST"]
    port = int(os.getenv("DIAGNOSTICO_SMTP_PORT", "465"))
    if port not in (465, 587):
        raise ValueError("El puerto SMTP debe usar TLS.")
    if port == 465:
        with smtplib.SMTP_SSL(host, port, timeout=18, context=ssl.create_default_context()) as server:
            server.login(os.environ["DIAGNOSTICO_SMTP_USER"],
                         os.environ["DIAGNOSTICO_SMTP_PASSWORD"])
            server.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=18) as server:
            server.starttls(context=ssl.create_default_context())
            server.login(os.environ["DIAGNOSTICO_SMTP_USER"],
                         os.environ["DIAGNOSTICO_SMTP_PASSWORD"])
            server.send_message(msg)
    return True


def stripe_email(session):
    """No se acepta dirección email enviada por parámetros del navegador."""
    return (session.get("customer_details") or {}).get("email", "") or ""


def paid_delivery(session_id, revision=False):
    """Valida la transacción en Stripe, genera PDF real y entrega al email pagador.

    No marca éxito si se rechaza la autorización ni si el correo falla. El
    adjunto contiene la misma revisión que el panel o botón Descargar.
    """
    from herramientas import diagnostico_web as dw
    from herramientas import diagnostico_seguimiento as mon
    from herramientas import diagnostico_evaluacion as business
    from herramientas.diagnostico_pdf import build_pdf
    from werkzeug.exceptions import HTTPException

    if not (configured() and dw.stripe_ready() and dw.stripe_session_valid(session_id)):
        raise RuntimeError("El envío de correo no está disponible.")
    session = dw._billing_request("GET", "checkout/sessions/" + quote(session_id, safe=""))
    if (session.get("id") != session_id
            or session.get("livemode") is not (dw.stripe_mode() == "live")
            or session.get("status") != "complete"
            or session.get("payment_status") != "paid"
            or session.get("currency") != "mxn"):
        raise ValueError("Stripe todavía no confirma el pago.")
    email = stripe_email(session)
    if not valid_email(email):
        raise ValueError("El pago no contiene un correo válido del comprador.")
    service = (session.get("metadata") or {}).get("service")
    if service == "diagnostico-web-informe" and not revision:
        url, goal, snapshot = dw.verify_purchase(session_id)
        if snapshot is None:
            raise ValueError("La compra no conserva el análisis para enviar por correo.")
        pdf = build_pdf(snapshot, dw.report_for(snapshot, goal), dw.GOALS[goal],
                        seo_checks=business.checks(snapshot, goal)).getvalue()
        filename = "Diagnostico_Web_Informe_Completo.pdf"
        subject = "Tu informe de Diagnóstico Web está listo"
        link = dw.stripe_return_origin() + "/diagnostico-web/informe?session_id=" + quote(session_id)
        marker = "diagnostico_mail_informe"
        unique = session_id + "-informe"
    elif service == "diagnostico-web-seguimiento":
        sub, url, goal, baseline = dw._monthly_subscription(session_id)
        history = mon.history(sub.get("metadata") or {})
        latest = history[-1]["audit"] if history else baseline
        previous = history[-2]["audit"] if len(history) > 1 else baseline
        marker = "diagnostico_mail_seguimiento"
        token = hashlib.sha256((latest.get("checked", "") + "|" + str(latest.get("title",""))).encode()).hexdigest()[:16]
        unique = session_id + "-" + token
        if (session.get("metadata") or {}).get(marker) == token:
            return "ya_enviado"
        pdf = mon.comparison_pdf(url, dw.GOALS[goal], baseline, latest, previous,
                                 goal=goal, history=history).getvalue()
        filename = "Diagnostico_Web_Seguimiento_Mensual.pdf"
        subject = "Tu revisión de Diagnóstico Web está lista"
        link = dw.stripe_return_origin() + "/diagnostico-web/seguimiento?session_id=" + quote(session_id)
    else:
        raise ValueError("Este pago no pertenece a Diagnóstico Web.")
    if service == "diagnostico-web-informe" and (session.get("metadata") or {}).get(marker) == "enviado":
        return "ya_enviado"
    text = (
        "Hola:\n\nAdjuntamos el diagnóstico de tu página web en PDF.\n\n"
        "Tu informe y sus recomendaciones se basan en las señales públicas de la web analizada. "
        "No son cifras de ventas o posiciones de Google.\n\n"
        "También puedes abrir tu resultado desde este enlace privado:\n" + link + "\n\n"
        "Conserva este mensaje para recuperar tu informe. No compartas el enlace.\n\n"
        "Si tienes dudas sobre el cargo o la renovación, revisa el recibo de Stripe.\n\n"
        "Diagnóstico Web · CONVERTE\nhttps://converte.uno/diagnostico-web/\n"
    )
    mail_send(email, subject, text, filename, pdf, unique)
    # Persistencia de idempotencia en Stripe, sin base de datos adicional.
    # Si el permiso del API no permite actualizar Checkout, no se reenvía el
    # webhook por ese motivo: el mensaje ya fue aceptado para entrega.
    state = token if service == "diagnostico-web-seguimiento" else "enviado"
    try:
        dw._billing_request("POST", "checkout/sessions/" + quote(session_id, safe=""),
                            {"metadata[" + marker + "]": state})
    except (requests.RequestException, ValueError, KeyError):
        from flask import current_app
        current_app.logger.warning("Correo aceptado; Stripe no permitió guardar la marca de entrega.")
    return "enviado"
