"""
Interface web para o Conversor de Arquivos.

Funcionalidades:
  1. Iniciar o conversor com configuração de pastas
  2. Visualizar e editar o arquivo de schemas (utils/sped_schemas.json)
  3. Visualizar o relatório gerado (Relatório das Conversões.json)

Instalação:
  pip install flask

Uso:
  python app.py
  Acesse: http://localhost:5000
"""

import json
import logging
import threading
import webbrowser
from pathlib import Path

from flask import Flask, jsonify, render_template_string, request

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

app = Flask(__name__)

SCHEMAS_FILE = Path("utils/sped_schemas.json")
REPORT_FILE  = Path("Relatório das Conversões.json")

# ---------------------------------------------------------------------------
# Estado da execução (imutável por fora; só run_conversor escreve)
# ---------------------------------------------------------------------------

_lock  = threading.Lock()
_state: dict = {"running": False, "done": False, "reports": [], "error": None}


def _get_state() -> dict:
    with _lock:
        return dict(_state)


def _set_state(**kwargs) -> None:
    with _lock:
        _state.update(kwargs)


# ---------------------------------------------------------------------------
# Template HTML
# ---------------------------------------------------------------------------

HTML = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Sistema de Conversão — Gestão Documental</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,500;0,600;1,400&family=Jost:wght@300;400;500;600&family=JetBrains+Mono:wght@400&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    :root {
      --bg:          #0B0C10;
      --surface:     #111318;
      --card:        #161820;
      --border:      #252830;
      --border-hi:   #353840;
      --gold:        #B8973D;
      --gold-light:  #D4AF61;
      --gold-dim:    #7A6028;
      --text:        #DDD8C4;
      --text-muted:  #6B6758;
      --text-dim:    #8C8778;
      --green-bg:    #0D2419;
      --green-text:  #5BC48A;
      --red-bg:      #200E0E;
      --red-text:    #E07070;
      --blue-bg:     #0D1A2E;
      --blue-text:   #8AB8E0;
      --blue-border: #2A5F9A;
      --font-head:   'Cormorant Garamond', Georgia, serif;
      --font-body:   'Jost', system-ui, sans-serif;
      --font-mono:   'JetBrains Mono', monospace;
    }

    body {
      font-family: var(--font-body);
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 3.5rem 1.5rem 5rem;
    }

    /* ── Header ── */
    .header {
      text-align: center;
      margin-bottom: 3rem;
      width: 100%;
      max-width: 920px;
    }

    .header-rule {
      height: 1px;
      background: linear-gradient(90deg, transparent, var(--gold-dim) 20%, var(--gold) 50%, var(--gold-dim) 80%, transparent);
      margin-bottom: 1.75rem;
    }

    .header-rule-bottom {
      height: 1px;
      background: linear-gradient(90deg, transparent, var(--gold-dim) 30%, transparent 70%);
      margin-top: 1.75rem;
    }

    .header-eyebrow {
      font-size: .65rem;
      font-weight: 500;
      letter-spacing: .22em;
      text-transform: uppercase;
      color: var(--gold);
      margin-bottom: .6rem;
    }

    .header h1 {
      font-family: var(--font-head);
      font-size: 2.1rem;
      font-weight: 500;
      color: var(--text);
      letter-spacing: .01em;
      line-height: 1.2;
      margin-bottom: .6rem;
    }

    .header-sub {
      font-size: .72rem;
      color: var(--text-muted);
      letter-spacing: .12em;
      text-transform: uppercase;
    }

    /* ── Navigation ── */
    .nav {
      display: flex;
      border-bottom: 1px solid var(--border);
      margin-bottom: 2.5rem;
      width: 100%;
      max-width: 920px;
    }

    .tab-btn {
      padding: .9rem 2rem;
      border: none;
      border-bottom: 2px solid transparent;
      margin-bottom: -1px;
      cursor: pointer;
      font-family: var(--font-body);
      font-size: .72rem;
      font-weight: 500;
      letter-spacing: .12em;
      text-transform: uppercase;
      background: transparent;
      color: var(--text-muted);
      transition: color .2s, border-color .2s;
    }

    .tab-btn:hover { color: var(--text-dim); }
    .tab-btn.active { color: var(--gold-light); border-bottom-color: var(--gold); }


    .truncate-cell {
    max-width: 80px;         /* Defina a largura máxima que a célula pode ter */
    white-space: nowrap;      /* Impede o texto de quebrar em várias linhas */
    overflow: hidden;         /* Esconde o texto que passar do limite */
    text-overflow: ellipsis;  /* Adiciona os "..." automaticamente no final */
    }

    /* ── Panels ── */
    .panel { display: none; width: 100%; }
    .panel.active { display: block; }

    .panel-title {
      font-family: var(--font-head);
      font-size: 1.45rem;
      font-weight: 500;
      color: var(--text);
      margin-bottom: 1.5rem;
      padding-bottom: .85rem;
      border-bottom: 1px solid var(--border);
    }

    /* ── Cards ── */
    .card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 3px;
      padding: 1.5rem;
      margin-bottom: 1rem;
    }

    .card-title {
      font-size: .62rem;
      font-weight: 600;
      letter-spacing: .18em;
      text-transform: uppercase;
      color: var(--gold);
      margin-bottom: 1.25rem;
    }

    /* ── Form ── */
    .form-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 1.1rem;
      margin-bottom: 1.5rem;
    }

    @media (max-width: 560px) { .form-grid { grid-template-columns: 1fr; } }

    .field { display: flex; flex-direction: column; gap: .3rem; }

    .field label {
      font-size: .68rem;
      font-weight: 500;
      letter-spacing: .12em;
      text-transform: uppercase;
      color: var(--text-muted);
    }

    .field small {
      font-size: .72rem;
      color: var(--text-muted);
      line-height: 1.4;
    }

    input[type="text"] {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 2px;
      padding: .6rem .9rem;
      color: var(--text);
      font-family: var(--font-body);
      font-size: .875rem;
      outline: none;
      transition: border-color .2s;
      margin-top: .2rem;
    }

    input[type="text"]:focus { border-color: var(--gold-dim); }

    /* ── Buttons ── */
    .btn {
      padding: .65rem 1.75rem;
      border: 1px solid;
      border-radius: 2px;
      font-family: var(--font-body);
      font-size: .72rem;
      font-weight: 500;
      letter-spacing: .12em;
      text-transform: uppercase;
      cursor: pointer;
      transition: background .2s, color .2s, transform .1s;
    }

    .btn:active { transform: scale(.98); }

    .btn-primary {
      background: var(--gold);
      border-color: var(--gold);
      color: #0B0C10;
    }
    .btn-primary:hover { background: var(--gold-light); border-color: var(--gold-light); }
    .btn-primary:disabled { background: var(--border); border-color: var(--border); color: var(--text-muted); cursor: not-allowed; }

    .btn-ghost {
      background: transparent;
      border-color: var(--border-hi);
      color: var(--text-dim);
    }
    .btn-ghost:hover { border-color: var(--gold-dim); color: var(--gold); }

    .btn-row { display: flex; gap: .75rem; align-items: center; flex-wrap: wrap; }

    /* ── Status ── */
    .status-box {
      margin-top: 1rem;
      padding: .9rem 1.2rem;
      border-radius: 2px;
      font-size: .825rem;
      border-left: 3px solid;
      display: none;
      line-height: 1.5;
    }

    .status-box.info    { background: var(--blue-bg); border-color: var(--blue-border); color: var(--blue-text); display: block; }
    .status-box.success { background: var(--green-bg); border-color: #1A5C37; color: var(--green-text); display: block; }
    .status-box.failure   { background: var(--red-bg); border-color: #5C1A1A; color: var(--red-text); display: block; }

    /* ── Textarea ── */
    textarea {
      width: 100%;
      min-height: 420px;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 2px;
      padding: .9rem 1rem;
      color: #7DD3E0;
      font-family: var(--font-mono);
      font-size: .8rem;
      line-height: 1.75;
      resize: vertical;
      outline: none;
      transition: border-color .2s;
    }

    textarea:focus { border-color: var(--gold-dim); }

    /* ── Badges ── */
    .badge {
      display: inline-flex;
      align-items: center;
      gap: .25rem;
      padding: .18rem .6rem;
      border-radius: 2px;
      font-size: .7rem;
      font-weight: 600;
      letter-spacing: .04em;
      white-space: nowrap;
    }

    .badge-ok   { background: var(--green-bg); color: var(--green-text); }
    .badge-fail { background: var(--red-bg);   color: var(--red-text); }
    .badge-skip { background: var(--border);    color: var(--text-muted); }

    /* ── Stats bar ── */
    .stats-bar {
      display: none;
      gap: 0;
      margin-bottom: 1.5rem;
      border: 1px solid var(--border);
      border-radius: 3px;
      overflow: hidden;
    }

    .stat-item {
      flex: 1;
      padding: 1rem 1.25rem;
      background: var(--card);
      border-right: 1px solid var(--border);
    }

    .stat-item:last-child { border-right: none; }

    .stat-label {
      font-size: .62rem;
      font-weight: 600;
      letter-spacing: .14em;
      text-transform: uppercase;
      color: var(--text-muted);
      margin-bottom: .35rem;
    }

    .stat-value {
      font-family: var(--font-head);
      font-size: 1.65rem;
      font-weight: 500;
      color: var(--text);
      line-height: 1;
    }

    .stat-value.ok   { color: var(--green-text); }
    .stat-value.fail { color: var(--red-text); }

    /* ── Report Table ── */
    .report-wrap {
      overflow-x: auto;
      border: 1px solid var(--border);
      border-radius: 3px;
    }

    table { width: 100%; border-collapse: collapse; font-size: .825rem; }

    thead tr { border-bottom: 1px solid var(--gold-dim); }

    th {
      background: var(--surface);
      text-align: left;
      padding: .85rem 1rem;
      white-space: nowrap;
      cursor: default;
    }

    .th-label {
      font-size: .65rem;
      font-weight: 600;
      letter-spacing: .14em;
      text-transform: uppercase;
      color: var(--gold);
      display: block;
      margin-bottom: .2rem;
    }

    .th-key {
      font-family: var(--font-mono);
      font-size: .62rem;
      color: var(--text-muted);
      display: block;
    }

    .th-desc {
      font-size: .68rem;
      color: var(--text-muted);
      display: block;
      margin-top: .2rem;
      font-style: italic;
      font-weight: 400;
      letter-spacing: 0;
      text-transform: none;
      max-width: 160px;
      white-space: normal;
      line-height: 1.4;
    }

    td {
      padding: .7rem 1rem;
      border-bottom: 1px solid var(--border);
      color: var(--text);
      vertical-align: middle;
    }

    tr:last-child td { border-bottom: none; }
    tr:hover td { background: rgba(255,255,255,.02); }

    /* ── Pre / JSON ── */
    pre {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 3px;
      padding: 1rem;
      font-family: var(--font-mono);
      font-size: .8rem;
      overflow-x: auto;
      color: #7DD3E0;
      line-height: 1.7;
      max-height: 500px;
      overflow-y: auto;
    }

    /* ── Meta row ── */
    .meta-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 1rem;
    }

    .meta-row small { color: var(--text-muted); font-size: .75rem; }
  </style>
</head>
<body>

<!-- ── Header ── -->
<div class="header">
  <div class="header-rule"></div>
  <div class="header-eyebrow">Gestão Documental</div>
  <h1>Sistema de Conversão de Arquivos</h1>
  <div class="header-sub">Processamento &nbsp;·&nbsp; Validação &nbsp;·&nbsp; Relatório</div>
  <div class="header-rule-bottom"></div>
</div>

<!-- ── Navigation ── -->
<nav class="nav">
  <button class="tab-btn active" data-tab="run">Conversor</button>
  <button class="tab-btn"        data-tab="schemas">Schemas</button>
  <button class="tab-btn"        data-tab="report">Relatório</button>
</nav>

<!-- ══════════ ABA: CONVERSOR ══════════ -->
<div id="tab-run" class="panel active">
  <div class="panel-title">Iniciar Conversão</div>

  <div class="card">
    <div class="card-title">Configuração de Diretórios</div>
    <div class="form-grid">
      <div class="field">
        <label for="input_dir">Pasta de Entrada</label>
        <small>Diretório que contém os arquivos originais a serem convertidos</small>
        <input type="text" id="input_dir" value="Arquivos" placeholder="Arquivos" />
      </div>
      <div class="field">
        <label for="output_dir">Pasta de Saída</label>
        <small>Diretório onde os arquivos convertidos serão gravados</small>
        <input type="text" id="output_dir" value="Tratados" placeholder="Tratados" />
      </div>
      <div class="field">
        <label for="report_file">Arquivo de Relatório</label>
        <small>Nome do arquivo JSON que registrará o histórico das conversões</small>
        <input type="text" id="report_file" value="Relatório das Conversões.json" placeholder="Relatório das Conversões.json" />
      </div>
    </div>
    <div class="btn-row">
      <button class="btn btn-primary" id="btnRun" onclick="runConversor()">Iniciar Conversão</button>
    </div>
  </div>

  <div id="runStatus" class="status-box"></div>
</div>

<!-- ══════════ ABA: SCHEMAS ══════════ -->
<div id="tab-schemas" class="panel">
  <div class="panel-title">Editor de Schemas</div>

  <div class="card">
    <div class="meta-row">
      <div class="card-title" style="margin:0">Arquivo de Configuração</div>
      <small id="schemasPath" style="font-family:var(--font-mono);font-size:.7rem"></small>
    </div>
    <textarea id="schemasEditor" spellcheck="false" placeholder="Carregando schemas…"></textarea>
    <div class="btn-row" style="margin-top:1.1rem">
      <button class="btn btn-primary" onclick="saveSchemas()">Salvar Alterações</button>
      <button class="btn btn-ghost"   onclick="loadSchemas()">Recarregar</button>
    </div>
  </div>

  <div id="schemasStatus" class="status-box"></div>
</div>

<!-- ══════════ ABA: RELATÓRIO ══════════ -->
<div id="tab-report" class="panel">
  <div class="meta-row">
    <div class="panel-title" style="margin:0;border:none;padding:0">Relatório de Conversões</div>
    <button class="btn btn-ghost" style="font-size:.68rem;padding:.5rem 1.1rem" onclick="loadReport()">Atualizar</button>
  </div>

  <!-- Totalizadores -->
  <div id="statsBar" class="stats-bar">
    <div class="stat-item">
      <div class="stat-label">Total Processado</div>
      <div class="stat-value" id="statTotal">—</div>
    </div>
    <div class="stat-item">
      <div class="stat-label">Concluídos com Sucesso</div>
      <div class="stat-value ok" id="statOk">—</div>
    </div>
    <div class="stat-item">
      <div class="stat-label">Com Erro</div>
      <div class="stat-value fail" id="statErr">—</div>
    </div>
    <div class="stat-item">
      <div class="stat-label">Ignorados</div>
      <div class="stat-value" id="statSkip">—</div>
    </div>
  </div>

  <div id="reportContent"></div>
</div>

<script>
// ── Navegação ──
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', function () {
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.getElementById('tab-' + this.dataset.tab).classList.add('active');
    this.classList.add('active');
    if (this.dataset.tab === 'schemas') loadSchemas();
    if (this.dataset.tab === 'report')  loadReport();
  });
});

