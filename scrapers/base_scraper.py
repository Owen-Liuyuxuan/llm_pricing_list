# scrapers/base_scraper.py
"""
Base scraper class for LLM pricing extraction.
Provides common functionality for all provider-specific scrapers.
"""
import re
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """Abstract base class for pricing scrapers."""
    
    def __init__(self, provider_name: str, base_url: str):
        """
        Initialize the scraper.
        
        Args:
            provider_name: Name of the LLM provider
            base_url: Base URL for the pricing page
        """
        self.provider_name = provider_name
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        
    def fetch_page(self, url: str, retries: int = 3) -> Optional[BeautifulSoup]:
        """
        Fetch and parse a webpage.
        
        Args:
            url: URL to fetch
            retries: Number of retry attempts
            
        Returns:
            BeautifulSoup object or None if failed
        """
        for attempt in range(retries):
            try:
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                return BeautifulSoup(response.content, 'lxml')
            except Exception as e:
                logger.error(f"Attempt {attempt + 1} failed for {url}: {e}")
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    return None
                    
    @abstractmethod
    def scrape(self) -> Dict:
        """
        Scrape pricing data from the provider.
        
        Returns:
            Dictionary containing pricing information
        """
        pass
    
    def normalize_price(self, price_str: str) -> float:
        """
        Normalize price string to float.
        
        Args:
            price_str: Price string (e.g., "$0.003", "¥0.01", "$5 / MTok")
            
        Returns:
            Float price value
        """
        if not price_str or price_str.strip() in ('-', '—', 'N/A', 'Not available'):
            return 0.0
        # Extract first number (handles "$5 / MTok", "$2.00, prompts <= 200k", etc.)
        match = re.search(r'[\d,]+\.?\d*', price_str.replace(',', ''))
        if match:
            try:
                return float(match.group().replace(',', ''))
            except ValueError:
                pass
        cleaned = re.sub(r'[^\d.]', '', price_str)
        try:
            return float(cleaned) if cleaned else 0.0
        except ValueError:
            return 0.0

    def parse_context_window(self, text: str) -> int:
        """
        Parse context window from text like "128K", "200K", "1M", "128000".
        
        Returns:
            Integer token count, or 0 if unparseable
        """
        if not text:
            return 0
        text = str(text).upper().replace(',', '').strip()
        match = re.search(r'(\d+(?:\.\d+)?)\s*([KM])?', text)
        if match:
            num = float(match.group(1))
            unit = match.group(2) or ''
            if unit == 'K':
                return int(num * 1000)
            if unit == 'M':
                return int(num * 1_000_000)
            return int(num)
        return 0

    def model_id_from_name(self, name: str) -> str:
        """
        Derive model_id from model name (lowercase, hyphens, no spaces).
        """
        if not name:
            return ''
        return re.sub(r'[^a-z0-9\-]', '-', name.lower().strip()).strip('-')
            
    def format_output(self, models: List[Dict]) -> Dict:
        """
        Format scraped data into standardized structure.
        
        Args:
            models: List of model pricing dictionaries
            
        Returns:
            Formatted pricing data
        """
        return {
            'provider': self.provider_name,
            'scraped_at': datetime.utcnow().isoformat(),
            'currency': 'USD',
            'models': models,
            'source_url': self.base_url
        }
