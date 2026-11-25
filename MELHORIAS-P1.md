# Melhorias da P1

Revisão do MVP entregue na P1, feita antes de começar a P2. Cada item tem o
problema, onde ele aparece no código e o que será feito. Tudo isso vira
commit separado no histórico.

## 1. Pedidos não pertencem a ninguém

**Problema.** O `Pedido` guarda só `cliente_nome` e `cliente_email` digitados
no checkout e uma `sessao_chave`. Não existe vínculo com o usuário logado, então
o cliente não consegue consultar o que comprou e o vendedor não vê o que
vendeu.

**Onde.** `loja/models.py` (`Pedido`) e `loja/views.py` (`finalizar_pedido`).

**Correção.** Vincular o `Pedido` ao usuário que comprou, exigir login no
checkout e criar as telas "Meus pedidos" (cliente) e "Pedidos recebidos"
(vendedor, vendo só os itens dos próprios produtos).

## 2. Cupom sem dono e com desconto no total do carrinho

**Problema.** Qualquer vendedor logado cria cupons, e qualquer cliente usa o
cupom de qualquer vendedor. O `codigo` é `unique` no banco inteiro, então dois
vendedores não podem ter o mesmo código. Além disso, o desconto incide sobre
o carrinho inteiro, mesmo que ele misture produtos de vendedores diferentes.

**Onde.** `loja/models.py` (`Cupom`, `Pedido.calcular_desconto`) e
`loja/views.py` (`cadastrar_cupom`, `ver_carrinho`).

**Correção.** Adicionar `Cupom.vendedor`, preenchido a partir do usuário logado
e nunca do formulário. Trocar o `unique` global por unicidade por vendedor e
aplicar o desconto só sobre os itens daquele vendedor. Se vários vendedores
tiverem o mesmo código, o pedido aceita todos (`Pedido.cupons`, no máximo um
por vendedor), cada um descontando os itens do seu vendedor. Gravar também o
desconto no pedido ao finalizá-lo, para que editar ou desativar o cupom depois
não altere o total de pedidos antigos.

## 3. Estoque pode ser burlado e a baixa não é atômica

**Problema.** O estoque só é validado contra a quantidade de uma única
requisição. Adicionar o mesmo produto várias vezes, ou alterar a quantidade na
página do carrinho, passa do estoque sem erro. Além disso, o comentário de
`Pedido.finalizar()` diz proteger contra compras simultâneas, mas o método
não usa transação nem trava de linha. Duas compras ao mesmo tempo podem levar o
estoque abaixo de zero.

**Onde.** `loja/cart.py` (`adicionar`, `atualizar_quantidade`) e
`loja/models.py` (`Pedido.finalizar`).

**Correção.** Validar a quantidade acumulada contra o estoque e envolver a
finalização em `transaction.atomic()` com `select_for_update()` nos produtos.

## 4. Carrinho se perde ao fazer login

**Problema.** O carrinho é um `Pedido` ABERTO amarrado à `session_key`. O
Django troca essa chave ao autenticar, então quem monta o carrinho e só depois
entra (ou se cadastra) volta para um carrinho vazio.

**Onde.** `loja/cart.py` (`_obter_ou_criar_pedido_aberto`) e o fluxo de login e
cadastro em `loja/views.py`.

**Correção.** Associar o carrinho ao usuário quando houver login e migrar o
carrinho anônimo para ele no momento da autenticação.

## 5. Dívida técnica e documentação desatualizada

**Problema.** `views.py` repete imports (`Q`, `render`, `AdicionarAoCarrinhoForm`
e `Produto` aparecem duas vezes) e mistura o `healthcheck` com as views da
loja. O README ainda se apresenta como "Entrega 1", afirma que um `.env`
padrão vem incluso no projeto (ele fica fora do Git) e não descreve nada da P2.

**Onde.** `loja/views.py` e `README.md`.

**Correção.** Limpar os imports, mover o `healthcheck` para
`loja/health_urls.py` e reescrever o README com a estrutura atual, a API e o
roteiro de isolamento.

## Acompanhamento

| # | Melhoria | Situação |
|---|----------|----------|
| 1 | Pedidos vinculados ao usuário | Concluída (etapa 2) |
| 2 | Cupom exclusivo do vendedor | Concluída (etapa 1) |
| 3 | Estoque acumulado e baixa atômica | Concluída (etapa 2) |
| 4 | Carrinho preservado no login | Concluída (etapa 2) |
| 5 | Limpeza de código e README | Pendente |

## API REST

A API fica sob `/api/` e usa a **mesma sessão do login do site** (autenticação por sessão). Todas as respostas são JSON. Cada pessoa só enxerga os próprios dados: o registro de outra pessoa responde `404`, igual a um id que não existe.

