from django.contrib import admin

from .models import Cupom, ItemPedido, Pedido, Produto, Vendedor


@admin.register(Vendedor)
class VendedorAdmin(admin.ModelAdmin):
    list_display = ('nome', 'email', 'telefone', 'criado_em')
    search_fields = ('nome', 'email')


@admin.register(Produto)
class ProdutoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'vendedor', 'preco', 'estoque', 'ativo')
    list_filter = ('ativo', 'vendedor')
    search_fields = ('nome',)
    list_editable = ('preco', 'estoque', 'ativo')  # permite editar direto na listagem


@admin.register(Cupom)
class CupomAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'desconto_percentual', 'validade', 'ativo')
    list_filter = ('ativo',)


class ItemPedidoInline(admin.TabularInline):
    """
    Um "inline" mostra os ItemPedido diretamente dentro da tela do Pedido no
    admin, em vez de precisar navegar para outra tela — muito mais prático
    para conferir o que tem em cada pedido.
    """
    model = ItemPedido
    extra = 0  # não mostra linhas extras em branco por padrão
    readonly_fields = ('preco_unitario',)


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ('id', 'status', 'cliente_nome', 'cliente_email', 'criado_em', 'total_admin')
    list_filter = ('status',)
    inlines = [ItemPedidoInline]

    def total_admin(self, obj):
        """Coluna calculada mostrando o total do pedido (usa nosso método do model)."""
        return f'R$ {obj.calcular_total()}'
    total_admin.short_description = 'Total'
