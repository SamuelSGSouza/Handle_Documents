# requirements:
#   camelot-py[cv]  pymupdf4llm  anthropic  pandas

import time, re
from pathlib import Path

import camelot
import pandas as pd
import pymupdf4llm
import anthropic

from utils.constants import API_KEY
from utils.reporter_base import Report,success,failure

MODEL      = "claude-haiku-4-5-20251001"
MAX_TOKENS = 8192


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------



VALID_DATE_PATTERN = re.compile(r"^\d{4}_\d{2}$")
MIN_YEAR = 1990
MAX_YEAR = 2100
MIN_MONTH = 1
MAX_MONTH = 12


def _validate_ref_date(raw: str) -> tuple[str, str]:
    """Valida e normaliza o resultado retornado pela API.

    Args:
        raw: String no formato esperado YYYY_MM.

    Returns:
        Tupla (ano, mes) validada. Substitui valores inválidos por "00".
    """
    raw = raw.strip()

    if not VALID_DATE_PATTERN.match(raw):
        return "0000", "00"

    year_str, month_str = raw.split("_")
    year, month = int(year_str), int(month_str)

    validated_year = year_str if MIN_YEAR <= year <= MAX_YEAR else "0000"
    validated_month = month_str if MIN_MONTH <= month <= MAX_MONTH else "00"

    return validated_year, validated_month


def _extract_ref_date(path: str) -> tuple[str, str]:
    """Extrai mês e ano de referência a partir do nome de um arquivo.

    Usa a API da Anthropic para interpretar o nome do arquivo e retorna
    uma tupla (ano, mes) no formato YYYY e MM. Valores não identificados
    ou inválidos são substituídos por "00"/"0000".

    Args:
        path: Nome ou caminho do arquivo a ser analisado.

    Returns:
        Tupla (ano, mes) como strings, ex: ("2023", "04").

    Raises:
        anthropic.APIError: Em caso de falha na chamada à API.
        ValueError: Se a resposta da API estiver completamente malformada.
    """
    client = anthropic.Anthropic(api_key=API_KEY)

    prompt = f"""
A partir do nome do arquivo "{path}", retorne o mês e ano de referência no formato YYYY_MM.

Regras:
- Não retorne comentários ou explicações, apenas o YYYY_MM
- Um ano só possui 12 meses (01–12)
- O ano mais antigo aceito é 1990
- Se não puder afirmar com precisão, substitua o campo por 00
- Se não encontrar o mês: 2021_00
- Se não encontrar o ano: 0000_06

Formatos válidos: 2022_01 | 2003_12 | 2019_00 | 0000_06
Formatos inválidos: 1003_12 | 2023_99
"""

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=10,
        messages=[{"role": "user", "content": prompt}],
    )

    raw_result = message.content[0].text.strip()
    return _validate_ref_date(raw_result)


def _find_header_rows(df: pd.DataFrame, max_header_rows: int = 4) -> int:
    """
    Detecta quantas linhas iniciais formam o cabeçalho da tabela.

    Critério: a primeira linha que contenha um número de processo
    (padrão NNNNN.NNNNNN/AAAA-NN) ou que esteja ≥50 % preenchida
    é considerada a primeira linha de dados reais.

    Args:
        df:              DataFrame bruto do camelot.
        max_header_rows: Máximo de linhas a inspecionar.

    Returns:
        Índice (0-based) da primeira linha de dados.
    """
    for i in range(1, max_header_rows + 1):
        row = df.iloc[i]
        non_empty = row.astype(str).str.strip().ne("").sum()
        has_process_number = row.astype(str).str.contains(
            r"\d{5}\.\d{6}/\d{4}-\d{2}"
        ).any()
        if has_process_number or non_empty >= len(df.columns) * 0.5:
            return i
    return 1


# ---------------------------------------------------------------------------
# Main function
# ---------------------------------------------------------------------------

def parse_pdf_to_csv(input_path: str, output_folder: str) -> list[Report]:
    """
    Converte um PDF em CSV (tabela principal) e Markdown, gravando os
    arquivos de saída dentro de ``output_folder`` numa sub-estrutura
    ``<ano>/<mes>/`` derivada do nome do arquivo, preservando o nome base.

    Args:
        input_path:    Caminho completo do PDF de entrada.
        output_folder: Pasta raiz onde os arquivos serão gravados.
    """
    start_time = time.perf_counter()
    input_path    = Path(input_path)
    output_folder = Path(output_folder)

    if not input_path.exists():
        return [failure(
            reason=f"Arquivo não encontrado: {input_path}",
            solution="Verifique se o arquivo realmente existe",
            file_path=input_path
        ), ]

    # --- Cliente Anthropic ---
    resolved_key = API_KEY
    if not resolved_key:
        return [failure(
            reason=f"API_KEY não configurada em utils/constants.py",
            solution="Verifique se o arquivo de constants foi criado e se possui uma chave de API",
            file_path=input_path
        ), ]

    # --- Data de referência ---
    ano, mes = _extract_ref_date(input_path.name)

    # --- Pasta de destino: output_folder / ano / mes / (subpasta do arquivo) ---
    # Preserva a estrutura de subpastas relativa ao nome do arquivo pai, se houver.
    dest_folder = output_folder / ano / mes
    dest_folder.mkdir(parents=True, exist_ok=True)

    stem = input_path.stem  # nome sem extensão

    # --- Extração de tabela ---
    tables = camelot.read_pdf(str(input_path), flavor="lattice")
    if tables:
        df:pd.DataFrame = tables[0].df.copy()

        header_end  = _find_header_rows(df)

        # Reconstrói colunas concatenando as linhas de cabeçalho
        header_parts = df.iloc[:header_end].values
        new_columns  = []
        for col_idx in range(df.shape[1]):
            parts = [
                str(header_parts[row_idx][col_idx]).strip()
                for row_idx in range(header_end)
                if str(header_parts[row_idx][col_idx]).strip()
            ]
            new_columns.append(" ".join(parts))

        df.columns = new_columns
        df = df.iloc[header_end:].reset_index(drop=True)

        # Remove linhas completamente vazias
        df = df[df.astype(str).apply(lambda r: r.str.strip().ne("").any(), axis=1)]

        csv_path = dest_folder / f"{stem}.csv"
        df.to_csv(csv_path, sep=";", index=False, encoding="utf-8-sig")

        return [success(
            file_path=csv_path,
            find_cols=df.columns.tolist(),
            execution_time_seconds= round(time.perf_counter() - start_time, 4),
        ), ]
    else:
        print("Nenhuma tabela encontrada em: %s", input_path)


    # --- Extração Markdown ---
    md      = pymupdf4llm.to_markdown(str(input_path))
    md_path = dest_folder / f"{stem}.md"
    md_path.write_text(md, encoding="utf-8")

    return [success(
        file_path=md_path,
        find_cols=[],
        execution_time_seconds= round(time.perf_counter() - start_time, 4),
        warning="Esse arquivo é um .MD de um pdf convertido"
    ), ]
    
# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    
    parse_pdf_to_csv("Arquivos/V/1. 13868.7445082023-60/13868.7445082023-60_Laudo.pdf", "Resultado")