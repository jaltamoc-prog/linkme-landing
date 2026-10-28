# -*- coding: utf-8 -*-
"""Informes visuales de Diagnostico Web, hechos con los datos REALES del analisis.

Dos paginas deliberadamente compactas. El informe no calcula puntuaciones SEO
ficticias, ventas, posiciones ni visitas. Los estados indican exclusivamente
senales detectables en HTML o verificaciones que debe realizar el propietario.
"""
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas

from herramientas import diagnostico_evaluacion as business

W, H = A4
PAD = 34
RIGHT = W - PAD
WIDTH = W - 2 * PAD
NAVY = colors.HexColor("#173C42")
TEAL = colors.HexColor("#147A76")
DARK = colors.HexColor("#24444A")
MUTED = colors.HexColor("#587176")
PALE = colors.HexColor("#F5F9F7")
LINE = colors.HexColor("#DDE9E5")
WHITE = colors.white
STATES = {
    "ok": ("SEÑAL DETECTADA", colors.HexColor("#DDF1E6"), colors.HexColor("#1E6B4C")),
    "issue": ("CONVIENE MEJORAR", colors.HexColor("#FFF0D8"), colors.HexColor("#915C18")),
    "review": ("POR CONFIRMAR", colors.HexColor("#EBEFF3"), colors.HexColor("#596E7D")),
}
LABELS = {
    "search_console": "Presencia en Google",
    "sitemap": "Mapa de páginas",
    "analytics": "Medición de visitas",
    "business_profile": "Negocio en Google Maps",
    "keyword_title": "Lo que busca tu cliente",
    "city": "Ciudad donde vendes",
    "description": "Cómo explicas tu oferta",
    "internal_links": "Otros servicios visibles",
    "images_speed": "Imágenes y carga",
    "backlinks": "Menciones de otros sitios",
    "noindex": "Bloqueos en Google",
    "mobile": "Preparación para celular",
    "heading": "Mensaje principal",
    "action_path": "Contacto o compra",
}



# Frases comerciales cortas, derivadas SOLO del estado observado.
# Cuando Google exige acceso privado, nunca se afirma que funcionó.
QUICK = {
 "search_console": ("No tenemos acceso a esa cuenta", "Mira tus páginas en Search Console"),
 "sitemap": ("Encontramos una referencia al mapa", "Confirma que Google recibió tu mapa"),
 "analytics": ("Vimos una señal de medición", "Comprueba las visitas en Google Analytics"),
 "business_profile": ("Vimos un enlace a Google Maps", "Revisa datos y horarios en Google Maps"),
 "keyword_title": ("Tu frase aparece en el título", "Revisa que tu título diga qué ofreces"),
 "city": ("Tu ciudad aparece en esta página", "Incluye tu ciudad si atiendes una zona"),
 "description": ("Vimos una descripción de tu oferta", "Resume qué vendes en una frase"),
 "internal_links": ("Hay enlaces a más páginas", "Enlaza con tus productos o servicios"),
 "images_speed": ("Detectamos imágenes modernas", "Mide la carga en PageSpeed Insights"),
 "backlinks": ("Requiere datos de tu cuenta Google", "Revisa quién enlaza tu web en Google"),
 "noindex": ("No vimos bloqueo 'noindex'", "Consulta si la página debe ser pública"),
 "mobile": ("Hay una señal básica para móvil", "Prueba botones y texto en tu celular"),
 "heading": ("Encontramos un título principal", "Pon tu oferta en el título principal"),
 "action_path": ("Detectamos una forma de contacto", "Prueba tu botón de contacto o compra"),
}
ISSUE = {
 "sitemap": "No vimos una referencia al mapa",
 "analytics": "No vimos la etiqueta en el HTML",
 "keyword_title": "La frase elegida no está en el título",
 "city": "La ciudad elegida no aparece",
 "description": "Falta la descripción de tu oferta",
 "internal_links": "No vimos enlaces a otros servicios",
 "noindex": "Detectamos una orden de bloqueo",
 "mobile": "No vimos señal básica para móvil",
 "heading": "Revisa el título principal de tu web",
 "action_path": "No vimos una forma clara de contacto",
}
UNCERTAIN = {
 "search_console": "Solo tú puedes confirmar esa cuenta",
 "sitemap": "Puede existir aunque no lo vimos aquí",
 "analytics": "Puede cargarse después en el navegador",
 "business_profile": "No vimos enlace; el perfil puede existir",
 "keyword_title": "Falta indicar qué buscaría tu cliente",
 "city": "No indicaste una ciudad objetivo",
 "images_speed": "No medimos cuánto tarda en cargar",
 "backlinks": "No conocemos tus enlaces externos",
 "noindex": "Falta información para comprobarlo",
 "mobile": "Falta revisar cómo se ve en celular",
}
IMPACT = {
 "analytics": "Sin medir visitas, cuesta decidir qué mejorar.",
 "keyword_title": "Puede ser más difícil que te encuentre tu cliente.",
 "city": "Quien busca cerca podría no identificar tu zona.",
 "description": "Tu oferta podría verse poco clara en los resultados.",
 "internal_links": "Quizá el visitante no descubra tus otros servicios.",
 "noindex": "Google podría no mostrar esta página.",
 "mobile": "La experiencia en celular podría dificultar el contacto.",
 "action_path": "Un interesado podría irse sin preguntar.",
 "heading": "Tal vez no se entienda en segundos qué vendes.",
 "images_speed": "Una carga lenta puede hacer perder interesados.",
}
def _plain(item):
    key=item.get("id")
    status=item.get("status","review")
    positive,action=QUICK.get(key,("Detectamos una señal pública","Revisa este punto en tu página"))
    if status=="issue":
        evidence=ISSUE.get(key,"No vimos una señal esperada")
    elif status=="review":
        evidence=UNCERTAIN.get(key,"Necesita confirmación del negocio")
    else:
        evidence=positive
    return evidence,action,IMPACT.get(key,"Conviene comprobarlo para facilitar tus consultas.")