// ── Status helpers ──
function setStatus(id, msg, type) {
  const el = document.getElementById(id);
  el.textContent = msg;
  el.className = 'status-box ' + type;
}
function clearStatus(id) {
  const el = document.getElementById(id);
  el.className = 'status-box';
  el.textContent = '';
}

// ── Mapeamento de colunas para linguagem acessível ──
const COLUMN_LABELS = {
    find_cols:                      { label: 'Colunas Encontradas',                 desc: '' },
    execution_time_seconds:         { label: 'Tempo de tratamento do arquivo',      desc: '' },
    extension:                      { label: 'Extensão',                            desc: '' },
    failure_reason:                 { label: 'Motivo do Erro',                      desc: '' },
    pasta:                          { label: 'Caminho do Arquivo',                  desc: '' },
    result:                         { label: 'Status',                              desc: '' },
    suggested_solution:             { label: 'Solução Proposta',                    desc: '' },
    warning:                        { label: 'Avisos!',                             desc: '' },

};

function getColInfo(key) {
  const k = key.toLowerCase().replace(/[-\s]/g, '_');
  return COLUMN_LABELS[k] || { label: key, desc: 'Campo técnico do sistema' };
}

// ── Conversor ──
async function runConversor() {
  const btn = document.getElementById('btnRun');
  btn.disabled = true;
  setStatus('runStatus', 'Processando — aguarde enquanto a conversão é executada…', 'info');
  try {
    const res = await fetch('/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        input_dir:   document.getElementById('input_dir').value.trim(),
        output_dir:  document.getElementById('output_dir').value.trim(),
        report_file: document.getElementById('report_file').value.trim(),
      }),
    });
    const data = await res.json();
    if (!res.ok) {
      setStatus('runStatus', 'Erro na execução: ' + (data.failure || res.statusText), 'failure');
    } else {
      const n = (data.reports || []).length;
      setStatus('runStatus', `Conversão concluída — ${n} arquivo(s) processado(s). Acesse a aba Relatório para mais detalhes.`, 'success');
    }
  } catch (err) {
    setStatus('runStatus', 'Falha na comunicação com o servidor: ' + err.message, 'failure');
  } finally {
    btn.disabled = false;
  }
}

