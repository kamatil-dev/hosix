from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from datetime import datetime, date, timedelta
from beaupy import select, select_multiple
import getpass
import re
import os
import subprocess
import time

# =========================
# CONFIG
# =========================
LOGIN_URL = "https://sih/login.aspx?ReturnUrl=%2fApps%2fadm%2fCitas%2fcitax.aspx"

# Booking
BOOKING = '#_ctl0_cph_UcHistoria1'
TXT_IPP = "#_ctl0_cph_UcHistoria1_1"
CHK_MANTENER = "#_ctl0_cph_ChkMantenerPaciente"
TXT_CONSULTA = "#_ctl0_cph_TxtConsulta\\:_ctl0"  # escape ':' in CSS selector
TXT_OBS = "#_ctl0_cph_TxtObservaciones"
CMD_HORAS = "#_ctl0_cph_cmdHoras"

# Extra booking
TXT_FECHA_EXTRA = "#_ctl0_cph_TxtFechaExtra"
BTN_ADD_CITA_EXTRA = "#_ctl0_cph_CmdAddCitaExtra"
BLANK_SPACE = "#S_ctl0_cph_GrdBloqueosConsulta"
BTN_APLICAR = "#_ctl0_cph_CmdAplicar"
BTN_CERRAR = "#_ctl0_cph_cmdCerrar"
BTN_TOOL_1031 = "#tool-1031"

# CYTO checkboxes
CHK_CYTO = "#_ctl0_cph_lvwActividades__ctl2_CheckBox1"

# BES checkboxes
# Ionogramme sanguin
CHK_BES_7 = "#_ctl0_cph_lvwActividades__ctl7_CheckBox1"
CHK_BES_8 = "#_ctl0_cph_lvwActividades__ctl8_CheckBox1"
CHK_BES_9 = "#_ctl0_cph_lvwActividades__ctl9_CheckBox1"
CHK_BES_15 = "#_ctl0_cph_lvwActividades__ctl15_CheckBox1"
# Bilan hépatique
CHK_BES_3 = "#_ctl0_cph_lvwActividades__ctl3_CheckBox1"
CHK_BES_16 = "#_ctl0_cph_lvwActividades__ctl16_CheckBox1"
CHK_BES_17 = "#_ctl0_cph_lvwActividades__ctl17_CheckBox1"
CHK_BES_18 = "#_ctl0_cph_lvwActividades__ctl18_CheckBox1"
CHK_BES_19 = "#_ctl0_cph_lvwActividades__ctl19_CheckBox1"
CHK_BES_20 = "#_ctl0_cph_lvwActividades__ctl20_CheckBox1"
# CRP
CHK_BES_21 = "#_ctl0_cph_lvwActividades__ctl21_CheckBox1"

# HEMOS checkboxes
# Bilan d'hémostase
CHK_HEMOS_11 = "#_ctl0_cph_lvwActividades__ctl11_CheckBox1"
CHK_HEMOS_12 = "#_ctl0_cph_lvwActividades__ctl12_CheckBox1"
CHK_HEMOS_14 = "#_ctl0_cph_lvwActividades__ctl14_CheckBox1"

# BIM4 checkbox
CHK_BIM4_7 = "#_ctl0_cph_lvwActividades__ctl7_CheckBox1"

# BES2 checkbox
CHK_BES2_2 = "#_ctl0_cph_lvwActividades__ctl2_CheckBox1"

# =========================
# MENU CONFIG
# =========================
# Maps user-facing test names to booking codes and checkboxes
MENU_CONFIG = {
    "NFS": {"code": "CYTO", "checkboxes": [CHK_CYTO]},
    "CRP": {"code": "BES", "checkboxes": [CHK_BES_21]},
    "PCT": {"code": "BIM4", "checkboxes": [CHK_BIM4_7]},
    "Ionogramme sanguin": {"code": "BES", "checkboxes": [CHK_BES_7, CHK_BES_8, CHK_BES_9, CHK_BES_15]},
    "Bilan hépatique": {"code": "BES", "checkboxes": [CHK_BES_3, CHK_BES_16, CHK_BES_17, CHK_BES_18, CHK_BES_19, CHK_BES_20]},
    "Bilan d'hémostase": {"code": "HEMOS", "checkboxes": [CHK_HEMOS_11, CHK_HEMOS_12, CHK_HEMOS_14]},
    "Albumine": {"code": "BES2", "checkboxes": [CHK_BES2_2]},
}

