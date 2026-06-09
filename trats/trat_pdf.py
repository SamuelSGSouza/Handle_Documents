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
from typing import Literal, Optional
CATEGORIAS = Literal["SPED_EFD", "SPED_ECD", "NOTAS_FISCAIS", "OUTROS"]
CATEGORIAS_VALIDAS = {"SPED_EFD", "SPED_ECD", "NOTAS_FISCAIS", "OUTROS"}
 
 
def retorna_categoria(path: str,aba: Optional[str] = None,) -> CATEGORIAS:
    client = anthropic.Anthropic(api_key=API_KEY)
    """
    Classifica um arquivo em uma das categorias fiscais com base no nome
    do arquivo e, opcionalmente, no nome da aba.
 
    Args:
        path:   Caminho ou nome do arquivo a classificar.
        aba:    Nome da aba/sheet (opcional). Quando fornecido, enriquece
                o contexto para a classificação.
        client: Instância de anthropic.Anthropic já configurada.
        model:  ID do modelo a usar.
 
    Returns:
        Uma das strings: "SPED_EFD", "SPED_ECD", "NOTAS_FISCAIS", "OUTROS".
    """
    contexto_aba = f"\n<aba>{aba}</aba>" if aba else ""
 
    prompt = f"""\
Você é um classificador de arquivos fiscais brasileiros. Analise o nome do arquivo \
e, quando disponível, o nome da aba, e retorne EXATAMENTE uma das categorias abaixo \
— sem pontuação, sem espaços extras, sem explicações.
 
Categorias válidas:
- SPED_EFD      → Escrituração Fiscal Digital (EFD ICMS/IPI ou EFD Contribuições)
- SPED_ECD      → Escrituração Contábil Digital
- NOTAS_FISCAIS → Notas fiscais de entrada ou saída (NF-e, NFS-e, XML, DANFE)
- OUTROS        → Qualquer arquivo que não se enquadre nas categorias acima
 
Exemplos:
<arquivo>EFD_ICMS_IPI_2023_01.txt</arquivo> → SPED_EFD
<arquivo>sped_efd_contribuicoes_jan22.txt</arquivo> → SPED_EFD
<arquivo>ECD_2022.txt</arquivo> → SPED_ECD
<arquivo>escrituracao_contabil_2021.sped</arquivo> → SPED_ECD
<arquivo>NF_entrada_042023.xml</arquivo> → NOTAS_FISCAIS
<arquivo>notas_fiscais_saida_março.xlsx</arquivo><aba>NF-e Saída</aba> → NOTAS_FISCAIS
<arquivo>relatorio_vendas.xlsx</arquivo> → OUTROS
<arquivo>balancete_2022.pdf</arquivo> → OUTROS
 
Agora classifique:
<arquivo>{path}</arquivo>{contexto_aba}"""
 
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=20,
        messages=[{"role": "user", "content": prompt}],
    )
 
    resposta = message.content[0].text.strip().upper()
 
    # Retorno exato — caminho feliz
    if resposta in CATEGORIAS_VALIDAS:
        return resposta  # type: ignore[return-value]
 
    # Fallback: extrai substring válida caso o modelo adicione lixo ao redor
    for categoria in CATEGORIAS_VALIDAS:
        if categoria in resposta:
            return categoria  # type: ignore[return-value]
 
    # Fallback total: alucinação completa → default seguro
    return "OUTROS"

def _retorna_data(path, ):
    client = anthropic.Anthropic(api_key=API_KEY)

    prompt = f""""
    A partir do nome do arquivo "{path}"
    retorne o mẽs e ano de referẽncia no formato YYYY_MM
    Não retorne comentários ou explicações, apenas o YYYY_MM
    Lembre-se que um ano só possui 12 meses e que o ano mais antigo será 1990.
    Se não puder afirmar com precisão alguma das informações, prefira retornar 00
    Se não encontrar o ano ou o mês, retorne substituindo o que faltar por 00. Exemplo com mês não encontrado: 2021_00
    
    Formatos de retorno válidos:
    1. 2022_01
    2. 2003_12
    3. 2019_00
    4. 0000_06
    
    Formatos de retorno Inválidos:
    1. 1003_12
    2. 2023_99
    """

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=7,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text.strip()


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

def parse_pdf_to_csv(input_path: str, input_dir: str, output_folder: str) -> list[Report]:
    start_time    = time.perf_counter()
    input_path    = Path(input_path)
    input_dir     = Path(input_dir)
    output_folder = Path(output_folder)

    if not input_path.exists():
        return [failure(
            reason=f"Arquivo não encontrado: {input_path}",
            solution="Verifique se o arquivo realmente existe",
            file_path=input_path,
            original_path=input_path
        )]

    if not API_KEY:
        return [failure(
            reason="API_KEY não configurada em utils/constants.py",
            solution="Verifique se o arquivo de constants foi criado e se possui uma chave de API",
            file_path=input_path,
            original_path=input_path
        )]

    # --- Categoria e pasta de destino ---
    categoria = retorna_categoria(str(input_path))

    if categoria == "OUTROS":
        relative = input_path.relative_to(input_dir)
        dest_folder = output_folder / relative.parent
    else:
        data_referencia = _retorna_data(str(input_path))
        partes = data_referencia.split("_")
        if len(partes) != 2:
            raise ValueError(f"data_referencia inválida: {data_referencia!r}")
        ano, mes = partes
        dest_folder = output_folder / categoria / ano / mes

    dest_folder.mkdir(parents=True, exist_ok=True)
    stem = input_path.stem

    # --- Extração de tabela ---
    tables = camelot.read_pdf(str(input_path), flavor="lattice")
    if tables:
        df: pd.DataFrame = tables[0].df.copy()
        header_end   = _find_header_rows(df)
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
        df = df[df.astype(str).apply(lambda r: r.str.strip().ne("").any(), axis=1)]

        csv_path = dest_folder / f"{stem}.csv"
        df.to_csv(csv_path, sep=";", index=False, encoding="utf-8-sig")

        return [success(
            file_path=csv_path,
            find_cols=df.columns.tolist(),
            execution_time_seconds=round(time.perf_counter() - start_time, 4),
            original_path=input_path
        )]

    # --- Fallback: extração Markdown ---
    md      = pymupdf4llm.to_markdown(str(input_path))
    md_path = dest_folder / f"{stem}.md"
    md_path.write_text(md, encoding="utf-8")

    return [success(
        file_path=md_path,
        find_cols=[],
        execution_time_seconds=round(time.perf_counter() - start_time, 4),
        warning="Esse arquivo é um .MD de um pdf convertido",
        original_path=input_path
    )]
    
# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    
    parse_pdf_to_csv("Arquivos/V/1. 13868.7445082023-60/13868.7445082023-60_Laudo.pdf", "Resultado")