"""
Gera feed.xml para o Catálogo de Produtos do Meta (Facebook/Instagram)
a partir do vehicles.json do catalogo-brabo.

Formato: RSS 2.0 com namespace Google Merchant (g:)
URL do feed: https://luizintrepido.github.io/catalogo-brabo/feed.xml

Uso:
    python generate_feed.py
"""

import json
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from xml.dom import minidom

# ── Configurações ──────────────────────────────────────────────────────────────

WHATSAPP = "5513991575019"
BASE_URL  = "https://luizintrepido.github.io/catalogo-brabo"
FALLBACK_IMG = f"{BASE_URL}/em-preparacao.jpg"

# Mapeamento tipo → body_style para o catálogo Meta
BODY_STYLE = {
    "Hatch":     "Hatchback",
    "Sedan":     "Sedan",
    "SUV":       "SUV",
    "Utilitário": "Van",
    "Camionete": "Pickup",
    "Motos":     "Motorcycle",
}

# Mapeamento combustível
FUEL_MAP = {
    "Flex":      "Flex-fuel",
    "Gasolina":  "Gasoline",
    "Etanol":    "Gasoline",
    "Diesel":    "Diesel",
    "Elétrico":  "Electric",
    "Híbrido":   "Hybrid",
}

# Mapeamento câmbio
TRANS_MAP = {
    "Automático":   "Automatic",
    "Manual":       "Manual",
    "Automatizado": "Automated Manual",
    "CVT":          "CVT",
}


def drive_img(file_id: str) -> str:
    """Retorna URL pública estável de imagem do Google Drive."""
    return f"https://lh3.googleusercontent.com/d/{file_id}=s1080"


# Cache para não testar a mesma imagem 2x
_img_cache: dict = {}

def img_is_valid(file_id: str, timeout: int = 8) -> bool:
    """Testa se o link da imagem do Drive retorna uma imagem real (não HTML)."""
    if file_id in _img_cache:
        return _img_cache[file_id]
    url = drive_img(file_id)
    ok = False
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            ctype = r.headers.get("Content-Type", "")
            ok = (r.status == 200 and "image" in ctype)
    except Exception:
        ok = False
    _img_cache[file_id] = ok
    return ok


def first_valid_photo(fotos: list, validate: bool) -> tuple:
    """
    Retorna (foto_principal_url, fotos_extras_urls).
    Se validate=True, pula fotos quebradas e usa a primeira que funciona.
    """
    if not fotos:
        return FALLBACK_IMG, []

    if not validate:
        return drive_img(fotos[0]), [drive_img(f) for f in fotos[1:10]]

    # Encontrar índice da primeira foto válida
    validas = [f for f in fotos if img_is_valid(f)]
    if not validas:
        return FALLBACK_IMG, []
    return drive_img(validas[0]), [drive_img(f) for f in validas[1:10]]


def slug(v: dict) -> str:
    """Gera slug para a URL da página individual do carro."""
    marca  = v.get("marca", "").lower().replace(" ", "-")
    modelo = v.get("modelo", "").lower().replace(" ", "-")
    ano    = str(v.get("ano", ""))
    vid    = v.get("id", "")
    return f"{marca}-{modelo}-{ano}-{vid}"


def wa_link(v: dict) -> str:
    """Gera link WhatsApp pré-preenchido para o carro."""
    marca  = v.get("marca", "")
    modelo = v.get("modelo", "")
    ano    = v.get("ano", "")
    preco  = v.get("preco", 0)
    msg = (
        f"Oi Luiz! Vi o {marca} {modelo} {ano} "
        f"por R${preco:,.0f} no catálogo e quero saber as condições. CPF limpo"
    ).replace(",", ".")
    from urllib.parse import quote
    return f"https://api.whatsapp.com/send?phone={WHATSAPP}&text={quote(msg)}"


