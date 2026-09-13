"""
loja/urls.py
------------
Rotas específicas do app "loja". `app_name` cria um "namespace" (loja:...),
o que evita conflito de nomes de URL caso você crie outros apps no futuro
e queira usar, por exemplo, o mesmo nome 'lista' em cada um deles.
"""

from django.urls import path

from . import views

app_name = 'loja'

urlpatterns = [
    path('', views.lista_produtos, name='lista_produtos'),
    path('carrinho/', views.ver_carrinho, name='ver_carrinho'),
    path('carrinho/adicionar/<int:produto_id>/', views.adicionar_ao_carrinho, name='adicionar_ao_carrinho'),
    path('carrinho/remover/<int:produto_id>/', views.remover_do_carrinho, name='remover_do_carrinho'),
    path('finalizar/', views.finalizar_pedido, name='finalizar_pedido'),
    path('pedido/<int:pedido_id>/confirmado/', views.pedido_confirmado, name='pedido_confirmado'),
]
