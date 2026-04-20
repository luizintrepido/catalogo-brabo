"""
Scraper para https://recarautomarcas.com.br/Veiculos
"""
import re
import time
import logging
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from .base import BaseScraper
from utils import determine_tipo, parse_preco, parse_km, parse_ano
import config

logger = logging.getLogger(__name__)

AUTOCERTO_DEALER_ID = "4130"


class RecarAutomarcasScraper(BaseScraper):

    SITE_NAME = "Recar Automarcas"
    LOJA = "RECAR"
    BASE_URL = "https://recarautomarcas.com.br"
    LISTING_URL = "https://recarautomarcas.com.br/Veiculos"

    def __init__(self):
        super().__init__()
        self._playwright = None
        self._browser = None
        self._page = None

    def _start_browser(self):
        if self._browser is not None:
            return
        from playwright.sync_api import sync_playwright
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=True)
        ctx = self._browser.new_context(user_agent=config.HEADERS["User-Agent"], locale="pt-BR")
        self._page = ctx.new_page()

    def _stop_browser(self):
        try:
            if self._browser:
                self._browser.close()
            if self._playwright:
                self._playwright.stop()
        except Exception:
            pass

    def _fetch_with_playwright(self, url: str, wait_selector: str = None) -> str:
        self._start_browser()
        try:
            self._page.goto(url, timeout=30_000, wait_until="networkidle")
            if wait_selector:
                try:
                    self._page.wait_for_selector(wait_selector, timeout=10_000)
                except Exception:
                    pass
            return self._page.content()
        except Exception as e:
            logger.warning(f"[{self.SITE_NAME}] Playwright erro {url}: {e}")
            return ""

    def _get_all_car_links(self) -> list[str]:
        html = self._fetch_with_playwright(self.LISTING_URL, wait_selector="a[href*='/Veiculo/']")
        if not html:
            resp = self._fetch(self.LISTING_URL)
            html = resp.text if resp else ""
        soup = BeautifulSoup(html, "lxml")
        links = set()
        for tag in soup.find_all("a", href=True):
            href = tag["href"]
            if re.search(r"/Veiculo/[^/]+/\d+/detalhes", href, re.I):
                links.add(urljoin(self.BASE_URL, href))
        logger.info(f"[{self.SITE_NAME}] {len(links)} links encontrados")
        return list(links)

    def _extract_car_details(self, url: str) -> dict | None:
        html = self._fetch_with_playwright(url)
        if not html:
            resp = self._fetch(url)
            html = resp.text if resp else ""
        if not html:
            return None

        soup = BeautifulSoup(html, "lxml")

        id_m = re.search(r"/Veiculo/[^/]+/(\d+)/detalhes", url, re.I)
        car_id = id_m.group(1) if id_m else url.split("/")[-2]

        # Nome completo da página
        nome = ""
        for sel in ["h1", "h2", ".vehicle-name", ".titulo-veiculo"]:
            el = soup.select_one(sel)
            if el:
                nome = self._clean(self._text(el))
                if nome:
                    break
        if not nome:
            title = soup.find("title")
            if title:
                nome = self._clean(self._text(title).split("|")[0].split("-")[0])

        # Extrai marca e modelo do nome
        parts = nome.split()
        marca = parts[0].title() if parts else ""
        modelo = parts[1].upper() if len(parts) > 1 else nome.upper()
        versao = " ".join(parts[2:]).title() if len(parts) > 2 else ""

        page_text = soup.get_text(" ", strip=True)

        preco_str = ""
        pm = re.search(r"R\$\s*([\d.,]+)", page_text)
        if pm:
            preco_str = f"R$ {pm.group(1)}"
        preco = parse_preco(preco_str)

        ano_str = ""
        am = re.search(r"\b(20\d{2})\s*/\s*(20\d{2})\b", page_text)
        if am:
            ano_str = f"{am.group(1)}/{am.group(2)}"
        ano = parse_ano(ano_str)

        km_str = ""
        km_m = re.search(r"([\d.,]+)\s*km\b", page_text, re.I)
        if km_m:
            km_str = f"{km_m.group(1)} km"
        km = parse_km(km_str)

        cambio = ""
        cam_m = re.search(r"(autom[aá]tico|manual|cvt)", page_text, re.I)
        if cam_m:
            cambio = cam_m.group(1).title()

        comb = ""
        comb_m = re.search(r"(flex|gasolina|[aá]lcool|diesel|el[eé]trico)", page_text, re.I)
        if comb_m:
            comb = comb_m.group(1).title()

        opcionais = []
        for section in soup.find_all(["ul", "div"], class_=re.compile(r"optional|equip|acessor|opcion", re.I)):
            for li in section.find_all(["li", "span"]):
                text = self._clean(self._text(li))
                if text and 3 < len(text) < 60 and text not in opcionais:
                    opcionais.append(text)

        tipo = determine_tipo(marca, modelo, versao)

        return {
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
            "cor": "",
            "cambio": cambio,
            "combustivel": comb,
            "opcionais": opcionais[:30],
            "fotos": self._extract_photos(soup, car_id),
        }

    def _extract_photos(self, soup: BeautifulSoup, car_id: str) -> list[str]:
        """Extrai APENAS fotos deste carro específico via autocerto.com."""
        fotos = []
        seen = set()

        # Padrão: só aceita URLs com o car_id específico
        pattern = re.compile(
            rf"autocerto\.com/fotos/{AUTOCERTO_DEALER_ID}/{car_id}/\S+?\.jpg",
            re.I,
        )

        # Procura em atributos de tags
        for tag in soup.find_all(["img", "a"]):
            for attr in ["src", "data-src", "href", "data-zoom-image"]:
                val = tag.get(attr, "")
                if val and f"/{car_id}/" in val and "autocerto.com" in val:
                    if not val.startswith("http"):
                        val = "https:" + val if val.startswith("//") else f"https://www.autocerto.com{val}"
                    if val not in seen:
                        seen.add(val)
                        fotos.append(val)

        # Procura em scripts
        for script in soup.find_all("script"):
            text = script.string or ""
            for m in pattern.findall(text):
                url = f"https://www.autocerto.com/fotos/{AUTOCERTO_DEALER_ID}/{car_id}/{m.split('/')[-1]}"
                if url not in seen:
                    seen.add(url)
                    fotos.append(url)

        logger.debug(f"[{self.SITE_NAME}] Carro {car_id}: {len(fotos)} fotos encontradas")
        return fotos

    def get_all_cars(self) -> list[dict]:
        try:
            links = self._get_all_car_links()
            if not links:
                logger.warning(f"[{self.SITE_NAME}] Nenhum carro encontrado!")
                return []
            cars = []
            for i, link in enumerate(links, 1):
                logger.info(f"[{self.SITE_NAME}] Detalhes {i}/{len(links)}: {link}")
                details = self._extract_car_details(link)
                if details:
                    cars.append(details)
                time.sleep(config.DELAY_BETWEEN_CARS)
            return cars
        finally:
            self._stop_browser()
