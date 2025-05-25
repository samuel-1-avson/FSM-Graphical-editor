# graphics_items.py
import math
from typing import Optional, Dict, Any
from PyQt5.QtWidgets import (
    QGraphicsRectItem, QGraphicsPathItem, QGraphicsTextItem,
    QGraphicsItem, QGraphicsDropShadowEffect, QGraphicsSceneMouseEvent
)
from PyQt5.QtGui import (
    QBrush, QColor, QFont, QPen, QPainterPath, QPolygonF, QPainter,
    QPainterPathStroker, QFontMetrics
)
from PyQt5.QtCore import Qt, QRectF, QPointF, QLineF

from config import (
    COLOR_ITEM_STATE_DEFAULT_BG, COLOR_ITEM_STATE_DEFAULT_BORDER, APP_FONT_FAMILY,
    COLOR_TEXT_PRIMARY, COLOR_ITEM_STATE_SELECTION, COLOR_ITEM_TRANSITION_DEFAULT,
    COLOR_ITEM_TRANSITION_SELECTION, COLOR_ITEM_COMMENT_BG, COLOR_ITEM_COMMENT_BORDER,
    COLOR_PY_SIM_STATE_ACTIVE, COLOR_PY_SIM_STATE_ACTIVE_PEN_WIDTH,
    COLOR_BACKGROUND_LIGHT, COLOR_BORDER_LIGHT, COLOR_ACCENT_PRIMARY
)


class BaseGraphicsItem:
    """Base class providing common functionality for all graphics items."""
    
    def __init__(self):
        self._setup_common_flags()
        self._setup_shadow_effect()
    
    def _setup_common_flags(self):
        """Set up common item flags."""
        self.setFlags(
            QGraphicsItem.ItemIsSelectable |
            QGraphicsItem.ItemIsMovable |
            QGraphicsItem.ItemSendsGeometryChanges |
            QGraphicsItem.ItemIsFocusable
        )
    
    def _setup_shadow_effect(self, blur_radius: int = 10, offset: tuple = (2.5, 2.5), alpha: int = 60):
        """Set up drop shadow effect."""
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(blur_radius)
        shadow.setColor(QColor(0, 0, 0, alpha))
        shadow.setOffset(*offset)
        self.setGraphicsEffect(shadow)
    
    def itemChange(self, change, value):
        """Handle item changes and emit signals."""
        if change == QGraphicsItem.ItemPositionHasChanged and self.scene():
            self.scene().item_moved.emit(self)
        return super().itemChange(change, value)


