"""
Funções utilitárias compartilhadas entre scrapers e geradores.
"""
import re


TIPO_MAP = {
    'HATCH': ['hb20', 'onix hatch', 'polo', 'gol', 'fit', 'yaris hatch', 'argo', 'mobi', 'up!',
              'kwid', 'sandero', 'fox', 'etios hatch', 'ka hatch', 'march', 'micra'],
    'SEDAN': ['civic', 'corolla', 'cruze sedan', 'city sedan', 'vento', 'virtus', 'cronos',
              'etios sedan', 'ka sedan', 'siena', 'logan', 'cobalt', 'jetta'],
    'SUV': ['compass', 'renegade', 'tracker', 'creta', 't-cross', 'nivus', 'kicks', 'wr-v',
            'tiggo', 'sportage', 'taos', 'pulse', 'fastback', 'territory', 'equinox', 'tucson',
            'hrv', 'hr-v', 'cx-5', 'duster', 'captur', 'ecosport', 'aircross', 'c4 cactus',
            'c4 picasso', 'q3', 'q5', 'tucson', 'ix35', 'x1', 'x3', 'x5', 'rav4', 'sw4',
            'hilux sw4', 'pajero', 'commander', 'grand cherokee', 'jeep cherokee'],
    'PICAPE': ['saveiro', 'montana', 'rampage', 'maverick', 'oroch', 'strada', 'hilux',
               'ranger', 's10', 'l200', 'amarok', 'frontier', 'toro', 'f-250'],
    'MOTO': ['cg ', 'cb ', 'xre', 'bros', 'fazer', 'lander', 'tenere', 'nxr', 'pcx',
             'biz', 'pop', 'factor'],
}


def determine_tipo(marca: str, modelo: str, versao: str = '') -> str:
    """Determina o tipo do veículo (SUV, HATCH, SEDAN, PICAPE, MOTO)."""
    texto = f"{modelo} {versao}".lower()
    for tipo, keywords in TIPO_MAP.items():
        if any(kw in texto for kw in keywords):
            return tipo
    return 'SUV'  # padrão


def parse_preco(preco_str: str) -> int:
    """'R$ 84.900' → 84900"""
    if not preco_str:
        return 0
    nums = re.sub(r'[^\d]', '', preco_str)
    try:
        val = int(nums)
        # Sanidade: entre 5k e 2M
        if 5_000 < val < 2_000_000:
            return val
        # Se veio com centavos (ex: 8490000 → 84900)
        if val > 2_000_000:
            return val // 100
    except Exception:
        pass
    return 0


def parse_km(km_str: str) -> int:
    """'40.351 km' → 40351"""
    if not km_str:
        return 0
    nums = re.sub(r'[^\d]', '', km_str)
    try:
        return int(nums)
    except Exception:
        return 0


def parse_ano(ano_str: str) -> int:
    """'2017/2018' → 2018  |  '2021' → 2021"""
    if not ano_str:
        return 0
    anos = re.findall(r'20\d{2}', ano_str)
    if not anos:
        return 0
    return int(anos[-1])  # usa o ano do modelo (segundo)


def split_nome_reautov(url: str) -> tuple[str, str, str]:
    """
    Extrai marca, modelo e versao da URL do reautoveiculos.
    Ex: /carros/honda/wr-v-exl-1-5-flexone-16v-5p-aut/2018/970817
    → ('Honda', 'WR-V', 'EXL 1.5 Flexone 16V 5p Aut')
    """
    try:
        parts = url.rstrip('/').split('/')
        # partes: ['', 'carros', 'honda', 'wr-v-exl-...', '2018', 'id']
        marca_slug = parts[-4] if len(parts) >= 5 else ''
        modelo_versao_slug = parts[-3] if len(parts) >= 5 else ''

        marca = _slug_to_title(marca_slug)

        # Separa modelo (primeira palavra com hífen) da versão
        slug_parts = modelo_versao_slug.split('-')
        # Tenta detectar onde termina o modelo e começa a versão
        modelo_parts = []
        versao_parts = []
        in_versao = False
        for p in slug_parts:
            if not in_versao and re.match(r'^\d', p):
                in_versao = True
            if in_versao:
                versao_parts.append(p)
            else:
                modelo_parts.append(p)

        modelo = ' '.join(modelo_parts).upper()
        versao = ' '.join(versao_parts).title()

        return marca, modelo, versao
    except Exception:
        return '', '', ''


def _slug_to_title(slug: str) -> str:
    """'gm-chevrolet' → 'GM Chevrolet'  |  'vw-volkswagen' → 'Volkswagen'"""
    MAP = {
        'gm-chevrolet': 'Chevrolet',
        'vw-volkswagen': 'Volkswagen',
        'caoa-chery-chery': 'Chery',
        'kia-motors': 'Kia',
        'ram': 'RAM',
        'bmw': 'BMW',
    }
    if slug in MAP:
        return MAP[slug]
    parts = [p.title() for p in slug.split('-') if p]
    return ' '.join(parts)
