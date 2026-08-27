"""
header.py
------------------------------------------------
One-line bar below the Textual header showing:

  NIFTY: 24,188.65  |  PCR: 0.87  |  CE OI: 1,23,45,600  |  PE OI: 1,07,23,400  |  Updated: 15:27:00  |  ● Market Open or ● Market Closed
"""

from textual.widgets import Static
from textual.app import RenderResult
from rich.text import Text


class MarketHeader(Static):

    DEFAULT_CSS = """
    MarketHeader {
        height: 2;
        background: #161b22;
        color: #8b949e;
        padding: 0 2;
        border-bottom: solid #30363d;
    }
    """

    def __init__(self, symbol: str = "NIFTY", **kwargs):
        super().__init__(**kwargs)
        self.symbol        = symbol
        self._underlying   = 0.0
        self._pcr          = 0.0
        self._total_ce_oi  = 0
        self._total_pe_oi  = 0
        self._timestamp    = "--:--:--"
        self._market_open  = False

    def refresh_stats(self, store, market_open: bool) -> None:
        """Called by app.py after every fetch."""
        self._underlying  = store.current_underlying
        self._timestamp   = store.current_timestamp
        self._market_open = market_open

        total_ce = 0
        total_pe = 0
        for strike in store.get_all_strikes():
            ce_hist = store.get_history(strike, 'CE')
            pe_hist = store.get_history(strike, 'PE')
            if ce_hist:
                total_ce += ce_hist[-1].get('oi', 0)
            if pe_hist:
                total_pe += pe_hist[-1].get('oi', 0)

        self._total_ce_oi = total_ce
        self._total_pe_oi = total_pe
        self._pcr = round(total_pe / total_ce, 2) if total_ce > 0 else 0.0

        self.refresh()


    def refresh_market_status(self, market_open: bool) -> None:
        """
        Lightweight refresh — only updates the market open/closed badge.
        Used by BSE screen so NSE store data never bleeds into BSE header.
        """
        self._market_open = market_open
        self.refresh()

    def render(self) -> RenderResult:
        t = Text(overflow="ellipsis", no_wrap=True)

        # Symbol + spot
        t.append(f" {self.symbol}: ", style="bold white")
        t.append(f"₹{self._underlying:,.2f}", style="bold cyan")

        t.append("  │  ", style="#30363d")

        # PCR
        t.append("PCR: ", style="#8b949e")
        if self._pcr == 0.0:
            pcr_style = "#8b949e"
        elif self._pcr > 1.0:
            pcr_style = "bold red"
        elif self._pcr < 1.0:
            pcr_style = "bold green"
        else:
            pcr_style = "bold yellow"
        t.append(f"{self._pcr:.2f}", style=pcr_style)

        t.append("  │  ", style="#30363d")

        # CE OI
        t.append("CE OI: ", style="#8b949e")
        t.append(f"{self._total_ce_oi:,}", style="bold red")

        t.append("  │  ", style="#30363d")

        # PE OI
        t.append("PE OI: ", style="#8b949e")
        t.append(f"{self._total_pe_oi:,}", style="bold green")

        t.append("  │  ", style="#30363d")

        # NSE timestamp
        t.append("Updated: ", style="#8b949e")
        t.append(self._timestamp, style="white")

        t.append("  │  ", style="#30363d")

        # Market status badge
        if self._market_open:
            t.append("● Market Open", style="bold green")
        else:
            t.append("● Market Closed", style="bold red")

        return t