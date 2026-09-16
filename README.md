# Mini E-commerce — Projeto Django (Entrega 1)

Projeto acadêmico: **Mini E-commerce**, feito em Django + Bootstrap + um pouco de JS.

## Entidades
- **Vendedor**
- **Produto**
- **Pedido**
- **ItemPedido** (o "Item" pedido no enunciado)
- **Cupom**

## Escopo desta entrega (P1)
- Carrinho/Pedido com **cálculo de total** (subtotal - desconto de cupom).
- **Baixa de estoque** automática ao finalizar o pedido.

Todo o código está comentado explicando o que cada parte faz.

## Como rodar com Docker (recomendado)

O projeto sobe em dois containers, orquestrados pelo `docker-compose.yml`:
- **db**: PostgreSQL 16, com `healthcheck` via `pg_isready`.
- **web**: o projeto Django, servido pelo **Gunicorn** (não usamos o
  `runserver` em produção). Tem `healthcheck` batendo no endpoint
  `/healthz/`, que testa a conexão real com o banco.

O container `web` só sobe **depois** que o `db` estiver `healthy`
(`depends_on: condition: service_healthy` no compose) — ou seja, o app
depende do banco estar de pé e aceitando conexões, não só do container ter
"iniciado".

O arquivo `entrypoint.sh` (rodado automaticamente ao iniciar o container
`web`) faz, nessa ordem: espera o Postgres responder → `makemigrations` →
`migrate` → `collectstatic` → sobe o `gunicorn`.

### Passo a passo

1. (Opcional) copie e ajuste as variáveis de ambiente:
   ```bash
   cp .env.example .env
   ```
   Um `.env` padrão já vem incluso no projeto, então isso é só necessário se
   você quiser trocar usuário/senha do banco ou a `SECRET_KEY`.

2. Suba os containers:
   ```bash
   docker compose up --build
   ```

3. Acompanhe os logs até ver o Gunicorn subir (`Booting worker...`). Você
   pode checar a saúde dos containers com:
   ```bash
   docker compose ps
   ```
   A coluna `STATUS` deve mostrar `healthy` para os dois serviços.

4. Acesse:
   - Loja: http://localhost:8000/
   - Admin: http://localhost:8000/admin/
   - Healthcheck: http://localhost:8000/healthz/

5. Crie um super usuário (o container `web` já está rodando):
   ```bash
   docker compose exec web python manage.py createsuperuser
   ```

6. Para parar:
   ```bash
   docker compose down
   ```
   Para apagar também os dados do banco (volume do Postgres):
   ```bash
   docker compose down -v
   ```

### Arquivos do Docker

```
Dockerfile          -> como construir a imagem do container "web" (Django + Gunicorn)
entrypoint.sh        -> script rodado ao iniciar o container: migrations + collectstatic + gunicorn
docker-compose.yml   -> orquestra os containers "db" (Postgres) e "web" (Django)
.env.example         -> modelo de variáveis de ambiente (copie para .env)
.dockerignore         -> arquivos que NÃO devem ir para dentro da imagem Docker
```

## Como rodar sem Docker (ambiente local com venv)

Sem Docker, você precisa ter um **PostgreSQL rodando na sua máquina** (o
projeto não usa mais SQLite por padrão, já que passamos a usar Postgres em
todo lugar — veja o comentário em `config/settings.py` caso queira voltar a
usar SQLite rapidamente para testes).

1. Crie e ative um ambiente virtual:
   ```bash
   python -m venv venv
   source venv/bin/activate      # Linux/Mac
   venv\Scripts\activate         # Windows
   ```

2. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```

3. Exporte as variáveis de conexão com o seu Postgres local (ajuste os
   valores conforme sua instalação; `DATABASE_HOST=localhost` neste caso):
   ```bash
   export DATABASE_HOST=localhost
   export DATABASE_NAME=ecommerce
   export DATABASE_USER=ecommerce
   export DATABASE_PASSWORD=ecommerce
   ```

4. Crie as tabelas no banco de dados:
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

5. Crie um super usuário para acessar o admin:
   ```bash
   python manage.py createsuperuser
   ```

6. Rode o servidor:
   ```bash
   python manage.py runserver
   ```

7. Acesse:
   - Loja: http://127.0.0.1:8000/
   - Admin: http://127.0.0.1:8000/admin/

## Cadastrando dados de teste

Como ainda não há tela de cadastro de produtos (isso é lógica de "admin da
loja", fora do escopo do carrinho), use o **painel /admin/** para criar:

1. Um **Vendedor** (nome + e-mail).
2. Alguns **Produtos**, ligados a esse vendedor, com preço e estoque.
3. (Opcional) Um **Cupom**, com código, percentual de desconto e validade
   futura, para testar o campo de cupom no carrinho.

Depois disso, é só acessar a loja, adicionar produtos ao carrinho, aplicar
um cupom (se quiser) e finalizar o pedido — o estoque do produto será
reduzido automaticamente.

## Estrutura do projeto

```
ecommerce_projeto/
├── config/             -> configurações gerais do Django (settings, urls raiz)
├── loja/               -> app principal com toda a lógica do e-commerce
│   ├── models.py       -> entidades (Produto, Vendedor, Pedido, ItemPedido, Cupom)
│   ├── cart.py          -> classe Carrinho (liga a sessão do navegador a um Pedido)
│   ├── views.py         -> lógica das páginas (vitrine, carrinho, checkout, healthcheck)
│   ├── forms.py         -> formulários (quantidade, cupom, dados do cliente)
│   ├── urls.py          -> rotas do app
│   ├── health_urls.py   -> rota do endpoint /healthz/ (usado pelo Docker)
│   ├── admin.py         -> registro das entidades no painel administrativo
│   ├── templates/loja/  -> HTML (Bootstrap)
│   └── static/loja/     -> CSS e JS
├── manage.py
├── Dockerfile           -> build da imagem do container "web" (Django + Gunicorn)
├── entrypoint.sh        -> migrations + collectstatic + gunicorn, ao iniciar o container
├── docker-compose.yml   -> orquestra "db" (Postgres) e "web" (Django), com healthcheck
├── .env.example         -> modelo de variáveis de ambiente
└── requirements.txt
```

## Próximos passos (fora do escopo desta entrega, ver P2 do enunciado)
- Marketplace multi-vendedor com área própria para cada vendedor.
- Dashboard administrativo customizado.
- API com Django REST Framework (DRF).
