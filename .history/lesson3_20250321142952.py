import sys
from PyQt5.QtWidgets import (QApplication, QWidget, QMainWindow, QLabel, QPushButton,QVBoxLayout, QHBoxLayout, QGridLayout)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("My cool first GUI")
        self.setWindowIcon(QIcon('ad2.png'))
        self.setGeometry(700, 300, 500, 500)
        
    def iniUI(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        
        
                          
        
def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':    
    main()