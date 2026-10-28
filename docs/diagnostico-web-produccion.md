# Diagnostico Web publico - converte.uno/diagnostico-web/

## Producto y arquitectura
- Ruta publica dentro de la landing Flask existente. No crea otra aplicacion ni copia las credenciales de Revisar Metricas Web local.
- Motor libre: audita HTML publico y produce tres acciones justificadas y entendibles. No afirma conocer ventas, Google Analytics o indexacion sin autorización.
- Endurecimiento: consultas a IP publica verificada y fijada en conexion, limites 6/10 min por IP y 120/h por proceso, 3 auditorias simultaneas, HTML max 5 MB, timeout, cache 10 min, redirecciones validadas, no almacenamiento persistente de datos personales.
- El informe de pago se habilita solo si hay Price real y configuracion completa. La sesion se valida contra la API de Stripe y el Price ID antes de entregar el detalle. Los resultados se imprimen a PDF desde el navegador.
- Un contacto comercial se habilita solo si se configura WhatsApp de atencion. No existe un CRM o base de leads en esta version.

## Configuracion a autorizar (solo secretos de Render; nunca GitHub)
- DIAGNOSTICO_CONTACT_WHATSAPP: numero comercial real para atender solicitudes de mejora (cod. pais y telefono, sin + ni espacios).
- DIAGNOSTICO_STRIPE_SECRET_KEY: llave sk_live_... correspondiente a la cuenta comercial autorizada.
- DIAGNOSTICO_STRIPE_PRICE_ID: identificador price_... de un producto Stripe de cobro unico, cuya moneda y precio deben revisarse antes de activar.
- DIAGNOSTICO_PRICE_LABEL: precio visible exacto, p.ej. "$199 MXN" SOLO si coincide con Stripe.
- DIAGNOSTICO_PAGOS_ACTIVOS: 1 SOLO despues de probar en el entorno correspondiente. Por defecto los cobros estan deshabilitados.

## Verificacion
- /health debe devolver OK.
- /diagnostico-web/ debe devolver 200 y el formulario.
- /sitemap.xml debe incluir /diagnostico-web/.
- GitHub Actions: Diagnostico Web - pruebas antes del deploy, Verificar diagnostico-web en produccion, Diagnostico Web - prueba real de analisis y auditoria de sitios propios.

## Limites claros
- La version publica no usa OAuth de GA4 ni Search Console; esos permisos permanecen en la aplicacion local del propietario.
- La auditoria inicial no usa un navegador para ejecutar JS ni mide velocidad de PageSpeed.
- La monetizacion y captacion de clientes quedan inactivas hasta configurar y autorizar Stripe y el canal de atencion.
