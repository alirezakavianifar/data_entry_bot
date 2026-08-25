import random
import re
import time
from abc import ABC, abstractmethod
from typing import Optional, Tuple
from playwright.sync_api import Page, Locator, TimeoutError as PlaywrightTimeoutError

from data.models import Client, RegistrationResult, RegistrationStatus
from core.logger import get_logger, capture_failure_bundle, capture_login_proof_screenshot

ALREADY_REGISTERED_PATTERNS = [

    r"looks like you['’]re already registered",
    r"already registered",
    r"account with this e-?mail (?:already )?exists",
    r"account (?:already )?exists",
    r"(?:this )?e-?mail (?:already )?exists",
    r"e-?mail (?:address )?(?:is )?already (?:registered|in use|exists|taken)",
    r"user(?:name)? already exists",
    r"duplicate account",
    r"already have an account",
    r"you (?:may )?(?:already )?have an account",
    r"(?:it )?looks like you (?:already )?have an account",
    r"account set up with this e-?mail",
    r"recovering your account",
    r"self-exclusion",
    r"unable to register due to an active self-exclusion",
    r"already opened an account on our operating license",
    r"there['’]s an issue with your account registration",
    r"issue with your account registration"
]

def extract_clean_error_message(text: str) -> str:
    """Extracts a succinct, human-readable error message from raw modal/page text."""
    if not text or not isinstance(text, str):
        return ""
    # Check for known explicit error sentences
    for pat in [
        r"(Your account is restricted[^\.\n]*[\.\n]?)",
        r"(Please do not attempt to open another [^\.\n]+ account[^\.\n]*[\.\n]?)",
        r"(Your account has been (?:restricted|suspended|closed)[^\.\n]*[\.\n]?)",
        r"(looks like you['’]re already registered[^\.\n]*[\.\n]?)",
        r"((?:it )?looks like you already have an account[^\.\n]*[\.\n]?)",
        r"(You['’]re unable to register due to an active Self-Exclusion[^\.\n]*[\.\n]?)",
        r"(There['’]s an issue with your account registration[^\.\n]*[\.\n]?)",
        r"(an? account with this [^\.\n]+ already exists)",
        r"(an? account set up with this [^\.\n]+)",
        r"((?:this )?e-?mail (?:already )?exists[^\.\n]*)",
        r"(e-?mail (?:address )?(?:is )?already (?:registered|in use|exists|taken)[^\.\n]*)",
        r"(user(?:name)? already exists[^\.\n]*)",
        r"(already registered[^\.\n]*)",
        r"(already opened an account on our operating license[^\.\n]*)",
        r"(Thank you for attempting to open an account with us[^\.\n]*\.[^\.\n]*\.)",
        r"(No addresses? found for this (?:postal code|postcode)[^\.\n]*)",
        r"(No addresses? found[^\.\n]*)",
        r"(Invalid (?:postal code|postcode)[^\.\n]*)",
        r"([^\.\n]*should not contain special characters[^\.\n]*)",
        r"(Something went wrong[^\.\n]*)",
        r"(invalid credentials[^\.\n]*)",
        r"(unable to (?:register|process)[^\.\n]*)",
        r"(please (?:check|correct) the following errors?:?[^\.\n]*)",
    ]:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()

    # Look for line after "Error" label
    lines = [l.strip() for l in text.replace(" - ", "\n").splitlines() if l.strip()]
    for idx, line in enumerate(lines):
        if line.lower() in ("error", "error:", "×", "x", "alert", "warning") and idx + 1 < len(lines):
            candidate = lines[idx + 1]
            if len(candidate) > 5 and not any(k in candidate.lower() for k in ("contact us", "cookie policy", "terms")):
                return f"{candidate}"
        elif "error" in line.lower() and len(line) > 10 and not any(k in line.lower() for k in ("racing", "greyhound", "cookie")):
            return line

    for l in lines:
        if any(k in l.lower() for k in ("already", "exists", "invalid", "failed", "error", "unable", "sorry", "cannot", "restricted")):
            return l

    return text[:160].strip()

