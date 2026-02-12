# scrapers/deepseek_scraper.py
"""
Scraper for DeepSeek pricing.
Parses https://api-docs.deepseek.com/quick_start/pricing
"""
from typing import Dict, List
from bs4 import BeautifulSoup

from .base_scraper import BaseScraper, logger


class DeepSeekScraper(BaseScraper):
    """Scraper for DeepSeek pricing information."""

    def __init__(self):
        super().__init__(
            provider_name='DeepSeek',
            base_url='https://api-docs.deepseek.com/quick_start/pricing'
        )

    def scrape(self) -> Dict:
        """
        Scrape DeepSeek pricing data from the documentation page.
        Dynamically extracts models and pricing from the Model Details table.
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
        Parse the Model Details table. Structure:
        - Row 1: MODEL | model1 | model2 | ...
        - CONTEXT LENGTH row
        - PRICING: 1M INPUT (CACHE HIT), 1M INPUT (CACHE MISS), 1M OUTPUT
        """
        models = []
        model_ids = []
        context_window = 128000
        price_cache_hit = 0.0
        price_cache_miss = 0.0
        price_output = 0.0

        # Find table - in div with font-size or in theme-doc-markdown
        for div in soup.find_all('div', style=lambda s: s and 'font-size' in (s or '')):
            table = div.find('table')
            if table:
                break
        else:
            table = soup.find('table')

        if not table:
            return models

        rows = table.find_all('tr')
        for tr in rows:
            cells = [td.get_text(strip=True) for td in tr.find_all(['td', 'th'])]
            if not cells:
                continue

            first = cells[0].upper().strip()
            if first == 'MODEL' and len(cells) >= 2:
                # Header row: MODEL | model1 | model2
                model_ids = [c.strip() for c in cells[1:] if c and not c.startswith('http')
                            and 'deepseek-' in c.lower()]
            elif 'CONTEXT' in first and 'LENGTH' in first:
                ctx_val = cells[-1] if len(cells) > 1 else ''
                context_window = self.parse_context_window(ctx_val) or 128000
            elif 'PRICING' in first and len(cells) < 2:
                continue  # Standalone PRICING header
            else:
                # Check any cell for pricing row type (rowspan may put PRICING in first cell)
                row_text = ' '.join(cells).upper()
                val = cells[-1] if len(cells) > 1 else cells[0]
                price_val = self.normalize_price(val)
                if 'CACHE HIT' in row_text and 'INPUT' in row_text:
                    price_cache_hit = price_val
                elif 'CACHE MISS' in row_text:
                    price_cache_miss = price_val
                elif 'OUTPUT' in row_text and 'INPUT' not in row_text:
                    price_output = price_val

        if not model_ids:
            model_ids = ['deepseek-chat', 'deepseek-reasoner']

        for model_id in model_ids:
            if not model_id:
                continue
            # Human-readable name from model_id
            name = model_id.replace('-', ' ').title()

            if price_cache_miss > 0:
                models.append({
                    'model_name': f'{name}',
                    'model_id': model_id,
                    'input_price_per_mtok': round(price_cache_miss, 4),
                    'output_price_per_mtok': round(price_output, 4),
                    'context_window': context_window,
                    'notes': 'Cache miss pricing'
                })
            if price_cache_hit > 0:
                models.append({
                    'model_name': f'{name} (Cached)',
                    'model_id': model_id,
                    'input_price_per_mtok': round(price_cache_hit, 4),
                    'output_price_per_mtok': round(price_output, 4),
                    'context_window': context_window,
                    'notes': 'Cache hit pricing'
                })

        return models
