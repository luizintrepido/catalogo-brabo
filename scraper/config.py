"""Config para GitHub Actions — valores sensiveis vem de env vars."""
import os

DRIVE_ROOT_FOLDER       = "Estoque Veiculos"
GOOGLE_CREDENTIALS_FILE = "credentials.json"
GOOGLE_TOKEN_FILE       = "token.json"
GITHUB_TOKEN            = os.environ.get("CATALOG_GITHUB_TOKEN", "")
DELAY_BETWEEN_CARS      = 1.5
DELAY_BETWEEN_PAGES     = 1.0
DELAY_BETWEEN_PHOTOS    = 0.3
MAX_PAGES               = 50
REQUEST_TIMEOUT         = 30

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
}
SITES = {
    "ReAuto Veiculos":  {"enabled": True, "module": "scrapers.reautoveiculos",  "class": "ReautoVeiculosScraper"},
    "Recar Automarcas": {"enabled": True, "module": "scrapers.recarautomarcas", "class": "RecarAutomarcasScraper"},
}
