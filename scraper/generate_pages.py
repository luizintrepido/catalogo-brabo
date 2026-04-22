"""
Gera paginas HTML individuais por carro em /carros/{id}.html
Cada pagina tem Open Graph meta tags (foto, titulo, preco)
e redireciona automaticamente para o catalogo com o modal aberto.

Uso: python generate_pages.py
"""
import json
import logging
import os
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

CATALOG_URL  = "https://luizintrepido.github.io/catalogo-brabo"
WHATSAPP     = "5513991575019"
OUTPUT_DIR   = Path("carros")


def thumb_url(file_id: str) -> str:
    return f"https://drive.google.com/thumbnail?id={file_id}&sz=w600"


def fmt_preco(preco) -> str:
    try:
        return f"R$ {int(preco):,}".replace(",", ".")
    except Exception:
        return "Consultar"


def fmt_km(km) -> str:
    try:
        v = int(km)
        return f"{v:,} km".replace(",", ".") if v else ""
    except Exception:
        return ""


def gerar_pagina(v: dict) -> str:
    car_id   = v.get("id", "")
    marca    = v.get("marca", "")
    modelo   = v.get("modelo", "")
    versao   = v.get("versao", "") or ""
    ano      = v.get("ano", "")
    preco    = fmt_preco(v.get("preco", 0))
    km       = fmt_km(v.get("km", 0))
    fotos    = v.get("fotos_drive", [])

    titulo   = f"{marca} {modelo} {ano}".strip()
    subtitulo = versao[:80] if versao else ""
    descricao = f"{preco}"
    if km:
        descricao += f" · {km}"
    if subtitulo:
        descricao += f" · {subtitulo}"

    og_image = thumb_url(fotos[0]) if fotos else f"{CATALOG_URL}/og-default.jpg"
    redirect  = f"{CATALOG_URL}/#carro-{car_id}"

    wpp_msg  = f"Olá! Vi o {titulo} no catálogo e quero mais informações."
    wpp_link = f"https://wa.me/{WHATSAPP}?text={wpp_msg}"

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{titulo} — Catálogo Brabo</title>

  <!-- Open Graph (WhatsApp, Telegram, Facebook) -->
  <meta property="og:type"        content="website" />
  <meta property="og:site_name"   content="Catálogo Brabo" />
  <meta property="og:title"       content="{titulo}" />
  <meta property="og:description" content="{descricao}" />
  <meta property="og:image"       content="{og_image}" />
  <meta property="og:image:width" content="600" />
  <meta property="og:image:height" content="400" />
  <meta property="og:url"         content="{CATALOG_URL}/carros/{car_id}" />

  <!-- Twitter Card -->
  <meta name="twitter:card"        content="summary_large_image" />
  <meta name="twitter:title"       content="{titulo}" />
  <meta name="twitter:description" content="{descricao}" />
  <meta name="twitter:image"       content="{og_image}" />

  <!-- Redireciona para o catalogo com o modal aberto -->
  <meta http-equiv="refresh" content="0;url={redirect}" />
  <link rel="canonical" href="{redirect}" />

  <style>
    body {{
      margin: 0;
      font-family: 'Segoe UI', sans-serif;
      background: #0f0f0f;
      color: #f0f0f0;
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      text-align: center;
      padding: 20px;
    }}
    .card {{
      max-width: 420px;
    }}
    img {{
      width: 100%;
      border-radius: 12px;
      margin-bottom: 16px;
    }}
    h1 {{ font-size: 1.4rem; margin: 0 0 6px; color: #ff6b00; }}
    p  {{ color: #a0a0a0; margin: 4px 0; font-size: 0.9rem; }}
    .preco {{ font-size: 1.5rem; font-weight: 800; color: #ff6b00; margin: 12px 0; }}
    .btn {{
      display: inline-block;
      margin-top: 12px;
      padding: 12px 24px;
      background: #25d366;
      color: #fff;
      border-radius: 10px;
      text-decoration: none;
      font-weight: 700;
      font-size: 1rem;
    }}
    .btn-cat {{
      background: #ff6b00;
      margin-left: 10px;
    }}
    .loading {{ color: #a0a0a0; font-size: 0.85rem; margin-top: 16px; }}
  </style>
</head>
<body>
  <div class="card">
    <img src="{og_image}" alt="{titulo}" onerror="this.style.display='none'" />
    <h1>{titulo}</h1>
    <p>{subtitulo}</p>
    <div class="preco">{preco}</div>
    {f'<p>{km}</p>' if km else ''}
    <a class="btn" href="{wpp_link}">Quero esse carro!</a>
    <a class="btn btn-cat" href="{redirect}">Ver no catálogo</a>
    <p class="loading">Redirecionando para o catálogo...</p>
  </div>
  <script>
    setTimeout(() => {{ window.location.replace("{redirect}"); }}, 1500);
  </script>
</body>
</html>"""


def main(json_path: str = "vehicles.json", push: bool = True):
    data = json.loads(Path(json_path).read_text(encoding="utf-8"))
    vehicles = data.get("vehicles", [])

    OUTPUT_DIR.mkdir(exist_ok=True)

    gerados = 0
    ids_atuais = set()

    for v in vehicles:
        car_id = str(v.get("id", ""))
        if not car_id:
            continue
        ids_atuais.add(car_id)
        html = gerar_pagina(v)
        out_path = OUTPUT_DIR / f"{car_id}.html"
        out_path.write_text(html, encoding="utf-8")
        gerados += 1

    # Remove paginas de carros que nao existem mais
    removidos = 0
    for old_file in OUTPUT_DIR.glob("*.html"):
        if old_file.stem not in ids_atuais:
            old_file.unlink()
            removidos += 1
            logger.info(f"  Removida pagina obsoleta: {old_file.name}")

    logger.info(f"Paginas geradas: {gerados} | Removidas: {removidos}")

    if push:
        _push_pages(vehicles, removidos > 0)


def _push_pages(vehicles: list, had_removals: bool):
    """Envia todas as paginas HTML para o GitHub."""
    try:
        import config
        from github import Github, Auth, InputGitTreeElement

        auth = Auth.Token(config.GITHUB_TOKEN)
        g    = Github(auth=auth)
        repo = g.get_repo("luizintrepido/catalogo-brabo")
        branch = repo.default_branch
        master = repo.get_branch(branch)

        logger.info("Enviando paginas para o GitHub...")
        blobs = []

        for v in vehicles:
            car_id = str(v.get("id", ""))
            if not car_id:
                continue
            html_path = OUTPUT_DIR / f"{car_id}.html"
            if html_path.exists():
                content = html_path.read_text(encoding="utf-8")
                blob = repo.create_git_blob(content, "utf-8")
                blobs.append(InputGitTreeElement(
                    f"carros/{car_id}.html", "100644", "blob", sha=blob.sha
                ))

        if not blobs:
            logger.warning("Nenhuma pagina para enviar.")
            return

        base_tree = repo.get_git_tree(master.commit.sha, recursive=True)
        new_tree  = repo.create_git_tree(blobs, base_tree)
        new_commit = repo.create_git_commit(
            message=f"Auto-update: {len(blobs)} paginas de carros",
            tree=new_tree,
            parents=[repo.get_git_commit(master.commit.sha)],
        )
        repo.get_git_ref(f"heads/{branch}").edit(new_commit.sha)
        logger.info(f"OK! {len(blobs)} paginas enviadas para o GitHub.")

    except Exception as e:
        logger.error(f"Erro ao enviar paginas: {e}")


if __name__ == "__main__":
    main()
