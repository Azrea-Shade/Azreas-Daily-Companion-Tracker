from PyQt5.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QLineEdit, QPushButton, QLabel, QHBoxLayout

class ChatDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AI Chat (preview)")
        v = QVBoxLayout(self)

        self.banner = QLabel("This is a local demo. Cloud API not configured.")
        self.log = QTextEdit(); self.log.setReadOnly(True)

        row = QHBoxLayout()
        self.input = QLineEdit()
        send = QPushButton("Send")
        send.clicked.connect(self._send)
        row.addWidget(self.input); row.addWidget(send)

        v.addWidget(self.banner)
        v.addWidget(self.log)
        v.addLayout(row)

    def _send(self):
        t = (self.input.text() or "").strip()
        if not t:
            return
        self.log.append(f"You: {t}")
        if t.lower() in ("hi", "hello"):
            resp = "Hello! Ask about a company, ticker, or reminder."
        else:
            resp = "(demo) I’ll look that up when cloud access is enabled."
        self.log.append(f"AI: {resp}")
        self.input.clear()
