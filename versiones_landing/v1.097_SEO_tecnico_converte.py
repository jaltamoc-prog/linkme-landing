
from pathlib import Path
import re

ROOT = Path(r"C:\procesos python\landing linkme")
APP = ROOT / "app.py"
HTML = ROOT / "templates" / "index.html"

if not APP.exists():
    raise SystemExit(f"ERROR: no existe {APP}")
if not HTML.exists():
    raise SystemExit(f"ERROR: no existe {HTML}")

app_text = APP.read_text(encoding="utf-8")
html = HTML.read_text(encoding="utf-8")

verification = '<meta name="google-site-verification" content="IfrkQftaidYk_tGlvoIfQFGFdc6-4w_FD961KWGjJWk" />'

seo_block = (
'<!-- SEO CONVERTE v1.097 -->\n'
'<title>Converte | Tarjeta digital profesional</title>\n'
'<meta name="description" content="Converte es tu tarjeta digital profesional para compartir contacto, redes sociales y perfil desde una sola liga. Lista para presentar quién eres y cómo contactarte.">\n'
'<meta name="robots" content="index,follow,max-image-preview:large">\n'
'<link rel="canonical" href="https://converte.uno/">\n'
'<meta property="og:type" content="website">\n'
'<meta property="og:locale" content="es_MX">\n'
'<meta property="og:site_name" content="Converte">\n'
'<meta property="og:title" content="Converte | Tarjeta digital profesional">\n'
'<meta property="og:description" content="Comparte tu contacto, redes sociales y perfil profesional desde una sola liga con Converte.">\n'
'<meta property="og:url" content="https://converte.uno/">\n'
'<meta name="twitter:card" content="summary">\n'
'<meta name="twitter:title" content="Converte | Tarjeta digital profesional">\n'
'<meta name="twitter:description" content="Tu tarjeta digital profesional para compartir contacto, redes sociales y perfil desde una sola liga.">\n'
'<script type="application/ld+json">\n'
'{"@context":"https://schema.org","@graph":[{"@type":"Organization","@id":"https://converte.uno/#organization","name":"Converte","url":"https://converte.uno/"},{"@type":"WebSite","@id":"https://converte.uno/#website","url":"https://converte.uno/","name":"Converte","inLanguage":"es-MX","publisher":{"@id":"https://converte.uno/#organization"}}]}\n'
'</script>\n'
'<!-- /SEO CONVERTE v1.097 -->'
)

# Evitar duplicados de elementos principales
html = re.sub(r'<title>.*?</title>', '', html, count=1, flags=re.I|re.S)
html = re.sub(r'<meta\s+name=["\']description["\'][^>]*>', '', html, count=1, flags=re.I)
html = re.sub(r'<link\s+rel=["\']canonical["\'][^>]*>', '', html, count=1, flags=re.I)

head_open = re.search(r'<head[^>]*>', html, flags=re.I)
if not head_open:
    raise SystemExit("ERROR: no se encontró <head> en templates\\index.html")

pos = head_open.end()
insert = "\n"
if verification not in html:
    insert += "  " + verification + "\n"
if '<!-- SEO CONVERTE v1.097 -->' not in html:
    insert += seo_block + "\n"
html = html[:pos] + insert + html[pos:]
HTML.write_text(html, encoding="utf-8")

# Asegurar Response en import de Flask
lines = app_text.splitlines()
for i, line in enumerate(lines):
    if line.startswith("from flask import "):
        if "Response" not in line:
            lines[i] = line.rstrip() + ", Response"
        break
app_text = "\n".join(lines) + ("\n" if app_text.endswith("\n") else "")

routes_block = (
"\n# --- SEO CONVERTE v1.097 ---\n"
"@app.route('/robots.txt')\n"
"def converte_robots_txt():\n"
"    body = \"User-agent: *\\nAllow: /\\nDisallow: /admin\\nDisallow: /api\\nDisallow: /checkout\\nDisallow: /success\\nDisallow: /cancel\\n\\nSitemap: https://converte.uno/sitemap.xml\\n\"\n"
"    return Response(body, mimetype='text/plain')\n\n"
"@app.route('/sitemap.xml')\n"
"def converte_sitemap_xml():\n"
"    xml = \"<?xml version=\\\"1.0\\\" encoding=\\\"UTF-8\\\"?>\\n<urlset xmlns=\\\"http://www.sitemaps.org/schemas/sitemap/0.9\\\"><url><loc>https://converte.uno/</loc><changefreq>weekly</changefreq><priority>1.0</priority></url></urlset>\"\n"
"    return Response(xml, mimetype='application/xml')\n"
"# --- /SEO CONVERTE v1.097 ---\n\n"
)

if "# --- SEO CONVERTE v1.097 ---" not in app_text:
    markers = ['if __name__ == "__main__":', "if __name__ == '__main__':"]
    inserted = False
    for marker in markers:
        p = app_text.find(marker)
        if p != -1:
            app_text = app_text[:p] + routes_block + app_text[p:]
            inserted = True
            break
    if not inserted:
        app_text += routes_block

APP.write_text(app_text, encoding="utf-8")

# Validaciones
compile(APP.read_text(encoding="utf-8"), str(APP), "exec")
final = HTML.read_text(encoding="utf-8") + APP.read_text(encoding="utf-8")

checks = [
    verification,
    'rel="canonical" href="https://converte.uno/"',
    'name="description"',
    '"@type":"WebSite"',
    "@app.route('/robots.txt')",
    "@app.route('/sitemap.xml')",
    "https://converte.uno/sitemap.xml",
]
missing = [x for x in checks if x not in final]
if missing:
    raise SystemExit("ERROR: validación SEO incompleta: " + " | ".join(missing))

print("OK: SEO técnico de Converte instalado.")
print("OK: Search Console conservado.")
print("OK: robots.txt y sitemap.xml agregados.")
print("OK: sintaxis de app.py validada.")
