import json

with open("Relatório das Conversões.json", "r", encoding="utf-8") as arq:
    relatorio = json.load(arq)


new_list_res = []
for item in relatorio:
    new_dict_res = {}

    if item["result"] == "failure":
        for k,v in item.items():
            new_dict_res[k] = v
        new_list_res.append(new_dict_res)


with open("Relatório das Conversões Resumido.json", "w", encoding="utf-8") as arq:
    json.dump(new_list_res, arq, indent=4, ensure_ascii=False)
