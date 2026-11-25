from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),          # painel administrativo do Django
    path('healthz/', include('loja.health_urls')),  # endpoint usado pelo HEALTHCHECK do Docker
    path('api/', include('loja.api_urls')),   # API REST (DRF): produtos, cupons e pedidos
    path('api-auth/', include('rest_framework.urls')),  # login/logout da Browsable API
    path('', include('loja.urls')),           # todas as outras URLs vêm do app "loja"
]

# Os arquivos ESTÁTICOS (CSS/JS) são servidos pelo WhiteNoise em qualquer
# ambiente (inclusive com DEBUG=False, dentro do container). Já os arquivos
# de MÍDIA (uploads, ex: imagem do produto) não têm um "WhiteNoise" pronto,
# então em desenvolvimento pedimos ao próprio Django para servi-los.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