# Printing
USE_KIOSK_PRINTING = True  # True = no print dialog (prints to default printer)
PRINT_PAUSE_MS = 4000       # give time for print dialog to appear (if not kiosk)
USE_XDOTOOL = True          # True = use xdotool to press Enter on print dialog (Linux only)

# Browser
USE_PRIVATE_MODE = True     # True = launch in incognito/private mode
HEADLESS = True             # False = show the browser window (disable headless mode)

# Safety/timeouts
DEFAULT_TIMEOUT_MS = 0  # 0 = no timeout, wait indefinitely
SOFT_TIMEOUT_MS = 30000  # Soft timeout for optional waits (30 seconds)

# Logging
VERBOSE = False  # Set to True to show debug/info logs


# =========================
# HELPERS
# =========================
def log(message):
    """Print message only if VERBOSE is True."""
    if VERBOSE:
        print(message)

def parse_ddmmyyyy_strict(s: str) -> date:
    """Parse 'dd/mm/yyyy' after removing whitespace."""
    s = re.sub(r"\s+", "", s)
    return datetime.strptime(s, "%d/%m/%Y").date()

def get_second_td_date(page) -> date:
    """
    Reads the 2nd <td> text from a row that has class 'ft_r ui-widget-header'.
    You said: second td text in class="ft_r ui-widget-header" like "  29/01/2026  ".
    """
    # Try finding the date in any iframe FIRST
    frames = page.frames
    for frame in frames:
        try:
            td2 = frame.locator("#_ctl0_cph_tablaResultados > tbody > tr:nth-child(1) > td").nth(2)
            td2.wait_for(state="visible", timeout=5000)
            raw = td2.text_content() or ""
            log(f"\n--- Found date in iframe: {raw} ---")
            return parse_ddmmyyyy_strict(raw)
        except Exception:
            continue
    
    # Then try the original selector on page
    try:
        td2 = page.locator("#_ctl0_cph_tablaResultados > tbody > tr:nth-child(1) > td").nth(2)
        td2.wait_for(state="visible", timeout=5000)
        raw = td2.text_content() or ""
        log(f"\n--- Found date: {raw} ---")
        return parse_ddmmyyyy_strict(raw)
    except PlaywrightTimeoutError:
        log("[DEBUG] Date selector not found in page or iframes")
        pass
    
    raise Exception("Could not find date element in page or iframes")

def click_row_with_wait(page, row_locator):
    """
    ASPX row click may do full postback navigation or partial update.
    Try expect_navigation first; fallback to networkidle.
    """
    row_locator.scroll_into_view_if_needed()
    try:
        with page.expect_navigation(wait_until="networkidle", timeout=8000):
            row_locator.click()
    except PlaywrightTimeoutError:
        row_locator.click()
        page.wait_for_load_state("networkidle")

def safe_click(page, selector: str):
    """Click element, wait indefinitely for it to appear."""
    if DEFAULT_TIMEOUT_MS > 0:
        page.wait_for_selector(selector, timeout=DEFAULT_TIMEOUT_MS)
    else:
        page.wait_for_selector(selector)
    page.click(selector)

def try_click(page, selector: str, timeout_ms: int = None):
    """Try to click element, skip if not found within timeout."""
    try:
        timeout = timeout_ms or SOFT_TIMEOUT_MS
        page.wait_for_selector(selector, timeout=timeout)
        page.click(selector)
        return True
    except PlaywrightTimeoutError:
        log(f"[INFO] Element {selector} not found, continuing...")
        return False

def safe_click_in_iframe(page, selector: str):
    """Click element inside an iframe within #panelDatos-body"""
    try:
        # Wait for the container
        page.wait_for_selector("#panelDatos-body", timeout=DEFAULT_TIMEOUT_MS)
        
        # Get all frames and search for the selector
        frames = page.frames
        for frame in frames:
            try:
                # Try to find and click in this frame
                frame.wait_for_selector(selector, timeout=5000)
                frame.click(selector)
                log(f"[DEBUG] Clicked button in frame")
                return
            except Exception:
                continue
        
        # If not found in any frame, log and try fallback
        log(f"[DEBUG] Element not found in any iframe, trying direct click")
        safe_click(page, selector)
    except Exception as e:
        log(f"[DEBUG] Failed to click in iframe: {e}")
        # Last resort: try direct click
        try:
            safe_click(page, selector)
        except Exception as e2:
            log(f"[DEBUG] Direct click also failed: {e2}")

