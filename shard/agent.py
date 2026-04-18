"""Worker that tracks prompts/responses as plain text. No LLM, no outbound calls.

Each ``AgentWorker`` owns:
  * A FIFO queue of pending text prompts.
  * A persistent transcript (list of ``{role, content}`` dicts).
  * A background ``QThread`` that drains the queue and "responds" by echoing
    the text back, emitting Qt signals so the UI can stream it.

Workers are independent. A "child subprocessor" is just another ``AgentWorker``
seeded with a deep copy of its parent's transcript at fork time. Interrupting
one worker (cancelling the in-flight item and clearing its queue) does not
affect any other worker.

Everything is exposed over a small local HTTP API (see ``shard.api``) so that
external scripts can POST prompts, fork, interrupt, and read history.
"""
from __future__ import annotations

import copy
import queue
import threading
import time
import uuid
from dataclasses import dataclass

from PySide6.QtCore import QObject, QThread, Signal


@dataclass
class AgentConfig:
    # How fast to "stream" the echoed response, characters per second.
    stream_cps: int = 240
    # Optional prefix applied to every stored response.
    response_prefix: str = ""


class AgentWorker(QObject):
    """One text-tracking worker. Lives on its own QThread."""

    # name, role ("user"/"assistant"/"info"), text
    message_started = Signal(str, str, str)
    # name, delta_text
    message_delta = Signal(str, str)
    # name
    message_finished = Signal(str)
    # name, queue_size, busy
    state_changed = Signal(str, int, bool)
    # name, error_text
    error = Signal(str, str)
    # name, api_enabled
    api_enabled_changed = Signal(str, bool)
    # name  (history was mutated; subscribers may persist)
    history_changed = Signal(str)

    def __init__(
        self,
        name: str,
        config: AgentConfig | None = None,
        history: list[dict] | None = None,
    ) -> None:
        super().__init__()
        self.name = name
        self.config = config or AgentConfig()
        self.history: list[dict] = history if history is not None else []
        self._queue: "queue.Queue[str | None]" = queue.Queue()
        self._cancel = threading.Event()
        self._stop = threading.Event()
        self._busy = False
        self._api_enabled = True
        self._thread = QThread()
        self.moveToThread(self._thread)
        self._thread.started.connect(self._run)

    # ---- public API (call from any thread) -----------------------------------
    def start(self) -> None:
        self._thread.start()

    def enqueue(self, prompt: str) -> None:
        self._queue.put(prompt)
        self._emit_state()

    def interrupt(self) -> None:
        """Cancel the in-flight item and drop all queued prompts."""
        self._cancel.set()
        try:
            while True:
                self._queue.get_nowait()
        except queue.Empty:
            pass
        self._emit_state()

    def shutdown(self) -> None:
        self._stop.set()
        self.interrupt()
        self._queue.put(None)
        self._thread.quit()
        self._thread.wait(2000)

    def snapshot_history(self) -> list[dict]:
        return copy.deepcopy(self.history)

    def queue_size(self) -> int:
        return self._queue.qsize()

    def is_busy(self) -> bool:
        return self._busy

    def api_enabled(self) -> bool:
        return self._api_enabled

    def set_api_enabled(self, enabled: bool) -> None:
        if self._api_enabled == enabled:
            return
        self._api_enabled = enabled
        self.api_enabled_changed.emit(self.name, enabled)
        self._emit_state()

    def post_assistant(self, text: str) -> None:
        """Inject an externally-authored assistant message into the history.

        Emits the same signals as a streamed reply so the UI shows it. Safe to
        call from any thread; ``list.append`` is atomic in CPython.
        """
        self.message_started.emit(self.name, "assistant", "")
        if text:
            self.message_delta.emit(self.name, text)
        self.history.append({"role": "assistant", "content": text})
        self.history_changed.emit(self.name)
        self.message_finished.emit(self.name)

    # ---- worker loop ---------------------------------------------------------
    def _emit_state(self) -> None:
        self.state_changed.emit(self.name, self._queue.qsize(), self._busy)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                prompt = self._queue.get(timeout=0.25)
            except queue.Empty:
                continue
            if prompt is None or self._stop.is_set():
                break
            self._cancel.clear()
            self._busy = True
            self._emit_state()
            try:
                self._handle_prompt(prompt)
            except Exception as exc:  # noqa: BLE001
                self.error.emit(self.name, f"{type(exc).__name__}: {exc}")
            finally:
                self._busy = False
                self._emit_state()

    def _handle_prompt(self, prompt: str) -> None:
        self.history.append({"role": "user", "content": prompt})
        self.history_changed.emit(self.name)
        self.message_started.emit(self.name, "user", prompt)

        response = f"{self.config.response_prefix}{prompt}"
        self.message_started.emit(self.name, "assistant", "")

        # "Stream" so the UI shows progressive output and interrupts are responsive.
        delay = 1.0 / max(1, self.config.stream_cps)
        emitted: list[str] = []
        for ch in response:
            if self._cancel.is_set():
                break
            self.message_delta.emit(self.name, ch)
            emitted.append(ch)
            if delay:
                time.sleep(delay)

        text = "".join(emitted)
        if self._cancel.is_set():
            text += "  [interrupted]"
        self.history.append({"role": "assistant", "content": text})
        self.history_changed.emit(self.name)
        self.message_finished.emit(self.name)


def new_worker_name(prefix: str = "agent") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:6]}"
