"""
config/urls.py
---------------
Arquivo raiz de rotas do projeto. O Django olha aqui primeiro para saber
para onde mandar cada requisição, dependendo da URL acessada.

Aqui só definimos duas coisas:
1. A rota do admin (/admin/), que já vem pronta com o Django.
2. Um "include" que delega TODAS as outras rotas para o arquivo loja/urls.py,
   que é onde de fato colocamos as URLs do nosso e-commerce.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),          # painel administrativo do Django
    path('healthz/', include('loja.health_urls')),  # endpoint usado pelo HEALTHCHECK do Docker
    path('', include('loja.urls')),           # todas as outras URLs vêm do app "loja"
]

# Os arquivos ESTÁTICOS (CSS/JS) são servidos pelo WhiteNoise em qualquer
# ambiente (inclusive com DEBUG=False, dentro do container). Já os arquivos
# de MÍDIA (uploads, ex: imagem do produto) não têm um "WhiteNoise" pronto,
# então em desenvolvimento pedimos ao próprio Django para servi-los.
# Em um projeto de produção "de verdade" (fora do escopo da entrega), o ideal
# seria usar um serviço de armazenamento externo (S3, etc.) para mídia.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
