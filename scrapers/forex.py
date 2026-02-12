"""
Currency exchange rate lookup using forex-python.
Runs on each scrape to get dynamic CNY->USD rate.
"""
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Fallback when API fails
CNY_TO_USD_FALLBACK = 1 / 7.2


def get_cny_to_usd() -> float:
    """
    Fetch current CNY to USD rate (how many USD per 1 CNY).
    Falls back to ~1/7.2 if forex-python unavailable or API fails.
    """
    try:
        from forex_python.converter import CurrencyRates
        c = CurrencyRates()
        # get_rate(base, dest) = dest per 1 base → CNY per 1 USD
        usd_per_cny = c.get_rate('CNY', 'USD')
        if usd_per_cny and usd_per_cny > 0:
            logger.info(f"Forex: 1 CNY = {usd_per_cny:.4f} USD (1 USD = {1/usd_per_cny:.1f} CNY)")
            return usd_per_cny
    except ImportError:
        logger.warning("forex-python not installed; using fallback CNY rate")
    except Exception as e:
        logger.warning(f"Forex API failed ({e}); using fallback CNY rate")
    return CNY_TO_USD_FALLBACK
