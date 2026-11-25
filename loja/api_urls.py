from django.urls import path

from . import api_views

app_name = 'api'

urlpatterns = [
    path('produtos/', api_views.ProdutoListCreateAPIView.as_view(), name='produto_lista'),
    path('produtos/<int:pk>/', api_views.ProdutoDetailAPIView.as_view(), name='produto_detalhe'),
    path('cupons/', api_views.CupomListCreateAPIView.as_view(), name='cupom_lista'),
    path('cupons/<int:pk>/', api_views.CupomDetailAPIView.as_view(), name='cupom_detalhe'),
    path('pedidos/', api_views.PedidoListAPIView.as_view(), name='pedido_lista'),
    path('pedidos/<int:pk>/', api_views.PedidoDetailAPIView.as_view(), name='pedido_detalhe'),
]
