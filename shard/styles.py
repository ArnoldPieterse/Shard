"""Global QSS for the 3D glassy look."""

QSS = """
* {
    color: #e7f0ff;
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 13px;
}

QWidget#GlassRoot {
    background: transparent;
}

QFrame#GlassFrame {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0    rgba(40, 60, 110, 190),
        stop:0.55 rgba(20, 28, 52,  175),
        stop:1    rgba(12, 14, 28,  185));
    border: 1px solid rgba(180, 210, 255, 70);
    border-radius: 16px;
}

QLabel#TitleLabel {
    color: #eaf2ff;
    font-size: 14px;
    font-weight: 700;
    letter-spacing: 2px;
}

QLabel#SubtleLabel {
    color: rgba(220, 235, 255, 150);
    font-size: 11px;
}

/* ---- 3D glass buttons ---------------------------------------------------- */
QPushButton {
    color: #eaf2ff;
    padding: 6px 14px;
    border-radius: 9px;
    border: 1px solid rgba(180, 210, 255, 90);
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0   rgba(255, 255, 255, 38),
        stop:0.5 rgba(255, 255, 255, 18),
        stop:0.5 rgba(0,   0,   0,   25),
        stop:1   rgba(0,   0,   0,   60));
}
QPushButton:hover {
    border: 1px solid rgba(220, 235, 255, 160);
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0   rgba(255, 255, 255, 60),
        stop:0.5 rgba(255, 255, 255, 28),
        stop:0.5 rgba(80,  120, 200, 40),
        stop:1   rgba(0,   0,   0,   70));
}
QPushButton:pressed {
    padding-top: 7px; padding-bottom: 5px;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0   rgba(0,   0,   0,   80),
        stop:0.5 rgba(40,  60,  110, 80),
        stop:1   rgba(255, 255, 255, 30));
}
QPushButton:checked {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0   rgba(120, 170, 255, 80),
        stop:1   rgba(80,  60,  180, 80));
    border: 1px solid rgba(180, 220, 255, 200);
}

QPushButton#WinBtn {
    min-width: 26px; max-width: 26px;
    min-height: 22px; max-height: 22px;
    padding: 0;
    border-radius: 7px;
    border: 1px solid rgba(180, 210, 255, 60);
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0   rgba(255, 255, 255, 28),
        stop:0.5 rgba(255, 255, 255, 12),
        stop:0.5 rgba(0,   0,   0,   25),
        stop:1   rgba(0,   0,   0,   55));
}
QPushButton#WinBtn:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 rgba(255,255,255,50), stop:1 rgba(0,0,0,40));
}
QPushButton#CloseBtn {
    min-width: 26px; max-width: 26px;
    min-height: 22px; max-height: 22px;
    padding: 0;
    border-radius: 7px;
    border: 1px solid rgba(255, 160, 180, 110);
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0   rgba(255, 255, 255, 28),
        stop:0.5 rgba(255, 255, 255, 12),
        stop:0.5 rgba(0,   0,   0,   25),
        stop:1   rgba(0,   0,   0,   55));
}
QPushButton#CloseBtn:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 rgba(255, 140, 160, 220), stop:1 rgba(180, 30, 60, 220));
    border: 1px solid rgba(255, 200, 210, 220);
}

QPushButton#DangerBtn {
    color: #fff5f7;
    border: 1px solid rgba(255, 160, 180, 140);
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0   rgba(255, 130, 150, 90),
        stop:0.5 rgba(220, 70,  100, 110),
        stop:1   rgba(120, 20,  50,  170));
}
QPushButton#DangerBtn:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0   rgba(255, 170, 185, 140),
        stop:1   rgba(170, 30,  60,  210));
}

QPushButton#FabBtn {
    color: white;
    font-size: 28px;
    font-weight: 700;
    border: 1px solid rgba(255, 255, 255, 220);
    border-radius: 28px;
    padding: 0 0 4px 0;
    background: qradialgradient(cx:0.35, cy:0.30, radius:0.85,
        fx:0.35, fy:0.30,
        stop:0    rgba(255, 255, 255, 240),
        stop:0.35 rgba(170, 215, 255, 235),
        stop:0.75 rgba(120, 110, 240, 235),
        stop:1    rgba(60,  20,  120, 245));
}
QPushButton#FabBtn:hover {
    background: qradialgradient(cx:0.35, cy:0.30, radius:0.95,
        fx:0.35, fy:0.30,
        stop:0    rgba(255, 255, 255, 250),
        stop:0.40 rgba(200, 230, 255, 245),
        stop:0.80 rgba(150, 130, 255, 245),
        stop:1    rgba(80,  30,  150, 250));
}
QPushButton#FabBtn:pressed { padding-top: 2px; }

/* ---- inputs -------------------------------------------------------------- */
QTextEdit, QLineEdit, QPlainTextEdit {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0   rgba(8,  12, 26, 200),
        stop:1   rgba(20, 26, 46, 180));
    border: 1px solid rgba(140, 180, 240, 70);
    border-radius: 11px;
    padding: 8px;
    selection-background-color: rgba(120, 170, 255, 130);
}
QTextEdit:focus, QLineEdit:focus, QPlainTextEdit:focus {
    border: 1px solid rgba(180, 220, 255, 200);
}

QListWidget {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0   rgba(8,  12, 26, 180),
        stop:1   rgba(20, 26, 46, 160));
    border: 1px solid rgba(140, 180, 240, 70);
    border-radius: 11px;
    padding: 4px;
}
QListWidget::item {
    padding: 6px 8px;
    border-radius: 7px;
    margin: 2px;
}
QListWidget::item:selected {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 rgba(180, 220, 255, 90), stop:1 rgba(80, 60, 180, 90));
    border: 1px solid rgba(200, 230, 255, 140);
}

QScrollBar:vertical {
    background: transparent; width: 10px; margin: 4px;
}
QScrollBar::handle:vertical {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 rgba(180, 210, 255, 90), stop:1 rgba(120, 150, 230, 130));
    border-radius: 4px; min-height: 24px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }

QSplitter::handle { background: transparent; }

/* ---- chat bubbles -------------------------------------------------------- */
QStackedWidget#Transcript { background: transparent; border: none; }
QScrollArea#BubblePane,
QScrollArea#BubblePane > QWidget,
QWidget#BubbleInner { background: transparent; border: none; }

QFrame#UserBubble {
    border-radius: 18px;
    border-top-right-radius: 4px;
    border: 1px solid rgba(180, 220, 255, 180);
    color: #f1f7ff;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0   rgba(120, 180, 255, 235),
        stop:0.5 rgba(70,  130, 230, 235),
        stop:1   rgba(40,  80,  190, 240));
}
QFrame#AssistantBubble {
    border-radius: 18px;
    border-top-left-radius: 4px;
    border: 1px solid rgba(210, 190, 255, 170);
    color: #f5f0ff;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0   rgba(160, 120, 240, 230),
        stop:0.5 rgba(100, 70,  200, 235),
        stop:1   rgba(60,  30,  140, 240));
}
QFrame#SystemBubble {
    border-radius: 14px;
    border: 1px dashed rgba(200, 220, 255, 130);
    background: rgba(20, 30, 60, 140);
    color: rgba(220, 235, 255, 200);
}
QFrame#SystemBubble[danger="true"] {
    border: 1px dashed rgba(255, 170, 190, 200);
    background: rgba(80, 20, 40, 160);
    color: #ffd0d8;
}

QLabel#BubbleHeader {
    color: rgba(255, 255, 255, 200);
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 2px;
    background: transparent;
}
QLabel#BubbleBody {
    color: #f5faff;
    font-size: 13px;
    background: transparent;
}
"""