// ── Schemas ──
async function loadSchemas() {
  clearStatus('schemasStatus');
  try {
    const res  = await fetch('/schemas');
    const data = await res.json();
    if (!res.ok) {
      setStatus('schemasStatus', data.failure || 'Não foi possível carregar os schemas.', 'failure');
      return;
    }
    document.getElementById('schemasEditor').value = JSON.stringify(data.schemas, null, 2);
    document.getElementById('schemasPath').textContent = data.path;
  } catch (err) {
    setStatus('schemasStatus', err.message, 'failure');
  }
}

async function saveSchemas() {
  clearStatus('schemasStatus');
  let parsed;
  try {
    parsed = JSON.parse(document.getElementById('schemasEditor').value);
  } catch {
    setStatus('schemasStatus', 'JSON inválido — verifique a sintaxe antes de salvar.', 'failure');
    return;
  }
  try {
    const res  = await fetch('/schemas', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ schemas: parsed }),
    });
    const data = await res.json();
    if (!res.ok) {
      setStatus('schemasStatus', data.failure || 'Falha ao salvar.', 'failure');
    } else {
      setStatus('schemasStatus', 'Schemas salvos com sucesso.', 'success');
    }
  } catch (err) {
    setStatus('schemasStatus', err.message, 'failure');
  }
}

