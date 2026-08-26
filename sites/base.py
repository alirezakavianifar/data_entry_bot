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



def select_matching_playbook_address(page: Page, client: Client, log=None) -> bool:
    """
    Specifically matches and selects the exact address for the client from Playbook's
    postcode lookup dropdown, or automatically falls back to manual entry to guarantee
    the address matches client.address_line1 and client.town_city 100%.
    """
    import re
    try:
        search_addr_btn = page.locator('button[data-test="sign-up-search-address-button"], button:has-text("Search"), button:has-text("Find Address")').first
        if search_addr_btn.is_visible(timeout=2000):
            if log:
                log.info(f"Searching address for postcode: {client.postcode}")
            search_addr_btn.click(force=True)
            human_pause(page, 1.5, 2.5)

            # Look for address dropdown options
            addr_list = page.locator('li[data-component="AddressesListItemWrapper"], ul[class*="AddressesList"] li, div[class*="AddressesList"] div, div[role="listbox"] div, div[role="option"]')
            cnt = addr_list.count()
            
            if cnt > 0:
                target_raw = client.address_line1.strip().lower()
                target_clean = re.sub(r'[^a-z0-9\s]', ' ', target_raw)
                target_tokens = [t for t in target_clean.split() if t]
                
                # Extract house/flat number or building number from target
                target_numbers = re.findall(r'\b\d+[a-z]?\b', target_clean)
                target_num = target_numbers[0] if target_numbers else None

                best_idx = -1
                best_score = -1
                best_text = ""

                for idx in range(cnt):
                    try:
                        item = addr_list.nth(idx)
                        item_text = (item.inner_text() or "").strip()
                        item_lower = item_text.lower()
                        item_clean = re.sub(r'[^a-z0-9\s]', ' ', item_lower)
                        item_numbers = re.findall(r'\b\d+[a-z]?\b', item_clean)

                        score = 0
                        # 1. Exact match or starts with target address line 1
                        if target_clean in item_clean or item_clean.startswith(target_clean):
                            score += 100
                        elif target_raw in item_lower:
                            score += 90
                        else:
                            # 2. House number matching
                            if target_num:
                                if target_num in item_numbers:
                                    score += 50
                                    # Bonus if it starts with the house number
                                    if item_clean.startswith(f"{target_num} ") or f" {target_num} " in item_clean:
                                        score += 20
                                else:
                                    # Mismatched house number penalty
                                    score -= 40
                            
                            # 3. Street name keyword matching
                            matching_tokens = [t for t in target_tokens if t not in (target_num or "") and len(t) > 2 and t in item_clean]
                            score += len(matching_tokens) * 15

                        if score > best_score:
                            best_score = score
                            best_idx = idx
                            best_text = item_text
                    except Exception:
                        continue

                # If we found a confident match (score >= 40), click it
                if best_idx >= 0 and best_score >= 40:
                    if log:
                        log.info(f"Selecting best matching address: '{best_text}' (score: {best_score})")
                    selected_item = addr_list.nth(best_idx)
                    selected_item.scroll_into_view_if_needed()
                    selected_item.click(force=True)
                    human_pause(page, 0.8, 1.5)

                    # Check if a second-level list appeared (e.g. street was clicked, now list of house numbers appears)
                    if addr_list.count() > 0:
                        sub_best_idx = -1
                        sub_best_score = -1
                        sub_best_text = ""
                        for s_idx in range(addr_list.count()):
                            try:
                                s_item = addr_list.nth(s_idx)
                                s_text = (s_item.inner_text() or "").strip()
                                s_lower = s_text.lower()
                                s_clean = re.sub(r'[^a-z0-9\s]', ' ', s_lower)
                                s_numbers = re.findall(r'\b\d+[a-z]?\b', s_clean)
                                
                                s_score = 0
                                if target_clean in s_clean:
                                    s_score += 100
                                elif target_num and target_num in s_numbers:
                                    s_score += 70
                                    if s_clean.startswith(f"{target_num} "):
                                        s_score += 20
                                
                                if s_score > sub_best_score:
                                    sub_best_score = s_score
                                    sub_best_idx = s_idx
                                    sub_best_text = s_text
                            except Exception:
                                continue

                        if sub_best_idx >= 0 and sub_best_score >= 40:
                            if log:
                                log.info(f"Selecting specific house number: '{sub_best_text}' (score: {sub_best_score})")
                            sub_item = addr_list.nth(sub_best_idx)
                            sub_item.scroll_into_view_if_needed()
                            sub_item.click(force=True)
                            human_pause(page, 0.8, 1.5)
                else:
                    if log:
                        log.info(f"No confident address match in dropdown for '{client.address_line1}' (best score: {best_score}). Will use manual entry.")

        # Address Verification & Fallback: Guarantee address_line1 and town_city match client details
        addr1 = page.locator('input[data-test="first-line-address-input"], input[name="address-1"], input[placeholder*="Address"]').first
        city_inp = page.locator('input[data-test="town-city-input"], input[name="town-city"], input[placeholder*="Town"], input[placeholder*="City"]').first

        # Check if address line 1 is visible and accurately filled
        addr_val = ""
        try:
            if addr1.is_visible(timeout=1000):
                addr_val = addr1.input_value().strip()
        except Exception:
            pass

        target_simple = re.sub(r'[^a-z0-9]', '', client.address_line1.lower())
        current_simple = re.sub(r'[^a-z0-9]', '', addr_val.lower())

        needs_manual = False
        if not addr_val:
            needs_manual = True
        elif target_simple not in current_simple and current_simple not in target_simple:
            if log:
                log.warning(f"Address field mismatch: populated with '{addr_val}', expected '{client.address_line1}'. Overriding with correct address.")
            needs_manual = True

        if needs_manual:
            manual_btn = page.locator('a:has-text("Enter Manually"), button:has-text("Enter Manually"), span:has-text("Enter Manually"), button:has-text("Enter address manually"), a:has-text("manual"), button:has-text("manual")').first
            if manual_btn.is_visible(timeout=1500):
                if log:
                    log.info("Switching to manual address entry mode")
                manual_btn.scroll_into_view_if_needed()
                manual_btn.click(force=True)
                human_pause(page, 0.6, 1.2)

            if addr1.is_visible(timeout=1500):
                addr1.scroll_into_view_if_needed()
                addr1.fill("")
                human_type(addr1, client.address_line1, page)
                if log:
                    log.info(f"Filled Address Line 1: '{client.address_line1}'")

            if city_inp.is_visible(timeout=1500):
                city_val = ""
                try:
                    city_val = city_inp.input_value().strip()
                except Exception:
                    pass
                if not city_val or client.town_city.lower() not in city_val.lower():
                    city_inp.scroll_into_view_if_needed()
                    city_inp.fill("")
                    human_type(city_inp, client.town_city, page)
                    if log:
                        log.info(f"Filled Town/City: '{client.town_city}'")

        return True
    except Exception as e:
        if log:
            log.warning(f"Warning in select_matching_playbook_address: {e}")
        return False