class GraphicsStateItem(QGraphicsRectItem, BaseGraphicsItem):
    """Enhanced state item with improved organization and performance."""
    
    Type = QGraphicsItem.UserType + 1
    
    # Class constants
    BORDER_RADIUS = 10
    TEXT_PADDING = 8
    INITIAL_MARKER_RADIUS = 6
    INITIAL_LINE_LENGTH = 18
    ARROW_SIZE = 8
    FINAL_INNER_OFFSET = 5
    
    def __init__(self, x: float, y: float, w: float, h: float, text: str, 
                 is_initial: bool = False, is_final: bool = False,
                 color: Optional[str] = None, entry_action: str = "",
                 during_action: str = "", exit_action: str = "", description: str = ""):
        QGraphicsRectItem.__init__(self, x, y, w, h)
        BaseGraphicsItem.__init__(self)
        
        # Core properties
        self.text_label = text
        self.is_initial = is_initial
        self.is_final = is_final
        self.entry_action = entry_action
        self.during_action = during_action
        self.exit_action = exit_action
        self.description = description
        
        # Visual properties
        self._setup_colors(color)
        self._setup_appearance()
        
        # State management
        self._is_hovered = False
        self.is_py_sim_active = False
        self._store_original_styles()
        
        self.setAcceptHoverEvents(True)
    
    def type(self) -> int:
        return GraphicsStateItem.Type
    
    def _setup_colors(self, color: Optional[str]):
        """Initialize color scheme."""
        if color:
            self.base_color = QColor(color)
            self.border_color = QColor(color).darker(120)
        else:
            self.base_color = QColor(COLOR_ITEM_STATE_DEFAULT_BG)
            self.border_color = QColor(COLOR_ITEM_STATE_DEFAULT_BORDER)
        
        self.hover_border_color = self.border_color.lighter(130)
        self.hover_brush_color = self.base_color.lighter(105)
    
    def _setup_appearance(self):
        """Initialize visual appearance."""
        self._text_color = QColor(COLOR_TEXT_PRIMARY)
        self._font = QFont(APP_FONT_FAMILY, 10, QFont.Bold)
        self._border_pen_width = 1.5
        
        self.setPen(QPen(self.border_color, self._border_pen_width))
        self.setBrush(QBrush(self.base_color))
    
    def _store_original_styles(self):
        """Store original styles for simulation mode restoration."""
        self.original_pen_for_py_sim_restore = QPen(self.pen())
        self.original_brush_for_py_sim_restore = QBrush(self.brush())
    
    def hoverEnterEvent(self, event: QGraphicsSceneMouseEvent):
        """Handle hover enter."""
        self._is_hovered = True
        self.update()
        super().hoverEnterEvent(event)
    
    def hoverLeaveEvent(self, event: QGraphicsSceneMouseEvent):
        """Handle hover leave."""
        self._is_hovered = False
        self.update()
        super().hoverLeaveEvent(event)
    
    def paint(self, painter: QPainter, option, widget):
        """Enhanced paint method with better organization."""
        painter.setRenderHint(QPainter.Antialiasing)
        
        current_rect = self.rect()
        pen, brush = self._get_current_styles()
        
        # Draw main shape
        painter.setPen(pen)
        painter.setBrush(brush)
        painter.drawRoundedRect(current_rect, self.BORDER_RADIUS, self.BORDER_RADIUS)
        
        # Draw text
        self._draw_text(painter, current_rect)
        
        # Draw state markers
        if self.is_initial:
            self._draw_initial_marker(painter, current_rect)
        if self.is_final:
            self._draw_final_marker(painter, current_rect)
        
        # Draw selection indicator
        if self.isSelected() and not self.is_py_sim_active:
            self._draw_selection_indicator(painter)
    
    def _get_current_styles(self) -> tuple[QPen, QBrush]:
        """Get current pen and brush based on state."""
        if self.is_py_sim_active:
            pen = QPen(COLOR_PY_SIM_STATE_ACTIVE, COLOR_PY_SIM_STATE_ACTIVE_PEN_WIDTH, Qt.DashLine)
            brush = self.brush()
        elif self._is_hovered and not self.isSelected():
            pen = QPen(self.hover_border_color, self._border_pen_width + 0.5)
            brush = QBrush(self.hover_brush_color)
        else:
            pen = self.pen()
            brush = self.brush()
        
        return pen, brush
    
    def _draw_text(self, painter: QPainter, rect: QRectF):
        """Draw state text."""
        painter.setPen(self._text_color)
        painter.setFont(self._font)
        text_rect = rect.adjusted(self.TEXT_PADDING, self.TEXT_PADDING, 
                                 -self.TEXT_PADDING, -self.TEXT_PADDING)
        painter.drawText(text_rect, Qt.AlignCenter | Qt.TextWordWrap, self.text_label)
    
    def _draw_initial_marker(self, painter: QPainter, rect: QRectF):
        """Draw initial state marker with arrow."""
        marker_color = Qt.black
        start_x = rect.left() - self.INITIAL_LINE_LENGTH - self.INITIAL_MARKER_RADIUS / 2
        start_y = rect.center().y()
        
        # Draw marker circle
        painter.setBrush(marker_color)
        painter.setPen(QPen(marker_color, self._border_pen_width))
        painter.drawEllipse(QPointF(start_x, start_y), 
                          self.INITIAL_MARKER_RADIUS, self.INITIAL_MARKER_RADIUS)
        
        # Draw line and arrow
        line_start = QPointF(start_x + self.INITIAL_MARKER_RADIUS, start_y)
        line_end = QPointF(rect.left(), start_y)
        painter.drawLine(line_start, line_end)
        
        self._draw_arrow(painter, line_end, 0)
    
    def _draw_final_marker(self, painter: QPainter, rect: QRectF):
        """Draw final state marker (inner rectangle)."""
        painter.setPen(QPen(self.border_color.darker(120), self._border_pen_width + 0.5))
        inner_rect = rect.adjusted(self.FINAL_INNER_OFFSET, self.FINAL_INNER_OFFSET, 
                                  -self.FINAL_INNER_OFFSET, -self.FINAL_INNER_OFFSET)
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(inner_rect, self.BORDER_RADIUS - 3, self.BORDER_RADIUS - 3)
    
    def _draw_arrow(self, painter: QPainter, point: QPointF, angle_rad: float):
        """Draw arrow at specified point and angle."""
        arrow_p1 = QPointF(
            point.x() - self.ARROW_SIZE * math.cos(angle_rad + math.pi / 6),
            point.y() - self.ARROW_SIZE * math.sin(angle_rad + math.pi / 6)
        )
        arrow_p2 = QPointF(
            point.x() - self.ARROW_SIZE * math.cos(angle_rad - math.pi / 6),
            point.y() - self.ARROW_SIZE * math.sin(angle_rad - math.pi / 6)
        )
        painter.drawPolygon(QPolygonF([point, arrow_p1, arrow_p2]))
    
    def _draw_selection_indicator(self, painter: QPainter):
        """Draw selection indicator."""
        selection_pen = QPen(QColor(COLOR_ITEM_STATE_SELECTION), self._border_pen_width + 1)
        selection_rect = self.boundingRect().adjusted(-1, -1, 1, 1)
        painter.setPen(selection_pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(selection_rect, self.BORDER_RADIUS + 1, self.BORDER_RADIUS + 1)
    
    def set_py_sim_active_style(self, active: bool):
        """Toggle Python simulation active style."""
        if self.is_py_sim_active == active:
            return
        
        self.is_py_sim_active = active
        if active:
            self._store_original_styles()
        else:
            self.setPen(self.original_pen_for_py_sim_restore)
            self.setBrush(self.original_brush_for_py_sim_restore)
        
        self.update()
    
    def get_data(self) -> Dict[str, Any]:
        """Get state data for serialization."""
        return {
            'name': self.text_label,
            'x': self.x(),
            'y': self.y(),
            'width': self.rect().width(),
            'height': self.rect().height(),
            'is_initial': self.is_initial,
            'is_final': self.is_final,
            'color': self.base_color.name(),
            'entry_action': self.entry_action,
            'during_action': self.during_action,
            'exit_action': self.exit_action,
            'description': self.description
        }
    
    def set_text(self, text: str):
        """Update state text."""
        if self.text_label != text:
            self.prepareGeometryChange()
            self.text_label = text
            self.update()
    
    def set_properties(self, name: str, is_initial: bool, is_final: bool,
                      color_hex: Optional[str] = None, entry_action: str = "",
                      during_action: str = "", exit_action: str = "", description: str = ""):
        """Update state properties."""
        changed = self._update_basic_properties(name, is_initial, is_final, 
                                              entry_action, during_action, exit_action, description)
        
        if self._update_colors(color_hex):
            changed = True
        
        if changed:
            self.prepareGeometryChange()
            self.update()
    
    def _update_basic_properties(self, name: str, is_initial: bool, is_final: bool,
                               entry_action: str, during_action: str, exit_action: str, description: str) -> bool:
        """Update basic properties and return whether any changed."""
        changed = False
        properties = [
            ('text_label', name),
            ('is_initial', is_initial),
            ('is_final', is_final),
            ('entry_action', entry_action),
            ('during_action', during_action),
            ('exit_action', exit_action),
            ('description', description)
        ]
        
        for attr, value in properties:
            if getattr(self, attr) != value:
                setattr(self, attr, value)
                changed = True
        
        return changed
    
    def _update_colors(self, color_hex: Optional[str]) -> bool:
        """Update color scheme and return whether it changed."""
        new_base_color = QColor(color_hex) if color_hex else QColor(COLOR_ITEM_STATE_DEFAULT_BG)
        
        if self.base_color != new_base_color:
            self._setup_colors(color_hex)
            
            current_pen = QPen(self.border_color, self._border_pen_width)
            current_brush = QBrush(self.base_color)
            
            self.setPen(current_pen)
            self.setBrush(current_brush)
            self._store_original_styles()
            
            return True
        return False


class GraphicsTransitionItem(QGraphicsPathItem, BaseGraphicsItem):
    """Enhanced transition item with improved path handling and visual feedback."""
    
    Type = QGraphicsItem.UserType + 2
    
    # Class constants
    ARROW_SIZE = 10
    PEN_WIDTH = 2.0
    FONT_SIZE = 8
    STROKE_WIDTH_FOR_SHAPE = 18
    TEXT_BACKGROUND_PADDING = 2
    TEXT_OFFSET_DISTANCE = 10
    LOOP_RADIUS_FACTOR = 0.40
    CONTROL_POINT_FACTOR = 1.6
    
    def __init__(self, start_item: Optional['GraphicsStateItem'], 
                 end_item: Optional['GraphicsStateItem'],
                 event_str: str = "", condition_str: str = "", action_str: str = "",
                 color: Optional[str] = None, description: str = ""):
        QGraphicsPathItem.__init__(self)
        BaseGraphicsItem.__init__(self)
        
        self.start_item = start_item
        self.end_item = end_item
        self.event_str = event_str
        self.condition_str = condition_str
        self.action_str = action_str
        self.description = description
        
        self.base_color = QColor(color) if color else QColor(COLOR_ITEM_TRANSITION_DEFAULT)
        self.control_point_offset = QPointF(0, 0)
        
        self._setup_appearance()
        self.setAcceptHoverEvents(True)
        self.update_path()
    
    def type(self) -> int:
        return GraphicsTransitionItem.Type
    
    def _setup_appearance(self):
        """Initialize visual appearance."""
        self._text_color = QColor(COLOR_TEXT_PRIMARY)
        self._font = QFont(APP_FONT_FAMILY, self.FONT_SIZE)
        
        self.setPen(QPen(self.base_color, self.PEN_WIDTH, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsFocusable, True)
        self.setZValue(-1)
    
    def _compose_label_string(self) -> str:
        """Compose transition label from components."""
        parts = []
        if self.event_str:
            parts.append(self.event_str)
        if self.condition_str:
            parts.append(f"[{self.condition_str}]")
        if self.action_str:
            parts.append(f"/{{{self.action_str}}}")
        return " ".join(parts)
    
    def hoverEnterEvent(self, event: QGraphicsSceneMouseEvent):
        """Handle hover enter with visual feedback."""
        self.setPen(QPen(self.base_color.lighter(130), self.PEN_WIDTH + 0.5))
        super().hoverEnterEvent(event)
    
    def hoverLeaveEvent(self, event: QGraphicsSceneMouseEvent):
        """Handle hover leave."""
        self.setPen(QPen(self.base_color, self.PEN_WIDTH))
        super().hoverLeaveEvent(event)
    
    def boundingRect(self) -> QRectF:
        """Calculate bounding rectangle including text and arrow."""
        extra = (self.pen().widthF() + self.ARROW_SIZE) / 2.0 + 25
        path_bounds = self.path().boundingRect()
        
        current_label = self._compose_label_string()
        if current_label:
            fm = QFontMetrics(self._font)
            text_rect = fm.boundingRect(current_label)
            mid_point = self.path().pointAtPercent(0.5)
            
            text_render_rect = QRectF(
                mid_point.x() - text_rect.width() - 10,
                mid_point.y() - text_rect.height() - 10,
                text_rect.width() * 2 + 20,
                text_rect.height() * 2 + 20
            )
            path_bounds = path_bounds.united(text_render_rect)
        
        return path_bounds.adjusted(-extra, -extra, extra, extra)
    
    def shape(self) -> QPainterPath:
        """Create shape for better hit detection."""
        stroker = QPainterPathStroker()
        stroker.setWidth(self.STROKE_WIDTH_FOR_SHAPE + self.pen().widthF())
        stroker.setCapStyle(Qt.RoundCap)
        stroker.setJoinStyle(Qt.RoundJoin)
        return stroker.createStroke(self.path())
    
    def update_path(self):
        """Update the transition path between states."""
        if not self.start_item or not self.end_item:
            self.setPath(QPainterPath())
            return
        
        start_center = self.start_item.sceneBoundingRect().center()
        end_center = self.end_item.sceneBoundingRect().center()
        
        start_point = self._get_intersection_point(self.start_item, QLineF(start_center, end_center))
        end_point = self._get_intersection_point(self.end_item, QLineF(end_center, start_center))
        
        if start_point is None:
            start_point = start_center
        if end_point is None:
            end_point = end_center
        
        path = self._create_path(start_point, end_point)
        self.setPath(path)
        self.prepareGeometryChange()
    
    def _create_path(self, start_point: QPointF, end_point: QPointF) -> QPainterPath:
        """Create the actual path between points."""
        path = QPainterPath(start_point)
        
        if self.start_item == self.end_item:
            # Self-loop
            path, end_point = self._create_self_loop_path(path)
        else:
            # Regular transition
            path = self._create_regular_path(path, start_point, end_point)
        
        return path
    
    def _create_self_loop_path(self, path: QPainterPath) -> tuple[QPainterPath, QPointF]:
        """Create a self-loop path."""
        rect = self.start_item.sceneBoundingRect()
        loop_radius_x = rect.width() * self.LOOP_RADIUS_FACTOR
        loop_radius_y = rect.height() * self.LOOP_RADIUS_FACTOR
        
        p1 = QPointF(rect.center().x() + loop_radius_x * 0.35, rect.top())
        p2 = QPointF(rect.center().x() - loop_radius_x * 0.35, rect.top())
        
        ctrl1 = QPointF(rect.center().x() + loop_radius_x * self.CONTROL_POINT_FACTOR,
                       rect.top() - loop_radius_y * 2.8)
        ctrl2 = QPointF(rect.center().x() - loop_radius_x * self.CONTROL_POINT_FACTOR,
                       rect.top() - loop_radius_y * 2.8)
        
        path.moveTo(p1)
        path.cubicTo(ctrl1, ctrl2, p2)
        
        return path, p2
    
    def _create_regular_path(self, path: QPainterPath, start_point: QPointF, end_point: QPointF) -> QPainterPath:
        """Create a regular transition path."""
        if self.control_point_offset.x() == 0 and self.control_point_offset.y() == 0:
            path.lineTo(end_point)
        else:
            mid_x = (start_point.x() + end_point.x()) / 2
            mid_y = (start_point.y() + end_point.y()) / 2
            
            dx = end_point.x() - start_point.x()
            dy = end_point.y() - start_point.y()
            length = math.hypot(dx, dy) or 1
            
            perp_x = -dy / length
            perp_y = dx / length
            
            ctrl_pt_x = (mid_x + perp_x * self.control_point_offset.x() + 
                        (dx / length) * self.control_point_offset.y())
            ctrl_pt_y = (mid_y + perp_y * self.control_point_offset.x() + 
                        (dy / length) * self.control_point_offset.y())
            
            path.quadTo(QPointF(ctrl_pt_x, ctrl_pt_y), end_point)
        
        return path
    
    def _get_intersection_point(self, item: QGraphicsRectItem, line: QLineF) -> Optional[QPointF]:
        """Find intersection point between line and item boundary."""
        item_rect = item.sceneBoundingRect()
        edges = [
            QLineF(item_rect.topLeft(), item_rect.topRight()),
            QLineF(item_rect.topRight(), item_rect.bottomRight()),
            QLineF(item_rect.bottomRight(), item_rect.bottomLeft()),
            QLineF(item_rect.bottomLeft(), item_rect.topLeft())
        ]
        
        intersect_points = []
        for edge in edges:
            intersection_point = QPointF()
            intersect_type = line.intersect(edge, intersection_point)
            
            if intersect_type == QLineF.BoundedIntersection:
                if self._point_on_edge(intersection_point, edge):
                    intersect_points.append(QPointF(intersection_point))
        
        if not intersect_points:
            return item_rect.center()
        
        # Return closest intersection point
        return min(intersect_points, key=lambda pt: QLineF(line.p1(), pt).length())
    
    def _point_on_edge(self, point: QPointF, edge: QLineF, epsilon: float = 1e-3) -> bool:
        """Check if point lies on the edge segment."""
        edge_rect = QRectF(edge.p1(), edge.p2()).normalized()
        return (edge_rect.left() - epsilon <= point.x() <= edge_rect.right() + epsilon and
                edge_rect.top() - epsilon <= point.y() <= edge_rect.bottom() + epsilon)
    
    def paint(self, painter: QPainter, option, widget):
        """Enhanced paint method with better text rendering."""
        if not self.start_item or not self.end_item or self.path().isEmpty():
            return
        
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw selection background
        if self.isSelected():
            self._draw_selection_background(painter)
        
        # Draw main path
        painter.setPen(self.pen())
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(self.path())
        
        # Draw arrow
        self._draw_arrow(painter)
        
        # Draw label
        self._draw_label(painter)
    
    def _draw_selection_background(self, painter: QPainter):
        """Draw selection background."""
        stroker = QPainterPathStroker()
        stroker.setWidth(self.pen().widthF() + 6)
        stroker.setCapStyle(Qt.RoundCap)
        stroker.setJoinStyle(Qt.RoundJoin)
        
        selection_path = stroker.createStroke(self.path())
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(COLOR_ITEM_TRANSITION_SELECTION))
        painter.drawPath(selection_path)
    
    def _draw_arrow(self, painter: QPainter):
        """Draw arrow at path end."""
        if self.path().elementCount() < 1:
            return
        
        percent_at_end = 0.999 if self.path().length() >= 1 else 0.9
        line_end_point = self.path().pointAtPercent(1.0)
        angle_at_end_rad = -self.path().angleAtPercent(percent_at_end) * (math.pi / 180.0)
        
        arrow_p1 = line_end_point + QPointF(
            math.cos(angle_at_end_rad - math.pi / 7) * self.ARROW_SIZE,
            math.sin(angle_at_end_rad - math.pi / 7) * self.ARROW_SIZE
        )
        arrow_p2 = line_end_point + QPointF(
            math.cos(angle_at_end_rad + math.pi / 7) * self.ARROW_SIZE,
            math.sin(angle_at_end_rad + math.pi / 7) * self.ARROW_SIZE
        )
        
        painter.setBrush(self.pen().color())
        painter.drawPolygon(QPolygonF([line_end_point, arrow_p1, arrow_p2]))
    
    def _draw_label(self, painter: QPainter):
        """Draw transition label with background."""
        current_label = self._compose_label_string()
        if not current_label:
            return
        
        painter.setFont(self._font)
        fm = QFontMetrics(self._font)
        text_rect = fm.boundingRect(current_label)
        
        # Calculate text position
        text_pos_on_path = self.path().pointAtPercent(0.5)
        angle_at_mid_deg = self.path().angleAtPercent(0.5)
        offset_angle_rad = (angle_at_mid_deg - 90.0) * (math.pi / 180.0)
        
        text_center_x = text_pos_on_path.x() + self.TEXT_OFFSET_DISTANCE * math.cos(offset_angle_rad)
        text_center_y = text_pos_on_path.y() + self.TEXT_OFFSET_DISTANCE * math.sin(offset_angle_rad)
        
        text_final_pos = QPointF(
            text_center_x - text_rect.width() / 2,
            text_center_y - text_rect.height() / 2
        )
        
        # Draw background
        bg_rect = QRectF(
            text_final_pos.x() - self.TEXT_BACKGROUND_PADDING,
            text_final_pos.y() - self.TEXT_BACKGROUND_PADDING,
            text_rect.width() + 2 * self.TEXT_BACKGROUND_PADDING,
            text_rect.height() + 2 * self.TEXT_BACKGROUND_PADDING
        )
        
        painter.setBrush(QColor(COLOR_BACKGROUND_LIGHT).lighter(102))
        painter.setPen(QPen(QColor(COLOR_BORDER_LIGHT), 0.5))
        painter.drawRoundedRect(bg_rect, 3, 3)
        
        # Draw text
        painter.setPen(self._text_color)
        painter.drawText(text_final_pos, current_label)
    
    def get_data(self) -> Dict[str, Any]:
        """Get transition data for serialization."""
        return {
            'source': self.start_item.text_label if self.start_item else "None",
            'target': self.end_item.text_label if self.end_item else "None",
            'event': self.event_str,
            'condition': self.condition_str,
            'action': self.action_str,
            'color': self.base_color.name(),
            'description': self.description,
            'control_offset_x': self.control_point_offset.x(),
            'control_offset_y': self.control_point_offset.y()
        }
    
    def set_properties(self, event_str: str = "", condition_str: str = "", action_str: str = "",
                      color_hex: Optional[str] = None, description: str = "", 
                      offset: Optional[QPointF] = None):
        """Update transition properties."""
        changed = False
        
        # Update basic properties
        properties = [
            ('event_str', event_str),
            ('condition_str', condition_str),
            ('action_str', action_str),
            ('description', description)
        ]
        
        for attr, value in properties:
            if getattr(self, attr) != value:
                setattr(self, attr, value)
                changed = True
        
        # Update color
        if color_hex:
            new_color = QColor(color_hex)
            if self.base_color != new_color:
                self.base_color = new_color
                self.setPen(QPen(self.base_color, self.PEN_WIDTH))
                changed = True
        
        # Update control point offset
        if offset is not None and self.control_point_offset != offset:
            self.control_point_offset = offset
            changed = True
            self.update_path()  # Path needs update for offset changes
        
        if changed:
            self.prepareGeometryChange()
            self.update()
    
    def set_control_point_offset(self, offset: QPointF):
        """Set control point offset for curved paths."""
        if self.control_point_offset != offset:
            self.control_point_offset = offset
            self.update_path()
            self.update()


class GraphicsCommentItem(QGraphicsTextItem, BaseGraphicsItem):
    """Enhanced comment item with improved text handling and appearance."""
    
    Type = QGraphicsItem.UserType + 3
    
    # Class constants
    DEFAULT_WIDTH = 150
    BORDER_RADIUS = 4
    FONT_SIZE = 9
    
    def __init__(self, x: float, y: float, text: str = "Comment"):
        QGraphicsTextItem.__init__(self)
        BaseGraphicsItem.__init__(self)
        
        self.setPlainText(text)
        self.setPos(x, y)
        
        self._setup_appearance()
        self._setup_interaction()
        
        # Connect text change signal
        if self.document():
            self.document().contentsChanged.connect(self._on_contents_changed)
    
    def type(self) -> int:
        return GraphicsCommentItem.Type
    
    def _setup_appearance(self):
        """Initialize visual appearance."""
        self.setFont(QFont(APP_FONT_FAMILY, self.FONT_SIZE))
        self.setTextWidth(self.DEFAULT_WIDTH)
        
        self.border_pen = QPen(QColor(COLOR_ITEM_COMMENT_BORDER), 1)
        self.background_brush = QBrush(QColor(COLOR_ITEM_COMMENT_BG))
        
        # Override shadow effect from base class for comments
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(8)
        shadow.setColor(QColor(0, 0, 0, 50))
        shadow.setOffset(2, 2)
        self.setGraphicsEffect(shadow)
    
    def _setup_interaction(self):
        """Setup text interaction and flags."""
        self.setTextInteractionFlags(Qt.TextEditorInteraction)
        # Flags are set in BaseGraphicsItem.__init__()
    
    def _on_contents_changed(self):
        """Handle text content changes."""
        self.prepareGeometryChange()
        if self.scene():
            self.scene().item_moved.emit(self)
    
    def paint(self, painter: QPainter, option, widget):
        """Enhanced paint method with better background rendering."""
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw background
        painter.setPen(self.border_pen)
        painter.setBrush(self.background_brush)
        rect = self.boundingRect()
        painter.drawRoundedRect(
            rect.adjusted(0.5, 0.5, -0.5, -0.5), 
            self.BORDER_RADIUS, 
            self.BORDER_RADIUS
        )
        
        # Draw text
        self.setDefaultTextColor(QColor(COLOR_TEXT_PRIMARY))
        super().paint(painter, option, widget)
        
        # Draw selection indicator
        if self.isSelected():
            self._draw_selection_indicator(painter)
    
    def _draw_selection_indicator(self, painter: QPainter):
        """Draw selection indicator for comments."""
        selection_pen = QPen(QColor(COLOR_ACCENT_PRIMARY), 1.5, Qt.DashLine)
        painter.setPen(selection_pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(self.boundingRect())
    
    def get_data(self) -> Dict[str, Any]:
        """Get comment data for serialization."""
        doc_width = (self.document().idealWidth() 
                    if self.textWidth() < 0 
                    else self.textWidth())
        
        return {
            'text': self.toPlainText(),
            'x': self.x(),
            'y': self.y(),
            'width': doc_width
        }
    
    def set_properties(self, text: str, width: Optional[float] = None):
        """Update comment properties."""
        current_text = self.toPlainText()
        text_changed = (current_text != text)
        
        current_text_width = self.textWidth()
        target_width = width if width and width > 0 else self.DEFAULT_WIDTH
        width_changed = (current_text_width != target_width)
        
        if text_changed:
            self.setPlainText(text)
        
        if width_changed:
            self.setTextWidth(target_width)
        
        if text_changed or width_changed:
            self.update()


# Utility functions for graphics items
class GraphicsItemFactory:
    """Factory class for creating graphics items with consistent settings."""
    
    @staticmethod
    def create_state(x: float, y: float, w: float, h: float, text: str, **kwargs) -> GraphicsStateItem:
        """Create a state item with default settings."""
        return GraphicsStateItem(x, y, w, h, text, **kwargs)
    
    @staticmethod
    def create_transition(start_item: GraphicsStateItem, end_item: GraphicsStateItem, **kwargs) -> GraphicsTransitionItem:
        """Create a transition item between two states."""
        return GraphicsTransitionItem(start_item, end_item, **kwargs)
    
    @staticmethod
    def create_comment(x: float, y: float, text: str = "Comment") -> GraphicsCommentItem:
        """Create a comment item."""
        return GraphicsCommentItem(x, y, text)


class GraphicsItemUtils:
    """Utility functions for working with graphics items."""
    
    @staticmethod
    def get_item_center(item: QGraphicsItem) -> QPointF:
        """Get the center point of any graphics item."""
        return item.sceneBoundingRect().center()
    
    @staticmethod
    def calculate_distance(item1: QGraphicsItem, item2: QGraphicsItem) -> float:
        """Calculate distance between two graphics items."""
        p1 = GraphicsItemUtils.get_item_center(item1)
        p2 = GraphicsItemUtils.get_item_center(item2)
        return math.hypot(p2.x() - p1.x(), p2.y() - p1.y())
    
    @staticmethod
    def find_nearest_state(target_item: QGraphicsItem, state_items: list) -> Optional[GraphicsStateItem]:
        """Find the nearest state item to the target item."""
        if not state_items:
            return None
        
        return min(state_items, 
                  key=lambda state: GraphicsItemUtils.calculate_distance(target_item, state))
    
    @staticmethod
    def validate_transition_connection(start_item: GraphicsStateItem, end_item: GraphicsStateItem) -> bool:
        """Validate that a transition connection is valid."""
        return (start_item is not None and 
                end_item is not None and 
                isinstance(start_item, GraphicsStateItem) and 
                isinstance(end_item, GraphicsStateItem))


# Type hints for better IDE support
StateItemType = GraphicsStateItem
TransitionItemType = GraphicsTransitionItem
CommentItemType = GraphicsCommentItem