import sys

from PyQt6.QtWidgets import QApplication

from .timedot_widget import TimeDotsWidget

def run_app():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    w = TimeDotsWidget()
    w.show()
    return app.exec()

if __name__ == "__main__":
    sys.exit(run_app())
