import csv
from pathlib import Path
from contextlib import ExitStack
import logging
import traceback
import anthropic
import os, time, json
from contextlib import ExitStack
from pathlib import Path
from utils.reporter_base import Report, failure, success
from typing import Optional
from utils.constants import API_KEY

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Dicionário de Schemas oficiais do SPED (Exemplo: EFD ICMS/IPI)
# IMPORTANTE: Como sua variável `dados` remove o campo[1] (o próprio nome do registro, ex: 'C100'),
# a lista abaixo mapeia diretamente os campos seguintes ao tipo de registro.


with open("utils/sped_schemas.json", "r", encoding="utf-8") as arq:
    SPED_SCHEMAS = json.load(arq)



def _detect_encoding(path: Path) -> str:
    return "latin1"

def _retorna_data(path):
    client = anthropic.Anthropic(api_key=API_KEY)

    prompt = f""""
    A partir do nome do arquivo "{path}"
    retorne o mẽs e ano de referẽncia no formato YYYY_MM
    Não retorne comentários ou explicações, apenas o YYYY_MM
    Se não encontrar o ano ou o mês, retorne substituindo o que faltar por 00. Exemplo com mês não encontrado: 2021_00
    Formatos de retorno válidos:
    1. 2022_01
    2. 2003_12
    3. 2019_00
    4. 0000_06
    """

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=7,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text.strip()

def _retorna_tipo_sped(path):
    client = anthropic.Anthropic(api_key=API_KEY)

    prompt = f""""
    A partir do nome do arquivo "{path}"
    Retorne o tipo de SPED que ele se qualifica. Retorne apenas o tipo de sped sem explicações ou comentários.
    Formatos de retorno válidos:
    1. ECD
    2. EFD
    """

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=7,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text.strip()

def validate_sped_file(path: Path) -> tuple[bool, str | None]:
    if path.suffix.lower() != ".txt":
        return False, f"UnsupportedExtension: Esperado .txt, recebido {path.suffix}"
    try:
        raw_sample = path.read_bytes()[:512]
        if b"\x00" in raw_sample:
            return False, "BinaryContentError: arquivo contém null bytes."
    except Exception as exc:
        return False, f"FileReadError: {exc}"
    return True, None

def parse_sped_to_csvs(sped_path: Path, output_dir: Path) -> list[dict]:
    """
    Processa um arquivo SPED e gera um CSV por tipo de registro.
 
    Args:
        sped_path:  Caminho para o arquivo SPED de entrada.
        output_dir: Diretório raiz onde os CSVs serão gravados.
 
    Returns:
        Lista de dicts com relatório de execução.
        - Sucesso: um dict por tipo de registro gerado, contendo path, colunas, tempo, etc.
        - Falha:   lista com um único dict descrevendo o erro e sugestão de solução.
    """
    sped_path = Path(sped_path)
    output_dir = Path(output_dir)

    data = _retorna_data(sped_path)
    ano = data.split("_")[0]
    mes = data.split("_")[1]
    output_path = (
        output_dir
        / ano
        / mes
        / "SPED"
        / _retorna_tipo_sped(sped_path)
    )
    
 
    # --- Validação inicial ---
    is_valid, err_msg = validate_sped_file(sped_path)
    if not is_valid:
        return [failure(
            file_path=sped_path,
            reason=err_msg or "Arquivo SPED inválido.",
            solution="Verifique se o arquivo existe e está no formato SPED correto.",
        ), ]
 
    encoding = _detect_encoding(sped_path)
    output_dir.mkdir(parents=True, exist_ok=True)
 
    global_id = 0
    contexto_pai: dict[str, Optional[int]] = {"C100": None, "D100": None, "H005": None}
    cols_por_registro: dict[str, list[str]] = {}   # acumula colunas para o relatório
 
    start_time = time.perf_counter()
 
    with ExitStack() as stack:
        writers: dict[str, csv.writer] = {}
 
        try:
            with open(sped_path, "r", encoding=encoding) as sped_file:
                
                output_path.mkdir(parents=True, exist_ok=True)
 
                for line in sped_file:
                    line = line.strip()
                    if not line or not line.startswith("|"):
                        continue
 
                    campos = line.split("|")
                    if len(campos) < 3:
                        continue
 
                    registro_tipo = campos[1]
                    dados = campos[2:-1]
 
                    global_id += 1
                    row_id = global_id
                    parent_id: Optional[int] = None
 
                    # Controle de contexto pai-filho
                    if registro_tipo in contexto_pai:
                        contexto_pai[registro_tipo] = row_id
                    elif registro_tipo in ("C170", "C190"):
                        parent_id = contexto_pai["C100"]
                    elif registro_tipo == "D190":
                        parent_id = contexto_pai["D100"]
                    elif registro_tipo == "H010":
                        parent_id = contexto_pai["H005"]
 
                    # Inicialização lazy: cria o CSV e escreve o cabeçalho apenas
                    # na primeira ocorrência do tipo de registro
                    if registro_tipo not in writers:
                        csv_path = output_path / f"{registro_tipo}.csv"
                        f_out = stack.enter_context(
                            open(csv_path, "w", newline="", encoding="utf-8")
                        )
                        writer = csv.writer(f_out, delimiter=";")
 
                        colunas_schema = SPED_SCHEMAS.get(registro_tipo)
 
                        if colunas_schema:
                            if len(dados) > len(colunas_schema):
                                extra = len(dados) - len(colunas_schema)
                                campos_finais = colunas_schema + [
                                    f"CAMPO_EXTRA_{i+1}" for i in range(extra)
                                ]
                            else:
                                campos_finais = colunas_schema[: len(dados)]
                        else:
                            campos_finais = [f"CAMPO_{i+1}" for i in range(len(dados))]
 
                        writer.writerow(["id", "parent_id"] + campos_finais)
                        writers[registro_tipo] = writer
                        cols_por_registro[registro_tipo] = campos_finais
 
                    writers[registro_tipo].writerow(
                        [row_id, parent_id if parent_id is not None else ""] + dados
                    )
 
        except Exception:
            elapsed = round(time.perf_counter() - start_time, 4)
            reason = traceback.format_exc()
            return [failure(
                file_path=sped_path,
                reason=reason,
                solution=(
                    "Verifique se o arquivo SPED não está corrompido "
                    "e se todas as dependências estão instaladas."
                ),
            ),]
 
    elapsed = round(time.perf_counter() - start_time, 4)
 
    # Relatório de sucesso — um entry por tipo de registro gerado
    return [
        success(
            file_path=Path(str(output_path / f"{registro}.csv")),
            execution_time_seconds=elapsed,
            find_cols=colunas,
        )
        for registro, colunas in cols_por_registro.items()
    ]
# Exemplo de uso:
if __name__ == "__main__":
    result = parse_sped_to_csvs(Path("Arquivos/II/SPED 2019/59275792000150-636003724112-20190101-20190131-0-6AB91828942ECBB35F053441BFEBD0FD0E8C11BA-SPED-EFD.txt"), Path("Tratados"))
    