# scrapers/openai_scraper.py
"""
Scraper for OpenAI pricing.
Parses https://developers.openai.com/api/docs/pricing

The docs site uses Astro content switchers. Standard tier is now
``data-content-switcher-pane`` with ``data-value="standard"`` (not
``pane="standard"``). The full Standard "All models" list is embedded in
serialized ``rows`` in the HTML; the visible flagship table may only show
a few rows — see https://developers.openai.com/api/docs/pricing
"""
from __future__ import annotations

import html as html_lib
import re
from typing import Dict, List, Optional, Tuple

from bs4 import BeautifulSoup

from .base_scraper import BaseScraper, logger

_EMBEDDED_ROW_RE = re.compile(
    r'\[1,\[\[0,"([^"]*)"\],\[0,([^\]]+)\],\[0,([^\]]+)\],\[0,([^\]]+)\]\]\]'
)


class OpenAIScraper(BaseScraper):
    """Scraper for OpenAI pricing information."""

    def __init__(self):
        super().__init__(
            provider_name='OpenAI',
            base_url='https://developers.openai.com/api/docs/pricing'
        )

    def scrape(self) -> Dict:
        """Scrape OpenAI pricing; prefers embedded Standard rows, then HTML."""
        logger.info(f"Scraping {self.provider_name} pricing...")

        try:
            response = self.session.get(self.base_url, timeout=30)
            response.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to fetch {self.provider_name} pricing page: {e}")
            return self.format_output([])

        raw_html = response.text
        soup = BeautifulSoup(response.content, "lxml")
        models = self._parse_embedded_standard_rows(raw_html)
        if not models:
            models = self._parse_pricing_tables(soup)
        return self.format_output(models)

    def _parse_embedded_standard_rows(self, raw_html: str) -> List[Dict]:
        """Parse Astro-serialized Standard-tier model rows from page source."""
        parts = raw_html.split('&quot;rows&quot;:[1,')
        candidates: List[List[Tuple[str, str, str, str]]] = []

        for part in parts[1:]:
            chunk = '&quot;rows&quot;:[1,' + part[:120000]
            decoded = html_lib.unescape(chunk.replace('&quot;', '"'))
            rows = _EMBEDDED_ROW_RE.findall(decoded)
            if not rows or len(rows[0][0]) < 2:
                continue
            candidates.append(rows)

        for rows in candidates:
            name, inp, _, _ = rows[0]
            inp_s = inp.strip().strip('"')
            if 'gpt-5.4' in name and inp_s == '2.5':
                return self._rows_to_models(rows, 'embedded Standard tier')

        for rows in candidates:
            if len(rows) >= 5:
                name = rows[0][0]
                if re.match(r'^(gpt|o\d|davinci|babbage)', name, re.I):
                    return self._rows_to_models(rows, 'embedded (first large block)')

        return []

    def _rows_to_models(
        self, rows: List[Tuple[str, str, str, str]], source: str
    ) -> List[Dict]:
        models: List[Dict] = []
        seen: set = set()

        for name_raw, inp_s, cached_s, out_s in rows:
            model_name = html_lib.unescape(
                name_raw.replace('&lt;', '<').replace('&gt;', '>')
            ).strip()
            if not model_name or len(model_name) < 2:
                continue
            inp = self._parse_embedded_number(inp_s)
            out = self._parse_embedded_number(out_s)
            cached = self._parse_embedded_number(cached_s)
            if inp == 0 and out == 0:
                continue

            model_id = self.model_id_from_name(model_name) or model_name
            if model_id in seen:
                continue
            seen.add(model_id)

            notes = source
            if cached > 0:
                notes += f'; cached input ${cached:.2f}/MTok'

            models.append({
                'model_name': model_name,
                'model_id': model_id,
                'input_price_per_mtok': round(inp, 4),
                'output_price_per_mtok': round(out, 4),
                'context_window': 128000,
                'notes': notes,
            })

        logger.info(f"OpenAI: {len(models)} models from {source}")
        return models

    @staticmethod
    def _parse_embedded_number(raw: str) -> float:
        s = raw.strip().strip('"').replace('"', '')
        if s in ('', '-', 'null', 'None'):
            return 0.0
        try:
            return float(s)
        except ValueError:
            return 0.0

    def _parse_pricing_tables(self, soup: BeautifulSoup) -> List[Dict]:
        """HTML fallback: latest-pricing, Standard pane; 4- or 7-column tables."""
        models: List[Dict] = []
        seen_model_ids: set = set()

        root = soup.find('div', attrs={'data-content-switcher-id': 'latest-pricing'})
        pane = None
        if root:
            pane = root.find(
                'div',
                attrs={'data-content-switcher-pane': True, 'data-value': 'standard'},
            )
        if not pane:
            pane = soup.find('div', attrs={'data-content-switcher-pane': 'standard'})
        if not pane:
            for div in soup.find_all('div', attrs={'data-content-switcher-pane': True}):
                if div.get('data-value') == 'standard' and not div.has_attr('hidden'):
                    pane = div
                    break

        tables = pane.find_all('table') if pane else soup.find_all('table')

        for table in tables:
            thead = table.find('thead')
            if not thead:
                continue
            header_rows = thead.find_all('tr')
            last_header = header_rows[-1]
            headers = [
                th.get_text(strip=True).lower()
                for th in last_header.find_all(['th', 'td'])
            ]
            header_joined = ' '.join(headers)
            if 'model' not in header_joined or 'input' not in header_joined:
                continue
            if 'output' not in header_joined and 'cost' not in header_joined:
                continue

            ncols = len(headers)
            col_model = 0
            col_inp, col_out = self._pick_input_output_columns(headers, ncols)

            tbody = table.find('tbody')
            if not tbody:
                continue

            for tr in tbody.find_all('tr'):
                cells = tr.find_all('td')
                if len(cells) <= max(col_model, col_inp, col_out):
                    continue
                model_name = cells[col_model].get_text(strip=True)
                if not model_name or len(model_name) < 2:
                    continue
                model_id = self.model_id_from_name(model_name) or model_name
                if model_id in seen_model_ids:
                    continue
                input_price = self.normalize_price(cells[col_inp].get_text())
                output_price = self.normalize_price(cells[col_out].get_text())
                if input_price == 0 and output_price == 0:
                    continue
                seen_model_ids.add(model_id)
                models.append({
                    'model_name': model_name,
                    'model_id': model_id,
                    'input_price_per_mtok': round(input_price, 4),
                    'output_price_per_mtok': round(output_price, 4),
                    'context_window': 128000,
                    'notes': 'Standard tier (HTML)',
                })

            if models:
                logger.info(f"OpenAI: {len(models)} models from HTML")
                break

        return models

    @staticmethod
    def _pick_input_output_columns(
        headers: List[str], ncols: int
    ) -> Tuple[int, int]:
        if ncols >= 7 and headers and 'model' in headers[0]:
            return 1, 3
        col_inp: Optional[int] = None
        col_out: Optional[int] = None
        for i, h in enumerate(headers):
            if (h == 'input' or h.startswith('input')) and 'cached' not in h:
                if col_inp is None:
                    col_inp = i
            elif 'output' in h or '/ cost' in h:
                col_out = i
        if col_inp is None:
            col_inp = 1 if ncols > 1 else 0
        if col_out is None:
            col_out = ncols - 1
        return col_inp, col_out
