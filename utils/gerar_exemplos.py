import os
import shutil
from pathlib import Path

SEPARADOR = ";"
LINHAS = 5  # número de linhas de dados (fora o header)

def gerar_exemplos(PASTA_ORIGEM, PASTA_DESTINO):
    if not PASTA_ORIGEM.exists():
        print(f"[ERRO] Pasta '{PASTA_ORIGEM}' não encontrada.")
        return

    # Remove e recria a pasta destino para garantir estrutura limpa
    if PASTA_DESTINO.exists():
        shutil.rmtree(PASTA_DESTINO)
    PASTA_DESTINO.mkdir()

    csvs_processados = 0
    erros = []

    for caminho_csv in sorted(PASTA_ORIGEM.rglob("*.csv")):
        # Calcula o caminho relativo para replicar a estrutura
        relativo = caminho_csv.relative_to(PASTA_ORIGEM)
        destino = PASTA_DESTINO / relativo

        # Cria subpastas necessárias
        destino.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(caminho_csv, "r", encoding="utf-8") as f_in:
                linhas = f_in.readlines()

            # Header + até LINHAS linhas de dados
            conteudo = linhas[: LINHAS + 1]

            with open(destino, "w", encoding="utf-8") as f_out:
                f_out.writelines(conteudo)

            total_dados = len(linhas) - 1  # descontando header
            print(f"  ✓  {relativo}  ({min(LINHAS, total_dados)}/{total_dados} linhas)")
            csvs_processados += 1

        except Exception as e:
            erros.append((str(relativo), str(e)))
            print(f"  ✗  {relativo}  → {e}")

    print(f"\nConcluído: {csvs_processados} arquivo(s) gerado(s) em '{PASTA_DESTINO}/'")
    if erros:
        print(f"Erros ({len(erros)}):")
        for arq, msg in erros:
            print(f"  - {arq}: {msg}")

if __name__ == "__main__":
    gerar_exemplos()