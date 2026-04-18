"""Worker registry shared by the UI and the HTTP API.

Thread-safe orchestration layer. Worker creation/removal is marshalled to the
GUI thread via a Qt queued signal so that ``QThread`` objects are owned by the
main thread. Worker history is persisted to disk on every change.
"""
from __future__ import annotations

import json
import os
import re
import threading
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QObject, Qt, Signal, Slot

from .agent import AgentConfig, AgentWorker, new_worker_name

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_filename(name: str) -> str:
    return _SAFE_NAME.sub("_", name)[:80] or "worker"


class WorkerManager(QObject):
    """Owns the set of ``AgentWorker`` instances."""

    worker_added = Signal(str)            # name
    worker_removed = Signal(str)          # name
    save_dir_changed = Signal(str)        # new path

    # Internal: marshal a "create worker" call onto the main thread.
    _create_requested = Signal(str, object, object)  # name, history, callback

    def __init__(self, save_dir: str | os.PathLike[str], parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._workers: dict[str, AgentWorker] = {}
        self._lock = threading.RLock()
        self._save_dir = Path(save_dir)
        self._ensure_save_dir()
        self._create_requested.connect(self._create_on_main, Qt.QueuedConnection)

    # ---- save dir ------------------------------------------------------------
    def save_dir(self) -> Path:
        return self._save_dir

    def set_save_dir(self, path: str | os.PathLike[str]) -> None:
        new = Path(path)
        if new == self._save_dir:
            return
        self._save_dir = new
        self._ensure_save_dir()
        # Re-persist all workers into the new location.
        with self._lock:
            workers = list(self._workers.values())
        for w in workers:
            self._persist(w)
        self.save_dir_changed.emit(str(new))

    def _ensure_save_dir(self) -> None:
        try:
            self._save_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass

    def _path_for(self, name: str) -> Path:
        return self._save_dir / f"{_safe_filename(name)}.json"

    def _persist(self, w: AgentWorker) -> None:
        try:
            self._ensure_save_dir()
            data = {
                "name": w.name,
                "api_enabled": w.api_enabled(),
                "history": w.snapshot_history(),
            }
            tmp = self._path_for(w.name).with_suffix(".json.tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(tmp, self._path_for(w.name))
        except OSError:
            pass

    # ---- queries -------------------------------------------------------------
    def names(self) -> list[str]:
        with self._lock:
            return list(self._workers.keys())

    def get(self, name: str) -> AgentWorker | None:
        with self._lock:
            return self._workers.get(name)

    def snapshot(self) -> list[dict]:
        with self._lock:
            return [
                {
                    "name": w.name,
                    "busy": w.is_busy(),
                    "queue": w.queue_size(),
                    "history_len": len(w.history),
                    "api_enabled": w.api_enabled(),
                }
                for w in self._workers.values()
            ]

    # ---- mutations -----------------------------------------------------------
    def create(
        self,
        prefix: str = "agent",
        history: list[dict] | None = None,
        on_created: Callable[[AgentWorker], None] | None = None,
    ) -> str:
        name = new_worker_name(prefix)
        self._create_requested.emit(name, history, on_created)
        return name

    @Slot(str, object, object)
    def _create_on_main(
        self,
        name: str,
        history: list[dict] | None,
        on_created: Callable[[AgentWorker], None] | None,
    ) -> None:
        worker = AgentWorker(name=name, config=AgentConfig(), history=history)
        with self._lock:
            self._workers[name] = worker
        # Persist initial state and on every history mutation.
        worker.history_changed.connect(lambda _n, w=worker: self._persist(w))
        worker.api_enabled_changed.connect(lambda _n, _e, w=worker: self._persist(w))
        self._persist(worker)
        worker.start()
        self.worker_added.emit(name)
        if on_created is not None:
            on_created(worker)

    def fork(self, parent_name: str) -> str | None:
        with self._lock:
            parent = self._workers.get(parent_name)
            if parent is None:
                return None
            history = parent.snapshot_history()
        return self.create(prefix="child", history=history)

    def interrupt(self, name: str) -> bool:
        worker = self.get(name)
        if worker is None:
            return False
        worker.interrupt()
        return True

    def enqueue(self, name: str, text: str) -> bool:
        worker = self.get(name)
        if worker is None:
            return False
        worker.enqueue(text)
        return True

    def set_api_enabled(self, name: str, enabled: bool) -> bool:
        worker = self.get(name)
        if worker is None:
            return False
        worker.set_api_enabled(enabled)
        return True

    def remove(self, name: str) -> bool:
        with self._lock:
            worker = self._workers.pop(name, None)
        if worker is None:
            return False
        try:
            worker.shutdown()
        except Exception:
            pass
        try:
            self._path_for(name).unlink(missing_ok=True)
        except OSError:
            pass
        self.worker_removed.emit(name)
        return True

    def shutdown_all(self) -> None:
        with self._lock:
            workers = list(self._workers.values())
            self._workers.clear()
        for w in workers:
            try:
                self._persist(w)
            except Exception:
                pass
            try:
                w.shutdown()
            except Exception:
                pass