// ── Relatório ──
const OK_VALS   = ['ok','sucesso','success','true','sim','concluído','convertido'];
const FAIL_VALS = ['erro','failure','false','não','falha','fail'];
const SKIP_VALS = ['skip','ignorado','ignored'];

function badgeHtml(val) {
  if (typeof val === 'boolean') {
    return val
      ? '<span class="badge badge-ok">✓ Concluído</span>'
      : '<span class="badge badge-fail">✗ Erro</span>';
  }
  const s = String(val ?? '').toLowerCase();
  if (OK_VALS.includes(s))   return `<span class="badge badge-ok">✓ ${val}</span>`;
  if (FAIL_VALS.includes(s)) return `<span class="badge badge-fail">✗ ${val}</span>`;
  if (SKIP_VALS.includes(s)) return `<span class="badge badge-skip">— ${val}</span>`;
  return val ?? '—';
}

async function loadReport() {
  const el = document.getElementById('reportContent');
  el.innerHTML = '<small style="color:var(--text-muted);font-size:.78rem">Carregando relatório…</small>';
  document.getElementById('statsBar').style.display = 'none';

  try {
    const res  = await fetch('/report');
    const data = await res.json();

    if (!res.ok) {
      el.innerHTML = `<div class="status-box failure" style="display:block">${data.failure || 'Relatório indisponível.'}</div>`;
      return;
    }

    const reports = data.reports || [];
    if (!reports.length) {
      el.innerHTML = '<div class="status-box info" style="display:block">Nenhum dado encontrado. Execute uma conversão para gerar o relatório.</div>';
      return;
    }

    // Totalizadores
    const statusKey = Object.keys(reports[0]).find(k =>
      ['status','resultado','result','sucesso','ok','convertido'].includes(k.toLowerCase())
    );

    if (statusKey) {
      let okCount = 0, failCount = 0, skipCount = 0;
      reports.forEach(r => {
        const v = String(r[statusKey] ?? '').toLowerCase();
        if (OK_VALS.includes(v)   || r[statusKey] === true)  okCount++;
        else if (FAIL_VALS.includes(v) || r[statusKey] === false) failCount++;
        else if (SKIP_VALS.includes(v)) skipCount++;
      });
      document.getElementById('statTotal').textContent = reports.length;
      document.getElementById('statOk').textContent    = okCount;
      document.getElementById('statErr').textContent   = failCount;
      document.getElementById('statSkip').textContent  = skipCount;
      document.getElementById('statsBar').style.display = 'flex';
    }

    // Tabela
    const keys = Object.keys(reports[0]);
    const isTable = reports.every(r => typeof r === 'object' && !Array.isArray(r));

    if (isTable && keys.length) {
      let html = '<div class="report-wrap"><table><thead><tr>';
      keys.forEach(k => {
        const info = getColInfo(k);
        html += `<th>
          <span class="th-label">${info.label}</span>
          <span class="th-key">${k}</span>
          <span class="th-desc">${info.desc}</span>
        </th>`;
      });
      html += '</tr></thead><tbody>';
      reports.forEach(row => {
        html += '<tr>';
        keys.forEach(k => { html += `<td class="truncate-cell">${badgeHtml(row[k])}</td>`; });
        html += '</tr>';
      });
      html += '</tbody></table></div>';
      el.innerHTML = html;
    } else {
      el.innerHTML = `<pre>${JSON.stringify(reports, null, 2)}</pre>`;
    }
  } catch (err) {
    el.innerHTML = `<div class="status-box failure" style="display:block">${err.message}</div>`;
  }
}
</script>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------

