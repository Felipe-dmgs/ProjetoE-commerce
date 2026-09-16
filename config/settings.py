"""
settings.py
-----------
Arquivo central de configurações do projeto Django.
Aqui definimos: quais apps estão instalados, qual banco de dados usar,
onde ficam os templates, arquivos estáticos, etc.
"""

import os
from pathlib import Path

# BASE_DIR aponta para a pasta raiz do projeto (onde está o manage.py).
# Usamos isso para montar caminhos de forma relativa, sem "chumbar" caminhos fixos.
BASE_DIR = Path(__file__).resolve().parent.parent

# --------------------------------------------------------------------------
# SEGURANÇA
# --------------------------------------------------------------------------

# Chave secreta usada pelo Django para criptografia interna (sessions, tokens, etc.)
# Em produção (Docker), o valor real vem do arquivo .env / docker-compose.yml.
# O valor abaixo só é usado como "padrão" caso a variável não exista (ex: dev local).
SECRET_KEY = os.environ.get(
    'SECRET_KEY',
    'django-insecure-troque-esta-chave-em-producao-0123456789',
)

# DEBUG=True mostra páginas de erro detalhadas — ótimo para aprender/depurar,
# mas deve ser False quando o projeto for colocado em produção.
# A variável de ambiente sempre chega como string ("True"/"False"), então
# comparamos com 'True' explicitamente.
DEBUG = os.environ.get('DEBUG', 'True') == 'True'

# Lista de domínios/IPs que podem acessar o projeto, separados por vírgula.
# Ex.: ALLOWED_HOSTS=localhost,127.0.0.1,meusite.com
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

# --------------------------------------------------------------------------
# APLICAÇÕES INSTALADAS
# --------------------------------------------------------------------------

INSTALLED_APPS = [
    'django.contrib.admin',        # painel administrativo pronto do Django
    'django.contrib.auth',         # sistema de autenticação (usuários/login)
    'django.contrib.contenttypes', # suporte interno usado por outros apps
    'django.contrib.sessions',     # framework de sessões (usaremos para o carrinho!)
    'django.contrib.messages',     # sistema de mensagens (ex: "Produto adicionado!")
    'django.contrib.staticfiles',  # gerenciamento de arquivos estáticos (CSS/JS)

    'loja',  # nosso app principal, onde está toda a lógica do e-commerce
]

# --------------------------------------------------------------------------
# MIDDLEWARES
# --------------------------------------------------------------------------
# Middlewares são "camadas" que processam toda requisição/resposta HTTP,
# nessa ordem, de cima para baixo (na requisição) e de baixo para cima (na resposta).

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    # WhiteNoise serve os arquivos estáticos (CSS/JS) diretamente pelo próprio
    # processo do Django/Gunicorn, sem precisar de um Nginx separado. Precisa
    # ficar logo depois do SecurityMiddleware.
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',  # habilita request.session (usado pelo carrinho)
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',              # proteção contra ataques CSRF nos formulários
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'  # diz ao Django onde está o arquivo principal de rotas (urls.py)

# --------------------------------------------------------------------------
# TEMPLATES (HTML)
# --------------------------------------------------------------------------

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        # Além dos templates de cada app (loja/templates/loja/...),
        # também podemos ter uma pasta global de templates aqui:
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,  # permite que o Django procure templates dentro de cada app automaticamente
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# --------------------------------------------------------------------------
# BANCO DE DADOS
# --------------------------------------------------------------------------
# Agora usamos PostgreSQL, configurado 100% por variáveis de ambiente.
# Isso é o que permite que o mesmo settings.py funcione:
#   - rodando dentro do Docker Compose (onde DATABASE_HOST='db', o nome do
#     serviço do Postgres no docker-compose.yml)
#   - ou apontando para um Postgres local, se você preferir rodar sem Docker
#     (nesse caso, basta exportar as variáveis ou criar um .env com
#     DATABASE_HOST=localhost).
#
# Se quiser voltar a usar SQLite rapidamente (ex: só para testes), basta
# comentar este bloco e usar o bloco antigo com 'django.db.backends.sqlite3'.

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DATABASE_NAME', 'ecommerce'),
        'USER': os.environ.get('DATABASE_USER', 'ecommerce'),
        'PASSWORD': os.environ.get('DATABASE_PASSWORD', 'ecommerce'),
        # 'db' é o nome do serviço do Postgres dentro do docker-compose.yml —
        # o Docker resolve esse nome como se fosse um endereço de rede.
        'HOST': os.environ.get('DATABASE_HOST', 'localhost'),
        'PORT': os.environ.get('DATABASE_PORT', '5432'),
    }
}

