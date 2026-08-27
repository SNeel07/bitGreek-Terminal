from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import OptionList, Label, Button
from textual.containers import Vertical, Horizontal

class ExpiryModal(ModalScreen[str]):

    BINDINGS = [("escape", "cancel", "Cancel")]

    CSS = """
    ExpiryModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.7);
    }
    #modal_container {
        width: 30;
        height: 20;
        background: #161b22;
        border: solid #30363d;
        padding: 1 2;
    }
    #modal_header {
        height: 1;
        width: 1fr;
        margin-bottom: 1;
    }
    #modal_title {
        color: #58a6ff;
        text-style: bold;
        width: 1fr;
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
    OptionList {
        height: 1fr;
        margin-top: 1;
        background: #0d1117;
    }
    """

    def __init__(self, expiries: list[str]):
        super().__init__()
        self.expiries = expiries

    def compose(self) -> ComposeResult:
        with Vertical(id="modal_container"):
            with Horizontal(id="modal_header"):
                yield Label("Select Expiry Date", id="modal_title")
                yield Button("✕", id="close_btn")
            yield OptionList(*self.expiries, id="expiry_list")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close_btn":
            self.dismiss(None)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(str(event.option.prompt))

    def action_cancel(self) -> None:
        self.dismiss(None)