# Catálogo Brabo — como alterar dados

Repo do site em https://luizintrepido.github.io/catalogo-brabo/
Branch de publicação: **master** (não `main`).

O Luiz pede alterações daqui pelo celular. Normalmente é preço.

## Regra número um

Use sempre o `alterar.py`. **Nunca edite `vehicles.json`, `overrides.json` ou
`feed.xml` na mão.**

Motivo: uma alteração de preço tem que tocar três arquivos e na ordem certa.
Editar só o `vehicles.json` faz o preço voltar sozinho na próxima rodada do
robô, e esquecer o `feed.xml` deixa o catálogo do WhatsApp com o preço velho.
O script faz tudo isso e publica.

## Como atender um pedido

```
python alterar.py buscar "corolla cross"
python alterar.py editar --id 2325393 --preco 129900
```

Primeiro `buscar`, depois `editar --id`. Não pule a busca: o `--id` é o único
jeito de ter certeza de qual carro é.

Dá pra usar `--busca` em vez de `--id`, mas se a busca achar mais de um carro o
script para com código 2 e lista os candidatos. Quando isso acontecer, **mostre
a lista pro Luiz e pergunte qual**. Nunca escolha por conta própria.

Campos aceitos: `--preco` `--km` `--versao` `--cor` `--cambio` `--combustivel`
`--descricao` `--ocultar` `--mostrar-no-site` `--destaque` `--sem-destaque`.

Outros comandos: `status` (resumo do catálogo), `--teste` (mostra o que faria
sem gravar), `--sem-push` (altera os arquivos sem publicar).

## Nunca invente dado

Preço, km, ano e versão vêm do Luiz ou do site da loja. Se ele não disse o
valor, pergunte. Não estime, não arredonde, não complete.

Preço é em reais, valor cheio: `--preco 129900`. O script recusa valor abaixo
de mil justamente porque "129" quase sempre quer dizer 129 mil. Se ele disser
"129 mil", escreva 129000.

`--preco 0` é válido e significa "sob consulta".

## O que não fazer aqui

Não rode o `scraper/`. Ele precisa de credenciais do Google Drive que não
existem nesta sessão, e a cópia dentro do repo está velha (abril/2026, sem
suporte a overrides). Quem atualiza o estoque é o PC do Luiz.

Não use `git add -A`. O `alterar.py` adiciona só os três arquivos que mudou, de
propósito.

## Como o dado sobrevive

`overrides.json` é a camada de edição manual. O robô lê esse arquivo do GitHub
em toda rodada e reaplica por cima do que raspou do site da loja. Então preço
alterado por aqui **não** é apagado pela próxima atualização de estoque.

O mesmo arquivo é escrito pelo painel `admin.html`. Por isso o `alterar.py` dá
`git pull` antes de mexer: sem isso, duas edições no mesmo dia fazem a segunda
apagar a primeira.

## Problema conhecido

A Action `atualizar_catalogo.yml` (diária, 11h) está **falhando todo dia** desde
no mínimo 04/11/2026. O token do Google Drive guardado nos secrets expirou
(`invalid_grant`). Além disso ela roda a cópia velha do scraper, que não conhece
overrides: se alguém consertar o token sem atualizar a cópia, a rodada vai
sobrescrever o `vehicles.json` sem reaplicar as edições manuais e os preços
editados somem do site.

Não conserte isso de improviso. Avise o Luiz.
