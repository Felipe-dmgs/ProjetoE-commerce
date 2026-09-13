"""
loja/health_urls.py
--------------------
Arquivo de rotas separado só para o endpoint de healthcheck (/healthz/).
Mantido separado do loja/urls.py (que tem o app_name='loja') só para deixar
esse endpoint técnico sem namespace, já que ele não faz parte do "fluxo da
loja" em si — é usado pelo Docker para saber se o container está saudável.
"""

from django.urls import path

from . import views

urlpatterns = [
    path('', views.healthcheck, name='healthcheck'),
]