| Recurso | Rotas | Quem usa | Métodos |
|---|---|---|---|
| Produtos | `/api/produtos/` e `/api/produtos/<id>/` | Vendedor | GET, POST / GET, PUT, PATCH, DELETE |
| Cupons | `/api/cupons/` e `/api/cupons/<id>/` | Vendedor | GET, POST / GET, PUT, PATCH, DELETE |
| Pedidos | `/api/pedidos/` e `/api/pedidos/<id>/` | Cliente e vendedor | somente GET |

Nos pedidos, o **cliente** vê seus pedidos finalizados; o **vendedor** vê os pedidos finalizados que contêm produtos dele, **com apenas os itens dele**.

### Códigos de status

| Código | Quando |
|---|---|
| 200 | Leitura ou atualização com sucesso |
| 201 | Criação com sucesso |
| 204 | Exclusão com sucesso (sem corpo) |
| 400 | Dados inválidos (corpo traz o erro de cada campo) |
| 403 | Sem login, sem token CSRF, ou logado sem perfil de vendedor |
| 404 | Registro inexistente **ou de outra pessoa** |
| 405 | Método não permitido (ex.: POST em `/api/pedidos/`) |

Sem login a resposta é `403` (e não `401`), porque a autenticação por sessão não envia o cabeçalho `WWW-Authenticate`.

### Usando com curl (autenticação por sessão + CSRF)

Leituras (GET) só precisam do cookie de sessão. **Escritas (POST, PUT, PATCH, DELETE) também exigem o token CSRF** no cabeçalho `X-CSRFToken`. O passo a passo:

```bash
BASE=http://localhost:8000
JAR=cookies.txt

# 1) Abre a tela de login só para receber o cookie "csrftoken"
curl -s -c $JAR $BASE/entrar/ -o /dev/null
CSRF=$(awk '$6=="csrftoken" {print $7}' $JAR)

# 2) Faz login pelo formulário do site (troque usuário e senha)
curl -s -b $JAR -c $JAR -X POST $BASE/entrar/ \
  -d "username=vendA" -d "password=SUA_SENHA" -d "csrfmiddlewaretoken=$CSRF" \
  -o /dev/null -w "%{http_code}\n"
# Esperado: 302 (login ok). Se vier 200, usuário ou senha estão errados.

# 3) IMPORTANTE: o login TROCA o token CSRF. Leia o cookie de novo
CSRF=$(awk '$6=="csrftoken" {print $7}' $JAR)
```

Daqui em diante, toda chamada leva `-b $JAR` (cookie de sessão). As de escrita levam também `-H "X-CSRFToken: $CSRF"` e `-H "Content-Type: application/json"`.

> Alternativa sem curl: a **Browsable API**. Abra `http://localhost:8000/api/produtos/` no navegador, clique em **Log in** (vai para `/api-auth/login/`) e use os formulários da própria página; o CSRF é tratado automaticamente.

### Produtos (conta de vendedor)

```bash
# Criar -> 201
curl -s -b $JAR -X POST $BASE/api/produtos/ \
  -H "X-CSRFToken: $CSRF" -H "Content-Type: application/json" \
  -d '{"nome": "Caneca", "descricao": "Caneca de ceramica", "preco": "25.90", "estoque": 10}'
```
```json
{"id": 1, "vendedor": 1, "nome": "Caneca", "descricao": "Caneca de ceramica",
 "preco": "25.90", "estoque": 10, "ativo": true, "imagem": null,
 "criado_em": "2026-11-24T20:15:03.123456-03:00"}
```
Repare que o corpo enviado não tem `vendedor`: o dono vem do login. Se ele for enviado, é ignorado.

```bash
# Listar (só os produtos do vendedor logado) -> 200
curl -s -b $JAR $BASE/api/produtos/

# Ver um -> 200
curl -s -b $JAR $BASE/api/produtos/1/

# Atualizar parte -> 200
curl -s -b $JAR -X PATCH $BASE/api/produtos/1/ \
  -H "X-CSRFToken: $CSRF" -H "Content-Type: application/json" \
  -d '{"estoque": 25}'

# Dados inválidos -> 400
curl -s -b $JAR -X POST $BASE/api/produtos/ \
  -H "X-CSRFToken: $CSRF" -H "Content-Type: application/json" \
  -d '{"nome": "Ruim", "preco": "0", "estoque": -1}'
```
```json
{"preco": ["Certifique-se de que este valor seja maior ou igual a 0.01."],
 "estoque": ["Certifique-se de que este valor seja maior ou igual a 0."]}
```

```bash
# Excluir -> 204 (sem corpo)
curl -s -b $JAR -X DELETE $BASE/api/produtos/1/ \
  -H "X-CSRFToken: $CSRF" -o /dev/null -w "%{http_code}\n"
```
Um produto que **já foi vendido** (ou está em algum carrinho) não pode ser excluído: a resposta é `400` com `{"detail": "Este produto não pode ser excluído porque já consta em pedidos ou carrinhos. Desative-o (ativo=false) em vez de excluir."}`. Nesse caso use `PATCH` com `{"ativo": false}`.

