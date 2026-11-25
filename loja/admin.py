from django.contrib import admin

from .models import Cupom, DescontoCupom, ItemPedido, Pedido, Produto, Vendedor


@admin.register(Vendedor)
class VendedorAdmin(admin.ModelAdmin):
    list_display = ('nome', 'usuario', 'email', 'telefone', 'criado_em')
    search_fields = ('nome', 'email', 'usuario__username')


@admin.register(Produto)
class ProdutoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'vendedor', 'preco', 'estoque', 'ativo')
    list_filter = ('ativo', 'vendedor')
    search_fields = ('nome',)
    list_editable = ('preco', 'estoque', 'ativo')  # permite editar direto na listagem


@admin.register(Cupom)
class CupomAdmin(admin.ModelAdmin):
    # Cupons antigos (criados antes de existir "dono") aparecem com vendedor
    # vazio e não valem até você escolher um vendedor para eles aqui.
    list_display = ('codigo', 'vendedor', 'desconto_percentual', 'validade', 'ativo')
    list_filter = ('ativo', 'vendedor')


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
    list_display = ('id', 'status', 'cliente', 'cliente_nome', 'cliente_email', 'criado_em', 'total_admin')
    list_filter = ('status',)
    inlines = [ItemPedidoInline]

    def total_admin(self, obj):
        """Coluna calculada mostrando o total do pedido (usa nosso método do model)."""
        return f'R$ {obj.calcular_total()}'
    total_admin.short_description = 'Total'


@admin.register(DescontoCupom)
class DescontoCupomAdmin(admin.ModelAdmin):
    """Desconto gravado na finalização de cada pedido (só leitura: é histórico)."""
    list_display = ('pedido', 'vendedor', 'codigo', 'percentual', 'valor')
    list_filter = ('vendedor',)
    readonly_fields = ('pedido', 'vendedor', 'cupom', 'codigo', 'percentual', 'valor')
