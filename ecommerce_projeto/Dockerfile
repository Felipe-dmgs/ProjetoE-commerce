# Dockerfile
# ----------
# Descreve como construir a imagem do container que vai rodar o Django
# (via Gunicorn). O Postgres NÃO entra aqui — ele usa uma imagem pronta,
# definida diretamente no docker-compose.yml.

# Imagem base: Python "slim" = versão enxuta do Debian com Python já instalado.
FROM python:3.12-slim

# Evita que o Python crie arquivos .pyc (desnecessário dentro do container)
# e faz os logs (print, etc.) aparecerem imediatamente no "docker logs",
# sem ficar "presos" em buffer.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Pasta onde o projeto vai viver dentro do container.
WORKDIR /app

# Dependências de sistema operacional (não são bibliotecas Python):
#   - libpq-dev e gcc: necessários para compilar/rodar o psycopg2 (driver do Postgres)
#   - curl: usado pelo HEALTHCHECK, para "bater" no endpoint /healthz/
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpq-dev \
        gcc \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Copiamos primeiro só o requirements.txt (e instalamos) antes de copiar o
# resto do código. Isso é uma otimização de cache do Docker: se você mudar
# só o código depois, o Docker não precisa reinstalar as dependências de novo.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Agora sim copiamos todo o restante do projeto para dentro do container.
COPY . .

# Torna o entrypoint executável (o Git às vezes não preserva essa permissão).
RUN chmod +x /app/entrypoint.sh

# Porta em que o Gunicorn vai escutar dentro do container.
EXPOSE 8000

# HEALTHCHECK: o Docker roda este comando periodicamente para decidir se o
# container está "saudável". Aqui, consideramos saudável quando o endpoint
# /healthz/ responde HTTP 200 (o que só acontece se o Django conseguir
# consultar o Postgres com sucesso — veja loja/views.py:healthcheck).
#   --interval: de quanto em quanto tempo verifica
#   --timeout:  quanto tempo espera por resposta antes de considerar falha
#   --start-period: tempo de "tolerância" inicial (migrations/collectstatic
#                    podem demorar um pouco na primeira subida)
#   --retries:  quantas falhas seguidas até marcar como "unhealthy"
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=5 \
    CMD curl -f http://localhost:8000/healthz/ || exit 1

# Script que roda migrations/collectstatic e depois sobe o Gunicorn.
ENTRYPOINT ["/app/entrypoint.sh"]
