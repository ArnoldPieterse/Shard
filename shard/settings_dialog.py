"""Settings dialog: API host/port/token and save folder."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .config import KEYS, load_settings, save_settings
from .styles import QSS


class _FolderField(QWidget):
    def __init__(self, value: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self.edit = QLineEdit(value, self)
        self.btn = QPushButton("Browse…", self)
        self.btn.clicked.connect(self._browse)
        lay.addWidget(self.edit, 1)
        lay.addWidget(self.btn)

    def _browse(self) -> None:
        chosen = QFileDialog.getExistingDirectory(
            self, "Choose save folder", self.edit.text() or ""
        )
        if chosen:
            self.edit.setText(chosen)

    def text(self) -> str:
        return self.edit.text()


class SettingsDialog(QDialog):
    def __init__(self, parent=None, manager=None) -> None:
        super().__init__(parent)
        self._manager = manager
        self.setWindowTitle("Shard · Settings")
        self.setStyleSheet(QSS)
        self.setMinimumWidth(520)

        values = load_settings()
        self._fields: dict[str, object] = {}

        outer = QVBoxLayout(self)
        outer.addWidget(QLabel(
            "Shard exposes a local HTTP API. Restart for host/port changes to take effect.\n"
            "Save folder changes apply immediately."
        ))
        form = QFormLayout()
        form.setContentsMargins(8, 8, 8, 8)
        form.setSpacing(8)
        for key in KEYS:
            if key == "SHARD_SAVE_DIR":
                w = _FolderField(values.get(key, ""), self)
                self._fields[key] = w
                form.addRow(key, w)
                continue
            edit = QLineEdit(values.get(key, ""), self)
            if key == "SHARD_API_TOKEN":
                edit.setEchoMode(QLineEdit.Password)
                edit.setPlaceholderText("optional shared secret; empty = no auth")
            self._fields[key] = edit
            form.addRow(key, edit)
        outer.addLayout(form)

        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel, parent=self)
        btns.accepted.connect(self._accept)
        btns.rejected.connect(self.reject)
        outer.addWidget(btns)

    def _accept(self) -> None:
        values = {k: w.text().strip() for k, w in self._fields.items()}
        save_settings(values)
        if self._manager is not None and values.get("SHARD_SAVE_DIR"):
            self._manager.set_save_dir(values["SHARD_SAVE_DIR"])
        self.accept()
