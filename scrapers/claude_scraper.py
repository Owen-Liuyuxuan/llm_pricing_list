# scrapers/claude_scraper.py
"""
Scraper for Anthropic Claude pricing.
Parses https://platform.claude.com/docs/en/about-claude/pricing
"""
from typing import Dict, List
from bs4 import BeautifulSoup

from .base_scraper import BaseScraper, logger


class ClaudeScraper(BaseScraper):
    """Scraper for Claude pricing information."""

    def __init__(self):
        super().__init__(
            provider_name='Claude',
            base_url='https://platform.claude.com/docs/en/about-claude/pricing'
        )

    def scrape(self) -> Dict:
        """
        Scrape Claude pricing data from the documentation page.
        Dynamically extracts all models from the Model pricing table.
        """
        logger.info(f"Scraping {self.provider_name} pricing...")

        soup = self.fetch_page(self.base_url)
        if not soup:
            logger.error(f"Failed to fetch {self.provider_name} pricing page")
            return self.format_output([])

        models = self._parse_pricing_table(soup)
        return self.format_output(models)

    def _parse_pricing_table(self, soup: BeautifulSoup) -> List[Dict]:
        """
        Find the main Model pricing table (Model | Base Input Tokens | ... | Output Tokens)
        and extract all model rows dynamically.
        """
        models = []
        tables = soup.find_all('table', class_='w-full')
        if not tables:
            tables = soup.find_all('table')

        for table in tables:
            thead = table.find('thead')
            if not thead:
                continue

            headers = [th.get_text(strip=True).lower() for th in thead.find_all('th')]
            # Look for the main model pricing table (Base Input + Output columns)
            if 'base input tokens' not in ' '.join(headers) or 'output tokens' not in ' '.join(headers):
                continue

            # Determine column indices
            col_model = 0
            col_base_input = None
            col_output = None
            for i, h in enumerate(headers):
                if 'base input' in h or (h == 'base input tokens'):
                    col_base_input = i
                elif 'output' in h and 'token' in h:
                    col_output = i

            if col_base_input is None or col_output is None:
                continue

            tbody = table.find('tbody')
            if not tbody:
                continue

            for tr in tbody.find_all('tr'):
                cells = tr.find_all('td')
                if len(cells) <= max(col_base_input, col_output):
                    continue

                model_name = cells[col_model].get_text(strip=True)
                # Skip empty rows (e.g. continuation rows in long context table)
                if not model_name or len(model_name) < 3:
                    continue
                # Skip non-model rows (e.g. "Context window" tables)
                if 'token' in model_name.lower() and '$' not in model_name:
                    continue

                input_price = self.normalize_price(cells[col_base_input].get_text())
                output_price = self.normalize_price(cells[col_output].get_text())

                if input_price == 0 and output_price == 0:
                    continue

                notes = []
                if 'deprecated' in model_name.lower():
                    notes.append('Deprecated')

                models.append({
                    'model_name': model_name,
                    'model_id': self.model_id_from_name(model_name),
                    'input_price_per_mtok': round(input_price, 4),
                    'output_price_per_mtok': round(output_price, 4),
                    'context_window': 200000,  # Claude standard context
                    'notes': '; '.join(notes) if notes else 'Base input and output pricing'
                })

            break  # Use first matching table only

        return models
