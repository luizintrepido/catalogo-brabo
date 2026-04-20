"""
Corrige campos marca/modelo/versao/tipo que ficaram vazios no vehicles.json.
Extrai os dados a partir da url_original de cada veiculo.
Uso: python fix_vehicles_json.py
"""

import json
import re
import logging
from pathlib import Path
from utils import split_nome_reautov, determine_tipo, parse_ano

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Mapa: palavra-chave no slug -> (marca, modelo_oficial)
RECAR_MODEL_MAP = [
    # Chery
    ("tiggo-8",    "Chery",      "Tiggo 8"),
    ("tiggo-7",    "Chery",      "Tiggo 7"),
    ("tiggo-5x",   "Chery",      "Tiggo 5X"),
    ("tiggo-2",    "Chery",      "Tiggo 2"),
    ("tiggo",      "Chery",      "Tiggo"),
    ("arrizo",     "Chery",      "Arrizo"),
    # Honda
    ("hr-v",       "Honda",      "HR-V"),
    ("wr-v",       "Honda",      "WR-V"),
    ("fit",        "Honda",      "Fit"),
    ("civic",      "Honda",      "Civic"),
    ("city",       "Honda",      "City"),
    ("crv",        "Honda",      "CR-V"),
    ("cr-v",       "Honda",      "CR-V"),
    # Toyota
    ("corolla",    "Toyota",     "Corolla"),
    ("yaris",      "Toyota",     "Yaris"),
    ("hilux",      "Toyota",     "Hilux"),
    ("sw4",        "Toyota",     "SW4"),
    ("rav4",       "Toyota",     "RAV4"),
    # Volkswagen
    ("gol",        "Volkswagen", "Gol"),
    ("polo",       "Volkswagen", "Polo"),
    ("virtus",     "Volkswagen", "Virtus"),
    ("t-cross",    "Volkswagen", "T-Cross"),
    ("tcross",     "Volkswagen", "T-Cross"),
    ("taos",       "Volkswagen", "Taos"),
    ("jetta",      "Volkswagen", "Jetta"),
    ("saveiro",    "Volkswagen", "Saveiro"),
    ("up",         "Volkswagen", "Up!"),
    ("voyage",     "Volkswagen", "Voyage"),
    # Chevrolet
    ("onix",       "Chevrolet",  "Onix"),
    ("tracker",    "Chevrolet",  "Tracker"),
    ("cruze",      "Chevrolet",  "Cruze"),
    ("spin",       "Chevrolet",  "Spin"),
    ("s10",        "Chevrolet",  "S10"),
    ("montana",    "Chevrolet",  "Montana"),
    ("equinox",    "Chevrolet",  "Equinox"),
    ("cobalt",     "Chevrolet",  "Cobalt"),
    # Fiat
    ("pulse",      "Fiat",       "Pulse"),
    ("fastback",   "Fiat",       "Fastback"),
    ("argo",       "Fiat",       "Argo"),
    ("cronos",     "Fiat",       "Cronos"),
    ("strada",     "Fiat",       "Strada"),
    ("toro",       "Fiat",       "Toro"),
    ("mobi",       "Fiat",       "Mobi"),
    ("uno",        "Fiat",       "Uno"),
    ("doblo",      "Fiat",       "Doblo"),
    # Hyundai
    ("hb20",       "Hyundai",    "HB20"),
    ("creta",      "Hyundai",    "Creta"),
    ("tucson",     "Hyundai",    "Tucson"),
    ("ix35",       "Hyundai",    "ix35"),
    # Renault
    ("kwid",       "Renault",    "Kwid"),
    ("sandero",    "Renault",    "Sandero"),
    ("duster",     "Renault",    "Duster"),
    ("captur",     "Renault",    "Captur"),
    ("logan",      "Renault",    "Logan"),
    ("oroch",      "Renault",    "Oroch"),
    # Jeep
    ("compass",    "Jeep",       "Compass"),
    ("renegade",   "Jeep",       "Renegade"),
    ("commander",  "Jeep",       "Commander"),
    # Nissan
    ("kicks",      "Nissan",     "Kicks"),
    ("versa",      "Nissan",     "Versa"),
    ("frontier",   "Nissan",     "Frontier"),
    ("sentra",     "Nissan",     "Sentra"),
    # Kia
    ("sportage",      "Kia",         "Sportage"),
    ("stonic",        "Kia",         "Stonic"),
    ("cerato",        "Kia",         "Cerato"),
    ("soul",          "Kia",         "Soul"),
    # Mitsubishi
    ("eclipse",       "Mitsubishi",  "Eclipse Cross"),
    ("pajero",        "Mitsubishi",  "Pajero"),
    ("l200",          "Mitsubishi",  "L200"),
    ("asx",           "Mitsubishi",  "ASX"),
    # Ford
    ("ka",            "Ford",        "Ka"),
    ("ranger",        "Ford",        "Ranger"),
    ("maverick",      "Ford",        "Maverick"),
    ("ecosport",      "Ford",        "EcoSport"),
    ("territory",     "Ford",        "Territory"),
    # Peugeot / Citroen
    ("2008",          "Peugeot",     "2008"),
    ("208",           "Peugeot",     "208"),
    ("c4",            "Citroen",     "C4"),
    ("aircross",      "Citroen",     "Aircross"),
    # RAM
    ("rampage",       "RAM",         "Rampage"),
    # BMW
    ("x1",            "BMW",         "X1"),
    ("x3",            "BMW",         "X3"),
    # Audi
    ("q3",            "Audi",        "Q3"),
    ("q5",            "Audi",        "Q5"),
    ("a3",            "Audi",        "A3"),
    ("a4",            "Audi",        "A4"),
    # Land Rover
    ("range-rover",   "Land Rover",  "Range Rover Evoque"),
    ("range",         "Land Rover",  "Range Rover"),
    ("discovery",     "Land Rover",  "Discovery"),
    # Volkswagen (modelos extras)
    ("fox",           "Volkswagen",  "Fox"),
    ("spacefox",      "Volkswagen",  "SpaceFox"),
    ("crossfox",      "Volkswagen",  "CrossFox"),
    ("amarok",        "Volkswagen",  "Amarok"),
    # Nissan (modelos extras)
    ("march",         "Nissan",      "March"),
    # Toyota (modelos extras)
    ("etios",         "Toyota",      "Etios"),
    ("prius",         "Toyota",      "Prius"),
    # Subaru
    ("impreza",       "Subaru",      "Impreza"),
    ("xv",            "Subaru",      "XV"),
    # Volvo
    ("xc60",          "Volvo",       "XC60"),
    ("xc40",          "Volvo",       "XC40"),
]


