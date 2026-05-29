import subprocess
import sys
import os

def run_command(command, description):
    """Executa um comando no terminal e trata possíveis erros."""
    print(f"[*] {description}...")
    try:
        # shell=True permite executar os comandos como strings no terminal
        result = subprocess.run(command, shell=True, check=True, text=True, capture_output=True)
        print(f"[+] {description} concluído com sucesso.")
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"[-] Erro ao executar: {description}")
        print(f"Detalhes do erro:\n{e.stderr}")
        sys.exit(1)

def main():
    # 1. Garante que o repositório local está atualizado (Faz o Git Pull)
    # Nota: O git pull assume que você já clonou o repositório e está na branch correta.
    run_command("git init .", "Iniciando Git no local")
    run_command("git pull https://github.com/SamuelSGSouza/Handle_Documents.git", "Atualizando o repositório local via Git Pull")

    # 2. Instala/Reinstala as dependências do requirements.txt
    # O argumento --force-reinstall garante a reinstalação, como solicitado.
    if os.path.exists("requirements.txt"):
        run_command(f"{sys.executable} -m pip install -r requirements.txt --force-reinstall", "Instalando/Reinstalando dependências do requirements.txt")
    else:
        print("[-] Arquivo 'requirements.txt' não encontrado no diretório atual. Pulando esta etapa.")

    # 3. Chama a função main_start() do app.py
    print("[*] Iniciando a aplicação (controler_trats.py -> main_start)...")
    try:
        # Importa dinamicamente o app.py para chamar a função diretamente no mesmo processo Python
        import controler_trats
        if hasattr(controler_trats, 'start_conversions'):
            controler_trats.start_conversions()
        else:
            print("[-] Erro: A função 'start_conversions()' não foi encontrada dentro de 'controler_tasks.py'.")
    except ImportError:
        print("[-] Erro: Não foi possível encontrar o arquivo 'app.py' no diretório atual.")
    except Exception as e:
        print(f"[-] Erro ao executar a função principal: {e}")

if __name__ == "__main__":
    main()