"""
Script de limpeza de fotos erradas no Google Drive.

O que faz:
  - Varre todas as pastas de carros no Drive
  - Remove fotos com menos de 40KB (logos, ícones, placeholders)
  - Remove fotos duplicadas (mesmo tamanho)
  - Exibe relatório do que foi removido

Uso:
  python cleanup_photos.py              # apenas analisa (dry-run)
  python cleanup_photos.py --delete     # apaga de verdade
"""

import argparse
import logging
from collections import defaultdict

from drive_uploader import DriveUploader
import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Tamanho mínimo para ser considerada uma foto real (em bytes)
MIN_PHOTO_SIZE = 40_000  # 40 KB


def cleanup(dry_run: bool = True):
    uploader = DriveUploader()

    logger.info("Conectando ao Google Drive...")
    root_folder_id = uploader.create_folder_if_not_exists(config.DRIVE_ROOT_FOLDER)

    # Lista pastas dos sites
    site_folders = uploader.list_subfolders(root_folder_id)
    logger.info(f"Sites encontrados: {[f['name'] for f in site_folders]}")

    total_removidos = 0
    total_mantidos = 0

    for site_folder in site_folders:
        logger.info(f"\nSite: {site_folder['name']}")
        car_folders = uploader.list_subfolders(site_folder["id"])
        logger.info(f"  {len(car_folders)} carros encontrados")

        for car_folder in car_folders:
            files = uploader.list_files_in_folder(car_folder["id"])
            fotos = [f for f in files if f["name"].startswith("foto_") and f["name"].endswith(".jpg")]

            if not fotos:
                continue

            # Detecta fotos a remover
            to_remove = []
            size_seen = {}

            for foto in sorted(fotos, key=lambda x: x["name"]):
                size = int(foto.get("size", 0))
                name = foto["name"]

                # Muito pequena → logo/ícone
                if size < MIN_PHOTO_SIZE:
                    to_remove.append((foto, f"muito pequena ({size/1024:.1f} KB)"))
                    continue

                # Duplicada por tamanho exato
                if size in size_seen:
                    to_remove.append((foto, f"duplicada de {size_seen[size]}"))
                    continue

                size_seen[size] = name

            # Exibe e remove
            if to_remove:
                logger.info(f"\n  {car_folder['name']}")
                for foto, motivo in to_remove:
                    logger.info(f"    REMOVER: {foto['name']} — {motivo}")
                    if not dry_run:
                        uploader.delete_file(foto["id"])
                    total_removidos += 1
            else:
                total_mantidos += len(fotos)

    logger.info(f"\n{'='*50}")
    if dry_run:
        logger.info(f"SIMULACAO (use --delete para apagar de verdade)")
    logger.info(f"Fotos que seriam/foram removidas : {total_removidos}")
    logger.info(f"Fotos mantidas                   : {total_mantidos}")
    logger.info(f"{'='*50}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Limpa fotos erradas no Google Drive")
    parser.add_argument("--delete", action="store_true", help="Apaga de verdade (sem --delete é apenas simulação)")
    args = parser.parse_args()

    cleanup(dry_run=not args.delete)
