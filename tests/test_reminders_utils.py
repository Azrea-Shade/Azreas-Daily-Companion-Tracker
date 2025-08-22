from PyQt5.QtWidgets import QApplication
from app import main as m

app = QApplication.instance() or QApplication([])

def test_add_reminder_and_refresh(tmp_path, monkeypatch):
    # Redirect data file to temp
    m.DATA_FILE = tmp_path / "data.json"
    data = m.load_data()
    w = m.MainWindow()
    # simulate adding reminder via data layer
    data.setdefault("reminders", []).append({"title":"Morning scan","hour":8,"minute":0,"days":[0,1,2,3,4],"enabled":True})
    m.save_data(data)
    w.data = m.load_data()
    w._refresh_reminders()
    assert w.rem_tbl.rowCount() >= 1
