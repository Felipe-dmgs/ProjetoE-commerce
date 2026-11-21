"""
forms.py
--------
Formulários usados nas telas do carrinho/checkout, autenticação e área do
vendedor (cadastro de produto/cupom).

Usar um Form/ModelForm do Django nos dá, de graça: validação dos dados,
hashing de senha (no caso do cadastro) e proteção básica contra entradas
inválidas.
"""

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User
from django.utils import timezone

from .models import Cupom, Produto, Vendedor


def _adicionar_classe_bootstrap(form):
    """
    Função auxiliar: percorre todos os campos de um form e adiciona a classe
    'form-control' do Bootstrap a cada widget. Evita ter que repetir
    `widget=forms.TextInput(attrs={'class': 'form-control'})` em cada campo
    dos forms que herdam do Django (como UserCreationForm/AuthenticationForm,
    que já vêm prontos, mas sem estilo).
    """
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
    """
    Formulário para o CLIENTE digitar um código de cupom na página do carrinho.
    (Não confundir com `CupomCadastroForm`, que é usada pelo VENDEDOR para
    criar um cupom novo.)
    """

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


# ============================================================================
# AUTENTICAÇÃO (cadastro / login)
# ============================================================================
class RegistroForm(UserCreationForm):
    """
    Formulário de cadastro. Herda de UserCreationForm (pronto do Django), que
    já cuida de: validar que as duas senhas digitadas são iguais, aplicar as
    regras de senha (AUTH_PASSWORD_VALIDATORS no settings.py) e salvar a
    senha com hash (nunca em texto puro).

    Acrescentamos só o campo `tipo`, que é o "dropdown" pedido: a pessoa
    escolhe se está se cadastrando como Cliente ou como Vendedor.
    """

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
        # "Só com nome e senha básica": usamos o próprio username como
        # identificação. Não pedimos e-mail para manter o cadastro simples.
        fields = ('username',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _adicionar_classe_bootstrap(self)
        self.fields['username'].widget.attrs['placeholder'] = 'Escolha um nome de usuário'
        self.fields['username'].label = 'Nome de usuário'
        # Por padrão, o Django colocaria "tipo" depois de password1/password2
        # (é um detalhe de como a herança de formulários funciona). Reordenamos
        # aqui só para a tela ficar mais natural: username -> tipo -> senhas.
        self.order_fields(['username', 'tipo', 'password1', 'password2'])

    def save(self, commit=True):
        """
        Além de criar o User (isso o UserCreationForm já faz sozinho), se o
        tipo escolhido for "vendedor", criamos também um registro de Vendedor
        ligado a esse usuário — é esse vínculo que dá acesso às páginas de
        cadastrar produto/cupom (ver loja/decorators.py).
        """
        usuario = super().save(commit=commit)

        if commit and self.cleaned_data['tipo'] == self.TIPO_VENDEDOR:
            Vendedor.objects.create(usuario=usuario, nome=usuario.username)

        return usuario


class LoginForm(AuthenticationForm):
    """
    Mesma tela de login pronta do Django (AuthenticationForm), só com as
    classes do Bootstrap aplicadas para ficar visualmente igual ao resto do
    site.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _adicionar_classe_bootstrap(self)


# ============================================================================
# ÁREA DO VENDEDOR
# ============================================================================
class ProdutoForm(forms.ModelForm):
    """
    Formulário de cadastro de Produto, usado na página exclusiva do vendedor.
    Repare que NÃO incluímos o campo `vendedor` aqui: ele é preenchido
    automaticamente pela view com o vendedor logado (ver views.cadastrar_produto),
    por segurança — não queremos que um vendedor consiga cadastrar um produto
    "em nome" de outro vendedor manipulando o formulário.
    """

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
    """
    Formulário de cadastro e edição de Cupom, usado na área do vendedor.

    O campo `vendedor` NÃO está no formulário: a view o preenche com o vendedor
    logado, para ninguém criar cupom "em nome de" outro vendedor. Por isso o
    Django não valida sozinho a unicidade de (vendedor, codigo), e fazemos essa
    checagem em `clean_codigo` para devolver um erro amigável em vez de deixar
    estourar um IntegrityError no banco.
    """

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
        # `vendedor` é obrigatório (keyword-only): sem ele não dá para checar
        # a unicidade do código por vendedor.
        super().__init__(*args, **kwargs)
        self.vendedor = vendedor

    def clean_codigo(self):
        # Guardamos sempre em maiúsculas: o código "promo10" e o "PROMO10"
        # passam a ser o mesmo cupom, e a restrição única do banco (que
        # diferencia maiúsculas de minúsculas) deixa de ter brecha.
        codigo = self.cleaned_data['codigo'].strip().upper()

        existentes = Cupom.objects.filter(vendedor=self.vendedor, codigo__iexact=codigo)
        if self.instance.pk:
            # Ao EDITAR, o próprio cupom não conta como duplicado.
            existentes = existentes.exclude(pk=self.instance.pk)
        if existentes.exists():
            raise forms.ValidationError('Você já possui um cupom com este código.')
        return codigo

    def clean_desconto_percentual(self):
        desconto = self.cleaned_data.get('desconto_percentual')
        if desconto and (desconto <= 0 or desconto > 100):
            raise forms.ValidationError(
                'O desconto deve ser um valor percentual entre 0.01% e 100%.'
            )
        return desconto

    def clean_validade(self):
        validade = self.cleaned_data.get('validade')
        # Ao editar, manter a validade que já estava salva é permitido mesmo
        # que ela já tenha passado (ex.: o vendedor só quer desativar um cupom
        # vencido). Só bloqueamos datas passadas NOVAS.
        validade_mudou = not self.instance.pk or validade != self.instance.validade
        if validade and validade_mudou and validade < timezone.localdate():
            raise forms.ValidationError(
                'A data de validade não pode ser no passado.'
            )
        return validade
