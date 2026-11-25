"""
loja/management/commands/popular_dados.py
-----------------------------------------
Comando Django (`python manage.py popular_dados`) que popula o banco de dados
com contas de teste (admin, vendedores e clientes), produtos, cupons e pedidos
finalizados de exemplo, para facilitar a visualização e avaliação do sistema.

O comando é idempotente: pode ser executado várias vezes (inclusive a cada
inicialização do container no `entrypoint.sh`) sem duplicar registros nem
quebrar com erro de integridade. Ao final, sempre imprime no terminal as
credenciais de acesso prontas para login.
"""

from datetime import datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from loja.models import Cupom, ItemPedido, Pedido, Produto, Vendedor


ADMIN_SEED = {
    'username': 'admin',
    'password': 'admin123',
    'email': 'admin@ecommerce.local',
    'first_name': 'Administrador',
    'last_name': 'Sistema',
}

VENDEDORES_SEED = [
    {
        'username': 'vendedor1',
        'password': 'vendedor123',
        'first_name': 'Ana',
        'last_name': 'Oliveira',
        'email': 'contato@techstore.com',
        'loja_nome': 'TechStore Brasil',
        'telefone': '(24) 99999-1001',
        'produtos': [
            {
                'nome': 'Notebook Pro 15"',
                'descricao': 'Notebook com processador octa-core, 16GB RAM e SSD 512GB.',
                'preco': Decimal('4299.90'),
                'estoque_final': 12,
            },
            {
                'nome': 'Mouse Sem Fio Ergonômico',
                'descricao': 'Mouse óptico recarregável com conexão Bluetooth e USB.',
                'preco': Decimal('149.90'),
                'estoque_final': 25,
            },
            {
                'nome': 'Teclado Mecânico RGB',
                'descricao': 'Teclado mecânico ABNT2 com switches táteis e iluminação RGB.',
                'preco': Decimal('329.90'),
                'estoque_final': 4,  # estoque baixo (<= 5) para destaque no dashboard
            },
            {
                'nome': 'Headset Gamer Surround',
                'descricao': 'Fone circum-aural com microfone removível e som surround 7.1.',
                'preco': Decimal('279.90'),
                'estoque_final': 18,
            },
            {
                'nome': 'Webcam Full HD 1080p',
                'descricao': 'Webcam 1080p 60fps com foco automático e microfone embutido.',
                'preco': Decimal('199.90'),
                'estoque_final': 0,  # esgotado para aparecer no gráfico de estoque
            },
        ],
        'cupons': [
            {
                'codigo': 'TECH10',
                'desconto_percentual': Decimal('10.00'),
                'dias_validade': 60,
            },
            {
                'codigo': 'BEMVINDO15',
                'desconto_percentual': Decimal('15.00'),
                'dias_validade': 30,
            },
        ],
    },
    {
        'username': 'vendedor2',
        'password': 'vendedor123',
        'first_name': 'Carlos',
        'last_name': 'Mendes',
        'email': 'contato@casaecafe.com',
        'loja_nome': 'Casa & Café',
        'telefone': '(24) 99999-2002',
        'produtos': [
            {
                'nome': 'Cafeteira Italiana Inox 6 Xícaras',
                'descricao': 'Cafeteira moka em aço inoxidável compatível com fogão de indução.',
                'preco': Decimal('189.90'),
                'estoque_final': 15,
            },
            {
                'nome': 'Café Especial Torra Média 500g',
                'descricao': 'Grãos 100% arábica selecionados com notas de chocolate e caramelo.',
                'preco': Decimal('49.90'),
                'estoque_final': 40,
            },
            {
                'nome': 'Moedor de Café Manual',
                'descricao': 'Moedor com lâminas de cerâmica e regulagem fina de moagem.',
                'preco': Decimal('129.90'),
                'estoque_final': 3,  # estoque baixo (<= 5) para destaque no dashboard
            },
            {
                'nome': 'Caneca Térmica 450ml',
                'descricao': 'Caneca em aço inox com parede dupla e tampa antivazamento.',
                'preco': Decimal('79.90'),
                'estoque_final': 22,
            },
            {
                'nome': 'Chaleira Bico de Ganso',
                'descricao': 'Chaleira de precisão 800ml ideal para café coado.',
                'preco': Decimal('219.90'),
                'estoque_final': 0,  # esgotado para aparecer no gráfico de estoque
            },
        ],
        'cupons': [
            {
                'codigo': 'CAFE10',
                'desconto_percentual': Decimal('10.00'),
                'dias_validade': 60,
            },
            {
                'codigo': 'CASA20',
                'desconto_percentual': Decimal('20.00'),
                'dias_validade': 30,
            },
        ],
    },
]

