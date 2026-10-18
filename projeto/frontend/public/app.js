/* ==========================================================================
   Servidores do Executivo Federal - lógica da página
   Consome a API Flask em /api (proxy do Nginx para o contêiner backend).
   ========================================================================== */
(() => {
  'use strict';

  const API = '/api';
  const $ = (sel) => document.querySelector(sel);
  const fmtInt = (n) => Number(n || 0).toLocaleString('pt-BR');

  async function chamarAPI(caminho) {
    const resp = await fetch(API + caminho, { headers: { Accept: 'application/json' } });
    const corpo = await resp.json();
    if (!resp.ok) throw corpo;
    return corpo;
  }

  async function carregarStatus() {
    const el = $('#estado-api');
    try {
      const h = await chamarAPI('/health');
      el.classList.add('estado--ok');
      el.querySelector('.estado__texto').textContent = `API online · ${fmtInt(h.total_servidores)} registros`;
    } catch (e) {
      el.classList.add('estado--erro');
      el.querySelector('.estado__texto').textContent = 'API indisponível';
    }
  }

  carregarStatus();
})();
