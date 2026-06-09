"""
Gerador de relatório HTML de *linhagem* de arquivos.

Lê o CSV de resultados do tratamento (separador ';') e produz um HTML que mostra,
de forma visual e intuitiva, a ligação entre cada arquivo ORIGINAL e todos os
arquivos que foram GERADOS a partir dele — pensado para um leitor leigo (advogado).

Cada arquivo original vira um "bloco de linhagem": o original à esquerda, ligado
por linhas curvas a cada arquivo gerado à direita.

Colunas esperadas no CSV:
    (índice), original_path, path, extension, execution_time_seconds, result,
    find_cols, warning, failure_reason, suggested_solution

Dependências:
    pip install pandas

Uso:
    python relatorio_conexoes.py entrada.csv -o saida.html
"""

from __future__ import annotations

import argparse
import html
import json
import logging
from datetime import datetime
from pathlib import Path
import os
import pandas as pd

logger = logging.getLogger(__name__)

EXPECTED_COLS = [
    "original_path", "path", "extension", "execution_time_seconds", "result",
    "find_cols", "warning", "failure_reason", "suggested_solution",
]


# ── Normalização ────────────────────────────────────────────────────────────
def _normalizar(df: pd.DataFrame) -> pd.DataFrame:
    """Garante colunas, tipos e valores limpos."""
    df = df.copy()

    # Remove coluna de índice anônima (primeira coluna sem nome)
    if df.columns[0] in ("", "Unnamed: 0"):
        df = df.iloc[:, 1:]

    for col in EXPECTED_COLS:
        if col not in df.columns:
            df[col] = ""

    df["result"] = df["result"].fillna("unknown").astype(str).str.lower()
    df["execution_time_seconds"] = (
        pd.to_numeric(df["execution_time_seconds"], errors="coerce").fillna(0)
    )
    # Sem original_path não dá para montar a linhagem
    df["original_path"] = df["original_path"].fillna("(origem desconhecida)").astype(str)
    return df


# ── Helpers de formatação ─────────────────────────────────────────────────────
def _nome(path_str: str) -> str:
    return str(path_str).replace("\\", "/").rstrip("/").split("/")[-1] or str(path_str)


def _vazio(v) -> bool:
    return str(v).strip().lower() in ("", "nan", "none")


def _fmt_time(t: float) -> str:
    t = float(t)
    if t <= 0:
        return "—"
    if t < 1:
        return f"{t * 1000:.0f} ms"
    return f"{t:.2f} s"


def _fmt_cols(raw) -> str:
    """Renderiza a lista de colunas como tags."""
    if _vazio(raw) or str(raw).strip() == "[]":
        return '<em class="muted">Nenhuma coluna identificada</em>'
    try:
        cols = json.loads(str(raw).replace("'", '"'))
        cols = [c for c in cols if c]
    except (json.JSONDecodeError, TypeError):
        return html.escape(str(raw))
    if not cols:
        return '<em class="muted">Nenhuma coluna identificada</em>'
    return "".join(f'<span class="col-tag">{html.escape(str(c))}</span>' for c in cols)


def _badge(result: str) -> str:
    if result == "success":
        return '<span class="badge success">✔ Sucesso</span>'
    if result == "failure":
        return '<span class="badge failure">✖ Falha</span>'
    return '<span class="badge warning">⚠ Outro</span>'


def _ext_pretty(ext: str) -> str:
    return html.escape(str(ext).lstrip(".").upper() or "?")


