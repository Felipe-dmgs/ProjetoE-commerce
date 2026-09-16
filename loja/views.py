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

from .cart import Carrinho
from .decorators import vendedor_required
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
    except Exception as erro:  # pragma: no cover - só usado para diagnóstico
        return JsonResponse({'status': 'erro', 'detalhe': str(erro)}, status=500)


def lista_produtos(request):
    """Vitrine: mostra todos os produtos ativos e com estoque disponível."""
    produtos = Produto.objects.filter(ativo=True).select_related('vendedor')
    form_quantidade = AdicionarAoCarrinhoForm()

    contexto = {
        'produtos': produtos,
        'form_quantidade': form_quantidade,
    }
    return render(request, 'loja/produto_list.html', contexto)


@require_POST  # só aceita requisições POST — adicionar ao carrinho não deveria ser um GET
def adicionar_ao_carrinho(request, produto_id):
    """Recebe o formulário da vitrine e adiciona X unidades de um produto ao carrinho."""
    produto = get_object_or_404(Produto, id=produto_id, ativo=True)
    form = AdicionarAoCarrinhoForm(request.POST)

    if form.is_valid():
        quantidade = form.cleaned_data['quantidade']

        # Checagem simples de estoque só para dar um feedback melhor ao usuário;
        # a checagem "de verdade" (que garante consistência) acontece de novo
        # em Pedido.finalizar(), no momento de fechar a compra.
        if not produto.tem_estoque(quantidade):
            messages.error(
                request,
                f'Não há estoque suficiente de "{produto.nome}". '
                f'Disponível: {produto.estoque}.',
            )
            return redirect('loja:lista_produtos')

        carrinho = Carrinho(request)
        carrinho.adicionar(produto, quantidade)
        messages.success(request, f'"{produto.nome}" adicionado ao carrinho.')
    else:
        messages.error(request, 'Quantidade inválida.')

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
            cupom = Cupom.objects.filter(codigo__iexact=codigo).first()
            if cupom and cupom.esta_valido():
                carrinho.pedido.cupom = cupom
                carrinho.pedido.save(update_fields=['cupom'])
                messages.success(request, f'Cupom "{cupom.codigo}" aplicado!')
            else:
                messages.error(request, 'Cupom inválido ou expirado.')
        return redirect('loja:ver_carrinho')

    contexto = {
        'itens': carrinho.itens(),
        'subtotal': carrinho.subtotal(),
        'desconto': carrinho.pedido.calcular_desconto(),
        'total': carrinho.total(),
        'cupom_aplicado': carrinho.pedido.cupom,
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
                # Aqui acontece a mágica: valida estoque + dá baixa + muda status.
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
@vendedor_required
def cadastrar_produto(request):
    """
    Página exclusiva de vendedores logados para cadastrar um novo Produto.
    O `@vendedor_required` (loja/decorators.py) garante duas coisas antes de
    deixar chegar até aqui: a pessoa está logada E tem um perfil de Vendedor.
    """
    if request.method == 'POST':
        form = ProdutoForm(request.POST, request.FILES)  # request.FILES: necessário para o upload de imagem
        if form.is_valid():
            produto = form.save(commit=False)  # commit=False: ainda não salva no banco
            produto.vendedor = request.user.perfil_vendedor  # associa ao vendedor logado
            produto.save()
            messages.success(request, f'Produto "{produto.nome}" cadastrado com sucesso!')
            return redirect('loja:lista_produtos')
    else:
        form = ProdutoForm()

    return render(request, 'loja/produto_form.html', {'form': form})


@vendedor_required
def cadastrar_cupom(request):
    """Página exclusiva de vendedores logados para cadastrar um novo Cupom."""
    if request.method == 'POST':
        form = CupomCadastroForm(request.POST)
        if form.is_valid():
            cupom = form.save()
            messages.success(request, f'Cupom "{cupom.codigo}" cadastrado com sucesso!')
            return redirect('loja:lista_produtos')
    else:
        form = CupomCadastroForm()

    return render(request, 'loja/cupom_form.html', {'form': form})