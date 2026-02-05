from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from datetime import datetime, date, timedelta
from beaupy import select, select_multiple
import getpass
import re
import os
import subprocess
import urllib.request

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
CHK_ACTIVIDAD = "#_ctl0_cph_lvwActividades__ctl2_CheckBox1"
TXT_FECHA_EXTRA = "#_ctl0_cph_TxtFechaExtra"
BTN_ADD_CITA_EXTRA = "#_ctl0_cph_CmdAddCitaExtra"
BLANK_SPACE = "#S_ctl0_cph_GrdBloqueosConsulta"
BTN_APLICAR = "#_ctl0_cph_CmdAplicar"
BTN_CERRAR = "#_ctl0_cph_cmdCerrar"

# BES checkboxes
CHK_BES_7 = "#_ctl0_cph_lvwActividades__ctl7_CheckBox1"
CHK_BES_8 = "#_ctl0_cph_lvwActividades__ctl8_CheckBox1"
CHK_BES_9 = "#_ctl0_cph_lvwActividades__ctl9_CheckBox1"
CHK_BES_15 = "#_ctl0_cph_lvwActividades__ctl15_CheckBox1"
CHK_BES_21 = "#_ctl0_cph_lvwActividades__ctl21_CheckBox1"

# HEMOS checkboxes
CHK_HEMOS_12 = "#_ctl0_cph_lvwActividades__ctl12_CheckBox1"
CHK_HEMOS_14 = "#_ctl0_cph_lvwActividades__ctl14_CheckBox1"

# BIM4 checkbox
CHK_BIM4_7 = "#_ctl0_cph_lvwActividades__ctl7_CheckBox1"

# BES2 checkbox
CHK_BES2_2 = "#_ctl0_cph_lvwActividades__ctl2_CheckBox1"

# Printing
USE_KIOSK_PRINTING = True  # True = no print dialog (prints to default printer)
PRINT_PAUSE_MS = 4000       # give time for print dialog to appear (if not kiosk)
USE_XDOTOOL = True          # True = use xdotool to press Enter on print dialog (Linux only)
USE_PRIVATE_MODE = True     # True = launch in incognito/private mode

PRINT_PA3 = "#_ctl0_cph_lvwActividades__ctl3_CheckBox1"
CHK_BES_7 = "#_ctl0_cph_lvwActividades__ctl7_CheckBox1"
CHK_BES_8 = "#_ctl0_cph_lvwActividades__ctl8_CheckBox1"
CHK_BES_9 = "#_ctl0_cph_lvwActividades__ctl9_CheckBox1"
CHK_BES_15 = "#_ctl0_cph_lvwActividades__ctl15_CheckBox1"
CHK_BES_16 = "#_ctl0_cph_lvwActividades__ctl16_CheckBox1"
CHK_BES_17 = "#_ctl0_cph_lvwActividades__ctl17_CheckBox1"
CHK_BES_18 = "#_ctl0_cph_lvwActividades__ctl18_CheckBox1"
CHK_BES_19 = "#_ctl0_cph_lvwActividades__ctl19_CheckBox1"
CHK_BES_20 = "#_ctl0_cph_lvwActividades__ctl20

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

async def press_ctrl_p(page):
    """Send Ctrl+P keyboard shortcut to trigger print dialog."""
    page.bring_to_front()
    await page.evaluate('(() => {window.waitForPrintDialog = new Promise(f => window.print = f);})()')
    await page.waitForFunction('window.waitForPrintDialog')

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
    """Show date selection menu and return selected date."""
    today = date.today()
    tomorrow = today + timedelta(days=1)
    after_tomorrow = today + timedelta(days=2)
    
    options = [
        f"Aujourd'hui     ({today.strftime('%d/%m/%Y')})",
        f"Demain          ({tomorrow.strftime('%d/%m/%Y')})",
        f"Après-demain    ({after_tomorrow.strftime('%d/%m/%Y')})",
    ]
    dates = [today, tomorrow, after_tomorrow]
    
    print()
    print("Sélectionnez la date de rendez-vous:")
    choice = select(options, cursor=">", cursor_style="cyan")
    
    selected = dates[options.index(choice)]
    print(f"\n[INFO] Date sélectionnée: {selected.strftime('%d/%m/%Y')}")
    return selected.strftime("%d/%m/%Y") + " 08:00:00"

