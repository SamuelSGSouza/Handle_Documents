import time
import chardet
import pandas as pd
from reporter_base import failure, success
import csv
from pathlib import Path
import shutil

def parse_csv(file_path, output_dir):
    start_time = time.perf_counter()
    try:
        encoding = _detectar_encoding_csv(file_path)
        delimiter = _detectar_sep_csv(file_path)
        df = pd.read_csv(file_path, sep=delimiter, dtype=str, encoding=encoding)
        colunas = df.columns.tolist()
        elapsed = round(time.perf_counter() - start_time, 4)

        output_path = Path(output_dir) / Path(file_path).name  # define o destino
        shutil.copy2(file_path, output_path)                   # copia o arquivo

        return success(
            file_path=output_path,
            find_cols=colunas,
            execution_time_seconds=elapsed
        )
    except Exception as e:
        return failure(
            reason=f"Falha desconhecida: {e}",
            solution="Verifique se o arquivo realmente existe e se é um csv válido.",
            file_path=Path(file_path)
        )
    

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
    result = parse_csv("Arquivos/Export_2021_V2__Export2021_InvoiceData.csv", "Tratados")
