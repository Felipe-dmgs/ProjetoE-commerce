"""
views.py
--------
Views são funções (ou classes) que recebem uma requisição HTTP e devolvem
uma resposta HTTP (geralmente renderizando um template HTML).

Este arquivo reúne as views HTML do app, em três blocos:
    1. Vitrine e carrinho  -> `lista_produtos`, `adicionar_ao_carrinho`,
                              `ver_carrinho`, `remover_do_carrinho`,
                              `finalizar_pedido` (aqui acontece a BAIXA DE
                              ESTOQUE) e `pedido_confirmado`
    2. Autenticação e área do cliente -> `EntrarView`, `registro`,
                              `meus_pedidos` e `detalhe_pedido`
    3. Área do vendedor    -> produtos, cupons e pedidos recebidos

O healthcheck do Docker (/healthz/) fica em loja/health.py, e a API REST em
loja/api_views.py.
"""

from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from django.db.models import Prefetch, Q

from .cart import Carrinho, unir_carrinho_anonimo
from .decorators import vendedor_atual, vendedor_required
from .forms import (
    AdicionarAoCarrinhoForm,
    AplicarCupomForm,
    CupomCadastroForm,
    FinalizarPedidoForm,
    LoginForm,
    ProdutoForm,
    RegistroForm,
)
from .models import Cupom, ItemPedido, Pedido, Produto


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
        try:
            carrinho.adicionar(produto, quantidade)
        except ValueError as erro:
            # A soma do que já estava no carrinho com o novo pedido passou do
            # estoque: o carrinho não muda e avisamos o usuário.
            messages.error(request, str(erro))
        else:
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
        try:
            nova_quantidade = int(request.POST.get('quantidade', 1))
        except (TypeError, ValueError):
            nova_quantidade = 1
        try:
            produto_id = int(request.POST.get('produto_id'))
        except (TypeError, ValueError):
            # id adulterado/ausente: não há o que atualizar.
            return redirect('loja:ver_carrinho')
        try:
            carrinho.atualizar_quantidade(produto_id, nova_quantidade)
        except ValueError as erro:
            # Quantidade acima do estoque: mantém a anterior e avisa.
            messages.error(request, str(erro))
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


