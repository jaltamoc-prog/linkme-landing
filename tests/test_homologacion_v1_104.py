from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class LandingV1104Tests(unittest.TestCase):
    def test_header_has_both_google_accesses_and_no_dudas(self):
        base = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")
        self.assertIn("Sign CONVERTE", base)
        self.assertIn("Sign CONVERTE UNIDOS", base)
        self.assertIn('href="https://app.converte.uno/s/in"', base)
        self.assertIn('href="https://unidos.converte.uno/login"', base)
        self.assertGreaterEqual(base.count('class="lm-google-g"'), 2)
        self.assertNotIn('href="/#preguntas">Dudas', base)

    def test_unidos_page_has_approved_content(self):
        page = (ROOT / "templates" / "converte_unidos.html").read_text(encoding="utf-8")
        required = (
            "Reúne de 2 a 15 perfiles CONVERTE",
            "Potencia a tu equipo con hasta 15 perfiles",
            "Ediciones y consultas (escaneos) ilimitados por un año.",
            "Sin cargos ocultos ni letras chiquitas",
            "menos de dos pesos mexicanos al día por perfil",
            "Precios incluyen IVA.",
            "https://unidos.converte.uno/nuevo",
        )
        for text in required:
            self.assertIn(text, page)
        forbidden = (
            "La organización cuenta como una unidad adicional.",
            "Primer pago de contado o a meses con intereses",
            "Renovación automática cada 12 meses en un solo cargo.",
            "Cancelar detiene únicamente la siguiente renovación",
        )
        for text in forbidden:
            self.assertNotIn(text, page)

    def test_individual_landing_fingerprint_is_unchanged(self):
        import hashlib
        index = (ROOT / "templates" / "index.html").read_bytes()
        self.assertEqual(
            hashlib.sha256(index).hexdigest(),
            "a7f42decc45d4a190a431c4313e361ddf12ca583a5d3b83cd589a5ab020bd0e9",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
