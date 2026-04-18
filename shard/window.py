"""Frameless glassy main window."""
from __future__ import annotations

import html
from dataclasses import dataclass, field

from PySide6.QtCore import QPoint, QRect, QRectF, Qt, QTimer, Signal, Slot
from PySide6.QtGui import (
    QBrush,
    QColor,
    QKeyEvent,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .agent import AgentWorker
from .logo import ShardLogo
from .manager import WorkerManager
from .settings_dialog import SettingsDialog
from .styles import QSS
from .textures import shattered_glass_pixmap

RESIZE_MARGIN = 6

# Bit flags for edges (avoid PySide6's strict Qt.Edge enum which forbids |/&).
E_LEFT = 1
E_RIGHT = 2
E_TOP = 4
E_BOTTOM = 8


# ---- Chat bubble widgets ----------------------------------------------------
class _Bubble(QFrame):
    """A single chat bubble.

    ``role`` is one of ``user`` / ``assistant`` / ``system``. The object name
    drives QSS so user/assistant bubbles get distinct colors and corner radii.
    """

    def __init__(self, role: str, header: str, text: str,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.role = role
        self.turn: int = 0  # set by caller for correlation/merging
        self.setObjectName({
            "user": "UserBubble",
            "assistant": "AssistantBubble",
            "system": "SystemBubble",
        }[role])
        self.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Maximum)
        self.setMaximumWidth(420)
        self.setMinimumWidth(220)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 8, 14, 10)
        layout.setSpacing(2)

        if header:
            self._header = QLabel(header, self)
            self._header.setObjectName("BubbleHeader")
            layout.addWidget(self._header)

        self._body = QLabel(text, self)
        self._body.setObjectName("BubbleBody")
        self._body.setWordWrap(True)
        self._body.setTextInteractionFlags(Qt.TextSelectableByMouse)
        body_policy = self._body.sizePolicy()
        body_policy.setHorizontalPolicy(QSizePolicy.MinimumExpanding)
        body_policy.setHeightForWidth(True)
        self._body.setSizePolicy(body_policy)
        layout.addWidget(self._body)

        # Soft drop shadow for depth.
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 4)
        if role == "user":
            shadow.setColor(QColor(40, 80, 180, 140))
        elif role == "assistant":
            shadow.setColor(QColor(90, 50, 180, 150))
        else:
            shadow.setColor(QColor(0, 0, 0, 80))
        self.setGraphicsEffect(shadow)

    def set_body(self, text: str) -> None:
        self._body.setText(text)

    def append_paragraph(self, text: str) -> None:
        current = self._body.text()
        sep = "\n\n───\n\n"
        self._body.setText(current + sep + text)


