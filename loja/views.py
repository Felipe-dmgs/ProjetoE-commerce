"""
views.py
--------
Views são funções (ou classes) que recebem uma requisição HTTP e devolvem
uma resposta HTTP (geralmente renderizando um template HTML).

Fluxo desta primeira entrega:
    1. `lista_produtos`      -> vitrine de produtos, com botão "adicionar ao carrinho"
    2. `adicionar_ao_carrinho` -> processa o formulário e adiciona o item
    3. `ver_carrinho`        -> mostra os itens, permite alterar quantidade,
                                aplicar cupom e mostra o TOTAL calculado
    4. `remover_do_carrinho` -> remove um item do carrinho
    5. `finalizar_pedido`    -> tela com dados do cliente + confirma o pedido
                                (aqui acontece a BAIXA DE ESTOQUE)
    6. `pedido_confirmado`   -> página de sucesso, mostrando o resumo do pedido
"""

from django.contrib import messages
from django.contrib.auth import login
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.db.models import Q
from .cart import Carrinho
from .decorators import vendedor_atual, vendedor_required
from .forms import (
    AdicionarAoCarrinhoForm,
    AplicarCupomForm,
    CupomCadastroForm,
    FinalizarPedidoForm,
    ProdutoForm,
    RegistroForm,
)
from .models import Cupom, Pedido, Produto