def _line(c, x, y, value, width, size=10, bold=False, color=DARK, max_lines=1):
    """Write bounded lines. Never let long customer URLs or content overlap."""
    value = " ".join(str(value or "").replace("\n", " ").split())
    font = "Helvetica-Bold" if bold else "Helvetica"
    chunks = simpleSplit(value, font, size, max(10, width))
    chunks = chunks[:max_lines]
    if not chunks:
        return y
    if len(simpleSplit(value, font, size, max(10, width))) > max_lines:
        last = chunks[-1]
        while last and c.stringWidth(last + "...", font, size) > width:
            last = last[:-1]
        chunks[-1] = last.rstrip() + "..."
    c.setFont(font, size)
    c.setFillColor(color)
    for item in chunks:
        c.drawString(x, y, item)
        y -= size + 3.3
    return y


def _rect(c, x, y, width, height, bg=WHITE, stroke=LINE, radius=12):
    c.setFillColor(bg)
    c.setStrokeColor(stroke)
    c.setLineWidth(.7)
    c.roundRect(x, y-height, width, height, radius, fill=1, stroke=1)


def _state(c, x, y, status, small=False):
    label, bg, fg = STATES.get(status, STATES["review"])
    size = 7.1 if small else 8
    width = c.stringWidth(label, "Helvetica-Bold", size) + (14 if small else 18)
    c.setFillColor(bg)
    c.roundRect(x, y-8, width, 18 if not small else 16, 8, fill=1, stroke=0)
    c.setFillColor(fg)
    c.setFont("Helvetica-Bold", size)
    c.drawString(x+8, y-3.3, label)
    return width


def _header(c, title, subtitle, url, date, page, plan):
    c.setFillColor(NAVY)
    c.rect(0, H-103, W, 103, fill=1, stroke=0)
    c.setFillColor(colors.HexColor("#B7E6DC"))
    c.setFont("Helvetica-Bold", 10)
    c.drawString(PAD, H-27, "CONVERTE  /  DIAGNÓSTICO WEB")
    c.setFillColor(WHITE)
    _line(c, PAD, H-53, title, WIDTH, size=19, bold=True, color=WHITE)
    _line(c, PAD, H-75, subtitle, WIDTH, size=10, color=WHITE)
    c.setFillColor(MUTED)
    _line(c, PAD, H-123, "Página: " + str(url), WIDTH-145, 8.3, color=MUTED)
    c.setFont("Helvetica", 8)
    c.drawRightString(RIGHT, H-123, str(date or "")[:22])
    c.setStrokeColor(LINE)
    c.line(PAD, 40, RIGHT, 40)
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 8)
    c.drawString(PAD, 26, "Señales del sitio público. No medimos ventas ni posiciones en Google.")
    c.drawRightString(RIGHT, 26, "Página %d  /  %s" % (page, plan))


def _kpi(c, left, top, value, label, bg, fg):
    width = (WIDTH-20)/3
    _rect(c, left, top, width, 79, bg=bg, stroke=bg, radius=12)
    _line(c, left+13, top-32, str(value), width-26, 27, bold=True, color=fg)
    _line(c, left+13, top-55, label, width-26, 9.2, color=DARK)


def _distribution(c, top, stats):
    total = sum(stats)
    x = PAD
    for n, key in zip(stats, ("ok", "issue", "review")):
        segment = WIDTH * n / max(total, 1)
        if segment > 0:
            c.setFillColor(STATES[key][2])
            c.rect(x, top-13, segment, 13, fill=1, stroke=0)
        x += segment


