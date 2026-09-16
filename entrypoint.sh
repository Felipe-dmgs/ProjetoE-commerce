set -e

echo ">> Aguardando o PostgreSQL aceitar conexoes..."
# Mesmo com o healthcheck do banco no docker-compose.yml garantindo que o
# Postgres já está de pé antes deste container iniciar, fazemos aqui uma
# segunda checagem simples via Python, como camada extra de segurança
# (ex: caso você rode este script fora do Compose, sem o "depends_on").
python << 'PYCODE'
import os
import sys
import time

import psycopg2

host = os.environ.get('DATABASE_HOST', 'db')
port = os.environ.get('DATABASE_PORT', '5432')
nome = os.environ.get('DATABASE_NAME', 'ecommerce')
usuario = os.environ.get('DATABASE_USER', 'ecommerce')
senha = os.environ.get('DATABASE_PASSWORD', 'ecommerce')

tentativas = 30
for tentativa in range(1, tentativas + 1):
    try:
        conexao = psycopg2.connect(
            host=host, port=port, dbname=nome, user=usuario, password=senha,
        )
        conexao.close()
        print('>> PostgreSQL disponivel!')
        break
    except psycopg2.OperationalError:
        print(f'>> Postgres ainda nao respondeu (tentativa {tentativa}/{tentativas})...')
        time.sleep(2)
else:
    print('>> Nao foi possivel conectar ao Postgres a tempo.', file=sys.stderr)
    sys.exit(1)
PYCODE

python manage.py makemigrations --noinput

python manage.py migrate --noinput

python manage.py collectstatic --noinput

echo ">> Subindo o Gunicorn..."
# --bind 0.0.0.0:8000 -> aceita conexoes de fora do container
# --workers 3         -> numero de processos que atendem requisicoes em paralelo
# --access-logfile -  -> manda o log de acesso para a saida padrao (aparece no "docker logs")
exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 3 \
    --access-logfile - \
    --error-logfile -
