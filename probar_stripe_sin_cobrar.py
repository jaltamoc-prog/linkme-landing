# -*- coding: utf-8 -*-
"""Punto de arranque local: Stripe real en TEST mode, sin cobrar.

No guarda claves en disco, no habilita rutas de prueba en Render y nunca
modifica los identificadores del ambiente live de converte.uno.
"""
import getpass
import os
import re
import sys
import webbrowser

URL = "http://127.0.0.1:8876/diagnostico-web/"


def ask_price(label):
    value = input(label + " (price_...): ").strip()
    if not re.fullmatch(r"price_[A-Za-z0-9]{8,120}", value):
        raise ValueError("El identificador del precio de pruebas no es válido.")
    return value


def main():
    if os.environ.get("RENDER", "").lower() == "true":
        raise SystemExit("Por seguridad no se permite iniciar esta prueba desde Render.")
    print("\nDiagnostico Web - PRUEBA REAL DE CHECKOUT SIN DINERO")
    print("Se usa la misma aplicacion Flask, pero una cuenta de pruebas separada.")
    print("No escribas claves de produccion, numeros de tarjeta reales ni datos personales.\n")
    key = getpass.getpass("Clave Stripe de PRUEBA (sk_test_... o rk_test_...): ").strip()
    if not key.startswith(("sk_test_", "rk_test_")):
        raise ValueError("Solo se acepta una clave de Stripe de PRUEBAS.")
    report = ask_price("Precio de prueba para informe UNICO de 387 MXN")
    monthly = ask_price("Precio de prueba para seguimiento MENSUAL de 597 MXN")

    # Las claves de prueba quedan solo en la memoria de este proceso.
    os.environ.update({
        "DIAGNOSTICO_STRIPE_MODE": "test",
        "DIAGNOSTICO_PRUEBA_SIN_COBRO": "1",
        "DIAGNOSTICO_TEST_ORIGIN": "http://127.0.0.1:8876",
        "DIAGNOSTICO_STRIPE_SECRET_KEY": key,
        "DIAGNOSTICO_STRIPE_TEST_PRICE_ID": report,
        "DIAGNOSTICO_STRIPE_TEST_MONTHLY_PRICE_ID": monthly,
        "DIAGNOSTICO_PRICE_LABEL": "$387 MXN",
        "DIAGNOSTICO_PAGOS_ACTIVOS": "1",
        "DIAGNOSTICO_SUSCRIPCIONES_ACTIVAS": "1",
    })
    from app import app
    from herramientas import diagnostico_web as audit
    if not audit.stripe_ready() or not audit.subscriptions_enabled():
        raise RuntimeError("El entorno de prueba no superó la verificación de seguridad.")

    print("\nAbriendo " + URL)
    print("Prueba primero el pago de 387 y descarga el PDF.")
    print("Después prueba la suscripción de 597, su panel, la revisión y PDF.")
    print("Toda tarjeta utilizada DEBE ser de prueba, nunca una tarjeta real.")
    print("Cierra el proceso con Ctrl+C al terminar.\n")
    webbrowser.open(URL)
    app.run(host="127.0.0.1", port=8876, debug=False, use_reloader=False)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError) as error:
        print("\nERROR:", error, file=sys.stderr)
        raise SystemExit(1)
