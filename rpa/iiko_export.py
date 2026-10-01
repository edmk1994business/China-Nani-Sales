r"""
iikoChain 9.4 -> Excel export bot  (Windows, runs daily via Task Scheduler)

What it does
  1. Closes any running iikoChain, launches the desktop shortcut "iikochain 9.4"
  2. Picks server "China Nani", logs in (login/password from config.json)
  3. Selects all companies, opens  Розничные продажи -> OLAP Отчет по продажам
  4. Selects report format "AI update", waits for the data to build
  5. Clicks "Excel..." and saves to a TEMP file, validates it, then atomically
     replaces  C:\Users\edmk1\Dropbox\AI Sales Dashboard\Update Sales.xlsx
  6. Closes iikoChain, waits for Dropbox to sync, optionally pings the dashboard

Usage
  python iiko_export.py --calibrate     # one-time: record button positions (+ image templates)
  python iiko_export.py                 # run the export (what Task Scheduler calls)
  python iiko_export.py --check         # validate config/templates without clicking anything

Why calibration?  iikoChain is a desktop app without an automation API, so the bot clicks
on screen positions. Calibration records those positions (and a small screenshot of each
button) on YOUR screen. At run time the bot first looks for the button image; if it is not
found it falls back to the recorded coordinates. Re-run --calibrate if the screen
resolution, scaling or iiko layout changes.

All text is entered through the clipboard (Ctrl+V), so the active keyboard layout
(EN / RU / HY) does not matter.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import sys
import time
import webbrowser
from datetime import date, datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONFIG_PATH = HERE / "config.json"
TEMPLATES = HERE / "templates"
LOGS = HERE / "logs"
LOCK = HERE / ".running.lock"

try:
    import pyautogui
    import pyperclip
    import psutil
except ImportError as e:  # pragma: no cover
    sys.exit(f"Missing package: {e.name}. Run:  pip install -r requirements-rpa.txt")

try:
    import win32con
    import win32gui
except ImportError:  # pragma: no cover
    win32gui = win32con = None

try:
    import cv2  # noqa: F401  (enables fuzzy image matching in pyautogui)
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

pyautogui.FAILSAFE = True      # slam the mouse into a screen corner to abort
pyautogui.PAUSE = 0.35

log = logging.getLogger("iiko_rpa")

# Order = order of the real workflow. (name, required, instruction shown during calibration)
STEPS = [
    ("server_dropdown",      False, "the SERVER drop-down on the login window (skip if 'China Nani' is always pre-selected)"),
    ("server_item",          False, "the 'China Nani' item in the OPEN server list"),
    ("login_field",          True,  "the LOGIN text box"),
    ("password_field",       True,  "the PASSWORD text box"),
    ("enter_button",         False, "the ENTER / Войти button (skip = press Enter key)"),
    ("companies_select_all", False, "the 'select all' checkbox/button in the companies pop-up (skip = Ctrl+A)"),
    ("companies_ok",         False, "the OK / Enter button of the companies pop-up (skip = press Enter key)"),
    ("menu_retail",          True,  "the 'Розничные продажи' menu"),
    ("menu_olap_sales",      True,  "the 'OLAP Отчет по продажам' menu item"),
    ("report_format_dropdown", True, "the 'Формат отчета' drop-down in the OLAP window"),
    ("report_format_item",   False, "the 'AI update' item in the OPEN format list (skip = type 'AI update' + Enter)"),
    ("build_report_button",  False, "the 'Построить'/'Обновить' (build report) button — skip if the report builds by itself"),
    ("excel_button",         True,  "the 'Excel...' button on the right-hand menu"),
]


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def load_config() -> dict:
    if not CONFIG_PATH.exists():
        sys.exit(f"config.json not found next to the script. Copy config.example.json to config.json and edit it.")
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def save_config(cfg: dict) -> None:
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")


def setup_logging() -> Path:
    LOGS.mkdir(exist_ok=True)
    logfile = LOGS / f"{date.today():%Y-%m-%d}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s %(message)s",
        handlers=[logging.FileHandler(logfile, encoding="utf-8"), logging.StreamHandler(sys.stdout)],
    )
    # keep 30 days of logs/screenshots
    cutoff = time.time() - 30 * 86400
    for f in LOGS.glob("*"):
        if f.stat().st_mtime < cutoff:
            f.unlink(missing_ok=True)
    return logfile


def snap(tag: str) -> None:
    path = LOGS / f"{datetime.now():%Y-%m-%d_%H%M%S}_{tag}.png"
    try:
        pyautogui.screenshot(str(path))
        log.info("Screenshot saved: %s", path.name)
    except Exception as exc:
        log.warning("Screenshot failed: %s", exc)


def paste_text(text: str) -> None:
    pyperclip.copy(text)
    time.sleep(0.15)
    pyautogui.hotkey("ctrl", "a")
    pyautogui.hotkey("ctrl", "v")


def iiko_processes(cfg: dict) -> list:
    names = {n.lower() for n in cfg["iiko_process_names"]}
    out = []
    for p in psutil.process_iter(["name"]):
        try:
            if (p.info["name"] or "").lower() in names:
                out.append(p)
        except psutil.Error:
            pass
    return out


def kill_iiko(cfg: dict) -> None:
    procs = iiko_processes(cfg)
    for p in procs:
        try:
            p.terminate()
        except psutil.Error:
            pass
    gone, alive = psutil.wait_procs(procs, timeout=15)
    for p in alive:
        try:
            p.kill()
        except psutil.Error:
            pass
    if procs:
        log.info("Closed %d running iiko process(es).", len(procs))
        time.sleep(3)


def launch_iiko(cfg: dict) -> None:
    shortcut = Path(os.path.expandvars(cfg["iiko_shortcut"]))
    if not shortcut.exists():
        raise FileNotFoundError(f"iiko shortcut not found: {shortcut}")
    log.info("Launching %s", shortcut)
    os.startfile(str(shortcut))  # type: ignore[attr-defined]


def foreground() -> tuple[int, str, str]:
    if not win32gui:
        return 0, "", ""
    hwnd = win32gui.GetForegroundWindow()
    return hwnd, win32gui.GetWindowText(hwnd), win32gui.GetClassName(hwnd)


def maximize_foreground() -> None:
    if not win32gui:
        pyautogui.hotkey("win", "up")
        return
    hwnd, title, _ = foreground()
    if hwnd:
        win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
        log.info("Maximized window: %s", title)
    time.sleep(1.5)


def wait_for_dialog(timeout: float) -> bool:
    """Wait for a standard Windows dialog (class #32770, e.g. 'Save As') to be in front."""
    end = time.time() + timeout
    while time.time() < end:
        _, _, cls = foreground()
        if cls == "#32770":
            return True
        time.sleep(0.5)
    return False


def wait_cpu_idle(cfg: dict, min_wait: float, max_wait: float, idle_pct: float = 3.0, idle_secs: int = 8) -> None:
    """Wait until iiko stops crunching (CPU below idle_pct for idle_secs in a row)."""
    log.info("Waiting for report data (min %ss, max %ss)…", min_wait, max_wait)
    time.sleep(min_wait)
    end = time.time() + max_wait - min_wait
    quiet, ncpu = 0, max(psutil.cpu_count() or 1, 1)
    while time.time() < end:
        procs = iiko_processes(cfg)
        for p in procs:                      # prime the per-process counters
            try:
                p.cpu_percent(interval=None)
            except psutil.Error:
                pass
        time.sleep(1)
        cpu = 0.0
        for p in procs:
            try:
                cpu += p.cpu_percent(interval=None)
            except psutil.Error:
                pass
        cpu /= ncpu                          # % of the whole machine
        quiet = quiet + 1 if cpu < idle_pct else 0
        if quiet >= idle_secs:
            log.info("iiko is idle — report looks ready.")
            return
    log.warning("Report wait hit the %ss maximum; continuing anyway.", max_wait)


# --------------------------------------------------------------------------- #
# Clicking with image templates + coordinate fallback
# --------------------------------------------------------------------------- #
def locate(name: str):
    tpl = TEMPLATES / f"{name}.png"
    if not tpl.exists():
        return None
    try:
        kw = {"confidence": 0.82} if HAS_CV2 else {}
        box = pyautogui.locateOnScreen(str(tpl), grayscale=True, **kw)
        return pyautogui.center(box) if box else None
    except pyautogui.ImageNotFoundException:
        return None
    except Exception as exc:
        log.debug("locate(%s) error: %s", name, exc)
        return None


def click(cfg: dict, name: str, timeout: float = 30, required: bool = True, double: bool = False) -> bool:
    """Wait for the button image to appear, click it; else fall back to the saved point."""
    pt = cfg["points"].get(name)
    if pt is None and not (TEMPLATES / f"{name}.png").exists():
        if required:
            raise RuntimeError(f"Step '{name}' is not calibrated. Run: python iiko_export.py --calibrate")
        return False
    end = time.time() + timeout
    found = None
    while time.time() < end and (TEMPLATES / f"{name}.png").exists():
        found = locate(name)
        if found:
            break
        time.sleep(1)
    if found:
        x, y = found
        log.info("Click %-22s at %s (image match)", name, (x, y))
    elif pt:
        x, y = pt
        log.info("Click %-22s at %s (saved coordinates)", name, (x, y))
    else:
        if required:
            raise RuntimeError(f"Could not find '{name}' on screen.")
        return False
    (pyautogui.doubleClick if double else pyautogui.click)(x, y)
    return True


# --------------------------------------------------------------------------- #
# File handling
# --------------------------------------------------------------------------- #
def validate_export(path: Path, max_age_days: int) -> str:
    import openpyxl

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.worksheets[0]
    header_found, rows, last_date = False, 0, None
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if not header_found:
            if any(isinstance(v, str) and "Учетный день" in v for v in row):
                header_found = True
            if i > 25:
                break
            continue
        rows += 1
        for v in row[:3]:
            if isinstance(v, datetime):
                last_date = max(last_date, v.date()) if last_date else v.date()
    wb.close()
    if not header_found:
        raise ValueError("Exported file has no 'Учетный день' header — wrong report format?")
    if rows < 5:
        raise ValueError(f"Exported file looks empty ({rows} data rows).")
    if last_date is None or last_date < date.today() - timedelta(days=max_age_days):
        raise ValueError(f"Latest date in export is {last_date} — data looks stale.")
    return f"{rows} rows, latest day {last_date:%d.%m.%Y}"


def wait_for_file(path: Path, timeout: float) -> None:
    end, last = time.time() + timeout, -1
    while time.time() < end:
        if path.exists():
            size = path.stat().st_size
            if size > 0 and size == last:
                return
            last = size
        time.sleep(1.5)
    raise TimeoutError(f"Export file did not appear: {path}")


def publish(tmp_export: Path, dest: Path, retries: int = 10) -> None:
    """Copy next to temp then atomically replace the Dropbox file (no half-written file ever syncs)."""
    staged = tmp_export.with_suffix(".staged.xlsx")
    shutil.copy2(tmp_export, staged)
    dest.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(1, retries + 1):
        try:
            os.replace(staged, dest)
            log.info("Published -> %s", dest)
            return
        except PermissionError:
            log.warning("Destination is locked (open in Excel?). Retry %d/%d in 30s…", attempt, retries)
            time.sleep(30)
        except OSError:  # different drive: fall back to copy
            shutil.copy2(staged, dest)
            staged.unlink(missing_ok=True)
            log.info("Published (copy) -> %s", dest)
            return
    raise PermissionError(f"Could not overwrite {dest} — close it in Excel and re-run.")


# --------------------------------------------------------------------------- #
# Workflow
# --------------------------------------------------------------------------- #
def run_export(cfg: dict) -> None:
    t = cfg["timeouts"]
    tmp_dir = Path(os.path.expandvars(cfg["temp_dir"]))
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_export = tmp_dir / "iiko_export.xlsx"
    tmp_export.unlink(missing_ok=True)          # no "file exists, replace?" prompt later
    dest = Path(cfg["output_path"])

    kill_iiko(cfg)
    launch_iiko(cfg)

    # --- login window -------------------------------------------------------
    log.info("Waiting for login window…")
    time.sleep(t["app_start_min"])
    if click(cfg, "server_dropdown", timeout=t["app_start"], required=False):
        time.sleep(1)
        if not click(cfg, "server_item", timeout=10, required=False):
            paste_text(cfg["server_name"])
            pyautogui.press("enter")
        time.sleep(1)

    click(cfg, "login_field", timeout=t["app_start"])
    paste_text(cfg["login"])
    click(cfg, "password_field", timeout=10)
    paste_text(cfg["password"])
    if not click(cfg, "enter_button", timeout=5, required=False):
        pyautogui.press("enter")
    log.info("Logging in…")

    # --- companies pop-up ---------------------------------------------------
    time.sleep(t["after_login"])
    if not click(cfg, "companies_select_all", timeout=t["login"], required=False):
        pyautogui.hotkey("ctrl", "a")
    time.sleep(0.8)
    if not click(cfg, "companies_ok", timeout=10, required=False):
        pyautogui.press("enter")

    # --- main window --------------------------------------------------------
    log.info("Waiting for main window…")
    time.sleep(t["main_window"])
    maximize_foreground()

    click(cfg, "menu_retail", timeout=t["login"])
    time.sleep(1)
    click(cfg, "menu_olap_sales", timeout=15)
    log.info("Opening OLAP report…")
    time.sleep(t["olap_open"])

    click(cfg, "report_format_dropdown", timeout=60)
    time.sleep(1)
    if not click(cfg, "report_format_item", timeout=10, required=False):
        paste_text(cfg["report_format"])
        pyautogui.press("enter")
    time.sleep(2)
    if click(cfg, "build_report_button", timeout=10, required=False):
        log.info("Build report clicked.")

    wait_cpu_idle(cfg, t["report_build_min"], t["report_build_max"])
    snap("report_ready")

    # --- export -------------------------------------------------------------
    click(cfg, "excel_button", timeout=30)
    if not wait_for_dialog(t["save_dialog"]):
        raise TimeoutError("'Save as' dialog did not appear after clicking Excel…")
    time.sleep(1)
    paste_text(str(tmp_export))                 # filename box has focus by default
    pyautogui.press("enter")
    log.info("Saving to temp file %s", tmp_export)
    wait_for_file(tmp_export, t["save"])
    time.sleep(2)
    _, title, cls = foreground()
    if cls == "#32770":                          # e.g. "Open the file?" message box
        log.info("Closing follow-up dialog '%s'", title)
        pyautogui.press("esc")

    summary = validate_export(tmp_export, cfg.get("max_data_age_days", 3))
    log.info("Export OK: %s", summary)
    publish(tmp_export, dest)

    if cfg.get("close_iiko_after", True):
        kill_iiko(cfg)


def after_publish(cfg: dict) -> None:
    url = (cfg.get("dashboard_url") or "").strip()
    if not url:
        return
    wait = cfg.get("dropbox_sync_wait", 90)
    log.info("Waiting %ss for Dropbox to sync, then refreshing the dashboard…", wait)
    time.sleep(wait)
    sep = "&" if "?" in url else "?"
    webbrowser.open(f"{url}{sep}refresh=1")


# --------------------------------------------------------------------------- #
# Calibration
# --------------------------------------------------------------------------- #
def calibrate(cfg: dict) -> None:
    TEMPLATES.mkdir(exist_ok=True)
    print(__doc__.split("Usage")[0])
    print("CALIBRATION — follow the prompts. For every step:\n"
          "  * press Enter here, then within 5 seconds HOVER the mouse over the requested element\n"
          "  * after the capture, perform that action yourself in iiko (click / type), then come back here\n"
          "  * type 's' + Enter to skip an optional step\n")
    input("Press Enter to launch iikoChain…")
    kill_iiko(cfg)
    launch_iiko(cfg)
    w, h = pyautogui.size()
    for i, (name, required, text) in enumerate(STEPS, 1):
        if name == "menu_retail":
            input("\nLog in & confirm companies yourself if not done yet. When the MAIN window is open, "
                  "press Enter (it will be maximized)…")
            time.sleep(1)
            maximize_foreground()
        tag = "REQUIRED" if required else "optional"
        ans = input(f"\n[{i}/{len(STEPS)}] ({tag}) Hover over {text}.\n    Enter = start 5s countdown, s = skip: ").strip().lower()
        if ans == "s" and not required:
            cfg["points"][name] = None
            (TEMPLATES / f"{name}.png").unlink(missing_ok=True)
            print("    skipped.")
            continue
        for s in range(5, 0, -1):
            print(f"    capturing in {s}…", end="\r")
            time.sleep(1)
        x, y = pyautogui.position()
        cfg["points"][name] = [x, y]
        # take a small template image without the cursor in it
        pyautogui.moveTo(w - 5, h // 2, duration=0.1)
        time.sleep(0.3)
        bw, bh = 90, 34
        region = (max(0, x - bw // 2), max(0, y - bh // 2), bw, bh)
        pyautogui.screenshot(str(TEMPLATES / f"{name}.png"), region=region)
        pyautogui.moveTo(x, y, duration=0.1)
        print(f"    saved {name} at ({x}, {y}).            ")
        if name in ("login_field", "password_field"):
            print("    (now click the field and type your credentials yourself)")
    save_config(cfg)
    print("\nCalibration saved to config.json and templates/. Test with:  python iiko_export.py")


def check(cfg: dict) -> None:
    ok = True
    for name, required, _ in STEPS:
        has = cfg["points"].get(name) is not None
        tpl = (TEMPLATES / f"{name}.png").exists()
        flag = "OK " if has or not required else "MISSING"
        ok &= flag != "MISSING"
        print(f"  {flag:8s} {name:24s} point={cfg['points'].get(name)}  template={'yes' if tpl else 'no'}")
    print(f"  shortcut exists: {Path(os.path.expandvars(cfg['iiko_shortcut'])).exists()}")
    print(f"  output folder exists: {Path(cfg['output_path']).parent.exists()}")
    running = sorted({p.info["name"] for p in psutil.process_iter(["name"])
                      if p.info["name"] and any(k in p.info["name"].lower() for k in ("iiko", "backoffice", "chain"))})
    print(f"  iiko-like processes running now: {running or 'none'}  (configured: {cfg['iiko_process_names']})")
    print(f"  OpenCV fuzzy matching: {'on' if HAS_CV2 else 'off (pip install opencv-python)'}")
    print("READY" if ok else "Run --calibrate first.")


# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--calibrate", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    cfg = load_config()

    if args.calibrate:
        calibrate(cfg)
        return 0
    if args.check:
        check(cfg)
        return 0

    logfile = setup_logging()
    if LOCK.exists() and time.time() - LOCK.stat().st_mtime < 3600:
        log.error("Another run is in progress (%s). Exiting.", LOCK)
        return 2
    LOCK.write_text(str(os.getpid()))
    try:
        attempts = cfg.get("attempts", 2)
        for attempt in range(1, attempts + 1):
            log.info("=== iiko export — attempt %d/%d ===", attempt, attempts)
            try:
                run_export(cfg)
                after_publish(cfg)
                log.info("=== DONE ===")
                return 0
            except pyautogui.FailSafeException:
                log.error("Aborted by user (mouse moved to a screen corner).")
                return 3
            except Exception as exc:
                log.exception("Attempt %d failed: %s", attempt, exc)
                snap(f"error_attempt{attempt}")
                kill_iiko(cfg)
                time.sleep(20)
        log.error("All attempts failed. See %s", logfile)
        return 1
    finally:
        LOCK.unlink(missing_ok=True)


if __name__ == "__main__":
    sys.exit(main())
