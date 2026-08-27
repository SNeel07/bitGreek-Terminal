"""
oi_table.py — Options OI Table Widget
----------------------------------------

Symmetrical option chain layout with strike in the centre.
The trend cell now embeds a sparkline alongside the label:

    CE ΔOI | CE OI | CE LTP |  CE Trend  | STRIKE | PE Trend | PE LTP | PE OI | PE ΔOI
"""

from textual.widgets import DataTable
from textual.app import ComposeResult
from textual.widget import Widget


class OITable(Widget):
    """Encapsulates the Textual DataTable for displaying options OI data."""

    DEFAULT_CSS = """
    OITable {
        height: 1fr;
    }
    """

    def compose(self) -> ComposeResult:
        yield DataTable(id="spurt_table")

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.cursor_type  = "row"
        table.zebra_stripes = True

        # Symmetrical layout — strike in the centre
        table.add_columns(
            "CE ΔOI",
            "CE OI",
            "CE LTP",
            "CE Trend",
            "Strike",
            "PE Trend",        
            "PE LTP",
            "PE OI",
            "PE ΔOI",
        )