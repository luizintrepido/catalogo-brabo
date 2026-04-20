"""
Sistema de scraping de veiculos com sincronizacao completa.

- Adiciona carros novos
- Atualiza preco/km dos existentes
- REMOVE do Drive os carros que saíram dos sites

Uso:
  python main.py                    # sincroniza os dois sites
  python main.py --site reautov     # so ReAuto
  python main.py --site recar       # so Recar
  python main.py --no-drive         # salva localmente (sem Drive)
  python main.py --json-only        # so regenera vehicles.json do Drive
  python main.py --no-push          # nao envia para GitHub
"""

import argparse
import importlib
import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path

import config
from drive_uploader import DriveUploader
from push_to_github import push_vehicles_json

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("scraping.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

WHATSAPP = "5513991575019"


# ─── HELPERS ──────────────────────────────────────────────────────────────────

def sanitize_folder_name(name: str) -> str:
    for ch in r'\/:*?"<>|':
        name = name.replace(ch, "_")
    return name.strip()[:100]


def extract_id_from_folder_name(folder_name: str) -> str:
    """'Honda WR-V 2018 [970817]' -> '970817'"""
    m = re.search(r'\[([^\]]+)\]', folder_name)
    return m.group(1) if m else ""


# ─── PROCESSAMENTO ────────────────────────────────────────────────────────────

def process_car(car: dict, uploader, car_folder_id: str | None,
                local_folder: Path | None, scraper) -> list:
    """Salva info.json e faz upload das fotos. Retorna lista de Drive file IDs."""
    foto_ids = []

    info_json = json.dumps(car, ensure_ascii=False, indent=2)
    if uploader and car_folder_id:
        uploader.upload_text(info_json, "info.json", car_folder_id, mime_type="application/json")
    if local_folder:
        local_folder.mkdir(parents=True, exist_ok=True)
        (local_folder / "info.json").write_text(info_json, encoding="utf-8")

    fotos = car.get("fotos", [])
    if not fotos:
        logger.warning(f"  Nenhuma foto para: {car.get('modelo', car['id'])}")

    for j, img_url in enumerate(fotos, 1):
        filename = f"foto_{j:02d}.jpg"

        if uploader and car_folder_id:
            existing_id = uploader.get_file_id_in_folder(filename, car_folder_id)
            if existing_id:
                foto_ids.append(existing_id)
                logger.debug(f"  {filename} ja existe")
                continue

        img_data = scraper.download_image(img_url)
        if img_data is None:
            logger.warning(f"  Foto {j} nao pôde ser baixada: {img_url}")
            continue

        file_id = None
        if uploader and car_folder_id:
            file_id = uploader.upload_bytes(img_data, filename, car_folder_id, make_public=True)
        if local_folder:
            (local_folder / filename).write_bytes(img_data)

        if file_id:
            foto_ids.append(file_id)
            logger.info(f"  [{j}/{len(fotos)}] {filename} ok")

        time.sleep(config.DELAY_BETWEEN_PHOTOS)

    return foto_ids


def build_vehicle_entry(car: dict, foto_ids: list, folder_id: str) -> dict:
    return {
        "id":          car["id"],
        "loja":        car.get("loja", ""),
        "marca":       car.get("marca", ""),
        "modelo":      car.get("modelo", ""),
        "versao":      car.get("versao", ""),
        "ano":         car.get("ano", 0),
        "km":          car.get("km", 0),
        "preco":       car.get("preco", 0),
        "tipo":        car.get("tipo", "SUV"),
        "cor":         car.get("cor", ""),
        "cambio":      car.get("cambio", ""),
        "combustivel": car.get("combustivel", ""),
        "opcionais":   car.get("opcionais", []),
        "fotos_drive": foto_ids,
        "drive_folder": folder_id or "",
        "url_original": car.get("url", ""),
        "whatsapp":    WHATSAPP,
    }


# ─── SINCRONIZACAO ────────────────────────────────────────────────────────────

def sync_site(site_name: str, site_cfg: dict, uploader, root_folder_id: str,
              local_base: Path | None) -> list:
    """
    Sincroniza um site completo:
    - Remove carros que saíram do site
    - Adiciona/atualiza carros existentes
    Retorna lista de vehicle entries para vehicles.json
    """
    module = importlib.import_module(site_cfg["module"])
    scraper = getattr(module, site_cfg["class"])()

    # Pasta do site no Drive
    site_folder_id = None
    if uploader:
        site_folder_id = uploader.create_folder_if_not_exists(site_name, parent_id=root_folder_id)

    site_local = (local_base / sanitize_folder_name(site_name)) if local_base else None

    # ── 1. SCRAPING: coleta todos os carros atuais do site ──────────────────
    logger.info(f"Coletando lista de carros em {site_name}...")
    cars = scraper.get_all_cars()
    logger.info(f"{site_name}: {len(cars)} carros encontrados no site.")

    scraped_ids = {str(car["id"]) for car in cars}

    # ── 2. REMOCAO: deleta do Drive os que saíram do site ───────────────────
    if uploader and site_folder_id:
        existing_folders = uploader.list_subfolders(site_folder_id)
        existing_by_id = {}
        for folder in existing_folders:
            cid = extract_id_from_folder_name(folder["name"])
            if cid:
                existing_by_id[cid] = folder

        removed_ids = set(existing_by_id.keys()) - scraped_ids
        if removed_ids:
            logger.info(f"\n{len(removed_ids)} carro(s) REMOVIDO(S) do site — excluindo do Drive:")
            for cid in removed_ids:
                folder = existing_by_id[cid]
                logger.info(f"  Excluindo: {folder['name']}")
                try:
                    # Deleta todos os arquivos dentro da pasta
                    files = uploader.list_files_in_folder(folder["id"])
                    for f in files:
                        uploader.delete_file(f["id"])
                    # Deleta a pasta
                    uploader.delete_file(folder["id"])
                    logger.info(f"  OK: {folder['name']} excluido")
                except Exception as e:
                    logger.error(f"  Erro ao excluir {folder['name']}: {e}")
        else:
            logger.info("Nenhum carro removido do site.")

    # ── 3. PROCESSAMENTO: adiciona/atualiza cada carro ──────────────────────
    all_vehicles = []

    for i, car in enumerate(cars, 1):
        nome = f"{car.get('marca','')} {car.get('modelo', car['id'])}"
        folder_name = sanitize_folder_name(
            f"{car.get('marca','')} {car.get('modelo','')} {car.get('ano','')} [{car['id']}]"
        )
        logger.info(f"\n[{i}/{len(cars)}] {nome}")

        car_folder_id = None
        if uploader and site_folder_id:
            car_folder_id = uploader.create_folder_if_not_exists(folder_name, parent_id=site_folder_id)

        car_local = (site_local / folder_name) if site_local else None

        try:
            foto_ids = process_car(car, uploader, car_folder_id, car_local, scraper)
            entry = build_vehicle_entry(car, foto_ids, car_folder_id or "")
            all_vehicles.append(entry)
            logger.info(f"  {len(foto_ids)} foto(s)")
        except Exception as exc:
            logger.error(f"  Erro: {exc}", exc_info=True)

        time.sleep(config.DELAY_BETWEEN_CARS)

    return all_vehicles


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", choices=["reautov", "recar"])
    parser.add_argument("--no-drive",  action="store_true")
    parser.add_argument("--local-dir", default="output")
    parser.add_argument("--json-only", action="store_true",
                        help="So regenera vehicles.json do Drive sem scraping")
    parser.add_argument("--no-push",   action="store_true",
                        help="Nao envia para GitHub")
    args = parser.parse_args()

    # Modo: so gerar JSON a partir do Drive
    if args.json_only:
        from generate_json import generate_from_drive
        generate_from_drive(push=not args.no_push)
        return

    # Inicializa Drive
    uploader = None
    root_folder_id = None
    if not args.no_drive:
        logger.info("Conectando ao Google Drive...")
        uploader = DriveUploader()
        root_folder_id = uploader.create_folder_if_not_exists(config.DRIVE_ROOT_FOLDER)
        logger.info(f"Pasta raiz: '{config.DRIVE_ROOT_FOLDER}'")

    local_base = Path(args.local_dir) if args.no_drive else None

    # Seleciona sites
    sites_to_run = {k: v for k, v in config.SITES.items() if v["enabled"]}
    if args.site == "reautov":
        sites_to_run = {k: v for k, v in sites_to_run.items() if "reautov" in v["module"]}
    elif args.site == "recar":
        sites_to_run = {k: v for k, v in sites_to_run.items() if "recar" in v["module"]}

    all_vehicles = []

    for site_name, site_cfg in sites_to_run.items():
        logger.info(f"\n{'='*60}\nINICIANDO: {site_name}\n{'='*60}")

        try:
            vehicles = sync_site(
                site_name, site_cfg, uploader, root_folder_id, local_base
            )
            all_vehicles.extend(vehicles)
        except Exception as e:
            logger.error(f"Erro fatal em {site_name}: {e}", exc_info=True)

    # ── Aplica correcoes de marca/modelo/preco ───────────────────────────────
    try:
        from fix_vehicles_json import fix_vehicle
        all_vehicles = [fix_vehicle(v) for v in all_vehicles]
        logger.info("Marca/modelo/preco corrigidos.")
    except Exception as e:
        logger.warning(f"fix_vehicle nao aplicado: {e}")

    # ── Salva vehicles.json ──────────────────────────────────────────────────
    total_fotos = sum(len(v.get("fotos_drive", [])) for v in all_vehicles)
    vehicles_data = {
        "updated_at": datetime.now().isoformat(),
        "total":      len(all_vehicles),
        "vehicles":   all_vehicles,
    }
    json_path = Path("vehicles.json")
    json_path.write_text(json.dumps(vehicles_data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"\nvehicles.json salvo com {len(all_vehicles)} veiculos.")

    # ── Push GitHub ──────────────────────────────────────────────────────────
    if not args.no_push and not args.no_drive:
        try:
            push_vehicles_json(str(json_path))
        except Exception as e:
            logger.error(f"Erro ao enviar para GitHub: {e}")

    logger.info(f"\n{'='*60}")
    logger.info(f"CONCLUIDO! Carros: {len(all_vehicles)} | Fotos: {total_fotos}")
    logger.info(f"{'='*60}\n")


if __name__ == "__main__":
    main()