def generate_feed(vehicles_path: str = "vehicles.json",
                  output_path:   str = "feed.xml",
                  validate_images: bool = True) -> int:
    """
    Lê vehicles.json e grava feed.xml.
    validate_images=True testa cada foto e usa a primeira que funciona.
    Retorna número de itens gerados.
    """
    data = json.loads(Path(vehicles_path).read_text(encoding="utf-8"))
    vehicles = data.get("vehicles", data) if isinstance(data, dict) else data

    # Raiz RSS
    rss = ET.Element("rss", {
        "version": "2.0",
        "xmlns:g": "http://base.google.com/ns/1.0",
    })
    channel = ET.SubElement(rss, "channel")

    ET.SubElement(channel, "title").text       = "O Brabo das Vendas — Estoque de Veículos"
    ET.SubElement(channel, "link").text        = BASE_URL
    ET.SubElement(channel, "description").text = (
        "Estoque de veículos seminovos e usados — Recar Automarcas / Reauto Veículos. "
        "Laudo cautelar aprovado, garantia até 2 anos, financiamento facilitado."
    )
    ET.SubElement(channel, "lastBuildDate").text = (
        datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    )

    count = 0
    for v in vehicles:
        preco = v.get("preco", 0)
        if not preco or preco <= 0:
            continue  # pula sem preço

        fotos = v.get("fotos_drive", [])
        img_url, extras = first_valid_photo(fotos, validate_images)

        tipo      = v.get("tipo", "")
        combustivel = v.get("combustivel", "")
        cambio    = v.get("cambio", "")
        marca     = v.get("marca", "")
        modelo    = v.get("modelo", "")
        ano       = v.get("ano", "")
        km        = v.get("km", 0)
        versao    = v.get("versao", "")
        vid       = v.get("id", "")

        # URL da página individual no GitHub Pages
        car_page  = f"{BASE_URL}/carros/{marca.lower()}-{modelo.lower()}-{ano}.html".replace(" ", "-")
        # fallback para link WhatsApp direto
        link      = wa_link(v)

        titulo = f"{marca} {modelo} {ano}"
        desc   = (
            f"{marca} {modelo} {versao} | "
            f"Ano {ano} | {km:,} km | "
            f"{combustivel} | {cambio}. "
            "Laudo cautelar aprovado, garantia de até 2 anos. "
            "Fale com O Brabo das Vendas!"
        ).replace(",", ".")

        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "g:id").text           = str(vid)
        ET.SubElement(item, "g:title").text        = titulo
        ET.SubElement(item, "g:description").text  = desc
        ET.SubElement(item, "g:availability").text = "in stock"
        ET.SubElement(item, "g:condition").text    = "used"
        ET.SubElement(item, "g:price").text        = f"{preco:.2f} BRL"
        # Cada veículo é único: quantidade 1 (corrige "Quantidade não informada")
        ET.SubElement(item, "g:quantity_to_sell_on_facebook").text = "1"
        ET.SubElement(item, "g:inventory").text    = "1"
        ET.SubElement(item, "g:link").text         = link
        ET.SubElement(item, "g:image_link").text   = img_url

        # Imagens adicionais (até 9 extras, já validadas)
        for extra_url in extras:
            ET.SubElement(item, "g:additional_image_link").text = extra_url

        ET.SubElement(item, "g:brand").text        = marca
        ET.SubElement(item, "g:make").text         = marca
        ET.SubElement(item, "g:model").text        = modelo
        ET.SubElement(item, "g:year").text         = str(ano)

        if km:
            mileage = ET.SubElement(item, "g:mileage")
            mileage.set("value", str(km))
            mileage.set("unit", "KM")

        body = BODY_STYLE.get(tipo, "SUV")
        ET.SubElement(item, "g:body_style").text   = body

        fuel = FUEL_MAP.get(combustivel, "Flex-fuel")
        ET.SubElement(item, "g:fuel_type").text    = fuel

        trans = TRANS_MAP.get(cambio, "Automatic")
        ET.SubElement(item, "g:transmission").text = trans

        if versao:
            ET.SubElement(item, "g:trim").text     = versao[:100]

        ET.SubElement(item, "g:vehicle_id").text   = str(vid)

        count += 1

    # Serializar com indentação
    raw = ET.tostring(rss, encoding="unicode", xml_declaration=False)
    pretty = minidom.parseString(
        '<?xml version=\'1.0\' encoding=\'utf-8\'?>' + raw
    ).toprettyxml(indent="  ", encoding=None)

    # Remover a linha <?xml ...?> duplicada que o minidom adiciona
    lines = pretty.splitlines()
    if lines and lines[0].startswith("<?xml"):
        lines = lines[1:]
    final_xml = "<?xml version='1.0' encoding='utf-8'?>\n" + "\n".join(lines)

    Path(output_path).write_text(final_xml, encoding="utf-8")
    print(f"[feed] {count} veiculos gerados em {output_path}")
    return count


if __name__ == "__main__":
    n = generate_feed()
    print(f"Feed gerado com {n} veículos.")
