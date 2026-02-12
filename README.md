# LLM Pricing Tracker

Automated daily scraper and beautiful visualization dashboard for tracking pricing across major LLM providers.

https://owen-liuyuxuan.github.io/llm_pricing_list/

## Features

- 🤖 **Multi-Provider Support**: Claude, OpenAI, Gemini, DeepSeek, Doubao
- 📊 **Beautiful Dashboard**: Interactive HTML interface with filtering and sorting
- ⏰ **Automated Updates**: GitHub Actions runs weekly scraping
- 📈 **Historical Data**: Tracks pricing changes over time
- 🔍 **Search & Filter**: Easy model comparison
- 📱 **Responsive Design**: Works on all devices

## Supported Providers

| Provider | Models | Currency | Update Frequency |
|----------|--------|----------|------------------|
| Claude (Anthropic) | 5+ models | USD | Daily |
| OpenAI | 7+ models | USD | Daily |
| Gemini (Google) | 6+ models | USD | Daily |
| DeepSeek | 4+ models | USD | Daily |
| Doubao (ByteDance) | 3+ models | CNY→USD | Daily |

## Setup

### 1. Clone Repository

```bash
git clone git@github.com:Owen-Liuyuxuan/llm_pricing_list.git
cd llm-pricing-tracker
```

### 2. Install Dependencies (UV)

This project uses [uv](https://docs.astral.sh/uv/) for dependency management.

```bash
# Install uv: https://docs.astral.sh/uv/getting-started/installation/
uv sync
```

Alternatively with pip: `pip install -r requirements.txt`

### 3. Run Locally

```bash
uv run python scrape.py
# or: python scrape.py
```

## Project Structure

```
llm-pricing-tracker/
├── .github/workflows/       # GitHub Actions workflows
├── scrapers/                # Provider-specific scrapers
│   ├── base_scraper.py     # Base scraper class
│   ├── claude_scraper.py   # Claude pricing
│   ├── openai_scraper.py   # OpenAI pricing
│   ├── gemini_scraper.py   # Gemini pricing
│   ├── deepseek_scraper.py # DeepSeek pricing
│   └── doubao_scraper.py   # Doubao pricing
├── data/                    # Pricing data storage
│   ├── current_pricing.json # Latest pricing
│   └── history/            # Historical snapshots (not in git)
├── docs/                    # GitHub Pages site
│   └── index.html          # Dashboard
├── scrape.py               # Main orchestration script
├── pyproject.toml          # Project config (UV)
├── uv.lock                  # Locked dependencies
└── requirements.txt         # Fallback for pip
```

## Data Format

```json
{
  "scraped_at": "2026-02-12T10:08:00Z",
  "providers": [
    {
      "provider": "Claude",
      "currency": "USD",
      "models": [
        {
          "model_name": "Claude 3.5 Sonnet",
          "model_id": "claude-3-5-sonnet-20241022",
          "input_price_per_mtok": 3.00,
          "output_price_per_mtok": 15.00,
          "context_window": 200000,
          "notes": "Most intelligent model"
        }
      ]
    }
  ]
}
```

## Customization

### Add New Provider

1. Create new scraper in `scrapers/`:

```python
from .base_scraper import BaseScraper

class NewProviderScraper(BaseScraper):
    def __init__(self):
        super().__init__('ProviderName', 'https://...')
    
    def scrape(self) -> Dict:
        # Implement scraping logic
        models = [...]
        return self.format_output(models)
```

2. Add to `scrape.py`:

```python
from scrapers.new_provider_scraper import NewProviderScraper

self.scrapers = [
    # ... existing scrapers
    NewProviderScraper()
]
```
