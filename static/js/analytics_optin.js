/* Medicion GA4 opcional. Nunca envía formularios ni parámetros de URL. */
(() => {
  'use strict';
  const script = document.currentScript;
  const id = (script && script.dataset.measurementId) || '';
  if (!/^G-[A-Z0-9]+$/.test(id)) return;
  const storageKey = 'analytics_consent_local_v1';
  let choice = null;
  try { choice = localStorage.getItem(storageKey); } catch (_) {}
  const save = (x) => { try {localStorage.setItem(storageKey, x);} catch (_) {} };
  const privacyButton = document.createElement('button');
  privacyButton.type = 'button';
  privacyButton.textContent = 'Privacidad';
  privacyButton.setAttribute('aria-label','Cambiar preferencias de analítica');
  privacyButton.style.cssText = 'position:fixed;bottom:10px;left:10px;z-index:9998;background:#fff;color:#334155;border:1px solid #b5bdc9;border-radius:14px;padding:5px 10px;font:12px Arial,sans-serif;cursor:pointer;box-shadow:0 2px 9px #0002';
  const panel = document.createElement('section');
  panel.setAttribute('role','region');
  panel.setAttribute('aria-label','Preferencias de analítica');
  panel.style.cssText = 'position:fixed;bottom:44px;left:12px;z-index:9999;width:min(360px,calc(100vw - 24px));padding:15px;border-radius:12px;border:1px solid #ccd2d9;background:#fff;color:#1f2937;box-shadow:0 8px 30px #0003;font:14px/1.5 Arial,sans-serif';
  panel.innerHTML = '<strong>Analítica opcional</strong><p style="margin:8px 0 12px">Usamos Google Analytics para mejorar el sitio. Solo se activa con tu autorización. No enviamos datos de formularios.</p><div style="display:flex;gap:8px"><button type="button" data-answer="denied" style="padding:9px 13px;background:#e5e7eb;color:#111;border:0;border-radius:7px;cursor:pointer">Rechazar</button><button type="button" data-answer="granted" style="padding:9px 13px;background:#143c50;color:#fff;border:0;border-radius:7px;cursor:pointer">Aceptar</button></div>';
  panel.hidden = true;
  function loadGA() {
    if (window.__analyticsOptinLoaded) return;
    window.__analyticsOptinLoaded = true;
    window.dataLayer = window.dataLayer || [];
    window.gtag = window.gtag || function(){window.dataLayer.push(arguments);};
    window.gtag('consent','default',{analytics_storage:'denied',ad_storage:'denied',ad_user_data:'denied',ad_personalization:'denied'});
    window.gtag('consent','update',{analytics_storage:'granted'});
    window.gtag('js',new Date());
    window.gtag('config',id,{page_location:location.origin+location.pathname,allow_google_signals:false,allow_ad_personalization_signals:false});
    const tag=document.createElement('script');tag.async=true;
    tag.src='https://www.googletagmanager.com/gtag/js?id='+encodeURIComponent(id);
    document.head.appendChild(tag);
  }
  function setChoice(answer){
    choice=answer;save(answer);panel.hidden=true;
    if(answer==='granted')loadGA();
    else if(window.gtag){window.gtag('consent','update',{analytics_storage:'denied'});}
  }
  panel.querySelectorAll('[data-answer]').forEach(b=>b.addEventListener('click',()=>setChoice(b.dataset.answer)));
  privacyButton.addEventListener('click',()=>{panel.hidden=!panel.hidden;});
  document.body.append(privacyButton,panel);
  if(choice==='granted')loadGA();
  if(!choice)panel.hidden=false;
  document.addEventListener('click',(e)=>{
    if(choice!=='granted'||!window.gtag)return;
    const a=e.target.closest('a[href]');if(!a)return;
    const h=a.getAttribute('href')||'';
    let eventName='';
    if(/wa\.me|api\.whatsapp\.com|whatsapp:/i.test(h))eventName='whatsapp_click';
    else if(/\/nuevo(?:\?|$)/i.test(h))eventName='create_click';
    else if(/checkout\.stripe\.com/i.test(h))eventName='checkout_click';
    if(eventName)window.gtag('event',eventName,{send_to:id});
  });
})();