# -*- coding: utf-8 -*-
"""Checklist empresarial de 10 puntos y comparaciones verificables.

No atribuye posiciones, ventas, backlinks, indexación ni métricas privadas sin acceso
del propietario. Solo compara indicadores realmente observables en las dos fechas.
"""
import datetime as dt
import unicodedata

STATUS = {"ok": "Señal encontrada", "issue": "Conviene revisar",
          "review": "Por confirmar"}

def _fold(text):
    return "".join(c for c in unicodedata.normalize("NFKD", str(text or "").casefold())
                   if not unicodedata.combining(c))

def _text(value, max_chars=150):
    return str(value or "")[:max_chars]

def _row(key, title, status, evidence, action, why, group="Diez puntos", effort="Sencillo"):
    return dict(id=key, title=title, status=status, status_label=STATUS[status],
                evidence=evidence, action=action, why=why, group=group, effort=effort,
                comparable=status!="review")

def checks(a, goal="contactos"):
    """Una misma metodología para el informe único y las revisiones mensuales."""
    rows=[]
    add=rows.append
    g="Diez puntos"
    add(_row("search_console", "1. ¿Google conoce tu página?",
        "review", "Search Console es una cuenta privada; no podemos saber si el sitio está registrado.",
        "Entra a Search Console con la cuenta de tu negocio. Añade y verifica la propiedad; consulta páginas indexadas y errores.",
        "Si Google no puede descubrir o indexar páginas importantes, podrías perder contactos."))

    sitemap=a.get("sitemap_hint")
    add(_row("sitemap", "2. ¿Google puede descubrir las páginas de tu sitio?",
        "ok" if sitemap else "review",
        ("Se encontró una referencia a un sitemap en esta página; no confirma su envío a Google."
         if sitemap else "No hay una referencia sitemap en el HTML analizado; podría existir en /sitemap.xml o robots.txt."),
        "Abre /sitemap.xml de tu dominio. Si existe y es correcto, envíalo desde Search Console y confirma su lectura.",
        "Un mapa del sitio ayuda a descubrir direcciones, pero no garantiza que Google las incluya."))

    tracking=a.get("analytics_signal")
    add(_row("analytics", "3. ¿Sabes cuántas personas te visitan?",
        "ok" if tracking else ("issue" if tracking is False else "review"),
        ("Encontramos una etiqueta de Google Analytics o Google Tag Manager; falta comprobar que envía datos."
         if tracking else "No detectamos etiquetas de Google en el HTML inicial; podrían cargarse con JavaScript."),
        "Abre Google Analytics 4 → Tiempo real. Visita tu web en otra pestaña y confirma que se registre la visita.",
        "Sin medir visitas y consultas es más difícil saber qué esfuerzos te funcionan."))

    business=a.get("google_profile_link")
    add(_row("business_profile", "4. ¿Te encuentran en Google Maps?",
        "ok" if business else "review",
        ("Detectamos un enlace hacia Google Maps o el Perfil de Empresa; no confirma que esté verificado."
         if business else "No vimos enlace a Google Maps. Aun así el negocio podría tener un perfil activo."),
        "Busca tu negocio en Google Maps y comprueba dirección, categoría, horarios, fotos, reseñas y vínculo al sitio.",
        "Para negocios locales, un perfil completo facilita recibir llamadas y solicitudes."))

    kw=_text(a.get("keyword"),75).strip()
    title=_text(a.get("title"),240)
    add(_row("keyword_title", "5. ¿Tu título dice lo que busca el cliente?",
        ("ok" if _fold(kw) in _fold(title) else "issue") if kw and title else "review",
        (("Frase objetivo: «"+kw+"». Título analizado: «"+_text(title,150)+"»." )
         if kw else "No proporcionaste la frase que quieres posicionar; no es correcto adivinarla."),
        "Escribe la frase específica por la que quieres que te encuentren. Si corresponde al negocio, úsala de forma natural en el título.",
        "Un título específico ayuda a explicar de qué trata cada página."))

    city=_text(a.get("city"),65).strip()
    on_page=a.get("city_in_page")
    add(_row("city", "6. ¿Mencionas la ciudad donde vendes?",
        ("ok" if on_page else "issue") if city and on_page is not None else "review",
        ("Ciudad objetivo: «"+city+"». "+("Encontrada" if on_page else "No encontrada")+" en el texto inicial de esta página.")
         if city else "No indicaste una ciudad objetivo; puede que tu servicio no necesite orientación local.",
        "Si atiendes en una ciudad concreta, explica en qué zonas trabajas en las páginas de servicio relevantes. Evita repetir nombres sin sentido.",
        "Las personas suelen buscar servicios cercanos o disponibles en su ciudad."))

    desc=a.get("description")
    add(_row("description", "7. ¿Tu página explica su oferta en Google?",
        ("ok" if desc else "issue") if desc is not None else "review",
        ("Esta página tiene una descripción ("+str(len(desc or ""))+
         " caracteres); no se comprobó si otras páginas usan la misma." if desc else
         "No encontramos meta description en la página analizada."),
        "Escribe una descripción clara de cada página importante. Revisa que las descripciones no sean idénticas entre páginas.",
        "Una descripción relevante ayuda a que el visitante entienda lo que ofreces antes de entrar."))

    internal=a.get("internal_links")
    add(_row("internal_links", "8. ¿Es fácil descubrir tus otros servicios?",
        ("ok" if internal>0 else "issue") if isinstance(internal,int) else "review",
        ("Encontramos "+str(internal)+" enlace(s) internos diferentes en el HTML de esta página."
         if internal is not None else "No se capturó este dato en la revisión anterior."),
        "Enlaza desde la página principal hacia servicios, productos, contacto o información útil; revisa que los enlaces funcionen.",
        "Si el cliente no encuentra otros servicios, puede abandonar sin pedir información."))

    modern=a.get("modern_images")
    images=a.get("images_total")
    missing_dims=a.get("images_without_dimensions")
    add(_row("images_speed", "9. ¿Tus fotos hacen lenta la página?",
        "ok" if isinstance(modern,int) and modern>0 else "review",
        ("Identificamos "+str(images)+" imágenes, "+str(modern)+" con formato WebP/AVIF y "+
         str(missing_dims)+" sin ancho y alto declarados. No medimos su peso ni los segundos de carga."
         if isinstance(modern,int) and isinstance(images,int) and isinstance(missing_dims,int)
         else "La revisión anterior no guardó los formatos de las imágenes."),
        "Pasa la URL por PageSpeed Insights. Comprime las imágenes grandes, usa WebP/AVIF si conviene y vuelve a medir en celular.",
        "Una página lenta puede hacer que un interesado se retire antes de contactar."))

    add(_row("backlinks", "10. ¿Otros sitios recomiendan tu negocio?",
        "review", "No analizamos el índice de enlaces externos de Google: sería incorrecto inventar backlinks.",
        "En Search Console entra a Enlaces → Sitios con más enlaces. Busca menciones legítimas en directorios relevantes, proveedores y aliados; evita comprar enlaces.",
        "Los enlaces de sitios confiables pueden ayudar a que otras personas descubran tu negocio."))

    extra="Además revisamos"
    noindex=a.get("noindex")
    add(_row("noindex", "¿Tu web permite aparecer en Google?",
        ("issue" if noindex else "ok") if noindex is not None else "review",
        "Encontramos noindex: "+("sí" if noindex else "no")+"; no confirma la indexación real."
          if noindex is not None else "Dato no disponible.",
        "Si la página debe ser pública y tiene noindex, consulta con tu desarrollador antes de cambiarlo.",
        "Un bloqueo noindex puede excluir tu página de resultados.", extra))
    viewport=a.get("viewport")
    add(_row("mobile", "¿Está preparada para celulares?",
        ("ok" if viewport else "issue") if viewport is not None else "review",
        "Etiqueta viewport "+("detectada" if viewport else "no detectada")+"; no equivale a una prueba visual."
          if viewport is not None else "Dato no disponible.",
        "Abre tu página en un celular: lee el texto, usa los botones y prueba formularios.",
        "Gran parte de los contactos se inicia desde el teléfono.", extra))
    h1=a.get("h1")
    add(_row("heading", "¿El encabezado principal comunica el servicio?",
        ("ok" if h1==1 else "issue") if isinstance(h1,int) else "review",
        "Se detectaron "+str(h1)+" encabezados principales H1." if h1 is not None else "Dato no disponible.",
        "Utiliza un encabezado principal claro que diga qué haces y para quién.",
        "El visitante debe entender en segundos si está en el lugar correcto.", extra))
    contact_goal={"ventas":"purchase","contactos":"contact","reservas":"booking",
                  "informacion":"contact"}.get(goal,"contact")
    signal=a.get(contact_goal)
    add(_row("action_path", "¿Se entiende cómo contratarte o contactarte?",
        ("ok" if signal else "issue") if signal is not None else "review",
        "Detectamos una ruta reconocible para "+{"purchase":"comprar o cotizar","contact":"contactar",
              "booking":"reservar"}.get(contact_goal,"contactar")+": "+("sí" if signal else "no")+
              ". Los botones creados por JavaScript pueden no aparecer aquí."
              if signal is not None else "Dato no disponible.",
        "Comprueba que el botón de contacto, cotización o reserva sea visible en celular y que funcione de principio a fin.",
        "Si el siguiente paso no es claro, puedes perder consultas interesadas.", extra))
    return rows


