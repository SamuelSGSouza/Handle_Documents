import os
from trat_csv import parse_csv
from trat_planilha import xls_to_csvs
from trat_sped import parse_sped_to_csvs
from reporter_base import Report, failure
from pathlib import Path
import json

def conversor(input_dir:str, output_dir:str):
    all_reports:list[Report] = []
    for file in os.listdir(input_dir):
        filepath = os.path.join(input_dir, file)
        if file.endswith(".csv"):
            reports = parse_csv(filepath, output_dir)
        elif "sped" in file.lower():
            reports = parse_sped_to_csvs(filepath, output_dir)
        elif file.endswith("xlsx") or file.endswith("xlsb"):
            reports = xls_to_csvs(filepath, output_dir)
        else:
            reports = [
                failure(
                    reason="Arquivo possui um formato ou nomenclatura não suportada",
                    solution="Verifique o formato e nomenclatura e crie uma função de tratamento caso necessário.",
                    file_path=Path(filepath)
                ),
            ]
        all_reports += reports

    return all_reports

if __name__ == "__main__":
    reports = conversor("Arquivos", "Tratados")
    with open("report_conversions.json", "w", encoding="utf-8") as arq:
        json.dump(reports, arq, indent=4, ensure_ascii=False)