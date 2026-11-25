from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User

from .models import Cupom, Produto, Vendedor
from .validators import (
    normalizar_codigo_cupom,
    validar_codigo_cupom_unico,
    validar_validade_cupom,
)


def _adicionar_classe_bootstrap(form):
    for campo in form.fields.values():
        css_atual = campo.widget.attrs.get('class', '')
        campo.widget.attrs['class'] = f'{css_atual} form-control'.strip()
    return form


class AdicionarAoCarrinhoForm(forms.Form):
    quantidade = forms.IntegerField(
        min_value=1,
        initial=1,
        widget=forms.NumberInput(
            attrs={'class': 'form-control', 'style': 'width: 80px'}
            ),
    )

    def __init__(self, *args, **kwargs):
        self.estoque_maximo = kwargs.pop('estoque_maximo', None)
        super().__init__(*args, **kwargs)
        
    def clean_quantidade(self):
        quantidade = self.cleaned_data.get('quantidade')
        if (
            self.estoque_maximo is not None
            and quantidade
            and quantidade > self.estoque_maximo):
            raise forms.ValidationError(
            f'Estoque insuficiente. Disponível: {self.estoque_maximo}.'
            )
        return quantidade


class AplicarCupomForm(forms.Form):
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


class RegistroForm(UserCreationForm):
    TIPO_CLIENTE = 'cliente'
    TIPO_VENDEDOR = 'vendedor'
    TIPO_CHOICES = [
        (TIPO_CLIENTE, 'Cliente (quero comprar)'),
        (TIPO_VENDEDOR, 'Vendedor (quero vender produtos)'),
    ]

    tipo = forms.ChoiceField(
        choices=TIPO_CHOICES,
        initial=TIPO_CLIENTE,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Tipo de conta',
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _adicionar_classe_bootstrap(self)
        self.fields['username'].widget.attrs['placeholder'] = 'Escolha um nome de usuário'
        self.fields['username'].label = 'Nome de usuário'
        self.order_fields(['username', 'tipo', 'password1', 'password2'])

    def save(self, commit=True):
        usuario = super().save(commit=commit)

        if commit and self.cleaned_data['tipo'] == self.TIPO_VENDEDOR:
            Vendedor.objects.create(usuario=usuario, nome=usuario.username)

        return usuario


class LoginForm(AuthenticationForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _adicionar_classe_bootstrap(self)


class ProdutoForm(forms.ModelForm):

    class Meta:
        model = Produto
        fields = ['nome', 'descricao', 'preco', 'estoque', 'imagem', 'ativo']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'descricao': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'preco': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'estoque': forms.NumberInput(attrs={'class': 'form-control'}),
            'imagem': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'ativo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class CupomCadastroForm(forms.ModelForm):
    class Meta:
        model = Cupom
        fields = ['codigo', 'desconto_percentual', 'validade', 'ativo']
        widgets = {
            'codigo': forms.TextInput(
                attrs={'class': 'form-control', 'placeholder': 'Ex: BEMVINDO10'}
            ),
            'desconto_percentual': forms.NumberInput(
                attrs={'class': 'form-control', 'step': '0.01'}
            ),
            'validade': forms.DateInput(
                attrs={'class': 'form-control', 'type': 'date'}
            ),
            'ativo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, vendedor, **kwargs):
        super().__init__(*args, **kwargs)
        self.vendedor = vendedor
    def clean_codigo(self):
        codigo = normalizar_codigo_cupom(self.cleaned_data['codigo'])
        validar_codigo_cupom_unico(self.vendedor, codigo, self.instance)
        return codigo

    def clean_validade(self):
        validade = self.cleaned_data.get('validade')
        validar_validade_cupom(validade, self.instance)
        return validade
