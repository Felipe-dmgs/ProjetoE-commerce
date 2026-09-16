"""
wsgi.py
-------
Ponto de entrada usado por servidores de produção (ex: Gunicorn) para rodar
o projeto Django via protocolo WSGI. Para desenvolvimento local, você não
usa este arquivo diretamente (usa o "python manage.py runserver").
"""
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
application = get_wsgi_application()
