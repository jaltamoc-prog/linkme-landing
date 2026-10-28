"""Prueba integral de entregas: simulador local de Stripe, jamás realiza cobros.

Ejecuta Flask completo y simula la API de Stripe únicamente dentro de unittest.
Verifica ambas compras, los retornos, las protecciones, el PDF, el seguimiento y la
cancelación sin crear suscriptores ni recursos reales en la cuenta de producción.
"""
import json
import os
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from app import app
from herramientas import diagnostico_web as dw
from herramientas import diagnostico_seguimiento as mon

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

OLD_HTML = """<!doctype html><html><head><title>Panaderia de ejemplo</title></head>
<body><h1>Panaderia artesanal</h1><img src="/foto.png">
<a href="/contacto">Escribenos</a></body></html>"""
NEW_HTML = """<!doctype html><html><head><title>Panaderia artesanal en Puebla</title>
<meta name="description" content="Pan artesanal, pasteles y pedidos en Puebla">
<meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body><h1>Panaderia artesanal en Puebla</h1><a href="/contacto">Escribenos</a>
<a href="/catalogo">Ver nuestros panes</a>
<img src="/foto.webp" width="640" height="400" alt="Pan recien horneado">
</body></html>"""
SINGLE_ID = "cs_live_" + "T" * 27
MONTH_ID = "cs_live_" + "M" * 27
SUB_ID = "sub_" + "S" * 27
STRIPE_URL = "https://checkout.stripe.com/c/pay/test_delivery_no_charge"
ENV = {
    "DIAGNOSTICO_STRIPE_SECRET_KEY": "rk_live_mock_unauthenticated",
    "DIAGNOSTICO_STRIPE_PRICE_ID": dw.REPORT_PRICE_ID,
    "DIAGNOSTICO_STRIPE_MONTHLY_PRICE_ID": mon.PRICE_ID,
    "DIAGNOSTICO_PAGOS_ACTIVOS": "1",
    "DIAGNOSTICO_SUSCRIPCIONES_ACTIVAS": "1",
    "DIAGNOSTICO_PRICE_LABEL": "$387 MXN",
}


def mock_response(payload, status=200):
    response = Mock()
    response.status_code = status
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


def extract_pdf(body):
    if PdfReader is None:
        return ""
    from io import BytesIO
    pages = PdfReader(BytesIO(body)).pages
    if not pages:
        raise AssertionError("El PDF no contiene páginas")
    return "\n".join(page.extract_text() or "" for page in pages)


def save_artifact(filename, data):
    destination = os.getenv("DIAGNOSTICO_TEST_EVIDENCE_DIR")
    if destination:
        folder = Path(destination)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / filename).write_bytes(data)


