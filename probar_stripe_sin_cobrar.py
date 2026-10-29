# -*- coding: utf-8 -*-
"""Arranque seguro de la misma app de Converte con Stripe Test Checkout.

Un solo dato secreto ingresado de forma privada. Crea/reutiliza precios SOLO
en el sandbox (nunca en producción), sin guardar claves en disco o en GitHub.
"""
import getpass
import os
import re
import sys
import webbrowser

import requests

URL = "http://127.0.0.1:8876/diagnostico-web/"
PRICE_DEFINITIONS = (
    ("diagnostico_web_test_informe_387_v1", "Diagnóstico Web - Informe completo (prueba)",
     38700, False),
    ("diagnostico_web_test_seguimiento_597_v1", "Diagnóstico Web - Seguimiento mensual (prueba)",
     59700, True),
)


def valid_price(result, amount, recurring):
    return (
        isinstance(result, dict)
        and result.get("livemode") is False
        and result.get("currency") == "mxn"
        and result.get("unit_amount") == amount
        and result.get("active") is True
        and bool((result.get("recurring") or {}).get("interval") == "month") is recurring
        and isinstance(result.get("id"), str)
        and re.fullmatch(r"price_[A-Za-z0-9]{8,120}", result["id"]) is not None
    )


def test_price(key, lookup, label, amount, monthly):
    """Reutiliza el mismo precio de sandbox; lo crea si aún no existe."""
    auth = (key, "")
    response = requests.get("https://api.stripe.com/v1/prices",
                            auth=auth, params={"lookup_keys[]": lookup},
                            timeout=20)
    response.raise_for_status()
    matches = response.json().get("data", [])
    if matches:
        price = matches[0]
    else:
        payload = {
            "currency": "mxn",
            "unit_amount": amount,
            "product_data[name]": label,
            "lookup_key": lookup,
            "nickname": "EXCLUSIVO PARA PRUEBAS - NO COBRA DINERO REAL",
        }
        if monthly:
            payload["recurring[interval]"] = "month"
        created = requests.post("https://api.stripe.com/v1/prices",
                                auth=auth, data=payload, timeout=20)
        created.raise_for_status()
        price = created.json()
    if not valid_price(price, amount, monthly):
        raise ValueError("El precio de prueba no coincide con la moneda o importe esperado.")
    return price["id"]


def main():
    if os.environ.get("RENDER", "").lower() == "true":
        raise SystemExit("Las pruebas sin cobro están bloqueadas en Render.")
    print("\nDIAGNOSTICO WEB: PRUEBA DE STRIPE SIN COBROS REALES")
    print("Se usa la MISMA aplicación, aislada en tu PC.")
    print("No escribas ninguna clave de produccion ni datos de tarjetas reales.")
    key = getpass.getpass("\nClave SECRETA de Stripe TEST (sk_test_...): ").strip()
    if not key.startswith("sk_test_"):
        raise ValueError("Se requiere una clave sk_test_ del entorno de pruebas.")

    print("\nPreparando automáticamente los precios de prueba de 387 y 597 MXN...")
    report, monthly = [
        test_price(key, lookup, label, amount, recurrent)
        for lookup, label, amount, recurrent in PRICE_DEFINITIONS
    ]
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
        raise RuntimeError("No se habilitó la prueba: revisar las claves de Stripe.")

    print("\nAbriendo", URL)
    print("1) Prueba el informe único por 387 MXN (dinero ficticio).")
    print("2) Prueba el plan mensual de 597 MXN: panel, nueva revisión y PDF.")
    print("Tarjeta de prueba: 4242 4242 4242 4242; caducidad 12/34; CVC 123.")
    print("Usa SOLO datos de prueba. Cierra con Ctrl+C cuando termines.\n")
    webbrowser.open(URL)
    app.run(host="127.0.0.1", port=8876, debug=False, use_reloader=False)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, requests.RequestException) as error:
        print("\nERROR EN LA PRUEBA:", error, file=sys.stderr)
        raise SystemExit(1)
