"""
switcher.py — Symbol Switcher Modal
"""

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Input

OPTIONS_TARGETS = [
    "NIFTY", "BANKNIFTY", "RELIANCE", "HDFCBANK", "BHARTIARTL",
    "AXISBANK", "ICICIBANK", "SBIN", "TCS", "BAJFINANCE",
    "LT", "HINDUNILVR", "INFY", "SUNPHARMA", "ADANIPORTS",
    "MARUTI", "ADANIENT", "M&M", "TITAN", "ITC",
    "NTPC", "ULTRACEMCO", "ONGC", "JSWSTEEL", "HCLTECH",
    "BEL", "BAJAJ-AUTO", "NESTLEIND", "COALINDIA", "POWERGRID",
    "BAJAJFINSV", "ASIANPAINT", "TATASTEEL", "HINDALCO", "ETERNAL",
    "GRASIM", "SHRIRAMFIN", "EICHERMOT", "WIPRO", "INDIGO",
    "SBILIFE", "JIOFIN", "TECHM", "TRENT", "TMPV",
    "APOLLOHOSP", "HDFCLIFE", "CIPLA", "TATACONSUM", "DRREDDY",
    "MAXHEALTH", "KOTAKBANK",
]


class TerminalSwitcherModal(ModalScreen[str | None]):

    CSS = """
    TerminalSwitcherModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.75);
    }
    #switcher_box {
        width: 40;
        height: auto;
        max-height: 70vh;
        background: #161b22;
        border: solid #30363d;
        padding: 1 2;
    }
    #modal_header {
        height: 1;
        width: 1fr;
        margin-bottom: 1;
    }
    #switcher_title {
        color: #58a6ff;
        text-style: bold;
        width: 1fr;
        text-align: center;
    }
    #close_btn {
        width: 3;
        min-width: 3;
        height: 1;
        border: none;
        background: transparent;
        color: #8b949e;
        padding: 0;
        text-style: bold;
        dock: right;
    }
    #close_btn:hover {
        background: #da3633;
        color: #ffffff;
    }
    #search_input {
        margin-bottom: 1;
        background: #0d1117;
        border: solid #30363d;
    }
    #search_input:focus {
        border: solid #58a6ff;
    }
    #button_container {
        height: auto;
        max-height: 50vh;
        border-top: solid #30363d;
        padding-top: 1;
    }
    .switch-btn {
        width: 100%;
        margin-bottom: 1;
        background: #21262d;
        color: #c9d1d9;
        border: none;
    }
    .switch-btn:hover {
        background: #30363d;
        color: #ffffff;
    }
    .switch-btn.-active {
        background: #1f6feb;
        color: #ffffff;
    }
    """

    BINDINGS = [
        ("escape",  "cancel",       "Cancel"),
        ("t",       "cancel",       "Cancel"),
        ("ctrl+l",  "focus_search", "Search"),
    ]

    def __init__(self, current_terminal: str, **kwargs):
        super().__init__(**kwargs)
        self.current_symbol = current_terminal
        self.button_map = {}

    def compose(self) -> ComposeResult:
        with Vertical(id="switcher_box"):
            with Horizontal(id="modal_header"):
                yield Label("Select Symbol", id="switcher_title")
                yield Button("✕", id="close_btn")
            yield Input(placeholder="Press Ctrl+L to search...", id="search_input")
            with VerticalScroll(id="button_container"):
                for index, symbol in enumerate(OPTIONS_TARGETS):
                    safe_id = f"btn_ticker_{index}"
                    self.button_map[safe_id] = symbol
                    btn = Button(symbol, id=safe_id, classes="switch-btn")
                    if symbol == self.current_symbol:
                        btn.add_class("-active")
                    yield btn

    def on_input_changed(self, event: Input.Changed) -> None:
        search_term = event.value.upper()
        for btn in self.query(".switch-btn"):
            symbol = self.button_map.get(btn.id)
            if symbol:
                btn.display = not search_term or search_term in symbol

    def action_focus_search(self) -> None:
        self.query_one("#search_input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close_btn":
            self.dismiss(None)
            return
        if event.button.id in self.button_map:
            self.dismiss(self.button_map[event.button.id])

    def action_cancel(self) -> None:
        self.dismiss(None)