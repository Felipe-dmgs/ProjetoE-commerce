from decimal import Decimal

from django.db import transaction

from .models import Pedido, ItemPedido, Produto


class Carrinho:
    """Encapsula as operações do carrinho: adicionar, remover, listar itens, total."""

    def __init__(self, request):
        # Guardamos a request para poder acessar/gravar dados na sessão.
        self.request = request
        self.session = request.session

        # Garante que exista uma sessão criada (para termos uma session_key única).
        if not self.session.session_key:
            self.session.create()

        self.pedido = self._obter_ou_criar_pedido_aberto()

    def _obter_ou_criar_pedido_aberto(self):
        """
        Busca o carrinho (Pedido ABERTO) de quem está navegando:
          - usuário LOGADO: o carrinho é dele (cliente=usuário), em qualquer
            sessão/navegador. A session_key não serve de identidade aqui,
            porque o Django a troca ao autenticar e ao sair.
          - visitante ANÔNIMO: o carrinho é o da sessão atual, e só vale um
            pedido sem dono (cliente nulo), para nunca "puxar" o carrinho de
            alguém que já tem conta.
        Se não existir nenhum, cria um novo.
        """
        session_key = self.session.session_key
        usuario = self.request.user

        if usuario.is_authenticated:
            filtro = {'cliente': usuario}
        else:
            filtro = {'sessao_chave': session_key, 'cliente__isnull': True}

        pedido = Pedido.objects.filter(
            status=Pedido.Status.ABERTO,
            **filtro,
        ).order_by('-criado_em').first()

        if pedido is None:
            pedido = Pedido.objects.create(
                sessao_chave=session_key,
                status=Pedido.Status.ABERTO,
                cliente=usuario if usuario.is_authenticated else None,
            )

        return pedido

    def _quantidade_no_carrinho(self, produto: Produto) -> int:
        """Quantas unidades deste produto já estão no carrinho (0 se nenhuma)."""
        item = self.pedido.itens.filter(produto=produto).first()
        return item.quantidade if item else 0

    def adicionar(self, produto: Produto, quantidade: int = 1):
        """
        Adiciona um produto ao carrinho (ou aumenta a quantidade, se ele já
        estiver lá). `preco_unitario` é copiado do produto no momento da adição.

        Levanta ValueError se a quantidade ACUMULADA (a que já estava no
        carrinho + a nova) passar do estoque. Validar só a quantidade da
        requisição não basta: clicar em "adicionar" várias vezes furaria o limite.
        """
        ja_no_carrinho = self._quantidade_no_carrinho(produto)
        if ja_no_carrinho + quantidade > produto.estoque:
            raise ValueError(
                f'Estoque insuficiente para "{produto.nome}". '
                f'Disponível: {produto.estoque}, já no carrinho: {ja_no_carrinho}.'
            )

        item, criado = ItemPedido.objects.get_or_create(
            pedido=self.pedido,
            produto=produto,
            defaults={
                'quantidade': quantidade,
                'preco_unitario': produto.preco,
            },
        )

        if not criado:
            # O item já existia no carrinho: apenas somamos a nova quantidade.
            item.quantidade += quantidade
            # Atualizamos o preço também, caso o produto tenha mudado de preço.
            item.preco_unitario = produto.preco
            item.save(update_fields=['quantidade', 'preco_unitario'])

        return item

    def atualizar_quantidade(self, produto_id: int, quantidade: int):
        """
        Define diretamente a quantidade de um item (usado na página do carrinho).
        Levanta ValueError se a nova quantidade passar do estoque do produto.
        """
        try:
            item = self.pedido.itens.select_related('produto').get(produto_id=produto_id)
        except ItemPedido.DoesNotExist:
            return None

        if quantidade <= 0:
            item.delete()
            return None

        # Aqui a quantidade é o total desejado (não uma soma), então comparamos
        # direto com o estoque.
        if quantidade > item.produto.estoque:
            raise ValueError(
                f'Estoque insuficiente para "{item.produto.nome}". '
                f'Disponível: {item.produto.estoque}, solicitado: {quantidade}.'
            )

        item.quantidade = quantidade
        item.save(update_fields=['quantidade'])
        return item

    def remover(self, produto_id: int):
        """Remove completamente um produto do carrinho."""
        self.pedido.itens.filter(produto_id=produto_id).delete()

    def limpar(self):
        """Remove todos os itens do carrinho (mas mantém o Pedido em aberto)."""
        self.pedido.itens.all().delete()

    def itens(self):
        """Retorna os itens do carrinho já otimizado (evita N+1 queries)."""
        return self.pedido.itens.select_related('produto').all()

    def quantidade_total(self):
        """Soma a quantidade de todos os itens (útil para mostrar um "badge" no menu)."""
        return sum(item.quantidade for item in self.itens())

    def subtotal(self) -> Decimal:
        return self.pedido.calcular_subtotal()

    def total(self) -> Decimal:
        return self.pedido.calcular_total()


