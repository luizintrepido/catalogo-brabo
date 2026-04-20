"""
Envia o vehicles.json para o repositório GitHub do catálogo.

Requer:
  - pip install PyGithub
  - Token do GitHub configurado em config.py (GITHUB_TOKEN)
  - Repositório: luizintrepido/catalogo-brabo
"""

import json
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

GITHUB_REPO = "luizintrepido/catalogo-brabo"
GITHUB_FILE_PATH = "vehicles.json"


def push_vehicles_json(json_path: str = "vehicles.json"):
    """Envia vehicles.json para o GitHub."""
    import config

    if not hasattr(config, "GITHUB_TOKEN") or not config.GITHUB_TOKEN:
        logger.warning("GITHUB_TOKEN não configurado em config.py — pulando push.")
        return

    try:
        from github import Github
    except ImportError:
        logger.error("PyGithub não instalado. Execute: pip install PyGithub")
        return

    content = Path(json_path).read_text(encoding="utf-8")

    g = Github(config.GITHUB_TOKEN)
    repo = g.get_repo(GITHUB_REPO)

    try:
        existing = repo.get_contents(GITHUB_FILE_PATH)
        repo.update_file(
            path=GITHUB_FILE_PATH,
            message=f"Auto-update catalogo {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            content=content,
            sha=existing.sha,
        )
        logger.info(f"vehicles.json atualizado no GitHub!")
    except Exception:
        # Arquivo não existe ainda — cria
        repo.create_file(
            path=GITHUB_FILE_PATH,
            message="Criar vehicles.json inicial",
            content=content,
        )
        logger.info(f"vehicles.json criado no GitHub!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    push_vehicles_json()
