import camelot
import pandas as pd
import pymupdf4llm

arquivo = "Arquivos/V/1. 13868.7445082023-60/13868.7445082023-60_Laudo.pdf"

tables = camelot.read_pdf(arquivo, flavor="lattice")
if tables: #Se possui uma tabela identificável
    df = tables[0].df.copy()

    # --- Reconstrução do header ---
    # 1. Concatena as primeiras linhas até encontrar a primeira linha com dados reais
    # (heurística: linha de header tem mais células não-vazias que as seguintes "continuation" rows)

    def find_header_rows(df: pd.DataFrame, max_header_rows: int = 4) -> int:
        """
        Detecta quantas linhas iniciais formam o cabeçalho.
        Critério: linhas do header tendem a ter células com texto curto e sem padrões de dados
        (ex: números de processo, datas). Retorna o índice da primeira linha de dados.
        """
        for i in range(1, max_header_rows + 1):
            row = df.iloc[i]
            # Se a linha parecer dado real (tem padrão de número de processo ou está preenchida)
            non_empty = row.astype(str).str.strip().ne("").sum()
            has_process_number = row.astype(str).str.contains(r"\d{5}\.\d{6}/\d{4}-\d{2}").any()
            if has_process_number or non_empty >= len(df.columns) * 0.5:
                return i
        return 1

    header_end = find_header_rows(df)

    # 2. Junta as linhas de cabeçalho (concatena com espaço, removendo vazios)
    header_parts = df.iloc[:header_end].values
    new_columns = []
    for col_idx in range(df.shape[1]):
        parts = [str(header_parts[row_idx][col_idx]).strip() 
                for row_idx in range(header_end) 
                if str(header_parts[row_idx][col_idx]).strip()]
        new_columns.append(" ".join(parts))

    # 3. Aplica header e descarta as linhas usadas
    df.columns = new_columns
    df = df.iloc[header_end:].reset_index(drop=True)

    # 4. Remove linhas completamente vazias
    df = df[df.astype(str).apply(lambda r: r.str.strip().ne("").any(), axis=1)]

    df.to_csv("Teste.csv", sep=";", index=False)

md = pymupdf4llm.to_markdown(arquivo)
with open("Teste.md", "w", encoding="utf-8") as arq:
    arq.write(md)