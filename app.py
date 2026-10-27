"""
-------------------------------------------
  app.py — Dynamic Stocks Options Terminal
-------------------------------------------

Live options OI terminal built with Textual.
Supports switching between NIFTY index and individual equities.

Keybindings (global):
    q — Quit
    s — Toggle quick links sidebar
    t — Switch active stock/index
    i — Change fetch interval

Keybindings (Terminal screen):
    r — Force refresh
    f — Filter expiry date
"""
import urllib.request
import json
import uuid
import threading
from pathlib import Path
import time
import threading
from datetime import datetime
from zoneinfo import ZoneInfo

from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import Header, Footer, Static

from widgets.expiry_modal import ExpiryModal

from fetcher import NSEDataFetcher
from store import OptionsDataStore
from calculator import SpurtCalculator
from widgets.oi_table import OITable
from widgets.header import MarketHeader

from widgets.sidebar import LinkSidebar
from widgets.switcher import TerminalSwitcherModal  # We will update this modal next
from widgets.interval_modal import IntervalModal, INTERVALS
from widgets.update_modal import UpdateModal

import urllib.request
import json
import threading

CURRENT_VERSION = "v1.7.1"

def check_for_updates(app_instance):
    """
    Checks GitHub for a new release in the background.
    Safely hands the data back to the main UI thread if an update exists.
    """
    api_url = "https://api.github.com/repos/SNeel07/bitGreek-Terminal/releases/latest"
    
    try:
        # User-Agent is required by GitHub's API
        req = urllib.request.Request(api_url, headers={'User-Agent': 'BitGreek-Terminal-App'})
        
        with urllib.request.urlopen(req, timeout=3) as response:
            data = json.loads(response.read().decode())
            
        latest_version = data.get("tag_name")
        
        # Compare current version to the latest GitHub tag
        if latest_version and latest_version != CURRENT_VERSION:
            
            # Find the actual .exe download link in the assets array
            download_url = None
            for asset in data.get("assets", []):
                if asset.get("name", "").endswith(".exe"):
                    download_url = asset.get("browser_download_url")
                    break
            
            release_notes = (
                "A new version of BitGreek Terminal is available!\n\n"
                "Update: Added dynamic fetching list for 185 F&O stocks."
                "        Stable UI frame while data refreshing."
            )
            
            # If we found an executable, alert the main Textual app
            if download_url:
                app_instance.call_from_thread(
                    app_instance.show_update_modal, 
                    latest_version, 
                    download_url, 
                    release_notes
                )
                
    except Exception:
        # Silently fail if the user has no internet or GitHub rate-limits the IP
        pass

# --------------- CONSTANTS ----------------

DEFAULT_INTERVAL = 60       # Default poll interval - 60 seconds
ATM_WING         = 70
IST              = ZoneInfo("Asia/Kolkata")



# --------------- COMPANIES MAPPING ----------------
# Base indices. Equities will be fetched dynamically on startup.
SUPPORTED_SYMBOLS = {
    "NIFTY": "NIFTY 50 Index",
    "BANKNIFTY": "NIFTY Bank Index",
}


# ------------- SCREEN DEFINITION --------------------

