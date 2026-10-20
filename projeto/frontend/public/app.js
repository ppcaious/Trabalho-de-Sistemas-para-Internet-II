(() => {
  'use strict';

  const API = '/api';
  const $ = (sel) => document.querySelector(sel);

  // Estado da busca atual (para paginação)
  const estado = { filtros: null, page: 1, totalPaginas: 1, modo: 'exata' };

  // Elementos
  const form = $('#form-busca');
  const btnBuscar = $('#btn-buscar');
  const msg = $('#mensagem');
  const secResultado = $('#resultado');
  const registroUnico = $('#registro-unico');
  const lista = $('#lista');
  const corpoTabela = $('#tabela-corpo');
  const resumo = $('#resultado-resumo');
  const pgInfo = $('#pg-info');
  const modal = $('#modal');

  // Utilidades
  const fmtMoeda = (v) => v == null ? '—' : Number(v).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const fmtData = (iso) => iso ? new Date(iso + 'T00:00:00').toLocaleDateString('pt-BR') : '—';
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
      throw { status: 0, erro: 'Não foi possível conectar à API.', detalhes: { dica: 'Verifique se os contêineres estão no ar (docker compose ps).' } };
    }
    let corpo = null;
    try { corpo = await resp.json(); } catch (_) { /* resposta sem JSON */ }
    if (!resp.ok) throw corpo || { status: resp.status, erro: `Erro HTTP ${resp.status}` };
    return corpo;
  }

  // status da API / listas auxiliares
  async function carregarStatus() {
    const el = $('#estado-api');
    try {
      const h = await chamarAPI('/health');
      el.classList.add('estado--ok');
      el.querySelector('.estado__texto').textContent = `API online · ${fmtInt(h.total_servidores)} registros`;
      renderEstatisticas(h);
    } catch (e) {
      el.classList.add('estado--erro');
      el.querySelector('.estado__texto').textContent = 'API indisponível';
    }
  }

  function renderEstatisticas(h) {
    $('#estatisticas').innerHTML = [
      ['Total de registros', h.total_servidores],
      ['Servidores ativos', h.ativos],
      ['Aposentados', h.aposentados],
    ].map(([r, v]) => `<div class="cartao estat"><div class="estat__valor">${fmtInt(v)}</div><div class="estat__rotulo">${r}</div></div>`).join('');
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

  // Abas (nome exato x similar)
  document.querySelectorAll('.aba').forEach((aba) => {
    aba.addEventListener('click', () => {
      document.querySelectorAll('.aba').forEach((a) => { a.classList.remove('aba--ativa'); a.setAttribute('aria-selected', 'false'); });
      aba.classList.add('aba--ativa'); aba.setAttribute('aria-selected', 'true');
      estado.modo = aba.dataset.modo;
      const similar = estado.modo === 'similar';
      $('#campo-nome').classList.toggle('oculto', similar);
      $('#campo-similar').classList.toggle('oculto', !similar);
      $('#campo-limit').classList.toggle('oculto', !similar);
      (similar ? $('#similar') : $('#nome')).focus();
    });
  });

  // Busca
  function lerFiltros() {
    const f = {
      cargo: $('#cargo').value.trim(),
      uf: $('#uf').value,
      orgao: $('#orgao').value.trim(),
      situacao: $('#situacao').value,
      per_page: $('#per_page').value,
    };
    if (estado.modo === 'similar') {
      f.similar = $('#similar').value.trim();
      f.limit = $('#limit').value;
    } else {
      f.nome = $('#nome').value.trim();
    }
    return f;
  }

  form.addEventListener('submit', (ev) => {
    ev.preventDefault();
    const f = lerFiltros();
    const temCriterio = f.nome || f.similar || f.cargo || f.uf || f.orgao || f.situacao;
    if (!temCriterio) {
      mostrarMensagem('aviso', 'Informe pelo menos um critério de busca.', 'Nome, cargo, UF, órgão ou situação.');
      return;
    }
    estado.filtros = f;
    estado.page = 1;
    buscar();
  });

  $('#btn-limpar').addEventListener('click', () => {
    form.reset();
    $('#limit').value = 100;
    limparMensagem();
    secResultado.classList.add('oculto');
    estado.filtros = null;
  });

  async function buscar() {
    limparMensagem();
    btnBuscar.classList.add('botao--carregando');
    btnBuscar.disabled = true;
    try {
      const d = await chamarAPI('/servidores', { ...estado.filtros, page: estado.page });
      renderResultado(d);
    } catch (e) {
      secResultado.classList.add('oculto');
      const tipo = e.status === 404 ? 'aviso' : e.status === 429 || e.status === 503 || e.status === 504 ? 'aviso' : 'erro';
      const detalhe = e.detalhes?.dica || (e.detalhes?.ufs_validas ? `UFs válidas: ${e.detalhes.ufs_validas.join(', ')}` : '') || (e.detalhes?.permitidos ? `Parâmetros aceitos: ${e.detalhes.permitidos.join(', ')}` : '');
      mostrarMensagem(tipo, e.erro || 'Erro inesperado', detalhe);
    } finally {
      btnBuscar.classList.remove('botao--carregando');
      btnBuscar.disabled = false;
    }
  }

  // Renderização
  function renderResultado(d) {
    secResultado.classList.remove('oculto');
    estado.totalPaginas = d.total_paginas;

    const partes = [`${fmtInt(d.total)} registro${d.total === 1 ? '' : 's'}`];
    if (d.filtros.similar) partes.push(`${d.filtros.limit} nomes mais parecidos`);
    resumo.textContent = partes.join(' · ');

    if (d.registro_unico) {
      lista.classList.add('oculto');
      registroUnico.classList.remove('oculto');
      registroUnico.innerHTML = `<div class="detalhe__topo"><h3>${esc(titulo(d.itens[0].nome))}</h3>${tagSituacao(d.itens[0].situacao)}</div>${htmlDetalhes(d.itens[0])}`;
      return;
    }

    registroUnico.classList.add('oculto');
    lista.classList.remove('oculto');
    corpoTabela.innerHTML = d.itens.map((s) => `
      <tr data-id="${s.id}">
        <td class="nome">${esc(titulo(s.nome))}${s.similaridade != null ? `<span class="sec">similaridade ${(s.similaridade * 100).toFixed(0)}%</span>` : ''}</td>
        <td>${esc(titulo(s.cargo) || '—')}</td>
        <td>${esc(titulo(s.orgao) || '—')}${s.orgao_sigla ? `<span class="sec">${esc(s.orgao_sigla)}</span>` : ''}</td>
        <td class="centro">${esc(s.uf || '—')}</td>
        <td class="centro">${tagSituacao(s.situacao)}</td>
        <td class="direita">${fmtMoeda(s.valor)}</td>
        <td class="direita"><button type="button" class="botao botao--icone" data-detalhe="${s.id}" title="Ver detalhes">Ver</button></td>
      </tr>`).join('');

    pgInfo.textContent = `Página ${d.page} de ${d.total_paginas}`;
    $('#pg-primeira').disabled = $('#pg-anterior').disabled = d.page <= 1;
    $('#pg-proxima').disabled = $('#pg-ultima').disabled = d.page >= d.total_paginas;
    secResultado.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function tagSituacao(s) {
    const cls = s === 'ATIVO' ? 'tag--ativo' : 'tag--aposentado';
    return `<span class="tag ${cls}">${esc(titulo(s))}</span>`;
  }

  function htmlDetalhes(s) {
    const campos = [
      ['Nome', titulo(s.nome)], ['CPF', s.cpf], ['Matrícula', s.matricula],
      ['Situação', titulo(s.situacao)], ['Cargo', titulo(s.cargo)],
      ['Órgão', titulo(s.orgao)], ['Sigla do órgão', s.orgao_sigla], ['UF', s.uf],
      ['Código da carreira', s.codigo_carreira], ['Classe / Padrão', [s.classe, s.padrao].filter(Boolean).join(' / ')],
      ['Referência / Nível', [s.referencia, s.nivel].filter(Boolean).join(' / ')],
      ['Tipo de aposentadoria', titulo(s.tipo_aposentadoria)], ['Fundamento legal', s.fundamento_legal],
      ['Diploma legal', s.diploma_legal], ['Data da inatividade', fmtData(s.data_inatividade)],
      ['Ingresso no serviço público', titulo(s.ocorrencia_ingresso)], ['Data de ingresso', fmtData(s.data_ingresso)],
      [s.situacao === 'ATIVO' ? 'Remuneração (R$)' : 'Provento (R$)', fmtMoeda(s.valor)],
      ['Mês de referência', s.mes_referencia], ['ID', s.id],
    ].filter(([, v]) => v != null && v !== '' && v !== '—');
    return `<dl class="lista-dados">${campos.map(([k, v]) => `<div><dt>${esc(k)}</dt><dd>${esc(v)}</dd></div>`).join('')}</dl>`;
  }

  // Paginação
  const irPara = (p) => { if (p >= 1 && p <= estado.totalPaginas && p !== estado.page) { estado.page = p; buscar(); } };
  $('#pg-primeira').addEventListener('click', () => irPara(1));
  $('#pg-anterior').addEventListener('click', () => irPara(estado.page - 1));
  $('#pg-proxima').addEventListener('click', () => irPara(estado.page + 1));
  $('#pg-ultima').addEventListener('click', () => irPara(estado.totalPaginas));

  // Modal de detalhes
  corpoTabela.addEventListener('click', async (ev) => {
    const btn = ev.target.closest('[data-detalhe]');
    if (!btn) return;
    try {
      const s = await chamarAPI(`/servidores/${btn.dataset.detalhe}`);
      $('#modal-titulo').innerHTML = `${esc(titulo(s.nome))} ${tagSituacao(s.situacao)}`;
      $('#modal-corpo').innerHTML = htmlDetalhes(s);
      modal.classList.remove('oculto');
    } catch (e) {
      mostrarMensagem('erro', e.erro || 'Não foi possível carregar os detalhes.');
    }
  });
  modal.querySelectorAll('[data-fechar]').forEach((el) => el.addEventListener('click', () => modal.classList.add('oculto')));
  document.addEventListener('keydown', (ev) => { if (ev.key === 'Escape') modal.classList.add('oculto'); });

  // Inicialização
  carregarStatus();
  carregarUFs();
  autocompletar('cargo', 'lista-cargos', '/cargos');
  autocompletar('orgao', 'lista-orgaos', '/orgaos');
})();