CLIENTES_SEED = [
    {
        'username': 'cliente1',
        'password': 'cliente123',
        'first_name': 'Maria',
        'last_name': 'Silva',
        'email': 'maria@exemplo.com',
    },
    {
        'username': 'cliente2',
        'password': 'cliente123',
        'first_name': 'João',
        'last_name': 'Santos',
        'email': 'joao@exemplo.com',
    },
]

# Pedidos de exemplo que alimentam "Meus pedidos", "Pedidos recebidos" e o Dashboard.
# Inclui um pedido misto (itens dos dois vendedores + cupons dos dois) para demonstrar
# o isolamento multi-organização.
PEDIDOS_SEED = [
    {
        'cliente': 'cliente1',
        'itens': [
            ('vendedor1', 'Notebook Pro 15"', 1),
            ('vendedor1', 'Mouse Sem Fio Ergonômico', 2),
            ('vendedor2', 'Café Especial Torra Média 500g', 2),
        ],
        'cupons': [
            ('vendedor1', 'TECH10'),
            ('vendedor2', 'CAFE10'),
        ],
        'no_mes_atual': True,
        'fracao_mes': 0.25,
    },
    {
        'cliente': 'cliente2',
        'itens': [
            ('vendedor1', 'Teclado Mecânico RGB', 1),
            ('vendedor1', 'Headset Gamer Surround', 1),
        ],
        'cupons': [],
        'no_mes_atual': True,
        'fracao_mes': 0.50,
    },
    {
        'cliente': 'cliente2',
        'itens': [
            ('vendedor2', 'Cafeteira Italiana Inox 6 Xícaras', 1),
            ('vendedor2', 'Caneca Térmica 450ml', 2),
        ],
        'cupons': [
            ('vendedor2', 'CASA20'),
        ],
        'no_mes_atual': True,
        'fracao_mes': 0.75,
    },
    {
        'cliente': 'cliente1',
        'itens': [
            ('vendedor1', 'Headset Gamer Surround', 2),
            ('vendedor1', 'Mouse Sem Fio Ergonômico', 1),
        ],
        'cupons': [
            ('vendedor1', 'BEMVINDO15'),
        ],
        'no_mes_atual': True,
        'fracao_mes': 1.00,
    },
    {
        'cliente': 'cliente1',
        'itens': [
            ('vendedor2', 'Moedor de Café Manual', 1),
            ('vendedor2', 'Café Especial Torra Média 500g', 3),
        ],
        'cupons': [
            ('vendedor2', 'CAFE10'),
        ],
        'no_mes_atual': False,
        'dias_atras': 35,
    },
]


