"""Application entry point."""
from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication


def _try_enable_acrylic(win) -> None:
    """Best-effort: enable Windows 11 acrylic blur behind the window."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        from ctypes import wintypes

        hwnd = int(win.winId())
        DWMWA_SYSTEMBACKDROP_TYPE = 38
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        backdrop = ctypes.c_int(3)  # 3 = Acrylic
        dark = ctypes.c_int(1)
        dwm = ctypes.windll.dwmapi
        dwm.DwmSetWindowAttribute(
            wintypes.HWND(hwnd),
            DWMWA_SYSTEMBACKDROP_TYPE,
            ctypes.byref(backdrop),
            ctypes.sizeof(backdrop),
        )
        dwm.DwmSetWindowAttribute(
            wintypes.HWND(hwnd),
            DWMWA_USE_IMMERSIVE_DARK_MODE,
            ctypes.byref(dark),
            ctypes.sizeof(dark),
        )
    except Exception:
        pass


def main() -> int:
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Shard")
    app.setOrganizationName("Shard")

    from .config import load_settings
    settings = load_settings()

    from .api import ApiServer
    from .manager import WorkerManager
    from .window import ShardWindow

    manager = WorkerManager(save_dir=settings["SHARD_SAVE_DIR"])

    api: ApiServer | None = None
    try:
        api = ApiServer(manager=manager)
        api.start()
        api_url = api.url
        print(f"[shard] HTTP API listening on {api_url}")
    except OSError as exc:
        print(f"[shard] WARNING: HTTP API failed to start: {exc}", file=sys.stderr)
        api_url = ""

    win = ShardWindow(manager=manager, api_url=api_url)
    win.show()
    _try_enable_acrylic(win)

    try:
        rc = app.exec()
    finally:
        if api is not None:
            api.stop()
        manager.shutdown_all()
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