def is_already_registered_error(text: str) -> bool:
    """Returns True if the error message indicates the client account already exists."""
    if not text or not isinstance(text, str):
        return False
    for pat in ALREADY_REGISTERED_PATTERNS:
        if re.search(pat, text, re.IGNORECASE):
            return True
    return False

PENDING_VERIFICATION_PATTERNS = [
    r"verify your email",
    r"verification (?:email|link)",
    r"activation (?:email|link)",
    r"check your (?:inbox|email)",
    r"activate your account",
    r"account (?:is )?not (?:yet )?(?:activated|verified)",
    r"email (?:has not been|is not|not) verified",
    r"more info needed",
    r"proof of id",
    r"proof of address",
    r"electoral roll",
    r"document upload",
    r"upload (?:your )?documents",
    r"kyc",
    r"verify your details",
    r"account pending verification",
    r"require email verification",
    r"email verification",
    r"account (?:is |has been )?suspended",
    r"suspended",
    r"account (?:is |has been )?locked",
    r"account (?:is |has been )?restricted",
    r"your account is restricted",
    r"restricted",
    r"do not attempt to open another",
    r"unable to open another"
]

def is_pending_verification_error(text: str) -> bool:
    """Returns True if the message indicates the account exists but requires user email or KYC verification."""
    if not text:
        return False
    for pat in PENDING_VERIFICATION_PATTERNS:
        if re.search(pat, text, re.IGNORECASE):
            return True
    return False


def human_pause(page: Page, min_sec: float = 0.5, max_sec: float = 1.5):
    """Waits for a randomized duration to simulate human reading/thinking pauses."""
    try:
        duration_ms = int(random.uniform(min_sec, max_sec) * 1000)
        page.wait_for_timeout(duration_ms)
    except Exception:
        pass


def _calculate_bezier_points(p0: Tuple[float, float], p3: Tuple[float, float], num_points: int = 15) -> list[Tuple[float, float]]:
    """Calculates smooth cubic Bezier curve points between two screen coordinates."""
    x0, y0 = p0
    x3, y3 = p3
    dx = x3 - x0
    dy = y3 - y0

    # Generate realistic control points with slight curvature
    deviation_x = dx * random.uniform(0.1, 0.4) + random.uniform(-20, 20)
    deviation_y = dy * random.uniform(0.1, 0.4) + random.uniform(-20, 20)
    
    p1 = (x0 + deviation_x, y0 + deviation_y)
    p2 = (x3 - deviation_x * 0.5, y3 - deviation_y * 0.5)

    points = []
    for i in range(num_points + 1):
        t = i / float(num_points)
        # Cubic Bezier formula: (1-t)^3*p0 + 3(1-t)^2*t*p1 + 3(1-t)*t^2*p2 + t^3*p3
        x = ((1 - t) ** 3) * p0[0] + 3 * ((1 - t) ** 2) * t * p1[0] + 3 * (1 - t) * (t ** 2) * p2[0] + (t ** 3) * p3[0]
        y = ((1 - t) ** 3) * p0[1] + 3 * ((1 - t) ** 2) * t * p1[1] + 3 * (1 - t) * (t ** 2) * p2[1] + (t ** 3) * p3[1]
        points.append((x, y))
    return points


def human_mouse_move(page: Page, target_x: float, target_y: float, steps: int = 12):
    """Moves the mouse to target coordinates along a realistic Bezier curve."""
    try:
        # Default start from current approximate position or near center
        start_x = random.randint(100, 500)
        start_y = random.randint(100, 400)
        points = _calculate_bezier_points((start_x, start_y), (target_x, target_y), num_points=steps)
        for px, py in points:
            page.mouse.move(px, py)
            page.wait_for_timeout(random.randint(5, 18))
    except Exception:
        try:
            page.mouse.move(target_x, target_y)
        except Exception:
            pass