def safe_click_in_iframe_by_id(page, selector: str, frame_id: str):
    """Click element inside a specific iframe by id. Waits indefinitely."""
    if DEFAULT_TIMEOUT_MS > 0:
        page.wait_for_selector(f"#{frame_id}", timeout=DEFAULT_TIMEOUT_MS)
    else:
        page.wait_for_selector(f"#{frame_id}")
    frame = page.frame_locator(f"#{frame_id}")
    if DEFAULT_TIMEOUT_MS > 0:
        frame.locator(selector).wait_for(state="visible", timeout=DEFAULT_TIMEOUT_MS)
    else:
        frame.locator(selector).wait_for(state="visible")
    frame.locator(selector).click()

def try_click_in_iframe_by_id(page, selector: str, frame_id: str, timeout_ms: int = None):
    """Try to click element in iframe, skip if not found."""
    try:
        timeout = timeout_ms or SOFT_TIMEOUT_MS
        page.wait_for_selector(f"#{frame_id}", timeout=timeout)
        frame = page.frame_locator(f"#{frame_id}")
        frame.locator(selector).wait_for(state="visible", timeout=timeout)
        frame.locator(selector).click()
        return True
    except PlaywrightTimeoutError:
        log(f"[INFO] Element {selector} in iframe not found, continuing...")
        return False

def safe_click_with_nav(page, selector: str):
    """Click and expect navigation"""
    page.wait_for_selector(selector, timeout=DEFAULT_TIMEOUT_MS)
    try:
        with page.expect_navigation(wait_until="networkidle", timeout=0):
            page.click(selector)
    except PlaywrightTimeoutError:
        pass

def safe_check(page, selector: str):
    if DEFAULT_TIMEOUT_MS > 0:
        page.wait_for_selector(selector, timeout=DEFAULT_TIMEOUT_MS)
    else:
        page.wait_for_selector(selector)
    page.locator(selector).check()

def safe_check_in_iframe(page, selector: str, frame_id: str):
    """Check element inside a specific iframe by id."""
    if DEFAULT_TIMEOUT_MS > 0:
        page.wait_for_selector(f"#{frame_id}", timeout=DEFAULT_TIMEOUT_MS)
    else:
        page.wait_for_selector(f"#{frame_id}")
    frame = page.frame_locator(f"#{frame_id}")
    if DEFAULT_TIMEOUT_MS > 0:
        frame.locator(selector).wait_for(state="visible", timeout=DEFAULT_TIMEOUT_MS)
    else:
        frame.locator(selector).wait_for(state="visible")
    frame.locator(selector).check()

def safe_fill(page, selector: str, value: str):
    if DEFAULT_TIMEOUT_MS > 0:
        page.wait_for_selector(selector, timeout=DEFAULT_TIMEOUT_MS)
    else:
        page.wait_for_selector(selector)
    page.fill(selector, value)

def safe_fill_in_iframe(page, selector: str, value: str, frame_id: str):
    """Fill input inside a specific iframe by id."""
    if DEFAULT_TIMEOUT_MS > 0:
        page.wait_for_selector(f"#{frame_id}", timeout=DEFAULT_TIMEOUT_MS)
    else:
        page.wait_for_selector(f"#{frame_id}")
    frame = page.frame_locator(f"#{frame_id}")
    if DEFAULT_TIMEOUT_MS > 0:
        frame.locator(selector).wait_for(state="visible", timeout=DEFAULT_TIMEOUT_MS)
    else:
        frame.locator(selector).wait_for(state="visible")
    frame.locator(selector).fill(value)

def press_ctrl_p(page):
    """Send Ctrl+P keyboard shortcut to trigger print dialog."""
    page.bring_to_front()
    page.evaluate('(() => {window.waitForPrintDialog = new Promise(f => window.print = f);})()')
    page.wait_for_function('window.waitForPrintDialog')

def enter_opens_popup_and_print(page):
    """
    Press Enter => new window expected => send Ctrl+P in that window.
    If no popup appears, fallback to same page.
    """
    try:
        with page.expect_popup(timeout=5000) as popup_info:
            page.keyboard.press("Enter")
        print_page = popup_info.value
    except PlaywrightTimeoutError:
        # no popup, assume same tab
        page.keyboard.press("Enter")
        print_page = page

    print_page.wait_for_load_state("networkidle")

    press_ctrl_p(print_page)

    # If not kiosk printing, an OS print dialog will appear (not controllable by Playwright)
    print_page.wait_for_timeout(PRINT_PAUSE_MS)

    # If a real popup was created, you may want to close it after print is launched.
    if print_page is not page:
        # Closing immediately can sometimes cancel printing on some setups.
        # Keep a small delay above; if needed increase PRINT_PAUSE_MS.
        try:
            print_page.close()
        except Exception:
            pass

