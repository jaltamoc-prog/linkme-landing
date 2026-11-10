from pathlib import Path
import hashlib
import unittest


ROOT = Path(__file__).resolve().parents[1]


class LandingV1105Tests(unittest.TestCase):
    def test_unidos_header_separates_access_and_purchase(self):
        base = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")
        self.assertIn("Sign CONVERTE", base)
        self.assertIn("Sign CONVERTE UNIDOS", base)
        secondary_start = base.index('<div class="lm-secondary')
        unidos_start = base.index(
            "{% if request.path.startswith('/converte-unidos') %}",
            secondary_start,
        )
        unidos_end = base.index("{% else %}", unidos_start)
        unidos_header = base[unidos_start:unidos_end]
        self.assertIn('href="https://converte.uno/"', unidos_header)
        self.assertIn(">CONVERTE</a>", unidos_header)
        self.assertIn('href="https://converte.uno/#precio"', unidos_header)
        self.assertIn('href="#planes-unidos"', unidos_header)
        self.assertIn("Crea CONVERTE", unidos_header)
        self.assertIn("Crea CONVERTE UNIDOS", unidos_header)
        self.assertNotIn(">Planes</a>", unidos_header)

    def test_mobile_steps_and_package_scroll_are_explicit(self):
        page = (ROOT / "templates" / "converte_unidos.html").read_text(encoding="utf-8")
        css = (ROOT / "static" / "css" / "style.css").read_text(encoding="utf-8")
        self.assertIn("Desliza para ver los paquetes de 2 a 15 integrantes.", page)
        self.assertIn(".unidos-how .steps", css)
        self.assertIn("overflow-x:auto", css)
        self.assertIn("scroll-snap-type:x mandatory", css)
        self.assertIn("overflow-y:scroll!important", css)
        self.assertIn(".unidos-plan-list::-webkit-scrollbar", css)

    def test_individual_landing_content_remains_unchanged(self):
        digest = hashlib.sha256((ROOT / "templates" / "index.html").read_bytes()).hexdigest()
        self.assertEqual(
            digest,
            "a7f42decc45d4a190a431c4313e361ddf12ca583a5d3b83cd589a5ab020bd0e9",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
