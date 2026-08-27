"""
sidebar.py — Quick Links Sidebar
-----------------------------------

A slide-in sidebar for storing and opening browser links.
Supports terminal-specific multi-tenant data isolation.
"""

import json
import webbrowser
from pathlib import Path
from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal, VerticalScroll, Container
from textual.screen import ModalScreen
from textual.message import Message
from textual.widgets import Button, Input, Label


# ---------------- Persistent storage ---------------------------------

LINKS_FILE = Path.home() / ".nse_terminal" / "links.json"


def _load_links() -> dict:
    try:
        LINKS_FILE.parent.mkdir(parents=True, exist_ok=True)
        if LINKS_FILE.exists():
            data = json.loads(LINKS_FILE.read_text(encoding="utf-8"))
            if isinstance(data, list):
                migrated_data = {"nse": data}
                _save_links(migrated_data)
                return migrated_data
            return data
    except Exception:
        pass
    return {}


def _save_links(links_dict: dict) -> None:
    try:
        LINKS_FILE.parent.mkdir(parents=True, exist_ok=True)
        LINKS_FILE.write_text(
            json.dumps(links_dict, indent=2), encoding="utf-8"
        )
    except Exception:
        pass


# --------------------- Add Link Modal -----------------------------
class AddLinkModal(ModalScreen[dict | None]):
    CSS = """
    AddLinkModal { align: center middle; background: rgba(0,0,0,0.75); }
    #add_modal_box {
        width: 52; 
        height: auto; 
        background: #161b22; 
        border: solid #30363d; 
        padding: 1 2; 
    }
    
    #close_btn {
        dock: right;
        width: 3; 
        min-width: 3; 
        height: 1; 
        border: none;
        background: transparent; 
        color: #8b949e; 
        padding: 0; 
        text-style: bold;
    }
    #close_btn:hover { background: #da3633; color: #ffffff; }

    #add_modal_header {
        height: 1;
        width: 1fr;
        margin-bottom: 1;
    }
    #add_modal_title {
        color: #58a6ff;
        text-style: bold;
        width: 1fr;
    }
    #add_modal_box Label { color: #58a6ff; text-style: bold; margin-bottom: 1; }
    #add_modal_box .field-label { color: #8b949e; margin-top: 1; margin-bottom: 0; }
    Input { background: #0d1117; border: solid #30363d; color: #e6edf3; margin-bottom: 1; }
    Input:focus { border: solid #58a6ff; }
    #add_btn_row { height: auto; margin-top: 1; align: right middle; }
    #add_btn_row Button { margin-left: 1; }
    #btn_confirm { background: #238636; color: #ffffff; border: solid #2ea043; }
    #btn_confirm:hover { background: #2ea043; }
    #btn_cancel_add { background: #21262d; color: #8b949e; border: solid #30363d; }
    #btn_cancel_add:hover { background: #30363d; color: #e6edf3; }
    """
    BINDINGS = [("escape", "cancel_add", "Cancel")]

    def compose(self) -> ComposeResult:
        with Vertical(id="add_modal_box"):
            with Horizontal(id="add_modal_header"):
                yield Label("Add New Link", id="add_modal_title")
                yield Button("✕", id="close_btn")
            yield Label("Name", classes="field-label")
            yield Input(placeholder="e.g. Zerodha Charts", id="inp_name")
            yield Label("URL", classes="field-label")
            yield Input(placeholder="e.g. https://kite.zerodha.com", id="inp_url")
            with Horizontal(id="add_btn_row"):
                yield Button("Cancel", id="btn_cancel_add")
                yield Button("Add Link", id="btn_confirm")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close_btn":
            self.dismiss(None)
            return

        if event.button.id == "btn_confirm":
            name = self.query_one("#inp_name", Input).value.strip()
            url  = self.query_one("#inp_url",  Input).value.strip()
            if name and url:
                if not url.startswith(("http://", "https://")):
                    url = "https://" + url
                self.dismiss({"name": name, "url": url})
            else:
                self.app.notify("Both name and URL are required.", severity="warning", timeout=3)
        elif event.button.id == "btn_cancel_add":
            self.dismiss(None)

    def action_cancel_add(self) -> None:
        self.dismiss(None)