def parse_recar_url(url: str):
    """
    /Veiculo/hb20-1.0-turbo-comfort-3764621
    => marca='Hyundai', modelo='HB20', versao='1.0 Turbo Comfort'
    """
    try:
        # Pega o slug apos /Veiculo/ ou /veiculo/
        m = re.search(r'/[Vv]eiculo[s]?/([^/?#]+)', url)
        if not m:
            return '', '', ''

        slug = m.group(1).lower()

        # Remove o ID numerico no final (ex: -3764621)
        slug = re.sub(r'-\d{5,}$', '', slug)

        marca, modelo = '', ''
        model_end = 0

        for keyword, m_marca, m_modelo in RECAR_MODEL_MAP:
            if slug.startswith(keyword) or f'-{keyword}' in slug:
                idx = slug.find(keyword)
                marca = m_marca
                modelo = m_modelo
                model_end = idx + len(keyword)
                break

        if not marca:
            # Fallback: usa as primeiras palavras como modelo
            parts = slug.split('-')
            modelo = ' '.join(parts[:2]).title()
            marca = 'N/D'
            model_end = len('-'.join(parts[:2]))

        # Versao = resto do slug apos o modelo
        versao_slug = slug[model_end:].lstrip('-')
        versao = versao_slug.replace('-', ' ').title().strip()

        return marca, modelo, versao
    except Exception as e:
        logger.warning(f"Erro parse_recar_url({url}): {e}")
        return '', '', ''


def parse_preco_str(val) -> int:
    """'R$ 135.900,00' ou 135900 ou '135900' -> 135900"""
    if isinstance(val, int):
        return val if val > 0 else 0
    if not val:
        return 0
    nums = re.sub(r'[^\d]', '', str(val))
    if not nums:
        return 0
    n = int(nums)
    # Se veio com centavos (13590000 -> 135900)
    if n > 2_000_000:
        n = n // 100
    return n if 1_000 < n < 5_000_000 else 0


def parse_km_str(val) -> int:
    """'40.351 km' ou 40351 ou '' -> inteiro"""
    if isinstance(val, int):
        return val
    if not val:
        return 0
    nums = re.sub(r'[^\d]', '', str(val))
    return int(nums) if nums else 0


def fix_vehicle(v: dict) -> dict:
    """Corrige marca/modelo/versao/tipo/preco/km/ano."""
    url = v.get('url_original', '')
    marca = v.get('marca', '').strip()
    modelo = v.get('modelo', '').strip()
    loja = v.get('loja', '')

    # --- Corrige marca/modelo ---
    if not (marca and modelo) or marca in ('N/D', 'ND', 'n/d'):
        if loja == 'REAUTO' and url:
            path = '/' + url.split('/', 3)[-1] if 'reautoveiculos' in url else url
            nova_marca, novo_modelo, nova_versao = split_nome_reautov(path)
        elif loja == 'RECAR' and url:
            nova_marca, novo_modelo, nova_versao = parse_recar_url(url)
        else:
            nova_marca, novo_modelo, nova_versao = '', '', ''

        if nova_marca:
            v['marca'] = nova_marca
        if novo_modelo:
            v['modelo'] = novo_modelo
        if nova_versao and not v.get('versao', '').strip():
            v['versao'] = nova_versao

    # --- Corrige ano ---
    if isinstance(v.get('ano'), str):
        v['ano'] = parse_ano(v['ano'])
    if not v.get('ano'):
        v['ano'] = 0

    # --- Corrige preco ---
    v['preco'] = parse_preco_str(v.get('preco'))

    # --- Corrige km ---
    v['km'] = parse_km_str(v.get('km'))

    # --- Recalcula tipo ---
    v['tipo'] = determine_tipo(
        v.get('marca', ''),
        v.get('modelo', ''),
        v.get('versao', '')
    )

    return v


def main():
    json_path = Path(__file__).parent / 'vehicles.json'
    if not json_path.exists():
        logger.error("vehicles.json nao encontrado! Execute generate_json.py primeiro.")
        return

    data = json.loads(json_path.read_text(encoding='utf-8'))
    vehicles = data.get('vehicles', [])

    fixed = 0
    for v in vehicles:
        marca_antes = v.get('marca', '')
        v = fix_vehicle(v)
        if v.get('marca') and not marca_antes:
            fixed += 1

    data['vehicles'] = vehicles
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    logger.info(f"Corrigidos: {fixed}/{len(vehicles)} veiculos")

    # Mostra amostra
    for v in vehicles[:5]:
        try:
            preco = int(v.get('preco') or 0)
        except Exception:
            preco = 0
        logger.info(f"  {v.get('marca')} {v.get('modelo')} {v.get('ano')} - R${preco:,.0f}")

    # Envia pro GitHub
    from push_to_github import push_vehicles_json
    push_vehicles_json(str(json_path))


if __name__ == '__main__':
    main()