class OptionsDisplayScreen(Screen):
    """
    A single dynamic screen layout that handles rendering whichever 
    symbol is currently active in the core application.
    """
    BINDINGS = [
        ("r", "force_refresh", "Force Refresh"),
        ("f", "change_expiry", "Filter Expiry"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield MarketHeader(symbol=self.app.current_symbol, id="market_header")
        yield Container(OITable(), id="main_container")
        yield Static(id="download_progress")
        yield Footer()

    

    def on_mount(self) -> None:
        # Explicitly hide the download progress widget on startup
        # CSS display:none alone can flash briefly before being applied
        try:
            self.query_one("#download_progress", Static).display = False
        except Exception:
            pass

    def action_force_refresh(self):
        self.app.action_force_refresh()

    # Filter Expiry feature
    def action_change_expiry(self):
        self.app.action_change_expiry()


# --------------- MAIN APPLICATION ------------------------

class TradingTerminal(App):

    CSS = """
    Screen { background: #0d1117; }

    MarketHeader {
        height: 2;
        background: #161b22;
        color: #8b949e;
        padding: 0 2;
        border-bottom: solid #30363d;
    }

    #main_container {
        padding: 0 1;
        height: 1fr;
    }

    DataTable {
        height: 1fr;
        border: solid #30363d;
    }

    DataTable > .datatable--header  { background: #161b22; color: #e6edf3; text-style: bold; }
    DataTable > .datatable--cursor  { background: #1f2937; }
    DataTable > .datatable--odd-row  { background: #0d1117; }
    DataTable > .datatable--even-row { background: #111827; }

    Screen { 
        background: #0d1117; 
        layers: base overlay; /* This is the magic word that allows widgets to float */
    }

    #download_progress {
        layer: overlay; 
        dock: right;
        margin-top: 1;
        margin-right: 1;
        width: 30;
        height: 3;
        background: #161b22;
        color: #58a6ff;
        border: solid #30363d;
        content-align: center middle;
        text-style: bold;
        display: none; 
    }

    Footer { height: 2; }
    """

    BINDINGS = [
        ("q", "quit",             "Quit"),
        ("s", "toggle_sidebar",   "Links"),
        ("t", "switch_terminal",  "Switch Symbol"),
        ("i", "change_interval",  "Interval"),
        ("p", "toggle_straddle",  "Straddle"),
    ]

    def __init__(self):
        super().__init__()
        self.fetcher          = NSEDataFetcher()
        self.store            = OptionsDataStore()
        
        # NEW: Initialize the dynamic holidays set
        self.dynamic_holidays = set() 
        
        self.last_raw_data    = None
        self.target_expiry    = None
        self._refresh_event   = threading.Event()
        self._rendered_cells  = {}
        
        self.current_symbol   = "NIFTY"
        self.poll_interval    = DEFAULT_INTERVAL
        self.show_straddle    = False

    def on_mount(self) -> None:
        self.title = "bitGreek Terminal"
        self.install_screen(OptionsDisplayScreen(), name="options_display")
        self.push_screen("options_display")
        
        # NEW: Fetch the holidays and symbols dynamically right as the app starts
        self.dynamic_holidays = self.fetcher.fetch_trading_holidays()
        dynamic_symbols = self.fetcher.fetch_fo_symbols()
        
        # Update the global dictionary in-place so the switcher modal sees them
        for sym in dynamic_symbols:
            if sym not in SUPPORTED_SYMBOLS:
                # We map the ticker to itself since the API doesn't provide the full company name
                SUPPORTED_SYMBOLS[sym] = sym 
        
        threading.Thread(target=check_for_updates, args=(self,), daemon=True).start()
        self.update_data_loop()

    def is_market_open(self) -> bool:
        """Dynamic market hours and holiday checker."""
        now = datetime.now(IST)
        if now.weekday() >= 5: # Saturday or Sunday
            return False
            
        # Check against the dynamically pulled list
        if now.strftime("%Y-%m-%d") in self.dynamic_holidays:
            return False
            
        hhmm = now.hour * 100 + now.minute
        return 915 <= hhmm < 1530

    def show_update_modal(self, version: str, download_url: str, release_notes: str):
        """Called by the background updater thread to display the modal."""
        self.push_screen(UpdateModal(version, download_url, release_notes))

    def rebuild_columns(self):
        """Dynamically clears and reconstructs the data table columns with specific keys."""
        try:
            table = self.screen.query_one("#spurt_table")
            table.clear(columns=True)
            self._rendered_cells.clear()
            
            # 1. Define distinct string keys for every column
            self.col_keys = [
                "ce_doi", "ce_oi", "ce_ltp", "ce_trend", 
                "left_bar", "strike", "right_bar", "net_oi", 
                "pe_trend", "pe_ltp", "pe_oi", "pe_doi"
            ]
            
            cols = [
                "CE ΔOI", "CE OI", "CE LTP", "CE Trend", 
                "      ", "Strike", "     ", "Net OI", 
                "PE Trend", "PE LTP", "PE OI", "PE ΔOI"
            ]
            
            if self.show_straddle:
                self.col_keys.append("straddle")
                cols.append("Straddle")
                
            # 2. Map the keys to the columns upon creation
            for key, label in zip(self.col_keys, cols):
                table.add_column(label, key=key)
        except Exception:
            pass

    # -------------- GLOBAL ACTIONS -----------------------

    def action_toggle_sidebar(self):
        self.push_screen(LinkSidebar(self.current_symbol.lower()))

    def action_toggle_straddle(self):
        """Toggles the visibility of the Straddle column and rebuilds the table."""
        self.show_straddle = not self.show_straddle
        self.rebuild_columns()
        
        # Instantly refresh the UI to show the new column data
        if self.last_raw_data is not None:
            self.refresh_ui(self.is_market_open())

    def action_switch_terminal(self):
        # Pass the dynamic keys to the switcher modal
        self.push_screen(
            TerminalSwitcherModal(self.current_symbol, list(SUPPORTED_SYMBOLS.keys())),
            self._on_symbol_switched
        )

    def action_change_interval(self):
        self.push_screen(
            IntervalModal(self.poll_interval),
            self._on_interval_selected
        )

    def _on_interval_selected(self, seconds: int | None):
        if seconds and seconds != self.poll_interval:
            self.poll_interval = seconds
            label = next((lbl for lbl, s in INTERVALS if s == seconds), f"{seconds}s")
            self.notify(f"Fetch interval set to {label}", severity="information", timeout=3)
            self._refresh_event.set()

    def _on_symbol_switched(self, selected_symbol: str | None):
        """
        Triggered when a user picks a company from the selection modal window.
        """
        if not selected_symbol or selected_symbol == self.current_symbol:
            return
            
        self.current_symbol = selected_symbol
        
        # Reset current data buffers so we don't mix up calculations between stock transitions
        self.last_raw_data = None
        self.target_expiry = None
        self._rendered_cells.clear()
        self.store.clear_store()
        
        # Dynamically change the structural target symbol in our active widgets
        try:
            header = self.screen.query_one("#market_header", MarketHeader)
            header.symbol = selected_symbol
        except Exception:
            pass

        self.notify(
            f"Switched to {SUPPORTED_SYMBOLS.get(selected_symbol, selected_symbol)}",
            severity="information",
            timeout=3
        )
        
        # Force the worker thread to skip the remaining sleep loop time and fetch the new ticker data instantly
        self._refresh_event.set()

    def action_force_refresh(self):
        self.notify("Force refresh triggered...", severity="warning", timeout=3)
        self._refresh_event.set()


    # Delete these two methods completely:
    def action_change_expiry(self):
        expiries = getattr(self.store, 'available_expiries', [])
        if not expiries:
            self.notify("No expiries yet. Waiting for first data fetch...", severity="warning")
            return
        self.push_screen(ExpiryModal(expiries), self._apply_expiry)

    def _apply_expiry(self, selected_expiry: str):
        if selected_expiry and selected_expiry != self.target_expiry:
            self.target_expiry = selected_expiry
            self.notify(f"Fetching data for {selected_expiry}...", severity="information")
            
            # Clear old data so the UI doesn't show the wrong strikes while loading
            self.last_raw_data = None
            self._rendered_cells.clear()
            self.store.clear_store()
            
            # Force the background worker to fetch the new date instantly
            self._refresh_event.set()


    # -------------- DYNAMIC BACKGROUND POLLING WORKER ---------------------------

    @work(thread=True)
    def update_data_loop(self):
        """
        Persistent data engine.
        Uses self.current_symbol dynamically to pull whichever target stock is active.
        """
        while True:
            market_open   = self.is_market_open()
            active_ticker = self.current_symbol
            now_str       = datetime.now(IST).strftime("%H:%M:%S")

            self.call_from_thread(self._refresh_header, market_open)

            self.call_from_thread(
                self.notify,
                f"Fetching live {active_ticker} data... [{now_str}]",
                severity="information",
                timeout=4,
            )

            # CRITICAL PASS: Pass the active dynamic ticker straight to your scraper object
            raw_data = self.fetcher.get_option_chain(active_ticker, self.target_expiry)

            # --- MOCK DATA CHANGE FOR AFTER-HOURS UI TESTING ---
            """
            import random

            if raw_data:
                records = raw_data.get("records")
                if isinstance(records, dict):
                    records["timestamp"] = datetime.now(IST).strftime("%d-%b-%Y %H:%M:%S")

                def mutate_option_rows(rows):
                    if not isinstance(rows, list):
                        return
                    for row in rows:
                        if not isinstance(row, dict):
                            continue
                        for side in ("CE", "PE"):
                            option = row.get(side)
                            if not isinstance(option, dict):
                                continue

                            def numeric(value, default=0.0):
                                try:
                                    if value is None or str(value).strip() in ("", "-"):
                                        return default
                                    return float(value)
                                except (TypeError, ValueError):
                                    return default

                            # Deliberately synthetic movement for visual testing only.
                            shift_oi = random.randint(-100000, 100000)
                            shift_price = random.uniform(-2.0, 2.0)
                            option["openInterest"] = max(
                                0, int(numeric(option.get("openInterest")) + shift_oi)
                            )
                            option["changeinOpenInterest"] = int(
                                numeric(option.get("changeinOpenInterest")) + shift_oi
                            )
                            option["lastPrice"] = max(
                                0.1, numeric(option.get("lastPrice")) + shift_price
                            )
                            option["change"] = (
                                numeric(option.get("change")) + shift_price
                            )

                if isinstance(records, dict):
                    mutate_option_rows(records.get("data"))
                filtered = raw_data.get("filtered")
                if isinstance(filtered, dict):
                    mutate_option_rows(filtered.get("data"))
            # --- END MOCK DATA CHANGE --- ---
            """

            # Ensure the user didn't change tickers mid-fetch cycle
            if raw_data and self.current_symbol == active_ticker:
                self.last_raw_data = raw_data
                self.store.update_snapshot(raw_data, self.target_expiry)
                self.call_from_thread(self.refresh_ui, market_open)
            elif not raw_data:
                self.call_from_thread(
                    self.notify,
                    f"Fetch failed for {active_ticker} at {now_str}. Retrying...",
                    severity="error",
                    timeout=6,
                )

            # Wait for interval duration, or break sleep loop instantly on key commands
            self._refresh_event.clear()
            self._refresh_event.wait(timeout=self.poll_interval)

    # ----------------- UI REFRESH ------------------------

    def refresh_ui(self, market_open: bool = True):
        self._refresh_header(market_open)
        self._refresh_table()

    def _refresh_header(self, market_open: bool):
        try:
            header = self.screen.query_one("#market_header", MarketHeader)
            header.refresh_stats(self.store, market_open)
        except Exception:
            pass

    def _refresh_table(self):
        try:
            table = self.screen.query_one("#spurt_table")
        except Exception:
            return

        strikes = self.store.get_all_strikes()
        underlying = self.store.current_underlying
        current_exp = getattr(self.store, "current_expiry", None) or "Awaiting API"
        self.sub_title = (
            f"{self.current_symbol} | Expiry: {current_exp} | Spot: ₹{underlying:,.2f}"
        )

        if underlying == 0 or not strikes:
            return

        closest = min(strikes, key=lambda x: abs(x - underlying))
        idx = strikes.index(closest)
        lo = max(0, idx - ATM_WING)
        hi = min(len(strikes), idx + ATM_WING + 1)
        display = strikes[lo:hi]

        max_diff = 1
        for strike in display:
            c_hist = self.store.get_history(strike, "CE")
            p_hist = self.store.get_history(strike, "PE")
            c_oi = c_hist[-1].get("oi", 0) if c_hist else 0
            p_oi = p_hist[-1].get("oi", 0) if p_hist else 0
            max_diff = max(max_diff, abs(p_oi - c_oi))

        MAX_BAR_WIDTH = 12
        current_display_keys = set()
        existing_row_keys = {row_key.value for row_key in table.rows.keys()}

        def cell_signature(value):
            if isinstance(value, Text):
                return (
                    "Text",
                    value.plain,
                    tuple((span.start, span.end, str(span.style)) for span in value.spans),
                )
            return ("value", str(value))

        for strike in display:
            strike_key = str(strike)
            current_display_keys.add(strike_key)

            ce_hist = self.store.get_history(strike, "CE")
            pe_hist = self.store.get_history(strike, "PE")
            ce_trend = SpurtCalculator.classify_spurt(ce_hist)
            pe_trend = SpurtCalculator.classify_spurt(pe_hist)

            ce = ce_hist[-1] if ce_hist else {"price": 0.0, "oi": 0, "doi": 0}
            pe = pe_hist[-1] if pe_hist else {"price": 0.0, "oi": 0, "doi": 0}
            diff = pe.get("oi", 0) - ce.get("oi", 0)

            bar_len = int((abs(diff) / max_diff) * MAX_BAR_WIDTH)
            if diff != 0 and bar_len == 0:
                bar_len = 1

            bar_char = "█" * bar_len
            empty_space = " " * MAX_BAR_WIDTH

            if diff < 0:
                left_bar = Text(bar_char.rjust(MAX_BAR_WIDTH), style="bold red")
                right_bar = Text(empty_space)
            elif diff > 0:
                left_bar = Text(empty_space)
                right_bar = Text(bar_char.ljust(MAX_BAR_WIDTH), style="bold green")
            else:
                left_bar = Text(empty_space)
                right_bar = Text(empty_space)

            strike_cell = Text(
                f"{strike:,.0f}",
                style="bold yellow" if strike == closest else "white",
            )

            if diff > 0:
                net_oi_cell = Text(f"+{diff:,}", style="bold green")
            elif diff < 0:
                net_oi_cell = Text(f"{diff:,}", style="bold red")
            else:
                net_oi_cell = Text("0", style="white")

            straddle = ce.get("price", 0.0) + pe.get("price", 0.0)
            row_data_dict = {
                "ce_doi": self._style_doi(ce.get("doi", 0)),
                "ce_oi": f"{ce.get('oi', 0):,}",
                "ce_ltp": f"{ce.get('price', 0.0):.2f}",
                "ce_trend": self._style_trend(ce_trend),
                "left_bar": left_bar,
                "strike": strike_cell,
                "right_bar": right_bar,
                "net_oi": net_oi_cell,
                "pe_trend": self._style_trend(pe_trend),
                "pe_ltp": f"{pe.get('price', 0.0):.2f}",
                "pe_oi": f"{pe.get('oi', 0):,}",
                "pe_doi": self._style_doi(pe.get("doi", 0)),
            }

            if self.show_straddle:
                row_data_dict["straddle"] = Text(f"{straddle:.2f}", style="cyan")

            if strike_key not in existing_row_keys:
                row_values = [
                    row_data_dict[key] for key in self.col_keys
                    if key in row_data_dict
                ]
                table.add_row(*row_values, key=strike_key)
                for col_key, value in row_data_dict.items():
                    self._rendered_cells[(strike_key, col_key)] = cell_signature(value)
            else:
                for col_key, value in row_data_dict.items():
                    cache_key = (strike_key, col_key)
                    signature = cell_signature(value)
                    if self._rendered_cells.get(cache_key) != signature:
                        table.update_cell(
                            row_key=strike_key,
                            column_key=col_key,
                            value=value,
                        )
                        self._rendered_cells[cache_key] = signature

        for row_key in existing_row_keys:
            if row_key not in current_display_keys:
                table.remove_row(row_key)
                stale_cache_keys = [
                    key for key in self._rendered_cells if key[0] == row_key
                ]
                for key in stale_cache_keys:
                    del self._rendered_cells[key]

    @staticmethod
    def _style_trend(text: str) -> Text:
        if "Long Buildup" in text or "Short Covering" in text:
            return Text(text, style="bold green")
        elif "Short Buildup" in text or "Long Unwinding" in text:
            return Text(text, style="bold red")
        elif "Low OI" in text:
            return Text(text, style="dim")
        return Text(text, style="bold cyan")

    @staticmethod
    def _style_doi(doi: int) -> Text:
        if doi > 0:
            return Text(f"+{doi:,}", style="green")
        elif doi < 0:
            return Text(f"{doi:,}", style="red")
        return Text("0", style="white")


    
# Launch the terminal
app = TradingTerminal()
app.run()