def human_click(locator: Locator, page: Optional[Page] = None):
    """Performs a humanized click by moving to element bounding box, pausing, and pressing."""
    try:
        try:
            locator.scroll_into_view_if_needed(timeout=1500)
        except Exception:
            pass
        box = locator.bounding_box()
        if box and page:
            # Pick a target point inside the element with slight offset from center
            target_x = box["x"] + box["width"] * random.uniform(0.3, 0.7)
            target_y = box["y"] + box["height"] * random.uniform(0.3, 0.7)
            human_mouse_move(page, target_x, target_y)
            page.wait_for_timeout(random.randint(40, 100))
            page.mouse.down()
            page.wait_for_timeout(random.randint(60, 130))
            page.mouse.up()
            page.wait_for_timeout(random.randint(50, 120))
            return
    except Exception:
        pass
    # Fallback to standard click
    locator.click(force=True)


def human_scroll(page: Page, distance_y: int = 300, steps: int = 5):
    """Simulates realistic mouse-wheel scrolling with momentum easing."""
    try:
        step_distance = distance_y / steps
        for _ in range(steps):
            jitter = random.randint(-15, 15)
            page.mouse.wheel(0, step_distance + jitter)
            page.wait_for_timeout(random.randint(30, 80))
    except Exception:
        pass


def human_type(locator: Locator, text: str, page: Optional[Page] = None, min_delay_ms: int = 25, max_delay_ms: int = 75):
    """Types text character-by-character into an input element with realistic human digraph rhythms."""
    try:
        try:
            locator.scroll_into_view_if_needed(timeout=1500)
        except Exception:
            pass
        if page:
            human_click(locator, page)
        else:
            locator.click(force=True)
        locator.fill("")
        
        for idx, ch in enumerate(text):
            # Add slightly longer pause on space, dots, and at symbols
            if ch in (" ", ".", "@", "-", "_"):
                delay = random.randint(110, 220)
            elif idx > 0 and text[idx - 1] == ch:
                delay = random.randint(min_delay_ms, min_delay_ms + 25)
            else:
                delay = random.randint(min_delay_ms, max_delay_ms)
                
            locator.press_sequentially(ch, delay=delay)
            
        if page:
            page.wait_for_timeout(random.randint(80, 250))
    except Exception:
        try:
            locator.fill(text)
        except Exception:
            pass



