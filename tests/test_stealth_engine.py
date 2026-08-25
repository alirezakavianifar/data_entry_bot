import pytest
from unittest.mock import MagicMock
from core.browser import BrowserManager, STEALTH_EVASION_SCRIPT
from sites.base import (
    human_mouse_move,
    human_click,
    human_scroll,
    human_type,
    _calculate_bezier_points
)


def test_stealth_script_content():
    assert "navigator.webdriver" in STEALTH_EVASION_SCRIPT
    assert "window.chrome.runtime" in STEALTH_EVASION_SCRIPT
    assert "UNMASKED_VENDOR_WEBGL" in STEALTH_EVASION_SCRIPT
    assert "UNMASKED_RENDERER_WEBGL" in STEALTH_EVASION_SCRIPT
    assert "Google Inc. (NVIDIA)" in STEALTH_EVASION_SCRIPT
    assert "permissions.query" in STEALTH_EVASION_SCRIPT


def test_bezier_points_calculation():
    p0 = (100.0, 100.0)
    p3 = (500.0, 400.0)
    points = _calculate_bezier_points(p0, p3, num_points=10)
    assert len(points) == 11
    # Check start point
    assert abs(points[0][0] - 100.0) < 0.001
    assert abs(points[0][1] - 100.0) < 0.001
    # Check end point
    assert abs(points[-1][0] - 500.0) < 0.001
    assert abs(points[-1][1] - 400.0) < 0.001


def test_human_mouse_move_and_scroll():
    mock_page = MagicMock()
    human_mouse_move(mock_page, 200, 300, steps=5)
    assert mock_page.mouse.move.called

    human_scroll(mock_page, distance_y=200, steps=3)
    assert mock_page.mouse.wheel.called


def test_human_click():
    mock_page = MagicMock()
    mock_loc = MagicMock()
    mock_loc.bounding_box.return_value = {"x": 50, "y": 50, "width": 100, "height": 30}
    
    human_click(mock_loc, mock_page)
    assert mock_page.mouse.move.called
    assert mock_page.mouse.down.called
    assert mock_page.mouse.up.called


def test_browser_manager_proxy_config():
    bm = BrowserManager(proxy_server="http://127.0.0.1:8080")
    proxy_dict = bm._get_proxy_dict()
    assert proxy_dict is not None
    assert proxy_dict["server"] == "http://127.0.0.1:8080"


def test_restricted_account_pattern_matching():
    from sites.base import is_pending_verification_error, extract_clean_error_message

    betfred_restricted_msg = "Your account is restricted. Please do not attempt to open another Betfred account."
    assert is_pending_verification_error(betfred_restricted_msg) is True

    cleaned = extract_clean_error_message(betfred_restricted_msg)
    assert "Your account is restricted" in cleaned
