"""
-------------------------------------------
  app.py — Dynamic Stocks Options Terminal
-------------------------------------------

The driver code to run the terminal app
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
from widgets.switcher import TerminalSwitcherModal
from widgets.interval_modal import IntervalModal, INTERVALS
from widgets.update_modal import UpdateModal

import urllib.request
import json
import threading

CURRENT_VERSION = "v1.7.0"

def check_for_updates(app_instance):
    """
    Checks GitHub for a new release in the background.
    Safely hands the data back to the main UI thread if an update exists.
    """
    api_url = "https://api.github.com/repos/SNeel07/bitGreek-Terminal/releases/latest"
    
    try:
        
        req = urllib.request.Request(api_url, headers={'User-Agent': 'BitGreek-Terminal-App'})
        
        with urllib.request.urlopen(req, timeout=3) as response:
            data = json.loads(response.read().decode())
            
        latest_version = data.get("tag_name")
        

        if latest_version and latest_version != CURRENT_VERSION:
            
            download_url = None
            for asset in data.get("assets", []):
                if asset.get("name", "").endswith(".exe"):
                    download_url = asset.get("browser_download_url")
                    break
            
            release_notes = (
                "A new version of BitGreek Terminal is available!\n\n"
                "Update: Introduced a per strike PE CE difference bar "
                "Click [b cyan]Install Update[/b cyan] to download the "
                "new setup file. You can safely continue using the terminal meanwhile "
                "while the update downloads in the background."
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
# Mapping tickers to their specific NSE company descriptors
SUPPORTED_SYMBOLS = {
    "NIFTY": "NIFTY 50 Index",
    "BANKNIFTY": "NIFTY Bank Index",
    "RELIANCE": "Reliance Industries Limited",
    "HDFCBANK": "HDFC Bank Limited",
    "BHARTIARTL": "Bharti Airtel Limited",
    "AXISBANK": "Axis Bank Limited",
    "ICICIBANK": "ICICI Bank Limited",
    "SBIN": "State Bank of India",
    "TCS": "Tata Consultancy Services Limited",
    "BAJFINANCE": "Bajaj Finance Limited",
    "LT": "Larsen & Toubro Limited",
    "HINDUNILVR": "Hindustan Unilever Limited",
    "INFY": "Infosys Limited",
    "SUNPHARMA": "Sun Pharmaceutical Industries Limited",
    "ADANIPORTS": "Adani Ports and Special Economic Zone Limited",
    "MARUTI": "Maruti Suzuki India Limited",
    "ADANIENT": "Adani Enterprises Limited",
    "M&M": "Mahindra & Mahindra Limited",
    "TITAN": "Titan Company Limited",
    "ITC": "ITC Limited",
    "NTPC": "NTPC Limited",
    "ULTRACEMCO": "UltraTech Cement Limited",
    "ONGC": "Oil & Natural Gas Corporation Limited",
    "JSWSTEEL": "JSW Steel Limited",
    "HCLTECH": "HCL Technologies Limited",
    "BEL": "Bharat Electronics Limited",
    "BAJAJ-AUTO": "Bajaj Auto Limited",
    "NESTLEIND": "Nestle India Limited",
    "COALINDIA": "Coal India Limited",
    "POWERGRID": "Power Grid Corporation of India Limited",
    "BAJAJFINSV": "Bajaj Finserv Limited",
    "ASIANPAINT": "Asian Paints Limited",
    "TATASTEEL": "Tata Steel Limited",
    "HINDALCO": "Hindalco Industries Limited",
    "ETERNAL": "Eternal Limited",
    "GRASIM": "Grasim Industries Limited",
    "SHRIRAMFIN": "Shriram Finance Limited",
    "EICHERMOT": "Eicher Motors Limited",
    "WIPRO": "Wipro Limited",
    "INDIGO": "InterGlobe Aviation Limited",
    "SBILIFE": "SBI Life Insurance Company Limited",
    "JIOFIN": "Jio Financial Services Limited",
    "TECHM": "Tech Mahindra Limited",
    "TRENT": "Trent Limited",
    "TMPV": "Tata Motors Passenger Vehicles Limited",
    "APOLLOHOSP": "Apollo Hospitals Enterprise Limited",
    "HDFCLIFE": "HDFC Life Insurance Company Limited",
    "CIPLA": "Cipla Limited",
    "TATACONSUM": "Tata Consumer Products Limited",
    "DRREDDY": "Dr. Reddy's Laboratories Limited",
    "MAXHEALTH": "Max Healthcare Institute Limited",
    "KOTAKBANK": "Kotak Mahindra Bank Limited"
}


# --------------- NSE TRADING HOLIDAYS 2026 ----------------------

NSE_HOLIDAYS_2026 = {
    "2026-01-15", "2026-01-26", "2026-03-03", "2026-03-26", "2026-03-31",
    "2026-04-03", "2026-04-14", "2026-05-01", "2026-05-28", "2026-06-26",
    "2026-09-14", "2026-10-02", "2026-10-20", "2026-11-08", "2026-11-10",
    "2026-11-24", "2026-12-25"
}

def is_trading_holiday(date: "datetime") -> bool:
    return date.strftime("%Y-%m-%d") in NSE_HOLIDAYS_2026

def is_market_open() -> bool:
    now = datetime.now(IST)
    if now.weekday() >= 5:
        return False
    if is_trading_holiday(now):
        return False
    hhmm = now.hour * 100 + now.minute
    return 915 <= hhmm < 1530


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
        try:
            self.query_one("#download_progress", Static).display = False
        except Exception:
            pass

    def action_force_refresh(self):
        self.app.action_force_refresh()

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
        self.last_raw_data    = None
        self.target_expiry    = None
        self._refresh_event   = threading.Event()
        
        # Track the active dynamic equity symbol (Default to NIFTY)
        self.current_symbol   = "NIFTY"
        self.poll_interval    = DEFAULT_INTERVAL

        self.show_straddle    = False

    def on_mount(self) -> None:
        self.title = "bitGreek Terminal"
        self.install_screen(OptionsDisplayScreen(), name="options_display")
        self.push_screen("options_display")
        
        # Launch the update checker in the background
        threading.Thread(target=check_for_updates, args=(self,), daemon=True).start()
        
        self.update_data_loop()

    def show_update_modal(self, version: str, download_url: str, release_notes: str):
        """Called by the background updater thread to display the modal."""
        self.push_screen(UpdateModal(version, download_url, release_notes))

    def rebuild_columns(self):
        """Dynamically clears and reconstructs the data table columns."""
        try:
            table = self.screen.query_one("#spurt_table")
            table.clear(columns=True)
            
            cols = [
                "CE ΔOI", "CE OI", "CE LTP", "CE Trend", 
                "      ", "Strike", "     ", "Net OI", 
                "PE Trend", "PE LTP", "PE OI", "PE ΔOI"
            ]
            
            # Conditionally append the Straddle column
            if self.show_straddle:
                cols.append("Straddle")
                
            table.add_columns(*cols)
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
            self.refresh_ui(is_market_open())

    def action_switch_terminal(self):
        
        self.push_screen(
            TerminalSwitcherModal(self.current_symbol),
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
        
        # Reset current data buffers so it doesn't mix up calculations between stock transitions
        self.last_raw_data = None
        self.target_expiry = None
        self.store.clear_store()
        
        # Dynamically change the structural target symbol in the active widgets
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
            market_open   = is_market_open()
            active_ticker = self.current_symbol
            now_str       = datetime.now(IST).strftime("%H:%M:%S")

            self.call_from_thread(self._refresh_header, market_open)

            self.call_from_thread(
                self.notify,
                f"Fetching live {active_ticker} data... [{now_str}]",
                severity="information",
                timeout=4,
            )

            # Pass the active dynamic ticker straight to your scraper object
            raw_data = self.fetcher.get_option_chain(active_ticker, self.target_expiry)

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

        table.clear()

        strikes     = self.store.get_all_strikes()
        underlying  = self.store.current_underlying
        current_exp = getattr(self.store, 'current_expiry', None) or "Awaiting API"

        self.sub_title = f"{self.current_symbol} | Expiry: {current_exp} | Spot: ₹{underlying:,.2f}"

        if underlying == 0 or not strikes:
            return

        closest = min(strikes, key=lambda x: abs(x - underlying))
        idx     = strikes.index(closest)
        lo      = max(0, idx - ATM_WING)
        hi      = min(len(strikes), idx + ATM_WING + 1)
        display = strikes[lo:hi]

        # Calculate the maximum difference for proportional scaling ---
        max_diff = 1
        for strike in display:
            c_hist = self.store.get_history(strike, 'CE')
            p_hist = self.store.get_history(strike, 'PE')
            c_oi = c_hist[-1].get('oi', 0) if c_hist else 0
            p_oi = p_hist[-1].get('oi', 0) if p_hist else 0
            max_diff = max(max_diff, abs(p_oi - c_oi))
            
        MAX_BAR_WIDTH = 12  # Maximum characters for each side

        for strike in display:
            ce_hist = self.store.get_history(strike, 'CE')
            pe_hist = self.store.get_history(strike, 'PE')

            ce_trend = SpurtCalculator.classify_spurt(ce_hist)
            pe_trend = SpurtCalculator.classify_spurt(pe_hist)

            ce = ce_hist[-1] if ce_hist else {'price': 0.0, 'oi': 0, 'doi': 0}
            pe = pe_hist[-1] if pe_hist else {'price': 0.0, 'oi': 0, 'doi': 0}
            
            # --- UPDATED: Split visual histogram bars ---
            diff = pe.get('oi', 0) - ce.get('oi', 0)
            
            # Calculate proportional length
            bar_len = int((abs(diff) / max_diff) * MAX_BAR_WIDTH)
            
            # Force a minimum of 1 block if there is a difference
            if diff != 0 and bar_len == 0:
                bar_len = 1
                
            bar_char = "█" * bar_len
            
            empty_space = " " * MAX_BAR_WIDTH

            if diff < 0:
                # Call heavy
                left_bar = Text(bar_char.rjust(MAX_BAR_WIDTH), style="bold red")
                right_bar = Text(empty_space)
            elif diff > 0:
                # Put heavy
                left_bar = Text(empty_space)
                right_bar = Text(bar_char.ljust(MAX_BAR_WIDTH), style="bold green")
            else:
                left_bar = Text(empty_space)
                right_bar = Text(empty_space)

            strike_cell = Text(
                f"{strike:,.0f}",
                style="bold yellow" if strike == closest else "white"
            )

            
            if diff > 0:
                net_oi_cell = Text(f"+{diff:,}", style="bold green")
            elif diff < 0:
                net_oi_cell = Text(f"{diff:,}", style="bold red")
            else:
                net_oi_cell = Text("0", style="white")

            # --- UPDATED: Add net_oi_cell to the row ---
            straddle = ce.get('price', 0.0) + pe.get('price', 0.0)

            # --- UPDATED: Package the row data dynamically ---
            row_data = [
                self._style_doi(ce.get('doi', 0)),
                f"{ce.get('oi', 0):,}",
                f"{ce.get('price', 0.0):.2f}",
                self._style_trend(ce_trend),
                left_bar,
                strike_cell,
                right_bar,
                net_oi_cell,
                self._style_trend(pe_trend),
                f"{pe.get('price', 0.0):.2f}",
                f"{pe.get('oi', 0):,}",
                self._style_doi(pe.get('doi', 0)),
            ]

            # Append the calculated straddle if the toggle is ON
            if self.show_straddle:
                row_data.append(Text(f"{straddle:.2f}", style="cyan"))

            # Unpack the list directly into the row
            table.add_row(*row_data)

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


if __name__ == "__main__":
    
    # Launch the terminal
    app = TradingTerminal()
    app.run()