class Command(BaseCommand):
    help = (
        'Popula o banco com usuários (admin, vendedores e clientes), produtos, '
        'cupons e pedidos de exemplo, exibindo os dados de login no terminal.'
    )

    def handle(self, *args, **options):
        with transaction.atomic():
            resumo = self._popular()

        self._imprimir_resumo(resumo)
        self._imprimir_credenciais()

    def _popular(self):
        hoje = timezone.localdate()
        resumo = {
            'admin_criado': False,
            'vendedores_criados': 0,
            'clientes_criados': 0,
            'produtos_criados': 0,
            'cupons_criados': 0,
            'pedidos_criados': 0,
        }

        # 1. Superusuário para acesso ao /admin/
        admin_user, criado = User.objects.get_or_create(
            username=ADMIN_SEED['username'],
            defaults={
                'email': ADMIN_SEED['email'],
                'first_name': ADMIN_SEED['first_name'],
                'last_name': ADMIN_SEED['last_name'],
                'is_staff': True,
                'is_superuser': True,
            },
        )
        if criado:
            admin_user.set_password(ADMIN_SEED['password'])
            admin_user.save(update_fields=['password'])
            resumo['admin_criado'] = True

        # 2. Clientes
        clientes_map = {}
        for dados in CLIENTES_SEED:
            usuario, criado = User.objects.get_or_create(
                username=dados['username'],
                defaults={
                    'email': dados['email'],
                    'first_name': dados['first_name'],
                    'last_name': dados['last_name'],
                },
            )
            if criado:
                usuario.set_password(dados['password'])
                usuario.save(update_fields=['password'])
                resumo['clientes_criados'] += 1
            clientes_map[dados['username']] = usuario

        # Verifica se os pedidos de exemplo já existem para os clientes do seed
        precisa_criar_pedidos = not Pedido.objects.filter(
            cliente__in=clientes_map.values(),
            status=Pedido.Status.FINALIZADO,
        ).exists()

        # Calcula quantas unidades de cada produto serão baixadas pelos pedidos de exemplo,
        # para que após chamar `pedido.finalizar()` o estoque final seja exatamente `estoque_final`.
        consumo_seed = {}
        if precisa_criar_pedidos:
            for pedido_cfg in PEDIDOS_SEED:
                for vend_user, prod_nome, qtd in pedido_cfg['itens']:
                    chave = (vend_user, prod_nome)
                    consumo_seed[chave] = consumo_seed.get(chave, 0) + qtd

        # 3. Vendedores, produtos e cupons
        produtos_map = {}
        cupons_map = {}

        for dados in VENDEDORES_SEED:
            usuario, criado_user = User.objects.get_or_create(
                username=dados['username'],
                defaults={
                    'email': dados['email'],
                    'first_name': dados['first_name'],
                    'last_name': dados['last_name'],
                },
            )
            if criado_user:
                usuario.set_password(dados['password'])
                usuario.save(update_fields=['password'])

            vendedor, criado_vend = Vendedor.objects.get_or_create(
                usuario=usuario,
                defaults={
                    'nome': dados['loja_nome'],
                    'email': dados['email'],
                    'telefone': dados['telefone'],
                },
            )
            if criado_vend:
                resumo['vendedores_criados'] += 1

            for prod_cfg in dados['produtos']:
                estoque_inicial = prod_cfg['estoque_final'] + consumo_seed.get(
                    (dados['username'], prod_cfg['nome']), 0
                )
                produto, criado_prod = Produto.objects.get_or_create(
                    vendedor=vendedor,
                    nome=prod_cfg['nome'],
                    defaults={
                        'descricao': prod_cfg['descricao'],
                        'preco': prod_cfg['preco'],
                        'estoque': estoque_inicial,
                        'ativo': True,
                    },
                )
                if criado_prod:
                    resumo['produtos_criados'] += 1
                produtos_map[(dados['username'], prod_cfg['nome'])] = produto

            for cupom_cfg in dados['cupons']:
                cupom, criado_cupom = Cupom.objects.get_or_create(
                    vendedor=vendedor,
                    codigo=cupom_cfg['codigo'],
                    defaults={
                        'desconto_percentual': cupom_cfg['desconto_percentual'],
                        'validade': hoje + timedelta(days=cupom_cfg['dias_validade']),
                        'ativo': True,
                    },
                )
                if criado_cupom:
                    resumo['cupons_criados'] += 1
                cupons_map[(dados['username'], cupom_cfg['codigo'])] = cupom

        # 4. Pedidos finalizados de exemplo (passando pela lógica real `pedido.finalizar()`)
        if precisa_criar_pedidos:
            agora = timezone.now()
            fuso = timezone.get_current_timezone()
            inicio_mes = timezone.make_aware(
                datetime.combine(hoje.replace(day=1), time.min), fuso
            )
            intervalo_mes = max(agora - inicio_mes, timedelta(0))

            for pedido_cfg in PEDIDOS_SEED:
                cliente = clientes_map[pedido_cfg['cliente']]
                pedido = Pedido.objects.create(
                    cliente=cliente,
                    cliente_nome=cliente.get_full_name() or cliente.username,
                    cliente_email=cliente.email,
                )

                for vend_user, prod_nome, qtd in pedido_cfg['itens']:
                    produto = produtos_map[(vend_user, prod_nome)]
                    produto.refresh_from_db(fields=['estoque'])
                    # Garante estoque suficiente caso o produto já existisse antes
                    if produto.estoque < qtd:
                        produto.estoque = qtd
                        produto.save(update_fields=['estoque'])
                    ItemPedido.objects.create(
                        pedido=pedido,
                        produto=produto,
                        quantidade=qtd,
                        preco_unitario=produto.preco,
                    )

                cupons_pedido = [
                    cupons_map[(vend_user, codigo)]
                    for vend_user, codigo in pedido_cfg['cupons']
                ]
                if cupons_pedido:
                    pedido.cupons.set(cupons_pedido)

                pedido.finalizar()

                # Distribui as datas de finalização dentro do mês atual (ou mês anterior)
                # para que o gráfico do dashboard já comece preenchido.
                if pedido_cfg['no_mes_atual']:
                    data_pedido = inicio_mes + intervalo_mes * pedido_cfg['fracao_mes']
                else:
                    data_pedido = agora - timedelta(days=pedido_cfg['dias_atras'])

                Pedido.objects.filter(pk=pedido.pk).update(
                    criado_em=data_pedido,
                    finalizado_em=data_pedido,
                )
                resumo['pedidos_criados'] += 1

        return resumo

    def _imprimir_resumo(self, resumo):
        total_criados = (
            int(resumo['admin_criado'])
            + resumo['vendedores_criados']
            + resumo['clientes_criados']
            + resumo['produtos_criados']
            + resumo['cupons_criados']
            + resumo['pedidos_criados']
        )
        if total_criados > 0:
            self.stdout.write(
                self.style.SUCCESS(
                    '>> Banco populado com sucesso: '
                    f"{resumo['vendedores_criados']} vendedor(es), "
                    f"{resumo['clientes_criados']} cliente(s), "
                    f"{resumo['produtos_criados']} produto(s), "
                    f"{resumo['cupons_criados']} cupom(ns) e "
                    f"{resumo['pedidos_criados']} pedido(s) criado(s)."
                )
            )
        else:
            self.stdout.write(
                '>> Dados de demonstracao ja existentes no banco (nenhuma duplicacao criada).'
            )

    def _imprimir_credenciais(self):
        linha = '=' * 72
        sublinha = '-' * 72

        self.stdout.write('')
        self.stdout.write(linha)
        self.stdout.write('  CREDENCIAIS DE ACESSO — MINI E-COMMERCE (DADOS DE DEMONSTRACAO)')
        self.stdout.write(linha)
        self.stdout.write(f"  {'PERFIL':<14} {'USUARIO':<14} {'SENHA':<14} {'DETALHES'}")
        self.stdout.write(sublinha)

        for v in VENDEDORES_SEED:
            self.stdout.write(
                f"  {'Vendedor':<14} {v['username']:<14} {v['password']:<14} Loja: {v['loja_nome']}"
            )

        for c in CLIENTES_SEED:
            nome = f"{c['first_name']} {c['last_name']}".strip()
            self.stdout.write(
                f"  {'Cliente':<14} {c['username']:<14} {c['password']:<14} {nome} ({c['email']})"
            )

        self.stdout.write(
            f"  {'Admin':<14} {ADMIN_SEED['username']:<14} {ADMIN_SEED['password']:<14} Painel /admin/"
        )

        self.stdout.write(sublinha)
        self.stdout.write('  Cupons ativos para testar no carrinho:')
        for v in VENDEDORES_SEED:
            codigos = ', '.join(
                f"{cp['codigo']} (-{int(cp['desconto_percentual'])}%)"
                for cp in v['cupons']
            )
            self.stdout.write(f"    - {v['loja_nome']}: {codigos}")

        self.stdout.write(sublinha)
        self.stdout.write('  URLs principais:')
        self.stdout.write('    - Vitrine / Loja:       http://localhost:8000/')
        self.stdout.write('    - Login:                http://localhost:8000/entrar/')
        self.stdout.write('    - Dashboard Vendedor:   http://localhost:8000/vendedor/dashboard/')
        self.stdout.write('    - Painel Admin:         http://localhost:8000/admin/')
        self.stdout.write(linha)
        self.stdout.write('')
