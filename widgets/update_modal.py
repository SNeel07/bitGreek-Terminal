import os
import urllib.request
import threading
from pathlib import Path
import time

from textual.screen import ModalScreen
from textual.containers import Vertical, Horizontal
from textual.widgets import Static, Button


class UpdateModal(ModalScreen):
    """
    Displays release notes and handles background download
    and execution of the new installer.
    """

    CSS = """
    UpdateModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.7);
    }
    #update_dialog {
        width: 60;
        height: auto;
        padding: 1 2;
        background: #161b22;
        border: solid #30363d;
    }
    #release_notes {
        height: auto;
        margin: 1 0;
        color: #c9d1d9;
    }
    #button_container {
        width: 100%;
        height: auto;
        align: center middle;
    }
    Button { margin: 0 1; }
    """

    def __init__(self, version: str, download_url: str, release_notes: str):
        super().__init__()
        self.version      = version
        self.download_url = download_url
        self.release_notes = release_notes

    def compose(self):
        with Vertical(id="update_dialog"):
            yield Static(
                f"[bold cyan]Update Available: {self.version}[/bold cyan]",
                id="update_title"
            )
            yield Static(self.release_notes, id="release_notes")
            with Horizontal(id="button_container"):
                yield Button("Install Update", variant="success", id="btn_install")
                yield Button("Skip",           variant="error",   id="btn_skip")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_skip":
            self.dismiss()
            if self.app.last_raw_data is not None:
                self.app.refresh_ui(True)

        elif event.button.id == "btn_install":
            self.install_update()

    def install_update(self):
        self.dismiss()

        if getattr(self.app, 'last_raw_data', None) is not None:
            self.app.refresh_ui(True)

        app_ref = self.app

        threading.Thread(
            target=self._download_and_run,
            args=(app_ref,),
            daemon=True
        ).start()

    def _download_and_run(self, app_ref):
        """
        Runs in a background thread.
        Uses app_ref (captured before dismiss) — never self.app.
        Updates #download_progress safely.
        """

        def set_progress(msg: str):
            try:
                
                box = app_ref.get_screen("options_display").query_one("#download_progress", Static)
                box.display = True
                box.update(msg)
            except Exception:
                pass

        def hide_progress():
            try:
                
                app_ref.get_screen("options_display").query_one("#download_progress", Static).display = False
            except Exception:
                pass

        def safe_update(func):
            try:
                if app_ref.is_running:
                    app_ref.call_from_thread(func)
            except RuntimeError:
                pass
        try:
            safe_update(lambda: set_progress("Connecting..."))

            update_dir    = Path.home() / ".nse_terminal" / "updates"
            update_dir.mkdir(parents=True, exist_ok=True)
            installer_path = update_dir / f"bitGreek_Setup_{self.version}.exe"

            req = urllib.request.Request(
                self.download_url,
                headers={'User-Agent': 'BitGreek-Terminal-App'}
            )

            with urllib.request.urlopen(req, timeout=60) as response, \
                 open(installer_path, 'wb') as out_file:

                total_length   = response.headers.get('content-length')
                downloaded     = 0
                chunk_size     = 64 * 1024
                last_ui_update = 0

                if total_length:
                    safe_update(lambda: set_progress("Downloading... 0%"))
                else:
                    safe_update(lambda: set_progress("Downloading... 0.0 MB"))

                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    downloaded += len(chunk)
                    out_file.write(chunk)

                    now = time.time()
                    if now - last_ui_update >= 0.5:
                        last_ui_update = now
                        if total_length:
                            pct = int(downloaded / int(total_length) * 100)
                            safe_update(lambda p=pct: set_progress(f"Downloading... {p}%"))
                        else:
                            mb = downloaded / (1024 * 1024)
                            safe_update(lambda m=mb: set_progress(f"Downloading... {m:.1f} MB"))

            safe_update(lambda: set_progress("Download complete! Launching installer..."))
            time.sleep(1)
            os.startfile(installer_path)
            safe_update(app_ref.exit)

        except Exception:
            def on_error():
                app_ref.notify(
                    "Update failed. Please check your connection and try again.",
                    severity="error",
                    timeout=5
                )
                hide_progress()

            safe_update(on_error)