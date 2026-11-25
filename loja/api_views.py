from django.db.models import Prefetch, ProtectedError
from rest_framework import generics
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .dashboard import montar_dashboard, periodo_da_requisicao
from .decorators import vendedor_atual
from .models import Cupom, ItemPedido, Pedido, Produto
from .permissions import IsVendedor
from .serializers import (
    CupomSerializer,
    PedidoClienteSerializer,
    PedidoVendedorSerializer,
    ProdutoSerializer,
)


class ProdutoListCreateAPIView(generics.ListCreateAPIView):
    serializer_class = ProdutoSerializer
    permission_classes = [IsVendedor]

    def get_queryset(self):
        return Produto.objects.filter(vendedor=vendedor_atual(self.request))

    def perform_create(self, serializer):
        serializer.save(vendedor=vendedor_atual(self.request))


class ProdutoDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ProdutoSerializer
    permission_classes = [IsVendedor]

    def get_queryset(self):
        return Produto.objects.filter(vendedor=vendedor_atual(self.request))

    def perform_destroy(self, instance):
        try:
            instance.delete()
        except ProtectedError:
            raise ValidationError({
                'detail': 'Este produto não pode ser excluído porque já consta em '
                          'pedidos ou carrinhos. Desative-o (ativo=false) em vez de excluir.'
            })


class CupomListCreateAPIView(generics.ListCreateAPIView):
    serializer_class = CupomSerializer
    permission_classes = [IsVendedor]

    def get_queryset(self):
        return Cupom.objects.filter(vendedor=vendedor_atual(self.request))

    def perform_create(self, serializer):
        serializer.save(vendedor=vendedor_atual(self.request))


class CupomDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CupomSerializer
    permission_classes = [IsVendedor]

    def get_queryset(self):
        return Cupom.objects.filter(vendedor=vendedor_atual(self.request))


class PedidoQuerysetMixin:
    def _eh_vendedor(self):
        return hasattr(self.request.user, 'perfil_vendedor')

    def get_queryset(self):
        if self._eh_vendedor():
            vendedor = vendedor_atual(self.request)

            itens_do_vendedor = ItemPedido.objects.filter(
                produto__vendedor=vendedor
            ).select_related('produto')

            return (
                Pedido.objects
                .filter(
                    status=Pedido.Status.FINALIZADO,
                    cliente__isnull=False,
                    itens__produto__vendedor=vendedor,
                )
                .distinct()
                .prefetch_related(
                    Prefetch('itens', queryset=itens_do_vendedor, to_attr='itens_do_vendedor')
                )
                .order_by('-finalizado_em', '-pk')
            )

        return (
            Pedido.objects
            .filter(cliente=self.request.user, status=Pedido.Status.FINALIZADO)
            .prefetch_related('itens__produto') 
            .order_by('-finalizado_em', '-pk')
        )

    def get_serializer_class(self):
        if self._eh_vendedor():
            return PedidoVendedorSerializer
        return PedidoClienteSerializer


class PedidoListAPIView(PedidoQuerysetMixin, generics.ListAPIView):
    """GET lista os pedidos visíveis para o usuário logado (POST/PUT/DELETE: 405)."""


class PedidoDetailAPIView(PedidoQuerysetMixin, generics.RetrieveAPIView):
    """GET de um pedido visível para o usuário logado (de outra pessoa: 404)."""


class DashboardAPIView(APIView):
    """
    GET /api/dashboard/?de=AAAA-MM-DD&ate=AAAA-MM-DD  (padrão: mês atual)

    As mesmas métricas da tela, geradas pelas mesmas funções de
    loja/dashboard.py. Só vendedor acessa (IsVendedor) e só vê os próprios
    números. Como só existe get(), POST/PUT/DELETE respondem 405.
    """
    permission_classes = [IsVendedor]

    def get(self, request):
        form, de, ate = periodo_da_requisicao(request.GET)
        if not form.is_valid():
            # Na API, período inválido é erro 400 (a tela, ao contrário, mostra
            # um aviso e usa o mês atual).
            erros = {}
            for campo, lista in form.errors.get_json_data().items():
                erros['periodo' if campo == '__all__' else campo] = [e['message'] for e in lista]
            return Response(erros, status=400)

        # Decimal e date são convertidos para texto pelo renderizador do DRF.
        return Response(montar_dashboard(vendedor_atual(request), de, ate))