class BubblePane(QScrollArea):
    """Scrollable list of per-turn rows pairing question with its answers."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setObjectName("BubblePane")

        self._inner = QWidget(self)
        self._inner.setObjectName("BubbleInner")
        self._layout = QVBoxLayout(self._inner)
        self._layout.setContentsMargins(14, 12, 14, 12)
        self._layout.setSpacing(14)
        self._layout.addStretch(1)
        self.setWidget(self._inner)

        # turn id -> (row_widget, left_vbox, right_vbox)
        self._rows: dict[int, tuple[QWidget, QVBoxLayout, QVBoxLayout]] = {}
        self._last_bubble: "_Bubble | None" = None

    def _ensure_row(self, turn: int) -> tuple[QVBoxLayout, QVBoxLayout]:
        if turn in self._rows:
            _, left, right = self._rows[turn]
            return left, right
        row_widget = QWidget(self._inner)
        row_widget.setObjectName("TurnRow")
        row = QHBoxLayout(row_widget)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(18)
        left = QVBoxLayout()
        left.setSpacing(8)
        left.setContentsMargins(0, 0, 0, 0)
        right = QVBoxLayout()
        right.setSpacing(8)
        right.setContentsMargins(0, 0, 0, 0)
        # Left column flush-left, right column flush-right; the stretch goes
        # in the middle so columns hug their respective edges and stay
        # vertically aligned with each other.
        left_wrap = QVBoxLayout()
        left_wrap.addLayout(left)
        left_wrap.addStretch(1)
        right_wrap = QVBoxLayout()
        right_wrap.addLayout(right)
        right_wrap.addStretch(1)
        row.addLayout(left_wrap, 1)
        row.addLayout(right_wrap, 1)
        idx = self._layout.count() - 1  # before trailing stretch
        self._layout.insertWidget(idx, row_widget)
        self._rows[turn] = (row_widget, left, right)
        return left, right

    def add_bubble(self, bubble: _Bubble) -> None:
        turn = getattr(bubble, "turn", 0)
        left, right = self._ensure_row(turn)
        if bubble.role == "user":
            right.addWidget(bubble, 0, Qt.AlignRight)
        elif bubble.role == "assistant":
            left.addWidget(bubble, 0, Qt.AlignLeft)
        else:
            # system messages span the row, centered
            left.addWidget(bubble, 0, Qt.AlignHCenter)
        self._last_bubble = bubble
        QTimer.singleShot(0, self._scroll_to_end)

    def last_bubble(self) -> "_Bubble | None":
        return self._last_bubble

    def _scroll_to_end(self) -> None:
        sb = self.verticalScrollBar()
        sb.setValue(sb.maximum())


@dataclass
class WorkerView:
    worker: AgentWorker
    pane: "BubblePane | None" = None
    item: QListWidgetItem | None = None
    pending_bubble: "_Bubble | None" = None
    assistant_buf: list[str] = field(default_factory=list)
    assistant_prefix: str = ""  # text already in pending_bubble before stream
    turn: int = 0  # latest user-prompt index (Q##)
    user_count: int = 0  # total user messages seen
    assistant_count: int = 0  # total assistant messages seen
    last_user_text: str = ""  # used to suppress echo bubbles
    suppress_current: bool = False  # current streaming assistant is an echo


class _PromptEdit(QPlainTextEdit):
    """Multiline input: Enter sends, Shift+Enter inserts newline."""

    submit = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setPlaceholderText("Enter text…  (Enter to queue, Shift+Enter for newline)")
        self.setFixedHeight(72)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def keyPressEvent(self, e: QKeyEvent) -> None:  # noqa: N802
        if e.key() in (Qt.Key_Return, Qt.Key_Enter) and not (e.modifiers() & Qt.ShiftModifier):
            self.submit.emit()
            return
        super().keyPressEvent(e)


class ShardWindow(QWidget):
    def __init__(self, manager: WorkerManager, api_url: str = "") -> None:
        super().__init__()
        self.setObjectName("GlassRoot")
        self.setWindowTitle("Shard")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMouseTracking(True)
        self.resize(1100, 720)
        self.setMinimumSize(640, 420)
        self.setStyleSheet(QSS)

        self._drag_pos: QPoint | None = None
        self._resize_edges: int = 0
        self._resize_start_geom: QRect | None = None
        self._resize_start_global: QPoint | None = None

        self._manager = manager
        self._views: dict[str, WorkerView] = {}
        self._active_name: str | None = None
        self._api_url = api_url

        self._build_ui()

        # React to workers added by the manager (UI-thread or API-thread).
        self._manager.worker_added.connect(self._on_worker_added)
        self._manager.worker_removed.connect(self._on_worker_removed)

        # Spawn the initial root worker via the manager.
        self._manager.create(prefix="root")

    # ---- UI construction -----------------------------------------------------
    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)

        self.frame = QFrame(self)
        self.frame.setObjectName("GlassFrame")
        self.frame.setMouseTracking(True)
        outer.addWidget(self.frame)

        layout = QVBoxLayout(self.frame)
        layout.setContentsMargins(14, 10, 14, 14)
        layout.setSpacing(10)

        layout.addLayout(self._build_titlebar())

        body = QSplitter(Qt.Horizontal, self.frame)
        body.setHandleWidth(8)
        body.setChildrenCollapsible(False)
        layout.addWidget(body, 1)

        # Left: transcript + input
        left = QWidget(body)
        left_l = QVBoxLayout(left)
        left_l.setContentsMargins(0, 0, 0, 0)
        left_l.setSpacing(8)

        self.transcript = QStackedWidget(left)
        self.transcript.setObjectName("Transcript")
        self._empty_pane = QWidget(self.transcript)
        self.transcript.addWidget(self._empty_pane)
        left_l.addWidget(self.transcript, 1)

        self.input = _PromptEdit(left)
        self.input.submit.connect(self._on_submit)
        left_l.addWidget(self.input)

        row = QHBoxLayout()
        self.send_btn = QPushButton("Queue", left)
        self.send_btn.clicked.connect(self._on_submit)
        self.fork_btn = QPushButton("Fork →  child subprocessor", left)
        self.fork_btn.clicked.connect(self._on_fork)
        self.pause_btn = QPushButton("⏸ Pause API", left)
        self.pause_btn.setCheckable(True)
        self.pause_btn.clicked.connect(self._on_toggle_pause)
        self.interrupt_btn = QPushButton("Interrupt selected", left)
        self.interrupt_btn.setObjectName("DangerBtn")
        self.interrupt_btn.clicked.connect(self._on_interrupt)
        self.delete_btn = QPushButton("Delete selected", left)
        self.delete_btn.setObjectName("DangerBtn")
        self.delete_btn.clicked.connect(self._on_delete)
        row.addWidget(self.send_btn)
        row.addStretch(1)
        row.addWidget(self.pause_btn)
        row.addWidget(self.fork_btn)
        row.addWidget(self.interrupt_btn)
        row.addWidget(self.delete_btn)
        left_l.addLayout(row)

        body.addWidget(left)

        # Right: subprocessors panel
        right = QWidget(body)
        right_l = QVBoxLayout(right)
        right_l.setContentsMargins(0, 0, 0, 0)
        right_l.setSpacing(6)
        cap = QLabel("SUBPROCESSORS", right)
        cap.setObjectName("SubtleLabel")
        right_l.addWidget(cap)
        self.workers_list = QListWidget(right)
        self.workers_list.itemSelectionChanged.connect(self._on_select_worker)
        right_l.addWidget(self.workers_list, 1)

        api_label = QLabel(
            f"API: <code>{html.escape(self._api_url) or '(not running)'}</code><br>"
            "POST <code>/workers/&lt;name&gt;/prompt</code> to queue text,<br>"
            "POST <code>/workers/&lt;name&gt;/fork</code> to duplicate,<br>"
            "POST <code>/workers/&lt;name&gt;/interrupt</code> to cancel.",
            right,
        )
        api_label.setObjectName("SubtleLabel")
        api_label.setWordWrap(True)
        api_label.setTextFormat(Qt.RichText)
        right_l.addWidget(api_label)

        body.addWidget(right)
        body.setStretchFactor(0, 3)
        body.setStretchFactor(1, 1)
        body.setSizes([760, 280])

        # Floating "+" FAB — duplicates the active worker.
        self.fab = QPushButton("+", self)
        self.fab.setObjectName("FabBtn")
        self.fab.setToolTip("Duplicate this instance (fork active worker)")
        self.fab.setCursor(Qt.PointingHandCursor)
        self.fab.setFixedSize(52, 52)
        self.fab.clicked.connect(self._on_fork)
        self.fab.raise_()

    def _build_titlebar(self) -> QHBoxLayout:
        bar = QHBoxLayout()
        bar.setSpacing(10)

        self.logo = ShardLogo(self.frame, size=30)
        bar.addWidget(self.logo)

        title = QLabel("SHARD", self.frame)
        title.setObjectName("TitleLabel")
        bar.addWidget(title)

        self.subtitle = QLabel("· glassy text-queue console", self.frame)
        self.subtitle.setObjectName("SubtleLabel")
        bar.addWidget(self.subtitle)

        bar.addStretch(1)

        self.status_label = QLabel("", self.frame)
        self.status_label.setObjectName("SubtleLabel")
        bar.addWidget(self.status_label)

        bar.addSpacing(8)

        self.settings_btn = QPushButton("⚙", self.frame)
        self.settings_btn.setObjectName("WinBtn")
        self.settings_btn.setToolTip("API host / port / token")
        self.settings_btn.clicked.connect(self._open_settings)
        bar.addWidget(self.settings_btn)

        self.min_btn = QPushButton("–", self.frame)
        self.min_btn.setObjectName("WinBtn")
        self.min_btn.clicked.connect(self.showMinimized)
        bar.addWidget(self.min_btn)

        self.max_btn = QPushButton("☐", self.frame)
        self.max_btn.setObjectName("WinBtn")
        self.max_btn.clicked.connect(self._toggle_max)
        bar.addWidget(self.max_btn)

        self.close_btn = QPushButton("✕", self.frame)
        self.close_btn.setObjectName("CloseBtn")
        self.close_btn.clicked.connect(self.close)
        bar.addWidget(self.close_btn)

        return bar

    def _toggle_max(self) -> None:
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self, manager=self._manager)
        dlg.exec()

    # ---- worker registration -------------------------------------------------
    @Slot(str)
    def _on_worker_added(self, name: str) -> None:
        worker = self._manager.get(name)
        if worker is None or name in self._views:
            return
        pane = BubblePane(self.transcript)
        self.transcript.addWidget(pane)
        view = WorkerView(worker=worker, pane=pane)
        item = QListWidgetItem(name)
        item.setData(Qt.UserRole, name)
        view.item = item
        self.workers_list.addItem(item)
        self._views[name] = view
        worker.message_started.connect(self._on_message_started)
        worker.message_delta.connect(self._on_message_delta)
        worker.message_finished.connect(self._on_message_finished)
        worker.state_changed.connect(self._on_state_changed)
        worker.api_enabled_changed.connect(self._on_api_enabled_changed)
        worker.error.connect(self._on_error)
        self._refresh_item(name)
        if self._active_name is None:
            self._set_active(name)

    def _set_active(self, name: str) -> None:
        if name not in self._views:
            return
        self._active_name = name
        view = self._views[name]
        for i in range(self.workers_list.count()):
            it = self.workers_list.item(i)
            if it.data(Qt.UserRole) == name:
                self.workers_list.setCurrentItem(it)
                break
        if view.pane is not None:
            self.transcript.setCurrentWidget(view.pane)
        self.subtitle.setText(f"· active: {name}")
        self._sync_pause_button()

    def _refresh_item(self, name: str) -> None:
        view = self._views.get(name)
        if not view or not view.item:
            return
        w = view.worker
        status = "● busy" if w.is_busy() else "○ idle"
        api = "api:on" if w.api_enabled() else "api:OFF"
        view.item.setText(f"{w.name}\n  {status}   queue: {w.queue_size()}   {api}")

    # ---- UI actions ----------------------------------------------------------
    def _on_submit(self) -> None:
        text = self.input.toPlainText().strip()
        if not text or not self._active_name:
            return
        self.input.clear()
        self._manager.enqueue(self._active_name, text)

    def _on_fork(self) -> None:
        if not self._active_name:
            return
        parent_name = self._active_name
        parent_history = list(self._views[parent_name].worker.history)
        child_name = self._manager.fork(parent_name)
        if not child_name:
            return

        def _seed_when_added(added_name: str) -> None:
            if added_name != child_name:
                return
            view = self._views.get(added_name)
            if view is not None and view.pane is not None:
                # Re-render the inherited history into bubbles.
                last_user = ""
                for entry in parent_history:
                    role = entry.get("role", "")
                    text = entry.get("content", "")
                    if role == "user":
                        view.user_count += 1
                        view.turn = view.user_count
                        last_user = text
                        b = _Bubble("user", f"YOU  ·  Q{view.turn:02d}", text)
                        b.turn = view.turn
                        view.pane.add_bubble(b)
                    elif role == "assistant":
                        view.assistant_count += 1
                        # Skip echo bubbles (assistant text == prior user).
                        if text == last_user:
                            last_user = ""  # only the immediate echo counts
                            continue
                        # Round-robin assistants across the existing
                        # questions so authored replies posted after the
                        # last prompt distribute back to Q01, Q02, …
                        if view.user_count > 0:
                            turn = ((view.assistant_count - 1)
                                    % view.user_count) + 1
                        else:
                            turn = 0
                        tag = f"A{turn:02d}" if turn else "•"
                        b = _Bubble(
                            "assistant",
                            f"SHARD  ·  {tag}  ·  {parent_name}", text)
                        b.turn = turn
                        view.pane.add_bubble(b)
                view.pane.add_bubble(_Bubble(
                    "system", "", f"forked from {parent_name}"))
            self._manager.worker_added.disconnect(_seed_when_added)
            self._set_active(child_name)

        self._manager.worker_added.connect(_seed_when_added)

    def _on_interrupt(self) -> None:
        item = self.workers_list.currentItem()
        if not item:
            return
        name = item.data(Qt.UserRole)
        if not self._manager.interrupt(name):
            return
        view = self._views.get(name)
        if view and view.pane is not None:
            b = _Bubble("system", "", "interrupted")
            b.setProperty("danger", True)
            b.turn = view.turn
            view.pane.add_bubble(b)

    def _on_delete(self) -> None:
        item = self.workers_list.currentItem()
        if not item:
            return
        name = item.data(Qt.UserRole)
        if not name:
            return
        reply = QMessageBox.question(
            self,
            "Delete subprocessor",
            f"Delete worker {name!r}?\nIts persisted history will be removed.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        self._manager.remove(name)

    @Slot(str)
    def _on_worker_removed(self, name: str) -> None:
        view = self._views.pop(name, None)
        if view is None:
            return
        # Remove list item.
        for i in range(self.workers_list.count()):
            it = self.workers_list.item(i)
            if it and it.data(Qt.UserRole) == name:
                self.workers_list.takeItem(i)
                break
        # Remove transcript pane.
        if view.pane is not None:
            self.transcript.removeWidget(view.pane)
            view.pane.deleteLater()
        # Reassign active worker if needed.
        if self._active_name == name:
            self._active_name = None
            remaining = self._manager.names()
            if remaining:
                self._set_active(remaining[0])
            else:
                self.subtitle.setText("")
        # If we just removed the last worker, spin up a fresh root.
        if not self._manager.names():
            self._manager.create(prefix="root")

    def _on_select_worker(self) -> None:
        item = self.workers_list.currentItem()
        if not item:
            return
        name = item.data(Qt.UserRole)
        if name and name != self._active_name:
            self._set_active(name)

    # ---- worker signal handlers ---------------------------------------------
    def _on_message_started(self, name: str, role: str, text: str) -> None:
        view = self._views.get(name)
        if not view or view.pane is None:
            return
        if role == "user":
            view.user_count += 1
            view.turn = view.user_count
            view.last_user_text = text
            b = _Bubble("user", f"YOU  ·  Q{view.turn:02d}", text)
            b.turn = view.turn
            view.pane.add_bubble(b)
        elif role == "assistant":
            view.assistant_count += 1
            view.assistant_buf = []
            view.assistant_prefix = ""
            # Suppress this stream entirely if it's the echo of the last user
            # prompt. Echoes only follow their own prompt immediately, so we
            # consume the flag after one assistant.
            if view.last_user_text:
                view.suppress_current = True
                view.last_user_text = ""
                view.pending_bubble = None
                return
            view.suppress_current = False
            if view.user_count > 0:
                turn = ((view.assistant_count - 1) % view.user_count) + 1
            else:
                turn = 0
            tag = f"A{turn:02d}" if turn else "•"
            bubble = _Bubble(
                "assistant", f"SHARD  ·  {tag}  ·  {name}", "▍")
            bubble.turn = turn
            view.pending_bubble = bubble
            view.pane.add_bubble(bubble)

    def _on_message_delta(self, name: str, delta: str) -> None:
        view = self._views.get(name)
        if not view or view.pending_bubble is None:
            return
        view.assistant_buf.append(delta)
        view.pending_bubble.set_body(
            view.assistant_prefix + "".join(view.assistant_buf) + " ▍")
        if view.pane is not None and name == self._active_name:
            view.pane._scroll_to_end()

    def _on_message_finished(self, name: str) -> None:
        view = self._views.get(name)
        if not view:
            return
        view.suppress_current = False
        if view.pending_bubble is not None:
            view.pending_bubble.set_body(
                view.assistant_prefix + "".join(view.assistant_buf))
            view.pending_bubble = None
            view.assistant_buf = []
            view.assistant_prefix = ""

    def _on_state_changed(self, name: str, _q: int, _busy: bool) -> None:
        self._refresh_item(name)
        if name == self._active_name:
            self._sync_pause_button()

    def _on_api_enabled_changed(self, name: str, _enabled: bool) -> None:
        self._refresh_item(name)
        if name == self._active_name:
            self._sync_pause_button()

    def _on_toggle_pause(self) -> None:
        if not self._active_name:
            return
        worker = self._manager.get(self._active_name)
        if worker is None:
            return
        worker.set_api_enabled(not worker.api_enabled())

    def _sync_pause_button(self) -> None:
        if not self._active_name:
            self.pause_btn.setEnabled(False)
            return
        worker = self._manager.get(self._active_name)
        if worker is None:
            self.pause_btn.setEnabled(False)
            return
        self.pause_btn.setEnabled(True)
        enabled = worker.api_enabled()
        self.pause_btn.blockSignals(True)
        self.pause_btn.setChecked(not enabled)
        self.pause_btn.setText("▶ Resume API" if not enabled else "⏸ Pause API")
        self.pause_btn.blockSignals(False)

    def _on_error(self, name: str, message: str) -> None:
        view = self._views.get(name)
        if not view or view.pane is None:
            return
        b = _Bubble("system", "", f"error: {message}")
        b.setProperty("danger", True)
        b.turn = view.turn
        view.pane.add_bubble(b)

    # ---- frameless background paint -----------------------------------------
    def paintEvent(self, _e) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        rect = self.frame.geometry()
        rectf = QRectF(rect)

        # 1) Soft outer drop-shadow halo (multi-pass for depth).
        for i in range(14, 0, -1):
            path = QPainterPath()
            r = rectf.adjusted(-i, -i + 2, i, i + 4)
            path.addRoundedRect(r, 16 + i, 16 + i)
            p.fillPath(path, QColor(10, 14, 30, max(2, 22 - i)))

        # 2) Subtle blue rim glow.
        for i in range(6, 0, -1):
            path = QPainterPath()
            r = rectf.adjusted(-i, -i, i, i)
            path.addRoundedRect(r, 16 + i, 16 + i)
            p.fillPath(path, QColor(140, 190, 255, max(2, 14 - i)))

        # 3) Clipped region for the glass body itself.
        body_path = QPainterPath()
        body_path.addRoundedRect(rectf, 16, 16)
        p.save()
        p.setClipPath(body_path)

        # 3a) Diagonal specular sheen across the whole pane.
        sheen = QLinearGradient(rectf.topLeft(), rectf.bottomRight())
        sheen.setColorAt(0.0, QColor(255, 255, 255, 28))
        sheen.setColorAt(0.45, QColor(255, 255, 255, 6))
        sheen.setColorAt(0.55, QColor(0, 0, 0, 30))
        sheen.setColorAt(1.0, QColor(0, 0, 0, 70))
        p.fillRect(rectf, sheen)

        # 3b) Soft cool radial glow at upper-left (light source).
        glow = QRadialGradient(
            rectf.topLeft() + QPoint(int(rectf.width() * 0.25),
                                     int(rectf.height() * 0.15)),
            max(rectf.width(), rectf.height()) * 0.85,
        )
        glow.setColorAt(0.0, QColor(150, 200, 255, 55))
        glow.setColorAt(1.0, QColor(150, 200, 255, 0))
        p.fillRect(rectf, QBrush(glow))

        # 3c) Shattered-glass texture overlay (procedural, cached).
        tex = shattered_glass_pixmap(int(rectf.width()), int(rectf.height()))
        p.setOpacity(0.55)
        p.drawPixmap(rect.topLeft(), tex)
        p.setOpacity(1.0)

        # 3d) Bottom-edge inner shadow for depth.
        bottom_shadow = QLinearGradient(rectf.bottomLeft(),
                                        rectf.bottomLeft() - QPoint(0, 60))
        bottom_shadow.setColorAt(0.0, QColor(0, 0, 0, 110))
        bottom_shadow.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.fillRect(rectf, bottom_shadow)

        p.restore()

        # 4) Crisp double-bevel border (bright outer + subtle inner highlight).
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(220, 235, 255, 180), 1.2))
        p.drawRoundedRect(rectf, 16, 16)
        inner = rectf.adjusted(1.5, 1.5, -1.5, -1.5)
        p.setPen(QPen(QColor(255, 255, 255, 55), 1.0))
        p.drawRoundedRect(inner, 14.5, 14.5)

        p.end()

    # ---- frameless drag + resize --------------------------------------------
    def _edges_at(self, pos: QPoint) -> int:
        m = RESIZE_MARGIN
        edges = 0
        if pos.x() <= m:
            edges |= E_LEFT
        if pos.x() >= self.width() - m:
            edges |= E_RIGHT
        if pos.y() <= m:
            edges |= E_TOP
        if pos.y() >= self.height() - m:
            edges |= E_BOTTOM
        return edges

    def _cursor_for(self, edges: int) -> Qt.CursorShape:
        if edges in (E_LEFT | E_TOP, E_RIGHT | E_BOTTOM):
            return Qt.SizeFDiagCursor
        if edges in (E_RIGHT | E_TOP, E_LEFT | E_BOTTOM):
            return Qt.SizeBDiagCursor
        if edges & (E_LEFT | E_RIGHT):
            return Qt.SizeHorCursor
        if edges & (E_TOP | E_BOTTOM):
            return Qt.SizeVerCursor
        return Qt.ArrowCursor

    def mousePressEvent(self, e) -> None:  # noqa: N802
        if e.button() != Qt.LeftButton:
            return
        edges = self._edges_at(e.position().toPoint())
        if edges:
            self._resize_edges = edges
            self._resize_start_geom = self.geometry()
            self._resize_start_global = e.globalPosition().toPoint()
        else:
            local = e.position().toPoint()
            if local.y() <= 56:
                self._drag_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e) -> None:  # noqa: N802
        if self._resize_edges:
            self._do_resize(e.globalPosition().toPoint())
            return
        if self._drag_pos is not None and (e.buttons() & Qt.LeftButton):
            if self.isMaximized():
                self.showNormal()
            self.move(e.globalPosition().toPoint() - self._drag_pos)
            return
        edges = self._edges_at(e.position().toPoint())
        self.setCursor(self._cursor_for(edges))

    def mouseReleaseEvent(self, _e) -> None:  # noqa: N802
        self._drag_pos = None
        self._resize_edges = 0
        self._resize_start_geom = None
        self._resize_start_global = None

    def _do_resize(self, gpos: QPoint) -> None:
        if not self._resize_start_geom or not self._resize_start_global:
            return
        delta = gpos - self._resize_start_global
        g = QRect(self._resize_start_geom)
        minw, minh = self.minimumWidth(), self.minimumHeight()
        if self._resize_edges & E_LEFT:
            g.setLeft(min(g.left() + delta.x(), g.right() - minw))
        if self._resize_edges & E_RIGHT:
            g.setRight(max(g.right() + delta.x(), g.left() + minw))
        if self._resize_edges & E_TOP:
            g.setTop(min(g.top() + delta.y(), g.bottom() - minh))
        if self._resize_edges & E_BOTTOM:
            g.setBottom(max(g.bottom() + delta.y(), g.top() + minh))
        self.setGeometry(g)

    def resizeEvent(self, e) -> None:  # noqa: N802
        super().resizeEvent(e)
        if hasattr(self, "fab"):
            margin = 24
            self.fab.move(self.width() - self.fab.width() - margin,
                          self.height() - self.fab.height() - margin)
            self.fab.raise_()

    def closeEvent(self, e) -> None:  # noqa: N802
        try:
            self._manager.shutdown_all()
        except Exception:
            pass
        super().closeEvent(e)
