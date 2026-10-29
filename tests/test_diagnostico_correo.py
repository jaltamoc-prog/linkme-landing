"""Pruebas de entrega por email: PDF real, webhook firmado, nunca cargos ni correos reales."""
import base64
import hashlib
import hmac
import json
import os
import time
import unittest
from unittest.mock import Mock, patch
from io import BytesIO

from app import app
from herramientas import diagnostico_correo as mail
from herramientas import diagnostico_web as dw
from herramientas import diagnostico_seguimiento as mon

HTML = """<!doctype html><html><head><title>Panadería artesanal</title>
<meta name="description" content="Pan artesanal y pasteles"></head>
<body><h1>Panadería artesanal</h1><a href="tel:5551234">Llámanos</a></body></html>"""
SID = "cs_live_" + "R" * 26
MSID = "cs_live_" + "S" * 26
SUB = "sub_" + "Q" * 26
ENV = {
    "DIAGNOSTICO_STRIPE_MODE": "live",
    "DIAGNOSTICO_STRIPE_SECRET_KEY": "rk_live_mock_email_not_real",
    "DIAGNOSTICO_STRIPE_PRICE_ID": dw.REPORT_PRICE_ID,
    "DIAGNOSTICO_STRIPE_MONTHLY_PRICE_ID": mon.PRICE_ID,
    "DIAGNOSTICO_PAGOS_ACTIVOS": "1",
    "DIAGNOSTICO_SUSCRIPCIONES_ACTIVAS": "1",
    "DIAGNOSTICO_PRICE_LABEL": "$387 MXN",
    "DIAGNOSTICO_STRIPE_WEBHOOK_SECRET": "whsec_mock_unique_secret",
    "DIAGNOSTICO_RESEND_API_KEY": "re_mock_not_real",
    "DIAGNOSTICO_CORREO_REMITENTE": "informes@example.com",
}
HEADERS = {"Content-Type": "application/json"}
CUSTOMER = "cliente@example.com"


def demo_audit():
    with patch.object(dw, "fetch_html", return_value=("https://example.com/", HTML, {})):
        return dw.with_context(dw.analyse("https://example.com/"), goal="contactos")


def signed_payload(payload):
    ts = str(int(time.time()))
    signature = hmac.new(ENV["DIAGNOSTICO_STRIPE_WEBHOOK_SECRET"].encode(),
                         ts.encode()+b"."+payload, hashlib.sha256).hexdigest()
    return {"Stripe-Signature": f"t={ts},v1={signature}"}


def mocked_resend(collected):
    def send(url, **kwargs):
        if not url.startswith("https://api.resend.com/emails"):
            raise AssertionError("Unexpected outbound HTTP POST " + url)
        collected.append(kwargs)
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"id": "email_approved_test"}
        return response
    return send


class EmailDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        dw._payment_ip.clear()

    def test_webhook_invalid_signature_rejected_and_does_not_send(self):
        body = json.dumps({"type":"checkout.session.completed",
                           "data":{"object":{"id":SID,
                                             "metadata":{"service":"diagnostico-web-informe"}}}}).encode()
        with patch.dict(os.environ, ENV), patch.object(mail, "paid_delivery") as deliver:
            result = self.client.post("/diagnostico-web/stripe-evento", data=body,
                headers={"Stripe-Signature": "t=1,v1=deadbeef",
                         "Content-Type": "application/json"})
        self.assertEqual(result.status_code, 400)
        deliver.assert_not_called()

    def test_purchased_one_time_pdf_sent_to_email_from_stripe_not_user_form(self):
        audit = demo_audit()
        session = {"id": SID, "livemode": True, "mode":"payment",
                   "status":"complete","payment_status":"paid", "currency":"mxn",
                   "metadata":{"service":"diagnostico-web-informe"},
                   "customer_details":{"email":CUSTOMER}}
        calls = []
        def stripe(method,path,fields=None):
            if method=="GET":
                return session
            if method=="POST":
                self.assertTrue("metadata[diagnostico_mail_informe]" in fields)
                self.assertEqual(fields["metadata[diagnostico_mail_informe]"],"enviado")
                session["metadata"]["diagnostico_mail_informe"]="enviado"
                return session
            raise AssertionError()
        with patch.dict(os.environ, ENV), patch.object(dw,"_billing_request",side_effect=stripe), \
             patch.object(dw,"verify_purchase",return_value=(audit["url"],"contactos",audit)), \
             patch("requests.post",side_effect=mocked_resend(calls)):
            result=mail.paid_delivery(SID)
            again=mail.paid_delivery(SID)
        self.assertEqual(result, "enviado")
        self.assertEqual(again, "ya_enviado")
        self.assertEqual(len(calls),1)
        payload=calls[0]["json"]
        self.assertEqual(payload["to"],[CUSTOMER])
        self.assertIn("informe",payload["subject"].lower())
        self.assertIn("/diagnostico-web/informe?session_id="+SID,payload["text"])
        pdf=base64.b64decode(payload["attachments"][0]["content"])
        self.assertTrue(pdf.startswith(b"%PDF-"))
        self.assertGreater(len(pdf),3000)
        self.assertNotIn("sk_live_",str(payload))

    def test_webhook_automatic_delivery_and_unrelated_event_ignored(self):
        obj={"id":SID,"livemode":True,"metadata":{"service":"diagnostico-web-informe"}}
        body=json.dumps({"id":"evt_test_signed","type":"checkout.session.completed",
                         "data":{"object":obj}}).encode()
        with patch.dict(os.environ,ENV), patch.object(mail,"paid_delivery",return_value="enviado") as deliver:
            response=self.client.post("/diagnostico-web/stripe-evento",
                 data=body,headers={**HEADERS,**signed_payload(body)})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json["delivery"],"enviado")
        deliver.assert_called_once_with(SID)

        other=json.dumps({"type":"charge.succeeded",
                          "data":{"object":obj}}).encode()
        with patch.dict(os.environ,ENV),patch.object(mail,"paid_delivery") as deliver:
            ignored=self.client.post("/diagnostico-web/stripe-evento",
                data=other,headers={**HEADERS,**signed_payload(other)})
        self.assertEqual(ignored.status_code,200)
        deliver.assert_not_called()

    def test_webhook_delivery_failure_prompts_retry(self):
        body=json.dumps({"type":"checkout.session.completed","data":{"object":{
            "id":SID,"metadata":{"service":"diagnostico-web-informe"}}}}).encode()
        with patch.dict(os.environ,ENV), patch.object(mail,"paid_delivery",side_effect=RuntimeError("smtp offline")):
            response=self.client.post("/diagnostico-web/stripe-evento",
                data=body,headers={**HEADERS,**signed_payload(body)})
        self.assertEqual(response.status_code,503)

    def test_monthly_pdf_sent_to_stripe_customer_email(self):
        audit=demo_audit()
        meta=mon.baseline_metadata(audit)
        session={"id":MSID,"livemode":True,"mode":"subscription",
                 "status":"complete","payment_status":"paid","currency":"mxn",
                 "metadata":{"service":"diagnostico-web-seguimiento"},
                 "customer_details":{"email":CUSTOMER}}
        sub={"id":SUB,"status":"active","livemode":True,
             "metadata":meta,"items":{"data":[{"quantity":1,"price":{"id":mon.PRICE_ID}}]}}
        called=[]
        def stripe(method,path,fields=None):
            if method=="GET":
                return session
            if method=="POST":
                session["metadata"]["diagnostico_mail_seguimiento"] = fields["metadata[diagnostico_mail_seguimiento]"]
                return session
            raise AssertionError("Unexpected payment API method")
        with patch.dict(os.environ,ENV),patch.object(dw,"_billing_request",side_effect=stripe), \
             patch.object(dw,"_monthly_subscription",return_value=(sub,audit["url"],"contactos",audit)), \
             patch("requests.post",side_effect=mocked_resend(called)):
            status=mail.paid_delivery(MSID)
        self.assertEqual(status,"enviado")
        self.assertEqual(len(called),1)
        self.assertEqual(called[0]["json"]["to"],[CUSTOMER])
        self.assertTrue(base64.b64decode(called[0]["json"]["attachments"][0]["content"]).startswith(b"%PDF-"))

    def test_resend_button_uses_only_stripe_email(self):
        audit=demo_audit()
        with patch.dict(os.environ,ENV), patch.object(mail,"paid_delivery",return_value="enviado") as sender, \
             patch.object(dw,"verify_purchase",return_value=(audit["url"],"contactos",audit)):
            response=self.client.post("/diagnostico-web/correo/reenviar",
                data={"session_id":SID,"correo":"attacker@example.com"})
        self.assertEqual(response.status_code,200)
        sender.assert_called_once_with(SID)
        self.assertNotIn(b"attacker@example.com",response.data)

    def test_legal_docs_are_specific_and_not_legacy(self):
        for section, phrase in [
            ("terminos","$387 MXN"),
            ("privacidad","Stripe"),
            ("pagos","$597 MXN"),
        ]:
            result=self.client.get("/diagnostico-web/"+section)
            self.assertEqual(result.status_code,200)
            self.assertIn(phrase.encode(),result.data)
            self.assertNotIn(b"USD $29",result.data)
            self.assertNotIn(b"Converte.one",result.data)
        home=self.client.get("/diagnostico-web/")
        self.assertIn(b"/diagnostico-web/terminos",home.data)
        self.assertIn(b"/diagnostico-web/privacidad",home.data)
        self.assertIn(b"/diagnostico-web/pagos",home.data)


if __name__=="__main__":
    unittest.main()
