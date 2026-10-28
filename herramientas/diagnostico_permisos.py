# -*- coding: utf-8 -*-
"""Comprobación de permisos Stripe para seguimiento.

Únicamente comprueba permisos. No crea ni modifica ninguna suscripción real.
Devuelve códigos HTTP, nunca datos de clientes ni credenciales.
"""
import secrets
import requests


def check_restricted_key(key, base="https://api.stripe.com/v1"):
    result = {"read": None, "write": None, "write_result": None}
    if not key or not key.startswith(("rk_live_", "sk_live_")):
        return result
    auth = (key, "")
    try:
        resp = requests.get(base + "/subscriptions",
                            params={"limit": 1}, auth=auth, timeout=8)
        result["read"] = resp.status_code
        if resp.status_code != 200:
            return result
        # Usar un identificador irreal y aleatorio asegura que
        # NO se modifique ninguna suscripción existente.
        fake_id = "sub_" + secrets.token_hex(24)
        response = requests.post(
            base + "/subscriptions/" + fake_id,
            auth=auth, timeout=8,
            data={"metadata[permission_probe]": "1"})
        result["write"] = response.status_code
        if response.status_code == 404:
            body = response.json()
            result["write_result"] = (body.get("error") or {}).get("code", "unknown")
    except (requests.RequestException, ValueError):
        pass
    return result


def permissions_verified(status):
    """200 lectura y 404 recurso inexistente demuestra autorización de escritura.

    No debe considerarse válida una falla 403, una red interrumpida o un 400 ambiguo.
    """
    return (status.get("read") == 200 and status.get("write") == 404
            and status.get("write_result") == "resource_missing")
