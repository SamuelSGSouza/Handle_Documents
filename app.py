"""
Flask App - Sistema de Processamento de Pastas
Advocacia · Seleção de pastas via janela nativa (tkinter) + Relatórios
"""

import threading, os, traceback
import tkinter as tk
from tkinter import filedialog
from pathlib import Path
import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Response
from trats.controler_trats import start_conversions
from flask import send_from_directory, abort
from flask import session
from utils.gerar_relatorio_conexoes import gerar_relatorio_conexoes

app = Flask(__name__)
app.secret_key = "advocacia-chave-secreta-2024"

# ─── Tkinter: abre janela nativa de seleção de pasta ─────────────────────────

def abrir_dialogo_pasta(titulo: str) -> str:
    """
    Abre a janela nativa do SO para selecionar uma pasta.
    Roda na thread principal via threading.Event para não bloquear o Flask.

    Args:
        titulo: Título exibido na janela de seleção.

    Returns:
        Caminho absoluto selecionado, ou string vazia se cancelado.
    """
    resultado = {"caminho": ""}
    evento = threading.Event()

    def _abrir():
        root = tk.Tk()
        root.withdraw()           # esconde a janela root
        root.attributes("-topmost", True)   # garante que fique na frente
        caminho = filedialog.askdirectory(title=titulo, parent=root)
        root.destroy()
        resultado["caminho"] = caminho or ""
        evento.set()

    # tkinter precisa rodar na thread principal no Windows;
    # no Linux/Mac roda normalmente em thread separada.
    t = threading.Thread(target=_abrir, daemon=True)
    t.start()
    evento.wait(timeout=120)   # aguarda até 2 min o usuário escolher
    return resultado["caminho"]


# ─── Endpoint AJAX: abre o diálogo e devolve o caminho ───────────────────────

@app.route("/selecionar-pasta")
def selecionar_pasta():
    """Abre janela nativa e retorna o caminho escolhido como JSON."""
    tipo  = request.args.get("tipo", "entrada")
    titulo = "Selecionar Pasta de Entrada" if tipo == "entrada" else "Selecionar Pasta de Saída"

    caminho = abrir_dialogo_pasta(titulo)
    return jsonify({"caminho": caminho})


# ─── Processamento ────────────────────────────────────────────────────────────

def processar_pastas(pasta_entrada: str, pasta_saida: str) -> dict:
    """
    Placeholder para o processamento principal.
    Substitua o corpo desta função pelo seu código real.

    Args:
        pasta_entrada: Caminho absoluto da pasta de entrada.
        pasta_saida:   Caminho absoluto da pasta de saída.

    Returns:
        dict com status e mensagem do processamento.
    """
    start_conversions(pasta_entrada, pasta_saida)
    
    return {
        "status": "ok",
        "mensagem": f"Processamento concluído. Entrada: {pasta_entrada} | Saída: {pasta_saida}",
    }


# ─── VIEW 1 · Seleção de pastas ───────────────────────────────────────────────

@app.route("/", methods=["GET"])
def index():
    """Exibe o formulário de seleção de pastas."""
    return render_template("index.html")


@app.route("/processar", methods=["POST"])
def processar():
    """Recebe as pastas, executa o processamento e redireciona."""
    pasta_entrada = request.form.get("pasta_entrada", "").strip()
    pasta_saida   = request.form.get("pasta_saida",   "").strip()
    session["pasta_saida"] = pasta_saida

    if not pasta_entrada or not pasta_saida:
        flash("Ambos os campos são obrigatórios.", "erro")
        return redirect(url_for("index"))

    if not Path(pasta_entrada).is_dir():
        flash(f"Pasta de entrada não encontrada: {pasta_entrada}", "erro")
        return redirect(url_for("index"))

    try:
        resultado = processar_pastas(pasta_entrada, pasta_saida)
        flash(resultado["mensagem"], "sucesso")
    except Exception as exc:
        flash(f"Erro no processamento: {traceback.format_exc()}", "erro")

    return redirect(url_for("index"))


# ─── VIEW 2 · Relatórios ──────────────────────────────────────────────────────