# ── Montagem de um nó gerado ───────────────────────────────────────────────────
def _target_node(row: pd.Series, idx: int, src_id: str) -> str:
    nome = html.escape(_nome(row["path"]))
    ext = _ext_pretty(row["extension"]) if False else _ext_pretty(row["extension"])
    tempo = _fmt_time(row["execution_time_seconds"])
    badge = _badge(row["result"])
    colunas = _fmt_cols(row["find_cols"])
    path_full = html.escape(str(row["path"]))

    extra = ""
    if not _vazio(row["failure_reason"]):
        extra += (
            '<div class="detail-row"><span class="detail-label">⚠ Motivo da falha</span>'
            f'<span class="detail-val">{html.escape(str(row["failure_reason"]))}</span></div>'
        )
    if not _vazio(row["suggested_solution"]):
        extra += (
            '<div class="detail-row"><span class="detail-label">💡 Sugestão</span>'
            f'<span class="detail-val">{html.escape(str(row["suggested_solution"]))}</span></div>'
        )
    if not _vazio(row["warning"]):
        extra += (
            '<div class="detail-row"><span class="detail-label">📋 Aviso</span>'
            f'<span class="detail-val">{html.escape(str(row["warning"]))}</span></div>'
        )

    is_fail = "is-failure" if row["result"] == "failure" else ""
    busca = f"{nome} {path_full}".lower()

    return f"""
      <div class="target-node {is_fail}" data-src="{src_id}" data-target-idx="{idx}" data-search="{html.escape(busca)}">
        <div class="tn-head">
          <span class="ext-pill">{ext}</span>
          <span class="tn-name" title="{path_full}">{nome}</span>
          <span class="tn-meta">
            <span class="time-chip">⏱ {tempo}</span>
            {badge}
          </span>
        </div>
        <div class="tn-path">{path_full}</div>
        <div class="cols-block">{colunas}</div>
        {('<div class="extra-details">' + extra + '</div>') if extra else ''}
      </div>"""


# ── Montagem de um bloco de linhagem (1 original + seus gerados) ───────────────
def _lineage_block(src_idx: int, original_path: str, grupo: pd.DataFrame) -> str:
    src_id = f"src-{src_idx}"
    nome_orig = html.escape(_nome(original_path))
    path_orig = html.escape(str(original_path))
    ext_orig = _ext_pretty(Path(str(original_path)).suffix)

    total = len(grupo)
    ok = int((grupo["result"] == "success").sum())
    fail = int((grupo["result"] == "failure").sum())

    targets = "".join(
        _target_node(row, i, src_id) for i, (_, row) in enumerate(grupo.iterrows())
    )

    fail_chip = f'<span class="stat-chip fail">{fail} falha(s)</span>' if fail else ""
    busca_orig = f"{nome_orig} {path_orig}".lower()

    return f"""
    <section class="lineage" data-lineage data-search="{html.escape(busca_orig)}">
      <svg class="connectors" aria-hidden="true"></svg>

      <div class="source-col">
        <div class="source-node" id="{src_id}">
          <div class="sn-icon">📄</div>
          <span class="ext-pill src-ext">{ext_orig}</span>
          <div class="sn-name" title="{path_orig}">{nome_orig}</div>
          <div class="sn-path">{path_orig}</div>
          <div class="sn-stats">
            <span class="stat-chip total">{total} gerado(s)</span>
            <span class="stat-chip ok">{ok} ok</span>
            {fail_chip}
          </div>
        </div>
      </div>

      <div class="targets-col">
        {targets}
      </div>
    </section>"""


# ── Função principal ───────────────────────────────────────────────────────────
def gerar_relatorio_conexoes(
    df: pd.DataFrame,
    output_path: str | Path | None = None,
    back_url: str | None = None,
) -> str:
    """Gera o HTML de linhagem dos arquivos.

    Args:
        df: DataFrame com os resultados do tratamento.
        output_path: Se informado, salva o HTML nesse caminho. Se ``None``
            (padrão), apenas retorna a string — útil para servir via Flask.
        back_url: Se informado, renderiza um link "Voltar" no topo apontando
            para essa URL (usado quando servido dentro de uma aplicação web).

    Returns:
        O documento HTML como string.
    """
    df = _normalizar(df)

    total_arq = len(df)
    total_orig = df["original_path"].nunique()
    sucessos = int((df["result"] == "success").sum())
    falhas = int((df["result"] == "failure").sum())
    tempo_total = float(df["execution_time_seconds"].sum())
    pct = int(round((sucessos / total_arq) * 100)) if total_arq else 0
    data_hora = datetime.now().strftime("%d/%m/%Y às %H:%M")

    # Agrupa por original preservando a ordem de aparição
    blocos = ""
    for i, (orig, grupo) in enumerate(df.groupby("original_path", sort=False)):
        blocos += _lineage_block(i, orig, grupo)

    back_link = ""
    if back_url:
        back_link = (
            f'<a class="back-link" href="{html.escape(str(back_url))}">'
            '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">'
            '<path d="M19 12H5M12 19l-7-7 7-7"/></svg> Voltar ao sistema</a>'
        )

    html_doc = _TEMPLATE.format(
        blocos=blocos,
        back_link=back_link,
        total_arq=total_arq,
        total_orig=total_orig,
        sucessos=sucessos,
        falhas=falhas,
        tempo_total=_fmt_time(tempo_total),
        pct=pct,
        data_hora=data_hora,
    )
    
    if output_path is not None:
        output_path = os.path.join(os.getcwd(), output_path)
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html_doc, encoding="utf-8")
        logger.info("Relatório salvo em: %s", out)
        print(f"✅ Relatório salvo em: {out}")
    return html_doc


