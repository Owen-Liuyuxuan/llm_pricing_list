# LLM Pricing Tracker

Automated daily scraper and beautiful visualization dashboard for tracking pricing across major LLM providers.

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
git clone https://github.com/yourusername/llm-pricing-tracker.git
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

### 4. Enable GitHub Pages

1. Go to repository Settings → Pages
2. Set source to "gh-pages" branch
3. Your dashboard will be available at: `https://yourusername.github.io/llm-pricing-tracker/`

### 5. Configure GitHub Actions

The workflow runs:
- **Weekly** on Sunday at 00:00 UTC
- **Manual trigger** via Actions tab → "Run workflow"

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

### Modify Scraping Schedule

Edit `.github/workflows/scrape-pricing.yaml`:

```yaml
schedule:
  # Run weekly on Sunday at 00:00 UTC
  - cron: '0 0 * * 0'
```

## Development

### Run Tests

```bash
python -m pytest tests/
```

### Lint Code

```bash
black scrapers/ scrape.py
flake8 scrapers/ scrape.py
mypy scrapers/ scrape.py
```

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## License

MIT License - see LICENSE file for details

## Acknowledgments

- Pricing data from official provider documentation
- Built with Python, BeautifulSoup, and GitHub Actions
- Dashboard uses vanilla JavaScript (no frameworks)

## Roadmap

- [ ] Add more providers (Cohere, Mistral, etc.)
- [ ] Historical price change graphs
- [ ] Email notifications for price changes
- [ ] API endpoint for programmatic access
- [ ] Cost calculator tool
- [ ] Multi-currency support

## Support

For issues or questions:
- Open an issue on GitHub
- Check existing issues for solutions
- Contribute fixes via Pull Requests
```

## Usage Instructions

### Quick Start

1. **Create the repository structure**:
```bash
mkdir -p llm-pricing-tracker/{.github/workflows,scrapers,data/history,docs}
cd llm-pricing-tracker
```

2. **Copy all the code files** into their respective locations

3. **Initialize git and push to GitHub**:
```bash
git init
git add .
git commit -m "Initial commit: LLM pricing tracker"
git branch -M main
git remote add origin https://github.com/yourusername/llm-pricing-tracker.git
git push -u origin main
```

4. **Enable GitHub Pages**:
   - Go to Settings → Pages
   - Source: Deploy from branch `gh-pages`
   - Wait for first workflow run to create the branch

5. **Access your dashboard**:
   - Visit: `https://yourusername.github.io/llm-pricing-tracker/`

### Key Features

✅ **Automated Scraping**: Runs weekly via GitHub Actions (or manual trigger)  
✅ **Beautiful UI**: Modern, responsive dashboard with gradients and animations  
✅ **Real-time Filtering**: Search, sort, and filter by provider  
✅ **Historical Tracking**: Saves daily snapshots for trend analysis  
✅ **Multi-Provider**: Covers 5 major LLM providers  
✅ **No Backend Required**: Pure static site on GitHub Pages  
✅ **Easy to Extend**: Modular scraper architecture  

The system is production-ready and follows best practices for Python code (type hints, docstrings, error handling) and is compatible with Ubuntu 22.04 as requested!