def compute_booking_plan(selected_items):
    """Group selected items by booking code and return ordered list of (code, checkboxes) tuples."""
    code_to_checkboxes = {}
    code_order = []

    for item in selected_items:
        config = MENU_CONFIG[item]
        code = config["code"]
        if code not in code_to_checkboxes:
            code_to_checkboxes[code] = []
            code_order.append(code)
        code_to_checkboxes[code].extend(config["checkboxes"])

    return [(code, code_to_checkboxes[code]) for code in code_order]

def handle_print_popup(print_page):
    """Handle the print popup window."""
    log(f"[INFO] Popup URL: {print_page.url}")
    print_page.bring_to_front()
    print_page.wait_for_load_state("networkidle")
    print_page.wait_for_load_state("load")
    print_page.wait_for_timeout(3000)

    log("[INFO] Triggering print dialog via JavaScript...")
    print_page.evaluate("window.print()")

    if USE_KIOSK_PRINTING:
        log("[INFO] Kiosk printing enabled - printing directly to default printer...")
        print_page.wait_for_timeout(3000)
    elif USE_XDOTOOL:
        log("[INFO] Using xdotool to confirm print dialog...")
        print_page.wait_for_timeout(2000)
        subprocess.run(["xdotool", "key", "Return"], check=False)
        print_page.wait_for_timeout(2000)
    else:
        log("[INFO] Print dialog should be open. Waiting for user to print...")
        print_page.wait_for_timeout(30000)

def perform_booking(page, context, code, checkboxes, selected_date_08):
    """Perform a single booking with the given code and checkboxes."""
    log(f"[INFO] Starting booking ({code})...")

    safe_fill(page, TXT_CONSULTA, code)
    page.keyboard.press("Enter")
    time.sleep(2)
    safe_fill(page, TXT_OBS, "     ")
    page.keyboard.press("Enter")
    safe_click(page, CMD_HORAS)
    page.wait_for_load_state("networkidle")

    # Check all checkboxes in iframe
    for chk in checkboxes:
        safe_check_in_iframe(page, chk, "VentanaModal_1_ifrm")

    # Fill date
    log(f"[INFO] Setting date: {selected_date_08}")
    safe_fill_in_iframe(page, TXT_FECHA_EXTRA, selected_date_08, "VentanaModal_1_ifrm")

    # Add cita extra
    safe_click_in_iframe_by_id(page, BTN_ADD_CITA_EXTRA, "VentanaModal_1_ifrm")
    page.wait_for_load_state("networkidle")

    # Zoom out
    log("[INFO] Zooming out...")
    page.keyboard.down("Control")
    page.keyboard.press("Minus")
    page.keyboard.up("Control")
    page.wait_for_timeout(500)

    # Dialog handler
    def handle_dialog(dialog):
        try:
            log(f"[INFO] Alert detected: {dialog.message}")
            dialog.accept()
        except Exception as e:
            log(f"[WARNING] Failed to accept dialog: {e}")

    page.once("dialog", handle_dialog)

    # Apply and handle print popup
    print_page = None
    try:
        with page.expect_popup(timeout=10000) as popup_info:
            safe_click_in_iframe_by_id(page, BTN_APLICAR, "VentanaModal_1_ifrm")
        print_page = popup_info.value
        handle_print_popup(print_page)
    except PlaywrightTimeoutError:
        log(f"[WARNING] No popup detected for {code} booking. Checking for new pages...")
        pages = context.pages
        if len(pages) > 1:
            print_page = pages[-1]
            handle_print_popup(print_page)
        else:
            log("[WARNING] No new page found")

    # Cleanup
    if print_page:
        try:
            print_page.close()
        except Exception:
            pass

    page.bring_to_front()
    page.wait_for_timeout(1000)
    safe_click_in_iframe_by_id(page, BTN_CERRAR, "VentanaModal_1_ifrm")
    page.wait_for_load_state("networkidle")

    log(f"[INFO] Booking ({code}) completed.")


