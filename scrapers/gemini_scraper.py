# scrapers/gemini_scraper.py
"""
Scraper for Google Gemini pricing.
Parses https://ai.google.dev/gemini-api/docs/pricing
"""
from typing import Dict, List, Optional, Tuple
from bs4 import BeautifulSoup, Tag

from .base_scraper import BaseScraper, logger


class GeminiScraper(BaseScraper):
    """Scraper for Gemini pricing information."""

    def __init__(self):
        super().__init__(
            provider_name='Gemini',
            base_url='https://ai.google.dev/gemini-api/docs/pricing'
        )

    def scrape(self) -> Dict:
        """
        Scrape Gemini pricing data from the documentation page.
        Dynamically extracts all models from model sections and their Standard tier tables.
        """
        logger.info(f"Scraping {self.provider_name} pricing...")

        soup = self.fetch_page(self.base_url)
        if not soup:
            logger.error(f"Failed to fetch {self.provider_name} pricing page")
            return self.format_output([])

        models = self._parse_model_sections(soup)
        return self.format_output(models)

    def _parse_model_sections(self, soup: BeautifulSoup) -> List[Dict]:
        """
        Find models-section divs and their associated Standard pricing tables.
        Each model has: heading-group (h2 + code) and a following ds-selector-tabs with Standard table.
        """
        models = []
        seen_ids = set()

        # Find all model heading groups (h2 with id like gemini-*)
        model_headers = soup.find_all('h2', id=lambda x: x and 'gemini' in (x or '').lower())
        for h2 in model_headers:
            model_name = (h2.get('data-text') or h2.get_text(strip=True)).strip()
            code = h2.find_next_sibling('em')
            model_id = ''
            if code and code.find('code'):
                model_id = code.find('code').get_text(strip=True)
            if not model_id:
                model_id = self.model_id_from_name(model_name)

            if model_id in seen_ids:
                continue

            # Find ds-selector-tabs: sibling of models-section, or next in document
            models_section = h2.find_parent('div', class_=lambda c: c and 'models-section' in c)
            tabs = None
            if models_section:
                sib = models_section.find_next_sibling()
                while sib:
                    if isinstance(sib, Tag) and sib.get('class') and 'ds-selector-tabs' in sib.get('class', []):
                        tabs = sib
                        break
                    sib = sib.find_next_sibling()
            if not tabs:
                tabs = h2.find_next('div', class_=lambda c: c and 'ds-selector-tabs' in (c or []))

            if not tabs:
                continue

            std_table = None
            for sec in tabs.find_all('section', recursive=True):
                h3 = sec.find('h3')
                if h3 and 'standard' in (h3.get_text(strip=True) or '').lower():
                    std_table = sec.find('table', class_='pricing-table')
                    if std_table:
                        break
            if not std_table:
                std_table = tabs.find('table', class_='pricing-table')

            if not std_table:
                continue

            input_price, output_price, context = self._parse_gemini_table(std_table)
            if input_price == 0 and output_price == 0:
                # Free tier only, skip or include with 0
                if 'free' in model_name.lower() or 'preview' in model_name.lower():
                    pass  # Include free models
                else:
                    continue

            seen_ids.add(model_id)
            models.append({
                'model_name': model_name,
                'model_id': model_id,
                'input_price_per_mtok': round(input_price, 4),
                'output_price_per_mtok': round(output_price, 4),
                'context_window': context or 1000000,
                'notes': 'Standard tier; prompts <= 200k'
            })

        return models

    def _parse_gemini_table(self, table: Tag) -> Tuple[float, float, int]:
        """Extract input and output price from a Gemini pricing-table. Third column is Paid Tier."""
        input_price = 0.0
        output_price = 0.0
        context = 0

        for tr in (table.find('tbody') or table).find_all('tr'):
            cells = tr.find_all('td')
            if len(cells) < 3:
                continue
            label = cells[0].get_text(strip=True).lower()
            paid_cell = cells[2].get_text()
            val = self.normalize_price(paid_cell)
            if 'input price' in label and 'output' not in label:
                input_price = val
            elif 'output price' in label:
                output_price = val
            if '200k' in paid_cell.lower() or '200k' in label:
                context = max(context, self.parse_context_window('200K'))

        return input_price, output_price, context or 200000
