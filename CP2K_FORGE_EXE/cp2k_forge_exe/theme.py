from __future__ import annotations


LIGHT_QSS = """
QMainWindow {
    background-color: #E7ECF3;
}

QWidget {
    font-family: "Microsoft YaHei", "Segoe UI", "Consolas", sans-serif;
    font-size: 9pt;
    color: #213547;
}

QGroupBox {
    border: 1px solid #CAD5E3;
    border-radius: 7px;
    margin-top: 14px;
    padding: 16px 10px 10px 10px;
    background-color: #FFFFFF;
    font-weight: bold;
}

QGroupBox[collapsed="false"] {
    border: 1px solid #9FC6D4;
}

QGroupBox[collapsed="true"] {
    background-color: #F8FAFC;
    border: 1px solid #D6E0EA;
}

QGroupBox#PinnedInputGroup {
    border: 1px solid #7FB5C8;
    background-color: #FBFEFF;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 2px 11px;
    color: #FFFFFF;
    background-color: #176B87;
    border-radius: 5px;
    font-size: 10.5pt;
    font-weight: 700;
}

QGroupBox::indicator {
    width: 0px;
    height: 0px;
}

QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background-color: #FFFFFF;
    border: 1px solid #CAD5E3;
    border-radius: 5px;
    padding: 5px 8px;
    selection-background-color: #176B87;
    selection-color: #FFFFFF;
}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #176B87;
    background-color: #F8FBFE;
}

QLineEdit#StructureDropEdit {
    border: 1px dashed #5E9FB6;
    background-color: #F7FCFE;
    padding: 10px 12px;
    font-size: 10pt;
}

QLineEdit#StructureDropEdit:focus {
    border: 1px dashed #176B87;
    background-color: #FFFFFF;
}

QComboBox {
    padding-right: 24px;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 24px;
    border: none;
    background: transparent;
}

QComboBox::down-arrow {
    image: none;
    width: 0px;
    height: 0px;
    border: none;
}

QComboBox::down-arrow:on {
    top: 0px;
    left: 0px;
}

QComboBox:disabled, QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QPlainTextEdit:disabled, QListWidget:disabled {
    background-color: #F1F5F9;
    border-color: #DDE5EF;
    color: #94A3B8;
}

QSpinBox, QDoubleSpinBox {
    padding-right: 24px;
}

QSpinBox::up-button, QDoubleSpinBox::up-button {
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 22px;
    border-left: 1px solid #D6E0EA;
    border-top-right-radius: 5px;
    background-color: #F8FAFC;
}

QSpinBox::down-button, QDoubleSpinBox::down-button {
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 22px;
    border-left: 1px solid #D6E0EA;
    border-bottom-right-radius: 5px;
    background-color: #F8FAFC;
}

QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
    background-color: #E6F2F6;
    border-left: 1px solid #9FC6D4;
}

QSpinBox::up-button:pressed, QDoubleSpinBox::up-button:pressed,
QSpinBox::down-button:pressed, QDoubleSpinBox::down-button:pressed {
    background-color: #D7EAF1;
    border-left: 1px solid #6DAFC5;
}

QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
    image: none;
    width: 0px;
    height: 0px;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-bottom: 5px solid #64748B;
}

QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
    image: none;
    width: 0px;
    height: 0px;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #64748B;
}

QSpinBox::up-arrow:hover, QDoubleSpinBox::up-arrow:hover,
QSpinBox::down-arrow:hover, QDoubleSpinBox::down-arrow:hover {
    border-bottom-color: #176B87;
    border-top-color: #176B87;
}

QSpinBox::up-arrow:pressed, QDoubleSpinBox::up-arrow:pressed,
QSpinBox::down-arrow:pressed, QDoubleSpinBox::down-arrow:pressed {
    top: 1px;
}

QSpinBox::up-button:disabled, QDoubleSpinBox::up-button:disabled,
QSpinBox::down-button:disabled, QDoubleSpinBox::down-button:disabled {
    background-color: #EEF2F7;
    border-left: 1px solid #DDE5EF;
}

QLabel:disabled, QCheckBox:disabled {
    color: #94A3B8;
}

QPushButton {
    background-color: #F7FAFC;
    border: 1px solid #CAD5E3;
    border-radius: 5px;
    padding: 6px 10px;
    color: #213547;
    font-weight: bold;
}

QPushButton:hover {
    background-color: #E6F2F6;
    border: 1px solid #176B87;
    color: #176B87;
}

QPushButton:disabled {
    background-color: #F1F5F9;
    border: 1px solid #E2E8F0;
    color: #94A3B8;
}

QPushButton#PrimaryBtn {
    background-color: #176B87;
    border: 1px solid #0F536A;
    color: #FFFFFF;
    padding: 8px 14px;
}

QPushButton#PrimaryBtn:hover {
    background-color: #1F7F9E;
    color: #FFFFFF;
}

QPushButton#SmallBtn {
    min-width: 24px;
    padding: 3px 5px;
}

QPushButton#VisualActionButton, QPushButton#ColorChooseButton {
    min-height: 22px;
    padding: 3px 8px;
    font-weight: 600;
}

QPushButton#ColorChooseButton {
    min-width: 58px;
}

QLabel#VisualFormLabel {
    color: #475569;
    font-weight: 600;
}

QLabel#VisualSubhead {
    color: #176B87;
    font-size: 9pt;
    font-weight: 700;
    padding: 3px 0px 1px 0px;
    border-bottom: 1px solid #E2E8F0;
}

QLabel#ColorSwatch {
    min-width: 28px;
    max-width: 28px;
    min-height: 24px;
    max-height: 24px;
}

QTextEdit, QPlainTextEdit, QListWidget {
    background-color: #F8FAFC;
    border: 1px solid #CAD5E3;
    border-radius: 6px;
    padding: 8px;
    font-family: "Consolas", "Courier New", monospace;
}

QScrollArea {
    border: none;
    background-color: transparent;
}

QTabWidget::pane {
    border: none;
    background-color: #FFFFFF;
}

QTabBar::tab {
    background-color: #F1F5F9;
    border: 1px solid #CAD5E3;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 8px 16px;
    margin-right: 3px;
    color: #53606E;
    font-weight: bold;
}

QTabBar::tab:selected {
    background-color: #FFFFFF;
    color: #176B87;
    border-bottom: 2px solid #176B87;
}

QLabel#StatusLabel {
    color: #176B87;
    font-weight: bold;
    padding: 5px 10px;
    background-color: #EEF7FA;
    border: 1px solid #CBE3EA;
    border-radius: 4px;
}

QLabel#ResultState {
    padding: 2px 4px;
}

QLabel#OutputLine {
    color: #334155;
    padding: 2px 4px;
}
"""
