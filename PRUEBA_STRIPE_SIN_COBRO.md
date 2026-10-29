# Diagnóstico Web — prueba real sin cobrar dinero

## Qué se comprueba

La **misma aplicación Converte**, arrancada temporalmente en `http://127.0.0.1:8876/diagnostico-web/`, abre **Stripe Checkout de prueba**. El pago de prueba se registra como completado, Stripe regresa a la aplicación y se comprueba la entrega, sin dinero real.

No se altera `https://converte.uno/diagnostico-web/`, no se modifican sus precios reales y no se crea otra aplicación.

## Preparación

1. En la cuenta Stripe **CONVERTE.uno**, entra al entorno de pruebas: https://dashboard.stripe.com/sandboxes. Copia tu **clave secreta de prueba `sk_test_...`** desde Desarrolladores → Claves de API. No uses la clave `sk_live_`, no la compartas en un chat ni la guardes en GitHub.
2. Abre **CMD** en una copia de trabajo del repositorio existente `jaltamoc-prog/linkme-landing` (la misma versión de Converte). La prueba es un arranque temporal, no una nueva aplicación.
3. Ejecuta exactamente:

```cmd
py -3 -m pip install -r requirements.txt
py -3 probar_stripe_sin_cobrar.py
```

4. Cuando se te pida la clave, pégala en CMD. El texto no se mostrará. El script **crea o reutiliza automáticamente** en Stripe dos precios de prueba: MXN $387 (único) y MXN $597 (mensual). No pide Price IDs.
5. Se abrirá `http://127.0.0.1:8876/diagnostico-web/`. Comprueba la franja amarilla **MODO DE PRUEBA**. Si no la ves, **no continúes**.

## Plan único de $387 — recorrer como cliente

1. Escribe la URL de una página web pública, por ejemplo `https://converte.uno/`.
2. Pulsa toda la tarjeta de **Informe completo**. Debe abrir **Stripe Checkout** con $387 MXN.
3. Usa exclusivamente tarjeta de PRUEBA `4242 4242 4242 4242`; caducidad futura `12/34`; CVC ficticio `123`. No uses una tarjeta real.
4. Completa el pago ficticio. Checkout debe regresar a `http://127.0.0.1:8876/diagnostico-web/informe?...cs_test_...`.
5. Debe aparecer **Pago confirmado por Stripe**, el enlace **Descargar mi informe** y la descarga automática de un **PDF de dos páginas** con hallazgos visuales sobre la URL que escribiste.
6. Cierra y reabre el enlace de confirmación mientras el servidor local siga encendido: debe volver a descargar sin otra compra.

## Suscripción de $597/mes — recorrer como cliente

1. Vuelve a la página inicial y pulsa **Seguimiento mensual** con la misma URL. Comprueba **$597 MXN/mes** en Stripe Checkout, también de pruebas.
2. Completa con tarjeta de prueba. Stripe debe regresar a `/diagnostico-web/seguimiento?session_id=cs_test_...`.
3. Verifica el **panel**, la gráfica inicial y **Ver los 14 aspectos de esta revisión**.
4. Pulsa **Revisar mi página y guardar este mes**. Confirma que aparezca la revisión, el historial y las recomendaciones.
5. Pulsa **Descargar comparación en PDF**. Comprueba que el PDF tenga **dos páginas**, gráfica y acciones de mejora.
6. En Stripe **sandbox**, abre **Suscripciones** y cancela la suscripción de prueba. El enlace de gestión en la app se omite hasta configurar un portal de pruebas; el portal real no se comparte con el sandbox. La app debe mostrar el estado correcto en la siguiente visita. La cancelación al final del periodo conserva acceso mientras siga activa.
7. Para ensayar renovaciones futuras en pocos minutos, usa una simulación o reloj de prueba de Stripe, si esa suscripción lo permite. No muevas el reloj de producción.

## Qué resultados esperar

- Ambas compras usan objetos `cs_test_` y una clave `sk_test_`: **ningún banco recibe cargo real**.
- Una sesión no pagada **no desbloquea** PDF ni panel.
- El informe de $387 es una sola revisión; el de $597 admite comparaciones.
- La revisión de una web pública es real; **la operación bancaria es la única simulada**.
- No queda ninguna clave de Stripe guardada en archivo. Se borra de memoria al cerrar CMD.
- Para detener el servidor, presiona **Ctrl+C**.

## Limitaciones de esta prueba

Esta prueba interactiva verifica la integración con Stripe en sandbox, pero no demuestra por sí sola que el retorno funcione después de una transacción bancaria real. Para eso ya hay verificaciones de Checkout en producción y un conjunto automatizado de pruebas sin cobros. **No afirmes que las dos compras reales fueron completadas si no existe evidencia de ello.**

Si el script no abre la web, revisa que CMD se haya ejecutado dentro de la carpeta del repositorio, que Python esté instalado, y que el puerto 8876 esté disponible.

Documentación oficial: https://docs.stripe.com/testing y https://docs.stripe.com/keys
