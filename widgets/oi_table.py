"""
oi_table.py — Options OI Table Widget
----------------------------------------

Used for diplaying the headers on the table
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

        self.app.rebuild_columns()