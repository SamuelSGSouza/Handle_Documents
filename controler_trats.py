import os
from trat_csv import parse_csv
from trat_planilha import xls_to_csvs
from trat_planilhas_homolog import convert_xls_to_csv
from trat_sped import parse_sped_to_csvs
from reporter_base import Report, failure
from pathlib import Path
import json, shutil

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
        

        if file.endswith(".csv"):
            reports = parse_csv(str(filepath), output_dir)
        elif "sped" in file.lower():
            reports = parse_sped_to_csvs(str(filepath), output_dir)
        elif file.endswith("xlsx") or file.endswith("xlsb"):
            reports = convert_xls_to_csv(str(filepath), output_dir)
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

def start_conversions(input_folder="Arquivos", output_folder="Tratados"):
    #Apagando a pasta caso exista
    if os.path.exists(output_folder):
        shutil.rmtree(output_folder)

    #Recriando a pasta
    os.makedirs(output_folder, exist_ok=True)

    reports = conversor(input_folder,output_folder )
    with open("Relatório das Conversões.json", "w", encoding="utf-8") as arq:
        json.dump(reports, arq, indent=4, ensure_ascii=False)

def restart_conversions(input_folder="Arquivos", output_folder="Tratados"):
    nome_relatorio = "Relatório das Conversões.json"
    #Apagando a pasta caso exista
    if not os.path.exists(nome_relatorio):
        raise FileNotFoundError("O arquivo de relatório não existe. Primeiro execute as conversões para depois reiniciar")

    with open(nome_relatorio, "r", encoding="utf-8") as arq:
        relatorio = json.load(arq)
    
    print("Quantidade de sucessos: ", len(relatorio))

    files_to_reload = [item["path"] for item in relatorio if item["result"]=="failure"]
    print("Quantidade de falhas: ", len(files_to_reload))

    with open("Relatório das Conversões 2.json", "r", encoding="utf-8") as arq:
        relatorio_revisao = json.load(arq)

    print("Quantidade de sucessos na revisão: ", len(relatorio_revisao))
    ainda_falhas = [f for f in files_to_reload if f in str(relatorio_revisao)]
    print("Quantidade de Falhas que ainda são falhas após a revisão: ", len(ainda_falhas))

    # reports = conversor(input_folder,output_folder, files_to_reload)
    # novo_relatorio = [item for item in relatorio if item["path"] not in files_to_reload]
    # novo_relatorio += reports
    # with open("Relatório das Conversões 2.json", "w", encoding="utf-8") as arq:
    #     json.dump(reports, arq, indent=4, ensure_ascii=False)

if __name__ == "__main__":
    restart_conversions()