# =========================
# FETCH PATIENTS WITHOUT BILANS
# =========================
PATIENTS_LOGIN_URL = "https://sih/login.aspx?ReturnUrl=%2fApps%2fmed%2fdefault.aspx"
PATIENT_HISTORY_URL = "https://sih/Apps/adm/Historias/historialPaciente.aspx"
HISTORY_IPP_INPUT = "#_ctl0_cph_UcHistoria1_1"
HISTORY_TABLE_BODY = "#_ctl0_cph_GrdHistorial-body"


def fetch_patients_without_bilans(username, password, filter_option, booking_codes=None):
    """
    Fetch all patients from SIH and determine which ones already have bilans
    for the specified period.

    filter_option: "today" or "yesterday"
    booking_codes: list of booking codes to check (e.g. ['CYTO', 'BES']).
                   Defaults to ['CYTO'] if not provided.
    Returns: list of dicts {"ip": str, "name": str, "has_bilan": bool}
    """
    if filter_option == "today":
        target_date = date.today()
    elif filter_option == "yesterday":
        target_date = date.today() - timedelta(days=1)
    else:
        raise ValueError(f"Invalid filter option: {filter_option}")

    if not booking_codes:
        booking_codes = ["CYTO"]

    with sync_playwright() as p:
        launch_args = ["--incognito"] if USE_PRIVATE_MODE else []
        browser = p.chromium.launch(headless=HEADLESS, args=launch_args)
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()
        page.set_default_timeout(60000)

        try:
            # Login
            page.goto(PATIENTS_LOGIN_URL, timeout=60000)
            page.wait_for_selector('input[name="txtUsername"]', timeout=60000)
            page.fill('input[name="txtUsername"]', username)
            page.fill('input[name="txtPassword"]', password)
            page.click("#cmdLogin")
            page.wait_for_load_state("networkidle")

            # Wait for episodes table
            page.wait_for_selector("#GrdEpisodios-body", timeout=60000)

            # Get all patients from the table (ip from 2nd td, name from 5th td)
            all_patients = page.evaluate("""
                () => {
                    const tbody = document.querySelector('#GrdEpisodios-body tbody');
                    if (!tbody) return [];
                    const rows = tbody.querySelectorAll('tr');
                    const patients = [];
                    rows.forEach(row => {
                        const tds = row.querySelectorAll('td');
                        if (tds.length >= 2) {
                            const ip = tds[1].textContent.trim();
                            const name = tds.length >= 4 ? tds[3].textContent.trim() : '';
                            if (ip) patients.push({ ip, name });
                        }
                    });
                    return patients;
                }
            """)

            if not all_patients:
                return []

            result = []
            for patient in all_patients:
                ip = patient.get("ip", "")
                name = patient.get("name", "")
                if not ip:
                    continue
                try:
                    page.goto(PATIENT_HISTORY_URL, timeout=60000)
                    page.wait_for_load_state("networkidle")

                    # Type IP in the input and blur
                    page.wait_for_selector(HISTORY_IPP_INPUT, timeout=60000)
                    page.fill(HISTORY_IPP_INPUT, ip)
                    page.keyboard.press("Tab")
                    page.wait_for_load_state("networkidle")

                    # Look for any of the booking codes in the history table
                    has_bilan_on_target = False
                    try:
                        page.wait_for_selector(HISTORY_TABLE_BODY, timeout=15000)

                        bilan_date_str = page.evaluate("""
                            (codes) => {
                                const tbody = document.querySelector('#_ctl0_cph_GrdHistorial-body tbody');
                                if (!tbody) return null;
                                const rows = tbody.querySelectorAll('tr');
                                for (const row of rows) {
                                    const tds = row.querySelectorAll('td');
                                    if (tds.length >= 5) {
                                        const fourthTd = tds[4].textContent.trim();
                                        for (const code of codes) {
                                            if (fourthTd.includes('(' + code + ')')) {
                                                return tds[1].textContent.trim();
                                            }
                                        }
                                    }
                                }
                                return null;
                            }
                        """, booking_codes)

                        if bilan_date_str:
                            # Parse date from format like "04/03/2026 8:33"
                            try:
                                bilan_date = datetime.strptime(
                                    bilan_date_str.split()[0], "%d/%m/%Y"
                                ).date()
                                if bilan_date == target_date:
                                    has_bilan_on_target = True
                            except (ValueError, IndexError):
                                pass

                    except PlaywrightTimeoutError:
                        pass

                    result.append({"ip": ip, "name": name, "has_bilan": has_bilan_on_target})

                except Exception as e:
                    log(f"[WARNING] Error checking IP {ip}, skipping: {e}")
                    result.append({"ip": ip, "name": name, "has_bilan": False})

            return result
        finally:
            browser.close()