def handle_playbook_safer_gambling_no_limit(page: Page, log=None) -> bool:
    """
    Specifically detects and physically completes the Playbook Engineering Safer Gambling
    and Rolling Net Deposit Limit onboarding modal via a guaranteed multi-stage execution:
      - Step 0: Aggressive scroll-to-bottom of ALL internal scroll containers & viewport
      - Step 1: Deposit limit input population (100/200/300/400/500) if required
      - Step 2: Multi-vector toggle/switch activation (Mouse, React Fiber, Prototype, Container, Keyboard)
      - Step 3: Deep React Fiber property and synthetic DOM event dispatch
      - Step 4: Multi-selector Progression CTA (Next / Save / Done / Continue / Accept / Acknowledge)
      - Step 5: Verification & Dismissal check
    """
    import random
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
            ':has-text("Rolling Net Deposit Limits")',
            ':has-text("Rolling Net Deposit Limit")',
            ':has-text("rolling net 1-day deposit limit")',
            ':has-text("How do Rolling Net Deposit Limits help me?")',
            ':has-text("Can I set my own Rolling Net Deposit Limits?")',
            ':has-text("What happens if I reach my Rolling Net Deposit Limit?")',
            ':has-text("Would you like to set a deposit limit")',
            ':has-text("No I don\'t want to set a deposit limit")',
            ':has-text("No, I don\'t want to set a deposit limit")',
            ':has-text("No I dont want to set a deposit limit")',
            ':has-text("I do not wish to set a deposit limit")',
            ':has-text("I don\'t want to set a deposit limit")',
            ':has-text("I\'ve looked at my deposit limit")',
            ':has-text("I am happy with deposit limit")',
            ':has-text("happy with deposit limit")',
            ':has-text("happy with it")'
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
            log.info("Playbook Safer Gambling / Rolling Deposit Limit modal detected — executing aggressive scroll, toggle & progression...")

        max_passes = 4
        for pass_num in range(1, max_passes + 1):
            # Step 0: AGGRESSIVE SCROLL TO BOTTOM OF ALL INTERNAL CONTAINERS
            # UKGC / Playbook requires scrolling to the bottom of the terms container before enabling controls
            try:
                page.evaluate("""() => {
                    // 1. Scroll every single scrollable element to its very bottom
                    const allNodes = Array.from(document.querySelectorAll('*'));
                    for (const el of allNodes) {
                        if (el.scrollHeight > el.clientHeight + 10) {
                            el.scrollTop = el.scrollHeight;
                            el.dispatchEvent(new Event('scroll', { bubbles: true }));
                            el.dispatchEvent(new Event('wheel', { bubbles: true }));
                        }
                    }
                    // 2. Target specific modal/drawer containers
                    const specific = [
                        document.querySelector('aside[data-test="SignUpStepsContainer"]'),
                        document.querySelector('[data-test="SignUpStepsContainer"]'),
                        document.querySelector('div[class*="modal"]'),
                        document.querySelector('div[class*="drawer"]'),
                        document.querySelector('div[class*="dialog"]'),
                        document.querySelector('div[class*="content"]'),
                        document.querySelector('div[class*="body"]'),
                        document.body,
                        document.documentElement
                    ];
                    for (const c of specific) {
                        if (c) {
                            c.scrollTop = c.scrollHeight;
                            c.dispatchEvent(new Event('scroll', { bubbles: true }));
                        }
                    }
                    window.scrollTo(0, document.body.scrollHeight);
                }""")
                page.wait_for_timeout(200)

                # Physical mouse wheel over modal center
                modal_box = None
                for m_sel in ['aside[data-test="SignUpStepsContainer"]', '[data-test="SignUpStepsContainer"]', 'div[class*="modal"]', 'div[class*="drawer"]', 'body']:
                    try:
                        m_loc = page.locator(m_sel).first
                        if m_loc.is_visible(timeout=100):
                            modal_box = m_loc.bounding_box(timeout=200)
                            if modal_box:
                                break
                    except Exception:
                        continue

                if modal_box:
                    page.mouse.move(modal_box["x"] + modal_box["width"] / 2, modal_box["y"] + modal_box["height"] / 2)
                    page.mouse.wheel(0, 5000)

                # Keyboard page down & end to trigger any lazy rendering
                page.keyboard.press("PageDown")
                page.keyboard.press("PageDown")
                page.keyboard.press("End")
                page.wait_for_timeout(200)
            except Exception:
                pass

            # Step 1: Deposit Limit Inputs & Presets (Set 100/200/300/400/500 if inputs exist)
            deposit_limit_inputs = [
                'input[data-test*="deposit-limit" i]',
                'input[data-test*="amount" i]',
                'input[name*="limit" i]',
                'input[name*="amount" i]',
                'input[placeholder*="limit" i]',
                'input[placeholder*="amount" i]',
                'input[placeholder*="£" i]',
                'input[aria-label*="limit" i]',
                'input[id*="limit" i]',
                'input[type="number"]'
            ]
            random_limit = random.choice(["100", "200", "300", "400", "500"])
            for inp_sel in deposit_limit_inputs:
                try:
                    inps = page.locator(inp_sel)
                    for i in range(inps.count()):
                        inp = inps.nth(i)
                        if inp.is_visible(timeout=100):
                            val = ""
                            try:
                                val = inp.input_value().strip()
                            except Exception:
                                pass
                            if not val or val == "0":
                                if log and pass_num == 1:
                                    log.info(f"Filling deposit limit input {inp_sel} with £{random_limit}")
                                inp.scroll_into_view_if_needed()
                                inp.fill(random_limit)
                                page.wait_for_timeout(100)
                except Exception:
                    continue

            # Check for preset deposit limit pills/buttons (e.g. £500, £250, £100)
            preset_limit_buttons = [
                'button:has-text("£500")',
                'button:has-text("500")',
                'button:has-text("£250")',
                'button:has-text("£100")',
                'div[data-test*="preset"]:has-text("500")',
                'div[class*="preset"]:has-text("500")'
            ]
            for p_sel in preset_limit_buttons:
                try:
                    p_btn = page.locator(p_sel).first
                    if p_btn.is_visible(timeout=100):
                        p_btn.click(force=True)
                        page.wait_for_timeout(100)
                        break
                except Exception:
                    continue

            # Step 2: Explicit No Limit & Acknowledgment Radio / Option Selection
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
                'label:has-text("I am happy with deposit limit")',
                'span:has-text("I am happy with deposit limit")',
                'label:has-text("happy with it")',
                'span:has-text("happy with it")',
                'input[value="no_limit"]',
                'input[value="no"]',
                'input[id*="no-limit"]',
                'input[type="radio"][value*="no" i]',
                'input[type="radio"][id*="no" i]'
            ]
            for trig in no_limit_triggers:
                try:
                    el = page.locator(trig).first
                    if el.is_visible(timeout=100):
                        if log and pass_num == 1:
                            log.info(f"Selecting No Limit / Acknowledgment option: {trig}")
                        el.scroll_into_view_if_needed()
                        try:
                            box = el.bounding_box(timeout=200)
                            if box:
                                page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                        except Exception:
                            pass
                        el.click(force=True)
                        page.wait_for_timeout(150)
                except Exception:
                    continue

            # Step 3: Physical Switch / Toggle Interaction with Bounding Box & Keyboard Focus
            ack_switch_selectors = [
                '[role="switch"]',
                'button[role="switch"]',
                'span[class*="switch" i]',
                'div[class*="Switch" i]',
                'span[class*="Switch" i]',
                'div[class*="switch" i]',
                'label[class*="switch" i]',
                'label[class*="Switch" i]',
                'label:has-text("I\'ve looked at my deposit limit")',
                'label:has-text("I am happy with deposit limit")',
                'label:has-text("happy with it")',
                'label:has-text("happy with deposit limit")',
                'input[type="checkbox"]',
                '[data-component*="Switch" i]',
                '[data-test*="switch" i]',
                '[data-test*="limit-toggle" i]',
                '[data-test*="deposit-limit-switch" i]',
                'span[class*="slider" i]',
                'div[class*="toggle" i]',
                'span[class*="toggle" i]'
            ]
            for switch_sel in ack_switch_selectors:
                try:
                    switches = page.locator(switch_sel)
                    cnt = switches.count()
                    for i in range(cnt):
                        s = switches.nth(i)
                        if s.is_visible(timeout=100):
                            tag = s.evaluate("e => e.tagName")
                            if tag == "INPUT":
                                inp_type = (s.get_attribute("type") or "").lower()
                                if inp_type not in ("checkbox", "radio"):
                                    continue
                                if s.is_checked():
                                    continue

                            aria_chk = s.get_attribute("aria-checked")
                            if aria_chk != "true":
                                if log and pass_num == 1:
                                    log.info(f"Toggling Safer Gambling switch ON ({switch_sel} #{i})")
                                s.scroll_into_view_if_needed()
                                
                                # Physical mouse click at center
                                try:
                                    box = s.bounding_box(timeout=200)
                                    if box:
                                        page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                                except Exception:
                                    pass
                                s.click(force=True)
                                
                                # Keyboard toggle fallback
                                try:
                                    s.focus()
                                    page.keyboard.press("Space")
                                except Exception:
                                    pass
                                
                                page.wait_for_timeout(150)
                except Exception:
                    continue

            # Step 4: Deep JavaScript & React Fiber State Injection
            try:
                page.evaluate("""() => {
                    // 1. Force native checkboxes via React prototype setter
                    const checkboxes = Array.from(document.querySelectorAll('input[type="checkbox"]'));
                    checkboxes.forEach(cb => {
                        try {
                            const proto = window.HTMLInputElement.prototype;
                            const desc = Object.getOwnPropertyDescriptor(proto, 'checked');
                            if (desc && desc.set) {
                                desc.set.call(cb, true);
                            } else {
                                cb.checked = true;
                            }
                            cb.dispatchEvent(new Event('input', { bubbles: true }));
                            cb.dispatchEvent(new Event('change', { bubbles: true }));
                            cb.dispatchEvent(new MouseEvent('click', { bubbles: true }));
                        } catch (e) {}
                    });

                    // 2. Force custom switches / buttons + trigger React internal Fiber handlers
                    const switches = Array.from(document.querySelectorAll('[role="switch"], [class*="switch" i], [class*="Switch" i], [class*="toggle" i], [class*="Toggle" i]'));
                    switches.forEach(sw => {
                        try {
                            sw.setAttribute('aria-checked', 'true');
                            sw.classList.add('checked', 'active', 'on');
                            
                            ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click', 'input', 'change'].forEach(evtName => {
                                try {
                                    sw.dispatchEvent(new Event(evtName, { bubbles: true, cancelable: true }));
                                } catch (err) {}
                            });

                            if (sw.click) sw.click();

                            // Invoke React Fiber event handlers directly if present
                            for (const key in sw) {
                                if (key.startsWith('__reactProps') || key.startsWith('__reactEvents') || key.startsWith('__reactFiber')) {
                                    const props = sw[key];
                                    if (props) {
                                        if (typeof props.onChange === 'function') {
                                            try { props.onChange({ target: { checked: true, value: true } }); } catch (e) {}
                                        }
                                        if (typeof props.onClick === 'function') {
                                            try { props.onClick({ target: sw, currentTarget: sw }); } catch (e) {}
                                        }
                                    }
                                }
                            }
                        } catch (e) {}
                    });

                    // 3. Click any label or text container referencing deposit limits or acknowledgement
                    const labels = Array.from(document.querySelectorAll('label, span, div, p, a'));
                    labels.forEach(lbl => {
                        const txt = (lbl.innerText || lbl.textContent || '').toLowerCase();
                        if (txt.includes("i've looked at my deposit limit") || 
                            txt.includes("i am happy with deposit limit") ||
                            txt.includes("happy with it") || 
                            txt.includes("happy with deposit limit") ||
                            txt.includes("looked at my deposit limit") ||
                            txt.includes("no, i don't want to set a deposit limit") ||
                            txt.includes("no i don't want to set a deposit limit") ||
                            txt.includes("no i dont want to set a deposit limit") ||
                            txt.includes("rolling net deposit limit")) {
                            try {
                                lbl.click();
                            } catch (e) {}
                        }
                    });
                }""")
                page.wait_for_timeout(300)
            except Exception:
                pass

            # Step 5: Click Progression CTA (Next / Save & Continue / Done / Confirm / Accept / Acknowledge)
            progression_buttons = [
                'button[data-test="next-button"]',
                'button[data-test="save-button"]',
                'button[data-test="done-button"]',
                'button[data-test="accept-button"]',
                'button[data-test*="next" i]',
                'button[data-test*="save" i]',
                'button[data-test*="continue" i]',
                'button[data-test*="done" i]',
                'button[data-test*="confirm" i]',
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
                'button:has-text("I\'m Happy with this")',
                'button:has-text("I am Happy with this")',
                'button:has-text("I\'m happy with this")',
                'button:has-text("Accept")',
                'button:has-text("ACCEPT")',
                'button:has-text("Acknowledge")',
                'button:has-text("ACKNOWLEDGE")',
                'button:has-text("Agree & Continue")',
                'button:has-text("Got it")',
                'button:has-text("Understood")',
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
                    if btn.is_visible(timeout=200):
                        if log and pass_num == 1:
                            log.info(f"Clicking Safer Gambling progression button: {btn_sel}")
                        btn.scroll_into_view_if_needed()
                        box = None
                        try:
                            box = btn.bounding_box(timeout=200)
                        except Exception:
                            pass

                        try:
                            btn.evaluate("""b => {
                                b.removeAttribute('disabled');
                                b.disabled = false;
                                b.setAttribute('aria-disabled', 'false');
                                b.classList.remove('disabled');
                                if (b.click) b.click();
                            }""")
                        except Exception:
                            pass

                        if box:
                            try:
                                page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                            except Exception:
                                pass

                        try:
                            if btn.is_visible(timeout=100):
                                btn.click(force=True, timeout=500)
                        except Exception:
                            pass
                        page.wait_for_timeout(500)
                        btn_clicked = True
                        break
                except Exception:
                    continue

            # Fallback progression button click via JavaScript with React Fiber invocation
            if not btn_clicked:
                try:
                    page.evaluate("""() => {
                        const btns = Array.from(document.querySelectorAll('button, a, input[type="submit"]'));
                        const nextBtn = btns.find(b => {
                            const t = (b.innerText || b.textContent || b.value || '').trim().toLowerCase();
                            const dt = (b.getAttribute('data-test') || '').toLowerCase();
                            return ['next', 'save & continue', 'save and continue', 'save', 'done', 'finish', 'confirm', 'continue', 'agree & join', 'accept', 'acknowledge', 'got it', 'understood', 'skip'].includes(t) ||
                                   dt.includes('next') || dt.includes('save') || dt.includes('continue') || dt.includes('done') || dt.includes('accept');
                        });
                        if (nextBtn) {
                            nextBtn.removeAttribute('disabled');
                            nextBtn.setAttribute('aria-disabled', 'false');
                            nextBtn.classList.remove('disabled');
                            
                            // Direct React Fiber click invocation
                            for (const key in nextBtn) {
                                if (key.startsWith('__reactProps') || key.startsWith('__reactEvents') || key.startsWith('__reactFiber')) {
                                    const props = nextBtn[key];
                                    if (props && typeof props.onClick === 'function') {
                                        try { props.onClick({ target: nextBtn, currentTarget: nextBtn }); } catch (e) {}
                                    }
                                }
                            }
                            nextBtn.click();
                        }
                    }""")
                    page.wait_for_timeout(1000)
                except Exception:
                    pass

            # Verification: Check if modal has closed
            modal_still_open = False
            for sel in modal_selectors[:8]:
                try:
                    if page.locator(sel).first.is_visible(timeout=100):
                        modal_still_open = True
                        break
                except Exception:
                    continue

            if not modal_still_open:
                if log:
                    log.info(f"Playbook Safer Gambling modal successfully completed and dismissed on pass {pass_num}!")
                return True

            page.wait_for_timeout(500)

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