def _run_conversor(input_dir: str, output_dir: str, report_file: str) -> None:
    """Executa o conversor em thread separada e persiste o relatório."""
    _set_state(running=True, done=False, reports=[], error=None)
    try:
        from controler_trats import conversor  # módulo externo do usuário

        reports = conversor(input_dir, output_dir)

        serialized: list[dict] = []
        for r in reports:
            if hasattr(r, "__dict__"):
                item = {k: str(v) if isinstance(v, Path) else v for k, v in r.__dict__.items()}
            elif isinstance(r, dict):
                item = {k: str(v) if isinstance(v, Path) else v for k, v in r.items()}
            else:
                item = {"raw": str(r)}
            serialized.append(item)

        Path(report_file).write_text(
            json.dumps(serialized, indent=4, ensure_ascii=False),
            encoding="utf-8",
        )
        _set_state(reports=serialized)
        log.info("Conversão concluída: %d arquivo(s).", len(serialized))

    except Exception as exc:
        log.exception("Erro durante a conversão.")
        _set_state(error=str(exc))
    finally:
        _set_state(running=False, done=True)


# ---------------------------------------------------------------------------
# Rotas
# ---------------------------------------------------------------------------

@app.get("/")
def index():
    return render_template_string(HTML)


@app.post("/run")
def run():
    """Inicia o conversor (síncrono — substitua t.join() por polling se necessário)."""
    if _get_state()["running"]:
        return jsonify({"error": "Já existe uma execução em andamento."}), 409

    body        = request.get_json(silent=True) or {}
    input_dir   = body.get("input_dir",   "Arquivos")
    output_dir  = body.get("output_dir",  "Tratados")
    report_file = body.get("report_file", str(REPORT_FILE))

    Path(output_dir).mkdir(parents=True, exist_ok=True)

    t = threading.Thread(
        target=_run_conversor,
        args=(input_dir, output_dir, report_file),
        daemon=True,
    )
    t.start()
    t.join()  # síncrono — troque por polling assíncrono para arquivos grandes

    state = _get_state()
    if state["error"]:
        return jsonify({"error": state["error"]}), 500

    return jsonify({"reports": state["reports"]})


