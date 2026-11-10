from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class LegalV103Tests(unittest.TestCase):
    def test_legal_pages_are_current_and_publishable(self):
        paths = [
            ROOT / "templates" / "privacidad.html",
            ROOT / "templates" / "terminos.html",
            ROOT / "templates" / "reembolso.html",
        ]
        combined = "\n".join(path.read_text(encoding="utf-8") for path in paths)
        self.assertNotIn("Converte.one", combined)
        self.assertNotIn("pendiente de revisión", combined.lower())
        self.assertNotIn("USD $29", combined)
        self.assertIn("converte.uno@gmail.com", combined)
        self.assertIn("Altirum", combined)
        self.assertIn("Colonia Juárez, Ciudad de México", combined)

    def test_approved_refund_wording_is_preserved(self):
        text = (ROOT / "templates" / "reembolso.html").read_text(encoding="utf-8")
        self.assertIn("normalmente no son reembolsables", text)
        self.assertIn("gracias por informarnos", text)
        self.assertNotIn("salvo cuando legalmente corresponda", text.lower())

    def test_renewal_terms_are_clear(self):
        text = (ROOT / "templates" / "terminos.html").read_text(encoding="utf-8")
        self.assertIn("cinco días naturales", text)
        self.assertIn("cancelar la renovación automática", text)
        self.assertIn("hasta que termine la vigencia contratada", text)

    def test_footer_links_support_and_refund_policy(self):
        text = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")
        self.assertIn('href="mailto:converte.uno@gmail.com"', text)
        self.assertIn('href="/reembolso"', text)
        self.assertNotIn("WhatsApp de soporte", text)

    def test_chat_uses_current_converte_domain(self):
        text = (ROOT / "templates" / "_linkme_contigo.html").read_text(encoding="utf-8")
        self.assertNotIn("converte.one", text)
        self.assertIn("https://converte.uno/nuevo", text)


if __name__ == "__main__":
    unittest.main()
