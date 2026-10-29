# -*- coding: utf-8 -*-
"""GUI portátil de Stripe cargos ficticios (Windows).

Se instala exclusivamente en:
C:\procesos python\Revisar metricas web\versiones\Stripe cargos ficticios

Utiliza la MISMA lógica del diagnóstico público para probar los dos Checkout
en Stripe Test (cs_test_), regreso, PDF y panel. NUNCA captura datos de tarjeta:
el cliente solo teclea los datos de prueba en checkout.stripe.com.

En el primer uso se necesita la clave de PRUEBAS sk_test_, que queda cifrada
mediante DPAPI del usuario Windows junto al ejecutable. En ejecuciones siguientes
solo se selecciona plan y se introduce tarjeta ficticia en Stripe.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
import re
from pathlib import Path
import socket
import sys
import threading
import urllib.parse
import webbrowser

import requests

PORT = 8876
HOST = "127.0.0.1"
ORIGIN = "http://127.0.0.1:8876"
SITE = "https://converte.uno/"
LOOKUPS = (
    ("diagnostico_web_test_informe_387_v1", "Diagnóstico Web - Informe completo (PRUEBA)", 38700, False),
    ("diagnostico_web_test_seguimiento_597_v1", "Diagnóstico Web - Seguimiento mensual (PRUEBA)", 59700, True),
)


def application_folder() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def template_folder() -> Path:
    root = Path(getattr(sys, "_MEIPASS", application_folder()))
    return root / "templates"


def protected_key_file() -> Path:
    return application_folder() / "clave_stripe_test.dpapi"


def _crypt(data: bytes, encrypt: bool) -> bytes:
    """Windows DPAPI: secret encrypted to the currently logged-in account."""
    if sys.platform != "win32":
        raise RuntimeError("Esta herramienta está preparada exclusivamente para Windows.")
    class BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD),
                    ("pbData", ctypes.POINTER(ctypes.c_ubyte))]
    source = ctypes.create_string_buffer(data)
    inp = BLOB(len(data), ctypes.cast(source, ctypes.POINTER(ctypes.c_ubyte)))
    out = BLOB()
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    localfree = ctypes.WinDLL("kernel32", use_last_error=True).LocalFree
    localfree.argtypes = [ctypes.c_void_p]
    localfree.restype = ctypes.c_void_p
    if encrypt:
        method = crypt32.CryptProtectData
        method.argtypes = [ctypes.POINTER(BLOB), wintypes.LPCWSTR,
                           ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                           wintypes.DWORD, ctypes.POINTER(BLOB)]
        ok = method(ctypes.byref(inp), "Stripe Test solo este usuario",
                    None, None, None, 1, ctypes.byref(out))
    else:
        method = crypt32.CryptUnprotectData
        method.argtypes = [ctypes.POINTER(BLOB), ctypes.c_void_p,
                           ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                           wintypes.DWORD, ctypes.POINTER(BLOB)]
        ok = method(ctypes.byref(inp), None, None, None, None, 1, ctypes.byref(out))
    if not ok:
        raise OSError(ctypes.get_last_error(), "Windows no pudo proteger o recuperar la clave.")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        localfree(ctypes.cast(out.pbData, ctypes.c_void_p))


def read_key() -> str | None:
    f = protected_key_file()
    if not f.exists():
        return None
    value = _crypt(f.read_bytes(), encrypt=False).decode("utf-8")
    if not value.startswith("sk_test_"):
        raise ValueError("La clave guardada no es una clave Stripe de pruebas.")
    return value


def save_key(key: str):
    if not key.startswith("sk_test_"):
        raise ValueError("Solo se permite sk_test_ de Stripe, jamás sk_live_.")
    destination = protected_key_file()
    destination.write_bytes(_crypt(key.encode("utf-8"), encrypt=True))


def test_price(key: str, lookup: str, name: str, amount: int, monthly: bool) -> str:
    """Crea o reutiliza los precios, SOLO mediante clave test."""
    if not key.startswith("sk_test_"):
        raise ValueError("La clave no pertenece a Stripe de pruebas.")
    auth = (key, "")
    response = requests.get(
        "https://api.stripe.com/v1/prices",
        params={"lookup_keys[]": lookup},
        auth=auth, timeout=22,
    )
    response.raise_for_status()
    existing = response.json().get("data") or []
    if existing:
        price = existing[0]
    else:
        args = {
            "currency": "mxn",
            "unit_amount": amount,
            "product_data[name]": name,
            "lookup_key": lookup,
            "nickname": "PRUEBA SIN COBRO",
        }
        if monthly:
            args["recurring[interval]"] = "month"
        created = requests.post(
            "https://api.stripe.com/v1/prices",
            data=args, auth=auth, timeout=22,
        )
        created.raise_for_status()
        price = created.json()
    if (price.get("livemode") is not False
        or price.get("active") is not True
        or price.get("unit_amount") != amount
        or price.get("currency") != "mxn"
        or bool((price.get("recurring") or {}).get("interval") == "month") is not monthly
        or not re.fullmatch(r"price_[A-Za-z0-9]{8,120}", price.get("id", ""))):
        raise ValueError("El precio de prueba no coincide con la modalidad o el importe.")
    return price["id"]


def build_app():
    from flask import Flask, abort, request, render_template_string
    from herramientas import diagnostico_web
    app = Flask("converte_stripe_test_gui", template_folder=str(template_folder()))
    app.register_blueprint(diagnostico_web.bp)

    @app.before_request
    def host_is_local():
        if request.host not in ("127.0.0.1:8876", "localhost:8876"):
            abort(403)
        if request.remote_addr not in ("127.0.0.1", "::1"):
            abort(403)
        origin = request.headers.get("Origin")
        if request.method == "POST" and origin and origin != ORIGIN:
            abort(403)

    @app.get("/prueba/<plan>")
    def test_plan(plan):
        if plan not in ("informe", "mensual"):
            abort(404)
        # A normal browser form posts the default public URL into the SAME
        # Converte diagnostic engine used in production.
        target = "/diagnostico-web/comprar" if plan == "informe" else "/diagnostico-web/suscribir"
        return render_template_string(
            """<!doctype html><html lang="es"><head><meta charset="utf-8">
            <meta name="viewport" content="width=device-width,initial-scale=1">
            <title>Stripe · Preparando la compra ficticia</title>
            <style>body{font:16px system-ui;background:#f4f8f7;color:#17414a;
            min-height:100vh;display:grid;place-items:center}main{max-width:430px;
            padding:30px;background:white;border-radius:13px;text-align:center}
            button{background:#116e76;color:white;border:0;padding:12px 22px;
            border-radius:8px;font:inherit;cursor:pointer}</style>
            </head><body><main><h2>Prueba sin dinero real</h2>
            <p>Se abrirá Stripe para completar un pago de prueba.
            Escribe la tarjeta ficticia solamente en Stripe.</p>
            <form action="{{target}}" method="post" id="stripeform">
             <input type="hidden" name="url" value="{{site}}">
             <input type="hidden" name="objetivo" value="ventas">
             <button type="submit">Abrir el pago de prueba</button>
            </form>
            <p id="message">Preparando Stripe...</p></main>
            <script>document.getElementById('stripeform').submit();</script>
            </body></html>""", target=target, site=SITE,
        )
    return app


class GUI:
    def __init__(self):
        import tkinter as tk
        from tkinter import ttk
        self.tk = tk
        self.ttk = ttk
        self.window = tk.Tk()
        self.window.title("Stripe cargos ficticios — Diagnóstico Web")
        self.window.geometry("525x405")
        self.window.minsize(500, 390)
        self.window.configure(bg="#f5f8f7")
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.server = None
        self.ready = False
        self.loading = False
        self.key = None
        self.setup_ui()
        self.window.after(180, self.bootstrap)

    def setup_ui(self):
        tk = self.tk
        frame = tk.Frame(self.window, bg="#f5f8f7", padx=23, pady=19)
        frame.pack(fill="both", expand=True)
        tk.Label(frame, text="STRIPE · CARGOS FICTICIOS", bg="#f5f8f7",
                 fg="#16716d", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        tk.Label(frame, text="Prueba lo que recibe el cliente",
                 bg="#f5f8f7", fg="#193b43",
                 font=("Segoe UI", 17, "bold")).pack(anchor="w", pady=(6, 10))
        tk.Label(frame,
                 text="No se cobra dinero. Los datos de la tarjeta se escriben en\n"
                      "la pantalla oficial de Stripe, nunca en esta herramienta.",
                 bg="#f5f8f7", fg="#4e6c70", justify="left",
                 font=("Segoe UI", 10)).pack(anchor="w", pady=(0, 13))
        self.one = tk.Button(frame,
                 text="PROBAR INFORME ÚNICO — $387 MXN",
                 bg="#116e76", fg="white", activebackground="#0b5158",
                 font=("Segoe UI", 11, "bold"), relief="flat",
                 padx=14, pady=11, cursor="hand2", command=lambda:self.open_plan("informe"))
        self.one.pack(fill="x", pady=4)
        self.month = tk.Button(frame,
                 text="PROBAR SEGUIMIENTO — $597 MXN/MES",
                 bg="#116e76", fg="white", activebackground="#0b5158",
                 font=("Segoe UI", 11, "bold"), relief="flat",
                 padx=14, pady=11, cursor="hand2", command=lambda:self.open_plan("mensual"))
        self.month.pack(fill="x", pady=4)
        tk.Label(frame, text="Tarjeta de prueba: 4242 4242 4242 4242  |  12/34  |  123",
                 bg="#f5f8f7", fg="#173b42",
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(14, 7))
        self.status = tk.StringVar(value="Inicializando entorno protegido...")
        tk.Label(frame, textvariable=self.status, bg="#f5f8f7", fg="#476d72",
                 font=("Segoe UI", 9), wraplength=475, justify="left").pack(anchor="w")
        tk.Button(frame, text="Cambiar clave de pruebas", relief="flat",
                  bg="#f5f8f7", fg="#376e75", underline=0, cursor="hand2",
                  command=self.reset_key).pack(anchor="w", pady=(9, 0))
        self.one.config(state="disabled")
        self.month.config(state="disabled")

    def bootstrap(self):
        from tkinter import simpledialog, messagebox
        try:
            self.key = read_key()
        except (ValueError, OSError) as error:
            # On key recovery failure, require a fresh test key.
            messagebox.showwarning("Stripe de pruebas", "No se pudo recuperar la clave anterior:\n"+str(error))
            self.key = None
        if not self.key:
            key = simpledialog.askstring(
                "Primera configuración (una sola vez)",
                "Para probar pagos verdaderos sin dinero necesitas la CLAVE DE PRUEBA\n"
                "de Stripe (sk_test_...). Se guardará cifrada en esta carpeta y\n"
                "solo se usa para crear cobros ficticios.\n\n"
                "Esta clave NO es un número de tarjeta. Nunca uses sk_live_.",
                parent=self.window, show="*",
            )
            if key is None:
                self.status.set("Falta vincular Stripe de pruebas. Ningún pago fue iniciado.")
                return
            self.key = key.strip()
        if not self.key.startswith("sk_test_"):
            messagebox.showerror("Clave no permitida", "Solo se admiten claves secretas de prueba sk_test_.")
            self.key = None
            return
        self.one.config(state="disabled")
        self.month.config(state="disabled")
        self.status.set("Preparando los dos planes de prueba en Stripe...")
        threading.Thread(target=self.start_server, daemon=True).start()

    def start_server(self):
        try:
            import tkinter as tk
            from werkzeug.serving import make_server
            report, monthly = [test_price(self.key, *row) for row in LOOKUPS]
            os.environ.update({
                "RENDER": "",
                "DIAGNOSTICO_STRIPE_MODE": "test",
                "DIAGNOSTICO_PRUEBA_SIN_COBRO": "1",
                "DIAGNOSTICO_TEST_ORIGIN": ORIGIN,
                "DIAGNOSTICO_STRIPE_SECRET_KEY": self.key,
                "DIAGNOSTICO_STRIPE_TEST_PRICE_ID": report,
                "DIAGNOSTICO_STRIPE_TEST_MONTHLY_PRICE_ID": monthly,
                "DIAGNOSTICO_PAGOS_ACTIVOS": "1",
                "DIAGNOSTICO_SUSCRIPCIONES_ACTIVAS": "1",
                "DIAGNOSTICO_PRICE_LABEL": "$387 MXN",
            })
            from herramientas import diagnostico_web as dw
            if not (dw.stripe_ready() and dw.subscriptions_enabled()):
                raise RuntimeError("Stripe no pudo autorizar los precios de prueba.")
            self.server = make_server(HOST, PORT, build_app(), threaded=True)
            save_key(self.key)  # Only after both test prices validated
            self.server.serve_forever()
        except Exception as e:
            self.window.after(0, lambda error=str(e): self.fail(error))
        else:
            pass

    def enable_if_started(self):
        if self.server:
            self.ready = True
            self.one.config(state="normal")
            self.month.config(state="normal")
            self.status.set("Modo de PRUEBA listo. Elige un paquete; la tarjeta se ingresa en Stripe.")
        else:
            self.window.after(350, self.enable_if_started)

    def fail(self, error):
        from tkinter import messagebox
        self.one.config(state="disabled")
        self.month.config(state="disabled")
        self.status.set("Error al preparar el entorno de prueba.")
        messagebox.showerror("No se pudo iniciar Stripe de pruebas", error)

    def open_plan(self, plan):
        from tkinter import messagebox
        if not self.server:
            messagebox.showwarning("No disponible", "Todavía no ha terminado de iniciarse la prueba.")
            return
        webbrowser.open(ORIGIN+"/prueba/"+plan)

    def reset_key(self):
        from tkinter import messagebox
        if self.server:
            messagebox.showinfo("Cambiar clave",
                                "Cierra el programa y vuelve a abrirlo para cambiar de clave.")
            return
        f = protected_key_file()
        if f.exists():
            f.unlink()
        self.key = None
        self.bootstrap()

    def close(self):
        if self.server:
            # The local server thread is a daemon and terminates with the GUI.
            threading.Thread(target=self.server.shutdown, daemon=True).start()
        self.window.destroy()


def main():
    if "--self-test" in sys.argv:
        assert template_folder().joinpath("diagnostico_web.html").exists()
        assert template_folder().joinpath("diagnostico_seguimiento.html").exists()
        assert template_folder().joinpath("diagnostico_checkout.html").exists()
        app = build_app()
        assert "/diagnostico-web/comprar" in [r.rule for r in app.url_map.iter_rules()]
        assert "/diagnostico-web/suscribir" in [r.rule for r in app.url_map.iter_rules()]
        return
    if sys.platform != "win32":
        raise SystemExit("El ejecutable está preparado para Windows.")
    GUI_instance = GUI()
    GUI_instance.window.after(350, GUI_instance.enable_if_started)
    GUI_instance.window.mainloop()


if __name__ == "__main__":
    main()
