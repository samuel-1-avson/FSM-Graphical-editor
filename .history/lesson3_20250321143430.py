import sys
from PyQt5.QtWidgets import (QApplication, QWidget, QMainWindow, QLabel, QPushButton,QVBoxLayout, QHBoxLayout, QGridLayout)
from PyQt5.QtGui import QPainter, QPen, QBrush, QColor, QPalette, QLinearGradient, QIcon, QPixmap, QCursor
from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("My cool first GUI")
        self.setWindowIcon(QIcon('ad2.png'))
        self.setGeometry(700, 300, 500, 500)
        
    def initUI(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        label1 = QLabel('#1', self)
        label2 = QLabel('#2', self)
        label3 = QLabel('#3', self)
        label4 = QLabel('#4', self)
        label5 = QLabel('#5', self)
        
        
        label1.setStyleSheet("background-color: red;")
        label2.setStyleSheet("background-color: green;")
        label3.setStyleSheet("background-color: blue;")
        label4.setStyleSheet("background-color: yellow;")
        label5.setStyleSheet("background-color: purple;")
        
        
        
                          
        
def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':    
    main()