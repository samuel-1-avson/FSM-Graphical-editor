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
        self.setGeometry(700, 300, 500, 500)
        self.setWindowIcon(QIcon('ad2.png'))
        label = QLabel('Hello', self)
        label.setFont(QFont('Arial', 40))
        label.setGeometry(0, 0, 500, 100)
        label.setStyleSheet("color: #2929;"
                            "background-color: blue;"
                            "font-weight: bold;"
                            "font-style: italic;"
                            "text-decoration: underline;")
        
        
def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':    
    main()