def fetch_all_patients(username, password, filter_option):
    """
    Fetch all patients from SIH without checking bilan history.

    filter_option: "today" or "yesterday"
    Returns: list of dicts {"ip": str, "name": str, "has_bilan": bool}
             has_bilan is always False since no bilan check is performed.
    """
    if filter_option == "today":
        target_date = date.today()
    elif filter_option == "yesterday":
        target_date = date.today() - timedelta(days=1)
    else:
        raise ValueError(f"Invalid filter option: {filter_option}")

    with sync_playwright() as p:
        launch_args = ["--incognito"] if USE_PRIVATE_MODE else []
        browser = p.chromium.launch(headless=HEADLESS, args=launch_args)
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()
        page.set_default_timeout(60000)

        try:
            # Login
            page.goto(PATIENTS_LOGIN_URL, timeout=60000)
            page.wait_for_selector('input[name="txtUsername"]', timeout=60000)
            page.fill('input[name="txtUsername"]', username)
            page.fill('input[name="txtPassword"]', password)
            page.click("#cmdLogin")
            page.wait_for_load_state("networkidle")

            # Wait for episodes table
            page.wait_for_selector("#GrdEpisodios-body", timeout=60000)

            # Get all patients from the table (ip from 2nd td, name from 5th td)
            all_patients = page.evaluate("""
                () => {
                    const tbody = document.querySelector('#GrdEpisodios-body tbody');
                    if (!tbody) return [];
                    const rows = tbody.querySelectorAll('tr');
                    const patients = [];
                    rows.forEach(row => {
                        const tds = row.querySelectorAll('td');
                        if (tds.length >= 2) {
                            const ip = tds[1].textContent.trim();
                            const name = tds.length >= 4 ? tds[3].textContent.trim() : '';
                            if (ip) patients.push({ ip, name });
                        }
                    });
                    return patients;
                }
            """)

            return [{"ip": p["ip"], "name": p["name"], "has_bilan": False} for p in all_patients if p.get("ip")]
        finally:
            browser.close()


# =========================
# MAIN FLOW
# =========================
def clear_console():
    """Clear the console screen."""
    os.system('cls' if os.name == 'nt' else 'clear')

def get_ipp_list():
    """Ask user for list of IPP numbers separated by comma."""
    print("=" * 50)
    print("       SYSTÈME D'IMPRESSION AUTOMATIQUE")
    print("=" * 50)
    print()
    user_input = input("Veuillez entrer la liste des IPP séparés par des virgules: ")
    # Remove all spaces and split by comma
    cleaned = re.sub(r'\s+', '', user_input)
    ipp_list = [ipp for ipp in cleaned.split(',') if ipp]
    return ipp_list

def get_selected_date():
    """Show date selection menu and return selected date as dd/mm/yyyy string."""
    today = date.today()
    tomorrow = today + timedelta(days=1)

    options = [
        f"Aujourd'hui     ({today.strftime('%d/%m/%Y')})",
        f"Demain          ({tomorrow.strftime('%d/%m/%Y')})",
        "Personnalisé    (saisir la date)",
    ]
    dates = [today, tomorrow, None]

    print()
    print("Sélectionnez la date de rendez-vous:")
    choice = select(options)
    idx = options.index(choice)

    if dates[idx] is not None:
        selected = dates[idx]
    else:
        while True:
            raw = input("Entrez la date (dd/mm/yyyy): ")
            try:
                selected = parse_ddmmyyyy_strict(raw)
                break
            except ValueError:
                print("[ERREUR] Format invalide. Veuillez utiliser dd/mm/yyyy.")

    print(f"\n[INFO] Date sélectionnée: {selected.strftime('%d/%m/%Y')}")
    return selected.strftime("%d/%m/%Y")


def get_selected_hour():
    """Show hour selection menu and return selected time as HH:MM:SS string."""
    PRESET_HOURS = ["06:00", "08:00", "09:00"]
    CUSTOM_LABEL = "Personnalisé    (saisir l'heure)"
    NOW_IDX = 0

    now_display = datetime.now().strftime("%H:%M")
    options = [
        f"Maintenant      ({now_display})",
        *PRESET_HOURS,
        CUSTOM_LABEL,
    ]

    print()
    print("Sélectionnez l'heure de rendez-vous:")
    choice = select(options)
    idx = options.index(choice)

    if idx == NOW_IDX:
        selected_time = datetime.now().strftime("%H:%M:%S")
    elif choice == CUSTOM_LABEL:
        while True:
            raw = input("Entrez l'heure (HH:MM): ").strip()
            try:
                parsed = datetime.strptime(raw, "%H:%M")
                selected_time = parsed.strftime("%H:%M:%S")
                break
            except ValueError:
                print("[ERREUR] Format invalide. Veuillez utiliser HH:MM.")
    else:
        selected_time = choice + ":00"

    print(f"\n[INFO] Heure sélectionnée: {selected_time}")
    return selected_time