# ------------------ Link Row ---------------------------------
class LinkRow(Container):
    CSS = """
    LinkRow { height: 5; min-height: 5; padding: 0 1; margin-bottom: 1; background: #0d1117; border: solid #21262d; border-radius: 4; }
    LinkRow:hover { border: solid #58a6ff; }
    .link-name { height: 1; min-height: 1; color: #e6edf3; text-style: bold; word-wrap: break-word; }
    .btn-row { height: 3; layout: horizontal; align: center middle; }
    .btn-open { width: 1fr; height: 3; margin-right: 1; background: #1f6feb; color: #ffffff; border: solid #388bfd; }
    .btn-open:hover { background: #388bfd; }
    .btn-delete { width: 5; height: 3; background: #21262d; color: #f85149; border: solid #30363d; }
    .btn-delete:hover { background: #f85149; color: #ffffff; }
    """
    def __init__(self, index: int, name: str, url: str, **kwargs):
        super().__init__(**kwargs)
        self.index = index
        self.link_name = name
        self.url = url

    def compose(self) -> ComposeResult:
        yield Label(self.link_name, classes="link-name")
        with Horizontal(classes="btn-row"):
            yield Button("Open ↗", classes="btn-open")
            yield Button("×", classes="btn-delete")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        if event.button.has_class("btn-open"):
            webbrowser.open(self.url)
            self.app.notify(f"Opening {self.link_name}...", severity="information", timeout=3)
        elif event.button.has_class("btn-delete"):
            self.post_message(LinkRow.DeleteRequested(self.index))

    class DeleteRequested(Message):
        def __init__(self, index: int):
            super().__init__()
            self.index = index


# --------------- Sidebar Screen -----------------------------
class LinkSidebar(ModalScreen):
    CSS = """
    LinkSidebar { align: right middle; background: rgba(0,0,0,0.5); }
    #sidebar_panel {
        width: 38; 
        height: 100%; 
        background: #161b22; 
        border-left: solid #30363d; 
        padding: 1; 
    }
    
    #close_btn {
        dock: right;
        width: 3; 
        min-width: 3; 
        height: 1; 
        border: none;
        background: transparent; 
        color: #8b949e; 
        padding: 0; 
        text-style: bold;
    }
    #close_btn:hover { background: #da3633; color: #ffffff; }

    #sidebar_header {
        height: 1;
        width: 1fr;
        margin-bottom: 1;
    }
    #sidebar_title { color: #58a6ff; text-style: bold; padding: 0 1; margin-bottom: 1; border-bottom: solid #30363d; height: 3; content-align: left middle; }
    #links_scroll { height: 1fr; padding-bottom: 1; scrollbar-gutter: stable; }
    #no_links_label { color: #8b949e; padding: 3 1; text-align: center; }
    #btn_add_link { dock: bottom; width: 1fr; margin-top: 1; background: #238636; color: #ffffff; border: solid #2ea043; }
    #btn_add_link:hover { background: #2ea043; }
    """

    BINDINGS = [
        ("escape", "close_sidebar", "Close"),
        ("s",      "close_sidebar", "Close"),
    ]

    def __init__(self, terminal_id: str, **kwargs):
        super().__init__(**kwargs)
        self.terminal_id = terminal_id
        self._all_links = _load_links()
        
        if self.terminal_id not in self._all_links:
            self._all_links[self.terminal_id] = []
            
        self._links = self._all_links[self.terminal_id]

    def _save_current_context(self) -> None:
        self._all_links[self.terminal_id] = self._links
        _save_links(self._all_links)

    def compose(self) -> ComposeResult:
        with Vertical(id="sidebar_panel"):
            with Horizontal(id="sidebar_header"):
                yield Label("", id="sidebar_title")
                yield Button("✕", id="close_btn")
            yield VerticalScroll(id="links_scroll")
            yield Button("＋  Add Link", id="btn_add_link")

    def on_mount(self) -> None:
        self._render_links()

    def _update_title(self) -> None:
        try:
            title_label = self.query_one("#sidebar_title", Label)
            title = f"  🔗 {self.terminal_id.upper()} Links ({len(self._links)}/10)"
            title_label.update(title)
        except Exception:
            pass

    def _render_links(self) -> None:
        scroll = self.query_one("#links_scroll", VerticalScroll)
        scroll.remove_children()
        self._update_title()

        if not self._links:
            scroll.mount(Label(f"No links for {self.terminal_id.upper()}.\nPress + to add one.", id="no_links_label"))
        else:
            for i, link in enumerate(self._links):
                scroll.mount(LinkRow(i, link["name"], link["url"]))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close_btn":
            self.dismiss()
            return

        if event.button.id == "btn_add_link":
            if len(self._links) >= 10:
                self.app.notify(
                    "Maximum limit reached! Please delete an existing link first.", 
                    severity="error", 
                    timeout=4
                )
            else:
                self.app.push_screen(AddLinkModal(), self._on_link_added)

    def on_link_row_delete_requested(self, event: LinkRow.DeleteRequested) -> None:
        self._links.pop(event.index)
        self._save_current_context()
        self._render_links()
        self.app.notify("Link removed.", severity="warning", timeout=2)

    def _on_link_added(self, result: dict | None) -> None:
        if result:
            self._links.append(result)
            self._save_current_context()
            self._render_links()
            self.app.notify(f"'{result['name']}' added.", severity="information", timeout=3)

    def action_close_sidebar(self) -> None:
        self.dismiss()