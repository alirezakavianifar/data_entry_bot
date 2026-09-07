import json
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse
from config.settings import PROMO_LINKS_FILE
from sites.base import BaseSiteAdapter, is_pending_verification_error
from sites.fairplaybet import FairplayBetAdapter
from sites.betfred import BetfredAdapter
from sites.quinnbet import QuinnbetAdapter
from sites.bresbet import BresbetAdapter
from sites.planetsportbet import PlanetSportBetAdapter
from sites.starsports import StarSportsAdapter
from sites.betgoodwin import BetgoodwinAdapter
from sites.betstgeorge import BetStGeorgeAdapter
from sites.affiliate_redirects import AffiliateRedirectAdapter
from sites.bettom import BetTOMAdapter
from sites.easybet import EasyBetAdapter
from sites.twentyfour7bet import TwentyFourSevenBetAdapter
from sites.paddypower import PaddyPowerAdapter
from sites.betfair import BetfairAdapter
from sites.dragonbet import DragonBetAdapter, BettingLounge2Adapter
from core.logger import get_logger

logger = get_logger(step="SiteRegistry")

DEFAULT_PROMO_LINKS: Dict[str, dict] = {
    "fairplaybet": {
        "name": "Fairplay Bet",
        "url": "https://fairplaybet.co.uk/",
        "link_type": "direct",
        "enabled": True,
        "requires_uk_ip": False
    },
    "starsports": {
        "name": "Star Sports",
        "url": "https://starsports.bet/",
        "link_type": "direct_promo",
        "enabled": True,
        "requires_uk_ip": False
    },
    "betfred": {
        "name": "Betfred",
        "url": "https://www.betfred.com/promotion/sports-onboarding-bet-10-get-10?utm_source=Betfred&utm_medium=Email&utm_campaign=BeatFredResults&p=5",
        "link_type": "direct_promo",
        "enabled": True,
        "requires_uk_ip": True
    },
    "quinnbet": {
        "name": "QuinnBet",
        "url": "https://www.quinnbet.com/uk/offers/sports-welcome-offer-ukcb50lo",
        "link_type": "direct_promo",
        "enabled": True,
        "requires_uk_ip": True
    },
    "bresbet": {
        "name": "BresBet",
        "url": "https://bresbet.com/?promo=welcomeb10g10&keyword=bresbet&btag=affelios",
        "link_type": "direct_promo",
        "enabled": True,
        "requires_uk_ip": True
    },
    "planetsportbet": {
        "name": "Planet Sport Bet",
        "url": "https://planetsportbet.com/?account=static-resource-carousel-promo-terms&promoId=12746",
        "link_type": "direct_promo",
        "enabled": True,
        "requires_uk_ip": True
    },
    "betstgeorge": {
        "name": "Bet St George",
        "url": "https://betstgeorge.com/?promo=B20G20afs&btag=6a8954687602ed96cd480d2c_699f0c4baa77fde72d25e55f&affiliateId=69c6b31e35700061a8907364",
        "link_type": "direct_promo",
        "enabled": True,
        "requires_uk_ip": True
    },
    "betgoodwin": {
        "name": "Betgoodwin",
        "url": "https://betgoodwin.co.uk/en/page/new-sportsbook-welcome-offer",
        "link_type": "direct_promo",
        "enabled": True,
        "requires_uk_ip": True
    },
    "bettinglounge2": {
        "name": "DragonBet (Betting Lounge #2)",
        "url": "https://bettinglounge.co.uk/out/ZRKfXhAAACkAStm_/?offer=betting",
        "link_type": "affiliate_redirect",
        "enabled": True,
        "requires_uk_ip": True
    },
    "dragonbet": {
        "name": "DragonBet",
        "url": "https://bettinglounge.co.uk/out/ZRKfXhAAACkAStm_/?offer=betting",
        "link_type": "affiliate_redirect",
        "enabled": True,
        "requires_uk_ip": True
    },
    "bettom": {
        "name": "BetTOM",
        "url": "https://www.bettom.com/en/sport/",
        "link_type": "direct_promo",
        "enabled": True,
        "requires_uk_ip": True
    },
    "easybet": {
        "name": "easyBet",
        "url": "https://welcome.easybet.net/EB20-Football",
        "link_type": "direct_promo",
        "enabled": True,
        "requires_uk_ip": True
    },
    "247bet": {
        "name": "247 Bet",
        "url": "https://www.247bet.com/en-gb/register",
        "link_type": "direct_promo",
        "enabled": True,
        "requires_uk_ip": True
    },
    "paddypower": {
        "name": "Paddy Power",
        "url": "https://redirect.rp-offers.com/?id=9708",
        "link_type": "affiliate_redirect",
        "enabled": True,
        "requires_uk_ip": True,
        "notes": "25-day cooling-off betting embargo applies"
    },
    "betfair": {
        "name": "Betfair",
        "url": "https://redirect.rp-offers.com/?id=8827",
        "link_type": "affiliate_redirect",
        "enabled": True,
        "requires_uk_ip": True,
        "notes": "25-day cooling-off betting embargo applies"
    }
}