def get_selected_bookings():
    """Show multi-select menu for booking types."""
    options = ["CYTO", "BES", "HEMOS", "BIM4", "BES2"]
    
    print()
    print("Sélectionnez les types de réservation (Espace pour sélectionner, Entrée pour valider):")
    selected = select_multiple(options, tick_character="✓", tick_style="green", cursor_style="cyan")
    
    if not selected:
        print("[WARNING] Aucune réservation sélectionnée, toutes seront effectuées.")
        return options
    
    print(f"\n[INFO] Réservations sélectionnées: {', '.join(selected)}")
    return selected

def main():
    clear_console()
    
    # Get list of IPP from user
    ipp_list = get_ipp_list()
    
    if not ipp_list:
        print("[ERREUR] Aucun IPP fourni. Fermeture du programme.")
        return
    
    print(f"\n[INFO] {len(ipp_list)} IPP à traiter: {', '.join(ipp_list)}")
    
    # Get selected date from user
    selected_date_08 = get_selected_date()
    
    # Get selected booking types from user
    selected_bookings = get_selected_bookings()
    print()
    
    # username = input("Username: ")
    username = "KAMAHTIL"
    # password = getpass.getpass("Password: ")
    password = "140221"

    yesterday = date.today() - timedelta(days=1)

    with sync_playwright() as p:
        launch_args = []
        if USE_KIOSK_PRINTING:
            launch_args.append("--kiosk-printing")
        if USE_PRIVATE_MODE:
            launch_args.append("--incognito")

        browser = p.chromium.launch(
            headless=False,
            args=launch_args
        )

        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()
        if DEFAULT_TIMEOUT_MS > 0:
            page.set_default_timeout(DEFAULT_TIMEOUT_MS)
        else:
            page.set_default_timeout(0)  # No timeout

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
            page.wait_for_load_state("networkidle")
            
            page.keyboard.press("Escape")
            page.keyboard.press("Enter")
            page.keyboard.press("Escape")

            safe_check(page, CHK_MANTENER)
            
            # ==========================================
            # FIRST BOOKING: CYTO
            # ==========================================
            if "CYTO" in selected_bookings:
                log("[INFO] Starting first booking (CYTO)...")
                safe_fill(page, TXT_CONSULTA, "CYTO")
                page.keyboard.press("Enter")
                safe_fill(page, TXT_OBS, "     ")
                page.keyboard.press("Enter")
                safe_click(page, CMD_HORAS)
                page.wait_for_load_state("networkidle")

                # activity checkbox + tomorrow 08:00 + add cita + aplicar
                safe_check_in_iframe(page, CHK_ACTIVIDAD, "VentanaModal_1_ifrm")
                log(selected_date_08)
                safe_fill_in_iframe(page, TXT_FECHA_EXTRA, selected_date_08, "VentanaModal_1_ifrm")
                # page.wait_for_load_state("networkidle")
                # safe_click_in_iframe_by_id(page, BLANK_SPACE, "VentanaModal_1_ifrm")
                # page.wait_for_load_state("networkidle")
                safe_click_in_iframe_by_id(page, BTN_ADD_CITA_EXTRA, "VentanaModal_1_ifrm")
                page.wait_for_load_state("networkidle")
                
                # Zoom out
                log("[INFO] Zooming out...")
                page.keyboard.down("Control")
                page.keyboard.press("Minus")
                page.keyboard.up("Control")
                page.wait_for_timeout(500)
                
                # Set up dialog handler just before clicking BTN_APLICAR
                def handle_dialog(dialog):
                    log(f"[INFO] Alert detected: {dialog.message}")
                    dialog.accept()
                
                page.once("dialog", handle_dialog)
                
                try:
                    with page.expect_popup(timeout=10000) as popup_info:
                        safe_click_in_iframe_by_id(page, BTN_APLICAR, "VentanaModal_1_ifrm")
                    
                    print_page = popup_info.value
                    pdf_url = print_page.url
                    log(f"[INFO] Popup PDF URL: {pdf_url}")
                    log("[INFO] Popup window opened, bringing to front...")
                    print_page.bring_to_front()
                    print_page.wait_for_load_state("networkidle")
                    print_page.wait_for_load_state("load")
                    print_page.wait_for_timeout(3000)  # Extra time for content rendering
                    
                    # Trigger print using JavaScript
                    log("[INFO] Triggering print dialog via JavaScript...")
                    print_page.evaluate("window.print()")
                    
                    if USE_KIOSK_PRINTING:
                        log("[INFO] Kiosk printing enabled - printing directly to default printer...")
                        print_page.wait_for_timeout(3000)
                    elif USE_XDOTOOL:
                        log("[INFO] Using xdotool to confirm print dialog...")
                        print_page.wait_for_timeout(2000)  # Wait for print dialog to appear
                        subprocess.run(["xdotool", "key", "Return"], check=False)
                        print_page.wait_for_timeout(2000)
                    else:
                        log("[INFO] Print dialog should be open. Waiting for user to print...")
                        print_page.wait_for_timeout(30000)  # Wait 30 seconds for user to handle print dialog
                except PlaywrightTimeoutError:
                    log("[WARNING] No popup detected. Checking for new pages in context...")
                    # Check if a new page was opened
                    pages = context.pages
                    if len(pages) > 1:
                        print_page = pages[-1]  # Get the last opened page
                        log(f"[INFO] Found new page: {print_page.url}")
                        print_page.bring_to_front()
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
                    else:
                        log("[WARNING] No new page found")

                # print_page.close()

                log("[INFO] First booking (CYTO) completed.")
                
                # Close print popup and go back to main window
                try:
                    print_page.close()
                except Exception:
                    pass
                
                page.bring_to_front()
                page.wait_for_timeout(1000)
                
                # Click Cerrar button to close modal
                safe_click_in_iframe_by_id(page, BTN_CERRAR, "VentanaModal_1_ifrm")
                page.wait_for_load_state("networkidle")
            
            # ==========================================
            # SECOND BOOKING: BES
            # ==========================================
            if "BES" in selected_bookings:
                log("[INFO] Starting second booking (BES)...")
            
                # Fill TXT_CONSULTA with "BES"
                safe_fill(page, TXT_CONSULTA, "BES")
                page.keyboard.press("Enter")
                
                # Fill observation with empty spaces
                safe_fill(page, TXT_OBS, "     ")
                page.keyboard.press("Enter")
                
                # Click CMD_HORAS to open modal
                safe_click(page, CMD_HORAS)
                page.wait_for_load_state("networkidle")
                
                # Select BES checkboxes in iframe
                safe_check_in_iframe(page, CHK_BES_7, "VentanaModal_1_ifrm")
                safe_check_in_iframe(page, CHK_BES_8, "VentanaModal_1_ifrm")
                safe_check_in_iframe(page, CHK_BES_9, "VentanaModal_1_ifrm")
                safe_check_in_iframe(page, CHK_BES_15, "VentanaModal_1_ifrm")
                safe_check_in_iframe(page, CHK_BES_21, "VentanaModal_1_ifrm")
                
                # Fill date with selected date
                log(f"[INFO] Setting date: {selected_date_08}")
                safe_fill_in_iframe(page, TXT_FECHA_EXTRA, selected_date_08, "VentanaModal_1_ifrm")
                
                # Add cita extra
                safe_click_in_iframe_by_id(page, BTN_ADD_CITA_EXTRA, "VentanaModal_1_ifrm")
                page.wait_for_load_state("networkidle")
                
                # Zoom out
                log("[INFO] Zooming out...")
                page.keyboard.down("Control")
                page.keyboard.press("Minus")
                page.keyboard.up("Control")3, "VentanaModal_1_ifrm")
                safe_check_in_iframe(page, CHK_BES_7, "VentanaModal_1_ifrm")
                safe_check_in_iframe(page, CHK_BES_8, "VentanaModal_1_ifrm")
                safe_check_in_iframe(page, CHK_BES_9, "VentanaModal_1_ifrm")
                safe_check_in_iframe(page, CHK_BES_15, "VentanaModal_1_ifrm")
                safe_check_in_iframe(page, CHK_BES_16, "VentanaModal_1_ifrm")
                safe_check_in_iframe(page, CHK_BES_17, "VentanaModal_1_ifrm")
                safe_check_in_iframe(page, CHK_BES_18, "VentanaModal_1_ifrm")
                safe_check_in_iframe(page, CHK_BES_19, "VentanaModal_1_ifrm")
                safe_check_in_iframe(page, CHK_BES_20ng
                page.once("dialog", handle_dialog)
                
                try:
                    with page.expect_popup(timeout=10000) as popup_info:
                        safe_click_in_iframe_by_id(page, BTN_APLICAR, "VentanaModal_1_ifrm")
                    
                    print_page = popup_info.value
                    pdf_url = print_page.url
                    log(f"[INFO] Popup PDF URL: {pdf_url}")
                    log("[INFO] Popup window opened, bringing to front...")
                    print_page.bring_to_front()
                    print_page.wait_for_load_state("networkidle")
                    print_page.wait_for_load_state("load")
                    print_page.wait_for_timeout(3000)
                    
                    # Trigger print using JavaScript
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
                        
                    # Close print popup
                    try:
                        print_page.close()
                    except Exception:
                        pass
                except PlaywrightTimeoutError:
                    log("[WARNING] No popup detected for BES booking. Checking for new pages in context...")
                    pages = context.pages
                    if len(pages) > 1:
                        print_page = pages[-1]
                        log(f"[INFO] Found new page: {print_page.url}")
                        print_page.bring_to_front()
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
                            
                        try:
                            print_page.close()
                        except Exception:
                            pass
                    else:
                        log("[WARNING] No new page found")

                log("[INFO] Second booking (BES) completed.")
                
                # Close print popup and go back to main window
                try:
                    print_page.close()
                except Exception:
                    pass
                
                page.bring_to_front()
                page.wait_for_timeout(1000)
                
                # Click Cerrar button to close modal
                safe_click_in_iframe_by_id(page, BTN_CERRAR, "VentanaModal_1_ifrm")
                page.wait_for_load_state("networkidle")

            # ==========================================
            # THIRD BOOKING: HEMOS
            # ==========================================
            if "HEMOS" in selected_bookings:
                log("[INFO] Starting third booking (HEMOS)...")
            
                # Fill TXT_CONSULTA with "HEMOS"
                safe_fill(page, TXT_CONSULTA, "HEMOS")
                page.keyboard.press("Enter")
                
                # Fill observation with empty spaces
                safe_fill(page, TXT_OBS, "     ")
                page.keyboard.press("Enter")
                
                # Click CMD_HORAS to open modal
                safe_click(page, CMD_HORAS)
                page.wait_for_load_state("networkidle")
                
                # Select HEMOS checkboxes in iframe
                safe_check_in_iframe(page, CHK_HEMOS_12, "VentanaModal_1_ifrm")
                safe_check_in_iframe(page, CHK_HEMOS_14, "VentanaModal_1_ifrm")
                
                # Fill date with selected date
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
                
                # Set up dialog handler for HEMOS booking
                page.once("dialog", handle_dialog)
                
                try:
                    with page.expect_popup(timeout=10000) as popup_info:
                        safe_click_in_iframe_by_id(page, BTN_APLICAR, "VentanaModal_1_ifrm")
                    
                    print_page = popup_info.value
                    pdf_url = print_page.url
                    log(f"[INFO] Popup PDF URL: {pdf_url}")
                    log("[INFO] Popup window opened, bringing to front...")
                    print_page.bring_to_front()
                    print_page.wait_for_load_state("networkidle")
                    print_page.wait_for_load_state("load")
                    print_page.wait_for_timeout(3000)
                    
                    # Trigger print using JavaScript
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
                        
                    # Close print popup
                    try:
                        print_page.close()
                    except Exception:
                        pass
                except PlaywrightTimeoutError:
                    log("[WARNING] No popup detected for HEMOS booking. Checking for new pages in context...")
                    pages = context.pages
                    if len(pages) > 1:
                        print_page = pages[-1]
                        log(f"[INFO] Found new page: {print_page.url}")
                        print_page.bring_to_front()
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
                            
                        try:
                            print_page.close()
                        except Exception:
                            pass
                    else:
                        log("[WARNING] No new page found")

                log("[INFO] Third booking (HEMOS) completed.")
                
                # Close print popup and go back to main window
                try:
                    print_page.close()
                except Exception:
                    pass
                
                page.bring_to_front()
                page.wait_for_timeout(1000)
                
                # Click Cerrar button to close modal
                safe_click_in_iframe_by_id(page, BTN_CERRAR, "VentanaModal_1_ifrm")
                page.wait_for_load_state("networkidle")

            # ==========================================
            # FOURTH BOOKING: BIM4
            # ==========================================
            if "BIM4" in selected_bookings:
                log("[INFO] Starting fourth booking (BIM4)...")
            
                # Fill TXT_CONSULTA with "BIM4"
                safe_fill(page, TXT_CONSULTA, "BIM4")
                page.keyboard.press("Enter")
                
                # Fill observation with empty spaces
                safe_fill(page, TXT_OBS, "     ")
                page.keyboard.press("Enter")
                
                # Click CMD_HORAS to open modal
                safe_click(page, CMD_HORAS)
                page.wait_for_load_state("networkidle")
                
                # Select BIM4 checkbox in iframe
                safe_check_in_iframe(page, CHK_BIM4_7, "VentanaModal_1_ifrm")
                
                # Fill date with selected date
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
                
                # Set up dialog handler for BIM4 booking
                page.once("dialog", handle_dialog)
                
                try:
                    with page.expect_popup(timeout=10000) as popup_info:
                        safe_click_in_iframe_by_id(page, BTN_APLICAR, "VentanaModal_1_ifrm")
                    
                    print_page = popup_info.value
                    pdf_url = print_page.url
                    log(f"[INFO] Popup PDF URL: {pdf_url}")
                    log("[INFO] Popup window opened, bringing to front...")
                    print_page.bring_to_front()
                    print_page.wait_for_load_state("networkidle")
                    print_page.wait_for_load_state("load")
                    print_page.wait_for_timeout(3000)
                    
                    # Trigger print using JavaScript
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
                        
                    # Close print popup
                    try:
                        print_page.close()
                    except Exception:
                        pass
                except PlaywrightTimeoutError:
                    log("[WARNING] No popup detected for BIM4 booking. Checking for new pages in context...")
                    pages = context.pages
                    if len(pages) > 1:
                        print_page = pages[-1]
                        log(f"[INFO] Found new page: {print_page.url}")
                        print_page.bring_to_front()
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
                            
                        try:
                            print_page.close()
                        except Exception:
                            pass
                    else:
                        log("[WARNING] No new page found")

                log("[INFO] Fourth booking (BIM4) completed.")
                
                # Close print popup and go back to main window
                try:
                    print_page.close()
                except Exception:
                    pass
                
                page.bring_to_front()
                page.wait_for_timeout(1000)
                
                # Click Cerrar button to close modal
                safe_click_in_iframe_by_id(page, BTN_CERRAR, "VentanaModal_1_ifrm")
                page.wait_for_load_state("networkidle")

            # ==========================================
            # FIFTH BOOKING: BES2
            # ==========================================
            if "BES2" in selected_bookings:
                log("[INFO] Starting fifth booking (BES2)...")
                safe_fill(page, TXT_CONSULTA, "BES2")
                page.keyboard.press("Enter")
                
                # Fill observation with empty spaces
                safe_fill(page, TXT_OBS, "     ")
                page.keyboard.press("Enter")
                
                # Click CMD_HORAS to open modal
                safe_click(page, CMD_HORAS)
                page.wait_for_load_state("networkidle")
                
                # Select BES2 checkbox in iframe
                safe_check_in_iframe(page, CHK_BES2_2, "VentanaModal_1_ifrm")
                
                # Fill date with selected date
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
                
                # Set up dialog handler for BES2 booking
                page.once("dialog", handle_dialog)
                
                try:
                    with page.expect_popup(timeout=10000) as popup_info:
                        safe_click_in_iframe_by_id(page, BTN_APLICAR, "VentanaModal_1_ifrm")
                    
                    print_page = popup_info.value
                    pdf_url = print_page.url
                    log(f"[INFO] Popup PDF URL: {pdf_url}")
                    log("[INFO] Popup window opened, bringing to front...")
                    print_page.bring_to_front()
                    print_page.wait_for_load_state("networkidle")
                    print_page.wait_for_load_state("load")
                    print_page.wait_for_timeout(3000)
                    
                    # Trigger print using JavaScript
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
                        
                    # Close print popup
                    try:
                        print_page.close()
                    except Exception:
                        pass
                except PlaywrightTimeoutError:
                    log("[WARNING] No popup detected for BES2 booking. Checking for new pages in context...")
                    pages = context.pages
                    if len(pages) > 1:
                        print_page = pages[-1]
                        log(f"[INFO] Found new page: {print_page.url}")
                        print_page.bring_to_front()
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
                            
                        try:
                            print_page.close()
                        except Exception:
                            pass
                    else:
                        log("[WARNING] No new page found")

                log("[INFO] Fifth booking (BES2) completed.")
            
            print(f"[INFO] IPP {current_ipp} terminé avec succès!")

        print(f"\n{'='*50}")
        print(f"[INFO] Tous les {len(ipp_list)} IPP ont été traités!")
        print(f"{'='*50}")
        print("[INFO] Script terminé. Appuyez sur Ctrl+C pour arrêter.")
        page.wait_for_timeout(10**9)

        browser.close()

if __name__ == "__main__":
    main()
