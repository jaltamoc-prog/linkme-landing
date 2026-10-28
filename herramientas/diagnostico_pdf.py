# -*- coding: utf-8 -*-
"""PDF descargable del diagnostico ampliado. No usa datos privados de Google."""
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, KeepTogether, HRFlowable


def build_pdf(audit, report, goal_label, checks=None):
    """Produce un PDF con observaciones respaldadas por HTML publico."""
    buffer = BytesIO()
    navy = colors.HexColor("#173741")
    teal = colors.HexColor("#126C72")
    muted = colors.HexColor("#4D6367")
    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "TituloDiagnostico", parent=styles["Title"], fontName="Helvetica-Bold",
        fontSize=22, leading=27, alignment=TA_LEFT, textColor=navy,
        spaceAfter=12,
    )
    section = ParagraphStyle(
        "SeccionDiagnostico", parent=styles["Heading2"], fontName="Helvetica-Bold",
        fontSize=13, leading=17, textColor=navy, spaceBefore=15, spaceAfter=8,
    )
    subtitle = ParagraphStyle(
        "SubtituloDiagnostico", parent=styles["Heading3"], fontName="Helvetica-Bold",
        fontSize=11, leading=15, textColor=teal, spaceBefore=8, spaceAfter=4,
    )
    body = ParagraphStyle(
        "TextoDiagnostico", parent=styles["Normal"], fontName="Helvetica",
        fontSize=9.5, leading=15, textColor=navy, spaceAfter=7,
    )
    note = ParagraphStyle(
        "NotaDiagnostico", parent=body, fontSize=8, leading=12, textColor=muted,
    )
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, rightMargin=19*mm, leftMargin=19*mm,
        topMargin=20*mm, bottomMargin=18*mm,
        title="Diagnostico Web - Informe completo",
        author="Diagnostico Web por Converte",
    )
    story = [
        Paragraph("DIAGNOSTICO WEB", subtitle),
        Paragraph("Informe completo de oportunidades", title),
        Paragraph("Una auditoria tecnica traducida a acciones claras para tu negocio.", body),
        HRFlowable(width="100%", thickness=1.2, color=teal, spaceAfter=12),
        Paragraph("<b>Pagina analizada:</b> " + escape(str(audit["url"])), body),
        Paragraph("<b>Objetivo:</b> " + escape(str(goal_label)), body),
        Paragraph("<b>Revision:</b> " + escape(str(audit["checked"])), body),
        Paragraph("<b>Oportunidades detectadas:</b> " + str(report["count"]), body),
        Paragraph("Por donde comenzar", section),
        Paragraph(
            "Las acciones estan ordenadas segun la gravedad observable en el codigo. "
            "No equivalen a perdidas de ventas ni a posiciones medidas en Google.",
            note,
        ),
    ]
    if not report["findings"]:
        story.append(Paragraph(
            "No encontramos problemas basicos en esta revision automatica. "
            "Una auditoria sin hallazgos no garantiza visibilidad ni conversiones.",
            body,
        ))
    for i, item in enumerate(report["findings"], 1):
        elements = [
            Paragraph(
                "%d. %s" % (i, escape(str(item["title"]))),
                subtitle,
            ),
            Paragraph(
                "<b>Prioridad:</b> %s &nbsp; | &nbsp; <b>Esfuerzo estimado:</b> %s"
                % (escape(str(item["level"])), escape(str(item["effort"]))),
                body,
            ),
            Paragraph("<b>Por que importa:</b> " + escape(str(item["reason"])), body),
            Paragraph("<b>Que corregir:</b> " + escape(str(item["action"])), body),
            Paragraph("<b>Evidencia:</b> " + escape(str(item["evidence"])), note),
            Spacer(1, 5),
        ]
        story.append(KeepTogether(elements))
    if checks:
        story.append(Paragraph("Plan completo de revisión y acciones", section))
        story.append(Paragraph(
            "Estas comprobaciones detallan qué se encontró en la página y qué debe "
            "verificar o cambiar el responsable web. Algunas requieren una revisión "
            "humana, aunque los indicadores básicos ya estén presentes.",
            note,
        ))
        for i, item in enumerate(checks, 1):
            story.append(KeepTogether([
                Paragraph("%d. %s" % (i, escape(str(item["area"]))), subtitle),
                Paragraph(
                    "<b>Estado:</b> %s &nbsp; | &nbsp; <b>Relevancia:</b> %s" %
                    (escape(str(item["status"])), escape(str(item["priority"]))), body),
                Paragraph("<b>Evidencia:</b> " + escape(str(item["evidence"])), note),
                Paragraph("<b>Acción:</b> " + escape(str(item["action"])), body),
                Spacer(1, 5),
            ]))
    story.append(Paragraph("Aspectos positivos comprobados", section))
    for positive in report["positives"]:
        story.append(Paragraph("&#8226; " + escape(str(positive)), body))
    story.extend([
        Paragraph("Datos tecnicos para tu responsable web", section),
        Paragraph(
            "<b>Titulo:</b> " + escape(audit.get("title") or "Ausente"), body),
        Paragraph(
            "<b>Descripcion para buscadores:</b> " + escape(audit.get("description") or "Ausente"), body),
        Paragraph(
            "<b>Direccion canonica:</b> " + escape(audit.get("canonical") or "No declarada"), body),
        Paragraph(
            "<b>Encabezados H1:</b> %s &nbsp; | &nbsp; <b>Imagenes sin atributo alt:</b> %s" %
            (audit.get("h1", 0), audit.get("noalt", 0)), body),
        Paragraph(
            "<b>Configuracion movil:</b> " + ("Detectada" if audit.get("viewport") else "No detectada"), body),
        Paragraph(
            "<b>Datos estructurados JSON-LD:</b> %s &nbsp; | &nbsp; <b>Formularios HTML:</b> %s" %
            (audit.get("jsonld", 0), audit.get("forms", 0)), body),
        Paragraph("Alcance y limitaciones", section),
        Paragraph(
            "Este documento examina el HTML publico de una direccion. No mide automaticamente "
            "ventas, conversiones, indexacion efectiva en Google, rendimiento del navegador "
            "ni elementos que dependan de JavaScript. Las sugerencias se deben contrastar "
            "con el contexto del negocio antes de aplicarlas. La fecha refleja el momento "
            "del analisis y no constituye monitoreo continuo.",
            note,
        ),
        Spacer(1, 12),
        HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#C8DAD8")),
        Paragraph("Diagnostico Web · converte.uno/diagnostico-web/", note),
    ])

    def decorate(canvas, reportdoc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(muted)
        canvas.drawString(19*mm, 12*mm, "Diagnostico Web por Converte")
        canvas.drawRightString(A4[0] - 19*mm, 12*mm, "Pagina %s" % reportdoc.page)
        canvas.restoreState()

    doc.build(story, onFirstPage=decorate, onLaterPages=decorate)
    buffer.seek(0)
    return buffer
