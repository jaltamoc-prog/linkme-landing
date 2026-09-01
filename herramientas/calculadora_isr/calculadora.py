from __future__ import annotations

import io
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from flask import Blueprint, jsonify, render_template, request, send_file
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

calculadora_isr_bp = Blueprint(
    "calculadora_isr", __name__, template_folder="templates", static_folder="static"
)

UMA_ANNUAL = {2025: Decimal("41273.52"), 2026: Decimal("42794.64")}

TARIFFS = {
    2025: [
        ("0.01", "8952.49", "0", "0.0192"),
        ("8952.50", "75984.55", "171.88", "0.064"),
        ("75984.56", "133536.07", "4461.94", "0.1088"),
        ("133536.08", "155229.80", "10723.55", "0.16"),
        ("155229.81", "185852.57", "14194.54", "0.1792"),
        ("185852.58", "374837.88", "19682.13", "0.2136"),
        ("374837.89", "590795.99", "60049.40", "0.2352"),
        ("590796.00", "1127926.84", "110842.74", "0.30"),
        ("1127926.85", "1503902.46", "271981.99", "0.32"),
        ("1503902.47", "4511707.37", "392294.17", "0.34"),
        ("4511707.38", None, "1414947.85", "0.35"),
    ],
    2026: [
        ("0.01", "10135.11", "0", "0.0192"),
        ("10135.12", "86022.11", "194.59", "0.064"),
        ("86022.12", "151176.19", "5051.37", "0.1088"),
        ("151176.20", "175735.66", "12140.13", "0.16"),
        ("175735.67", "210403.69", "16069.64", "0.1792"),
        ("210403.70", "424353.97", "22282.14", "0.2136"),
        ("424353.98", "668840.14", "67981.92", "0.2352"),
        ("668840.15", "1276925.98", "125485.07", "0.30"),
        ("1276925.99", "1702567.97", "307910.81", "0.32"),
        ("1702567.98", "5107703.92", "444116.23", "0.34"),
        ("5107703.93", None, "1601862.46", "0.35"),
    ],
}

GENERAL_DEDUCTION_KEYS = (
    "medical", "mortgage_interest", "medical_insurance",
    "school_transport", "local_salary_tax"
)

def money(value) -> Decimal:
    if value in (None, ""):
        return Decimal("0")
    try:
        result = Decimal(str(value).replace(",", "").replace("$", "").strip())
    except (InvalidOperation, ValueError):
        raise ValueError("Hay un importe con formato inválido.")
    if result < 0:
        raise ValueError("Los importes no pueden ser negativos.")
    return result


