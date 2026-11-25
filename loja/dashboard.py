"""
loja/dashboard.py
-----------------
Métricas do dashboard do vendedor. Fica fora do views.py para que a MESMA
lógica seja usada pela tela HTML, pelo CSV e pela API (/api/dashboard/), sem
duplicar consultas.

Regras que valem para TODAS as métricas daqui (isolamento multi-tenant):
  1. Toda consulta parte do vendedor logado (filtro `produto__vendedor`); o
     vendedor vem de vendedor_atual(request), nunca de URL ou formulário.
  2. Só pedidos FINALIZADOS entram (carrinho aberto não é venda).
  3. A receita é SEMPRE ItemPedido.preco_unitario x quantidade (o preço gravado
     na compra), nunca o preço atual do produto.
  4. Só os itens dos produtos do vendedor entram: um pedido pode ter itens de
     outros vendedores, que não aparecem nem somam aqui.
"""

from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.db.models import Count, DecimalField, ExpressionWrapper, F, Q, Sum
from django.db.models.functions import TruncDate, TruncMonth
from django.utils import timezone

from .forms import PeriodoForm
from .models import DescontoCupom, ItemPedido, Pedido, Produto

# Produto com estoque até este valor aparece como "estoque baixo". Constante
# (e não campo no model) para o dashboard não exigir mudança no cadastro.
ESTOQUE_BAIXO_LIMITE = 5

# Até este tamanho de período a série é diária; acima disso, mensal (um gráfico
# com centenas de barras diárias fica ilegível).
DIAS_MAX_SERIE_DIARIA = 62

ZERO = Decimal('0.00')

# preço gravado x quantidade. O ExpressionWrapper informa o tipo do resultado
# (Decimal x inteiro), que o Django não adivinha sozinho em todas as versões.
RECEITA = ExpressionWrapper(
    F('preco_unitario') * F('quantidade'),
    output_field=DecimalField(max_digits=14, decimal_places=2),
)


# ---------------------------------------------------------------------------
# Período
# ---------------------------------------------------------------------------
def periodo_padrao():
    """Mês atual: do dia 1º até hoje (no fuso do projeto)."""
    hoje = timezone.localdate()
    return hoje.replace(day=1), hoje


def resolver_periodo(dados):
    """
    Converte o cleaned_data do PeriodoForm no par (de, ate).
      - sem nada: mês atual;
      - só "de": de até hoje;
      - só "ate": do dia 1º do mês de "ate" até "ate".
    O PeriodoForm já garantiu que de <= ate.
    """
    de, ate = dados.get('de'), dados.get('ate')
    if de is None and ate is None:
        return periodo_padrao()
    if ate is None:
        ate = timezone.localdate()
    if de is None:
        de = ate.replace(day=1)
    return de, ate


def periodo_da_requisicao(params):
    """
    Lê ?de=&ate= (params = request.GET) e devolve (form, de, ate).
    Se o período for inválido, de/ate caem no padrão (mês atual) e o form
    carrega os erros: a tela mostra o aviso e a API responde 400.
    """
    form = PeriodoForm(params)
    if form.is_valid():
        de, ate = resolver_periodo(form.cleaned_data)
    else:
        de, ate = periodo_padrao()
    return form, de, ate


def limites_do_periodo(de, ate):
    """
    Datas -> intervalo de datetimes [inicio, fim) no fuso do projeto.
    O "ate" é inclusivo, por isso o limite superior é a meia-noite do dia
    seguinte, com `<`. (Usar `__lte=<data>` num DateTimeField cortaria o
    último dia, pois a data vira 00:00.)
    """
    fuso = timezone.get_current_timezone()
    inicio = timezone.make_aware(datetime.combine(de, time.min), fuso)
    fim = timezone.make_aware(datetime.combine(ate + timedelta(days=1), time.min), fuso)
    return inicio, fim


# ---------------------------------------------------------------------------
# Base filtrada: todas as métricas de vendas derivam dela
# ---------------------------------------------------------------------------
def itens_vendidos(vendedor, de, ate):
    """
    Itens vendidos pelo vendedor no período. Partir de ItemPedido (e não de
    Pedido) evita que o join com os itens multiplique linhas na soma.
    """
    inicio, fim = limites_do_periodo(de, ate)
    return ItemPedido.objects.filter(
        produto__vendedor=vendedor,  # 1ª linha de toda métrica: o dono
        pedido__status=Pedido.Status.FINALIZADO,
        # Mesma regra de "Pedidos recebidos" e de /api/pedidos/, para os
        # números baterem entre as telas (pedidos antigos sem cliente ficam fora).
        pedido__cliente__isnull=False,
        pedido__finalizado_em__gte=inicio,
        pedido__finalizado_em__lt=fim,
    )