def handle_playbook_safer_gambling_no_limit(page: Page, log=None) -> bool:
    """
    Specifically detects and physically completes the Playbook Engineering Safer Gambling
    and Deposit Limit onboarding step by ensuring 'No Deposit Limit' is selected / toggled ON
    and the Next / Save progression button is clicked until the modal is completely dismissed.
    """
    try:
        modal_selectors = [
            'aside[data-test="SignUpStepsContainer"]',
            '[data-test="SignUpStepsContainer"]',
            'legend:has-text("SAFER GAMBLING")',
            'h2:has-text("SAFER GAMBLING")',
            'h1:has-text("SAFER GAMBLING")',
            'h3:has-text("SAFER GAMBLING")',
            '[data-test*="safer-gambling"]',
            '[data-component*="SaferGambling"]',
            'aside[data-test="SignUpStepsContainer"]:has-text("SAFER GAMBLING")',
            'aside[data-test="SignUpStepsContainer"]:has-text("DEPOSIT LIMIT")',
            'aside[data-test="SignUpStepsContainer"]:has-text("deposit limit")',
            'div[class*="deposit-modal"]',
            'div:has-text("Set a deposit limit")',
            'label:has-text("deposit limit")',
            ':has-text("Would you like to set a deposit limit")',
            ':has-text("No I don\'t want to set a deposit limit")',
            ':has-text("No, I don\'t want to set a deposit limit")',
            ':has-text("No I dont want to set a deposit limit")',
            ':has-text("I do not wish to set a deposit limit")',
            ':has-text("I don\'t want to set a deposit limit")',
            ':has-text("I\'ve looked at my deposit limit")'
        ]

        is_modal_present = False
        for sel in modal_selectors:
            try:
                if page.locator(sel).first.is_visible(timeout=200):
                    is_modal_present = True
                    break
            except Exception:
                continue

        if not is_modal_present:
            return False

        if log:
            log.info("Playbook Safer Gambling / Onboarding modal detected — ensuring 'No Deposit Limit' is selected and progressing...")

        # 1. Look for explicit 'No I don't want to set a deposit limit' radio / button / label if present
        no_limit_triggers = [
            'label:has-text("No I don\'t want to set a deposit limit")',
            'span:has-text("No I don\'t want to set a deposit limit")',
            'button:has-text("No I don\'t want to set a deposit limit")',
            'div:has-text("No I don\'t want to set a deposit limit")',
            'label:has-text("No, I don\'t want to set a deposit limit")',
            'span:has-text("No, I don\'t want to set a deposit limit")',
            'button:has-text("No, I don\'t want to set a deposit limit")',
            'label:has-text("No I dont want to set a deposit limit")',
            'span:has-text("No I dont want to set a deposit limit")',
            'button:has-text("No I dont want to set a deposit limit")',
            'label:has-text("I don\'t want to set a deposit limit")',
            'span:has-text("I don\'t want to set a deposit limit")',
            'button:has-text("I don\'t want to set a deposit limit")',
            'label:has-text("I do not want to set a deposit limit")',
            'span:has-text("I do not want to set a deposit limit")',
            'button:has-text("I do not want to set a deposit limit")',
            'label:has-text("I do not wish to set a deposit limit")',
            'span:has-text("I do not wish to set a deposit limit")',
            'label:has-text("No limit")',
            'span:has-text("No limit")',
            'button:has-text("No limit")',
            '[data-test*="no-limit"]',
            'label:has-text("No deposit limit")',
            'span:has-text("No deposit limit")',
            'button:has-text("No deposit limit")',
            'label:has-text("Do not set a limit")',
            'span:has-text("Do not set a limit")',
            'label:has-text("I\'ve looked at my deposit limit")',
            'span:has-text("I\'ve looked at my deposit limit")',
            'input[value="no_limit"]',
            'input[value="no"]',
            'input[id*="no-limit"]',
            'input[type="radio"][value*="no" i]',
            'input[type="radio"][id*="no" i]'
        ]
        explicit_clicked = False
        for trig in no_limit_triggers:
            try:
                el = page.locator(trig).first
                if el.is_visible(timeout=200):
                    if log:
                        log.info(f"Selecting explicit No Limit option: {trig}")
                    el.scroll_into_view_if_needed()
                    el.click(force=True)
                    page.wait_for_timeout(300)
                    explicit_clicked = True
                    break
            except Exception:
                continue

        # 2. Handle acknowledgement switch / toggle (ensure toggle is switched ON if switch component is used)
        ack_switch_selectors = [
            '[role="switch"]',
            'button[role="switch"]',
            'span[class*="switch" i]',
            'div[class*="Switch" i]',
            'label[class*="switch" i]',
            'label:has-text("deposit limit")',
            'label:has-text("I\'ve looked at my deposit limit")',
            'input[type="checkbox"]',
            '[data-component*="Switch" i]',
            '[data-test*="switch" i]',
            '[data-test*="deposit-limit" i]',
            'span[class*="slider" i]',
            'div[class*="toggle" i]'
        ]
        toggled = explicit_clicked
        for switch_sel in ack_switch_selectors:
            try:
                switches = page.locator(switch_sel)
                cnt = switches.count()
                for i in range(cnt):
                    s = switches.nth(i)
                    if s.is_visible(timeout=200):
                        # Check checked state
                        aria_chk = s.get_attribute("aria-checked")
                        is_input_chk = False
                        try:
                            tag = s.evaluate("e => e.tagName")
                            if tag == "INPUT":
                                is_input_chk = s.is_checked()
                        except Exception:
                            pass

                        # If not already checked / true, toggle it
                        if aria_chk != "true" and not is_input_chk:
                            if log:
                                log.info(f"Toggling Safer Gambling switch ON ({switch_sel} #{i})")
                            s.scroll_into_view_if_needed()
                            s.click(force=True)
                            page.wait_for_timeout(300)
                            toggled = True
                            break
                        else:
                            if log:
                                log.info(f"Safer Gambling switch is already ON ({switch_sel} #{i})")
                            toggled = True
                            break
                if toggled:
                    break
            except Exception:
                continue

        # 3. JavaScript Fallback: Scan DOM and ensure switch / radio is toggled ON
        try:
            page.evaluate("""() => {
                const elements = Array.from(document.querySelectorAll('label, button, span, div, p, a, input[type="radio"], input[type="checkbox"], [role="switch"]'));
                const target = elements.find(el => {
                    const txt = (el.innerText || el.textContent || el.value || '').toLowerCase();
                    return (txt.includes("don't want to set a deposit limit") || 
                            txt.includes("dont want to set a deposit limit") ||
                            txt.includes("no i don't want") ||
                            txt.includes("no, i don't want") ||
                            txt.includes("no i dont want") ||
                            txt.includes("do not want to set a deposit limit") ||
                            txt.includes("do not wish to set a deposit limit") ||
                            txt.includes("i've looked at my deposit limit") ||
                            txt.includes("no deposit limit") ||
                            txt.includes("no limit"));
                });
                if (target) {
                    target.click();
                }
                const sw = document.querySelector('[role="switch"], [class*="switch" i], [class*="Switch" i], input[type="checkbox"]');
                if (sw && sw.getAttribute('aria-checked') !== 'true') {
                    sw.setAttribute('aria-checked', 'true');
                    sw.dispatchEvent(new Event('change', { bubbles: true }));
                    sw.dispatchEvent(new Event('input', { bubbles: true }));
                    sw.click();
                }
            }""")
            page.wait_for_timeout(400)
        except Exception:
            pass

        # 4. Click the progression CTA (Next / Save & Continue / Done / Confirm)
        progression_buttons = [
            'button[data-test="next-button"]',
            'button[data-test="save-button"]',
            'button[data-test="done-button"]',
            'button[data-test*="next" i]',
            'button[data-test*="save" i]',
            'button[data-test*="continue" i]',
            'button:has-text("Next")',
            'button:has-text("NEXT")',
            'button:has-text("Save & Continue")',
            'button:has-text("Save and Continue")',
            'button:has-text("Save")',
            'button:has-text("SAVE")',
            'button:has-text("Done")',
            'button:has-text("DONE")',
            'button:has-text("Finish")',
            'button:has-text("FINISH")',
            'button:has-text("Continue")',
            'button:has-text("CONTINUE")',
            'button:has-text("Confirm")',
            'button:has-text("CONFIRM")',
            'button:has-text("Agree & Join")',
            'button:has-text("Skip")',
            'button:has-text("Maybe later")',
            'a:has-text("Skip")',
            'button[type="submit"]'
        ]
        btn_clicked = False
        for btn_sel in progression_buttons:
            try:
                btn = page.locator(btn_sel).first
                if btn.is_visible(timeout=300):
                    if log:
                        log.info(f"Clicking Safer Gambling progression button: {btn_sel}")
                    btn.scroll_into_view_if_needed()
                    try:
                        btn.evaluate("b => b.removeAttribute('disabled')")
                    except Exception:
                        pass
                    btn.click(force=True)
                    page.wait_for_timeout(1500)
                    btn_clicked = True
                    break
            except Exception:
                continue

        # Fallback progression button click via JavaScript
        if not btn_clicked:
            try:
                page.evaluate("""() => {
                    const btns = Array.from(document.querySelectorAll('button, a, input[type="submit"]'));
                    const nextBtn = btns.find(b => {
                        const t = (b.innerText || b.textContent || b.value || '').trim().toLowerCase();
                        const dt = (b.getAttribute('data-test') || '').toLowerCase();
                        return ['next', 'save & continue', 'save and continue', 'save', 'done', 'finish', 'confirm', 'continue', 'agree & join', 'skip'].includes(t) ||
                               dt.includes('next') || dt.includes('save') || dt.includes('continue') || dt.includes('done');
                    });
                    if (nextBtn) {
                        nextBtn.removeAttribute('disabled');
                        nextBtn.click();
                    }
                }""")
                page.wait_for_timeout(1500)
            except Exception:
                pass

        return True
    except Exception as ex:
        if log:
            log.warning(f"Warning handling Playbook Safer Gambling modal: {ex}")
        return False


