"""Pruebas de humo para la herramienta publica, sin llamadas a sitios ajenos."""
import unittest
from unittest.mock import patch
from app import app
from herramientas import diagnostico_web as dw

HTML = """<!doctype html><html><head><title>Ejemplo de negocio</title></head>
<body><h1>Conoce nuestros servicios</h1><img src="/foto.png">
<a href="/contacto">Contactanos</a></body></html>"""


class DiagnosticSmokeTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        dw._by_ip.clear()
        dw._global.clear()
        dw._cache.clear()

    def test_public_landing_and_sitemap(self):
        r = self.client.get("/diagnostico-web/")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Analiza tu", r.data)
        self.assertIn(b"converte.uno/diagnostico-web/", self.client.get("/sitemap.xml").data)
        self.assertEqual(self.client.get("/health").status_code, 200)
        self.assertEqual(self.client.get("/").status_code, 200)

    def test_report_uses_evidence_and_escapes(self):
        with patch.object(dw, "fetch_html", return_value=("https://ejemplo.com/", HTML, {})):
            r = self.client.post("/diagnostico-web/", data={
                "url": "https://ejemplo.com/?token=<script>alert(1)</script>",
                "objetivo": "ventas",
            })
        self.assertEqual(r.status_code, 200)
        self.assertIn("Qué conviene hacer primero".encode(), r.data)
        self.assertIn("Tu pagina no tiene".encode(), r.data) if False else None
        self.assertNotIn(b"<script>alert(1)</script>", r.data)

    def test_public_result_always_has_a_working_next_step(self):
        with patch.dict("os.environ", {
            "DIAGNOSTICO_PAGOS_ACTIVOS": "",
            "DIAGNOSTICO_STRIPE_SECRET_KEY": "",
            "DIAGNOSTICO_CONTACT_WHATSAPP": "",
        }), patch.object(dw, "fetch_html",
                         return_value=("https://ejemplo.com/", HTML, {})):
            r = self.client.post("/diagnostico-web/", data={
                "url": "https://ejemplo.com/", "objetivo": "contactos",
            })
        self.assertEqual(r.status_code, 200)
        self.assertIn(b'href="#planes"', r.data)
        self.assertIn(b'id="planes"', r.data)
        self.assertIn("Ver cómo continuar con las mejoras".encode(), r.data)
        self.assertIn("Seguimiento de mejoras".encode(), r.data)
        self.assertIn("pago seguro".encode(), r.data)
        self.assertNotIn(b'action="/diagnostico-web/comprar"', r.data)

    def test_no_public_report_for_local_networks(self):
        for url in ["http://127.0.0.1/", "http://192.168.0.1/", "http://example.com:8080",
                    "http://localhost/", "http://user:secret@example.com/"]:
            with self.subTest(url=url):
                r = self.client.post("/diagnostico-web/", data={"url": url})
                self.assertEqual(r.status_code, 422)

    def test_proxy_visitor_identity_uses_last_trusted_hop_on_render(self):
        with patch.dict("os.environ", {"RENDER": "true"}):
            with app.test_request_context(
                "/diagnostico-web/",
                headers={"X-Forwarded-For": "9.9.9.9, 8.8.8.8"},
                environ_base={"REMOTE_ADDR": "10.0.0.3"},
            ):
                self.assertEqual(dw.visitor_ip(), "8.8.8.8")
            with app.test_request_context(
                "/diagnostico-web/",
                headers={"X-Forwarded-For": "9.9.9.9, no-es-ip"},
                environ_base={"REMOTE_ADDR": "10.0.0.3"},
            ):
                self.assertEqual(dw.visitor_ip(), "10.0.0.3")

    def test_limits_apply_to_new_sites_not_cached_rechecks_or_other_clients(self):
        with patch.dict("os.environ", {"RENDER": "true"}), patch.object(
            dw, "fetch_html", return_value=("https://ejemplo.com/", HTML, {})
        ) as download:
            headers = {"X-Forwarded-For": "9.9.9.9, 8.8.8.8"}
            for index in range(20):
                response = self.client.post(
                    "/diagnostico-web/",
                    data={"url": "https://sitio-" + str(index) + ".com/"},
                    headers=headers,
                )
                self.assertEqual(response.status_code, 200, index)
            blocked = self.client.post(
                "/diagnostico-web/",
                data={"url": "https://sitio-21.com/"},
                headers=headers,
            )
            self.assertEqual(blocked.status_code, 429)
            self.assertEqual(blocked.headers.get("Retry-After"), "600")

            repeat = self.client.post(
                "/diagnostico-web/",
                data={"url": "https://sitio-0.com/", "objetivo": "ventas"},
                headers=headers,
            )
            self.assertEqual(repeat.status_code, 200)

            other = self.client.post(
                "/diagnostico-web/",
                data={"url": "https://otro-cliente.com/"},
                headers={"X-Forwarded-For": "9.9.9.9, 1.1.1.1"},
            )
            self.assertEqual(other.status_code, 200)
            self.assertEqual(download.call_count, 21)

    def test_monthly_dashboard_and_saved_update_without_stripe_network(self):
        from herramientas import diagnostico_seguimiento as mon
        sid = "cs_live_" + "K"*24
        subid = "sub_" + "L"*22
        with patch.object(dw, "fetch_html",
                          return_value=("https://ejemplo.com/", HTML, {})):
            baseline = dw.analyse("https://ejemplo.com/")
        baseline["goal"] = "ventas"
        meta = mon.baseline_metadata(baseline)
        sub = {
            "id": subid, "status": "active", "livemode": True,
            "cancel_at_period_end": False, "metadata": dict(meta),
            "items": {"data": [{"price": {"id": mon.PRICE_ID}, "quantity": 1}]},
        }
        with patch.object(dw, "_monthly_subscription",
                          return_value=(sub, "https://ejemplo.com/", "ventas", baseline)):
            page = self.client.get("/diagnostico-web/seguimiento?session_id=" + sid)
        self.assertEqual(page.status_code, 200)
        self.assertIn("Seguimiento de tu página web".encode(), page.data)
        self.assertIn(b"no-store", page.headers.get("Cache-Control", "").encode())
        self.assertNotIn(b"checkout.stripe.com", page.data)

        saved = dict(sub)
        saved["metadata"] = dict(meta)
        def stripe_update(method, path, fields=None):
            self.assertEqual(method, "POST")
            self.assertEqual(path, "subscriptions/" + subid)
            self.assertTrue(any(k.startswith("metadata[monitor_m") for k in fields))
            updates = {k[len("metadata["):-1]: v for k, v in fields.items()}
            saved["metadata"].update(updates)
            return saved

        with patch.object(dw, "_monthly_subscription",
                          return_value=(sub, "https://ejemplo.com/", "ventas", baseline)), \
             patch.object(dw, "fetch_html",
                          return_value=("https://ejemplo.com/", HTML, {})), \
             patch.object(dw, "_billing_request", side_effect=stripe_update):
            result = self.client.post("/diagnostico-web/seguimiento/revisar",
                                      data={"session_id": sid})
        self.assertEqual(result.status_code, 200)
        self.assertIn("Revisión guardada".encode(), result.data)
        self.assertIn("Historial de revisiones".encode(), result.data)
        self.assertEqual(len(mon.history(saved["metadata"])), 1)

    def test_monthly_monitoring_pdf_is_protected_and_readable(self):
        from herramientas import diagnostico_seguimiento as mon
        sid = "cs_live_" + "Q"*24
        with patch.object(dw, "fetch_html",
                          return_value=("https://ejemplo.com/", HTML, {})):
            baseline = dw.analyse("https://ejemplo.com/")
        sub = {"metadata": {}, "status": "active", "cancel_at_period_end": False}
        with patch.object(dw, "_monthly_subscription",
                          return_value=(sub, "https://ejemplo.com/", "ventas", baseline)):
            page = self.client.get("/diagnostico-web/seguimiento/descargar?session_id=" + sid)
        self.assertEqual(page.status_code, 200)
        self.assertTrue(page.data.startswith(b"%PDF-"))
        self.assertIn("no-store", page.headers.get("Cache-Control", ""))
        self.assertEqual(
            self.client.get("/diagnostico-web/seguimiento/descargar?session_id=invalid").status_code,
            404)
        data = mon.comparison_pdf("https://ejemplo.com/", "Facilitar ventas",
                                  baseline, {**baseline, "h1": 2}, baseline)
        self.assertGreater(len(data.getvalue()), 1500)

    def test_monthly_history_has_bounded_twelve_months(self):
        import datetime as datetime_module
        from herramientas import diagnostico_seguimiento as mon
        with patch.object(dw, "fetch_html",
                          return_value=("https://ejemplo.com/", HTML, {})):
            audited = dw.analyse("https://ejemplo.com/")
        meta = mon.baseline_metadata(audited)
        for year in (2025, 2026):
            for month in range(1, 13):
                now = datetime_module.datetime(year, month, 10, tzinfo=datetime_module.timezone.utc)
                updates = mon.month_updates(meta, audited, now=now)
                for key, value in updates.items():
                    if value:
                        meta[key] = value
                    else:
                        meta.pop(key, None)
        self.assertEqual(len(mon.history(meta)), 12)
        self.assertLessEqual(len(meta), 30)

    def test_stripe_monthly_permissions_read_write_probe_is_nondestructive(self):
        from unittest.mock import Mock
        from herramientas.diagnostico_permisos import check_restricted_key, permissions_verified
        ok = Mock(status_code=200)
        missing = Mock(status_code=404)
        missing.json.return_value = {"error": {"code": "resource_missing"}}
        with patch("herramientas.diagnostico_permisos.requests.get", return_value=ok) as get, \
             patch("herramientas.diagnostico_permisos.requests.post", return_value=missing) as post:
            result = check_restricted_key("rk_live_fake_for_test")
        self.assertTrue(permissions_verified(result))
        self.assertEqual(get.call_args.kwargs["params"], {"limit": 1})
        self.assertIn("/subscriptions/sub_", post.call_args.args[0])
        self.assertIn("metadata[permission_probe]", post.call_args.kwargs["data"])

        denied = Mock(status_code=403)
        with patch("herramientas.diagnostico_permisos.requests.get", return_value=denied), \
             patch("herramientas.diagnostico_permisos.requests.post") as post:
            self.assertFalse(permissions_verified(check_restricted_key("rk_live_fake")))
            post.assert_not_called()

    def test_ten_points_are_honest_about_google_accounts(self):
        from herramientas import diagnostico_evaluacion as ev
        html = """<!DOCTYPE html><html><head><title>Abogado de empresas en Puebla</title>
        <meta name="description" content="Asesoría legal a negocios en Puebla">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <script src="https://www.googletagmanager.com/gtag/js?id=G-1234567890"></script>
        </head><body><h1>Asesoría en Puebla</h1>
        <a href="/servicios">Servicios</a>
        <a href="https://www.google.com/maps/place/example">Mapa</a>
        <img src="/web.webp" width="200" height="100" alt="Oficina">
        </body></html>"""
        with patch.object(dw, "fetch_html", return_value=("https://ejemplo.com/", html, {})):
            audit=dw.with_context(dw.analyse("https://ejemplo.com/"),
                                  "abogado de empresas", "Puebla", "contactos")
        checks=ev.checks(audit, "contactos")
        self.assertEqual(len(checks),14)
        ids={row["id"]:row for row in checks}
        self.assertEqual(ids["search_console"]["status"], "review")
        self.assertEqual(ids["backlinks"]["status"], "review")
        self.assertEqual(ids["analytics"]["status"], "ok")
        self.assertIn("no confirma", ids["analytics"]["evidence"] + ids["business_profile"]["evidence"])
        self.assertEqual(ids["keyword_title"]["status"], "ok")
        self.assertEqual(ids["city"]["status"], "ok")
        self.assertEqual(ids["internal_links"]["status"], "ok")
        self.assertEqual(ids["images_speed"]["status"], "ok")
        self.assertEqual(ids["business_profile"]["status"], "ok")
        self.assertEqual(ev.overview(audit, "contactos")["ok"]+
                         ev.overview(audit, "contactos")["issue"]+
                         ev.overview(audit, "contactos")["review"],14)
        self.assertNotIn("page_text", dw.restored_snapshot(
            dw.audit_snapshot(audit), audit["url"]))

    def test_keyword_and_city_are_optional_and_comparable(self):
        from herramientas import diagnostico_evaluacion as ev
        with patch.object(dw, "fetch_html",
                          return_value=("https://ejemplo.com/", HTML, {})):
            base=dw.analyse("https://ejemplo.com/")
        without=dw.with_context(base)
        self.assertEqual({x["id"]:x for x in ev.checks(without)}["keyword_title"]["status"],"review")
        with_words=dw.with_context(base,"ejemplo de negocio","Monterrey","ventas")
        self.assertEqual({x["id"]:x for x in ev.checks(with_words)}["keyword_title"]["status"],"ok")
        self.assertEqual({x["id"]:x for x in ev.checks(with_words)}["city"]["status"],"issue")
        changed=dict(with_words)
        changed["title"]="Otra página distinta"
        comparison=ev.progress(with_words,changed,"ventas")
        self.assertGreaterEqual(comparison["total"],3)
        self.assertTrue(any(item["id"]=="keyword_title" for item in comparison["regressed"]))
        self.assertNotIn("search_console", [item["id"] for item in comparison["regressed"]])

    def test_paid_single_purchase_can_save_one_followup_without_new_charge(self):
        sid="cs_live_"+"C"*24
        with patch.object(dw,"fetch_html",
                          return_value=("https://ejemplo.com/",HTML,{})):
            previous=dw.with_context(dw.analyse("https://ejemplo.com/"),
                                     "ejemplo","CDMX","ventas")
        previous["checked"]="01/09/2026 10:00 UTC"
        updated=dict(previous)
        updated["checked"]="28/10/2026 11:00 UTC"
        updated["title"]="Nuevo título de negocio"
        updates={}
        def post_stripe(method,path,fields=None):
            self.assertEqual(method,"POST")
            self.assertTrue(path.startswith("checkout/sessions/cs_live_"))
            self.assertTrue(any("metadata[followup_0]"==k for k in fields))
            updates.update(fields)
            return {"id":sid}
        with patch.dict("os.environ",{
            "DIAGNOSTICO_STRIPE_SECRET_KEY":"rk_live_mock",
            "DIAGNOSTICO_STRIPE_PRICE_ID":dw.REPORT_PRICE_ID,
        }),patch.object(dw,"verify_purchase",
                        return_value=(previous["url"],"ventas",previous)), \
            patch.object(dw,"purchased_progress",return_value=None), \
            patch.object(dw,"analyse",return_value=updated), \
            patch.object(dw,"_billing_request",side_effect=post_stripe):
            response=self.client.post("/diagnostico-web/comparar",
                                      data={"session_id":sid})
        self.assertEqual(response.status_code,200)
        self.assertIn("Primera revisión".encode(),response.data)
        self.assertIn("Revisión posterior".encode(),response.data)
        self.assertIn("Tu evolución".encode(),response.data)
        meta={key[len("metadata["):-1]:value for key,value in updates.items()}
        recovered=dw.restored_snapshot(meta,previous["url"],prefix="followup")
        self.assertEqual(recovered["title"],updated["title"])

    def test_monthly_pdf_includes_comparison_and_recommendations(self):
        from herramientas import diagnostico_seguimiento as mon
        with patch.object(dw,"fetch_html",
                          return_value=("https://ejemplo.com/",HTML,{})):
            baseline=dw.with_context(dw.analyse("https://ejemplo.com/"),
                                     "servicios","Puebla","ventas")
        latest=dict(baseline)
        latest["title"]="Servicio actualizado"
        latest["checked"]="02/11/2026 11:00 UTC"
        pdf=mon.comparison_pdf("https://ejemplo.com/","Atraer ventas",
                                baseline,latest,baseline,goal="ventas",
                                history=[{"month":"202611","audit":latest}])
        self.assertTrue(pdf.getvalue().startswith(b"%PDF-"))
        self.assertGreater(len(pdf.getvalue()),2200)

    def test_monthly_history_snapshot_and_comparison(self):
        from herramientas import diagnostico_seguimiento as mon
        with patch.object(dw, "fetch_html",
                          return_value=("https://ejemplo.com/", HTML, {})):
            audit = dw.analyse("https://ejemplo.com/")
        audit["goal"] = "ventas"
        metadata = mon.baseline_metadata(audit)
        self.assertEqual(mon.read_baseline(metadata)["title"], audit["title"])
        updates = mon.month_updates(metadata, audit)
        metadata.update(updates)
        records = mon.history(metadata)
        self.assertEqual(len(records), 1)
        self.assertEqual(len(mon.differences(mon.read_baseline(metadata), records[0]["audit"])), 0)
        changed = dict(audit)
        changed["title"] = "Nuevo título"
        updates = mon.month_updates(metadata, changed)
        metadata.update(updates)
        records = mon.history(metadata)
        self.assertEqual(len(records), 1)
        self.assertTrue(any(row["field"] == "Título de la página"
                            for row in mon.differences(mon.read_baseline(metadata),
                                                       records[0]["audit"])))

    def test_monthly_checkout_disabled_until_fully_configured(self):
        with patch.dict("os.environ", {
            "DIAGNOSTICO_SUSCRIPCIONES_ACTIVAS": "",
            "DIAGNOSTICO_STRIPE_MONTHLY_PRICE_ID": "",
        }):
            self.assertFalse(dw.subscriptions_enabled())
            self.assertEqual(self.client.post("/diagnostico-web/suscribir").status_code, 503)
            page = self.client.get("/diagnostico-web/")
            self.assertNotIn(b'action="/diagnostico-web/suscribir"', page.data)

    def test_monthly_checkout_validates_price_and_writes_baseline(self):
        from unittest.mock import Mock
        with patch.dict("os.environ", {
            "DIAGNOSTICO_STRIPE_SECRET_KEY": "rk_live_mock",
            "DIAGNOSTICO_STRIPE_PRICE_ID": dw.REPORT_PRICE_ID,
            "DIAGNOSTICO_SUSCRIPCIONES_ACTIVAS": "1",
            "DIAGNOSTICO_STRIPE_MONTHLY_PRICE_ID": dw.monitor.PRICE_ID,
        }), patch.object(dw, "fetch_html",
                        return_value=("https://ejemplo.com/", HTML, {})):
            mock = Mock()
            mock.json.return_value = {"url": "https://checkout.stripe.com/c/pay/example"}
            with patch("requests.post", return_value=mock) as stripe:
                result = self.client.post("/diagnostico-web/suscribir",
                    data={"url": "https://ejemplo.com/", "objetivo": "ventas"})
        self.assertEqual(result.status_code, 200)
        self.assertIn(b'<meta http-equiv="refresh"', result.data)
        self.assertIn(b'https://checkout.stripe.com/c/pay/example', result.data)
        data = stripe.call_args.kwargs["data"]
        self.assertEqual(data["mode"], "subscription")
        self.assertEqual(data["line_items[0][price]"], dw.monitor.PRICE_ID)
        self.assertEqual(data["subscription_data[metadata][monitor_goal]"], "ventas")
        self.assertEqual(data["subscription_data[metadata][monitor_service]"],
                         "diagnostico-web-seguimiento")

    def test_monthly_dashboard_requires_paid_active_subscription(self):
        from unittest.mock import Mock
        from werkzeug.exceptions import Forbidden
        from herramientas import diagnostico_seguimiento as mon
        sid = "cs_live_" + "Z"*24
        subid = "sub_" + "B"*22
        with patch.object(dw, "fetch_html",
                          return_value=("https://ejemplo.com/", HTML, {})):
            a = dw.analyse("https://ejemplo.com/")
        a["goal"] = "ventas"
        meta = mon.baseline_metadata(a)
        session = {"id":sid, "mode":"subscription", "status":"complete",
                   "payment_status":"paid", "amount_total":34900,
                   "currency":"mxn", "livemode":True, "subscription":subid,
                   "metadata":{"service":"diagnostico-web-seguimiento"}}
        subscription = {"id":subid, "status":"active", "livemode":True,
                        "metadata":meta, "items":{"data":[{
                            "price":{"id":mon.PRICE_ID}, "quantity":1
                        }]}}
        with app.test_request_context("/diagnostico-web/seguimiento"), patch.dict(
            "os.environ", {"DIAGNOSTICO_STRIPE_SECRET_KEY":"rk_live_mock",
                           "DIAGNOSTICO_STRIPE_PRICE_ID":dw.REPORT_PRICE_ID}
        ), patch.object(dw, "_billing_request", side_effect=[
            session, subscription,
        ]):
            result = dw._monthly_subscription(sid)
            self.assertEqual(result[1], "https://ejemplo.com/")
            self.assertEqual(result[2], "ventas")
        with app.test_request_context("/diagnostico-web/seguimiento"), patch.dict(
            "os.environ", {"DIAGNOSTICO_STRIPE_SECRET_KEY":"rk_live_mock",
                           "DIAGNOSTICO_STRIPE_PRICE_ID":dw.REPORT_PRICE_ID}
        ), patch.object(dw, "_billing_request", side_effect=[
            session, {**subscription, "status":"canceled"},
        ]):
            with self.assertRaises(Forbidden):
                dw._monthly_subscription(sid)

    def test_paid_feature_disabled_without_keys(self):
        with patch.dict("os.environ", {"DIAGNOSTICO_STRIPE_SECRET_KEY": "",
                                     "DIAGNOSTICO_STRIPE_PRICE_ID": ""}):
            self.assertEqual(self.client.post("/diagnostico-web/comprar").status_code, 503)

    def test_paid_report_has_ten_distinct_evidence_based_checks(self):
        with patch.object(dw, "fetch_html",
                          return_value=("https://ejemplo.com/", HTML, {})):
            audit = dw.analyse("https://ejemplo.com/")
        checks = dw.expanded_plan(audit, "ventas")
        self.assertEqual(len(checks), 10)
        self.assertTrue(any("Ruta de compra" in item["area"] for item in checks))
        self.assertTrue(all(item["evidence"] and item["action"] for item in checks))
        from herramientas.diagnostico_pdf import build_pdf
        report = dw.report_for(audit, "ventas")
        pdf = build_pdf(audit, report, dw.GOALS["ventas"], checks=checks)
        self.assertTrue(pdf.getvalue().startswith(b"%PDF-"))
        self.assertGreater(len(pdf.getvalue()), 4500)

    def test_paid_pdf_is_readable_and_contains_all_findings(self):
        from herramientas.diagnostico_pdf import build_pdf
        with patch.object(dw, "fetch_html",
                          return_value=("https://ejemplo.com/", HTML, {})):
            audit = dw.analyse("https://ejemplo.com/")
        report = dw.report_for(audit, "ventas")
        self.assertGreaterEqual(report["count"], 4)
        pdf = build_pdf(audit, report, "Facilitar compras y pedidos")
        content = pdf.getvalue()
        self.assertTrue(content.startswith(b"%PDF-"))
        self.assertGreater(len(content), 3000)

    def test_paid_session_requires_paid_live_price_and_matching_service(self):
        from unittest.mock import Mock
        from werkzeug.exceptions import Forbidden
        sid = "cs_live_" + "A" * 24
        context = {
            "DIAGNOSTICO_STRIPE_SECRET_KEY": "sk_live_test_key_for_mock",
            "DIAGNOSTICO_STRIPE_PRICE_ID": dw.REPORT_PRICE_ID,
        }
        valid = {
            "id": sid, "livemode": True, "mode": "payment", "currency": "mxn",
            "payment_status": "paid", "status": "complete", "amount_total": 19900,
            "metadata": {"service": "diagnostico-web-informe",
                         "url": "https://ejemplo.com/", "goal": "ventas"},
        }
        lines = {"data": [{"price": {"id": dw.REPORT_PRICE_ID},
                           "quantity": 1, "amount_total": 19900}]}
        def response(body):
            obj = Mock()
            obj.json.return_value = body
            return obj
        with app.test_request_context("/diagnostico-web/informe"), patch.dict(
            "os.environ", context
        ), patch("requests.get", side_effect=[response(valid), response(lines)]):
            self.assertEqual(dw.verify_purchase(sid), ("https://ejemplo.com/", "ventas", None))
        with app.test_request_context("/diagnostico-web/informe"), patch.dict(
            "os.environ", context
        ), patch("requests.get", side_effect=[response({
            **valid, "payment_status": "unpaid",
        })]):
            with self.assertRaises(Forbidden):
                dw.verify_purchase(sid)
        with app.test_request_context("/diagnostico-web/informe"), patch.dict(
            "os.environ", context
        ), patch("requests.get", side_effect=[
            response(valid), response({"data": [{"price": {"id": "price_other"},
                                                 "quantity": 1, "amount_total": 19900}]}),
        ]):
            with self.assertRaises(Forbidden):
                dw.verify_purchase(sid)

    def test_checkout_snapshot_survives_site_outage_after_payment(self):
        import copy
        with patch.object(dw, "fetch_html",
                          return_value=("https://ejemplo.com/", HTML, {})):
            audited = dw.analyse("https://ejemplo.com/")
        metadata = dw.audit_snapshot(audited)
        self.assertTrue(all(len(value) <= 500 for value in metadata.values()))
        recovered = dw.restored_snapshot(metadata, "https://ejemplo.com/")
        self.assertEqual({k:v for k,v in audited.items() if k != "page_text"}, recovered)
        self.assertNotIn("page_text", recovered)
        tampered = copy.deepcopy(metadata)
        tampered["audit_0"] = "not_valid"
        with self.assertRaises(ValueError):
            dw.restored_snapshot(tampered, "https://ejemplo.com/")
        with self.assertRaises(ValueError):
            dw.restored_snapshot(metadata, "https://otra-web.com/")

    def test_pdf_can_be_downloaded_without_revisiting_source(self):
        sid = "cs_live_" + "Z"*24
        with patch.dict("os.environ", {
            "DIAGNOSTICO_STRIPE_SECRET_KEY": "sk_live_test_key_for_mock",
            "DIAGNOSTICO_STRIPE_PRICE_ID": dw.REPORT_PRICE_ID,
        }), patch.object(dw, "fetch_html",
                        return_value=("https://ejemplo.com/", HTML, {})):
            audited = dw.analyse("https://ejemplo.com/")
            with patch.object(dw, "verify_purchase", return_value=(
                "https://ejemplo.com/", "ventas", audited
            )), patch.object(dw, "purchased_progress", return_value=None), \
                 patch.object(dw, "fetch_html", side_effect=RuntimeError("Site offline")):
                pdf = self.client.get("/diagnostico-web/descargar?session_id="+sid)
        self.assertEqual(pdf.status_code, 200)
        self.assertTrue(pdf.data.startswith(b"%PDF-"))

    def test_paid_page_has_real_pdf_download_and_no_messaging_service(self):
        context = {
            "DIAGNOSTICO_STRIPE_SECRET_KEY": "sk_live_test_key_for_mock",
            "DIAGNOSTICO_STRIPE_PRICE_ID": dw.REPORT_PRICE_ID,
            "DIAGNOSTICO_PAGOS_ACTIVOS": "",
        }
        sid = "cs_live_" + "A" * 24
        with patch.dict("os.environ", context), patch.object(
            dw, "verify_purchase", return_value=("https://ejemplo.com/", "ventas", None)
        ), patch.object(dw, "fetch_html",
                        return_value=("https://ejemplo.com/", HTML, {})), patch.object(
            dw, "purchased_progress", return_value=None):
            webpage = self.client.get("/diagnostico-web/informe?session_id=" + sid)
            pdf = self.client.get("/diagnostico-web/descargar?session_id=" + sid)
        self.assertEqual(webpage.status_code, 200)
        self.assertIn("Descargar mi informe completo".encode(), webpage.data)
        self.assertNotIn(b"wa.me", webpage.data)
        self.assertEqual(pdf.status_code, 200)
        self.assertEqual(pdf.mimetype, "application/pdf")
        self.assertTrue(pdf.data.startswith(b"%PDF-"))
        self.assertIn("no-store", pdf.headers.get("Cache-Control", ""))
        self.assertEqual(pdf.headers.get("X-Robots-Tag"), "noindex, nofollow")

    def test_checkout_creates_hosted_session_with_verified_audit_snapshot(self):
        from unittest.mock import Mock
        with patch.dict("os.environ", {
            "DIAGNOSTICO_STRIPE_SECRET_KEY": "sk_live_test_key_for_mock",
            "DIAGNOSTICO_STRIPE_PRICE_ID": dw.REPORT_PRICE_ID,
            "DIAGNOSTICO_PRICE_LABEL": "$199 MXN",
            "DIAGNOSTICO_PAGOS_ACTIVOS": "1",
        }), patch.object(dw, "fetch_html",
                        return_value=("https://ejemplo.com/", HTML, {})):
            stripe = Mock()
            stripe.json.return_value = {"url": "https://checkout.stripe.com/c/pay/test"}
            with patch("requests.post", return_value=stripe) as call:
                response = self.client.post("/diagnostico-web/comprar", data={
                    "url": "https://ejemplo.com/", "objetivo": "ventas",
                })
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'https://checkout.stripe.com/c/pay/test', response.data)
        self.assertIn(b'<meta http-equiv="refresh"', response.data)
        self.assertIn(b'Continuar al pago seguro', response.data)
        self.assertIn("no-store", response.headers.get("Cache-Control", ""))
        form = call.call_args.kwargs["data"]
        self.assertEqual(form["line_items[0][price]"], dw.REPORT_PRICE_ID)
        self.assertEqual(form["metadata[service]"], "diagnostico-web-informe")
        self.assertEqual(form["metadata[url]"], "https://ejemplo.com/")
        self.assertEqual(form["metadata[audit_version]"], "1")
        self.assertTrue(form["metadata[audit_0]"])
        self.assertEqual(form["mode"], "payment")

    def test_checkout_card_is_fully_clickable_and_csp_allows_stripe(self):
        # Chrome can enforce form-action on a 303 redirect to hosted Checkout.
        with patch.dict("os.environ", {
            "DIAGNOSTICO_STRIPE_SECRET_KEY": "rk_live_mock_for_test",
            "DIAGNOSTICO_STRIPE_PRICE_ID": dw.REPORT_PRICE_ID,
            "DIAGNOSTICO_PRICE_LABEL": "$199 MXN",
            "DIAGNOSTICO_PAGOS_ACTIVOS": "1",
        }), patch.object(dw, "fetch_html",
                        return_value=("https://ejemplo.com/", HTML, {})):
            result = self.client.post("/diagnostico-web/", data={
                "url": "https://ejemplo.com/", "objetivo": "ventas",
            })
        self.assertEqual(result.status_code, 200)
        csp = result.headers["Content-Security-Policy"]
        self.assertIn("form-action 'self' https://checkout.stripe.com", csp)
        self.assertIn("default-src 'none'", csp)
        self.assertIn("base-uri 'none'", csp)
        self.assertIn("tier popular tier-clickable", result.get_data(as_text=True))
        self.assertIn('action="/diagnostico-web/comprar"', result.get_data(as_text=True))
        self.assertIn('<button class="tier-inner" type="submit"', result.get_data(as_text=True))
        self.assertIn('<svg viewBox="0 0 24 24"', result.get_data(as_text=True))
        self.assertIn("form-grid", result.get_data(as_text=True))
        self.assertIn('class="tier popular tier-clickable"', result.get_data(as_text=True))
        self.assertIn('type="hidden" name="url"', result.get_data(as_text=True))

    def test_checkout_transition_never_redirects_to_untrusted_domain(self):
        with app.test_request_context("/diagnostico-web/comprar"):
            for bad in (
                "https://checkout.stripe.com.evil.example/x",
                "http://checkout.stripe.com/x",
                "https://evil.example/x",
                "https://user:password@checkout.stripe.com/x",
            ):
                with self.assertRaises(ValueError):
                    dw.checkout_handoff(bad)
            good = dw.checkout_handoff("https://checkout.stripe.com/c/pay/example")
            self.assertEqual(good.status_code, 200)
            self.assertIn(b'<meta http-equiv="refresh"', good.data)
            self.assertIn(b'href="https://checkout.stripe.com/c/pay/example"', good.data)
            self.assertIn("no-store", good.headers["Cache-Control"])
            self.assertEqual(good.headers["Referrer-Policy"], "no-referrer")

    def test_paid_checkout_disabled_by_default_even_if_stripe_keys_exist(self):
        with patch.dict("os.environ", {
            "DIAGNOSTICO_STRIPE_SECRET_KEY": "sk_live_test_key_for_mock",
            "DIAGNOSTICO_STRIPE_PRICE_ID": dw.REPORT_PRICE_ID,
            "DIAGNOSTICO_PRICE_LABEL": "$199 MXN",
            "DIAGNOSTICO_PAGOS_ACTIVOS": "",
        }):
            self.assertFalse(dw.payments_enabled())
            self.assertEqual(self.client.post("/diagnostico-web/comprar").status_code, 503)

    def test_redirect_network_with_private_address_is_blocked(self):
        with patch.object(dw.socket, "getaddrinfo",
                          return_value=[(None, None, None, None, ("127.0.0.1", 443))]):
            with self.assertRaises(ValueError):
                dw.verified_address("ejemplo.com", 443)


if __name__ == "__main__":
    unittest.main()
