#!/usr/bin/env python
"""
manage.py
---------
Arquivo padrão que o Django gera automaticamente em todo projeto.
É por meio dele que rodamos os comandos do Django, por exemplo:

    python manage.py runserver      -> liga o servidor local
    python manage.py makemigrations -> gera as "migrações" (scripts de criação/alteração de tabelas)
    python manage.py migrate        -> aplica as migrações no banco de dados
    python manage.py createsuperuser-> cria um usuário admin

Você não costuma precisar mexer neste arquivo.
"""
import os
import sys


def main():
    """Função principal que o Django usa para descobrir as configurações do projeto
    e repassar o comando digitado no terminal (ex: runserver) para o Django tratar."""

    # Diz ao Django onde estão as configurações (settings.py) deste projeto.
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Não foi possível importar o Django. Verifique se ele está instalado "
            "e se o ambiente virtual está ativado."
        ) from exc

    # Executa o comando que foi digitado no terminal (sys.argv contém os argumentos)
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
