"""
Classe base para os scrapers de veículos.
"""
import time
import logging
import requests
from bs4 import BeautifulSoup
import config

logger = logging.getLogger(__name__)


class BaseScraper:
    """Classe base com funcionalidades compartilhadas entre scrapers."""

    SITE_NAME = "Base"
    BASE_URL = ""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(config.HEADERS)

    # ------------------------------------------------------------------
    # Utilitários HTTP
    # ------------------------------------------------------------------

    def _fetch(self, url: str, retries: int = 3) -> requests.Response | None:
        """Faz uma requisição GET com retentativas."""
        for attempt in range(1, retries + 1):
            try:
                resp = self.session.get(url, timeout=config.REQUEST_TIMEOUT)
                resp.raise_for_status()
                return resp
            except requests.RequestException as exc:
                logger.warning(f"[{self.SITE_NAME}] Tentativa {attempt}/{retries} falhou para {url}: {exc}")
                if attempt < retries:
                    time.sleep(2 * attempt)
        return None

    def _fetch_soup(self, url: str) -> BeautifulSoup | None:
        """Faz requisição e retorna BeautifulSoup."""
        resp = self._fetch(url)
        if resp is None:
            return None
        return BeautifulSoup(resp.text, "lxml")

    def download_image(self, url: str) -> bytes | None:
        """Baixa uma imagem e retorna os bytes."""
        try:
            resp = self.session.get(url, timeout=config.REQUEST_TIMEOUT, stream=True)
            resp.raise_for_status()
            content = resp.content
            # Verifica se o conteúdo parece ser uma imagem real (mínimo 5 KB)
            if len(content) < 5_000:
                logger.debug(f"Imagem muito pequena (possivelmente placeholder): {url}")
                return None
            return content
        except Exception as exc:
            logger.warning(f"Erro ao baixar imagem {url}: {exc}")
            return None

    # ------------------------------------------------------------------
    # Métodos abstratos — implementados em cada scraper
    # ------------------------------------------------------------------

    def get_all_cars(self) -> list[dict]:
        """Retorna lista de dicts com todas as informações dos carros."""
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Utilitários de extração HTML
    # ------------------------------------------------------------------

    @staticmethod
    def _text(element) -> str:
        """Retorna texto limpo de um elemento BeautifulSoup."""
        if element is None:
            return ""
        return element.get_text(separator=" ", strip=True)

    @staticmethod
    def _clean(text: str) -> str:
        """Remove espaços extras e caracteres invisíveis."""
        return " ".join(text.split()).strip()
