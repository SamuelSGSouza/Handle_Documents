import os
from trats.trat_csv import parse_csv
from trats.trat_planilhas import convert_xls_to_csv
from trats.trat_sped import parse_sped_to_csvs
from trats.trat_pdf import parse_pdf_to_csv
from utils.reporter_base import Report, failure
from utils.gerar_exemplos import gerar_exemplos
from pathlib import Path
import json, shutil
import pandas as pd



def conversor(input_dir: str, output_dir: str, files_to_reload:list=[]) -> list[Report]:
    all_reports: list[Report] = []
    input_path = Path(input_dir)

    files_to_reload = "\n".join(files_to_reload)
    for filepath in input_path.rglob("*"):
        if not filepath.is_file():
            continue
        
        file = filepath.name
        if files_to_reload:
            if file not in files_to_reload:
                continue
        print(f"Tratando arquivo: {filepath}")
        if file.endswith(".pdf"):
            reports = parse_pdf_to_csv(str(filepath), output_dir)
        # if file.endswith(".csv"):
        #     reports = parse_csv(str(filepath), output_dir)
        
        # elif "sped" in file.lower():
        #     reports = parse_sped_to_csvs(str(filepath), output_dir)
        # elif file.endswith("xlsx") or file.endswith("xlsb"):
        #     reports = convert_xls_to_csv(str(filepath), output_dir)
        else:
            reports = [
                failure(
                    reason="Arquivo possui um formato ou nomenclatura não suportada",
                    solution="Verifique o formato e nomenclatura e crie uma função de tratamento caso necessário.",
                    file_path=filepath
                ),
            ]
        all_reports += reports

    return all_reports

def start_conversions(input_folder="+ Documentos Recebidos", output_folder="Resultados"):

    path_relatorio_json = os.path.join(output_folder, "Relatório das Conversões.json")
    path_relatorio_csv = os.path.join(output_folder, "Relatório das Conversões.csv")

    #Apagando a pasta caso exista
    if os.path.exists(output_folder):
        shutil.rmtree(output_folder)

    #Recriando a pasta
    os.makedirs(output_folder, exist_ok=True)

    destino_arquivos = os.path.join(output_folder, "Tratados")
    os.makedirs(destino_arquivos, exist_ok=True)

    reports = conversor(input_folder,  destino_arquivos)
    with open(path_relatorio_json, "w", encoding="utf-8") as arq:
        json.dump(reports, arq, indent=4, ensure_ascii=False)

    with open(path_relatorio_json, "r", encoding="utf-8") as arq:
        relatorio = json.load(arq)

    df = pd.DataFrame(relatorio)

    df["find_cols"] = df["find_cols"].apply(lambda x: x[:100])
    df.to_csv(path_relatorio_csv, sep=";")
    
    gerar_exemplos(Path(output_folder), Path("Exemplos"))

if __name__ == "__main__":
    pass
    