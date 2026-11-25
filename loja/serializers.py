from decimal import Decimal

from rest_framework import serializers

from .decorators import vendedor_atual
from .models import Cupom, ItemPedido, Pedido, Produto
from .validators import (
    normalizar_codigo_cupom,
    validar_codigo_cupom_unico,
    validar_validade_cupom,
)

class ProdutoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Produto
        fields = [
            'id', 'vendedor', 'nome', 'descricao', 'preco',
            'estoque', 'ativo', 'imagem', 'criado_em',
        ]
        read_only_fields = ['id', 'vendedor', 'criado_em']


class CupomSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cupom
        fields = ['id', 'vendedor', 'codigo', 'desconto_percentual', 'validade', 'ativo']
        read_only_fields = ['id', 'vendedor']

    def validate_codigo(self, valor):
        codigo = normalizar_codigo_cupom(valor)
        vendedor = vendedor_atual(self.context['request'])
        validar_codigo_cupom_unico(vendedor, codigo, self.instance)
        return codigo

    def validate_validade(self, valor):
        validar_validade_cupom(valor, self.instance)
        return valor


class ItemPedidoSerializer(serializers.ModelSerializer):

    produto_nome = serializers.CharField(source='produto.nome', read_only=True)
    subtotal = serializers.DecimalField(max_digits=20, decimal_places=2, read_only=True)

    class Meta:
        model = ItemPedido
        fields = ['id', 'produto', 'produto_nome', 'quantidade', 'preco_unitario', 'subtotal']
        read_only_fields = fields


class PedidoClienteSerializer(serializers.ModelSerializer):

    itens = ItemPedidoSerializer(many=True, read_only=True)
    subtotal = serializers.DecimalField(
        max_digits=20, decimal_places=2, source='calcular_subtotal', read_only=True
    )
    desconto = serializers.DecimalField(
        max_digits=20, decimal_places=2, source='calcular_desconto', read_only=True
    )
    total = serializers.DecimalField(
        max_digits=20, decimal_places=2, source='calcular_total', read_only=True
    )

    class Meta:
        model = Pedido
        fields = [
            'id', 'status', 'cliente_nome', 'cliente_email',
            'criado_em', 'finalizado_em',
            'itens', 'subtotal', 'desconto', 'total',
        ]
        read_only_fields = fields


class PedidoVendedorSerializer(serializers.ModelSerializer):
    itens = ItemPedidoSerializer(many=True, read_only=True, source='itens_do_vendedor')
    subtotal = serializers.SerializerMethodField()

    class Meta:
        model = Pedido
        fields = [
            'id', 'status', 'cliente_nome', 'cliente_email',
            'criado_em', 'finalizado_em',
            'itens', 'subtotal',
        ]
        read_only_fields = fields

    def get_subtotal(self, pedido):
        total = sum(
            (item.subtotal() for item in pedido.itens_do_vendedor), Decimal('0.00')
        )
        return total.quantize(Decimal('0.01'))
