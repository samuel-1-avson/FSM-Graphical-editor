# bsm_designer_project/custom_widgets.py

from PyQt5.QtWidgets import QPushButton, QApplication, QWidget, QToolButton 
from PyQt5.QtGui import QMouseEvent, QDrag, QPixmap, QPainter, QColor, QRegion
from PyQt5.QtCore import Qt, QPoint, QMimeData, QSize
import json 

class DraggableToolButton(QPushButton): 
    def __init__(self, text, mime_type, item_type_data_str, parent=None):
        super().__init__(text, parent)
        self.setObjectName("DraggableToolButton") 
        self.mime_type = mime_type
        self.item_type_data_str = item_type_data_str
        
        self.setMinimumHeight(42) 
        self.setIconSize(QSize(24, 24)) 
        
        self.drag_start_position = QPoint()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.drag_start_position = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if not (event.buttons() & Qt.LeftButton):
            return
        if (event.pos() - self.drag_start_position).manhattanLength() < QApplication.startDragDistance():
            return

        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setData(self.mime_type, self.item_type_data_str.encode('utf-8'))

        if self.mime_type == "application/x-bsm-template":
            try:
                template_obj = json.loads(self.item_type_data_str)
                mime_data.setText(f"FSM Template: {template_obj.get('name', 'Custom Template')}")
            except json.JSONDecodeError:
                mime_data.setText("FSM Template (Invalid JSON)")
        else:
            mime_data.setText(self.item_type_data_str)

        drag.setMimeData(mime_data)

        pixmap = QPixmap(self.size())
        pixmap.fill(Qt.transparent)
        
        # Corrected renderFlags usage
        # QWidget.DrawChildren is a common flag for this purpose.
        # You can combine flags using the bitwise OR operator if needed, e.g.,
        # QWidget.DrawChildren | QWidget.IgnoreMask
        self.render(pixmap, QPoint(), QRegion(), QWidget.RenderFlags(QWidget.DrawChildren))


        painter = QPainter(pixmap)
        painter.setCompositionMode(QPainter.CompositionMode_DestinationIn)
        painter.fillRect(pixmap.rect(), QColor(0, 0, 0, 150)) 
        painter.end()

        drag.setPixmap(pixmap)
        drag.setHotSpot(event.pos())
        drag.exec_(Qt.CopyAction)