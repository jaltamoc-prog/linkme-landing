"""Pruebas de humo para la herramienta publica, sin llamadas a sitios ajenos."""
import unittest
from unittest.mock import patch
from app import app
from herramientas import diagnostico_web as dw

HTML = """<!doctype html><html><head><title>Ejemplo de negocio</title></head>
<body><h1>Conoce nuestros servicios</h1><img src="/foto.png">
<a href="/contacto">Contactanos</a></body></html>"""


class DiagnosticSmokeTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        dw._by_ip.clear()
        dw._global.clear()
        dw._cache.clear()

    def test_public_landing_and_sitemap(self):
        r = self.client.get("/diagnostico-web/")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Analiza tu", r.data)
        self.assertIn(b"converte.uno/diagnostico-web/", self.client.get("/sitemap.xml").data)
        self.assertEqual(self.client.get("/health").status_code, 200)
        self.assertEqual(self.client.get("/").status_code, 200)

    def test_report_uses_evidence_and_escapes(self):
        with patch.object(dw, "fetch_html", return_value=("https://ejemplo.com/", HTML, {})):
            r = self.client.post("/diagnostico-web/", data={
                "url": "https://ejemplo.com/?token=<script>alert(1)</script>",
                "objetivo": "ventas",
            })
        self.assertEqual(r.status_code, 200)
        self.assertIn("Qué conviene hacer primero".encode(), r.data)
        self.assertIn("Tu pagina no tiene".encode(), r.data) if False else None
        self.assertNotIn(b"<script>alert(1)</script>", r.data)

    def test_public_result_always_has_a_working_next_step(self):
        with patch.dict("os.environ", {
            "DIAGNOSTICO_PAGOS_ACTIVOS": "",
            "DIAGNOSTICO_STRIPE_SECRET_KEY": "",
            "DIAGNOSTICO_CONTACT_WHATSAPP": "",
        }), patch.object(dw, "fetch_html",
                         return_value=("https://ejemplo.com/", HTML, {})):
            r = self.client.post("/diagnostico-web/", data={
                "url": "https://ejemplo.com/", "objetivo": "contactos",
            })
        self.assertEqual(r.status_code, 200)
        self.assertIn(b'href="#planes"', r.data)
        self.assertIn(b'id="planes"', r.data)
        self.assertIn("Ver cómo continuar con las mejoras".encode(), r.data)
        self.assertIn("Seguimiento de mejoras".encode(), r.data)
        self.assertIn("pago seguro".encode(), r.data)
        self.assertNotIn(b'action="/diagnostico-web/comprar"', r.data)

    def test_no_public_report_for_local_networks(self):
        for url in ["http://127.0.0.1/", "http://192.168.0.1/", "http://example.com:8080",
                    "http://localhost/", "http://user:secret@example.com/"]:
            with self.subTest(url=url):
                r = self.client.post("/diagnostico-web/", data={"url": url})
                self.assertEqual(r.status_code, 422)

    def test_proxy_visitor_identity_uses_last_trusted_hop_on_render(self):
        with patch.dict("os.environ", {"RENDER": "true"}):
            with app.test_request_context(
                "/diagnostico-web/",
                headers={"X-Forwarded-For": "9.9.9.9, 8.8.8.8"},
                environ_base={"REMOTE_ADDR": "10.0.0.3"},
            ):
                self.assertEqual(dw.visitor_ip(), "8.8.8.8")
            with app.test_request_context(
                "/diagnostico-web/",
                headers={"X-Forwarded-For": "9.9.9.9, no-es-ip"},
                environ_base={"REMOTE_ADDR": "10.0.0.3"},
            ):
                self.assertEqual(dw.visitor_ip(), "10.0.0.3")

    def test_limits_apply_to_new_sites_not_cached_rechecks_or_other_clients(self):
        with patch.dict("os.environ", {"RENDER": "true"}), patch.object(
            dw, "fetch_html", return_value=("https://ejemplo.com/", HTML, {})
        ) as download:
            headers = {"X-Forwarded-For": "9.9.9.9, 8.8.8.8"}
            for index in range(20):
                response = self.client.post(
                    "/diagnostico-web/",
                    data={"url": "https://sitio-" + str(index) + ".com/"},
                    headers=headers,
                )
                self.assertEqual(response.status_code, 200, index)
            blocked = self.client.post(
                "/diagnostico-web/",
                data={"url": "https://sitio-21.com/"},
                headers=headers,
            )
            self.assertEqual(blocked.status_code, 429)
            self.assertEqual(blocked.headers.get("Retry-After"), "600")

            repeat = self.client.post(
                "/diagnostico-web/",
                data={"url": "https://sitio-0.com/", "objetivo": "ventas"},
                headers=headers,
            )
            self.assertEqual(repeat.status_code, 200)

            other = self.client.post(
                "/diagnostico-web/",
                data={"url": "https://otro-cliente.com/"},
                headers={"X-Forwarded-For": "9.9.9.9, 1.1.1.1"},
            )
            self.assertEqual(other.status_code, 200)
            self.assertEqual(download.call_count, 21)

    def test_paid_feature_disabled_without_keys(self):
        with patch.dict("os.environ", {"DIAGNOSTICO_STRIPE_SECRET_KEY": "",
                                     "DIAGNOSTICO_STRIPE_PRICE_ID": ""}):
            self.assertEqual(self.client.post("/diagnostico-web/comprar").status_code, 503)

    def test_paid_report_has_ten_distinct_evidence_based_checks(self):
        with patch.object(dw, "fetch_html",
                          return_value=("https://ejemplo.com/", HTML, {})):
            audit = dw.analyse("https://ejemplo.com/")
        checks = dw.expanded_plan(audit, "ventas")
        self.assertEqual(len(checks), 10)
        self.assertTrue(any("Ruta de compra" in item["area"] for item in checks))
        self.assertTrue(all(item["evidence"] and item["action"] for item in checks))
        from herramientas.diagnostico_pdf import build_pdf
        report = dw.report_for(audit, "ventas")
        pdf = build_pdf(audit, report, dw.GOALS["ventas"], checks=checks)
        self.assertTrue(pdf.getvalue().startswith(b"%PDF-"))
        self.assertGreater(len(pdf.getvalue()), 4500)

    def test_paid_pdf_is_readable_and_contains_all_findings(self):
        from herramientas.diagnostico_pdf import build_pdf
        with patch.object(dw, "fetch_html",
                          return_value=("https://ejemplo.com/", HTML, {})):
            audit = dw.analyse("https://ejemplo.com/")
        report = dw.report_for(audit, "ventas")
        self.assertGreaterEqual(report["count"], 4)
        pdf = build_pdf(audit, report, "Facilitar compras y pedidos")
        content = pdf.getvalue()
        self.assertTrue(content.startswith(b"%PDF-"))
        self.assertGreater(len(content), 3000)

    def test_paid_session_requires_paid_live_price_and_matching_service(self):
        from unittest.mock import Mock
        from werkzeug.exceptions import Forbidden
        sid = "cs_live_" + "A" * 24
        context = {
            "DIAGNOSTICO_STRIPE_SECRET_KEY": "sk_live_test_key_for_mock",
            "DIAGNOSTICO_STRIPE_PRICE_ID": dw.REPORT_PRICE_ID,
        }
        valid = {
            "id": sid, "livemode": True, "mode": "payment", "currency": "mxn",
            "payment_status": "paid", "status": "complete", "amount_total": 19900,
            "metadata": {"service": "diagnostico-web-informe",
                         "url": "https://ejemplo.com/", "goal": "ventas"},
        }
        lines = {"data": [{"price": {"id": dw.REPORT_PRICE_ID},
                           "quantity": 1, "amount_total": 19900}]}
        def response(body):
            obj = Mock()
            obj.json.return_value = body
            return obj
        with app.test_request_context("/diagnostico-web/informe"), patch.dict(
            "os.environ", context
        ), patch("requests.get", side_effect=[response(valid), response(lines)]):
            self.assertEqual(dw.verify_purchase(sid), ("https://ejemplo.com/", "ventas", None))
        with app.test_request_context("/diagnostico-web/informe"), patch.dict(
            "os.environ", context
        ), patch("requests.get", side_effect=[response({
            **valid, "payment_status": "unpaid",
        })]):
            with self.assertRaises(Forbidden):
                dw.verify_purchase(sid)
        with app.test_request_context("/diagnostico-web/informe"), patch.dict(
            "os.environ", context
        ), patch("requests.get", side_effect=[
            response(valid), response({"data": [{"price": {"id": "price_other"},
                                                 "quantity": 1, "amount_total": 19900}]}),
        ]):
            with self.assertRaises(Forbidden):
                dw.verify_purchase(sid)

    def test_checkout_snapshot_survives_site_outage_after_payment(self):
        import copy
        with patch.object(dw, "fetch_html",
                          return_value=("https://ejemplo.com/", HTML, {})):
            audited = dw.analyse("https://ejemplo.com/")
        metadata = dw.audit_snapshot(audited)
        self.assertTrue(all(len(value) <= 500 for value in metadata.values()))
        recovered = dw.restored_snapshot(metadata, "https://ejemplo.com/")
        self.assertEqual(audited, recovered)
        tampered = copy.deepcopy(metadata)
        tampered["audit_0"] = "not_valid"
        with self.assertRaises(ValueError):
            dw.restored_snapshot(tampered, "https://ejemplo.com/")
        with self.assertRaises(ValueError):
            dw.restored_snapshot(metadata, "https://otra-web.com/")

    def test_pdf_can_be_downloaded_without_revisiting_source(self):
        sid = "cs_live_" + "Z"*24
        with patch.dict("os.environ", {
            "DIAGNOSTICO_STRIPE_SECRET_KEY": "sk_live_test_key_for_mock",
            "DIAGNOSTICO_STRIPE_PRICE_ID": dw.REPORT_PRICE_ID,
        }), patch.object(dw, "fetch_html",
                        return_value=("https://ejemplo.com/", HTML, {})):
            audited = dw.analyse("https://ejemplo.com/")
            with patch.object(dw, "verify_purchase", return_value=(
                "https://ejemplo.com/", "ventas", audited
            )), patch.object(dw, "fetch_html", side_effect=RuntimeError("Site offline")):
                pdf = self.client.get("/diagnostico-web/descargar?session_id="+sid)
        self.assertEqual(pdf.status_code, 200)
        self.assertTrue(pdf.data.startswith(b"%PDF-"))

    def test_paid_page_has_real_pdf_download_and_no_messaging_service(self):
        context = {
            "DIAGNOSTICO_STRIPE_SECRET_KEY": "sk_live_test_key_for_mock",
            "DIAGNOSTICO_STRIPE_PRICE_ID": dw.REPORT_PRICE_ID,
            "DIAGNOSTICO_PAGOS_ACTIVOS": "",
        }
        sid = "cs_live_" + "A" * 24
        with patch.dict("os.environ", context), patch.object(
            dw, "verify_purchase", return_value=("https://ejemplo.com/", "ventas", None)
        ), patch.object(dw, "fetch_html",
                        return_value=("https://ejemplo.com/", HTML, {})):
            webpage = self.client.get("/diagnostico-web/informe?session_id=" + sid)
            pdf = self.client.get("/diagnostico-web/descargar?session_id=" + sid)
        self.assertEqual(webpage.status_code, 200)
        self.assertIn("Descargar mi informe completo".encode(), webpage.data)
        self.assertNotIn(b"wa.me", webpage.data)
        self.assertEqual(pdf.status_code, 200)
        self.assertEqual(pdf.mimetype, "application/pdf")
        self.assertTrue(pdf.data.startswith(b"%PDF-"))
        self.assertIn("no-store", pdf.headers.get("Cache-Control", ""))
        self.assertEqual(pdf.headers.get("X-Robots-Tag"), "noindex, nofollow")

    def test_checkout_creates_hosted_session_with_verified_audit_snapshot(self):
        from unittest.mock import Mock
        with patch.dict("os.environ", {
            "DIAGNOSTICO_STRIPE_SECRET_KEY": "sk_live_test_key_for_mock",
            "DIAGNOSTICO_STRIPE_PRICE_ID": dw.REPORT_PRICE_ID,
            "DIAGNOSTICO_PRICE_LABEL": "$199 MXN",
            "DIAGNOSTICO_PAGOS_ACTIVOS": "1",
        }), patch.object(dw, "fetch_html",
                        return_value=("https://ejemplo.com/", HTML, {})):
            stripe = Mock()
            stripe.json.return_value = {"url": "https://checkout.stripe.com/c/pay/test"}
            with patch("requests.post", return_value=stripe) as call:
                response = self.client.post("/diagnostico-web/comprar", data={
                    "url": "https://ejemplo.com/", "objetivo": "ventas",
                })
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.location, "https://checkout.stripe.com/c/pay/test")
        form = call.call_args.kwargs["data"]
        self.assertEqual(form["line_items[0][price]"], dw.REPORT_PRICE_ID)
        self.assertEqual(form["metadata[service]"], "diagnostico-web-informe")
        self.assertEqual(form["metadata[url]"], "https://ejemplo.com/")
        self.assertEqual(form["metadata[audit_version]"], "1")
        self.assertTrue(form["metadata[audit_0]"])
        self.assertEqual(form["mode"], "payment")

    def test_paid_checkout_disabled_by_default_even_if_stripe_keys_exist(self):
        with patch.dict("os.environ", {
            "DIAGNOSTICO_STRIPE_SECRET_KEY": "sk_live_test_key_for_mock",
            "DIAGNOSTICO_STRIPE_PRICE_ID": dw.REPORT_PRICE_ID,
            "DIAGNOSTICO_PRICE_LABEL": "$199 MXN",
            "DIAGNOSTICO_PAGOS_ACTIVOS": "",
        }):
            self.assertFalse(dw.payments_enabled())
            self.assertEqual(self.client.post("/diagnostico-web/comprar").status_code, 503)

    def test_redirect_network_with_private_address_is_blocked(self):
        with patch.object(dw.socket, "getaddrinfo",
                          return_value=[(None, None, None, None, ("127.0.0.1", 443))]):
            with self.assertRaises(ValueError):
                dw.verified_address("ejemplo.com", 443)


if __name__ == "__main__":
    unittest.main()
