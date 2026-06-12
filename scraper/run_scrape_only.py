"""
Executa scraping dos sites e mescla com vehicles.json existente,
preservando os IDs do Drive para fotos ja cadastradas.

Uso: python run_scrape_only.py
"""

import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

import config
from scrapers.reautoveiculos import ReautoVeiculosScraper
from scrapers.recarautomarcas import RecarAutomarcasScraper
from utils import parse_preco, parse_km, parse_ano

WHATSAPP = "5513991575019"

ROOT_VEHICLES_JSON = Path(__file__).parent.parent / "vehicles.json"


def scrape_all() -> list[dict]:
    scrapers = [
        ReautoVeiculosScraper(),
        RecarAutomarcasScraper(),
    ]
    all_cars = []
    for scraper in scrapers:
        logger.info(f"\n{'='*60}\nScraping: {scraper.SITE_NAME}\n{'='*60}")
        try:
            cars = scraper.get_all_cars()
            logger.info(f"{scraper.SITE_NAME}: {len(cars)} carros encontrados")
            all_cars.extend(cars)
        except Exception as e:
            logger.error(f"Erro em {scraper.SITE_NAME}: {e}", exc_info=True)
        time.sleep(1)
    return all_cars


def build_entry(car: dict, existing: dict | None) -> dict:
    foto_ids = (existing or {}).get("fotos_drive", [])
    drive_folder = (existing or {}).get("drive_folder", "")
    slug = (existing or {}).get("slug", "")
    added_at = (existing or {}).get("added_at", datetime.now().isoformat())

    return {
        "id":           car["id"],
        "loja":         car.get("loja", ""),
        "marca":        car.get("marca", ""),
        "modelo":       car.get("modelo", ""),
        "versao":       car.get("versao", ""),
        "ano":          car.get("ano", 0),
        "km":           car.get("km", 0),
        "preco":        car.get("preco", 0),
        "tipo":         car.get("tipo", "SUV"),
        "cor":          car.get("cor", ""),
        "cambio":       car.get("cambio", ""),
        "combustivel":  car.get("combustivel", ""),
        "opcionais":    car.get("opcionais", []),
        "fotos_drive":  foto_ids,
        "drive_folder": drive_folder,
        "url_original": car.get("url", ""),
        "whatsapp":     WHATSAPP,
        "slug":         slug,
        "added_at":     added_at,
    }


def main():
    # Carrega vehicles.json existente para preservar Drive IDs
    existing_by_id: dict[str, dict] = {}
    if ROOT_VEHICLES_JSON.exists():
        data = json.loads(ROOT_VEHICLES_JSON.read_text(encoding="utf-8"))
        for v in data.get("vehicles", []):
            existing_by_id[str(v["id"])] = v
        logger.info(f"Carregados {len(existing_by_id)} veiculos existentes do vehicles.json")

    # Scraping
    fresh_cars = scrape_all()

    # Aplica correcoes
    try:
        from fix_vehicles_json import fix_vehicle
        fresh_cars_fixed = []
        for car in fresh_cars:
            dummy_entry = build_entry(car, None)
            fixed = fix_vehicle(dummy_entry)
            # preserva dados originais do scraping
            for k in ("id", "loja", "km", "preco", "ano", "url", "opcionais", "cor", "cambio", "combustivel"):
                if k in car:
                    fixed[k] = car.get(k, fixed.get(k))
            fresh_cars_fixed.append(fixed)
        fresh_cars = fresh_cars_fixed
        logger.info("Correcoes de marca/modelo/preco aplicadas.")
    except Exception as e:
        logger.warning(f"fix_vehicle nao aplicado: {e}")

    # Mescla
    merged = []
    new_count = 0
    updated_count = 0
    for car in fresh_cars:
        car_id = str(car["id"])
        existing = existing_by_id.get(car_id)
        entry = build_entry(car, existing)
        if existing is None:
            new_count += 1
            entry["added_at"] = datetime.now().isoformat()
        else:
            updated_count += 1
        merged.append(entry)

    removed_count = len(existing_by_id) - updated_count
    logger.info(f"\nResultado: {len(merged)} veiculos total")
    logger.info(f"  Novos: {new_count}")
    logger.info(f"  Atualizados: {updated_count}")
    logger.info(f"  Removidos: {removed_count}")

    # Salva vehicles.json na raiz
    vehicles_data = {
        "updated_at": datetime.now().isoformat(),
        "total":      len(merged),
        "vehicles":   merged,
    }
    ROOT_VEHICLES_JSON.write_text(
        json.dumps(vehicles_data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    logger.info(f"vehicles.json salvo em {ROOT_VEHICLES_JSON}")

    return len(merged)


if __name__ == "__main__":
    total = main()
    logger.info(f"\nConcluido! {total} veiculos no catalogo.")