# ---------------------------------------------------------------------------
# Métricas
# ---------------------------------------------------------------------------
def calcular_totais(vendedor, de, ate):
    """KPIs: faturamento, descontos, líquido, pedidos, unidades e ticket médio."""
    itens = itens_vendidos(vendedor, de, ate)

    # aggregate() devolve UM dicionário; Count com distinct conta cada pedido
    # uma vez, mesmo que ele tenha vários itens do vendedor.
    r = itens.aggregate(
        bruto=Sum(RECEITA),
        pedidos=Count('pedido', distinct=True),
        unidades=Sum('quantidade'),
    )
    bruto = r['bruto'] or ZERO
    pedidos = r['pedidos'] or 0
    unidades = r['unidades'] or 0

    # Descontos que os cupons DESTE vendedor concederam (gravados na
    # finalização). Mesmo filtro de pedidos e de período dos itens.
    inicio, fim = limites_do_periodo(de, ate)
    descontos = DescontoCupom.objects.filter(
        vendedor=vendedor,
        pedido__status=Pedido.Status.FINALIZADO,
        pedido__cliente__isnull=False,
        pedido__finalizado_em__gte=inicio,
        pedido__finalizado_em__lt=fim,
    ).aggregate(total=Sum('valor'))['total'] or ZERO

    # Ticket médio = faturamento bruto / pedidos, só da parte do vendedor.
    ticket = (bruto / pedidos).quantize(Decimal('0.01')) if pedidos else ZERO

    return {
        'faturamento_bruto': bruto,
        'descontos_concedidos': descontos,
        'faturamento_liquido': bruto - descontos,
        'pedidos': pedidos,
        'unidades': unidades,
        'ticket_medio': ticket,
    }


def calcular_top_produtos(vendedor, de, ate, limite=5):
    """Ranking dos produtos mais vendidos (por unidades; receita como desempate)."""
    return list(
        itens_vendidos(vendedor, de, ate)
        # Agrupa por id E nome: dois produtos com o mesmo nome não se fundem.
        .values('produto_id', 'produto__nome')
        .annotate(unidades=Sum('quantidade'), receita=Sum(RECEITA))
        # order_by completo, com desempate, para o ranking ser determinístico.
        .order_by('-unidades', '-receita', 'produto__nome')[:limite]
    )


def calcular_serie(vendedor, de, ate):
    """
    Faturamento bruto ao longo do tempo: por dia (períodos de até 62 dias) ou
    por mês. Dias/meses sem venda entram com zero, para o gráfico não pular.
    """
    diaria = (ate - de).days <= DIAS_MAX_SERIE_DIARIA
    trunc = (
        TruncDate('pedido__finalizado_em') if diaria
        else TruncMonth('pedido__finalizado_em')
    )

    linhas = (
        itens_vendidos(vendedor, de, ate)
        .annotate(periodo=trunc)
        .values('periodo')
        .annotate(receita=Sum(RECEITA), pedidos=Count('pedido', distinct=True))
        .order_by('periodo')  # sem order_by o gráfico sairia embaralhado
    )

    por_periodo = {}
    for linha in linhas:
        chave = linha['periodo']
        if isinstance(chave, datetime):  # TruncMonth devolve datetime
            chave = chave.date()
        por_periodo[chave] = linha

    # Percorre todos os dias (ou meses) do período preenchendo as lacunas.
    chaves = []
    if diaria:
        dia = de
        while dia <= ate:
            chaves.append(dia)
            dia += timedelta(days=1)
    else:
        ano, mes = de.year, de.month
        while (ano, mes) <= (ate.year, ate.month):
            chaves.append(date(ano, mes, 1))
            ano, mes = (ano + 1, 1) if mes == 12 else (ano, mes + 1)

    formato = '%d/%m' if diaria else '%m/%Y'
    serie = []
    for chave in chaves:
        linha = por_periodo.get(chave)
        serie.append({
            'periodo': chave,
            'rotulo': chave.strftime(formato),
            'receita': linha['receita'] if linha else ZERO,
            'pedidos': linha['pedidos'] if linha else 0,
        })
    return serie, ('dia' if diaria else 'mes')


def calcular_estoque(vendedor, limite_lista=10):
    """
    Situação do estoque dos produtos ATIVOS do vendedor. É uma "foto de agora":
    não depende do período escolhido.
    """
    ativos = Produto.objects.filter(vendedor=vendedor, ativo=True)

    # Count com filter= calcula as 4 contagens numa consulta só.
    contagem = ativos.aggregate(
        esgotados=Count('id', filter=Q(estoque=0)),
        baixos=Count('id', filter=Q(estoque__gt=0, estoque__lte=ESTOQUE_BAIXO_LIMITE)),
        ok=Count('id', filter=Q(estoque__gt=ESTOQUE_BAIXO_LIMITE)),
        total_ativos=Count('id'),
    )

    criticos = list(
        ativos.filter(estoque__lte=ESTOQUE_BAIXO_LIMITE)
        .order_by('estoque', 'nome')
        .values('id', 'nome', 'estoque')[:limite_lista]
    )
    return {'limite_baixo': ESTOQUE_BAIXO_LIMITE, **contagem, 'produtos_criticos': criticos}


def montar_dashboard(vendedor, de, ate):
    """Reúne todas as métricas; é o que a tela e a API devolvem."""
    serie, granularidade = calcular_serie(vendedor, de, ate)
    return {
        'periodo': {'de': de, 'ate': ate, 'granularidade': granularidade},
        'totais': calcular_totais(vendedor, de, ate),
        'top_produtos': [
            {
                'produto_id': r['produto_id'],
                'produto': r['produto__nome'],
                'unidades': r['unidades'],
                'receita': r['receita'],
            }
            for r in calcular_top_produtos(vendedor, de, ate)
        ],
        'serie': serie,
        'estoque': calcular_estoque(vendedor),
    }
