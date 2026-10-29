"""Stripe Test Checkout: aislamiento de produccion y entrega realista sin cobro.

No llama a Stripe de produccion ni usa claves reales. El recorrido manual con
Checkout de Stripe test requiere claves y precios test del propietario.
"""
import os
import unittest
from unittest.mock import Mock, patch

from app import app
from herramientas import diagnostico_web as dw
from herramientas import diagnostico_seguimiento as monitor

KEY = "sk_test_mock_no_live"
TEST_PRICE = "price_testReport387abc"
TEST_MONTHLY = "price_testMonthly597xyz"
ORIGIN = "http://127.0.0.1:8876"
SID = "cs_test_" + "A" * 25
MONTH_SID = "cs_test_" + "B" * 25
SUB = "sub_" + "S" * 25
PAGE = ("<!doctype html><html><head><title>Panadería de ejemplo</title>"
        "<meta name='description' content='Pan para todos'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "</head><body><h1>Panadería artesanal</h1>"
        "<a href='tel:12345678'>Llámanos</a><a href='/servicios'>Servicios</a></body></html>")
ENV = {
    "RENDER": "",
    "DIAGNOSTICO_STRIPE_MODE": "test",
    "DIAGNOSTICO_PRUEBA_SIN_COBRO": "1",
    "DIAGNOSTICO_TEST_ORIGIN": ORIGIN,
    "DIAGNOSTICO_STRIPE_SECRET_KEY": KEY,
    "DIAGNOSTICO_STRIPE_TEST_PRICE_ID": TEST_PRICE,
    "DIAGNOSTICO_STRIPE_TEST_MONTHLY_PRICE_ID": TEST_MONTHLY,
    "DIAGNOSTICO_PAGOS_ACTIVOS": "1",
    "DIAGNOSTICO_SUSCRIPCIONES_ACTIVAS": "1",
    "DIAGNOSTICO_PRICE_LABEL": "$387 MXN",
}


def reply(payload):
    obj = Mock()
    obj.raise_for_status.return_value = None
    obj.json.return_value = payload
    return obj


class StripeSandboxTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        dw._cache.clear()
        dw._payment_ip.clear()

    def test_isolation_requires_explicit_mode_flag_localhost_and_test_keys(self):
        with patch.dict(os.environ, ENV):
            self.assertTrue(dw.stripe_ready())
            self.assertTrue(dw.payments_enabled())
            self.assertTrue(dw.subscriptions_enabled())
            self.assertTrue(dw.stripe_session_valid(SID))
            self.assertFalse(dw.stripe_session_valid("cs_live_" + "A"*25))
            self.assertEqual(dw.report_price_id(), TEST_PRICE)
            self.assertEqual(dw.monthly_price_id(), TEST_MONTHLY)
        for forbidden in (
            {"DIAGNOSTICO_PRUEBA_SIN_COBRO": "0"},
            {"RENDER": "true"},
            {"DIAGNOSTICO_TEST_ORIGIN": "https://converte.uno"},
            {"DIAGNOSTICO_STRIPE_SECRET_KEY": "rk_live_secret_example"},
        ):
            with patch.dict(os.environ, {**ENV, **forbidden}):
                self.assertFalse(dw.stripe_ready())
                self.assertFalse(dw.payments_enabled())
                self.assertFalse(dw.subscriptions_enabled())
        with patch.dict(os.environ, {**ENV, "DIAGNOSTICO_STRIPE_MODE":"live"}):
            self.assertFalse(dw.stripe_ready())
            self.assertFalse(dw.stripe_session_valid(SID))

    def test_one_time_387_test_checkout_then_paid_pdf(self):
        created = {}
        def fake_checkout(url, **kwargs):
            self.assertEqual(url, "https://api.stripe.com/v1/checkout/sessions")
            created.update(kwargs["data"])
            return reply({"url":"https://checkout.stripe.com/c/pay/demo"})
        with patch.dict(os.environ, ENV), patch.object(dw,"fetch_html",
                 return_value=("https://example.com/",PAGE,{})),patch(
                 "requests.post",side_effect=fake_checkout):
            response=self.client.post("/diagnostico-web/comprar",data={
                "url":"https://example.com/","objetivo":"contactos"
            })
        self.assertEqual(response.status_code,200)
        self.assertEqual(created["line_items[0][price]"],TEST_PRICE)
        self.assertEqual(created["mode"],"payment")
        self.assertEqual(created["success_url"],
             ORIGIN+"/diagnostico-web/informe?session_id={CHECKOUT_SESSION_ID}")
        self.assertEqual(created["cancel_url"],ORIGIN+"/diagnostico-web/")
        metadata = {
           k[len("metadata["):-1]: v
           for k,v in created.items() if k.startswith("metadata[")
        }
        session={
            "id":SID,"livemode":False,"mode":"payment","status":"complete",
            "payment_status":"paid","currency":"mxn","amount_total":38700,
            "metadata":metadata
        }
        lines={"data":[{"price":{"id":TEST_PRICE},"amount_total":38700,"quantity":1}]}
        def fake_read(url,**kwargs):
            return reply(lines if url.endswith("/line_items") else session)
        with patch.dict(os.environ, ENV),patch("requests.get",side_effect=fake_read),patch.object(
                dw,"fetch_html",side_effect=RuntimeError("Site offline")):
            landing=self.client.get("/diagnostico-web/informe?session_id="+SID)
            pdf=self.client.get("/diagnostico-web/descargar?session_id="+SID)
        self.assertEqual(landing.status_code,200)
        self.assertIn("Pago confirmado por Stripe".encode(),landing.data)
        self.assertIn("MODO DE PRUEBA".encode(),landing.data)
        self.assertEqual(pdf.status_code,200)
        self.assertTrue(pdf.data.startswith(b"%PDF-"))
        self.assertGreater(len(pdf.data),2500)
        self.assertIn("attachment",pdf.headers["Content-Disposition"])

        # Stripe test must not accept the ID or credit from live mode.
        session["livemode"]=True
        with patch.dict(os.environ, ENV),patch("requests.get",side_effect=fake_read):
            bad=self.client.get("/diagnostico-web/descargar?session_id="+SID)
        self.assertEqual(bad.status_code,403)

    def test_monthly_597_test_checkout_panel_new_audit_and_pdf(self):
        created = {}
        def fake_checkout(url,**kwargs):
            created.update(kwargs["data"])
            return reply({"url":"https://checkout.stripe.com/c/pay/demo"})
        with patch.dict(os.environ,ENV),patch.object(dw,"fetch_html",
                return_value=("https://example.com/",PAGE,{})),patch("requests.post",
                side_effect=fake_checkout):
            checkout=self.client.post("/diagnostico-web/suscribir",data={
                "url":"https://example.com/","objetivo":"contactos"
            })
        self.assertEqual(checkout.status_code,200)
        self.assertEqual(created["mode"],"subscription")
        self.assertEqual(created["line_items[0][price]"],TEST_MONTHLY)
        self.assertEqual(created["success_url"],ORIGIN+
              "/diagnostico-web/seguimiento?session_id={CHECKOUT_SESSION_ID}")
        base_meta={
            k[len("subscription_data[metadata]["):-1]:v
            for k,v in created.items() if k.startswith("subscription_data[metadata][")
        }
        sess={
            "id":MONTH_SID,"livemode":False,"mode":"subscription",
            "status":"complete","payment_status":"paid","currency":"mxn",
            "amount_total":59700,
            "metadata":{"service":"diagnostico-web-seguimiento"},
            "subscription":SUB,
        }
        sub={
            "id":SUB,"livemode":False,"status":"active",
            "metadata":base_meta,
            "items":{"data":[{"quantity":1,"price":{"id":TEST_MONTHLY}}]},
        }
        def stripe(method,path,fields=None):
            if method=="GET" and path=="checkout/sessions/"+MONTH_SID:
                return sess
            if method=="GET" and path=="subscriptions/"+SUB:
                return sub
            if method=="POST" and path=="subscriptions/"+SUB:
                for k,v in fields.items():
                    name=k[len("metadata["):-1]
                    if v: sub["metadata"][name]=v
                    else: sub["metadata"].pop(name,None)
                return sub
            raise AssertionError("unexpected simulated Stripe API: "+method+" "+path)

        with patch.dict(os.environ,ENV),patch.object(dw,"_billing_request",side_effect=stripe):
            first=self.client.get("/diagnostico-web/seguimiento?session_id="+MONTH_SID)
        self.assertEqual(first.status_code,200)
        self.assertIn("MODO DE PRUEBA".encode(),first.data)
        self.assertIn("Tu próximo paso".encode(),first.data)

        with patch.dict(os.environ,ENV),patch.object(dw,"_billing_request",side_effect=stripe),patch.object(
            dw,"fetch_html",return_value=("https://example.com/",PAGE.replace(
                  "Panadería artesanal","Panadería artesanal en Puebla"),{})):
            after=self.client.post("/diagnostico-web/seguimiento/revisar",
                                   data={"session_id":MONTH_SID})
            pdf=self.client.get("/diagnostico-web/seguimiento/descargar?session_id="+MONTH_SID)
        self.assertEqual(after.status_code,200)
        self.assertEqual(pdf.status_code,200)
        self.assertTrue(pdf.data.startswith(b"%PDF-"))
        self.assertEqual(len(monitor.history(sub["metadata"])),1)

        sub["status"]="canceled"
        with patch.dict(os.environ,ENV),patch.object(dw,"_billing_request",side_effect=stripe):
            deny=self.client.get("/diagnostico-web/seguimiento/descargar?session_id="+MONTH_SID)
        self.assertEqual(deny.status_code,403)

    def test_sandbox_paywall_does_not_accept_forged_paid_flag(self):
        with patch.dict(os.environ,ENV):
            self.assertEqual(self.client.get("/diagnostico-web/descargar?session_id="+SID).status_code,503)
            self.assertEqual(self.client.get("/diagnostico-web/informe?session_id=cs_live_"+"L"*24).status_code,404)


if __name__=="__main__":
    unittest.main()