Para enviar a **imagem** do produto, use `multipart/form-data` em vez de JSON: `curl -b $JAR -X POST $BASE/api/produtos/ -H "X-CSRFToken: $CSRF" -F nome=Caneca -F preco=25.90 -F estoque=10 -F imagem=@caneca.jpg`.

### Cupons (conta de vendedor)

```bash
# Criar -> 201 (o código é guardado em maiúsculas)
curl -s -b $JAR -X POST $BASE/api/cupons/ \
  -H "X-CSRFToken: $CSRF" -H "Content-Type: application/json" \
  -d '{"codigo": "promo10", "desconto_percentual": "10", "validade": "2027-12-31"}'
```
```json
{"id": 1, "vendedor": 1, "codigo": "PROMO10", "desconto_percentual": "10.00",
 "validade": "2027-12-31", "ativo": true}
```

Erros de validação (todos `400`), as mesmas regras do formulário do site:

```bash
# Código repetido (sem diferenciar maiúsculas) -> {"codigo": ["Você já possui um cupom com este código."]}
curl -s -b $JAR -X POST $BASE/api/cupons/ -H "X-CSRFToken: $CSRF" -H "Content-Type: application/json" \
  -d '{"codigo": "Promo10", "desconto_percentual": "5", "validade": "2027-12-31"}'

# Desconto fora de 0,01 a 100 -> {"desconto_percentual": ["Certifique-se de que este valor seja menor ou igual a 100."]}
curl -s -b $JAR -X POST $BASE/api/cupons/ -H "X-CSRFToken: $CSRF" -H "Content-Type: application/json" \
  -d '{"codigo": "GRANDE", "desconto_percentual": "150", "validade": "2027-12-31"}'

# Validade no passado -> {"validade": ["A data de validade não pode ser no passado."]}
curl -s -b $JAR -X POST $BASE/api/cupons/ -H "X-CSRFToken: $CSRF" -H "Content-Type: application/json" \
  -d '{"codigo": "VELHO", "desconto_percentual": "5", "validade": "2020-01-01"}'
```
(Os textos de erro de desconto, preço e estoque vêm do DRF e podem variar um pouco.)

Listar, ver, `PATCH`, `PUT` e `DELETE` funcionam como em produtos, em `/api/cupons/` e `/api/cupons/<id>/`.

### Pedidos (somente leitura)

```bash
# Listar -> 200
curl -s -b $JAR $BASE/api/pedidos/

# Ver um -> 200
curl -s -b $JAR $BASE/api/pedidos/7/

# Escrever não é permitido -> 405
curl -s -b $JAR -X POST $BASE/api/pedidos/ -H "X-CSRFToken: $CSRF" -H "Content-Type: application/json" -d '{}'
```

Resposta para um **cliente** (todos os itens e os totais):
```json
{"id": 7, "status": "FINALIZADO", "cliente_nome": "Ana", "cliente_email": "ana@email.com",
 "criado_em": "2026-11-24T20:30:00-03:00", "finalizado_em": "2026-11-24T20:31:10-03:00",
 "itens": [
   {"id": 12, "produto": 1, "produto_nome": "Caneca", "quantidade": 2, "preco_unitario": "25.90", "subtotal": "51.80"},
   {"id": 13, "produto": 5, "produto_nome": "Camiseta", "quantidade": 1, "preco_unitario": "50.00", "subtotal": "50.00"}
 ],
 "subtotal": "101.80", "desconto": "5.18", "total": "96.62"}
```

Resposta para um **vendedor** (só os itens dele e o subtotal deles; sem desconto nem total do pedido inteiro):
```json
{"id": 7, "status": "FINALIZADO", "cliente_nome": "Ana", "cliente_email": "ana@email.com",
 "criado_em": "2026-11-24T20:30:00-03:00", "finalizado_em": "2026-11-24T20:31:10-03:00",
 "itens": [
   {"id": 12, "produto": 1, "produto_nome": "Caneca", "quantidade": 2, "preco_unitario": "25.90", "subtotal": "51.80"}
 ],
 "subtotal": "51.80"}
```

### Isolamento e permissões

```bash
# Registro de OUTRO vendedor (ou id inexistente) -> 404, mesma resposta nos dois casos
curl -s -i -b $JAR $BASE/api/produtos/999/
# {"detail": "Não encontrado."}

# Sem login -> 403
curl -s -i $BASE/api/produtos/
# {"detail": "As credenciais de autenticação não foram fornecidas."}

# Logado como CLIENTE (sem perfil de vendedor) em produtos ou cupons -> 403
# {"detail": "Esta API é exclusiva para contas de Vendedor."}

# Escrita sem o cabeçalho X-CSRFToken -> 403
curl -s -b $JAR -X POST $BASE/api/produtos/ -H "Content-Type: application/json" -d '{"nome": "X", "preco": "1", "estoque": 1}'
# {"detail": "CSRF Failed: CSRF token missing."}
```