# ── Template HTML (chaves CSS escapadas com {{ }}) ─────────────────────────────
_TEMPLATE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Linhagem dos Arquivos · Relatório de Conexões</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Sora:wght@300;400;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<style>
:root {{
  --bg:#070e1a; --surface:#0c1628; --surface2:#101d34;
  --border:#1a2d4d; --border-light:#233d68;
  --text:#e8eef8; --text-muted:#7a9cc4; --text-dim:#3a5272;
  --ok:#c9a84c; --ok-bg:#1e1608; --ok-border:#3d2e0f;
  --fail:#e05252; --fail-bg:#220d0d; --fail-border:#3d1515;
  --warn:#e8b84b; --warn-bg:#1e1608;
  --accent:#4d9de0; --accent2:#c9a84c; --purple:#7ab8f5;
  --line:#c9a84c;
  --radius:12px; --radius-sm:7px;
}}
*,*::before,*::after {{ box-sizing:border-box; margin:0; padding:0; }}
body {{ background:var(--bg); color:var(--text); font-family:'Sora',sans-serif;
  font-size:14px; line-height:1.6; min-height:100vh; }}

/* Topo */
.topbar {{ background:linear-gradient(135deg,#070e1a 0%,#0c1628 50%,#070e1a 100%);
  border-bottom:1px solid var(--border); padding:32px 40px 28px; position:relative; overflow:hidden; }}
.topbar::before {{ content:''; position:absolute; inset:0;
  background:radial-gradient(ellipse 60% 80% at 80% -20%, rgba(201,168,76,.10) 0%, transparent 70%); pointer-events:none; }}
.topbar-inner {{ max-width:1280px; margin:0 auto; position:relative; z-index:1; }}
.report-label {{ font-size:11px; font-weight:600; letter-spacing:.15em; text-transform:uppercase; color:var(--accent); margin-bottom:6px; }}
.back-link {{ display:inline-flex; align-items:center; gap:6px; color:var(--text-muted);
  text-decoration:none; font-size:12px; font-weight:600; letter-spacing:.04em;
  margin-bottom:14px; transition:color .2s; }}
.back-link:hover {{ color:var(--accent2); }}
.back-link svg {{ width:14px; height:14px; }}
h1 {{ font-size:clamp(22px,3vw,32px); font-weight:700; letter-spacing:-.02em; margin-bottom:4px; }}
.report-date {{ color:var(--text-muted); font-size:13px; }}

/* Sumário */
.summary-row {{ max-width:1280px; margin:28px auto 14px; padding:0 40px;
  display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:14px; }}
.summary-card {{ background:var(--surface); border:1px solid var(--border); border-radius:var(--radius);
  padding:18px 20px; display:flex; flex-direction:column; gap:4px; transition:border-color .2s,transform .2s; }}
.summary-card:hover {{ border-color:var(--border-light); transform:translateY(-2px); }}
.card-num {{ font-size:28px; font-weight:700; font-family:'JetBrains Mono',monospace; letter-spacing:-.03em; }}
.card-label {{ font-size:11px; color:var(--text-muted); font-weight:600; letter-spacing:.05em; text-transform:uppercase; }}
.c-orig .card-num {{ color:var(--accent); }}
.c-total .card-num {{ color:var(--accent2); }}
.c-ok .card-num {{ color:var(--ok); }}
.c-fail .card-num {{ color:var(--fail); }}
.c-time .card-num {{ color:var(--purple); font-size:22px; }}

/* Barra de busca + legenda */
.controls {{ max-width:1280px; margin:0 auto 8px; padding:0 40px; display:flex; gap:16px; align-items:center; flex-wrap:wrap; }}
.search-box {{ flex:1; min-width:220px; position:relative; }}
.search-box input {{ width:100%; background:var(--surface); border:1px solid var(--border); border-radius:99px;
  color:var(--text); font-family:'Sora',sans-serif; font-size:13px; padding:10px 16px 10px 38px; outline:none; transition:border-color .2s; }}
.search-box input:focus {{ border-color:var(--accent); }}
.search-box::before {{ content:'🔎'; position:absolute; left:14px; top:50%; transform:translateY(-50%); font-size:13px; opacity:.6; }}
.legend {{ display:flex; gap:14px; flex-wrap:wrap; font-size:12px; color:var(--text-muted); }}
.legend span {{ display:inline-flex; align-items:center; gap:6px; }}
.legend .dot {{ width:10px; height:10px; border-radius:3px; display:inline-block; }}
.legend .dot.orig {{ background:var(--accent); }}
.legend .dot.gen {{ background:var(--ok); }}
.legend .dot.line {{ width:18px; height:2px; border-radius:0; background:var(--line); }}

.no-results {{ max-width:1280px; margin:40px auto; padding:0 40px; text-align:center; color:var(--text-dim); display:none; }}

/* Conteúdo */
.main {{ max-width:1280px; margin:18px auto; padding:0 40px 60px; }}

.lineage {{ position:relative; display:flex; align-items:center; gap:0;
  margin-bottom:28px; background:var(--surface); border:1px solid var(--border);
  border-radius:var(--radius); padding:24px; overflow:hidden;
  animation:fadeUp .4s ease both; }}
.connectors {{ position:absolute; inset:0; width:100%; height:100%; pointer-events:none; z-index:0; }}

.source-col {{ flex:0 0 290px; z-index:1; }}
.source-node {{ background:var(--surface2); border:1px solid var(--accent);
  border-radius:var(--radius); padding:18px; position:relative;
  box-shadow:0 0 0 1px rgba(77,157,224,.12), 0 8px 30px rgba(0,0,0,.35); }}
.sn-icon {{ font-size:26px; margin-bottom:6px; }}
.sn-name {{ font-size:15px; font-weight:700; color:var(--text); word-break:break-word; margin-bottom:6px; line-height:1.3; }}
.sn-path {{ font-size:10.5px; color:var(--text-dim); font-family:'JetBrains Mono',monospace;
  word-break:break-all; margin-bottom:12px; max-height:48px; overflow:hidden; }}
.sn-stats {{ display:flex; flex-wrap:wrap; gap:6px; }}

.targets-col {{ flex:1; display:flex; flex-direction:column; gap:12px; padding-left:64px; z-index:1; min-width:0; }}

.target-node {{ background:var(--bg); border:1px solid var(--border); border-left:3px solid var(--ok);
  border-radius:var(--radius-sm); padding:13px 15px; transition:border-color .2s,box-shadow .2s,transform .15s; }}
.target-node:hover {{ border-color:var(--border-light); box-shadow:0 4px 20px rgba(0,0,0,.3); transform:translateX(2px); }}
.target-node.is-failure {{ border-left-color:var(--fail); }}

.tn-head {{ display:flex; align-items:center; gap:8px; flex-wrap:wrap; margin-bottom:6px; }}
.ext-pill {{ font-size:10px; font-weight:700; padding:2px 8px; border-radius:4px;
  background:rgba(77,157,224,.12); color:var(--accent); border:1px solid rgba(77,157,224,.25);
  text-transform:uppercase; white-space:nowrap; font-family:'JetBrains Mono',monospace; letter-spacing:.05em; }}
.ext-pill.src-ext {{ position:absolute; top:18px; right:18px; }}
.tn-name {{ font-size:13.5px; font-weight:600; color:var(--text); flex:1; min-width:80px;
  white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
.tn-meta {{ display:flex; align-items:center; gap:8px; flex-shrink:0; }}
.time-chip {{ font-size:11px; font-family:'JetBrains Mono',monospace; color:var(--text-muted);
  background:var(--surface2); border:1px solid var(--border); padding:2px 9px; border-radius:99px; }}

.badge {{ font-size:11px; font-weight:700; padding:3px 11px; border-radius:99px; letter-spacing:.04em; }}
.badge.success {{ background:var(--ok-bg); color:var(--ok); border:1px solid var(--ok-border); }}
.badge.failure {{ background:var(--fail-bg); color:var(--fail); border:1px solid var(--fail-border); }}
.badge.warning {{ background:var(--warn-bg); color:var(--warn); border:1px solid rgba(232,184,75,.3); }}

.tn-path {{ font-size:10.5px; color:var(--text-dim); font-family:'JetBrains Mono',monospace;
  white-space:nowrap; overflow:hidden; text-overflow:ellipsis; margin-bottom:9px; }}
.cols-block {{ display:flex; flex-wrap:wrap; gap:5px; }}
.col-tag {{ font-size:11px; padding:2px 9px; background:rgba(122,184,245,.08);
  border:1px solid rgba(122,184,245,.2); color:var(--purple); border-radius:5px;
  font-family:'JetBrains Mono',monospace; white-space:nowrap; }}
.muted {{ color:var(--text-dim); font-style:italic; font-size:12px; }}

.stat-chip {{ font-size:11px; font-weight:600; padding:3px 10px; border-radius:99px; letter-spacing:.04em; }}
.stat-chip.ok {{ background:var(--ok-bg); color:var(--ok); border:1px solid var(--ok-border); }}
.stat-chip.fail {{ background:var(--fail-bg); color:var(--fail); border:1px solid var(--fail-border); }}
.stat-chip.total {{ background:var(--surface); color:var(--text-muted); border:1px solid var(--border); }}

.extra-details {{ margin-top:11px; border-top:1px solid var(--border); padding-top:9px;
  display:flex; flex-direction:column; gap:6px; }}
.detail-row {{ display:flex; gap:10px; align-items:flex-start; flex-wrap:wrap; }}
.detail-label {{ font-size:11px; font-weight:600; color:var(--warn); white-space:nowrap; min-width:130px; }}
.detail-val {{ font-size:12px; color:var(--text-muted); flex:1; }}

.footer {{ text-align:center; padding:24px 40px; border-top:1px solid var(--border);
  color:var(--text-dim); font-size:12px; max-width:1280px; margin:0 auto; }}

@keyframes fadeUp {{ from {{ opacity:0; transform:translateY(16px); }} to {{ opacity:1; transform:translateY(0); }} }}

/* Responsivo: empilha e desenha conector vertical */
@media (max-width:820px) {{
  .topbar,.summary-row,.controls,.main,.no-results {{ padding-left:16px; padding-right:16px; }}
  .summary-row {{ grid-template-columns:1fr 1fr; }}
  .lineage {{ flex-direction:column; align-items:stretch; }}
  .source-col {{ flex:none; margin-bottom:20px; }}
  .targets-col {{ padding-left:18px; border-left:2px dashed var(--line); margin-left:18px; }}
  .connectors {{ display:none; }}
}}
</style>
</head>
<body>

<header class="topbar">
  <div class="topbar-inner">
    {back_link}
    <div class="report-label">Relatório de Linhagem</div>
    <h1>De onde veio cada arquivo</h1>
    <div class="report-date">Gerado em {data_hora} · cada documento original aparece ligado aos arquivos extraídos dele</div>
  </div>
</header>

<div class="summary-row">
  <div class="summary-card c-orig"><span class="card-num">{total_orig}</span><span class="card-label">Arquivos originais</span></div>
  <div class="summary-card c-total"><span class="card-num">{total_arq}</span><span class="card-label">Arquivos gerados</span></div>
  <div class="summary-card c-ok"><span class="card-num">{sucessos}</span><span class="card-label">Gerados com sucesso</span></div>
  <div class="summary-card c-fail"><span class="card-num">{falhas}</span><span class="card-label">Com falhas</span></div>
  <div class="summary-card c-time"><span class="card-num">{tempo_total}</span><span class="card-label">Tempo total</span></div>
</div>

<div class="controls">
  <div class="search-box"><input type="text" id="search" placeholder="Buscar por nome de arquivo ou caminho…" autocomplete="off"></div>
  <div class="legend">
    <span><span class="dot orig"></span> Arquivo original</span>
    <span><span class="dot gen"></span> Arquivo gerado</span>
    <span><span class="dot line"></span> Origem → resultado</span>
  </div>
</div>

<div class="no-results" id="no-results">Nenhum arquivo encontrado para a busca.</div>

<main class="main" id="main">
{blocos}
</main>

<footer class="footer">
  Relatório gerado automaticamente · {total_orig} originais → {total_arq} arquivos · {data_hora}
</footer>

<script>
// Desenha as linhas curvas ligando cada original aos arquivos gerados.
function drawConnectors() {{
  var stacked = window.matchMedia('(max-width:820px)').matches;
  document.querySelectorAll('.lineage').forEach(function(block) {{
    var svg = block.querySelector('.connectors');
    if (!svg) return;
    svg.innerHTML = '';
    if (stacked) return;

    var src = block.querySelector('.source-node');
    var targets = block.querySelectorAll('.target-node');
    if (!src || !targets.length) return;

    var base = block.getBoundingClientRect();
    var s = src.getBoundingClientRect();
    var x1 = s.right - base.left;
    var y1 = s.top + s.height / 2 - base.top;

    targets.forEach(function(t) {{
      if (t.style.display === 'none') return;
      var r = t.getBoundingClientRect();
      var x2 = r.left - base.left;
      var y2 = r.top + r.height / 2 - base.top;
      var midx = x1 + (x2 - x1) * 0.5;
      var d = 'M ' + x1 + ' ' + y1 +
              ' C ' + midx + ' ' + y1 + ', ' + midx + ' ' + y2 + ', ' + x2 + ' ' + y2;
      var fail = t.classList.contains('is-failure');
      var path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      path.setAttribute('d', d);
      path.setAttribute('fill', 'none');
      path.setAttribute('stroke', fail ? '#e05252' : '#c9a84c');
      path.setAttribute('stroke-width', '1.6');
      path.setAttribute('stroke-opacity', '0.55');
      svg.appendChild(path);

      var dot = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      dot.setAttribute('cx', x2); dot.setAttribute('cy', y2); dot.setAttribute('r', '3');
      dot.setAttribute('fill', fail ? '#e05252' : '#c9a84c');
      svg.appendChild(dot);
    }});
  }});
}}

// Busca por nome/caminho
var searchInput = document.getElementById('search');
var noResults = document.getElementById('no-results');
searchInput.addEventListener('input', function() {{
  var q = this.value.trim().toLowerCase();
  var visiveis = 0;
  document.querySelectorAll('.lineage').forEach(function(block) {{
    var blockMatch = !q || (block.dataset.search || '').indexOf(q) !== -1;
    var algumFilho = false;
    block.querySelectorAll('.target-node').forEach(function(t) {{
      var hit = !q || blockMatch || (t.dataset.search || '').indexOf(q) !== -1;
      t.style.display = hit ? '' : 'none';
      if (hit) algumFilho = true;
    }});
    var mostra = !q || blockMatch || algumFilho;
    block.style.display = mostra ? '' : 'none';
    if (mostra) visiveis++;
  }});
  noResults.style.display = visiveis ? 'none' : 'block';
  drawConnectors();
}});

window.addEventListener('load', drawConnectors);
window.addEventListener('resize', function() {{
  clearTimeout(window.__rt); window.__rt = setTimeout(drawConnectors, 120);
}});
</script>
</body>
</html>"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Gera relatório HTML de linhagem dos arquivos.")
    parser.add_argument("csv", help="Caminho do CSV de resultados (separador ';').")
    parser.add_argument("-o", "--output", default="templates/relatorio_conexoes.html",
                        help="Caminho do HTML de saída.")
    parser.add_argument("-s", "--sep", default=";", help="Separador do CSV (padrão ';').")
    parser.add_argument("-v", "--verbose", action="store_true", help="Logging detalhado.")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    csv_path = Path(args.csv)
    if not csv_path.is_file():
        logger.error("Arquivo não encontrado: %s", csv_path)
        return 1

    try:
        df = pd.read_csv(csv_path, sep=args.sep, dtype=str)
    except Exception as exc:  # leitura do CSV
        logger.error("Falha ao ler o CSV: %s", exc)
        return 2

    gerar_relatorio_conexoes(df, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())