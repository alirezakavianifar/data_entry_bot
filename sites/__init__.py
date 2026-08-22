import json
from pathlib import Path
from typing import Dict, List, Optional
from config.settings import PROMO_LINKS_FILE
from sites.base import BaseSiteAdapter, is_pending_verification_error
from sites.fairplaybet import FairplayBetAdapter
from sites.betfred import BetfredAdapter
from sites.quinnbet import QuinnbetAdapter
from sites.bresbet import BresbetAdapter
from sites.planetsportbet import PlanetSportBetAdapter
from sites.starsports import StarSportsAdapter
from sites.betgoodwin import BetgoodwinAdapter
from sites.affiliate_redirects import AffiliateRedirectAdapter
from core.logger import get_logger

logger = get_logger(step="SiteRegistry")


def load_promo_config() -> Dict[str, dict]:
    if PROMO_LINKS_FILE.exists():
        try:
            with open(PROMO_LINKS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load promo config from {PROMO_LINKS_FILE}: {e}")
    return {}


def get_site_adapters(filter_sites: Optional[List[str]] = None, enabled_only: bool = True) -> List[BaseSiteAdapter]:
    """Returns initialized site adapters based on config/promo_links.json and optional filters."""
    config = load_promo_config()
    adapters: List[BaseSiteAdapter] = []

    # Map of custom adapter classes
    adapter_classes = {
        "fairplaybet": FairplayBetAdapter,
        "betfred": BetfredAdapter,
        "quinnbet": QuinnbetAdapter,
        "bresbet": BresbetAdapter,
        "planetsportbet": PlanetSportBetAdapter,
        "starsports": StarSportsAdapter,
        "betgoodwin": BetgoodwinAdapter,
    }

    for site_id, site_cfg in config.items():
        if filter_sites and site_id not in filter_sites and site_cfg.get("name", "").lower() not in [s.lower() for s in filter_sites]:
            continue

        if enabled_only and not site_cfg.get("enabled", True):
            continue

        url = site_cfg.get("url", "")
        name = site_cfg.get("name", site_id)

        if site_id in adapter_classes:
            adapter = adapter_classes[site_id](promo_url=url)
        else:
            adapter = AffiliateRedirectAdapter(site_id=site_id, site_name=name, promo_url=url)

        adapters.append(adapter)

    return adapters