def unir_carrinho_anonimo(chave_antiga, usuario):
    """
    Passa para `usuario` o carrinho que ele montou antes de entrar (login ou
    cadastro).

    O carrinho anônimo é um Pedido ABERTO amarrado à session_key, e o Django
    TROCA essa chave quando a pessoa se autentica. Por isso quem chama esta
    função precisa ler `request.session.session_key` ANTES de chamar login() e
    passar esse valor aqui em `chave_antiga`; depois do login a chave antiga
    já não está mais na sessão.

    Dois casos:
      - o usuário NÃO tinha carrinho aberto: o próprio pedido anônimo vira o
        dele (os cupons já aplicados vão junto, pois são do mesmo Pedido);
      - o usuário JÁ tinha um carrinho aberto: os itens do anônimo são somados
        ao dele (sem passar do estoque), os cupons dos vendedores que o
        carrinho dele ainda não tinha são trazidos, e o anônimo é descartado.
    """
    if not chave_antiga:
        return

    anonimo = Pedido.objects.filter(
        sessao_chave=chave_antiga,
        status=Pedido.Status.ABERTO,
        cliente__isnull=True,  # nunca mexe em carrinho que já pertence a alguém
    ).first()
    if anonimo is None:
        return

    # atomic: ou a união acontece inteira, ou nada muda (não queremos perder o
    # carrinho anônimo com os itens só pela metade no carrinho do usuário).
    with transaction.atomic():
        do_usuario = Pedido.objects.filter(
            cliente=usuario,
            status=Pedido.Status.ABERTO,
        ).order_by('-criado_em').first()

        if do_usuario is None:
            anonimo.cliente = usuario
            anonimo.save(update_fields=['cliente'])
            return

        # Itens do carrinho do usuário, indexados por produto, para somar.
        existentes = {
            item.produto_id: item
            for item in do_usuario.itens.select_related('produto')
        }

        for item_anonimo in anonimo.itens.select_related('produto'):
            produto = item_anonimo.produto
            item = existentes.get(produto.pk)

            if item is None:
                # Produto novo para o usuário: leva a quantidade, limitada ao
                # estoque. Sem estoque nenhum, o item simplesmente não vem.
                quantidade = min(item_anonimo.quantidade, produto.estoque)
                if quantidade > 0:
                    ItemPedido.objects.create(
                        pedido=do_usuario,
                        produto=produto,
                        quantidade=quantidade,
                        preco_unitario=produto.preco,
                    )
            else:
                # Mesmo produto nos dois carrinhos: soma, mas sem passar do
                # estoque. Se o item do usuário já estava acima do estoque
                # (o estoque caiu depois), não o reduzimos aqui: quem barra é
                # a finalização, com a mensagem de estoque insuficiente.
                somada = min(item.quantidade + item_anonimo.quantidade, produto.estoque)
                item.quantidade = max(item.quantidade, somada)
                item.preco_unitario = produto.preco
                item.save(update_fields=['quantidade', 'preco_unitario'])

        # Cupons: no máximo um por vendedor. Se os dois carrinhos tinham cupom
        # do mesmo vendedor, vale o que o usuário já tinha; os de vendedores
        # que ele ainda não tinha são trazidos.
        vendedores_com_cupom = {c.vendedor_id for c in do_usuario.cupons.all()}
        for cupom in anonimo.cupons.all():
            if cupom.vendedor_id not in vendedores_com_cupom:
                do_usuario.cupons.add(cupom)
                vendedores_com_cupom.add(cupom.vendedor_id)

        # Descarta o carrinho anônimo (os itens saem junto, por CASCADE).
        anonimo.delete()