def _action(c, number, item, top, height=115):
    _rect(c, PAD, top, WIDTH, height, bg=PALE)
    c.setFillColor(TEAL)
    c.circle(PAD+21, top-25, 12, stroke=0, fill=1)
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(PAD+21, top-29, str(number))
    title = LABELS.get(item.get("id"), str(item.get("title","Recomendación")))
    _line(c, PAD+42, top-21, title, WIDTH-174, 12, bold=True)
    _state(c, RIGHT-117, top-22, item.get("status", "review"), small=True)
    is_compact = height < 100
    evidence, action, impact = _plain(item)
    if is_compact:
        _line(c, PAD+17, top-44, "Detectamos: " + evidence, WIDTH-33, 9.0, color=MUTED)
        _line(c, PAD+17, top-65, "Haz esto: " + action, WIDTH-33, 9.0, color=DARK)
    else:
        _line(c, PAD+17, top-46, "Detectamos: " + evidence, WIDTH-33, 9.3, color=MUTED)
        _line(c, PAD+17, top-65, "Te puede afectar: " + impact, WIDTH-33, 9.3, color=MUTED)
        _line(c, PAD+17, top-87, "Haz esto: " + action, WIDTH-33, 9.5, bold=True, color=DARK)


def _audit_grid(c, rows, title, subtitle, url, date, plan):
    _header(c, title, subtitle, url, date, 2, plan)
    count = min(14, len(rows))
    xgap, ygap = 10, 8
    cw = (WIDTH-xgap)/2
    card_h = 84
    top = H-152
    for i, item in enumerate(rows[:14]):
        column, row = i % 2, i // 2
        x = PAD + column*(cw+xgap)
        y = top-row*(card_h+ygap)
        _rect(c, x, y, cw, card_h, bg=WHITE)
        badge = "%02d" % (i+1)
        c.setFont("Helvetica-Bold", 8.8)
        c.setFillColor(TEAL)
        c.drawString(x+11, y-17, badge)
        title = LABELS.get(item.get("id"), str(item.get("title", "")))
        _line(c, x+32, y-17, title, cw-43, 10, bold=True)
        _state(c, x+11, y-35, item.get("status", "review"), small=True)
        evidence, action, _ = _plain(item)
        _line(c, x+11, y-52, "Vimos: " + evidence, cw-22, 8.3, color=MUTED)
        _line(c, x+11, y-68, "Haz esto: " + action, cw-22, 8.3, color=DARK)
    c.showPage()


def _main_one_time(c, audit, goal, rows):
    _header(c, "Informe completo de oportunidades",
            "Tu diagnóstico visual de hoy: qué hay y qué puedes mejorar",
            audit.get("url", ""), audit.get("checked", ""), 1, "Pago único")
    stats = (
        sum(a["status"]=="ok" for a in rows),
        sum(a["status"]=="issue" for a in rows),
        sum(a["status"]=="review" for a in rows),
    )
    _line(c, PAD, H-154, "Tu página, de un vistazo", WIDTH, 17, bold=True)
    labels = ("Señales encontradas", "Por mejorar", "Por confirmar")
    keys = ("ok","issue","review")
    for i, (n,label,key) in enumerate(zip(stats,labels,keys)):
        _kpi(c, PAD+i*((WIDTH-20)/3+10), H-174, n, label,
             STATES[key][1], STATES[key][2])
    _distribution(c, H-267, stats)
    _line(c, PAD, H-295, "%d aspectos revisados · No es una calificación SEO" % len(rows),
          WIDTH, 9, color=MUTED)
    _line(c, PAD, H-331, "Empieza por estas 3 acciones", WIDTH, 15, bold=True)
    prioritized = [r for r in rows if r["status"]=="issue"]+[r for r in rows if r["status"]=="review"]
    if not prioritized:
        prioritized = rows[:3]
    for index,item in enumerate(prioritized[:3]):
        _action(c, index+1,item,H-346-index*124,115)
    _line(c, PAD, 78, "En la siguiente página: tus 14 temas, con señales y pasos concretos.",
          WIDTH, 9, bold=True, color=TEAL)
    c.showPage()


def _progress_bars(c, top, prog):
    _line(c, PAD, top, "¿Tu web está mejorando?", WIDTH, 16, bold=True)
    if not prog["total"]:
        _line(c, PAD, top-24, "Aún no hay datos equivalentes para comparar estas fechas.",
              WIDTH, 10, color=MUTED)
        return
    for i,(title,ratio,value) in enumerate((
        ("Primera revisión",prog["start_pct"],prog["start"]),
        ("Última revisión",prog["end_pct"],prog["end"]),
    )):
        y = top - 32 - i*40
        _line(c, PAD, y, title, 150, 10, bold=True)
        left = PAD+163
        barwidth = WIDTH-231
        c.setFillColor(LINE)
        c.roundRect(left,y-4,barwidth,16,7,fill=1,stroke=0)
        c.setFillColor(TEAL)
        if ratio:
            c.roundRect(left,y-4,max(1,barwidth*ratio/100),16,7,fill=1,stroke=0)
        _line(c, RIGHT-61, y, "%s / %s" % (value,prog["total"]), 60, 10, bold=True)
    _line(c, PAD, top-112,
          "Solo señales observables en ambas fechas. No son visitas ni ventas.",
          WIDTH, 8.7, color=MUTED)


