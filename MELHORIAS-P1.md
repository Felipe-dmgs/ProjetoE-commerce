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
aplicar o desconto só sobre os itens daquele vendedor.

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
| 1 | Pedidos vinculados ao usuário | Pendente |
| 2 | Cupom exclusivo do vendedor | Pendente |
| 3 | Estoque acumulado e baixa atômica | Pendente |
| 4 | Carrinho preservado no login | Pendente |
| 5 | Limpeza de código e README | Pendente |