@login_required  # sem login o Django manda para /entrar/?next=/finalizar/ e volta aqui depois
def finalizar_pedido(request):
    """
    Tela de checkout: pede nome/e-mail do cliente e, ao confirmar,
    chama `Pedido.finalizar()`, que faz a BAIXA DE ESTOQUE e marca o
    pedido como FINALIZADO. O pedido passa a pertencer ao usuário logado.
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
            # O dono vem do login, nunca do formulário.
            pedido.cliente = request.user
            pedido.cliente_nome = form.cleaned_data['nome']
            pedido.cliente_email = form.cleaned_data['email']
            pedido.save(update_fields=['cliente', 'cliente_nome', 'cliente_email'])

            try:
                pedido.finalizar()
            except ValueError as erro:
                # Ex.: outro cliente comprou o último item enquanto este
                # ainda estava no carrinho — avisamos e voltamos ao carrinho.
                messages.error(request, str(erro))
                return redirect('loja:ver_carrinho')

            return redirect(reverse('loja:pedido_confirmado', args=[pedido.pk]))
    else:
        # Sugerimos os dados da conta para a pessoa não digitar tudo de novo.
        form = FinalizarPedidoForm(initial={
            'nome': request.user.get_full_name() or request.user.username,
            'email': request.user.email,
        })

    contexto = {
        'form': form,
        'itens': carrinho.itens(),
        'total': carrinho.total(),
    }
    return render(request, 'loja/finalizar_pedido.html', contexto)


@login_required
def pedido_confirmado(request, pedido_id):
    """Página final, mostrando o resumo do pedido já finalizado."""
    # O pedido tem que ser do usuário logado: trocar o id na URL pelo de um
    # pedido de outro cliente dá 404.
    pedido = get_object_or_404(
        Pedido,
        id=pedido_id,
        cliente=request.user,
        status=Pedido.Status.FINALIZADO,
    )
    contexto = {
        'pedido': pedido,
        'itens': pedido.itens.select_related('produto'),
        'total': pedido.calcular_total(),
    }
    return render(request, 'loja/pedido_confirmado.html', contexto)


# ============================================================================
# AUTENTICAÇÃO
# ============================================================================
class EntrarView(LoginView):
    """
    Mesma tela de login do Django, com um passo a mais: levar o carrinho que a
    pessoa montou ANTES de entrar para a conta dela.

    O carrinho anônimo está preso à session_key, e o login() troca essa chave.
    Por isso lemos a chave antiga ANTES de chamar o `form_valid` original (que
    é quem executa o login) e só depois fazemos a união dos carrinhos.
    """

    template_name = 'loja/login.html'
    authentication_form = LoginForm

    def form_valid(self, form):
        chave_antiga = self.request.session.session_key
        resposta = super().form_valid(form)  # aqui o login() acontece e a chave muda
        unir_carrinho_anonimo(chave_antiga, self.request.user)
        return resposta


def _proximo_seguro(request):
    """
    Lê o parâmetro `next` (ex.: /finalizar/) e só o devolve se for um endereço
    deste mesmo site. Sem essa checagem, um link malicioso poderia mandar a
    pessoa, logo após o cadastro, para um site de terceiros (open redirect).
    Devolve '' quando não há `next` ou ele não é seguro.
    """
    destino = request.POST.get('next') or request.GET.get('next') or ''
    if destino and url_has_allowed_host_and_scheme(
        destino,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return destino
    return ''


def registro(request):
    """
    Tela de cadastro: nome de usuário + senha + dropdown "Cliente/Vendedor".
    Se a pessoa escolher "Vendedor", o próprio RegistroForm já cria o
    registro de Vendedor ligado à conta (ver forms.RegistroForm.save()).
    """
    proximo = _proximo_seguro(request)

    # Se a pessoa já está logada, não faz sentido mostrar a tela de cadastro.
    if request.user.is_authenticated:
        return redirect('loja:lista_produtos')

    if request.method == 'POST':
        form = RegistroForm(request.POST)
        if form.is_valid():
            usuario = form.save()
            # A chave da sessão precisa ser lida ANTES do login(), que a troca:
            # é por ela que achamos o carrinho que a pessoa já tinha montado.
            chave_antiga = request.session.session_key
            # Loga a pessoa automaticamente após o cadastro, para ela já
            # cair "dentro" do site sem precisar preencher o login de novo.
            login(request, usuario)
            unir_carrinho_anonimo(chave_antiga, usuario)

            if form.cleaned_data['tipo'] == RegistroForm.TIPO_VENDEDOR:
                messages.success(
                    request,
                    f'Conta de vendedor criada! Bem-vindo(a), {usuario.username}. '
                    'Agora você já pode cadastrar produtos e cupons.',
                )
            else:
                messages.success(request, f'Conta criada! Bem-vindo(a), {usuario.username}.')

            # Volta para onde a pessoa estava indo (ex.: o checkout), se houver.
            return redirect(proximo or 'loja:lista_produtos')
    else:
        form = RegistroForm()

    return render(request, 'loja/registro.html', {'form': form, 'next': proximo})


# ============================================================================
# ÁREA DO CLIENTE: MEUS PEDIDOS
# ============================================================================
# Mesma regra de ouro da área do vendedor, agora com o CLIENTE logado como
# dono: toda consulta parte de `request.user` e o get_object_or_404 leva o
# cliente junto, então o pedido de outra pessoa dá 404. Pedidos antigos, sem
# cliente, nunca aparecem aqui (o filtro por cliente=request.user os exclui).


@login_required
def meus_pedidos(request):
    """Lista os pedidos FINALIZADOS do usuário logado, do mais recente ao mais antigo."""
    pedidos = (
        Pedido.objects
        .filter(cliente=request.user, status=Pedido.Status.FINALIZADO)
        .prefetch_related('itens')  # o total de cada linha soma os itens: evita 1 consulta por pedido
        .order_by('-finalizado_em', '-pk')
    )
    return render(request, 'loja/meus_pedidos.html', {'pedidos': pedidos})


@login_required
def detalhe_pedido(request, pk):
    """Detalhe de um pedido do usuário logado (de outro cliente ou aberto: 404)."""
    pedido = get_object_or_404(
        Pedido,
        pk=pk,
        cliente=request.user,
        status=Pedido.Status.FINALIZADO,
    )
    contexto = {
        'pedido': pedido,
        'itens': pedido.itens.select_related('produto__vendedor'),
        'subtotal': pedido.calcular_subtotal(),
        # Pedido finalizado: calcular_desconto devolve o desconto_aplicado
        # gravado na finalização, e não recalcula com os cupons de hoje.
        'desconto': pedido.calcular_desconto(),
        'total': pedido.calcular_total(),
    }
    return render(request, 'loja/pedido_detalhe.html', contexto)


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


@vendedor_required
def pedidos_recebidos(request):
    """
    Lista os pedidos FINALIZADOS que têm pelo menos um produto do vendedor
    logado. Cada linha mostra só o subtotal dos itens DELE: o pedido pode ter
    itens de outros vendedores, que ele não pode ver (nem somar).
    """
    vendedor = vendedor_atual(request)

    # Só os itens deste vendedor entram no pré-carregamento (to_attr), então
    # não existe caminho para itens de outros vendedores chegarem ao template.
    itens_do_vendedor = ItemPedido.objects.filter(
        produto__vendedor=vendedor
    ).select_related('produto')

    pedidos = list(
        Pedido.objects
        .filter(
            status=Pedido.Status.FINALIZADO,
            cliente__isnull=False,  # pedidos antigos, sem cliente, ficam de fora
            itens__produto__vendedor=vendedor,
        )
        # O join com os itens repete o pedido uma vez por item do vendedor;
        # distinct() devolve cada pedido uma vez só.
        .distinct()
        .prefetch_related(
            Prefetch('itens', queryset=itens_do_vendedor, to_attr='itens_do_vendedor')
        )
        .order_by('-finalizado_em', '-pk')
    )

    for pedido in pedidos:
        pedido.subtotal_vendedor = sum(
            (item.subtotal() for item in pedido.itens_do_vendedor), Decimal('0.00')
        )

    return render(request, 'loja/pedidos_recebidos.html', {'pedidos': pedidos})


@vendedor_required
def detalhe_pedido_recebido(request, pk):
    """
    Detalhe de um pedido recebido: mostra SÓ os itens do vendedor logado, o
    subtotal deles e os dados de contato do cliente. Pedido sem nenhum produto
    do vendedor dá 404, como se não existisse.
    """
    vendedor = vendedor_atual(request)

    # O queryset já nasce restrito aos pedidos que têm produto do vendedor;
    # distinct() evita que o join devolva o mesmo pedido várias vezes (e o
    # .get() do get_object_or_404 estourar com MultipleObjectsReturned).
    pedidos_do_vendedor = Pedido.objects.filter(
        itens__produto__vendedor=vendedor
    ).distinct()
    pedido = get_object_or_404(
        pedidos_do_vendedor,
        pk=pk,
        status=Pedido.Status.FINALIZADO,
        cliente__isnull=False,
    )

    itens = list(
        ItemPedido.objects
        .filter(pedido=pedido, produto__vendedor=vendedor)
        .select_related('produto')
    )
    subtotal = sum((item.subtotal() for item in itens), Decimal('0.00'))

    contexto = {
        'pedido': pedido,
        'itens': itens,
        'subtotal': subtotal,
    }
    return render(request, 'loja/pedido_recebido_detalhe.html', contexto)
