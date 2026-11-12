# -*- coding: utf-8 -*-
"""
Altera dados do catalogo por linha de comando, de qualquer lugar.

Pra que isso existe: o Luiz precisa mudar preco pelo celular, pedindo pro
Claude. Pedir pro agente editar JSON na mao e perigoso (ele erra a estrutura,
esquece de recalcular o vehicles.json, nao regenera o feed do WhatsApp). Aqui a
regra fica num comando so, deterministico e conferivel.

Como o dado sobrevive: edicao manual NAO vai direto no vehicles.json, vai no
overrides.json. O robo le o overrides.json em toda rodada e reaplica por cima
do que raspou. Preco escrito aqui nao e apagado pela proxima atualizacao.

O que um comando faz, em ordem:
  1. git pull        (o admin.html tambem escreve no overrides.json; sem pull
                      voce sobrescreve a edicao feita pelo painel)
  2. overrides.json  grava o campo pedido
  3. vehicles.json   recalcula aplicando TODOS os overrides
  4. feed.xml        regenera, senao o catalogo do WhatsApp fica com o preco velho
  5. git push        publica (o GitHub Pages atualiza em ~1 minuto)

Uso:
    python alterar.py buscar "corolla"
    python alterar.py editar --busca "corolla cross" --preco 95000
    python alterar.py editar --id 2316685 --preco 399900 --km 28000
    python alterar.py editar --id 2316685 --ocultar
    python alterar.py editar --id 2316685 --preco 95000 --teste   # nao grava
    python alterar.py status

Saida: exit 0 = feito. exit 2 = a busca deu em mais de um carro (ou nenhum),
e os candidatos vao impressos pra voce repetir com --id.
"""
import argparse
import json
import subprocess
import sys
import unicodedata
from pathlib import Path

BASE = Path(__file__).parent
sys.path.insert(0, str(BASE))

VEHICLES = BASE / "vehicles.json"
OVERRIDES = BASE / "overrides.json"

# Campos de texto que podem ser editados direto pela linha de comando.
# Mesma lista do overrides.py e do admin.html: mudar aqui sem mudar la cria
# edicao que o robo ignora silenciosamente.
TEXTO = ["versao", "cor", "cambio", "combustivel", "descricao"]

# Limites de sanidade. Nao sao gosto pessoal: "--preco 95" quase sempre quer
# dizer 95 mil, e gravar 95 reais colocaria o carro no site a noventa e cinco
# reais. Na duvida o script recusa em vez de adivinhar.
PRECO_MIN = 1000
PRECO_MAX = 3000000
KM_MAX = 1500000


def _sem_acento(s: str) -> str:
    s = unicodedata.normalize("NFD", str(s or ""))
    return "".join(c for c in s if unicodedata.category(c) != "Mn").lower()


def carregar_json(caminho: Path, padrao):
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return padrao
    except Exception as e:
        sys.exit("Nao consegui ler %s: %s" % (caminho.name, e))


def lista_veiculos(dados):
    return dados.get("vehicles", dados) if isinstance(dados, dict) else dados


def nome(v: dict) -> str:
    partes = [v.get("marca"), v.get("modelo"), v.get("versao")]
    txt = " ".join(str(p).strip() for p in partes if p)
    ano = v.get("ano")
    return ("%s %s" % (txt, ano)).strip() if ano else txt


def preco_fmt(p) -> str:
    p = int(p or 0)
    return "R$ %s" % format(p, ",d").replace(",", ".") if p > 0 else "Sob consulta"


def km_fmt(k) -> str:
    return "%s km" % format(int(k or 0), ",d").replace(",", ".")


def git(*args, check=True):
    r = subprocess.run(["git"] + list(args), cwd=str(BASE),
                       capture_output=True, text=True)
    if check and r.returncode != 0:
        sys.exit("git %s falhou:\n%s" % (" ".join(args), r.stderr.strip()))
    return r


def buscar(veiculos, texto):
    """Carros que casam com o texto. Cada palavra tem que aparecer."""
    alvo = _sem_acento(texto)
    palavras = [p for p in alvo.split() if p]
    achados = []
    for v in veiculos:
        if str(v.get("id")) == texto.strip():
            return [v]
        campo = _sem_acento("%s %s %s %s %s" % (
            v.get("marca", ""), v.get("modelo", ""), v.get("versao", ""),
            v.get("ano", ""), v.get("loja", "")))
        if all(p in campo for p in palavras):
            achados.append(v)
    return achados


def mostrar(veiculos, titulo="Encontrei"):
    print("%s %d carro(s):" % (titulo, len(veiculos)))
    for v in veiculos:
        marcas = []
        if v.get("hidden"):
            marcas.append("OCULTO")
        if v.get("destaque"):
            marcas.append("DESTAQUE")
        print("  [%s] %-46s %-12s %-14s %s %s" % (
            v.get("id"), nome(v)[:46], v.get("loja", ""),
            preco_fmt(v.get("preco")), km_fmt(v.get("km")),
            ("  " + " ".join(marcas)) if marcas else ""))


