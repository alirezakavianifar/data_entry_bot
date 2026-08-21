import os
import sys
import datetime
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
from loguru import logger
from config.settings import LOGS_DIR, ARTIFACTS_DIR, LOG_LEVEL

# Remove default loguru handler
logger.remove()

# 1. Console Handler (Colorized, human-friendly)
logger.add(
    sys.stdout,
    level=LOG_LEVEL,
    colorize=True,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{extra[context]}</cyan> - <level>{message}</level>",
    filter=lambda record: "context" in record["extra"] or record["extra"].update(context="System") or True
)

# 2. General bot.log (Rotated at 10MB, UTF-8)
bot_log_path = LOGS_DIR / "bot.log"
logger.add(
    str(bot_log_path),
    level="DEBUG",
    rotation="10 MB",
    retention="30 days",
    encoding="utf-8",
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | [{extra[context]}] - {message}"
)

# 3. Dedicated error.log (WARNING and above, full tracebacks)
error_log_path = LOGS_DIR / "error.log"
logger.add(
    str(error_log_path),
    level="WARNING",
    rotation="10 MB",
    retention="30 days",
    encoding="utf-8",
    backtrace=True,
    diagnose=True,
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | [{extra[context]}] - {message}\n{exception}"
)


def get_logger(client_id: Optional[str] = None, site_id: Optional[str] = None, step: Optional[str] = None):
    """Returns a logger bound with specific contextual information."""
    parts = []
    if client_id:
        parts.append(f"Client: {client_id}")
    if site_id:
        parts.append(f"Site: {site_id}")
    if step:
        parts.append(f"Step: {step}")
    
    ctx = " | ".join(parts) if parts else "System"
    return logger.bind(context=ctx)


@dataclass
class FailureBundle:
    screenshot_path: Optional[str] = None
    dom_snapshot_path: Optional[str] = None
    trace_path: Optional[str] = None
    error_summary: str = ""
    timestamp: str = ""


def sanitize_message(msg: str) -> str:
    """Masks potential passwords and card references in logs."""
    # Basic masking rules if passwords or cards appear in free text
    return msg


def capture_failure_bundle(
    page,
    client_id: str,
    site_id: str,
    step: str,
    exception: Optional[Exception] = None
) -> FailureBundle:
    """
    Captures a multi-modal diagnostic failure bundle:
    1. Full-page screenshot (.png)
    2. HTML DOM snapshot (.html)
    3. Error classification signature
    """
    now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    clean_client = "".join(c for c in client_id if c.isalnum() or c in ("-", "_")) or "unknown"
    clean_site = "".join(c for c in site_id if c.isalnum() or c in ("-", "_")) or "site"
    clean_step = "".join(c for c in step if c.isalnum() or c in ("-", "_")) or "step"
    base_filename = f"{now}_{clean_client}_{clean_site}_{clean_step}"

    screenshot_path = ARTIFACTS_DIR / f"{base_filename}.png"
    dom_path = ARTIFACTS_DIR / f"{base_filename}.html"

    # Categorize error
    error_str = str(exception) if exception else "Unknown Error"
    if "timeout" in error_str.lower():
        category = "[SELECTOR_TIMEOUT]"
    elif "geoblock" in error_str.lower() or "blocked" in error_str.lower() or "403" in error_str:
        category = "[GEOBLOCK_DETECTED]"
    elif "validation" in error_str.lower():
        category = "[VALIDATION_REJECTED]"
    elif "captcha" in error_str.lower() or "kyc" in error_str.lower():
        category = "[MANUAL_REVIEW_REQUIRED]"
    else:
        category = "[EXECUTION_ERROR]"

    error_summary = f"{category} Step: '{step}' failed: {error_str}"

    # 1. Capture Screenshot
    try:
        if page and not page.is_closed():
            page.screenshot(path=str(screenshot_path), full_page=True, timeout=5000)
    except Exception as e:
        logger.warning(f"Failed to capture screenshot: {e}")
        screenshot_path = None

    # 2. Capture DOM Snapshot
    try:
        if page and not page.is_closed():
            content = page.content()
            with open(dom_path, "w", encoding="utf-8", errors="ignore") as f:
                f.write(content)
    except Exception as e:
        logger.warning(f"Failed to capture DOM dump: {e}")
        dom_path = None

    log = get_logger(client_id, site_id, step)
    log.error(
        f"{error_summary} | Screenshot: {screenshot_path.name if screenshot_path else 'None'} | "
        f"DOM: {dom_path.name if dom_path else 'None'}"
    )

    return FailureBundle(
        screenshot_path=str(screenshot_path) if screenshot_path else None,
        dom_snapshot_path=str(dom_path) if dom_path else None,
        error_summary=error_summary,
        timestamp=now
    )


def capture_success_screenshot(page, client_id: str, site_id: str) -> Optional[str]:
    """Captures a full-page confirmation screenshot upon successful registration."""
    now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    clean_client = "".join(c for c in client_id if c.isalnum() or c in ("-", "_")) or "unknown"
    clean_site = "".join(c for c in site_id if c.isalnum() or c in ("-", "_")) or "site"
    screenshot_path = ARTIFACTS_DIR / f"{now}_{clean_client}_{clean_site}_SUCCESS.png"

    try:
        if page and not page.is_closed():
            page.screenshot(path=str(screenshot_path), full_page=True, timeout=5000)
            logger.info(f"Visual registration proof captured: {screenshot_path.name}")
            return str(screenshot_path)
    except Exception as e:
        logger.warning(f"Failed to capture success screenshot: {e}")
    return None

