from decimal import Decimal

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
        Busca, para a sessão atual, um Pedido com status ABERTO.
        Se não existir nenhum, cria um novo — esse será o "carrinho" do visitante.
        """
        session_key = self.session.session_key

        pedido = Pedido.objects.filter(
            sessao_chave=session_key,
            status=Pedido.Status.ABERTO,
        ).first()

        if pedido is None:
            pedido = Pedido.objects.create(
                sessao_chave=session_key,
                status=Pedido.Status.ABERTO,
            )

        return pedido

    def adicionar(self, produto: Produto, quantidade: int = 1):
        """
        Adiciona um produto ao carrinho (ou aumenta a quantidade, se ele já
        estiver lá). `preco_unitario` é copiado do produto no momento da adição.
        """
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
        """Define diretamente a quantidade de um item (usado na página do carrinho)."""
        try:
            item = self.pedido.itens.get(produto_id=produto_id)
        except ItemPedido.DoesNotExist:
            return None

        if quantidade <= 0:
            item.delete()
            return None

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
