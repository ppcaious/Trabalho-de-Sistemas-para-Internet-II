/* ==========================================================================
   Servidores do Executivo Federal - lógica da página
   Consome a API Flask em /api (proxy do Nginx para o contêiner backend).
   ========================================================================== */
(() => {
  'use strict';

  const API = '/api';
  const $ = (sel) => document.querySelector(sel);

  // ---- elementos ---------------------------------------------------------
  const form = $('#form-busca');
  const btnBuscar = $('#btn-buscar');
  const msg = $('#mensagem');
  const secResultado = $('#resultado');
  const corpoTabela = $('#tabela-corpo');
  const resumo = $('#resultado-resumo');

  // ---- utilidades ---------------------------------------------------------
  const fmtMoeda = (v) => v == null ? '—' : Number(v).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const fmtInt = (n) => Number(n || 0).toLocaleString('pt-BR');
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const titulo = (s) => String(s || '').toLowerCase().replace(/(^|\s)\S/g, (t) => t.toUpperCase());

  function mostrarMensagem(tipo, texto, detalhe) {
    msg.className = `mensagem mensagem--${tipo}`;
    msg.innerHTML = `<div><strong>${esc(texto)}</strong>${detalhe ? `<small>${esc(detalhe)}</small>` : ''}</div>`;
    msg.classList.remove('oculto');
  }
  function limparMensagem() { msg.classList.add('oculto'); }

  async function chamarAPI(caminho, params) {
    const url = new URL(API + caminho, location.origin);
    if (params) Object.entries(params).forEach(([k, v]) => { if (v !== '' && v != null) url.searchParams.set(k, v); });
    let resp;
    try {
      resp = await fetch(url, { headers: { Accept: 'application/json' } });
    } catch (e) {
      throw { status: 0, erro: 'Não foi possível conectar à API.' };
    }
    let corpo = null;
    try { corpo = await resp.json(); } catch (_) { /* resposta sem JSON */ }
    if (!resp.ok) throw corpo || { status: resp.status, erro: `Erro HTTP ${resp.status}` };
    return corpo;
  }

  // ---- status da API / listas auxiliares ----------------------------------
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

  async function carregarUFs() {
    try {
      const d = await chamarAPI('/ufs');
      const sel = $('#uf');
      d.itens.forEach((u) => {
        const o = document.createElement('option');
        o.value = u.sigla; o.textContent = `${u.sigla} – ${u.nome}`;
        sel.appendChild(o);
      });
    } catch (_) { /* sem UFs não quebra a página */ }
  }

  // Autocompletar de cargos/órgãos (datalist), com debounce
  function autocompletar(inputId, listaId, rota) {
    const input = document.getElementById(inputId);
    const dl = document.getElementById(listaId);
    let timer;
    input.addEventListener('input', () => {
      clearTimeout(timer);
      const q = input.value.trim();
      if (q.length < 2) return;
      timer = setTimeout(async () => {
        try {
          const d = await chamarAPI(rota, { q, limit: 15 });
          dl.innerHTML = d.itens.map((i) => `<option value="${esc(i.nome)}">${i.sigla ? esc(i.sigla) : ''}</option>`).join('');
        } catch (_) { /* ignora */ }
      }, 250);
    });
  }

  // ---- busca ----------------------------------------------------------------
  function lerFiltros() {
    return {
      nome: $('#nome').value.trim(),
      cargo: $('#cargo').value.trim(),
      uf: $('#uf').value,
      orgao: $('#orgao').value.trim(),
      situacao: $('#situacao').value,
      per_page: $('#per_page').value,
    };
  }

  form.addEventListener('submit', (ev) => {
    ev.preventDefault();
    const f = lerFiltros();
    if (!(f.nome || f.cargo || f.uf || f.orgao || f.situacao)) {
      mostrarMensagem('aviso', 'Informe pelo menos um critério de busca.', 'Nome, cargo, UF, órgão ou situação.');
      return;
    }
    buscar(f);
  });

  $('#btn-limpar').addEventListener('click', () => {
    form.reset();
    limparMensagem();
    secResultado.classList.add('oculto');
  });

  async function buscar(filtros) {
    limparMensagem();
    btnBuscar.classList.add('botao--carregando');
    btnBuscar.disabled = true;
    try {
      const d = await chamarAPI('/servidores', filtros);
      renderResultado(d);
    } catch (e) {
      secResultado.classList.add('oculto');
      mostrarMensagem(e.status === 404 ? 'aviso' : 'erro', e.erro || 'Erro inesperado');
    } finally {
      btnBuscar.classList.remove('botao--carregando');
      btnBuscar.disabled = false;
    }
  }

  // ---- renderização -------------------------------------------------------
  function renderResultado(d) {
    secResultado.classList.remove('oculto');
    resumo.textContent = `${fmtInt(d.total)} registro${d.total === 1 ? '' : 's'} · mostrando ${d.itens.length}`;
    corpoTabela.innerHTML = d.itens.map((s) => `
      <tr data-id="${s.id}">
        <td class="nome">${esc(titulo(s.nome))}</td>
        <td>${esc(titulo(s.cargo) || '—')}</td>
        <td>${esc(titulo(s.orgao) || '—')}${s.orgao_sigla ? `<span class="sec">${esc(s.orgao_sigla)}</span>` : ''}</td>
        <td class="centro">${esc(s.uf || '—')}</td>
        <td class="centro">${tagSituacao(s.situacao)}</td>
        <td class="direita">${fmtMoeda(s.valor)}</td>
      </tr>`).join('');
    secResultado.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function tagSituacao(s) {
    const cls = s === 'ATIVO' ? 'tag--ativo' : 'tag--aposentado';
    return `<span class="tag ${cls}">${esc(titulo(s))}</span>`;
  }

  // ---- inicialização ------------------------------------------------------
  carregarStatus();
  carregarUFs();
  autocompletar('cargo', 'lista-cargos', '/cargos');
  autocompletar('orgao', 'lista-orgaos', '/orgaos');
})();
