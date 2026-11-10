from pathlib import Path
import hashlib
import unittest


ROOT = Path(__file__).resolve().parents[1]


class LandingV1106Tests(unittest.TestCase):
    def test_real_directory_image_and_favicon_exist(self):
        page = (ROOT / "templates" / "converte_unidos.html").read_text(encoding="utf-8")
        base = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")
        self.assertIn("converte-unidos-directorio.png", page)
        self.assertIn("Directorio móvil CONVERTE UNIDOS de Clínica Juárez", page)
        self.assertIn("converte-unidos-favicon.png", base)
        self.assertTrue((ROOT / "static" / "img" / "converte-unidos-directorio.png").is_file())
        self.assertTrue((ROOT / "static" / "img" / "converte-unidos-favicon.png").is_file())

    def test_three_mobile_steps_fit_in_one_screen(self):
        page = (ROOT / "templates" / "converte_unidos.html").read_text(encoding="utf-8")
        css = (ROOT / "static" / "css" / "style.css").read_text(encoding="utf-8")
        self.assertIn("<h3>Crea</h3><p>Personaliza tu directorio.</p>", page)
        self.assertIn("<h3>Invita</h3><p>Cada integrante vincula su CONVERTE.</p>", page)
        self.assertIn("<h3>Comparte</h3><p>Usa tu liga, QR o Wallet.</p>", page)
        self.assertIn("grid-template-columns:repeat(3,minmax(0,1fr))!important", css)
        self.assertIn("overflow:visible!important", css)

    def test_pricing_heading_contrasts_and_footer_has_no_support(self):
        base = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")
        css = (ROOT / "static" / "css" / "style.css").read_text(encoding="utf-8")
        self.assertIn(".unidos-pricing .section-heading h2{color:#74e7cc!important}", css)
        self.assertNotIn("Soporte: converte.uno@gmail.com", base)

    def test_individual_landing_content_remains_unchanged(self):
        digest = hashlib.sha256((ROOT / "templates" / "index.html").read_bytes()).hexdigest()
        self.assertEqual(
            digest,
            "a7f42decc45d4a190a431c4313e361ddf12ca583a5d3b83cd589a5ab020bd0e9",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
