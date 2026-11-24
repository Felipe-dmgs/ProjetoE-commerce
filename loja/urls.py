"""
loja/urls.py
------------
Rotas específicas do app "loja". `app_name` cria um "namespace" (loja:...),
o que evita conflito de nomes de URL caso você crie outros apps no futuro
e queira usar, por exemplo, o mesmo nome 'lista' em cada um deles.
"""

from django.contrib.auth import views as auth_views
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
    path('cadastro/', views.registro, name='registro'),
    path('pedidos/', views.meus_pedidos, name='meus_pedidos'),
    path('pedidos/<int:pk>/', views.detalhe_pedido, name='detalhe_pedido'),
    # EntrarView = LoginView do Django + união do carrinho anônimo com o do usuário
    path('entrar/', views.EntrarView.as_view(), name='login'),
    path('sair/', auth_views.LogoutView.as_view(next_page='loja:lista_produtos'), name='logout'),
    path('vendedor/produtos/', views.meus_produtos, name='meus_produtos'),
    path('vendedor/produtos/novo/', views.cadastrar_produto, name='cadastrar_produto'),
    path('vendedor/produtos/<int:pk>/editar/', views.editar_produto, name='editar_produto'),
    path('vendedor/cupons/', views.meus_cupons, name='meus_cupons'),
    path('vendedor/cupons/novo/', views.cadastrar_cupom, name='cadastrar_cupom'),
    path('vendedor/cupons/<int:pk>/editar/', views.editar_cupom, name='editar_cupom'),
    path('vendedor/pedidos/', views.pedidos_recebidos, name='pedidos_recebidos'),
    path('vendedor/pedidos/<int:pk>/', views.detalhe_pedido_recebido, name='detalhe_pedido_recebido'),
]