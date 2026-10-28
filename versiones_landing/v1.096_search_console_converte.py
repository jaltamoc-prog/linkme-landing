from pathlib import Path

ROOT = Path(r"C:\procesos python\landing linkme")
HTML = ROOT / "templates" / "index.html"

TAG = '<meta name="google-site-verification" content="IfrkQftaidYk_tGlvoIfQFGFdc6-4w_FD961KWGjJWk" />'

if not HTML.exists():
    raise SystemExit(f"ERROR: No existe {HTML}")

text = HTML.read_text(encoding="utf-8")

if TAG in text:
    print("La etiqueta de Google Search Console ya existe. No se hicieron cambios.")
    raise SystemExit(0)

head_pos = text.lower().find("<head")
if head_pos == -1:
    raise SystemExit("ERROR: No se encontró <head> en templates\\index.html")

head_close = text.find(">", head_pos)
if head_close == -1:
    raise SystemExit("ERROR: <head> no está correctamente cerrado.")

new_text = text[:head_close+1] + "\n  " + TAG + text[head_close+1:]

# Validaciones de seguridad: un solo cambio funcional esperado.
if new_text.count(TAG) != 1:
    raise SystemExit("ERROR: La etiqueta no quedó insertada exactamente una vez.")

HTML.write_text(new_text, encoding="utf-8")

print("OK: Google Search Console agregado a converte.uno")
print(f"Archivo modificado: {HTML}")