def q(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate(payload: dict) -> dict:
    year = int(payload.get("year", 2025))
    if year not in TARIFFS:
        raise ValueError("El ejercicio debe ser 2025 o 2026.")

    salaries = money(payload.get("salaries"))
    assimilated = money(payload.get("assimilated"))
    real_interest = money(payload.get("real_interest"))
    other_accumulated = money(payload.get("other_accumulated"))
    exempt_income = money(payload.get("exempt_income"))
    isr_withheld = money(payload.get("isr_withheld"))
    interest_isr_withheld = money(payload.get("interest_isr_withheld"))
    provisional_payments = money(payload.get("provisional_payments"))
    subsidy = money(payload.get("subsidy"))

    total_income = salaries + assimilated + real_interest + other_accumulated + exempt_income
    accumulated_income = max(Decimal("0"), total_income - exempt_income)

    deductions = payload.get("deductions") or {}
    funeral_requested = money(deductions.get("funeral"))
    funeral_eligible = min(funeral_requested, UMA_ANNUAL[year])
    general_requested = sum((money(deductions.get(k)) for k in GENERAL_DEDUCTION_KEYS), Decimal("0")) + funeral_requested
    general_eligible = sum((money(deductions.get(k)) for k in GENERAL_DEDUCTION_KEYS), Decimal("0")) + funeral_eligible
    general_cap = min(total_income * Decimal("0.15"), UMA_ANNUAL[year] * Decimal("5"))
    general_applied = min(general_eligible, general_cap)

    retirement_requested = money(deductions.get("retirement"))
    retirement_cap = min(accumulated_income * Decimal("0.10"), UMA_ANNUAL[year] * Decimal("5"))
    retirement_applied = min(retirement_requested, retirement_cap)

    prior_year_accumulated = money(payload.get("prior_year_accumulated"))
    donations_requested = money(deductions.get("donations"))
    donations_cap = prior_year_accumulated * Decimal("0.07") if prior_year_accumulated else Decimal("0")
    donations_applied = min(donations_requested, donations_cap) if prior_year_accumulated else Decimal("0")

    tuition_requested = money(deductions.get("tuition"))
    tuition_applied = tuition_requested
    total_deductions = general_applied + retirement_applied + donations_applied + tuition_applied
    taxable_base = max(Decimal("0"), accumulated_income - total_deductions)

    bracket = TARIFFS[year][0]
    for candidate in TARIFFS[year]:
        lower, upper, _, _ = candidate
        if taxable_base >= Decimal(lower) and (upper is None or taxable_base <= Decimal(upper)):
            bracket = candidate
            break
    lower, upper, fixed, rate = bracket
    lower_d, fixed_d, rate_d = Decimal(lower), Decimal(fixed), Decimal(rate)
    excess = max(Decimal("0"), taxable_base - lower_d)
    marginal_tax = excess * rate_d
    tax_due = fixed_d + marginal_tax if taxable_base > 0 else Decimal("0")
    total_credits = isr_withheld + interest_isr_withheld + provisional_payments + subsidy
    balance = tax_due - total_credits

    status = "a_favor" if balance < 0 else ("por_pagar" if balance > 0 else "sin_diferencia")
    return {
        "year": year,
        "total_income": float(q(total_income)),
        "exempt_income": float(q(exempt_income)),
        "accumulated_income": float(q(accumulated_income)),
        "general_requested": float(q(general_requested)),
        "general_cap": float(q(general_cap)),
        "general_applied": float(q(general_applied)),
        "retirement_requested": float(q(retirement_requested)),
        "retirement_cap": float(q(retirement_cap)),
        "retirement_applied": float(q(retirement_applied)),
        "donations_requested": float(q(donations_requested)),
        "donations_cap": float(q(donations_cap)),
        "donations_applied": float(q(donations_applied)),
        "funeral_requested": float(q(funeral_requested)),
        "funeral_eligible": float(q(funeral_eligible)),
        "tuition_requested": float(q(tuition_requested)),
        "tuition_applied": float(q(tuition_applied)),
        "total_deductions": float(q(total_deductions)),
        "taxable_base": float(q(taxable_base)),
        "lower_limit": float(q(lower_d)),
        "excess": float(q(excess)),
        "rate": float(rate_d),
        "marginal_tax": float(q(marginal_tax)),
        "fixed_fee": float(q(fixed_d)),
        "tax_due": float(q(tax_due)),
        "total_credits": float(q(total_credits)),
        "balance": float(q(balance)),
        "status": status,
        "warnings": (["Los donativos no se aplicaron porque falta el ingreso acumulable del ejercicio anterior."]
                     if donations_requested and not prior_year_accumulated else []),
    }


@calculadora_isr_bp.get("/")
def index():
    return render_template("index.html")


@calculadora_isr_bp.get("/privacidad")
def privacy():
    return render_template("legal.html", page="privacidad")


@calculadora_isr_bp.get("/terminos")
def terms():
    return render_template("legal.html", page="terminos")


@calculadora_isr_bp.get("/contacto")
def contact():
    return render_template("legal.html", page="contacto")


@calculadora_isr_bp.get("/robots.txt")
def robots():
    return "User-agent: *\nAllow: /calculadora-isr\nSitemap: https://linkme.life/calculadora-isr/sitemap.xml\n", 200, {"Content-Type": "text/plain; charset=utf-8"}


@calculadora_isr_bp.get("/sitemap.xml")
def sitemap():
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://linkme.life/calculadora-isr</loc><priority>1.0</priority></url>
  <url><loc>https://linkme.life/calculadora-isr/privacidad</loc></url>
  <url><loc>https://linkme.life/calculadora-isr/terminos</loc></url>
  <url><loc>https://linkme.life/calculadora-isr/contacto</loc></url>
</urlset>"""
    return xml, 200, {"Content-Type": "application/xml; charset=utf-8"}


@calculadora_isr_bp.get("/health")
def health():
    return jsonify(status="ok", service="calculadora-isr-mx")


@calculadora_isr_bp.post("/api/calculate")
def api_calculate():
    try:
        return jsonify(calculate(request.get_json(silent=True) or {}))
    except ValueError as exc:
        return jsonify(error=str(exc)), 400


def mx(value: float) -> str:
    return f"${value:,.2f}"


@calculadora_isr_bp.post("/report.pdf")
def report_pdf():
    payload = request.get_json(silent=True) or {}
    try:
        result = calculate(payload)
    except ValueError as exc:
        return jsonify(error=str(exc)), 400

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=18*mm, leftMargin=18*mm,
                            topMargin=16*mm, bottomMargin=16*mm,
                            title=f"Estimación ISR {result['year']}")
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Brand", parent=styles["Title"], textColor=colors.HexColor("#123B5D"),
                              fontSize=20, leading=24, alignment=TA_LEFT, spaceAfter=4))
    styles.add(ParagraphStyle(name="SmallGray", parent=styles["BodyText"], textColor=colors.HexColor("#5E6B75"),
                              fontSize=8.5, leading=12))
    styles.add(ParagraphStyle(name="Result", parent=styles["Heading2"], textColor=colors.HexColor("#0B6B55"),
                              alignment=TA_CENTER, fontSize=16, leading=20))

    label = "Saldo estimado a favor" if result["status"] == "a_favor" else "ISR estimado por pagar"
    amount = abs(result["balance"])
    story = [
        Paragraph("Calculadora ISR México", styles["Brand"]),
        Paragraph(f"Reporte detallado · Ejercicio {result['year']} · Generado {datetime.now().strftime('%d/%m/%Y')}", styles["SmallGray"]),
        Spacer(1, 8*mm),
        Paragraph(f"{label}: {mx(amount)}", styles["Result"]),
        Spacer(1, 6*mm),
    ]
    rows = [
        ["Determinación", "Importe"],
        ["Ingresos totales", mx(result["total_income"])],
        ["Ingresos exentos", f"({mx(result['exempt_income'])})"],
        ["Ingresos acumulables", mx(result["accumulated_income"])],
        ["Deducciones aplicadas", f"({mx(result['total_deductions'])})"],
        ["Base gravable", mx(result["taxable_base"])],
        ["Límite inferior", mx(result["lower_limit"])],
        ["Excedente", mx(result["excess"])],
        [f"Porcentaje ({result['rate']*100:.2f}%)", mx(result["marginal_tax"])],
        ["Cuota fija", mx(result["fixed_fee"])],
        ["ISR causado", mx(result["tax_due"])],
        ["Retenciones, pagos y subsidio", f"({mx(result['total_credits'])})"],
        [label, mx(amount)],
    ]
    table = Table(rows, colWidths=[118*mm, 52*mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#123B5D")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("ALIGN", (1,1), (1,-1), "RIGHT"),
        ("GRID", (0,0), (-1,-1), .35, colors.HexColor("#CBD5DC")),
        ("BACKGROUND", (0,1), (-1,-2), colors.HexColor("#F6F8FA")),
        ("BACKGROUND", (0,-1), (-1,-1), colors.HexColor("#DDF4EA")),
        ("FONTNAME", (0,-1), (-1,-1), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 9),
        ("TOPPADDING", (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
    ]))
    story.extend([table, Spacer(1, 7*mm)])
    limits = [
        ["Control de deducciones", "Solicitado", "Aplicado"],
        ["Límite general Art. 151", mx(result["general_requested"]), mx(result["general_applied"])],
        ["Aportaciones para retiro", mx(result["retirement_requested"]), mx(result["retirement_applied"])],
        ["Donativos", mx(result["donations_requested"]), mx(result["donations_applied"])],
        ["Colegiaturas", mx(result["tuition_requested"]), mx(result["tuition_applied"])],
    ]
    limit_table = Table(limits, colWidths=[84*mm, 43*mm, 43*mm])
    limit_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#D8E8F2")),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("ALIGN", (1,1), (-1,-1), "RIGHT"),
        ("GRID", (0,0), (-1,-1), .35, colors.HexColor("#CBD5DC")),
        ("FONTSIZE", (0,0), (-1,-1), 8.5),
        ("TOPPADDING", (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
    ]))
    story.extend([limit_table, Spacer(1, 7*mm)])
    note = ("Resultado informativo elaborado con la tarifa anual oficial del ejercicio seleccionado. "
            "No sustituye la declaración prellenada del SAT ni una revisión profesional. El resultado final puede cambiar "
            "por CFDI, topes particulares, ingresos no capturados, pérdidas, acreditamientos o datos fiscales adicionales.")
    story.append(Paragraph(note, styles["SmallGray"]))
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph("Fuentes: Anexo 8 de la RMF 2025/2026; artículos 150, 151 y 152 de la LISR.", styles["SmallGray"]))
    doc.build(story)
    buffer.seek(0)
    return send_file(buffer, mimetype="application/pdf", as_attachment=True,
                     download_name=f"estimacion_isr_{result['year']}.pdf")

