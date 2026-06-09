from pathlib import Path

input_dir = "Arquivos"
input_path = Path(input_dir)
for filepath in input_path.rglob("*"):
    print(filepath)