def resolver(veiculos, args):
    """Devolve UM carro, ou morre explicando. Ambiguidade nunca vira chute."""
    if args.id:
        for v in veiculos:
            if str(v.get("id")) == str(args.id).strip():
                return v
        sys.exit("Nenhum carro com id %s no catalogo." % args.id)

    achados = buscar(veiculos, args.busca)
    if not achados:
        print("Nenhum carro casa com '%s'." % args.busca)
        sys.exit(2)
    if len(achados) > 1:
        mostrar(achados, "A busca '%s' deu em" % args.busca)
        print()
        print("Repita escolhendo um: --id <id>")
        sys.exit(2)
    return achados[0]


def validar(args):
    if args.preco is not None:
        if args.preco != 0 and not (PRECO_MIN <= args.preco <= PRECO_MAX):
            sys.exit("Preco %s fora do aceitavel (%s a %s, ou 0 pra 'sob "
                     "consulta'). Se quis dizer mil, escreva o valor cheio."
                     % (args.preco, PRECO_MIN, PRECO_MAX))
    if args.km is not None and not (0 <= args.km <= KM_MAX):
        sys.exit("Km %s fora do aceitavel (0 a %s)." % (args.km, KM_MAX))


def cmd_buscar(args):
    veiculos = lista_veiculos(carregar_json(VEHICLES, []))
    achados = buscar(veiculos, args.texto)
    if not achados:
        print("Nenhum carro casa com '%s'." % args.texto)
        return 2
    mostrar(achados)
    return 0


def cmd_status(args):
    veiculos = lista_veiculos(carregar_json(VEHICLES, []))
    ov = carregar_json(OVERRIDES, {})
    manuais = [k for k, o in ov.items() if o.get("_manual")]
    ocultos = [v for v in veiculos if v.get("hidden")]
    print("Catalogo: %d carro(s), %s em estoque." % (
        len(veiculos), preco_fmt(sum(int(v.get("preco") or 0) for v in veiculos))))
    print("Edicoes manuais guardadas: %d" % len(ov))
    print("  carros cadastrados na mao: %d" % len(manuais))
    print("  escondidos do site: %d" % len(ocultos))
    for v in ocultos:
        print("    [%s] %s" % (v.get("id"), nome(v)))
    return 0