COMMON_COOKIE_SELECTORS = [


    '#onetrust-accept-btn-handler',
    '#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll',
    '#CybotCookiebotDialogBodyButtonAccept',
    'button:has-text("Accept All Cookies")',
    'button:has-text("Accept all cookies")',
    'button:has-text("Accept All")',
    'button:has-text("Allow all")',
    'button:has-text("Accept")',
    'button:has-text("I Accept")',
    'button[id*="cookie-accept"]',
    'a:has-text("Accept")',
    'button:has-text("Agree")'
]

GEOBLOCK_KEYWORDS = [
    "unavailable in your location",
    "geographical restrictions",
    "access from certain territories",
    "outside uk or ireland",
    "offer not available for your country",
    "attention required! | cloudflare",
    "sorry, you have been blocked"
]


class BaseSiteAdapter(ABC):
    """Abstract base adapter for bookmaker registration platforms."""

    def __init__(self, site_id: str, site_name: str, default_promo_url: str, requires_uk_ip: bool = True):
        self.site_id = site_id
        self.site_name = site_name
        self.default_promo_url = default_promo_url
        self.requires_uk_ip = requires_uk_ip

    def navigate(self, page: Page, promo_url: Optional[str] = None) -> bool:
        """Navigates to the promo/registration URL and checks for immediate errors."""
        url = promo_url or self.default_promo_url
        log = get_logger(site_id=self.site_id, step="navigate")
        log.info(f"Navigating to {url}")
        
        resp = page.goto(url, wait_until="domcontentloaded", timeout=25000)
        page.wait_for_timeout(2000)
        
        status = resp.status if resp else 200
        if status == 403 or self.check_geoblock(page):
            log.warning(f"Geoblock / 403 detected on {self.site_name}")
            return False
        return True

    def accept_cookies(self, page: Page) -> bool:
        """Attempts to detect and click common cookie consent banners."""
        log = get_logger(site_id=self.site_id, step="accept_cookies")
        for selector in COMMON_COOKIE_SELECTORS:
            try:
                locator = page.locator(selector).first
                if locator.is_visible(timeout=1500):
                    log.info(f"Clicking cookie banner with selector: {selector}")
                    locator.click(force=True, timeout=2000)
                    page.wait_for_timeout(1000)
                    return True
            except Exception:
                continue
        log.debug("No cookie banner detected or already accepted")
        return False

    def check_geoblock(self, page: Page) -> bool:
        """Returns True if the page contains explicit geographic restriction copy."""
        try:
            body_text = page.inner_text("body").lower()
            for kw in GEOBLOCK_KEYWORDS:
                if kw in body_text:
                    return True
        except Exception:
            pass
        return False

    @abstractmethod
    def fill_registration(self, page: Page, client: Client, password: str) -> RegistrationResult:
        """Executes the specific form interactions for account signup."""
        pass

    def execute(self, page: Page, client: Client, password: str, promo_url: Optional[str] = None) -> RegistrationResult:
        """Main lifecycle template method with complete diagnostic bundle logging."""
        log = get_logger(client_id=client.client_id, site_id=self.site_id, step="execute")
        log.info(f"Starting registration workflow for {client.full_name} ({client.email})")

        try:
            # 1. Navigate
            if not self.navigate(page, promo_url):
                bundle = capture_failure_bundle(
                    page, client.client_id, self.site_id, "navigate",
                    Exception("Geographical IP restriction or 403 forbidden detected")
                )
                return RegistrationResult(
                    client_id=client.client_id,
                    client_name=client.full_name,
                    site_id=self.site_id,
                    site_name=self.site_name,
                    status=RegistrationStatus.FAILED,
                    email=client.email,
                    error_summary=bundle.error_summary,
                    screenshot_path=bundle.screenshot_path,
                    dom_snapshot_path=bundle.dom_snapshot_path
                )

            # 2. Accept Cookies
            self.accept_cookies(page)

            # 3. Fill and Submit Registration
            result = self.fill_registration(page, client, password)
            log.info(f"Registration finished with status: {result.status.value}")
            return result

        except Exception as e:
            log.error(f"Unhandled exception during registration execution: {e}")
            bundle = capture_failure_bundle(page, client.client_id, self.site_id, "fill_registration", e)
            return RegistrationResult(
                client_id=client.client_id,
                client_name=client.full_name,
                site_id=self.site_id,
                site_name=self.site_name,
                status=RegistrationStatus.FAILED,
                email=client.email,
                password=password,
                error_summary=bundle.error_summary,
                screenshot_path=bundle.screenshot_path,
                dom_snapshot_path=bundle.dom_snapshot_path
            )

    def login(
        self,
        page: Page,
        username_or_email: str,
        password: str,
        client_id: Optional[str] = None
    ) -> tuple[bool, Optional[str], Optional[str]]:
        """
        Attempts to authenticate into the site using provided credentials and capture proof.
        Returns: (success: bool, screenshot_path: Optional[str], error_message: Optional[str])
        """
        cid = client_id or "client"

        log = get_logger(client_id=cid, site_id=self.site_id, step="login")
        log.info(f"Initiating login verification for {username_or_email} on {self.site_name}")

        try:
            # 1. Determine clean login URL (strip promo / modal params if needed)
            from urllib.parse import urlparse
            parsed = urlparse(self.default_promo_url)
            clean_base_url = f"{parsed.scheme}://{parsed.netloc}/"
            
            # If site is an FSB technology platform (e.g. planetsportbet, bresbet, starsports)
            if self.site_id in ("planetsportbet", "bresbet", "starsports"):
                target_url = f"{clean_base_url}?account=login"
            else:
                target_url = clean_base_url

            log.info(f"Navigating to login target URL: {target_url}")
            resp = page.goto(target_url, wait_until="domcontentloaded", timeout=25000)
            page.wait_for_timeout(2000)

            if self.check_geoblock(page):
                return False, None, "Geoblock detected during login navigation"

            self.accept_cookies(page)

            # 2. If login inputs not yet visible, locate and click Login / Sign In CTA
            user_inp = page.locator('input[name="email"], input[name="username"], input[type="email"], input[id*="username" i], input[id*="email" i], input[placeholder*="email" i], input[placeholder*="user" i]').first
            if not user_inp.is_visible(timeout=2500):
                # Dismiss any overlay modal first
                close_btn = page.locator('button[aria-label="Close"], button:has-text("Close"), .modal-close, button:has-text("✕"), button:has-text("X")').first
                if close_btn.is_visible(timeout=1000):
                    try:
                        close_btn.click(force=True)
                        page.wait_for_timeout(1000)
                    except Exception:
                        pass

                login_btn = page.locator('a[data-test*="login"], button[data-test*="login"], a:has-text("Login"), button:has-text("Login"), button:has-text("Log In"), a:has-text("Log In"), button:has-text("Sign In"), a:has-text("Sign In")').first
                if login_btn.is_visible(timeout=4000):
                    log.info(f"Clicking Login CTA on {self.site_name}")
                    login_btn.click(force=True)
                    page.wait_for_timeout(2000)

            # 3. Locate credentials fields
            user_inp = page.locator('input[name="email"], input[name="username"], input[type="email"], input[id*="username" i], input[id*="email" i], input[placeholder*="email" i], input[placeholder*="user" i]').first
            pwd_inp = page.locator('input[name="password"], input[type="password"], input[id*="password" i]').first

            if not user_inp.is_visible(timeout=4000) or not pwd_inp.is_visible(timeout=4000):
                bundle = capture_failure_bundle(page, cid, self.site_id, "login_inputs_missing")
                return False, bundle.screenshot_path, f"Login inputs not visible on {self.site_name}"

            log.info(f"Filling credentials for {username_or_email}")
            user_inp.fill(username_or_email)
            pwd_inp.fill(password)
            page.wait_for_timeout(500)

            # 4. Submit login form
            submit_btn = page.locator('button[type="submit"]:has-text("Login"), button[type="submit"]:has-text("Log In"), button[type="submit"]:has-text("Sign In"), button:has-text("Login"), button:has-text("Log In"), button[type="submit"]').first
            if submit_btn.is_visible(timeout=2000):
                submit_btn.click(force=True)
            else:
                pwd_inp.press("Enter")

            # 5. Wait for authentication response & state transition
            page.wait_for_timeout(5000)

            # 6. Check for dismissible welcome / KYC / Deposit limit dialogs post-login
            dismiss_btn = page.locator('button:has-text("NO, MAYBE LATER"), button:has-text("No, Maybe Later"), button:has-text("NO, THANKS"), button:has-text("No thanks"), button:has-text("Dismiss"), button:has-text("Later"), button:has-text("Maybe Later"), button:has-text("Close"), button[aria-label="Close"], [class*="modal"] button[class*="close"]').first
            if dismiss_btn.is_visible(timeout=2000):
                try:
                    dismiss_btn.click(force=True)
                    page.wait_for_timeout(1000)
                except Exception:
                    pass

            # 7. Check if Login CTA is STILL visible
            login_cta = page.locator('a[data-test="account-navigation-login-link"], a:has-text("Login"), button:has-text("Login"), a:has-text("Log In"), button:has-text("Log In")').first
            is_login_cta_visible = False
            try:
                if login_cta.is_visible(timeout=1500):
                    is_login_cta_visible = True
            except Exception:
                pass

            # 8. Check for authentic post-login user widgets
            logged_in_indicators = [
                'button:has-text("DEPOSIT")', 'a:has-text("DEPOSIT")',
                'a:has-text("Deposit")', 'button:has-text("Deposit")',
                'button:has-text("Log Out")', 'a:has-text("Log Out")',
                'button:has-text("Logout")', 'a:has-text("Logout")',
                'a:has-text("My Account")', 'button:has-text("My Account")',
                '[data-testid*="user-menu"]', '[data-component="AccountNavigation"] [data-test*="account"]',
                '.user-balance', '.account-balance', '.wallet-balance'
            ]

            has_auth_widget = False
            for selector in logged_in_indicators:
                try:
                    if page.locator(selector).first.is_visible(timeout=1000):
                        has_auth_widget = True
                        log.info(f"Authenticated session element confirmed: {selector}")
                        break
                except Exception:
                    continue

            # Check for invalid credentials / lock error banner
            error_el = page.locator('div[class*="error"]:visible, span[class*="error"]:visible, p[class*="error"]:visible, div[role="alert"]:visible, [class*="alert"]:visible, :has-text("not verified"):visible, :has-text("Invalid"):visible, :has-text("incorrect"):visible').first
            err_msg_found = None
            if error_el.is_visible(timeout=1000):
                err_text = error_el.inner_text().strip()
                if any(err_kw in err_text.lower() for err_kw in ["invalid", "incorrect", "locked", "disabled", "failed", "unrecognized", "error", "not verified"]):
                    err_msg_found = err_text

            # Check if login modal/drawer is still open
            is_login_form_open = page.locator('input[type="password"]:visible, form input#password:visible').first.is_visible(timeout=1000)

            # Strict Evaluation: Login is ONLY verified if genuine auth indicators exist, login form is closed, and no errors
            is_authenticated = has_auth_widget and not is_login_form_open and not err_msg_found

            proof_path = capture_login_proof_screenshot(page, cid, self.site_id)

            if is_authenticated:
                log.info(f"Login verified successfully for {username_or_email}! Proof saved: {proof_path}")
                return True, proof_path, None
            else:
                err_summary = err_msg_found or "Login failed: account indicators not found or credentials rejected"
                log.warning(f"Login unconfirmed: {err_summary}")
                return False, proof_path, err_summary


        except Exception as e:
            log.error(f"Exception during login verification: {e}")
            bundle = capture_failure_bundle(page, cid, self.site_id, "login_exception", e)
            return False, bundle.screenshot_path, str(e)


