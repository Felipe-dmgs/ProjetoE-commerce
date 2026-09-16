"""
asgi.py
-------
Equivalente ao wsgi.py, mas para servidores assíncronos (ASGI). Não é
necessário para este projeto, mas o Django cria por padrão.
"""
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
application = get_asgi_application()
