"""
Regenera vehicles.json lendo os dados do Google Drive.
Útil para reconstruir o JSON sem rodar o scraper do zero.

Uso: python generate_json.py
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from drive_uploader import DriveUploader
from push_to_github import push_vehicles_json
import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

WHATSAPP = "5513991575019"


def generate_from_drive(push: bool = True):
    uploader = DriveUploader()
    root_folder_id = uploader.create_folder_if_not_exists(config.DRIVE_ROOT_FOLDER)
    site_folders = uploader.list_subfolders(root_folder_id)

    vehicles = []

    for site_folder in site_folders:
        loja = "RECAR" if "recar" in site_folder["name"].lower() else "REAUTO"
        car_folders = uploader.list_subfolders(site_folder["id"])
        logger.info(f"{site_folder['name']}: {len(car_folders)} carros")

        for car_folder in car_folders:
            try:
                files = uploader.list_files_in_folder(car_folder["id"])

                # Lê info.json
                info_file = next((f for f in files if f["name"] == "info.json"), None)
                info = {}
                if info_file:
                    raw = uploader.download_file_bytes(info_file["id"])
                    if raw:
                        info = json.loads(raw.decode("utf-8"))

                # Coleta IDs das fotos (ordenadas)
                fotos = sorted(
                    [f for f in files if f["name"].startswith("foto_") and f["name"].endswith(".jpg")],
                    key=lambda x: x["name"]
                )
                foto_ids = [f["id"] for f in fotos]

                # Torna fotos públicas (caso não sejam)
                for fid in foto_ids:
                    uploader.make_public(fid)

                entry = {
                    "id": info.get("id", car_folder["name"].split("[")[-1].rstrip("]")),
                    "loja": info.get("loja", loja),
                    "marca": info.get("marca", ""),
                    "modelo": info.get("modelo", ""),
                    "versao": info.get("versao", ""),
                    "ano": info.get("ano", 0),
                    "km": info.get("km", 0),
                    "preco": info.get("preco", 0),
                    "tipo": info.get("tipo", "SUV"),
                    "cor": info.get("cor", ""),
                    "cambio": info.get("cambio", ""),
                    "combustivel": info.get("combustivel", ""),
                    "opcionais": info.get("opcionais", []),
                    "fotos_drive": foto_ids,
                    "drive_folder": car_folder["id"],
                    "url_original": info.get("url", ""),
                    "whatsapp": WHATSAPP,
                }
                vehicles.append(entry)
                logger.info(f"  ok {entry['marca']} {entry['modelo']} — {len(foto_ids)} fotos")

            except Exception as e:
                logger.error(f"  Erro em {car_folder['name']}: {e}")

    data = {
        "updated_at": datetime.now().isoformat(),
        "total": len(vehicles),
        "vehicles": vehicles,
    }

    Path("vehicles.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"\nvehicles.json gerado com {len(vehicles)} veículos.")

    if push:
        push_vehicles_json("vehicles.json")


if __name__ == "__main__":
    generate_from_drive()
