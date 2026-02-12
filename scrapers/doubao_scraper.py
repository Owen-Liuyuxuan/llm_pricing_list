# scrapers/doubao_scraper.py
"""
Scraper for Doubao (ByteDance/Volcengine) pricing.
Parses https://www.volcengine.com/docs/82379/1544106?lang=zh

Note: Volcengine docs are a React SPA. Content may be in initial HTML or
loaded dynamically. This scraper tries multiple parsing strategies.

On each run: fetches the page, saves it to data/doubao_snapshot.html,
then parses from that file (enables inspection and JS-rendered content
if fetched externally).
"""
import json
import re
import time
from pathlib import Path
from typing import Dict, List, Any, Optional
from bs4 import BeautifulSoup

from .base_scraper import BaseScraper, logger

# Snapshot path: saved on each run, then parsed from file
DOUBAO_SNAPSHOT_PATH = Path('data') / 'doubao_snapshot.html'


# Fallback CNY->USD when forex-python unavailable
CNY_TO_USD_FALLBACK = 1 / 7.2


class DoubaoScraper(BaseScraper):
    """Scraper for Doubao pricing information."""

    def __init__(self, cny_to_usd: Optional[float] = None):
        super().__init__(
            provider_name='Doubao',
            base_url='https://www.volcengine.com/docs/82379/1544106?lang=zh'
        )
        self.cny_to_usd = cny_to_usd if cny_to_usd and cny_to_usd > 0 else CNY_TO_USD_FALLBACK

    def scrape(self) -> Dict:
        """
        Scrape Doubao pricing data.
        1. Fetch page and save to data/doubao_snapshot.html
        2. Parse from the saved file
        Dynamically extracts models from tables or embedded data.
        """
        logger.info(f"Scraping {self.provider_name} pricing...")

        soup = self._fetch_and_save_then_parse()
        if not soup:
            logger.error(f"Failed to fetch or load {self.provider_name} pricing page")
            return self.format_output([])

        models = self._parse_pricing(soup)
        if models:
            result = self.format_output(models)
            result['currency'] = 'USD (converted from CNY)'
            result['exchange_rate'] = f'1 USD = {1/self.cny_to_usd:.1f} CNY'
            result['cny_to_usd_rate'] = self.cny_to_usd
            return result
        return self.format_output([])

    def _fetch_and_save_then_parse(self) -> Optional[BeautifulSoup]:
        """
        Fetch the Doubao pricing page, save to data/doubao_snapshot.html,
        then parse from that file.
        """
        snapshot_path = Path(DOUBAO_SNAPSHOT_PATH)
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)

        # Fetch and save
        for attempt in range(3):
            try:
                response = self.session.get(self.base_url, timeout=30)
                response.raise_for_status()
                with open(snapshot_path, 'wb') as f:
                    f.write(response.content)
                logger.info(f"Saved Doubao page to {snapshot_path}")
                break
            except Exception as e:
                logger.error(f"Attempt {attempt + 1} failed for {self.base_url}: {e}")
                if attempt < 2:
                    time.sleep(2 ** attempt)
                else:
                    # Fallback: use existing snapshot if fetch failed
                    if snapshot_path.exists():
                        logger.warning("Using existing snapshot (fetch failed)")
                    else:
                        return None

        if not snapshot_path.exists():
            return None

        # Read from saved file and parse
        with open(snapshot_path, 'rb') as f:
            return BeautifulSoup(f.read(), 'lxml')

    def _parse_pricing(self, soup: BeautifulSoup) -> List[Dict]:
        """
        Try multiple strategies to extract pricing:
        1. Parse HTML tables with model names and yuan prices
        2. Parse _ROUTER_DATA or other embedded JSON for doc content
        3. Regex search for price patterns (元/千tokens, etc.)
        """
        models = []

        # Strategy 1: HTML tables
        models = self._parse_tables(soup)
        if models:
            return models

        # Strategy 2: _ROUTER_DATA embedded content
        models = self._parse_router_data(soup)
        if models:
            return models

        # Strategy 3: Regex on raw HTML for common Doubao price patterns
        models = self._parse_price_patterns(str(soup))
        if models:
            return models

        logger.warning(
            f"Could not extract pricing from {self.provider_name} page. "
            "Content may be loaded dynamically (SPA). Consider using Selenium."
        )
        return []

    def _parse_tables(self, soup: BeautifulSoup) -> List[Dict]:
        """Parse HTML tables containing model names and prices in 元."""
        models = []
        for table in soup.find_all('table'):
            rows = table.find_all('tr')
            if len(rows) < 2:
                continue

            headers = [th.get_text(strip=True) for th in rows[0].find_all(['th', 'td'])]
            header_str = ' '.join(headers)
            # Look for price-related headers (输入/输出/元/价格)
            if not any(k in header_str for k in ['元', '价格', '输入', '输出', 'input', 'output', 'price']):
                continue

            col_input = col_output = col_model = -1
            for i, h in enumerate(headers):
                hl = h.lower()
                if '模型' in h or 'model' in hl:
                    col_model = i
                elif '输入' in h or 'input' in hl:
                    col_input = i
                elif '输出' in h or 'output' in hl:
                    col_output = i
                elif '元' in h and col_input < 0:
                    col_input = i
                elif '元' in h and col_output < 0 and col_input >= 0:
                    col_output = i

            if col_model < 0:
                col_model = 0

            for tr in rows[1:]:
                cells = tr.find_all(['td', 'th'])
                if len(cells) <= max(col_model, col_input, col_output):
                    continue
                model_name = cells[col_model].get_text(strip=True) if col_model >= 0 else ''
                if not model_name or len(model_name) < 2:
                    continue

                in_cny = self._extract_yuan(cells[col_input].get_text()) if col_input >= 0 else 0
                out_cny = self._extract_yuan(cells[col_output].get_text()) if col_output >= 0 else 0
                if in_cny == 0 and out_cny == 0:
                    continue

                models.append(self._doubao_model(
                    model_name, in_cny, out_cny
                ))
        return models

    def _extract_yuan(self, text: str) -> float:
        """Extract price in CNY from text like '0.8元/千tokens' or '¥0.8'."""
        if not text:
            return 0.0
        # Match 0.8 or 0.80 or 5.0 before 元 or ¥
        match = re.search(r'[¥￥]?\s*([\d.]+)\s*元?|([\d.]+)\s*元', text)
        if match:
            return float(match.group(1) or match.group(2) or 0)
        return self.normalize_price(text)

    def _doubao_model(
        self, model_name: str, input_cny: float, output_cny: float
    ) -> Dict:
        """Build a Doubao model entry with USD conversion."""
        return {
            'model_name': model_name,
            'model_id': self.model_id_from_name(model_name),
            'input_price_per_mtok': round(input_cny * self.cny_to_usd, 4),
            'output_price_per_mtok': round(output_cny * self.cny_to_usd, 4),
            'context_window': 128000,
            'notes': f'CNY: ¥{input_cny}/¥{output_cny} per 1M tokens',
            'original_currency': 'CNY',
            'original_input_price': input_cny,
            'original_output_price': output_cny
        }

    def _parse_router_data(self, soup: BeautifulSoup) -> List[Dict]:
        """
        Extract doc content from window._ROUTER_DATA.
        Pricing tables are in loaderData as markdown (|模型名称|条件|输入|输出|).
        """
        raw_html = str(soup)
        match = re.search(r'window\._ROUTER_DATA\s*=\s*', raw_html)
        if not match:
            return []

        try:
            rest = raw_html[match.end():]
            data, _ = json.JSONDecoder().raw_decode(rest)
            loader = data.get('loaderData') or {}
            md_content = self._find_md_content(loader)
            if md_content:
                return self._parse_markdown_tables(md_content)
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.debug(f"Failed to parse _ROUTER_DATA: {e}")
        return []

    def _find_md_content(self, loader: Dict) -> str:
        """Locate curDoc.MDContent in loaderData (key may vary)."""
        for key, val in loader.items():
            if isinstance(val, dict):
                if 'curDoc' in val:
                    cur = val['curDoc']
                    if isinstance(cur, dict) and cur.get('MDContent'):
                        return cur['MDContent']
                found = self._find_md_content(val)
                if found:
                    return found
        return ''

    def _parse_markdown_tables(self, md: str) -> List[Dict]:
        """
        Parse markdown tables with 模型名称, 输入, 输出.
        Rows with ^^ continue the previous model. Uses 元/百万token.
        """
        models_dict: Dict[str, Dict] = {}  # model_id -> best (input, output)
        seen = set()

        # Split into table blocks (each starts with |模型名称 or similar)
        blocks = re.split(r'\n\n+', md)
        for block in blocks:
            if '|模型名称' not in block or '元' not in block or '|---' not in block:
                continue
            rows = [r.strip() for r in block.split('\n') if r.strip().startswith('|')]
            if len(rows) < 2:
                continue
            # Parse header to get column indices
            header = rows[0].replace('\\', '')
            sep_idx = -1
            for i, r in enumerate(rows):
                if re.match(r'^\|[-:\s|]+\|', r):
                    sep_idx = i
                    break
            if sep_idx < 0:
                continue
            headers = [c.strip() for c in rows[0].split('|')[1:-1]]
            col_model = col_input = col_output = -1
            for i, h in enumerate(headers):
                if '模型' in h or 'model' in h.lower():
                    col_model = i
                if h and ('输入' in h or '输入' == h.strip()):
                    if '缓存' not in h:
                        col_input = i
                if h and ('输出' in h or '输出' == h.strip()):
                    col_output = i
            if col_model < 0:
                col_model = 0
            if col_input < 0 or col_output < 0:
                continue

            current_model = ''
            for r in rows[sep_idx + 1:]:
                cells = [c.strip() for c in r.split('|')[1:-1]]
                if len(cells) <= max(col_model, col_input, col_output):
                    continue
                model_cell = cells[col_model]
                if model_cell and not model_cell.startswith('^^'):
                    current_model = model_cell.replace('\\-', '-').strip()
                if not current_model:
                    continue
                if '不支持' in (cells[col_input] if col_input < len(cells) else '') or \
                   '不支持' in (cells[col_output] if col_output < len(cells) else ''):
                    continue
                in_val = self._extract_yuan_from_cell(
                    cells[col_input] if col_input < len(cells) else '')
                out_val = self._extract_yuan_from_cell(
                    cells[col_output] if col_output < len(cells) else '')
                if in_val <= 0 and out_val <= 0:
                    continue
                mid = self.model_id_from_name(current_model)
                if mid not in models_dict or (in_val > 0 and out_val > 0):
                    models_dict[mid] = (current_model, in_val, out_val)
                elif in_val > 0 or out_val > 0:
                    cur = models_dict[mid]
                    ni = cur[1] if cur[1] > 0 else in_val
                    no = cur[2] if cur[2] > 0 else out_val
                    models_dict[mid] = (current_model, ni, no)

        return [
            self._doubao_model(name, inp, out)
            for _, (name, inp, out) in models_dict.items()
            if inp > 0 or out > 0
        ]

    def _extract_yuan_from_cell(self, cell: str) -> float:
        """Extract number from cell (e.g. '0.80 ', '2.00', '不支持')."""
        if not cell or '不支持' in cell:
            return 0.0
        m = re.search(r'([\d.]+)', cell)
        return float(m.group(1)) if m else 0.0

    def _extract_from_loader_data(self, data: Dict) -> List[Dict]:
        """Fallback: recursively search loaderData for pricing strings."""
        models = []
        loader = data.get('loaderData') or {}

        def search(obj: Any, depth: int = 0) -> None:
            if depth > 10:
                return
            if isinstance(obj, str) and '|模型名称' in obj and '元' in obj:
                models.extend(self._parse_markdown_tables(obj))
            elif isinstance(obj, dict):
                for v in obj.values():
                    search(v, depth + 1)
            elif isinstance(obj, list):
                for v in obj:
                    search(v, depth + 1)

        search(loader)
        return models

    def _parse_price_patterns(self, html: str) -> List[Dict]:
        """
        Regex-based extraction for patterns like:
        - 豆包-pro-32k: 0.8元/千tokens 输入, 2.0元/千tokens 输出
        - Model name followed by yuan prices
        """
        models = []
        # Pattern: model name (alphanumeric, hyphen) then price info
        # Common: 元/千tokens or 元/万tokens - we need per 1M so: 元/千 = *1000 for 1M
        pattern = re.compile(
            r'([a-zA-Z0-9\u4e00-\u9fff\-]+(?:pro|lite|32k|128k)?)\s*[：:]\s*'
            r'([\d.]+)\s*元[\/／]?[^\d]*[\d]*\s*[千万]?token[^,，]*[，,]?\s*'
            r'([\d.]+)\s*元[\/／]?[^\d]*[\d]*\s*[千万]?token',
            re.IGNORECASE
        )
        for m in pattern.finditer(html):
            name, in_yuan, out_yuan = m.groups()
            in_cny = float(in_yuan)
            out_cny = float(out_yuan)
            if in_cny > 0 or out_cny > 0:
                models.append(self._doubao_model(name.strip(), in_cny, out_cny))
        return models
