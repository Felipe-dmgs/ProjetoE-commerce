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
    Cupom de desconto criado por UM vendedor e válido apenas para os produtos
    dele. O `vendedor` é o dono do cupom: só ele o enxerga e edita na área
    do vendedor, e o desconto incide só sobre os itens desse vendedor no
    carrinho (ver Pedido.detalhar_descontos).

    `null=True, blank=True` existe só para os cupons criados ANTES desta
    mudança, que não tinham dono. Um cupom sem vendedor nunca é considerado
    válido (ver esta_valido) até que alguém atribua um dono a ele pelo admin.
    """

    vendedor = models.ForeignKey(
        Vendedor,
        on_delete=models.CASCADE,   # se o vendedor for apagado, seus cupons também são
        related_name='cupons',      # permite fazer vendedor.cupons.all()
        null=True,
        blank=True,
    )

    # Não é mais unique=True (global): dois vendedores diferentes podem ter um
    # cupom com o mesmo código. A unicidade agora é POR VENDEDOR (ver Meta).
    codigo = models.CharField(max_length=30)
    desconto_percentual = models.DecimalField(
        max_digits=5, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text='Valor de 0 a 100, representando a porcentagem de desconto.',
    )
    validade = models.DateField()
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ['codigo']
        constraints = [
            models.UniqueConstraint(
                fields=['vendedor', 'codigo'],
                name='cupom_codigo_unico_por_vendedor',
            ),
        ]

    def __str__(self):
        return f'{self.codigo} (-{self.desconto_percentual}%)'

    def esta_valido(self):
        """
        Um cupom só pode ser usado se tiver dono, estiver ativo e dentro da
        validade.
        """
        return (
            self.vendedor_id is not None
            and self.ativo
            and self.validade >= timezone.localdate()
        )


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

    # Um pedido pode ter VÁRIOS cupons, no máximo um por vendedor: cada cupom
    # desconta só os itens do seu vendedor (ver detalhar_descontos). A regra
    # "um por vendedor" é garantida na view que aplica o cupom (ver_carrinho).
    cupons = models.ManyToManyField(Cupom, blank=True, related_name='pedidos')

    # "Foto" do desconto no instante em que o pedido é finalizado. Sem isso, o
    # total de um pedido antigo mudaria se o vendedor depois alterasse a
    # porcentagem do cupom, desativasse ou deixasse vencer. Fica nulo enquanto
    # o pedido é um carrinho aberto (aí o desconto é calculado na hora).
    desconto_aplicado = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
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

    def detalhar_descontos(self):
        """
        Devolve uma lista de (cupom, valor_do_desconto), uma linha para cada
        cupom aplicado ao pedido.

        Cada cupom desconta somente os itens cujo produto pertence ao vendedor
        dono dele: um carrinho pode misturar vários vendedores, e o cupom de um
        não deve baratear o produto de outro. Um cupom vencido, desativado ou
        sem nenhum item do seu vendedor no carrinho aparece com valor zero.
        """
        itens = list(self.itens.select_related('produto'))
        detalhes = []

        for cupom in self.cupons.select_related('vendedor').order_by('vendedor__nome'):
            valor = Decimal('0.00')
            if cupom.esta_valido():
                base = sum(
                    (i.subtotal() for i in itens if i.produto.vendedor_id == cupom.vendedor_id),
                    Decimal('0.00'),
                )
                percentual = cupom.desconto_percentual / Decimal('100')
                valor = (base * percentual).quantize(Decimal('0.01'))
            detalhes.append((cupom, valor))

        return detalhes

    def calcular_desconto(self):
        """Valor total (em R$) de desconto: a soma do desconto de cada cupom aplicado."""
        # Pedido já finalizado: vale a "foto" gravada na finalização, para que
        # mudanças posteriores nos cupons não alterem o histórico.
        if self.status == Pedido.Status.FINALIZADO and self.desconto_aplicado is not None:
            return self.desconto_aplicado

        return sum((valor for _, valor in self.detalhar_descontos()), Decimal('0.00'))

    def calcular_total(self):
        """
        Total final do pedido = subtotal - desconto do cupom.
        Este é o valor que deve aparecer para o cliente no carrinho/checkout.
        """
        subtotal = self.calcular_subtotal()
        desconto = self.calcular_desconto()
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

        # 3) Guardamos o desconto como está agora (ainda com status ABERTO, o
        #    cálculo é "ao vivo") e só então atualizamos o status e a data.
        self.desconto_aplicado = self.calcular_desconto()
        self.status = Pedido.Status.FINALIZADO
        self.finalizado_em = timezone.now()
        self.save(update_fields=['status', 'finalizado_em', 'desconto_aplicado'])


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