def is_valid_url(url: str) -> bool:
    """Validates that a given string has a valid http/https URL structure."""
    if not url or not isinstance(url, str):
        return False
    url_clean = url.strip()
    try:
        parsed = urlparse(url_clean)
        return bool(parsed.scheme in ("http", "https") and parsed.netloc)
    except Exception:
        return False


def load_promo_config() -> Dict[str, dict]:
    """Loads promo config from JSON file or initializes from DEFAULT_PROMO_LINKS."""
    if PROMO_LINKS_FILE.exists():
        try:
            with open(PROMO_LINKS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and data:
                    return data
        except Exception as e:
            logger.error(f"Failed to load promo config from {PROMO_LINKS_FILE}: {e}")

    # If file doesn't exist or is invalid, persist defaults
    save_promo_config(DEFAULT_PROMO_LINKS)
    return dict(DEFAULT_PROMO_LINKS)


def save_promo_config(config_data: Dict[str, dict]) -> bool:
    """Safely saves promo config dictionary to config/promo_links.json."""
    try:
        PROMO_LINKS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(PROMO_LINKS_FILE, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False)
        logger.info(f"Successfully saved {len(config_data)} promo link(s) to {PROMO_LINKS_FILE}")
        return True
    except Exception as e:
        logger.error(f"Failed to save promo config to {PROMO_LINKS_FILE}: {e}")
        return False


def reset_promo_to_default(site_id: Optional[str] = None) -> Dict[str, dict]:
    """Resets a specific site or all sites to factory default configurations."""
    current = load_promo_config()
    if site_id:
        if site_id in DEFAULT_PROMO_LINKS:
            current[site_id] = dict(DEFAULT_PROMO_LINKS[site_id])
            save_promo_config(current)
            logger.info(f"Reset site '{site_id}' promo configuration to factory default")
    else:
        current = dict(DEFAULT_PROMO_LINKS)
        save_promo_config(current)
        logger.info("Reset ALL promo configurations to factory defaults")
    return current


def add_or_update_promo_link(
    site_id: str,
    name: str,
    url: str,
    enabled: bool = True,
    requires_uk_ip: bool = True,
    link_type: str = "direct_promo",
    notes: str = ""
) -> bool:
    """Adds a new promo link or updates an existing one."""
    clean_id = site_id.strip().lower().replace(" ", "_")
    if not clean_id or not url.strip():
        logger.warning(f"Invalid site_id ('{site_id}') or empty url")
        return False

    current = load_promo_config()
    current[clean_id] = {
        "name": name.strip() or clean_id,
        "url": url.strip(),
        "link_type": link_type,
        "enabled": enabled,
        "requires_uk_ip": requires_uk_ip
    }
    if notes.strip():
        current[clean_id]["notes"] = notes.strip()

    return save_promo_config(current)


def delete_custom_promo_link(site_id: str) -> bool:
    """Deletes a custom user promo link or disables it if it is a built-in default."""
    current = load_promo_config()
    if site_id not in current:
        return False

    if site_id in DEFAULT_PROMO_LINKS:
        # For default sites, disabling is safer than complete deletion
        current[site_id]["enabled"] = False
        logger.info(f"Disabled default site '{site_id}'")
    else:
        del current[site_id]
        logger.info(f"Deleted custom promo site '{site_id}'")

    return save_promo_config(current)


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
        "betstgeorge": BetStGeorgeAdapter,
        "bettinglounge1": BetStGeorgeAdapter,
        "bettinglounge2": BettingLounge2Adapter,
        "dragonbet": DragonBetAdapter,
        "bettom": BetTOMAdapter,
        "easybet": EasyBetAdapter,
        "247bet": TwentyFourSevenBetAdapter,
        "paddypower": PaddyPowerAdapter,
        "betfair": BetfairAdapter,
    }

    for site_id, site_cfg in config.items():
        if filter_sites and site_id not in filter_sites and site_cfg.get("name", "").lower() not in [s.lower() for s in filter_sites]:
            continue

        if enabled_only and not site_cfg.get("enabled", True):
            continue

        url = site_cfg.get("url", "")
        name = site_cfg.get("name", site_id)
        requires_uk_ip = site_cfg.get("requires_uk_ip", True)

        if site_id in adapter_classes:
            adapter = adapter_classes[site_id](promo_url=url)
        else:
            adapter = AffiliateRedirectAdapter(site_id=site_id, site_name=name, promo_url=url)

        # Update dynamic attributes
        adapter.site_id = site_id
        adapter.site_name = name
        adapter.default_promo_url = url
        adapter.requires_uk_ip = requires_uk_ip

        adapters.append(adapter)

    return adapters
