"""
Camada de EDICOES MANUAIS (overrides) do catalogo.

O catalogo e montado automaticamente pelo robo (Carmax Santos + Outlet Carmax).
Para que edicoes feitas no painel admin NAO sejam apagadas na proxima rodada,
elas ficam guardadas em `overrides.json` (no repo do site) e sao reaplicadas
toda vez — tanto pelo robo (main.py) quanto pelo proprio painel.

Formato de overrides.json:
{
  "<id_do_carro>": {
     "campos":   { "preco": 89900, "km": 50000, "versao": "...", "cor": "...",
                   "cambio": "...", "combustivel": "...", "opcionais": [...],
                   "descricao": "..." },
     "hidden":   true|false,          # esconde do catalogo (sem apagar)
     "destaque": true|false,          # marca como destaque (vai pro topo)
     "fotos":    ["url_ou_driveId", ...]   # ordem/conjunto de fotos (substitui)
  },
  "manual_1717...": {                  # carro cadastrado manualmente
     "_manual": true,
     "marca": "...", "modelo": "...", "versao": "...", "ano": 2020,
     "km": 0, "preco": 0, "tipo": "SUV", "cor": "", "cambio": "", "combustivel": "",
     "opcionais": [], "fotos": [...], "loja": "MANUAL", "destaque": false, "hidden": false
  }
}

Regras de aplicacao (idempotentes — aplicar 2x da o mesmo resultado):
- `campos`  -> sobrescreve apenas as chaves informadas
- `fotos`   -> substitui a lista de fotos do carro (fotos_drive)
- `hidden`  -> seta a flag (o catalogo/paginas filtram quem esta hidden)
- `destaque`-> seta a flag
- `_manual` -> carro novo, anexado ao catalogo
"""
import json
import logging
import urllib.request
from pathlib import Path

logger = logging.getLogger(__name__)

OVERRIDES_FILENAME = "overrides.json"
OVERRIDES_RAW_URL = (
    "https://raw.githubusercontent.com/luizintrepido/catalogo-brabo/master/overrides.json"
)

# Campos editaveis via painel
EDITABLE_FIELDS = [
    "preco", "km", "versao", "cor", "cambio", "combustivel", "opcionais", "descricao",
]


def load_overrides(prefer_remote: bool = True) -> dict:
    """Carrega overrides.json. Tenta o repo (fonte da verdade) e cai pro local."""
    if prefer_remote:
        try:
            req = urllib.request.Request(
                OVERRIDES_RAW_URL + "?t=0",
                headers={"User-Agent": "car-scraper-overrides"},
            )
            with urllib.request.urlopen(req, timeout=20) as r:
                data = json.loads(r.read().decode("utf-8"))
                if isinstance(data, dict):
                    logger.info(f"overrides.json carregado do repo ({len(data)} entradas)")
                    return data
        except Exception as e:
            logger.info(f"overrides.json remoto indisponivel ({e}); tentando local.")

    local = Path(OVERRIDES_FILENAME)
    if local.exists():
        try:
            return json.loads(local.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Falha lendo overrides.json local: {e}")
    return {}


def _manual_to_vehicle(oid: str, ov: dict) -> dict:
    """Converte uma entrada _manual em um veiculo no formato do catalogo."""
    return {
        "id": oid,
        "loja": ov.get("loja", "CARMAX"),
        "marca": ov.get("marca", ""),
        "modelo": ov.get("modelo", ""),
        "versao": ov.get("versao", ""),
        "ano": ov.get("ano", 0),
        "km": ov.get("km", 0),
        "preco": ov.get("preco", 0),
        "tipo": ov.get("tipo", "SUV"),
        "cor": ov.get("cor", ""),
        "cambio": ov.get("cambio", ""),
        "combustivel": ov.get("combustivel", ""),
        "opcionais": ov.get("opcionais", []),
        "descricao": ov.get("descricao", ""),
        "fotos_drive": ov.get("fotos", []),
        "drive_folder": "",
        "url_original": "",
        "whatsapp": "5513991575019",
        "destaque": bool(ov.get("destaque", False)),
        "hidden": bool(ov.get("hidden", False)),
        "added_at": ov.get("added_at", ""),
        "slug": ov.get("slug", ""),
        "_manual": True,
    }


def apply_overrides(vehicles: list, overrides: dict | None = None) -> list:
    """
    Aplica as edicoes manuais sobre a lista de veiculos.
    Retorna NOVA lista (inclui carros manuais e mantem a flag hidden).
    """
    if overrides is None:
        overrides = load_overrides()
    if not overrides:
        return vehicles

    out = []
    seen_ids = set()

    for v in vehicles:
        vid = str(v.get("id"))
        seen_ids.add(vid)
        ov = overrides.get(vid)
        if ov:
            v = dict(v)  # nao muta o original
            campos = ov.get("campos") or {}
            for k, val in campos.items():
                if k in EDITABLE_FIELDS:
                    v[k] = val
            if "fotos" in ov and isinstance(ov["fotos"], list):
                v["fotos_drive"] = ov["fotos"]
            if "destaque" in ov:
                v["destaque"] = bool(ov["destaque"])
            if "hidden" in ov:
                v["hidden"] = bool(ov["hidden"])
            if "em_preparacao" in ov:
                v["em_preparacao"] = bool(ov["em_preparacao"])
            if ov.get("loja"):
                v["loja"] = ov["loja"]
        out.append(v)

    # Carros manuais (nao vem das fontes)
    for oid, ov in overrides.items():
        if ov.get("_manual") and str(oid) not in seen_ids:
            out.append(_manual_to_vehicle(str(oid), ov))

    n_edit = sum(1 for k, ov in overrides.items() if not ov.get("_manual"))
    n_manual = sum(1 for ov in overrides.values() if ov.get("_manual"))
    n_hidden = sum(1 for v in out if v.get("hidden"))
    logger.info(
        f"Overrides aplicados: {n_edit} edicao(oes), {n_manual} manual(is), {n_hidden} escondido(s)."
    )
    return out


def photo_url(entry: str) -> str:
    """Resolve uma foto: URL completa (manual) ou ID do Drive."""
    if not entry:
        return ""
    if entry.startswith("http://") or entry.startswith("https://"):
        return entry
    return f"https://lh3.googleusercontent.com/d/{entry}=s800"