def get_selected_bookings():
    """Show multi-select menu for test types."""
    options = list(MENU_CONFIG.keys())
    
    print()
    print("Sélectionnez les analyses (Espace pour sélectionner, Entrée pour valider):")
    selected = select_multiple(options)
    
    if not selected:
        print("[WARNING] Aucune analyse sélectionnée, toutes seront effectuées.")
        return options
    
    print(f"\n[INFO] Analyses sélectionnées: {', '.join(selected)}")
    return selected

def run_job(ipp_list, selected_date, selected_hour, selected_bookings, username, password):
    """Run the booking automation without interactive prompts."""
    selected_date_08 = f"{selected_date} {selected_hour}"

    with sync_playwright() as p:
        launch_args = []
        if USE_KIOSK_PRINTING:
            launch_args.append("--kiosk-printing")
        if USE_PRIVATE_MODE:
            launch_args.append("--incognito")

        browser = p.chromium.launch(headless=HEADLESS, args=launch_args)
        context = browser.new_context(ignore_https_errors=True)
        context.set_default_timeout(0)  # unlimited; inherited by popups

        context.add_init_script("""
            (() => {
                const CSS = '.x-window-closable, .x-mask, .x-css-shadow { display: none!important }';
                const STYLE_ID = 'hosix-overlay-hide';
                const mo = new MutationObserver(function(mutations) {
                    for (const m of mutations) {
                        for (const node of m.removedNodes) {
                            if (node.id === STYLE_ID) { injectStyle(); return; }
                        }
                    }
                });
                function injectStyle() {
                    if (!document.getElementById(STYLE_ID)) {
                        const s = document.createElement('style');
                        s.id = STYLE_ID;
                        s.textContent = CSS;
                        const container = document.head || document.documentElement;
                        container.appendChild(s);
                        mo.observe(container, { childList: true });
                    }
                }
                injectStyle();
                // Re-inject after ASP.NET AJAX partial postbacks (UpdatePanel)
                document.addEventListener('DOMContentLoaded', function() {
                    if (window.Sys && Sys.WebForms && Sys.WebForms.PageRequestManager) {
                        Sys.WebForms.PageRequestManager.getInstance().add_endRequest(injectStyle);
                    }
                });
            })();
        """)

        page = context.new_page()

        page.goto(LOGIN_URL, timeout=0)
        page.wait_for_selector('input[name="txtUsername"]', timeout=DEFAULT_TIMEOUT_MS)
        page.fill('input[name="txtUsername"]', username)
        page.fill('input[name="txtPassword"]', password)
        safe_click_with_nav(page, "#cmdLogin")

        for ipp_index, current_ipp in enumerate(ipp_list):
            log(f"[INFO] Traitement IPP {ipp_index + 1}/{len(ipp_list)}: {current_ipp}")

            page.wait_for_selector(BOOKING, timeout=DEFAULT_TIMEOUT_MS)
            page.keyboard.press("Escape")
            page.keyboard.press("Enter")
            page.keyboard.press("Escape")

            safe_fill(page, TXT_IPP, current_ipp)
            page.locator(TXT_IPP).press("Tab")
            page.wait_for_load_state("networkidle")

            page.keyboard.press("Escape")
            page.keyboard.press("Enter")
            page.keyboard.press("Escape")

            safe_check(page, CHK_MANTENER)
            try_click(page, BTN_TOOL_1031, timeout_ms=3000)

            booking_plan = compute_booking_plan(selected_bookings)
            for code, checkboxes in booking_plan:
                perform_booking(page, context, code, checkboxes, selected_date_08)

            log(f"[INFO] IPP {current_ipp} terminé avec succès!")

        log(f"[INFO] Tous les {len(ipp_list)} IPP ont été traités!")
        browser.close()