class TestEntregaCompleta(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        dw._cache.clear()
        dw._by_ip.clear()
        dw._global.clear()
        dw._payment_ip.clear()

    def test_informe_387_pago_confirmado_entrega_pdf_y_no_requiere_web_activa(self):
        """URL -> Checkout 387 -> Stripe confirma -> informe -> PDF descargable."""
        create_data = {}
        def stripe_post(url, **kwargs):
            self.assertTrue(url.endswith("/v1/checkout/sessions"))
            create_data.update(kwargs["data"])
            return mock_response({"url": STRIPE_URL})

        with patch.dict(os.environ, ENV), \
             patch.object(dw, "fetch_html",
                          return_value=("https://example.com/", OLD_HTML, {})), \
             patch("requests.post", side_effect=stripe_post):
            start = self.client.post("/diagnostico-web/comprar", data={
                "url": "https://example.com/", "objetivo": "ventas",
                "keyword": "pan artesanal", "city": "Puebla",
            })
        self.assertEqual(start.status_code, 200)
        self.assertIn(STRIPE_URL.encode(), start.data)
        self.assertIn(b'<meta http-equiv="refresh"', start.data)
        self.assertEqual(create_data["mode"], "payment")
        self.assertEqual(create_data["line_items[0][price]"], dw.REPORT_PRICE_ID)
        self.assertEqual(create_data["line_items[0][quantity]"], "1")
        self.assertIn("session_id={CHECKOUT_SESSION_ID}", create_data["success_url"])

        metadata = {
            key[len("metadata["):-1]: value for key, value in create_data.items()
            if key.startswith("metadata[")
        }
        self.assertEqual(metadata["service"], "diagnostico-web-informe")
        self.assertIn("audit_version", metadata)
        session = {
            "id": SINGLE_ID, "livemode": True, "mode": "payment",
            "status": "complete", "payment_status": "paid",
            "amount_total": 38700, "currency": "mxn", "metadata": metadata,
        }
        line_items = {"data": [{
            "price": {"id": dw.REPORT_PRICE_ID}, "quantity": 1,
            "amount_total": 38700,
        }]}
        def stripe_get(url, **kwargs):
            return mock_response(line_items if url.endswith("/line_items") else session)

        # Aún si la página deja de responder, se entrega la auditoría
        # almacenada por Checkout al contratar, no se vuelve a analizar.
        with patch.dict(os.environ, ENV), \
             patch("requests.get", side_effect=stripe_get), \
             patch.object(dw, "fetch_html",
                          side_effect=RuntimeError("La web del cliente dejó de responder")):
            finished = self.client.get("/diagnostico-web/informe?session_id=" + SINGLE_ID)
            pdf = self.client.get("/diagnostico-web/descargar?session_id=" + SINGLE_ID)
        self.assertEqual(finished.status_code, 200)
        self.assertIn("Pago confirmado por Stripe".encode(), finished.data)
        self.assertIn("Descargar mi informe completo".encode(), finished.data)
        self.assertIn("/diagnostico-web/descargar?session_id=".encode(), finished.data)
        self.assertNotIn("/diagnostico-web/comparar".encode(), finished.data)
        self.assertEqual(pdf.status_code, 200)
        self.assertEqual(pdf.mimetype, "application/pdf")
        self.assertIn("attachment", pdf.headers["Content-Disposition"])
        self.assertIn("no-store", pdf.headers["Cache-Control"])
        self.assertTrue(pdf.data.startswith(b"%PDF-"))
        self.assertGreater(len(pdf.data), 7000)
        contents = extract_pdf(pdf.data)
        if PdfReader:
            self.assertIn("Informe completo de oportunidades", contents)
            self.assertIn("Panaderia", contents)
            self.assertIn("10 puntos clave", contents)
            self.assertIn("Que corregir:", contents)
        save_artifact("ejemplo_informe_387.pdf", pdf.data)
        self.single_receipt = {
            "servicio": "$387 MXN, pago único", "checkout": "simulado",
            "revisión": "guardada en Stripe simulado", "informe": finished.status_code,
            "pdf": pdf.status_code, "bytes_pdf": len(pdf.data),
            "páginas_pdf": len(PdfReader(__import__("io").BytesIO(pdf.data)).pages) if PdfReader else None,
        }
        save_artifact("comprobante_387.json", json.dumps(
            self.single_receipt, ensure_ascii=False, indent=2).encode())

    def test_informe_sin_pago_no_se_entrega(self):
        audit = {
            "service": "diagnostico-web-informe",
            "url": "https://example.com/",
            "goal": "ventas",
        }
        data = {"id": SINGLE_ID, "mode": "payment", "livemode": True,
                "status": "open", "payment_status": "unpaid",
                "currency": "mxn", "amount_total": 38700, "metadata": audit}
        with patch.dict(os.environ, ENV), \
             patch("requests.get", return_value=mock_response(data)):
            for endpoint in ("informe", "descargar"):
                r = self.client.get(
                    "/diagnostico-web/" + endpoint + "?session_id=" + SINGLE_ID)
                self.assertEqual(r.status_code, 403)

    def _build_monthly_state(self):
        """Una compra mensual simula Stripe Checkout y persiste la auditoría."""
        create = {}
        def billing_create(method, path, fields=None):
            self.assertEqual((method, path), ("POST", "checkout/sessions"))
            create.update(fields)
            return {"url": STRIPE_URL}

        with patch.dict(os.environ, ENV), \
             patch.object(dw, "fetch_html",
                          return_value=("https://example.com/", OLD_HTML, {})), \
             patch.object(dw, "_billing_request", side_effect=billing_create):
            response = self.client.post("/diagnostico-web/suscribir", data={
                "url": "https://example.com/", "objetivo": "contactos",
                "keyword": "pan artesanal", "city": "Puebla",
            })
        self.assertEqual(response.status_code, 200)
        self.assertIn(STRIPE_URL.encode(), response.data)
        self.assertEqual(create["mode"], "subscription")
        self.assertEqual(create["line_items[0][price]"], mon.PRICE_ID)
        self.assertEqual(create["line_items[0][quantity]"], "1")
        self.assertIn("session_id={CHECKOUT_SESSION_ID}", create["success_url"])
        meta = {
            key[len("subscription_data[metadata]["):-1]: value
            for key, value in create.items()
            if key.startswith("subscription_data[metadata][")
        }
        self.assertEqual(meta["monitor_service"], "diagnostico-web-seguimiento")
        baseline = mon.read_baseline(meta)
        self.assertEqual(baseline["keyword"], "pan artesanal")
        return meta

    def test_seguimiento_597_entrega_panel_revisiones_graficas_pdf_y_cancelacion(self):
        """Checkout mensual -> pago confirmado -> panel -> revisión -> PDF -> cancelación."""
        metadata = self._build_monthly_state()
        session = {
            "id": MONTH_ID, "livemode": True, "mode": "subscription",
            "status": "complete", "payment_status": "paid", "currency": "mxn",
            "amount_total": 59700, "metadata": {"service": "diagnostico-web-seguimiento"},
            "subscription": SUB_ID,
        }
        sub = {
            "id": SUB_ID, "livemode": True, "status": "active",
            "cancel_at_period_end": False, "metadata": metadata,
            "items": {"data": [
                {"quantity": 1, "price": {"id": mon.PRICE_ID}},
            ]},
        }

        def billing(method, path, fields=None):
            if method == "GET" and path == "checkout/sessions/" + MONTH_ID:
                return session
            if method == "GET" and path == "subscriptions/" + SUB_ID:
                return sub
            if method == "POST" and path == "subscriptions/" + SUB_ID:
                for key, value in fields.items():
                    self.assertTrue(key.startswith("metadata["))
                    actual_key = key[len("metadata["):-1]
                    if value == "":
                        sub["metadata"].pop(actual_key, None)
                    else:
                        sub["metadata"][actual_key] = value
                return sub
            self.fail("Llamada Stripe inesperada: %s %s" % (method, path))

        with patch.dict(os.environ, ENV), patch.object(dw, "_billing_request", side_effect=billing):
            first = self.client.get("/diagnostico-web/seguimiento?session_id=" + MONTH_ID)
        self.assertEqual(first.status_code, 200)
        self.assertIn("Seguimiento de tu página web".encode(), first.data)
        self.assertIn("Qué conviene hacer ahora".encode(), first.data)
        self.assertIn("Primera revisión".encode(), first.data)
        self.assertIn("no-store", first.headers["Cache-Control"])
        self.assertIn("noindex", first.headers["X-Robots-Tag"])

        with patch.dict(os.environ, ENV), \
             patch.object(dw, "_billing_request", side_effect=billing), \
             patch.object(dw, "fetch_html",
                          return_value=("https://example.com/", NEW_HTML, {})):
            updated = self.client.post("/diagnostico-web/seguimiento/revisar", data={
                "session_id": MONTH_ID,
            })
            after = self.client.get("/diagnostico-web/seguimiento?session_id=" + MONTH_ID)
            pdf = self.client.get("/diagnostico-web/seguimiento/descargar?session_id=" + MONTH_ID)
        self.assertEqual(updated.status_code, 200)
        self.assertIn("Revisión guardada".encode(), updated.data)
        self.assertEqual(after.status_code, 200)
        self.assertIn("Mes a mes".encode(), after.data)
        self.assertIn("Panaderia artesanal".encode(), after.data)
        self.assertIn("Qué conviene hacer ahora".encode(), after.data)
        self.assertEqual(len(mon.history(sub["metadata"])), 1)
        self.assertTrue(mon.differences(mon.read_baseline(metadata),
                                        mon.history(sub["metadata"])[0]["audit"]))
        self.assertEqual(pdf.status_code, 200)
        self.assertEqual(pdf.mimetype, "application/pdf")
        self.assertTrue(pdf.data.startswith(b"%PDF-"))
        self.assertGreater(len(pdf.data), 3200)
        contents = extract_pdf(pdf.data)
        if PdfReader:
            self.assertIn("Seguimiento mensual", contents)
            self.assertIn("Acciones recomendadas", contents)
            self.assertIn("Revisiones disponibles mes por mes", contents)
            self.assertIn("Panaderia", contents)
        save_artifact("ejemplo_seguimiento_597.pdf", pdf.data)

        # Simular cancelación confirmada en Stripe: se mantiene el periodo pagado,
        # pero no se renueva automáticamente.
        sub["cancel_at_period_end"] = True
        with patch.dict(os.environ, ENV), patch.object(dw, "_billing_request", side_effect=billing):
            canceled = self.client.get("/diagnostico-web/seguimiento?session_id=" + MONTH_ID)
        self.assertEqual(canceled.status_code, 200)
        self.assertIn("sin renovación automática".encode(), canceled.data)

        # Una vez cancelada o impagada, se rechaza el panel y el PDF.
        sub["status"] = "canceled"
        with patch.dict(os.environ, ENV), patch.object(dw, "_billing_request", side_effect=billing):
            deny = self.client.get("/diagnostico-web/seguimiento?session_id=" + MONTH_ID)
            deny_pdf = self.client.get("/diagnostico-web/seguimiento/descargar?session_id=" + MONTH_ID)
        self.assertEqual(deny.status_code, 403)
        self.assertEqual(deny_pdf.status_code, 403)

        evidence = {
            "servicio": "$597 MXN mensuales", "checkout": "simulado",
            "panel_inicial": first.status_code,
            "nueva_revision": updated.status_code,
            "historial_meses": len(mon.history(metadata)),
            "panel_actualizado": after.status_code,
            "pdf": pdf.status_code, "bytes_pdf": len(pdf.data),
            "páginas_pdf": len(PdfReader(__import__("io").BytesIO(pdf.data)).pages) if PdfReader else None,
            "renovacion_cancelada_status": canceled.status_code,
            "acceso_tras_vencimiento": deny.status_code,
        }
        save_artifact("comprobante_597.json", json.dumps(
            evidence, ensure_ascii=False, indent=2).encode())

    def test_suscripcion_sin_pago_no_da_acceso(self):
        meta = self._build_monthly_state()
        session = {
            "id": MONTH_ID, "livemode": True, "mode": "subscription",
            "status": "open", "payment_status": "unpaid", "currency": "mxn",
            "amount_total": 59700, "metadata": {"service": "diagnostico-web-seguimiento"},
            "subscription": SUB_ID,
        }
        with patch.dict(os.environ, ENV), patch.object(
            dw, "_billing_request", return_value=session
        ):
            for path in ("seguimiento", "seguimiento/descargar"):
                r = self.client.get("/diagnostico-web/" + path + "?session_id=" + MONTH_ID)
                self.assertEqual(r.status_code, 403)

    def test_una_compra_no_desbloquea_el_otro_servicio(self):
        # Sin sesión real y tipo de servicio explícito, el endpoint privado
        # nunca debe permitir canjear el enlace de otro servicio.
        data = {"id": MONTH_ID, "livemode": True, "mode": "subscription",
                "status": "complete", "payment_status": "paid", "currency": "mxn",
                "amount_total": 59700, "metadata": {"service": "diagnostico-web-seguimiento"},
                "subscription": SUB_ID}
        with patch.dict(os.environ, ENV), patch("requests.get", return_value=mock_response(data)):
            r = self.client.get("/diagnostico-web/descargar?session_id=" + MONTH_ID)
        self.assertEqual(r.status_code, 403)


if __name__ == "__main__":
    unittest.main()
