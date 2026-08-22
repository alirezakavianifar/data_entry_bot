import pytest
from pathlib import Path
from sites import (
    DEFAULT_PROMO_LINKS,
    load_promo_config,
    save_promo_config,
    reset_promo_to_default,
    add_or_update_promo_link,
    delete_custom_promo_link,
    is_valid_url,
    get_site_adapters
)


def test_is_valid_url():
    assert is_valid_url("https://fairplaybet.co.uk/") is True
    assert is_valid_url("http://example.com/promo?id=123") is True
    assert is_valid_url("ftp://example.com") is False
    assert is_valid_url("invalid-url") is False
    assert is_valid_url("") is False
    assert is_valid_url(None) is False


def test_load_promo_config():
    config = load_promo_config()
    assert isinstance(config, dict)
    assert "fairplaybet" in config
    assert "url" in config["fairplaybet"]
    assert config["fairplaybet"]["enabled"] is True


def test_add_and_delete_custom_promo(tmp_path, monkeypatch):
    test_promo_file = tmp_path / "promo_links.json"
    import sites
    monkeypatch.setattr(sites, "PROMO_LINKS_FILE", test_promo_file)

    # 1. Add new custom link
    ok = add_or_update_promo_link(
        site_id="custom_affiliate",
        name="Custom Affiliate 1",
        url="https://affiliate.example.com/out/123",
        enabled=True,
        requires_uk_ip=True,
        link_type="affiliate_redirect",
        notes="Testing notes"
    )
    assert ok is True

    cfg = load_promo_config()
    assert "custom_affiliate" in cfg
    assert cfg["custom_affiliate"]["name"] == "Custom Affiliate 1"
    assert cfg["custom_affiliate"]["url"] == "https://affiliate.example.com/out/123"

    # 2. Update existing link
    ok = add_or_update_promo_link(
        site_id="custom_affiliate",
        name="Custom Affiliate Updated",
        url="https://affiliate.example.com/out/456",
        enabled=False
    )
    assert ok is True
    cfg = load_promo_config()
    assert cfg["custom_affiliate"]["name"] == "Custom Affiliate Updated"
    assert cfg["custom_affiliate"]["enabled"] is False

    # 3. Delete custom link
    deleted = delete_custom_promo_link("custom_affiliate")
    assert deleted is True
    cfg = load_promo_config()
    assert "custom_affiliate" not in cfg


def test_reset_promo_to_default(tmp_path, monkeypatch):
    test_promo_file = tmp_path / "promo_links.json"
    import sites
    monkeypatch.setattr(sites, "PROMO_LINKS_FILE", test_promo_file)

    # Modify a default site URL
    add_or_update_promo_link(
        site_id="betfred",
        name="Betfred Modified",
        url="https://www.betfred.com/custom-promo"
    )
    cfg = load_promo_config()
    assert cfg["betfred"]["url"] == "https://www.betfred.com/custom-promo"

    # Reset single site
    reset_promo_to_default("betfred")
    cfg = load_promo_config()
    assert cfg["betfred"]["url"] == DEFAULT_PROMO_LINKS["betfred"]["url"]

    # Modify multiple and reset all
    add_or_update_promo_link("betfred", "Betfred", "https://custom1.com")
    add_or_update_promo_link("quinnbet", "QuinnBet", "https://custom2.com")
    reset_promo_to_default(None)
    cfg = load_promo_config()
    assert cfg["betfred"]["url"] == DEFAULT_PROMO_LINKS["betfred"]["url"]
    assert cfg["quinnbet"]["url"] == DEFAULT_PROMO_LINKS["quinnbet"]["url"]


def test_get_site_adapters_with_custom_url(tmp_path, monkeypatch):
    test_promo_file = tmp_path / "promo_links.json"
    import sites
    monkeypatch.setattr(sites, "PROMO_LINKS_FILE", test_promo_file)

    custom_url = "https://fairplaybet.co.uk/promo-2026"
    add_or_update_promo_link(
        site_id="fairplaybet",
        name="Fairplay Bet",
        url=custom_url,
        enabled=True
    )

    adapters = get_site_adapters(filter_sites=["fairplaybet"])
    assert len(adapters) == 1
    assert adapters[0].default_promo_url == custom_url
