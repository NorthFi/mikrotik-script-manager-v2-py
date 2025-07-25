import os
import sys
from PyQt5.QtWidgets import QApplication
from ui.main_window import MikroTikScriptManager

if __name__ == "__main__":
    os.makedirs("data", exist_ok=True)
    
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = MikroTikScriptManager()
    window.show()
    sys.exit(app.exec_())