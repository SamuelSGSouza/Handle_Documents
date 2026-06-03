import pandas as pd
from io import StringIO
from datetime import datetime
import html
import json


def gerar_relatorio_html(df: pd.DataFrame, output_path: str = "templates/relatorios.html") -> str:
    """
    Recebe um DataFrame com colunas de resultado de processamento de arquivos
    e gera um relatório HTML elegante e agrupado para usuário leigo.

    Colunas esperadas no df:
        path, extension, execution_time_seconds, result,
        find_cols, warning, failure_reason, suggested_solution
    """

    # ── Normalização das colunas ──────────────────────────────────────────────
    df = df.copy()

    # Remove coluna de índice se vier como coluna extra
    if df.columns[0] in ("", "Unnamed: 0"):
        df = df.iloc[:, 1:]

    # Garante que as colunas existam (preenche ausentes com "")
    expected_cols = [
        "path", "extension", "execution_time_seconds", "result",
        "find_cols", "warning", "failure_reason", "suggested_solution"
    ]
    for col in expected_cols:
        if col not in df.columns:
            df[col] = ""

    df["result"] = df["result"].fillna("unknown").str.lower()
    df["execution_time_seconds"] = pd.to_numeric(df["execution_time_seconds"], errors="coerce").fillna(0)

    # ── Estatísticas gerais ───────────────────────────────────────────────────
    total = len(df)
    sucessos = (df["result"] == "success").sum()
    falhas = (df["result"] == "failure").sum()
    outros = total - sucessos - falhas
    tempo_total = df["execution_time_seconds"].sum()

    # ── Agrupamento por pasta raiz ────────────────────────────────────────────
    def pasta_raiz(path_str):
        parts = str(path_str).replace("\\", "/").split("/")
        return parts[0] if len(parts) > 1 else "Raiz"

    df["_grupo"] = df["path"].apply(pasta_raiz)
    grupos = df.groupby("_grupo", sort=False)

    # ── Helpers ───────────────────────────────────────────────────────────────
    def badge(result):
        if result == "success":
            return '<span class="badge success">✔ Sucesso</span>'
        elif result == "failure":
            return '<span class="badge failure">✖ Falha</span>'
        return '<span class="badge warning">⚠ Outro</span>'

    def fmt_time(t):
        t = float(t)
        if t < 0.001:
            return "—"
        if t < 1:
            return f"{t*1000:.0f} ms"
        return f"{t:.2f} s"

    def fmt_cols(raw):
        if not raw or str(raw).strip() in ("", "[]", "nan"):
            return '<em class="muted">Nenhuma coluna identificada</em>'
        try:
            cols = json.loads(str(raw).replace("'", '"'))
            cols = [c for c in cols if c]
            if not cols:
                return '<em class="muted">Nenhuma coluna identificada</em>'
            return " ".join(f'<span class="col-tag">{html.escape(c)}</span>' for c in cols)
        except Exception:
            return html.escape(str(raw))

    def fmt_nome(path_str):
        return str(path_str).replace("\\", "/").split("/")[-1]

    def fmt_path(path_str):
        return html.escape(str(path_str))

    # ── Construção das linhas HTML por grupo ──────────────────────────────────
    grupos_html = ""
    for grupo_nome, grupo_df in grupos:
        g_total = len(grupo_df)
        g_ok = (grupo_df["result"] == "success").sum()
        g_fail = (grupo_df["result"] == "failure").sum()

        linhas = ""
        for _, row in grupo_df.iterrows():
            nome_arquivo = fmt_nome(row["path"])
            path_full = fmt_path(row["path"])
            ext = html.escape(str(row["extension"]))
            tempo = fmt_time(row["execution_time_seconds"])
            b = badge(row["result"])
            colunas = fmt_cols(row["find_cols"])

            motivo = html.escape(str(row["failure_reason"])) if str(row["failure_reason"]) not in ("", "nan") else ""
            sugestao = html.escape(str(row["suggested_solution"])) if str(row["suggested_solution"]) not in ("", "nan") else ""
            aviso = html.escape(str(row["warning"])) if str(row["warning"]) not in ("", "nan") else ""

            extra = ""
            if motivo:
                extra += f'<div class="detail-row"><span class="detail-label">⚠ Motivo da falha</span><span class="detail-val">{motivo}</span></div>'
            if sugestao:
                extra += f'<div class="detail-row"><span class="detail-label">💡 Sugestão</span><span class="detail-val">{sugestao}</span></div>'
            if aviso:
                extra += f'<div class="detail-row"><span class="detail-label">📋 Aviso</span><span class="detail-val">{aviso}</span></div>'

            is_failure = "row-failure" if row["result"] == "failure" else ""

            linhas += f"""
            <div class="file-card {is_failure}">
              <div class="file-header">
                <div class="file-name-block">
                  <span class="ext-pill">{ext}</span>
                  <span class="file-name" title="{path_full}">{html.escape(nome_arquivo)}</span>
                </div>
                <div class="file-meta">
                  <span class="time-chip">⏱ {tempo}</span>
                  {b}
                </div>
              </div>
              <div class="file-path">{path_full}</div>
              <div class="cols-block">{colunas}</div>
              {('<div class="extra-details">' + extra + '</div>') if extra else ''}
            </div>"""

        # Barra de progresso do grupo
        pct = int((g_ok / g_total) * 100) if g_total else 0

        grupos_html += f"""
        <section class="group-section">
          <div class="group-header">
            <div class="group-title-row">
              <h2 class="group-name">📁 {html.escape(grupo_nome)}</h2>
              <div class="group-stats">
                <span class="stat-chip ok">{g_ok} ok</span>
                <span class="stat-chip fail">{g_fail} falhas</span>
                <span class="stat-chip total">{g_total} arquivos</span>
              </div>
            </div>
            <div class="progress-bar-wrap">
              <div class="progress-bar-fill" style="width:{pct}%"></div>
              <span class="progress-label">{pct}% processados com sucesso</span>
            </div>
          </div>
          <div class="file-list">{linhas}</div>
        </section>"""

    # ── Sumário de status ─────────────────────────────────────────────────────
    pct_global = int((sucessos / total) * 100) if total else 0
    data_hora = datetime.now().strftime("%d/%m/%Y às %H:%M")

    html_content = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Relatório de Processamento de Arquivos</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Sora:wght@300;400;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg: #070e1a;
      --surface: #0c1628;
      --surface2: #101d34;
      --border: #1a2d4d;
      --border-light: #233d68;
      --text: #e8eef8;
      --text-muted: #7a9cc4;
      --text-dim: #3a5272;
      --ok: #c9a84c;
      --ok-bg: #1e1608;
      --ok-border: #3d2e0f;
      --fail: #e05252;
      --fail-bg: #220d0d;
      --fail-border: #3d1515;
      --warn: #e8b84b;
      --warn-bg: #1e1608;
      --accent: #4d9de0;
      --accent2: #c9a84c;
      --purple: #7ab8f5;
      --radius: 12px;
      --radius-sm: 7px;
    }}

    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    body {{
      background: var(--bg);
      color: var(--text);
      font-family: 'Sora', sans-serif;
      font-size: 14px;
      line-height: 1.6;
      min-height: 100vh;
    }}

    /* ── Topo ── */
    .topbar {{
      background: linear-gradient(135deg, #070e1a 0%, #0c1628 50%, #070e1a 100%);
      border-bottom: 1px solid var(--border);
      padding: 32px 40px 28px;
      position: relative;
      overflow: hidden;
    }}
    .topbar::before {{
      content: '';
      position: absolute;
      inset: 0;
      background: radial-gradient(ellipse 60% 80% at 80% -20%, rgba(201,168,76,0.10) 0%, transparent 70%);
      pointer-events: none;
    }}
    .topbar-inner {{ max-width: 1100px; margin: 0 auto; position: relative; z-index: 1; }}
    .report-label {{
      font-size: 11px;
      font-weight: 600;
      letter-spacing: 0.15em;
      text-transform: uppercase;
      color: var(--accent);
      margin-bottom: 6px;
    }}
    h1 {{
      font-size: clamp(22px, 3vw, 32px);
      font-weight: 700;
      color: var(--text);
      letter-spacing: -0.02em;
      margin-bottom: 4px;
    }}
    .report-date {{ color: var(--text-muted); font-size: 13px; }}

    /* ── Cards sumário ── */
    .summary-row {{
      max-width: 1100px;
      margin: 28px auto;
      padding: 0 40px;
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 14px;
    }}
    .summary-card {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 20px 22px;
      display: flex;
      flex-direction: column;
      gap: 4px;
      transition: border-color .2s, transform .2s;
    }}
    .summary-card:hover {{ border-color: var(--border-light); transform: translateY(-2px); }}
    .summary-card .card-num {{
      font-size: 30px;
      font-weight: 700;
      font-family: 'JetBrains Mono', monospace;
      letter-spacing: -0.03em;
    }}
    .summary-card .card-label {{ font-size: 12px; color: var(--text-muted); font-weight: 600; letter-spacing: 0.05em; text-transform: uppercase; }}
    .summary-card.c-total .card-num {{ color: var(--accent2); }}
    .summary-card.c-ok .card-num {{ color: var(--ok); }}
    .summary-card.c-fail .card-num {{ color: var(--fail); }}
    .summary-card.c-time .card-num {{ color: var(--purple); font-size: 22px; }}

    /* Barra global */
    .global-progress-wrap {{
      max-width: 1100px;
      margin: 0 auto 32px;
      padding: 0 40px;
    }}
    .gp-label {{ font-size: 13px; color: var(--text-muted); margin-bottom: 8px; }}
    .gp-bar {{ height: 8px; background: var(--surface2); border-radius: 99px; overflow: hidden; }}
    .gp-fill {{ height: 100%; background: linear-gradient(90deg, #c9a84c 0%, #e8d08a 100%); border-radius: 99px; transition: width 1s ease; }}

    /* ── Conteúdo principal ── */
    .main {{ max-width: 1100px; margin: 0 auto; padding: 0 40px 60px; }}

    .group-section {{
      margin-bottom: 36px;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      overflow: hidden;
    }}

    .group-header {{
      padding: 18px 22px 16px;
      background: var(--surface2);
      border-bottom: 1px solid var(--border);
    }}
    .group-title-row {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 10px;
      margin-bottom: 12px;
    }}
    .group-name {{
      font-size: 15px;
      font-weight: 600;
      color: var(--text);
      letter-spacing: -0.01em;
    }}
    .group-stats {{ display: flex; gap: 8px; flex-wrap: wrap; }}
    .stat-chip {{
      font-size: 11px;
      font-weight: 600;
      padding: 3px 10px;
      border-radius: 99px;
      letter-spacing: 0.04em;
    }}
    .stat-chip.ok {{ background: var(--ok-bg); color: var(--ok); border: 1px solid var(--ok-border); }}
    .stat-chip.fail {{ background: var(--fail-bg); color: var(--fail); border: 1px solid var(--fail-border); }}
    .stat-chip.total {{ background: var(--surface); color: var(--text-muted); border: 1px solid var(--border); }}

    .progress-bar-wrap {{
      position: relative;
      height: 6px;
      background: rgba(255,255,255,0.05);
      border-radius: 99px;
      overflow: visible;
    }}
    .progress-bar-fill {{
      height: 100%;
      background: linear-gradient(90deg, #c9a84c, #e8d08a);
      border-radius: 99px;
      transition: width 1s ease;
    }}
    .progress-label {{
      position: absolute;
      right: 0;
      top: -22px;
      font-size: 11px;
      color: var(--text-muted);
    }}

    /* ── Cards de arquivo ── */
    .file-list {{ padding: 12px 16px 16px; display: flex; flex-direction: column; gap: 10px; }}

    .file-card {{
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: var(--radius-sm);
      padding: 14px 16px;
      transition: border-color .2s, box-shadow .2s;
    }}
    .file-card:hover {{
      border-color: var(--border-light);
      box-shadow: 0 4px 20px rgba(0,0,0,0.3);
    }}
    .file-card.row-failure {{ border-left: 3px solid var(--fail); }}

    .file-header {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 10px;
      margin-bottom: 6px;
    }}
    .file-name-block {{ display: flex; align-items: center; gap: 8px; flex: 1; min-width: 0; }}

    .ext-pill {{
      font-size: 10px;
      font-weight: 700;
      padding: 2px 8px;
      border-radius: 4px;
      background: rgba(77,157,224,0.12);
      color: var(--accent);
      border: 1px solid rgba(77,157,224,0.25);
      text-transform: uppercase;
      white-space: nowrap;
      font-family: 'JetBrains Mono', monospace;
      letter-spacing: 0.05em;
    }}
    .file-name {{
      font-size: 14px;
      font-weight: 600;
      color: var(--text);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}

    .file-meta {{ display: flex; align-items: center; gap: 8px; flex-shrink: 0; }}
    .time-chip {{
      font-size: 11px;
      font-family: 'JetBrains Mono', monospace;
      color: var(--text-muted);
      background: var(--surface2);
      border: 1px solid var(--border);
      padding: 2px 9px;
      border-radius: 99px;
    }}

    .badge {{
      font-size: 11px;
      font-weight: 700;
      padding: 3px 11px;
      border-radius: 99px;
      letter-spacing: 0.04em;
    }}
    .badge.success {{ background: var(--ok-bg); color: var(--ok); border: 1px solid var(--ok-border); }}
    .badge.failure {{ background: var(--fail-bg); color: var(--fail); border: 1px solid var(--fail-border); }}
    .badge.warning {{ background: var(--warn-bg); color: var(--warn); border: 1px solid rgba(232,184,75,0.3); }}

    .file-path {{
      font-size: 11px;
      color: var(--text-dim);
      font-family: 'JetBrains Mono', monospace;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      margin-bottom: 10px;
    }}

    .cols-block {{
      display: flex;
      flex-wrap: wrap;
      gap: 5px;
      margin-bottom: 2px;
    }}
    .col-tag {{
      font-size: 11px;
      padding: 2px 9px;
      background: rgba(122,184,245,0.08);
      border: 1px solid rgba(122,184,245,0.2);
      color: var(--purple);
      border-radius: 5px;
      font-family: 'JetBrains Mono', monospace;
      white-space: nowrap;
    }}
    .muted {{ color: var(--text-dim); font-style: italic; font-size: 12px; }}

    .extra-details {{
      margin-top: 12px;
      border-top: 1px solid var(--border);
      padding-top: 10px;
      display: flex;
      flex-direction: column;
      gap: 6px;
    }}
    .detail-row {{
      display: flex;
      gap: 10px;
      align-items: flex-start;
      flex-wrap: wrap;
    }}
    .detail-label {{
      font-size: 11px;
      font-weight: 600;
      color: var(--warn);
      white-space: nowrap;
      min-width: 130px;
    }}
    .detail-val {{
      font-size: 12px;
      color: var(--text-muted);
      flex: 1;
    }}

    /* ── Footer ── */
    .footer {{
      text-align: center;
      padding: 24px 40px;
      border-top: 1px solid var(--border);
      color: var(--text-dim);
      font-size: 12px;
      max-width: 1100px;
      margin: 0 auto;
    }}

    /* ── Animações ── */
    @keyframes fadeUp {{
      from {{ opacity: 0; transform: translateY(16px); }}
      to {{ opacity: 1; transform: translateY(0); }}
    }}
    .group-section {{
      animation: fadeUp .4s ease both;
    }}
    .group-section:nth-child(2) {{ animation-delay: .07s; }}
    .group-section:nth-child(3) {{ animation-delay: .14s; }}
    .group-section:nth-child(4) {{ animation-delay: .21s; }}
    .group-section:nth-child(5) {{ animation-delay: .28s; }}

    /* ── Responsivo ── */
    @media (max-width: 640px) {{
      .topbar, .summary-row, .global-progress-wrap, .main {{ padding-left: 16px; padding-right: 16px; }}
      .summary-row {{ grid-template-columns: 1fr 1fr; }}
    }}
  </style>
</head>
<body>

<header class="topbar">
  <div class="topbar-inner">
    <div class="report-label">Relatório de Processamento</div>
    <h1>Arquivos Processados</h1>
    <div class="report-date">Gerado em {data_hora}</div>
  </div>
</header>

<div class="summary-row">
  <div class="summary-card c-total">
    <span class="card-num">{total}</span>
    <span class="card-label">Total de arquivos</span>
  </div>
  <div class="summary-card c-ok">
    <span class="card-num">{sucessos}</span>
    <span class="card-label">Processados com sucesso</span>
  </div>
  <div class="summary-card c-fail">
    <span class="card-num">{falhas}</span>
    <span class="card-label">Com falhas</span>
  </div>
  <div class="summary-card c-time">
    <span class="card-num">{fmt_time(tempo_total)}</span>
    <span class="card-label">Tempo total de execução</span>
  </div>
</div>

<div class="global-progress-wrap">
  <div class="gp-label">{pct_global}% dos arquivos processados com sucesso</div>
  <div class="gp-bar">
    <div class="gp-fill" style="width:{pct_global}%"></div>
  </div>
</div>

<main class="main">
{grupos_html}
</main>

<footer class="footer">
  Relatório gerado automaticamente · {total} arquivos analisados · {data_hora}
</footer>

</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"✅ Relatório salvo em: {output_path}")
    return html_content


# ── Exemplo de uso ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    
    df = pd.read_csv("+ Resultados do Tratamento/Relatório das Conversões.csv", sep=";")
    gerar_relatorio_html(df, "templates/relatorios.html")