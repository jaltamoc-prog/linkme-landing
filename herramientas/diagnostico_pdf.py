# -*- coding: utf-8 -*-
"""Compatibilidad con los informes ya comprados. La entrega usa ahora PDF visual."""
from herramientas.diagnostico_visual_pdf import build_one_time


def build_pdf(audit, report, goal_label, checks=None, seo_checks=None, comparison=None):
    """Informe de compra única: dos páginas gráficas, sin segunda revisión."""
    return build_one_time(audit, report, goal_label, seo_checks=seo_checks)
