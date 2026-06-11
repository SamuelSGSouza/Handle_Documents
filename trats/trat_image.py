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

# Tipos de imagem aceitos pela API de visão da Anthropic.
_SUPPORTED_MEDIA_TYPES = frozenset(
    {"image/jpeg", "image/png", "image/gif", "image/webp"}
)

# Prompt que instrui o modelo a se comportar como um motor de OCR puro.
_OCR_PROMPT = (
    "Extraia e retorne TODO o texto presente nesta imagem, exatamente como "
    "aparece, preservando a ordem de leitura e as quebras de linha. "
    "Não adicione comentários, explicações, títulos ou qualquer formatação "
    "extra. Se a imagem não contiver texto, retorne uma string vazia."
)


def _detecta_media_type(path: Path) -> str:
    """Infere o media type da imagem a partir da extensão do arquivo.

    Args:
        path: Caminho da imagem.

    Returns:
        O media type no formato aceito pela API (ex.: "image/png").

    Raises:
        ValueError: Se o formato não for suportado pela API de visão.
    """
    media_type, _ = mimetypes.guess_type(path.name)
    if media_type == "image/jpg":  # normalização defensiva
        media_type = "image/jpeg"
    if media_type not in _SUPPORTED_MEDIA_TYPES:
        raise ValueError(
            f"Formato não suportado para '{path.name}'. "
            f"Suportados: {', '.join(sorted(_SUPPORTED_MEDIA_TYPES))}."
        )
    return media_type

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

def retorna_texto(path: str | Path) -> str:
    """Extrai todo o texto de uma imagem usando o modelo de visão do Claude.

    Args:
        path: Caminho para o arquivo de imagem (jpeg, png, gif ou webp).
        max_tokens: Limite máximo de tokens da resposta. O default cobre
            imagens densas de texto; aumente para documentos muito extensos.

    Returns:
        O texto extraído da imagem, já com espaços nas pontas removidos.
        Retorna string vazia se a imagem não contiver texto.

    Raises:
        FileNotFoundError: Se o caminho não apontar para um arquivo existente.
        ValueError: Se o formato da imagem não for suportado.
    """
    image_path = Path(path)
    if not image_path.is_file():
        raise FileNotFoundError(f"Imagem não encontrada: {image_path}")

    media_type = _detecta_media_type(image_path)
    image_data = base64.standard_b64encode(image_path.read_bytes()).decode("utf-8")

    client = anthropic.Anthropic(api_key=API_KEY)
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=20000,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_data,
                        },
                    },
                    {"type": "text", "text": _OCR_PROMPT},
                ],
            }
        ],
    )
    return message.content[0].text.strip()


def parse_image(input_path: Path, input_dir, output_folder) -> list[Report]:
    try:
        start_time    = time.perf_counter()
        texto_imagem = retorna_texto(input_path)
        if len(texto_imagem) < 300:
            return [failure(reason="Não foi possível identificar com precisão o texto da imagem", solution="", file_path=input_path, original_path=input_path),]
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
            arq.write(texto_imagem)


        return [
            success(
                file_path=txt_path,
                original_path=input_path,
                find_cols=[],
                execution_time_seconds=round(time.perf_counter() - start_time, 4),
                warning="Esse era um arquivo de image, portanto foi convertido diretamente para txt."
            ), 
        ]
    except Exception as e:
        return [failure(reason=f"{traceback.format_exc()}", solution="", file_path=input_path, original_path=input_path),]

