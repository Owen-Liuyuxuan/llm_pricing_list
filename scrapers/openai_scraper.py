# scrapers/openai_scraper.py
"""
Scraper for OpenAI pricing.
Parses https://developers.openai.com/api/docs/pricing
"""
from typing import Dict, List
from bs4 import BeautifulSoup

from .base_scraper import BaseScraper, logger


class OpenAIScraper(BaseScraper):
    """Scraper for OpenAI pricing information."""

    def __init__(self):
        super().__init__(
            provider_name='OpenAI',
            base_url='https://developers.openai.com/api/docs/pricing'
        )

    def scrape(self) -> Dict:
        """
        Scrape OpenAI pricing data from the documentation page.
        Dynamically extracts all models from the Standard tier table.
        """
        logger.info(f"Scraping {self.provider_name} pricing...")

        soup = self.fetch_page(self.base_url)
        if not soup:
            logger.error(f"Failed to fetch {self.provider_name} pricing page")
            return self.format_output([])

        models = self._parse_pricing_tables(soup)
        return self.format_output(models)

    def _parse_pricing_tables(self, soup: BeautifulSoup) -> List[Dict]:
        """
        Find the Text tokens pricing table. Prefer Standard tier (default).
        Parse all model rows dynamically from tables with Model | Input | Output columns.
        """
        models = []
        seen_model_ids = set()

        # Try Standard pane first (data-content-switcher-initial="standard")
        pane = soup.find('div', attrs={'data-content-switcher-pane': 'standard'})
        if not pane:
            # Fallback: find any pane without hidden that contains a table
            for div in soup.find_all('div', attrs={'data-content-switcher-pane': True}):
                if div.get('hidden') is None and div.find('table'):
                    pane = div
                    break

        tables = [pane.find('table')] if pane else []
        if not tables or not tables[0]:
            # Fallback: any table with Model, Input, Output headers
            tables = soup.find_all('table')

        for table in tables:
            if not table:
                continue

            thead = table.find('thead')
            if not thead:
                continue

            headers = [th.get_text(strip=True).lower() for th in thead.find_all('th')]
            header_text = ' '.join(headers)
            if 'input' not in header_text or 'output' not in header_text or 'model' not in header_text:
                continue

            col_model = 0
            col_input = None
            col_output = None
            for i, h in enumerate(headers):
                if 'model' in h:
                    col_model = i
                elif 'input' in h and 'cached' not in h:
                    col_input = i
                elif 'output' in h:
                    col_output = i
            if col_input is None:
                col_input = 1 if len(headers) > 1 else 0
            if col_output is None:
                col_output = len(headers) - 1

            if col_output is None or col_output < 0:
                continue

            tbody = table.find('tbody')
            if not tbody:
                continue

            for tr in tbody.find_all('tr'):
                cells = tr.find_all('td')
                if len(cells) <= max(col_model, col_input, col_output):
                    continue

                model_name = cells[col_model].get_text(strip=True)
                if not model_name or len(model_name) < 2:
                    continue

                model_id = self.model_id_from_name(model_name) or model_name
                if model_id in seen_model_ids:
                    continue
                seen_model_ids.add(model_id)

                input_price = self.normalize_price(cells[col_input].get_text())
                output_price = self.normalize_price(cells[col_output].get_text())

                if input_price == 0 and output_price == 0:
                    continue

                notes = 'Standard tier'
                cached_cell = table.find('th', string=lambda t: t and 'cached' in t.lower()) if table else None
                if col_input + 1 < len(cells) and 'cached' in header_text:
                    cached_val = cells[col_input + 1].get_text(strip=True)
                    if cached_val and cached_val not in ('-', '—'):
                        notes = f'Standard tier; cached input: ${self.normalize_price(cached_val)}/MTok'

                models.append({
                    'model_name': model_name,
                    'model_id': model_id,
                    'input_price_per_mtok': round(input_price, 4),
                    'output_price_per_mtok': round(output_price, 4),
                    'context_window': 128000,  # OpenAI typical
                    'notes': notes
                })

            if models:
                break

        return models