@app.route("/relatorios")
def relatorios():
    """Exibe a página de relatórios."""
    return render_template("relatorios.html")


# ─────────────────────────────────────────────────────────────────────────────
@app.route("/baixar-relatorio")
def baixar_relatorio():
    """
    Serve o relatório solicitado como download.
    Parâmetro ?arquivo=csv ou ?arquivo=json
    """
    tipo = request.args.get("arquivo", "").lower()
 
    nomes = {
        "csv":  "Relatório das Conversões.csv",
        "json": "Relatório das Conversões.json",
    }
 
    if tipo not in nomes:
        abort(400, "Tipo de arquivo inválido.")
 
    nome_arquivo = nomes[tipo]
 
    # ──────────────────────────────────────────────────────────────────────────
    # AJUSTE: defina aqui a pasta onde os relatórios são salvos pelo backend.
    # Exemplos:
    #   pasta_relatorios = Path("relatorios")                 # relativo ao projeto
    #   pasta_relatorios = Path(r"C:\MeuSistema\relatorios")  # caminho absoluto
    # ──────────────────────────────────────────────────────────────────────────
    pasta_saida = session.get("pasta_saida", "")
    pasta_relatorios = Path(os.path.join(pasta_saida, "+ Resultados do Tratamento"))   # <── altere conforme necessário
 
    caminho = pasta_relatorios / nome_arquivo
    print("Caminho: ", caminho)
    if not caminho.exists():
        abort(404, f"Relatório não encontrado: {nome_arquivo}")
 
    return send_from_directory(
        directory=str(pasta_relatorios.resolve()),
        path=nome_arquivo,
        as_attachment=True,
    )
 

# ─────────────────────────────────────────────────────────────────────────────



# ─── VIEW 3 · Mapa de Linhagem (conexões original → gerados) ──────────────────

def _pagina_aviso(titulo: str, detalhe: str) -> Response:
    """Página simples (mesmo tema) para avisos quando não há dados."""
    corpo = f"""<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{titulo}</title><style>
body{{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;
background:#070e1a;color:#e8eef8;font-family:system-ui,'Segoe UI',sans-serif;padding:24px;}}
.box{{max-width:480px;text-align:center;background:#0c1628;border:1px solid #1a2d4d;
border-radius:12px;padding:40px 36px;}}
h1{{font-size:20px;color:#c9a84c;margin:0 0 12px;}}
p{{color:#7a9cc4;font-size:14px;line-height:1.6;margin:0 0 24px;word-break:break-word;}}
a{{display:inline-block;color:#070e1a;background:#c9a84c;text-decoration:none;
font-weight:600;font-size:13px;padding:10px 22px;border-radius:99px;}}
</style></head><body><div class="box">
<h1>{titulo}</h1><p>{detalhe}</p>
<a href="{url_for('index')}">← Voltar ao sistema</a>
</div></body></html>"""
    return Response(corpo, mimetype="text/html")


@app.route("/relatorio-conexoes")
def relatorio_conexoes():
    """Gera e exibe o mapa de linhagem ligando cada arquivo original aos gerados."""
    pasta_saida = session.get("pasta_saida", "")
    if not pasta_saida:
        return _pagina_aviso(
            "Nenhum processamento encontrado",
            "Selecione e processe uma pasta primeiro para gerar a linhagem dos arquivos.",
        )

    csv_path = Path(pasta_saida) / "+ Resultados do Tratamento" / "Relatório das Conversões.csv"
    if not csv_path.exists():
        return _pagina_aviso(
            "Relatório não encontrado",
            f"O arquivo esperado não existe: {csv_path}",
        )

    try:
        df = pd.read_csv(csv_path, sep=";", dtype=str)
        html_doc = gerar_relatorio_conexoes(df, output_path=None, back_url=url_for("index"))
    except Exception as exc:
        return _pagina_aviso("Erro ao gerar a linhagem", str(exc))

    return Response(html_doc, mimetype="text/html")


# ─────────────────────────────────────────────────────────────────────────────



if __name__ == "__main__":
    app.run(debug=False, port=5000)   # debug=False evita duplo processo no reloader