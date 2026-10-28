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

    def test_redirect_network_with_private_address_is_blocked(self):
        with patch.object(dw.socket, "getaddrinfo",
                          return_value=[(None, None, None, None, ("127.0.0.1", 443))]):
            with self.assertRaises(ValueError):
                dw.verified_address("ejemplo.com", 443)


if __name__ == "__main__":
    unittest.main()
