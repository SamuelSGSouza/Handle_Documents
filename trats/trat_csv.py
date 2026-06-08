import time
import chardet
import pandas as pd
from utils.reporter_base import failure, success
import csv
from pathlib import Path
import shutil
import anthropic
from utils.constants import API_KEY
import traceback


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

def parse_csv(file_path, input_dir, output_dir):
    start_time = time.perf_counter()
    try:
        encoding  = _detectar_encoding_csv(file_path)
        delimiter = _detectar_sep_csv(file_path)
        df        = pd.read_csv(file_path, sep=delimiter, dtype=str, encoding=encoding)
        colunas   = df.columns.tolist()
        elapsed   = round(time.perf_counter() - start_time, 4)

        categoria = retorna_categoria(file_path)

        if categoria == "OUTROS":
            relative = Path(file_path).relative_to(Path(input_dir))
            dest_dir = Path(output_dir) / relative.parent
        else:
            data_referencia = _retorna_data(file_path)
            partes = data_referencia.split("_")
            if len(partes) != 2:
                raise ValueError(f"data_referencia inválida: {data_referencia!r}")
            ano, mes = partes
            dest_dir = Path(output_dir) / categoria / ano / mes

        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_file = dest_dir / Path(file_path).name
        shutil.copy2(file_path, dest_dir)

        return [success(
            file_path=str(dest_file),
            find_cols=colunas,
            execution_time_seconds=elapsed,
        ),]

    except Exception as e:
        return [failure(
            reason=f"Falha desconhecida: {traceback.format_exc()}",
            solution="Verifique se o arquivo realmente existe e se é um csv válido.",
            file_path=Path(file_path),
        ),]
    

def _detectar_sep_csv(caminho: str, encoding: str = "latin-1", amostra: int = 4096):
    """Tenta inferir o separador (“delimiter”) de um CSV/TXT.

    Retorna o separador detectado (str). Se não conseguir, devolve ';' como padrão.
    """
    with open(caminho, "r", encoding=encoding, newline="") as f:
        sample = f.read(amostra)

    try:
        # Testa apenas separadores mais comuns para evitar falsos-positivos
        dialect = csv.Sniffer().sniff(sample, delimiters=[",", ";", "\t", "|"])
        return dialect.delimiter
    except csv.Error:
        # Fallback bem trivial: conta qual char aparece mais na primeira linha
        primeira_linha = sample.splitlines()[0] if sample else ""
        candidatos = [",", ";", "\t", "|"]
        frequencias = {c: primeira_linha.count(c) for c in candidatos}
        mais_comum = max(frequencias, key=frequencias.get)
        return mais_comum if frequencias[mais_comum] > 0 else ";"

def _detectar_encoding_csv(caminho, amostra=16000):
    with open(caminho, 'rb') as f:
        rawdata = f.read(amostra)
    resultado = chardet.detect(rawdata)
    encoding = resultado['encoding']
    # Prioriza utf-8 se for aceito ou default conhecido
    if encoding is None:
        return 'latin-1'  # fallback genérico
    if encoding.lower().replace('-', '') in ['utf8', 'utf']:
        return 'utf-8'
    if encoding.lower() == 'ascii':
        return 'latin-1'
    # Latin-1 raramente falha na leitura, mas pode mascarar problemas
    return encoding

if __name__ == "__main__":
    result = parse_csv("Arquivos/Export_2021__Export2021.csv", "+ Documentos","Tratados")
