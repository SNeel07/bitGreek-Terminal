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

from fetcher import NSEDataFetcher
from store import OptionsDataStore
from calculator import SpurtCalculator
from widgets.oi_table import OITable
from widgets.header import MarketHeader
from widgets.expiry_modal import ExpiryModal
from widgets.sidebar import LinkSidebar
from widgets.switcher import TerminalSwitcherModal
from widgets.interval_modal import IntervalModal, INTERVALS


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
        # We assign an ID to target this header widget dynamically
        yield MarketHeader(symbol=self.app.current_symbol, id="market_header")
        yield Container(OITable(), id="main_container")
        yield Footer()

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

    Footer { height: 2; }
    """

    BINDINGS = [
        ("q", "quit",             "Quit"),
        ("s", "toggle_sidebar",   "Links"),
        ("t", "switch_terminal",  "Switch Symbol"),
        ("i", "change_interval",  "Interval"),
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

    def on_mount(self) -> None:
        self.title = "Options Terminal"
        # Mount our single, dynamic display screen
        self.install_screen(OptionsDisplayScreen(), name="options_display")
        self.push_screen("options_display")
        self.update_data_loop()

    # -------------- GLOBAL ACTIONS -----------------------

    def action_toggle_sidebar(self):
        self.push_screen(LinkSidebar(self.current_symbol.lower()))

    def action_switch_terminal(self):
        # We pass our current selected symbol into the modal selection tool
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
        
        # Reset current data buffers so we don't mix up calculations between stock transitions
        self.last_raw_data = None
        self.target_expiry = None
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

    def action_change_expiry(self):
        expiries = getattr(self.store, 'available_expiries', [])
        if not expiries:
            self.notify("No expiries yet. Waiting for first data fetch...", severity="warning")
            return
        self.push_screen(ExpiryModal(expiries), self._apply_expiry)

    def _apply_expiry(self, selected_expiry: str):
        if selected_expiry and selected_expiry != self.target_expiry:
            self.target_expiry = selected_expiry
            self.notify(f"Switched to expiry: {selected_expiry}", severity="information")
            if self.last_raw_data:
                self.store.update_snapshot(self.last_raw_data, self.target_expiry)
                self.refresh_ui(is_market_open())


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

            # CRITICAL PASS: Pass the active dynamic ticker straight to your scraper object
            raw_data = self.fetcher.get_option_chain(active_ticker)

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

        table.clear()

        strikes     = self.store.get_all_strikes()
        underlying  = self.store.current_underlying
        current_exp = getattr(self.store, 'current_expiry', None) or "Awaiting API"

        # Dynamically set title based on the active dynamic ticker symbol state
        self.sub_title = f"{self.current_symbol} | Expiry: {current_exp} | Spot: ₹{underlying:,.2f}"

        if underlying == 0 or not strikes:
            return

        closest = min(strikes, key=lambda x: abs(x - underlying))
        idx     = strikes.index(closest)
        lo      = max(0, idx - ATM_WING)
        hi      = min(len(strikes), idx + ATM_WING + 1)
        display = strikes[lo:hi]

        for strike in display:
            ce_hist = self.store.get_history(strike, 'CE')
            pe_hist = self.store.get_history(strike, 'PE')

            ce_trend = SpurtCalculator.classify_spurt(ce_hist)
            pe_trend = SpurtCalculator.classify_spurt(pe_hist)

            ce = ce_hist[-1] if ce_hist else {'price': 0.0, 'oi': 0, 'doi': 0}
            pe = pe_hist[-1] if pe_hist else {'price': 0.0, 'oi': 0, 'doi': 0}

            strike_cell = Text(
                f"{strike:,.0f}",
                style="bold yellow" if strike == closest else "white"
            )

            table.add_row(
                self._style_doi(ce.get('doi', 0)),
                f"{ce.get('oi', 0):,}",
                f"{ce.get('price', 0.0):.2f}",
                self._style_trend(ce_trend),
                strike_cell,
                self._style_trend(pe_trend),
                f"{pe.get('price', 0.0):.2f}",
                f"{pe.get('oi', 0):,}",
                self._style_doi(pe.get('doi', 0)),
            )

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
    app = TradingTerminal()
    app.run()