def main():
    clear_console()
    
    # Get list of IPP from user
    ipp_list = get_ipp_list()
    
    if not ipp_list:
        print("[ERREUR] Aucun IPP fourni. Fermeture du programme.")
        return
    
    print(f"\n[INFO] {len(ipp_list)} IPP à traiter: {', '.join(ipp_list)}")
    
    # Get selected date from user
    selected_date = get_selected_date()

    # Get selected hour from user
    selected_hour = get_selected_hour()
    selected_date_08 = f"{selected_date} {selected_hour}"

    # Get selected booking types from user
    selected_bookings = get_selected_bookings()
    print()
    
    username = input("Username: ")
    password = getpass.getpass("Password: ")

    with sync_playwright() as p:
        launch_args = []
        if USE_KIOSK_PRINTING:
            launch_args.append("--kiosk-printing")
        if USE_PRIVATE_MODE:
            launch_args.append("--incognito")

        browser = p.chromium.launch(
            headless=HEADLESS,
            args=launch_args
        )

        context = browser.new_context(ignore_https_errors=True)
        context.set_default_timeout(0)  # unlimited; inherited by popups

        # Globally suppress unwanted ExtJS modals/overlays on every page and frame
        context.add_init_script("""
            (() => {
                const CSS = '.x-window-closable, .x-mask, .x-css-shadow { display: none!important }';
                const STYLE_ID = 'hosix-overlay-hide';
                const mo = new MutationObserver(function(mutations) {
                    for (const m of mutations) {
                        for (const node of m.removedNodes) {
                            if (node.id === STYLE_ID) { injectStyle(); return; }
                        }
                    }
                });
                function injectStyle() {
                    if (!document.getElementById(STYLE_ID)) {
                        const s = document.createElement('style');
                        s.id = STYLE_ID;
                        s.textContent = CSS;
                        const container = document.head || document.documentElement;
                        container.appendChild(s);
                        mo.observe(container, { childList: true });
                    }
                }
                injectStyle();
                // Re-inject after ASP.NET AJAX partial postbacks (UpdatePanel)
                document.addEventListener('DOMContentLoaded', function() {
                    if (window.Sys && Sys.WebForms && Sys.WebForms.PageRequestManager) {
                        Sys.WebForms.PageRequestManager.getInstance().add_endRequest(injectStyle);
                    }
                });
            })();
        """)

        page = context.new_page()

        # 1) Login
        page.goto(LOGIN_URL, timeout=0)  # No timeout
        page.wait_for_selector('input[name="txtUsername"]', timeout=DEFAULT_TIMEOUT_MS)
        page.fill('input[name="txtUsername"]', username)
        page.fill('input[name="txtPassword"]', password)
        safe_click_with_nav(page, "#cmdLogin")

        # Process each IPP
        for ipp_index, current_ipp in enumerate(ipp_list):
            print(f"\n{'='*50}")
            log(f"[INFO] Traitement IPP {ipp_index + 1}/{len(ipp_list)}: {current_ipp}")
            print(f"{'='*50}")

            # 2) Wait for Booking page
            page.wait_for_selector(BOOKING, timeout=DEFAULT_TIMEOUT_MS)
            page.keyboard.press("Escape")
            page.keyboard.press("Enter")
            page.keyboard.press("Escape")

            safe_fill(page, TXT_IPP, current_ipp)
            page.locator(TXT_IPP).press("Tab")  # Blur input to trigger ASPX change/postback
            page.wait_for_load_state("networkidle")

            page.keyboard.press("Escape")
            page.keyboard.press("Enter")
            page.keyboard.press("Escape")

            safe_check(page, CHK_MANTENER)
            
            # Optional click if the tool button appears after typing IPP
            try_click(page, BTN_TOOL_1031, timeout_ms=3000)
            
            # Compute booking plan from selections
            booking_plan = compute_booking_plan(selected_bookings)

            for code, checkboxes in booking_plan:
                perform_booking(page, context, code, checkboxes, selected_date_08)

            print(f"[INFO] IPP {current_ipp} terminé avec succès!")

        print(f"\n{'='*50}")
        print(f"[INFO] Tous les {len(ipp_list)} IPP ont été traités!")
        print(f"{'='*50}")

        browser.close()
        log("[INFO] Navigateur fermé.")

        return True  # Signal success

if __name__ == "__main__":
    while True:
        result = main()
        print()
        print("Que souhaitez-vous faire ?")
        choice = select(
            ["Relancer le script", "Quitter"]
        )
        if choice == "Quitter":
            print("\n[INFO] Au revoir!")
            break
        else:
            clear_console()