def cmd_editar(args):
    validar(args)

    # O admin.html escreve no mesmo overrides.json. Sem pull, duas edicoes no
    # mesmo dia fazem a segunda apagar a primeira.
    if not args.teste and not args.sem_push:
        print("Sincronizando com o GitHub...")
        git("pull", "--rebase", "--autostash")

    dados = carregar_json(VEHICLES, [])
    veiculos = lista_veiculos(dados)
    if not veiculos:
        sys.exit("vehicles.json vazio ou ilegivel. Nao vou editar no escuro.")

    carro = resolver(veiculos, args)
    cid = str(carro.get("id"))
    ov = carregar_json(OVERRIDES, {})
    entrada = ov.get(cid) or {}
    campos = dict(entrada.get("campos") or {})

    mudancas = []

    if args.preco is not None:
        antes = int(carro.get("preco") or 0)
        if antes != args.preco:
            campos["preco"] = args.preco
            mudancas.append(("preco", preco_fmt(antes), preco_fmt(args.preco)))

    if args.km is not None:
        antes = int(carro.get("km") or 0)
        if antes != args.km:
            campos["km"] = args.km
            mudancas.append(("km", km_fmt(antes), km_fmt(args.km)))

    for campo in TEXTO:
        novo = getattr(args, campo, None)
        if novo is not None:
            antes = str(carro.get(campo) or "")
            if antes != novo:
                campos[campo] = novo
                mudancas.append((campo, antes or "(vazio)", novo or "(vazio)"))

    if campos:
        entrada["campos"] = campos

    if args.ocultar or args.mostrar_no_site:
        valor = bool(args.ocultar)
        if bool(carro.get("hidden")) != valor:
            entrada["hidden"] = valor
            mudancas.append(("no site", "oculto" if not valor else "visivel",
                             "oculto" if valor else "visivel"))

    if args.destaque or args.sem_destaque:
        valor = bool(args.destaque)
        if bool(carro.get("destaque")) != valor:
            entrada["destaque"] = valor
            mudancas.append(("destaque", str(not valor), str(valor)))

    print()
    print("Carro: %s" % nome(carro))
    print("  id %s  |  %s  |  %s  |  %s" % (
        cid, carro.get("loja", ""), preco_fmt(carro.get("preco")),
        km_fmt(carro.get("km"))))
    print()

    if not mudancas:
        print("Nada a mudar: os valores pedidos ja sao os atuais.")
        return 0

    print("Mudancas:")
    for campo, antes, depois in mudancas:
        print("  %-12s %s  ->  %s" % (campo, antes, depois))
    print()

    if args.teste:
        print("--teste: nada foi gravado.")
        return 0

    ov[cid] = entrada
    OVERRIDES.write_text(json.dumps(ov, ensure_ascii=False, indent=1),
                         encoding="utf-8")
    print("overrides.json gravado.")

    # vehicles.json recalculado a partir dos overrides. E idempotente: aplicar
    # duas vezes da o mesmo resultado, entao usar o proprio vehicles.json como
    # base e seguro (e e o que o admin.html faz).
    try:
        from overrides import apply_overrides
        finais = apply_overrides(veiculos, ov)
    except Exception as e:
        sys.exit("Nao consegui aplicar os overrides (%s). overrides.json ja "
                 "foi gravado; rode de novo depois de corrigir." % e)

    if isinstance(dados, dict):
        dados["vehicles"] = finais
        saida = dados
    else:
        saida = finais
    VEHICLES.write_text(json.dumps(saida, ensure_ascii=False, indent=1),
                        encoding="utf-8")
    print("vehicles.json recalculado (%d carros)." % len(finais))

    # Sem isso o site mostra o preco novo e o catalogo do WhatsApp continua
    # mostrando o velho. validate_images fica desligado porque foto nenhuma
    # mudou aqui, e validar as 1500 fotos levaria minutos.
    try:
        from generate_feed import generate_feed
        n = generate_feed(str(VEHICLES), str(BASE / "feed.xml"),
                          validate_images=False)
        print("feed.xml regenerado (%d itens)." % n)
    except Exception as e:
        print("! feed.xml NAO foi regenerado: %s" % e)
        print("  O site vai atualizar, o catalogo do WhatsApp nao.")

    if args.sem_push:
        print()
        print("--sem-push: arquivos alterados, nada publicado.")
        return 0

    resumo = "; ".join("%s: %s -> %s" % m for m in mudancas)
    git("add", "overrides.json", "vehicles.json", "feed.xml")
    if not git("diff", "--staged", "--quiet", check=False).returncode:
        print("Nada mudou nos arquivos. Nada a publicar.")
        return 0
    git("commit", "-m", "%s — %s" % (nome(carro), resumo))
    git("push")
    print()
    print("Publicado. O site atualiza em cerca de 1 minuto:")
    print("  https://luizintrepido.github.io/catalogo-brabo/")
    return 0


def main():
    ap = argparse.ArgumentParser(
        description="Altera dados do catalogo (preco, km, versao, visibilidade).")
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("buscar", help="procura carro por nome ou id")
    b.add_argument("texto")
    b.set_defaults(func=cmd_buscar)

    s = sub.add_parser("status", help="resumo do catalogo e das edicoes manuais")
    s.set_defaults(func=cmd_status)

    e = sub.add_parser("editar", help="muda um campo de um carro")
    alvo = e.add_mutually_exclusive_group(required=True)
    alvo.add_argument("--id", help="id exato do carro")
    alvo.add_argument("--busca", help="nome do carro (tem que achar so um)")
    e.add_argument("--preco", type=int, help="preco em reais (0 = sob consulta)")
    e.add_argument("--km", type=int)
    for campo in TEXTO:
        e.add_argument("--%s" % campo)
    vis = e.add_mutually_exclusive_group()
    vis.add_argument("--ocultar", action="store_true",
                     help="esconde do site sem apagar")
    vis.add_argument("--mostrar-no-site", action="store_true", dest="mostrar_no_site")
    des = e.add_mutually_exclusive_group()
    des.add_argument("--destaque", action="store_true", help="joga pro topo")
    des.add_argument("--sem-destaque", action="store_true", dest="sem_destaque")
    e.add_argument("--teste", action="store_true",
                   help="mostra o que faria, sem gravar nada")
    e.add_argument("--sem-push", action="store_true", dest="sem_push",
                   help="altera os arquivos sem publicar")
    e.set_defaults(func=cmd_editar)

    args = ap.parse_args()

    if args.cmd == "editar":
        pedidos = [args.preco, args.km] + [getattr(args, c) for c in TEXTO]
        flags = [args.ocultar, args.mostrar_no_site, args.destaque, args.sem_destaque]
        if all(p is None for p in pedidos) and not any(flags):
            sys.exit("Voce nao pediu nenhuma mudanca. Use --preco, --km, "
                     "--versao, --cor, --cambio, --combustivel, --descricao, "
                     "--ocultar, --mostrar-no-site, --destaque ou --sem-destaque.")

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
