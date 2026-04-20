"""
Scraper para https://reautoveiculos.com.br/estoque
"""
import re
import time
import logging
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from .base import BaseScraper
from utils import determine_tipo, parse_preco, parse_km, parse_ano, split_nome_reautov
import config

logger = logging.getLogger(__name__)


class ReautoVeiculosScraper(BaseScraper):

    SITE_NAME = "ReAuto Veículos"
    LOJA = "REAUTO"
    BASE_URL = "https://reautoveiculos.com.br"
    LISTING_URL = "https://reautoveiculos.com.br/estoque"

    def _get_car_links_from_page(self, page: int) -> list[str]:
        url = f"{self.LISTING_URL}?registros_por_pagina=18&pagina={page}"
        soup = self._fetch_soup(url)
        if soup is None:
            return []
        links = set()
        for tag in soup.find_all("a", href=True):
            href = tag["href"]
            if re.search(r"/carros/[^/]+/[^/]+/\d{4}/\d+", href):
                full_url = urljoin(self.BASE_URL, href)
                links.add(full_url)
        return list(links)

    def _get_total_pages(self) -> int:
        soup = self._fetch_soup(self.LISTING_URL)
        if soup is None:
            return 1
        max_page = 1
        for tag in soup.find_all("a", href=True):
            m = re.search(r"pagina=(\d+)", tag["href"])
            if m:
                max_page = max(max_page, int(m.group(1)))
        text = soup.get_text()
        m = re.search(r"(\d+)\s+ve[íi]culos?", text, re.I)
        if m:
            total = int(m.group(1))
            max_page = max(max_page, (total // 18) + 1)
        return min(max_page, config.MAX_PAGES)

    def _extract_car_details(self, url: str) -> dict | None:
        soup = self._fetch_soup(url)
        if soup is None:
            return None

        car_id = url.rstrip("/").split("/")[-1]
        marca, modelo, versao = split_nome_reautov(url)

        page_text = soup.get_text(" ", strip=True)

        # Preço
        preco_str = ""
        pm = re.search(r"R\$\s*([\d.,]+)", page_text)
        if pm:
            preco_str = f"R$ {pm.group(1)}"
        preco = parse_preco(preco_str)

        # Ano
        ano_str = ""
        am = re.search(r"\b(20\d{2})\s*/\s*(20\d{2})\b", page_text)
        if am:
            ano_str = f"{am.group(1)}/{am.group(2)}"
        ano = parse_ano(ano_str)

        # KM
        km_str = ""
        km_m = re.search(r"([\d.,]+)\s*km\b", page_text, re.I)
        if km_m:
            km_str = f"{km_m.group(1)} km"
        km = parse_km(km_str)

        # Cor
        cor = ""
        cor_m = re.search(r"(?:cor|color)[:\s]+([A-Za-zÀ-ú ]+?)(?:\s*[,\.\n<])", page_text, re.I)
        if cor_m:
            cor = cor_m.group(1).strip()

        # Câmbio
        cambio = ""
        cam_m = re.search(r"(autom[aá]tico|manual|cvt|semi.autom[aá]tico)", page_text, re.I)
        if cam_m:
            cambio = cam_m.group(1).title()

        # Combustível
        comb = ""
        comb_m = re.search(r"(flex|gasolina|[aá]lcool|diesel|el[eé]trico|h[ií]brido)", page_text, re.I)
        if comb_m:
            comb = comb_m.group(1).title()

        # Opcionais
        opcionais = []
        for section in soup.find_all(["ul", "div"], class_=re.compile(r"optional|item|equip|acessor|opcion", re.I)):
            for li in section.find_all(["li", "span"]):
                text = self._clean(self._text(li))
                if text and 3 < len(text) < 60 and text not in opcionais:
                    opcionais.append(text)

        tipo = determine_tipo(marca, modelo, versao)

        info = {
            "id": car_id,
            "url": url,
            "site": self.SITE_NAME,
            "loja": self.LOJA,
            "marca": marca,
            "modelo": modelo,
            "versao": versao,
            "ano": ano,
            "km": km,
            "preco": preco,
            "tipo": tipo,
            "cor": cor,
            "cambio": cambio,
            "combustivel": comb,
            "opcionais": opcionais[:30],
            "fotos": self._extract_photos(soup, car_id),
        }

        return info

    def _extract_photos(self, soup: BeautifulSoup, car_id: str) -> list[str]:
        """Extrai APENAS fotos deste carro específico usando o car_id como âncora."""
        fotos = []
        seen = set()

        # Padrão: só aceita URLs que contenham o car_id específico
        pattern = re.compile(
            rf"veiculos/fotos/{car_id}/([a-f0-9]{{8}}-[a-f0-9]{{4}}-[a-f0-9]{{4}}-[a-f0-9]{{4}}-[a-f0-9]{{12}})\.jpg",
            re.I,
        )

        # 1) Procura nos scripts
        for script in soup.find_all("script"):
            text = script.string or ""
            for uuid in pattern.findall(text):
                url = (
                    f"https://resized-images.autoconf.com.br/1440x0/"
                    f"filters:format(jpg)/veiculos/fotos/{car_id}/{uuid}.jpg"
                )
                if url not in seen:
                    seen.add(url)
                    fotos.append(url)

        # 2) Procura em atributos de imagens/links
        for tag in soup.find_all(["img", "a"]):
            for attr in ["src", "data-src", "href", "data-original"]:
                val = tag.get(attr, "")
                if val and f"veiculos/fotos/{car_id}/" in val:
                    val = re.sub(r"/\d+x\d+/", "/1440x0/", val)
                    val = re.sub(r"filters:format\(\w+\)", "filters:format(jpg)", val)
                    if val not in seen:
                        seen.add(val)
                        fotos.append(val)

        logger.debug(f"[{self.SITE_NAME}] Carro {car_id}: {len(fotos)} fotos encontradas")
        return fotos

    def get_all_cars(self) -> list[dict]:
        logger.info(f"[{self.SITE_NAME}] Descobrindo páginas...")
        total_pages = self._get_total_pages()
        logger.info(f"[{self.SITE_NAME}] Total de páginas: {total_pages}")

        all_links = set()
        for page in range(1, total_pages + 1):
            links = self._get_car_links_from_page(page)
            all_links.update(links)
            logger.info(f"[{self.SITE_NAME}] Página {page}/{total_pages}: {len(links)} carros")
            time.sleep(config.DELAY_BETWEEN_PAGES)

        cars = []
        for i, link in enumerate(sorted(all_links), 1):
            logger.info(f"[{self.SITE_NAME}] Detalhes {i}/{len(all_links)}: {link}")
            details = self._extract_car_details(link)
            if details:
                cars.append(details)
            time.sleep(config.DELAY_BETWEEN_CARS)

        return cars
