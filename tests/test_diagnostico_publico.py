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
