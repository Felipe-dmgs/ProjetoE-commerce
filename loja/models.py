"""
models.py
---------
Aqui definimos as "entidades" do projeto (Produto, Vendedor, Pedido, Item, Cupom).
Cada classe abaixo vira uma TABELA no banco de dados, e cada atributo vira
uma COLUNA dessa tabela. O Django cuida de traduzir isso em SQL para nós.

Entidades pedidas no enunciado:
    - Produto
    - Vendedor
    - Pedido
    - Item (aqui chamado de ItemPedido, para deixar claro que é um item DE um pedido)
    - Cupom
"""

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone


# ============================================================================
# VENDEDOR
# ============================================================================
class Vendedor(models.Model):
    """
    Representa quem está vendendo o produto (uma loja/pessoa/empresa).

    O campo `usuario` liga este Vendedor a uma conta de login (o model padrão
    de usuário do Django, `auth.User`). É esse vínculo que permite ao sistema
    saber, quando alguém está logado, se essa pessoa "é vendedor" ou não —
    veja `loja/decorators.py` (`vendedor_required`) e o cadastro em
    `loja/forms.py` (`RegistroForm`).

    `null=True, blank=True` porque, tecnicamente, ainda é possível cadastrar
    um Vendedor "solto" (sem login) direto pelo admin, como antes.
    """

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='perfil_vendedor',
        null=True,
        blank=True,
    )

    nome = models.CharField(max_length=150)
    # Passou a ser opcional: no cadastro simplificado (só usuário/senha) não
    # pedimos e-mail. unique=True + null=True funciona bem no Postgres, que
    # trata cada NULL como "diferente" dos outros (não conflita a unicidade).
    email = models.EmailField(unique=True, null=True, blank=True)
    telefone = models.CharField(max_length=20, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['nome']  # ordena por nome por padrão nas consultas
        verbose_name = 'Vendedor'
        verbose_name_plural = 'Vendedores'

    def __str__(self):
        # __str__ define como o objeto aparece no admin e em prints/debug.
        return self.nome


# ============================================================================
# PRODUTO
# ============================================================================
class Produto(models.Model):
    """Representa um item à venda na loja."""

    vendedor = models.ForeignKey(
        Vendedor,
        on_delete=models.CASCADE,      # se o vendedor for apagado, seus produtos também são
        related_name='produtos',       # permite fazer vendedor.produtos.all()
    )
    nome = models.CharField(max_length=200)
    descricao = models.TextField(blank=True)

    # DecimalField é o tipo correto para dinheiro (evita erros de arredondamento do float).
    preco = models.DecimalField(
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
    )

    # Quantidade disponível em estoque. Não pode ser negativa.
    estoque = models.PositiveIntegerField(default=0)

    ativo = models.BooleanField(default=True)  # permite "desativar" um produto sem apagá-lo
    imagem = models.ImageField(upload_to='produtos/', blank=True, null=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['nome']

    def __str__(self):
        return f'{self.nome} (R$ {self.preco})'

    def tem_estoque(self, quantidade):
        """Verifica se há unidades suficientes em estoque para a quantidade pedida."""
        return self.estoque >= quantidade


# ============================================================================
# CUPOM
# ============================================================================
class Cupom(models.Model):
    """
    Cupom de desconto que pode ser aplicado a um pedido.
    Nesta primeira entrega o cupom já existe como entidade (pedido no enunciado),
    mas a aplicação do desconto no carrinho é bem simples: percentual sobre o total.
    """

    codigo = models.CharField(max_length=30, unique=True)
    desconto_percentual = models.DecimalField(
        max_digits=5, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text='Valor de 0 a 100, representando a porcentagem de desconto.',
    )
    validade = models.DateField()
    ativo = models.BooleanField(default=True)

    def __str__(self):
        return f'{self.codigo} (-{self.desconto_percentual}%)'

    def esta_valido(self):
        """Um cupom só pode ser usado se estiver ativo e dentro da validade."""
        return self.ativo and self.validade >= timezone.localdate()


# ============================================================================
# PEDIDO
# ============================================================================
class Pedido(models.Model):
    """
    Representa o pedido feito por um cliente. Um Pedido é composto por vários
    ItemPedido (relação um-para-muitos), e é aqui que calculamos o total e
    controlamos a baixa de estoque quando o pedido é finalizado.
    """

    class Status(models.TextChoices):
        # TextChoices cria um "enum" — evita erros de digitação com strings soltas
        # e gera automaticamente um campo de escolha (dropdown) no admin/forms.
        ABERTO = 'ABERTO', 'Aberto (carrinho)'
        FINALIZADO = 'FINALIZADO', 'Finalizado'
        CANCELADO = 'CANCELADO', 'Cancelado'

    # Dados simples do cliente. Como esta entrega ainda não pede login/cadastro
    # de usuários, guardamos só nome/e-mail para identificar quem fez o pedido.
    cliente_nome = models.CharField(max_length=150, blank=True)
    cliente_email = models.EmailField(blank=True)

    # Chave de sessão do navegador, usada para "amarrar" o carrinho (que vive na
    # sessão) a um Pedido em status ABERTO, mesmo antes do cliente se identificar.
    sessao_chave = models.CharField(max_length=40, blank=True, db_index=True)

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ABERTO)

    cupom = models.ForeignKey(
        Cupom, on_delete=models.SET_NULL, null=True, blank=True, related_name='pedidos'
    )

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    finalizado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-criado_em']

    def __str__(self):
        return f'Pedido #{self.pk} ({self.get_status_display()})'

    # ------------------------------------------------------------------
    # CÁLCULO DO TOTAL — parte central desta entrega
    # ------------------------------------------------------------------
    def calcular_subtotal(self):
        """
        Soma (preço unitário x quantidade) de todos os itens do pedido.
        Usamos `select_related`/`prefetch` nas views para evitar consultas
        extras ao banco, mas aqui a lógica em si é simples.
        """
        subtotal = Decimal('0.00')
        for item in self.itens.all():
            subtotal += item.subtotal()
        return subtotal

    def calcular_desconto(self, subtotal=None):
        """Calcula o valor (em R$) de desconto dado pelo cupom aplicado, se houver."""
        if subtotal is None:
            subtotal = self.calcular_subtotal()

        if self.cupom and self.cupom.esta_valido():
            percentual = self.cupom.desconto_percentual / Decimal('100')
            return (subtotal * percentual).quantize(Decimal('0.01'))
        return Decimal('0.00')

    def calcular_total(self):
        """
        Total final do pedido = subtotal - desconto do cupom.
        Este é o valor que deve aparecer para o cliente no carrinho/checkout.
        """
        subtotal = self.calcular_subtotal()
        desconto = self.calcular_desconto(subtotal)
        total = subtotal - desconto
        # Nunca deixamos o total ficar negativo, por segurança.
        return max(total, Decimal('0.00'))

    # ------------------------------------------------------------------
    # FINALIZAÇÃO DO PEDIDO — baixa de estoque
    # ------------------------------------------------------------------
    def finalizar(self):
        """
        Confirma o pedido:
          1. Verifica se todos os itens ainda têm estoque suficiente
             (protege contra o caso de dois clientes comprarem ao mesmo tempo).
          2. Dá baixa no estoque de cada produto.
          3. Muda o status do pedido para FINALIZADO.

        Levanta ValueError se algum item não tiver estoque suficiente, para que
        a view possa capturar o erro e avisar o usuário.
        """
        itens = list(self.itens.select_related('produto'))

        # 1) Primeiro validamos TUDO, antes de alterar qualquer estoque.
        #    Assim evitamos dar baixa em alguns produtos e falhar no meio do processo.
        for item in itens:
            if not item.produto.tem_estoque(item.quantidade):
                raise ValueError(
                    f'Estoque insuficiente para "{item.produto.nome}". '
                    f'Disponível: {item.produto.estoque}, solicitado: {item.quantidade}.'
                )

        # 2) Agora sim, damos baixa no estoque de cada produto.
        for item in itens:
            produto = item.produto
            produto.estoque -= item.quantidade
            produto.save(update_fields=['estoque'])

        # 3) Atualizamos o status e a data de finalização do pedido.
        self.status = Pedido.Status.FINALIZADO
        self.finalizado_em = timezone.now()
        self.save(update_fields=['status', 'finalizado_em'])


# ============================================================================
# ITEM (ItemPedido)
# ============================================================================
class ItemPedido(models.Model):
    """
    Representa uma linha do pedido: "X unidades do Produto Y".
    Guardamos o preço unitário no momento da compra (`preco_unitario`) para que,
    se o preço do produto mudar depois, o histórico do pedido não seja afetado.
    """

    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name='itens')
    produto = models.ForeignKey(Produto, on_delete=models.PROTECT, related_name='itens_pedido')
    quantidade = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    preco_unitario = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        # Evita ter duas linhas separadas para o mesmo produto no mesmo pedido;
        # em vez disso, a view deve aumentar a quantidade do item já existente.
        unique_together = ('pedido', 'produto')

    def __str__(self):
        return f'{self.quantidade}x {self.produto.nome}'

    def subtotal(self):
        """Preço unitário x quantidade = subtotal desta linha do pedido."""
        return self.preco_unitario * self.quantidade
