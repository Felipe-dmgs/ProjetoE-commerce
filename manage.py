import os
import sys


def main():
    """Função principal que o Django usa para descobrir as configurações do projeto
    e repassar o comando digitado no terminal (ex: runserver) para o Django tratar."""

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Não foi possível importar o Django. Verifique se ele está instalado "
            "e se o ambiente virtual está ativado."
        ) from exc

    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