def _history_chart(c, top, baseline, history, goal):
    points=business.history_progress(baseline, history or [],goal)
    _line(c,PAD,top,"Revisiones disponibles mes por mes",WIDTH,12,bold=True)
    if len(points)<2:
        _line(c,PAD,top-20,"Cuando realices otra revisión, aquí aparecerá su avance.",WIDTH,9,color=MUTED)
        return
    n=min(len(points),13)
    pad=17
    available=WIDTH-2*pad
    step=available/n
    barw=min(24,step*0.52)
    baseline_y=top-112
    c.setStrokeColor(LINE)
    c.line(PAD+pad,baseline_y,RIGHT-pad,baseline_y)
    for i,p in enumerate(points[-13:]):
        x=PAD+pad+(i+.5)*step
        ratio=max(0,min(100,p.get("pct",0)))
        h=74*ratio/100
        c.setFillColor(LINE)
        c.roundRect(x-barw/2,baseline_y,barw,74,4,fill=1,stroke=0)
        if h:
            c.setFillColor(TEAL)
            c.roundRect(x-barw/2,baseline_y,barw,h,4,fill=1,stroke=0)
        label="Inicio" if p["month"]=="Inicio" else str(p["month"])[-2:]
        c.setFont("Helvetica",7)
        c.setFillColor(MUTED)
        c.drawCentredString(x,baseline_y-11,label)
    _line(c,PAD,top-133,"Cada barra representa las señales positivas verificables de esa fecha.",WIDTH,8,color=MUTED)


def _main_monthly(c, url, goal, baseline, latest, history, rows):
    _header(c, "Seguimiento mensual de tu página web",
            "Antes y ahora, sin palabras técnicas",
            url, latest.get("checked",""),1,"Mensual")
    prog=business.progress(baseline,latest,goal)
    stats=(len(prog["improved"]),len(prog["regressed"]),
           sum(a["status"]=="review" for a in rows))
    labels=("Mejoras detectadas","Necesitan atención","Por confirmar")
    for i,(n,label,key) in enumerate(zip(stats,labels,("ok","issue","review"))):
        _kpi(c,PAD+i*((WIDTH-20)/3+10),H-149,n,label,STATES[key][1],STATES[key][2])
    _progress_bars(c,H-263,prog)
    _history_chart(c,H-417,baseline,history,goal)
    _line(c,PAD,H-583,"Acciones recomendadas para este mes",WIDTH,15,bold=True)
    prioritized=[r for r in rows if r["status"]=="issue"]+[r for r in rows if r["status"]=="review"]
    if not prioritized:prioritized=rows[:3]
    for i, item in enumerate(prioritized[:2]):
        _action(c,i+1,item,H-596-i*97,89)
    c.showPage()


def build_one_time(audit, report, goal_label, seo_checks=None):
    """Single-date visual report. No extra audits, fake grades or subscriptions."""
    rows=seo_checks or business.checks(audit,audit.get("goal","contactos"))
    buffer=BytesIO()
    c=canvas.Canvas(buffer,pagesize=A4,pageCompression=1)
    c.setTitle("Diagnostico visual de tu negocio - Informe completo")
    c.setAuthor("Converte - Diagnostico Web")
    _main_one_time(c,audit,goal_label,rows)
    _audit_grid(c,rows,"14 aspectos principales revisados",
                "Qué vimos y qué puedes hacer en cada tema",
                audit.get("url",""),audit.get("checked",""),"Pago único")
    c.save()
    buffer.seek(0)
    return buffer


def build_monthly(url, goal_label, baseline, latest, history=None, goal="contactos"):
    """Monthly chart is based strictly on saved user-requested review snapshots."""
    rows=business.checks(latest,goal)
    buffer=BytesIO()
    c=canvas.Canvas(buffer,pagesize=A4,pageCompression=1)
    c.setTitle("Seguimiento mensual - Diagnostico Web")
    c.setAuthor("Converte - Diagnostico Web")
    _main_monthly(c,url,goal,baseline,latest,history,rows)
    _audit_grid(c,rows,"Los 14 aspectos incluidos en cada revisión",
                "Estado de la última revisión: señales y próximos pasos",
                url,latest.get("checked",""),"Mensual")
    c.save()
    buffer.seek(0)
    return buffer