def healthcheck(request):
    """
    Endpoint simples usado pelo HEALTHCHECK do Docker (veja o docker-compose.yml).
    Faz uma consulta bem leve ao banco (SELECT 1) para garantir que a conexão
    com o Postgres está funcionando de verdade, não só que o Django "está de pé".
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1;')
        return JsonResponse({'status': 'ok'})
    except Exception as erro:
        return JsonResponse({'status': 'erro', 'detalhe': str(erro)}, status=500)


from django.db.models import Q
from django.shortcuts import render
from .forms import AdicionarAoCarrinhoForm
from .models import Produto


def lista_produtos(request):
    """Vitrine: mostra os produtos ativos e permite filtrar por nome OU vendedor usando Q."""
    produtos = Produto.objects.filter(ativo=True).select_related('vendedor')
    termo_nome = request.GET.get('nome', '').strip()
    termo_vendedor = request.GET.get('vendedor', '').strip()
    filtros_pesquisa = Q()
    if termo_nome:
        filtros_pesquisa |= Q(nome__icontains=termo_nome)
    if termo_vendedor:
        filtros_pesquisa |= Q(vendedor__nome__icontains=termo_vendedor)
    if termo_nome or termo_vendedor:
        produtos = produtos.filter(filtros_pesquisa)

    form_quantidade = AdicionarAoCarrinhoForm()

    contexto = {
        'produtos': produtos,
        'form_quantidade': form_quantidade,
        'v_nome': termo_nome,
        'v_vendedor': termo_vendedor,
    }
    return render(request, 'loja/produto_list.html', contexto)




@require_POST
def adicionar_ao_carrinho(request, produto_id):
    produto = get_object_or_404(Produto, id=produto_id, ativo=True)
    form = AdicionarAoCarrinhoForm(
        request.POST, estoque_maximo=produto.estoque
        )
    if form.is_valid():
        quantidade = form.cleaned_data['quantidade']
        carrinho = Carrinho(request)
        carrinho.adicionar(produto, quantidade)
        messages.success(request, f'"{produto.nome}" adicionado ao carrinho.')
    else:
        for erro in form.errors.values():
            messages.error(request, erro.as_text())

    return redirect('loja:lista_produtos')


def ver_carrinho(request):
    """
    Página do carrinho: lista os itens, permite atualizar quantidades,
    aplicar um cupom de desconto e mostra subtotal/desconto/TOTAL.
    """
    carrinho = Carrinho(request)

    # --- Atualização de quantidade (POST vindo dos inputs de quantidade) ---
    if request.method == 'POST' and 'atualizar' in request.POST:
        produto_id = request.POST.get('produto_id')
        try:
            nova_quantidade = int(request.POST.get('quantidade', 1))
        except (TypeError, ValueError):
            nova_quantidade = 1
        carrinho.atualizar_quantidade(produto_id, nova_quantidade)
        return redirect('loja:ver_carrinho')

    # --- Aplicação de cupom ---
    form_cupom = AplicarCupomForm(request.POST or None)
    if request.method == 'POST' and 'aplicar_cupom' in request.POST and form_cupom.is_valid():
        codigo = form_cupom.cleaned_data['codigo'].strip()
        if codigo:
            # Todo cupom pertence a UM vendedor. Só consideramos cupons dos
            # vendedores que têm algum produto neste carrinho. Se vários deles
            # tiverem o MESMO código, todos são aplicados: cada um desconta os
            # itens do seu vendedor.
            vendedores_do_carrinho = set(
                carrinho.itens().values_list('produto__vendedor_id', flat=True)
            )
            candidatos = Cupom.objects.filter(
                codigo__iexact=codigo,
                vendedor_id__in=vendedores_do_carrinho,
            ).select_related('vendedor').order_by('pk')

            # No máximo um cupom por vendedor (o mais antigo e válido).
            novos = {}
            for cupom in candidatos:
                if cupom.esta_valido():
                    novos.setdefault(cupom.vendedor_id, cupom)

            if novos:
                pedido = carrinho.pedido
                # O cupom novo SUBSTITUI o que o mesmo vendedor já tinha no
                # pedido; os cupons de outros vendedores continuam.
                mantidos = [c for c in pedido.cupons.all() if c.vendedor_id not in novos]
                pedido.cupons.set(mantidos + list(novos.values()))

                vendedores = ', '.join(c.vendedor.nome for c in novos.values())
                messages.success(
                    request,
                    f'Cupom "{codigo.upper()}" aplicado nos produtos de: {vendedores}.',
                )
            else:
                messages.error(
                    request,
                    'Cupom inválido, expirado ou não se aplica aos produtos do seu carrinho.',
                )
        return redirect('loja:ver_carrinho')

    contexto = {
        'itens': carrinho.itens(),
        'subtotal': carrinho.subtotal(),
        'desconto': carrinho.pedido.calcular_desconto(),
        'total': carrinho.total(),
        'cupons_aplicados': carrinho.pedido.detalhar_descontos(),
        'form_cupom': form_cupom,
    }
    return render(request, 'loja/carrinho.html', contexto)


@require_POST
def remover_do_carrinho(request, produto_id):
    """Remove um produto do carrinho."""
    carrinho = Carrinho(request)
    carrinho.remover(produto_id)
    messages.info(request, 'Item removido do carrinho.')
    return redirect('loja:ver_carrinho')


def finalizar_pedido(request):
    """
    Tela de checkout: pede nome/e-mail do cliente e, ao confirmar,
    chama `Pedido.finalizar()`, que faz a BAIXA DE ESTOQUE e marca o
    pedido como FINALIZADO.
    """
    carrinho = Carrinho(request)

    # Não faz sentido finalizar um carrinho vazio.
    if not carrinho.itens().exists():
        messages.warning(request, 'Seu carrinho está vazio.')
        return redirect('loja:lista_produtos')

    if request.method == 'POST':
        form = FinalizarPedidoForm(request.POST)
        if form.is_valid():
            pedido = carrinho.pedido
            pedido.cliente_nome = form.cleaned_data['nome']
            pedido.cliente_email = form.cleaned_data['email']
            pedido.save(update_fields=['cliente_nome', 'cliente_email'])

            try:
                pedido.finalizar()
            except ValueError as erro:
                # Ex.: outro cliente comprou o último item enquanto este
                # ainda estava no carrinho — avisamos e voltamos ao carrinho.
                messages.error(request, str(erro))
                return redirect('loja:ver_carrinho')

            return redirect(reverse('loja:pedido_confirmado', args=[pedido.pk]))
    else:
        form = FinalizarPedidoForm()

    contexto = {
        'form': form,
        'itens': carrinho.itens(),
        'total': carrinho.total(),
    }
    return render(request, 'loja/finalizar_pedido.html', contexto)


def pedido_confirmado(request, pedido_id):
    """Página final, mostrando o resumo do pedido já finalizado."""
    pedido = get_object_or_404(Pedido, id=pedido_id, status=Pedido.Status.FINALIZADO)
    contexto = {
        'pedido': pedido,
        'itens': pedido.itens.select_related('produto'),
        'total': pedido.calcular_total(),
    }
    return render(request, 'loja/pedido_confirmado.html', contexto)


# ============================================================================
# AUTENTICAÇÃO
# ============================================================================
def registro(request):
    """
    Tela de cadastro: nome de usuário + senha + dropdown "Cliente/Vendedor".
    Se a pessoa escolher "Vendedor", o próprio RegistroForm já cria o
    registro de Vendedor ligado à conta (ver forms.RegistroForm.save()).
    """
    # Se a pessoa já está logada, não faz sentido mostrar a tela de cadastro.
    if request.user.is_authenticated:
        return redirect('loja:lista_produtos')

    if request.method == 'POST':
        form = RegistroForm(request.POST)
        if form.is_valid():
            usuario = form.save()
            # Loga a pessoa automaticamente após o cadastro, para ela já
            # cair "dentro" do site sem precisar preencher o login de novo.
            login(request, usuario)

            if form.cleaned_data['tipo'] == RegistroForm.TIPO_VENDEDOR:
                messages.success(
                    request,
                    f'Conta de vendedor criada! Bem-vindo(a), {usuario.username}. '
                    'Agora você já pode cadastrar produtos e cupons.',
                )
            else:
                messages.success(request, f'Conta criada! Bem-vindo(a), {usuario.username}.')

            return redirect('loja:lista_produtos')
    else:
        form = RegistroForm()

    return render(request, 'loja/registro.html', {'form': form})


# ============================================================================
# ÁREA DO VENDEDOR
# ============================================================================
# Regra de ouro desta área: TODA consulta parte do vendedor logado
# (`vendedor_atual`) e TODO get_object_or_404 leva o vendedor junto. Assim,
# trocar o id na URL pelo de um registro de OUTRO vendedor dá 404, como se ele
# não existisse, em vez de mostrar ou deixar editar dados alheios.
#
# Os decorators garantem a ordem: `@vendedor_required` exige login E perfil de
# vendedor antes de a view rodar.


@vendedor_required
def meus_produtos(request):
    """Lista TODOS os produtos do vendedor logado (inclusive os inativos)."""
    produtos = Produto.objects.filter(vendedor=vendedor_atual(request))
    return render(request, 'loja/meus_produtos.html', {'produtos': produtos})


@vendedor_required
def cadastrar_produto(request):
    """Cadastra um novo Produto em nome do vendedor logado."""
    if request.method == 'POST':
        form = ProdutoForm(request.POST, request.FILES)  # request.FILES: necessário para o upload de imagem
        if form.is_valid():
            produto = form.save(commit=False)  # commit=False: ainda não salva no banco
            produto.vendedor = vendedor_atual(request)  # o dono vem do login, nunca do formulário
            produto.save()
            messages.success(request, f'Produto "{produto.nome}" cadastrado com sucesso!')
            return redirect('loja:meus_produtos')
    else:
        form = ProdutoForm()

    contexto = {
        'form': form,
        'titulo_pagina': 'Cadastrar produto',
        'texto_botao': 'Cadastrar produto',
        'editando': False,
    }
    return render(request, 'loja/produto_form.html', contexto)


@vendedor_required
def editar_produto(request, pk):
    """Edita um produto, desde que ele seja do vendedor logado (senão, 404)."""
    produto = get_object_or_404(Produto, pk=pk, vendedor=vendedor_atual(request))

    if request.method == 'POST':
        form = ProdutoForm(request.POST, request.FILES, instance=produto)
        if form.is_valid():
            form.save()
            messages.success(request, f'Produto "{produto.nome}" atualizado!')
            return redirect('loja:meus_produtos')
    else:
        form = ProdutoForm(instance=produto)

    contexto = {
        'form': form,
        'titulo_pagina': 'Editar produto',
        'texto_botao': 'Salvar alterações',
        'editando': True,
    }
    return render(request, 'loja/produto_form.html', contexto)


@vendedor_required
def meus_cupons(request):
    """Lista os cupons que o vendedor logado criou (e só os dele)."""
    cupons = Cupom.objects.filter(vendedor=vendedor_atual(request))
    return render(request, 'loja/meus_cupons.html', {'cupons': cupons})


@vendedor_required
def cadastrar_cupom(request):
    """Cadastra um novo Cupom, que passa a pertencer ao vendedor logado."""
    vendedor = vendedor_atual(request)

    if request.method == 'POST':
        form = CupomCadastroForm(request.POST, vendedor=vendedor)
        if form.is_valid():
            cupom = form.save(commit=False)
            cupom.vendedor = vendedor  # o dono vem do login, nunca do formulário
            cupom.save()
            messages.success(request, f'Cupom "{cupom.codigo}" cadastrado com sucesso!')
            return redirect('loja:meus_cupons')
    else:
        form = CupomCadastroForm(vendedor=vendedor)

    contexto = {
        'form': form,
        'titulo_pagina': 'Cadastrar cupom de desconto',
        'texto_botao': 'Cadastrar cupom',
    }
    return render(request, 'loja/cupom_form.html', contexto)


@vendedor_required
def editar_cupom(request, pk):
    """Edita um cupom, desde que ele seja do vendedor logado (senão, 404)."""
    vendedor = vendedor_atual(request)
    cupom = get_object_or_404(Cupom, pk=pk, vendedor=vendedor)

    if request.method == 'POST':
        form = CupomCadastroForm(request.POST, instance=cupom, vendedor=vendedor)
        if form.is_valid():
            form.save()
            messages.success(request, f'Cupom "{cupom.codigo}" atualizado!')
            return redirect('loja:meus_cupons')
    else:
        form = CupomCadastroForm(instance=cupom, vendedor=vendedor)

    contexto = {
        'form': form,
        'titulo_pagina': 'Editar cupom',
        'texto_botao': 'Salvar alterações',
    }
    return render(request, 'loja/cupom_form.html', contexto)