def overview(a,goal="contactos"):
    rows=checks(a,goal)
    return {
        "checks": rows,
        "ok": sum(r["status"]=="ok" for r in rows),
        "issue": sum(r["status"]=="issue" for r in rows),
        "review": sum(r["status"]=="review" for r in rows),
        "actionable": [r for r in rows if r["status"]=="issue"]+
                      [r for r in rows if r["status"]=="review"],
    }


def progress(baseline,current,goal="contactos"):
    old={r["id"]:r for r in checks(baseline,goal)}
    new={r["id"]:r for r in checks(current,goal)}
    shared=[k for k in old if old[k]["comparable"] and new[k]["comparable"]]
    start=sum(old[k]["status"]=="ok" for k in shared)
    end=sum(new[k]["status"]=="ok" for k in shared)
    improved=[new[k] for k in shared if old[k]["status"]=="issue" and new[k]["status"]=="ok"]
    to_fix=[new[k] for k in shared if old[k]["status"]=="ok" and new[k]["status"]=="issue"]
    return {
        "start":start, "end":end, "total":len(shared),
        "start_pct":round(start*100/len(shared)) if shared else 0,
        "end_pct":round(end*100/len(shared)) if shared else 0,
        "improved":improved,"regressed":to_fix,
        "start_label":_text(baseline.get("checked"),30),
        "end_label":_text(current.get("checked"),30),
        "same_date": baseline.get("checked")==current.get("checked"),
    }


def checklist_snapshot(a,goal="contactos"):
    """For a compact chart, count only observable signals (not an SEO score)."""
    result=overview(a,goal)
    measured=result["ok"]+result["issue"]
    return {"ok":result["ok"],"issue":result["issue"],
            "measured":measured,"review":result["review"]}


def history_progress(baseline,history,goal):
    result=[]
    for row in [{"month":"Inicio","audit":baseline}]+list(history):
        c=progress(baseline,row["audit"],goal)
        result.append({"month":row["month"],"ok":c["end"],"total":c["total"],
                       "pct":c["end_pct"]})
    return result