@app.get("/schemas")
def get_schemas():
    """Retorna o conteúdo de utils/sped_schemas.json."""
    if not SCHEMAS_FILE.exists():
        return jsonify({"error": f"Arquivo não encontrado: {SCHEMAS_FILE}"}), 404
    try:
        data = json.loads(SCHEMAS_FILE.read_text(encoding="utf-8"))
        return jsonify({"schemas": data, "path": str(SCHEMAS_FILE)})
    except json.JSONDecodeError as exc:
        return jsonify({"error": f"JSON inválido: {exc}"}), 422


@app.put("/schemas")
def put_schemas():
    """Sobrescreve utils/sped_schemas.json com o payload recebido."""
    body = request.get_json(silent=True)
    if body is None or "schemas" not in body:
        return jsonify({"error": "Payload inválido — envie {\"schemas\": ...}"}), 400
    try:
        SCHEMAS_FILE.parent.mkdir(parents=True, exist_ok=True)
        SCHEMAS_FILE.write_text(
            json.dumps(body["schemas"], indent=4, ensure_ascii=False),
            encoding="utf-8",
        )
        log.info("Schemas salvos em %s.", SCHEMAS_FILE)
        return jsonify({"ok": True, "path": str(SCHEMAS_FILE)})
    except OSError as exc:
        return jsonify({"error": str(exc)}), 500


@app.get("/report")
def get_report():
    """Retorna o relatório mais recente."""
    # Localização pode variar — tenta o padrão e o estado atual
    path = Path(_get_state().get("report_file", "") or REPORT_FILE)
    if not path.exists():
        path = REPORT_FILE
    if not path.exists():
        return jsonify({"error": "Nenhum relatório encontrado. Execute o conversor primeiro."}), 404
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return jsonify({"reports": data, "path": str(path)})
    except json.JSONDecodeError as exc:
        return jsonify({"error": f"Relatório com JSON inválido: {exc}"}), 422


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 52)
    print("  Conversor de Arquivos — Interface Web")
    print("  Acesse: http://localhost:5000")
    print("=" * 52)
    threading.Timer(1.2, lambda: webbrowser.open("http://localhost:5000")).start()
    app.run(debug=False, port=5000)