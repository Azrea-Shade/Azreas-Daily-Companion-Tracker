import sys
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QPushButton
from PyQt5.QtCore import Qt

class Companion(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Daily Companion")
        self.setGeometry(200, 160, 820, 520)
        self.setStyleSheet("background:#0b0f1a; color:#e8e8f0; font-family:Segoe UI; font-size:16px;")
        layout = QVBoxLayout(self)
        title = QLabel("🌌 Azrea’s Daily Companion Tracker")
        title.setStyleSheet("font-size:24px; color:#00e1ff; font-weight:600;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        subtitle = QLabel("Futuristic companion for research, quotes, and daily flow.")
        subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(subtitle)
        btn = QPushButton("Close")
        btn.setStyleSheet("background:#111a2a; border:1px solid #23314d; padding:10px 16px; border-radius:8px;")
        btn.clicked.connect(self.close)
        layout.addWidget(btn, alignment=Qt.AlignCenter)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = Companion()
    w.show()
    sys.exit(app.exec_())
