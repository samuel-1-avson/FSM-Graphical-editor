import sys
from PyQt5.QtWidgets import QApplication, QWidget, 

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowTitle('PyQt5 Lesson 1')
        self.setGeometry(100, 100, 300, 200)
        self.show()