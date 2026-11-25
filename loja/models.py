from decimal import Decimal

from django.conf import settings
from django.db import models, transaction
from django.core.validators import MaxValueValidator, MinValueValidator
from django.utils import timezone


class Vendedor(models.Model):

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='perfil_vendedor',
        null=True,
        blank=True,
    )

    nome = models.CharField(max_length=150)
    email = models.EmailField(unique=True, null=True, blank=True)
    telefone = models.CharField(max_length=20, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['nome'] 
        verbose_name = 'Vendedor'
        verbose_name_plural = 'Vendedores'

    def __str__(self):
        return self.nome


class Produto(models.Model):    

    vendedor = models.ForeignKey(
        Vendedor,
        on_delete=models.CASCADE,   
        related_name='produtos',   
    )
    nome = models.CharField(max_length=200)
    descricao = models.TextField(blank=True)

    preco = models.DecimalField(
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
    )

    estoque = models.PositiveIntegerField(default=0)

    ativo = models.BooleanField(default=True) 
    imagem = models.ImageField(upload_to='produtos/', blank=True, null=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['nome']

    def __str__(self):
        return f'{self.nome} (R$ {self.preco})'

    def tem_estoque(self, quantidade):
        return self.estoque >= quantidade


class Cupom(models.Model):
    vendedor = models.ForeignKey(
        Vendedor,
        on_delete=models.CASCADE, 
        related_name='cupons',   
        null=True,
        blank=True,
    )

    codigo = models.CharField(max_length=30)

    desconto_percentual = models.DecimalField(
        max_digits=5, decimal_places=2,
        validators=[
            MinValueValidator(
                Decimal('0.01'),
                message='O desconto deve ser um valor percentual entre 0.01% e 100%.',
            ),
            MaxValueValidator(
                Decimal('100'),
                message='O desconto deve ser um valor percentual entre 0.01% e 100%.',
            ),
        ],
        help_text='Valor de 0,01 a 100, representando a porcentagem de desconto.',
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
        return (
            self.vendedor_id is not None
            and self.ativo
            and self.validade >= timezone.localdate()
        )

class Pedido(models.Model):
    class Status(models.TextChoices):
        ABERTO = 'ABERTO', 'Aberto (carrinho)'
        FINALIZADO = 'FINALIZADO', 'Finalizado'
        CANCELADO = 'CANCELADO', 'Cancelado'

    cliente = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='pedidos',
        null=True,
        blank=True,
    )

    cliente_nome = models.CharField(max_length=150, blank=True)
    cliente_email = models.EmailField(blank=True)

    sessao_chave = models.CharField(max_length=40, blank=True, db_index=True)

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ABERTO)

    cupons = models.ManyToManyField(Cupom, blank=True, related_name='pedidos')

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

    def calcular_subtotal(self):
        subtotal = Decimal('0.00')
        for item in self.itens.all():
            subtotal += item.subtotal()
        return subtotal

    def detalhar_descontos(self):
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
        if self.status == Pedido.Status.FINALIZADO and self.desconto_aplicado is not None:
            return self.desconto_aplicado

        return sum((valor for _, valor in self.detalhar_descontos()), Decimal('0.00'))

    def calcular_total(self):
        subtotal = self.calcular_subtotal()
        desconto = self.calcular_desconto()
        total = subtotal - desconto
        return max(total, Decimal('0.00'))

    def finalizar(self):
        with transaction.atomic():
            atual = Pedido.objects.select_for_update().get(pk=self.pk)
            if atual.status != Pedido.Status.ABERTO:
                raise ValueError('Este pedido já foi finalizado.')

            itens = list(self.itens.all())

            produtos = {
                produto.pk: produto
                for produto in Produto.objects.select_for_update()
                .filter(pk__in=[item.produto_id for item in itens])
                .order_by('pk')
            }

            for item in itens:
                produto = produtos[item.produto_id]
                if not produto.tem_estoque(item.quantidade):
                    raise ValueError(
                        f'Estoque insuficiente para "{produto.nome}". '
                        f'Disponível: {produto.estoque}, solicitado: {item.quantidade}.'
                    )

            for item in itens:
                produto = produtos[item.produto_id]
                produto.estoque -= item.quantidade
                produto.save(update_fields=['estoque'])

            self.desconto_aplicado = self.calcular_desconto()
            self.status = Pedido.Status.FINALIZADO
            self.finalizado_em = timezone.now()
            self.save(update_fields=['status', 'finalizado_em', 'desconto_aplicado'])


class ItemPedido(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name='itens')
    produto = models.ForeignKey(Produto, on_delete=models.PROTECT, related_name='itens_pedido')
    quantidade = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    preco_unitario = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        unique_together = ('pedido', 'produto')

    def __str__(self):
        return f'{self.quantidade}x {self.produto.nome}'

    def subtotal(self):
        return self.preco_unitario * self.quantidade