# --------------------------------------------------------------------------
# VALIDAÇÃO DE SENHA (usado se você criar sistema de login de usuários)
# --------------------------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# --------------------------------------------------------------------------
# INTERNACIONALIZAÇÃO
# --------------------------------------------------------------------------

LANGUAGE_CODE = 'pt-br'   # textos padrão do Django (admin, validações) em português
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True

# --------------------------------------------------------------------------
# ARQUIVOS ESTÁTICOS (CSS, JS) E DE MÍDIA (uploads, ex: imagem do produto)
# --------------------------------------------------------------------------

STATIC_URL = 'static/'
# Pasta onde o comando "collectstatic" vai JUNTAR todos os arquivos estáticos
# (de todos os apps) em um único lugar, pronto para ser servido em produção.
# O entrypoint.sh do Docker roda "collectstatic" automaticamente ao iniciar.
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Faz o WhiteNoise comprimir e cachear os arquivos estáticos automaticamente.
STORAGES = {
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}

# Arquivos de MÍDIA são uploads feitos pelos usuários (ex: Produto.imagem).
# São diferentes dos estáticos porque mudam em tempo de execução, não fazem
# parte do código-fonte do projeto.
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

# --------------------------------------------------------------------------
# LOGGING (registro de erros)
# --------------------------------------------------------------------------
# Por padrão, o Django só imprime erros 500 no console quando DEBUG=True —
# com DEBUG=False (nosso caso em produção/Docker), os erros vão só para
# "mail_admins" (e-mail), que não está configurado aqui, então o erro
# "desaparece" e você só vê o "500" genérico no navegador.
#
# Esta configuração força que QUALQUER erro (mesmo com DEBUG=False) seja
# impresso no console — que é exatamente o que aparece em "docker logs" /
# "docker compose logs web". Essencial para depurar dentro de containers,
# já que não temos acesso a uma tela de erro do Django lá.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
        },
        'django.request': {
            # É este logger específico que recebe as exceptions de views
            # (erros 500). Colocamos nível DEBUG para não perder nada, e
            # propagate=False para não duplicar a mensagem no logger "django".
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}

# --------------------------------------------------------------------------
# CHAVE PRIMÁRIA PADRÃO
# --------------------------------------------------------------------------
# Define o tipo de campo usado automaticamente como "id" em modelos que não
# especificam uma chave primária customizada.
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# --------------------------------------------------------------------------
# AUTENTICAÇÃO
# --------------------------------------------------------------------------
# Para onde o Django manda o usuário quando uma view marcada com
# @login_required é acessada sem estar logado.
LOGIN_URL = 'loja:login'
# Para onde o Django manda o usuário depois de um login bem-sucedido (quando
# não há um "?next=" na URL) e depois de um logout, respectivamente.
LOGIN_REDIRECT_URL = 'loja:lista_produtos'
LOGOUT_REDIRECT_URL = 'loja:lista_produtos'

# --------------------------------------------------------------------------
# CONFIGURAÇÕES DO CARRINHO (usadas pelo nosso código em loja/cart.py)
# --------------------------------------------------------------------------
# Nome da chave que vamos usar dentro da sessão do usuário para guardar o carrinho.
CART_SESSION_ID = 'carrinho'