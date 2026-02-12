# scrape.py
"""
Main script to orchestrate all pricing scrapers and save results.
"""
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List
import logging

from scrapers.claude_scraper import ClaudeScraper
from scrapers.openai_scraper import OpenAIScraper
from scrapers.gemini_scraper import GeminiScraper
from scrapers.deepseek_scraper import DeepSeekScraper
from scrapers.doubao_scraper import DoubaoScraper
from scrapers.forex import get_cny_to_usd

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PricingAggregator:
    """Aggregates pricing data from all LLM providers."""
    
    def __init__(self, data_dir: str = 'data'):
        """
        Initialize the aggregator.
        
        Args:
            data_dir: Directory to store pricing data
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.history_dir = self.data_dir / 'history'
        self.history_dir.mkdir(exist_ok=True)
        
        self._scrapers = None  # Built lazily with fresh forex rate
        self._icon_sources_dir = Path(__file__).resolve().parent / '.agents' / 'icon_sources'

    # Map folder names to provider names used in pricing data
    _PROVIDER_NAMES = {
        'claude': 'Claude', 'openai': 'OpenAI', 'gemini': 'Gemini',
        'deepseek': 'DeepSeek', 'doubao': 'Doubao',
    }

    def sync_icon_sources(self) -> None:
        """
        Copy icon URLs from .agents/icon_sources/<provider>/link into
        data/provider_icons.json for use by the webpage.
        """
        icons = {}
        if not self._icon_sources_dir.exists():
            logger.warning(f"Icon sources dir not found: {self._icon_sources_dir}")
            return
        for subdir in sorted(self._icon_sources_dir.iterdir()):
            if not subdir.is_dir():
                continue
            link_file = subdir / 'link'
            if not link_file.exists():
                continue
            try:
                url = link_file.read_text(encoding='utf-8').strip()
                if url:
                    name = self._PROVIDER_NAMES.get(
                        subdir.name.lower(),
                        subdir.name.replace('_', ' ').title()
                    )
                    icons[name] = url
            except Exception as e:
                logger.warning(f"Could not read icon for {subdir.name}: {e}")
        if icons:
            out = self.data_dir / 'provider_icons.json'
            with open(out, 'w', encoding='utf-8') as f:
                json.dump(icons, f, indent=2)
            logger.info(f"Synced {len(icons)} provider icons to {out}")
        else:
            logger.warning("No icon sources found in .agents/icon_sources/")

    @property
    def scrapers(self):
        """Build scrapers with current forex rate (run at scrape time)."""
        if self._scrapers is None:
            cny_to_usd = get_cny_to_usd()
            self._scrapers = [
                ClaudeScraper(),
                OpenAIScraper(),
                GeminiScraper(),
                DeepSeekScraper(),
                DoubaoScraper(cny_to_usd=cny_to_usd)
            ]
        return self._scrapers

    def scrape_all(self) -> Dict:
        """
        Scrape pricing data from all providers.
        Fetches fresh forex rate (CNY->USD) before Doubao scrape.
        
        Returns:
            Dictionary containing all pricing data
        """
        self._scrapers = None  # Force fresh scrapers (new forex rate)
        results = {
            'scraped_at': datetime.utcnow().isoformat(),
            'providers': []
        }

        for scraper in self.scrapers:
            try:
                data = scraper.scrape()
                results['providers'].append(data)
                logger.info(f"Successfully scraped {scraper.provider_name}")
            except Exception as e:
                logger.error(f"Failed to scrape {scraper.provider_name}: {e}")
                
        return results
        
    def save_data(self, data: Dict):
        """
        Save pricing data to JSON files.
        Adds flattened all_models list for unified visualization.
        Syncs provider icons from .agents/icon_sources/.
        """
        self.sync_icon_sources()
        # Merge all models into single list with provider for unified view
        all_models = []
        for p in data.get('providers', []):
            for m in p.get('models', []):
                all_models.append({**m, 'provider': p.get('provider', '')})
        data['all_models'] = all_models

        # Save current pricing
        current_file = self.data_dir / 'current_pricing.json'
        with open(current_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved current pricing to {current_file}")
        
        # Save historical snapshot
        date_str = datetime.utcnow().strftime('%Y-%m-%d')
        history_file = self.history_dir / f'pricing_{date_str}.json'
        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved historical snapshot to {history_file}")
        
    def generate_summary(self, data: Dict) -> Dict:
        """
        Generate summary statistics from pricing data.
        
        Args:
            data: Pricing data
            
        Returns:
            Summary statistics
        """
        summary = {
            'total_providers': len(data['providers']),
            'total_models': sum(len(p['models']) for p in data['providers']),
            'cheapest_input': None,
            'cheapest_output': None,
            'most_expensive_input': None,
            'most_expensive_output': None
        }
        
        all_models = []
        for provider in data['providers']:
            for model in provider['models']:
                all_models.append({
                    'provider': provider['provider'],
                    'model': model['model_name'],
                    'input_price': model['input_price_per_mtok'],
                    'output_price': model['output_price_per_mtok']
                })
        
        # Filter out free models for min/max calculations
        paid_models = [m for m in all_models if m['input_price'] > 0]
        
        if paid_models:
            summary['cheapest_input'] = min(paid_models, key=lambda x: x['input_price'])
            summary['cheapest_output'] = min(paid_models, key=lambda x: x['output_price'])
            summary['most_expensive_input'] = max(paid_models, key=lambda x: x['input_price'])
            summary['most_expensive_output'] = max(paid_models, key=lambda x: x['output_price'])
        
        return summary


def main():
    """Main execution function."""
    logger.info("Starting LLM pricing scraper...")
    
    aggregator = PricingAggregator()
    data = aggregator.scrape_all()
    aggregator.save_data(data)
    
    summary = aggregator.generate_summary(data)
    logger.info(f"Scraping complete. Summary: {summary}")
    
    # Save summary
    summary_file = Path('data') / 'summary.json'
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)


if __name__ == '__main__':
    main()
