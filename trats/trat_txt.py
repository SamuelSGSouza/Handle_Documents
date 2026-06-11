"""Extração de texto de imagens (OCR) usando a API de visão do Claude.

Dependências:
    anthropic>=0.40
"""

import base64, time, traceback
import mimetypes
from pathlib import Path
from utils.reporter_base import Report, failure, success
import anthropic

from utils.constants import API_KEY


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

def parse_txt(input_path: Path, input_dir, output_folder) -> list[Report]:
    try:
        start_time    = time.perf_counter()
        with open(input_path, "r", encoding="utf-8") as arq:
            texto = arq.read()
        if len(texto) < 300:
            return [failure(reason="Não foi possível identificar com precisão o texto do arquivo", solution="", file_path=input_path, original_path=input_path),]
        categoria = retorna_categoria(str(input_path))

        if categoria == "OUTROS":
            relative = input_path.relative_to(input_dir)
            dest_folder = output_folder / relative.parent
        else:
            data_referencia = _retorna_data(str(input_path))
            partes = data_referencia.split("_")
            if len(partes) != 2:
                raise [failure(reason=f"data_referencia inválida: {data_referencia!r}", solution="Verificar o prompt e o nome do arquivo para encontrar o real problema", file_path=input_path, original_path=input_path),]
            ano, mes = partes
            dest_folder = output_folder / categoria / ano / mes

        dest_folder.mkdir(parents=True, exist_ok=True)
        stem = input_path.stem
        txt_path = dest_folder / f"{stem}.txt"

        with open(txt_path, "w", encoding="utf-8") as arq:
            arq.write(texto)


        return [
            success(
                file_path=txt_path,
                original_path=input_path,
                find_cols=[],
                execution_time_seconds=round(time.perf_counter() - start_time, 4),
                warning="Esse era um arquivo de txt, portanto foi convertido diretamente para txt."
            ), 
        ]
    except Exception as e:
        return [failure(reason=f"{traceback.format_exc()}", solution="", file_path=input_path, original_path=input_path),]

