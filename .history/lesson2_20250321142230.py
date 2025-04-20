import sys
from PyQt5.QtWidgets import QApplication, QWidget, QMainWindow, QLabel
from PyQt5.QtGui import QPainter, QPen, QBrush, QColor, QPalette, QLinearGradient, QIcon, QPixmap, QCursor
from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("My cool first GUI")
        self.setWindowIcon(QIcon('ad2.png'))
        self.setGeometry(700, 300, 1980, 1120)
        label = QLabel(self)
        label.setGeometry(0, 0, 1980, 1120)
        pixmap = QPixmap('img1.jpg')
        label.setPixmap(pixmap)
        label.setScaledContents(True)
        label.setGeometry(self.width(), - label.width(), 0, label.height())
        
def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':    
    main()