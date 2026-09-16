"""
forms.py
--------
Formulários usados nas telas do carrinho/checkout.
Usar um Form do Django nos dá, de graça: validação dos dados e proteção
básica contra entradas inválidas.
"""

from django import forms


class AdicionarAoCarrinhoForm(forms.Form):
    """Formulário simples usado no botão 'Adicionar ao carrinho' da lista de produtos."""

    quantidade = forms.IntegerField(
        min_value=1,
        initial=1,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'style': 'width: 80px'}),
    )


class CupomForm(forms.Form):
    """Formulário para o cliente digitar um código de cupom na página do carrinho."""

    codigo = forms.CharField(
        max_length=30,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Código do cupom (opcional)',
        }),
    )


class FinalizarPedidoForm(forms.Form):
    """Dados do cliente coletados na hora de fechar o pedido."""

    nome = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Seu nome'}),
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'seu@email.com'}),
    )
