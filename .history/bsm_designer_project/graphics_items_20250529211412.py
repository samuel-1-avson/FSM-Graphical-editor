
# bsm_designer_project/graphics_items.py

import math
from PyQt5.QtWidgets import (QGraphicsRectItem, QGraphicsPathItem, QGraphicsTextItem,
                             QGraphicsItem, QGraphicsDropShadowEffect, QApplication, QGraphicsSceneMouseEvent)
from PyQt5.QtGui import (QBrush, QColor, QFont, QPen, QPainterPath, QPolygonF, QPainter,
                         QPainterPathStroker, QPixmap, QMouseEvent, QDrag, QPalette)
from PyQt5.QtCore import Qt, QRectF, QPointF, QMimeData, QPoint, QLineF, QSize

from config import (COLOR_ITEM_STATE_DEFAULT_BG, COLOR_ITEM_STATE_DEFAULT_BORDER, APP_FONT_FAMILY,
                    COLOR_TEXT_PRIMARY, COLOR_ITEM_STATE_SELECTION_BG, COLOR_ITEM_STATE_SELECTION_BORDER,
                    COLOR_ITEM_TRANSITION_DEFAULT, COLOR_ITEM_TRANSITION_SELECTION, 
                    COLOR_ITEM_COMMENT_BG, COLOR_ITEM_COMMENT_BORDER,
                    COLOR_PY_SIM_STATE_ACTIVE, COLOR_PY_SIM_STATE_ACTIVE_PEN_WIDTH,
                    COLOR_BACKGROUND_LIGHT, COLOR_BORDER_LIGHT, COLOR_ACCENT_PRIMARY,
                    DEFAULT_EXECUTION_ENV, COLOR_TEXT_SECONDARY, COLOR_BACKGROUND_DIALOG)


class GraphicsStateItem(QGraphicsRectItem):
    Type = QGraphicsItem.UserType + 1

    def type(self): return GraphicsStateItem.Type

    def __init__(self, x, y, w, h, text, is_initial=False, is_final=False,
                 color=None, entry_action="", during_action="", exit_action="", description="",
                 is_superstate=False, sub_fsm_data=None, action_language=DEFAULT_EXECUTION_ENV): # Added action_language
        super().__init__(x, y, w, h)
        self.text_label = text
        self.is_initial = is_initial
        self.is_final = is_final
        self.is_superstate = is_superstate
        if sub_fsm_data and isinstance(sub_fsm_data, dict) and \
           all(k in sub_fsm_data for k in ['states', 'transitions', 'comments']):
            self.sub_fsm_data = sub_fsm_data
        else:
            self.sub_fsm_data = {'states': [], 'transitions': [], 'comments': []}

        self.base_color = QColor(color) if color and QColor(color).isValid() else QColor(COLOR_ITEM_STATE_DEFAULT_BG)
        self.border_color = QColor(color).darker(120) if color and QColor(color).isValid() else QColor(COLOR_ITEM_STATE_DEFAULT_BORDER)
        
        self.action_language = action_language 
        self.entry_action = entry_action
        self.during_action = during_action
        self.exit_action = exit_action
        self.description = description

        self._text_color = QColor(COLOR_TEXT_PRIMARY)
        self._font = QFont(APP_FONT_FAMILY, 10, QFont.Bold)
        self._border_pen_width = 1.8 # Slightly thicker border for states

        self.setPen(QPen(self.border_color, self._border_pen_width))
        self.setBrush(QBrush(self.base_color))

        self.setFlags(QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsMovable |
                      QGraphicsItem.ItemSendsGeometryChanges | QGraphicsItem.ItemIsFocusable)
        self.setAcceptHoverEvents(True)

        self.shadow_effect = QGraphicsDropShadowEffect()
        self.shadow_effect.setBlurRadius(12) # Softer, slightly larger shadow
        self.shadow_effect.setColor(QColor(0, 0, 0, 45)) # Lighter shadow
        self.shadow_effect.setOffset(3, 3) # Slightly larger offset
        self.setGraphicsEffect(self.shadow_effect)

        self.is_py_sim_active = False
        self.original_pen_for_py_sim_restore = self.pen()

    def paint(self, painter: QPainter, option, widget):
        painter.setRenderHint(QPainter.Antialiasing)
        current_rect = self.rect()
        border_radius = 12 # More rounded corners

        current_pen_to_use = self.pen()
        if self.is_py_sim_active:
            py_sim_pen = QPen(COLOR_PY_SIM_STATE_ACTIVE, COLOR_PY_SIM_STATE_ACTIVE_PEN_WIDTH, Qt.SolidLine) # Solid for active
            current_pen_to_use = py_sim_pen

        painter.setPen(current_pen_to_use)
        painter.setBrush(self.brush())
        painter.drawRoundedRect(current_rect, border_radius, border_radius)

        # Text styling
        painter.setPen(self._text_color)
        painter.setFont(self._font)
        text_rect = current_rect.adjusted(10, 10, -10, -10) # More padding for text
        painter.drawText(text_rect, Qt.AlignCenter | Qt.TextWordWrap, self.text_label)

        # Initial state marker
        if self.is_initial:
            marker_radius = 7; line_length = 20; marker_color = QColor(COLOR_TEXT_PRIMARY)
            start_marker_center_x = current_rect.left() - line_length - marker_radius / 2
            start_marker_center_y = current_rect.center().y()
            painter.setBrush(marker_color)
            painter.setPen(QPen(marker_color, self._border_pen_width + 0.5)) # Slightly thicker line for marker
            painter.drawEllipse(QPointF(start_marker_center_x, start_marker_center_y), marker_radius, marker_radius)
            line_start_point = QPointF(start_marker_center_x + marker_radius, start_marker_center_y)
            line_end_point = QPointF(current_rect.left(), start_marker_center_y)
            painter.drawLine(line_start_point, line_end_point)
            # Arrowhead
            arrow_size = 9; angle_rad = 0 
            arrow_p1 = QPointF(line_end_point.x() - arrow_size * math.cos(angle_rad + math.pi / 6),
                               line_end_point.y() - arrow_size * math.sin(angle_rad + math.pi / 6))
            arrow_p2 = QPointF(line_end_point.x() - arrow_size * math.cos(angle_rad - math.pi / 6),
                               line_end_point.y() - arrow_size * math.sin(angle_rad - math.pi / 6))
            painter.drawPolygon(QPolygonF([line_end_point, arrow_p1, arrow_p2]))

        # Final state marker (double border)
        if self.is_final:
            painter.setPen(QPen(self.border_color.darker(130), self._border_pen_width)) # Ensure consistent thickness
            inner_rect = current_rect.adjusted(6, 6, -6, -6) # Slightly larger gap for double border
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(inner_rect, border_radius - 4, border_radius - 4) # Adjust radius

        # Superstate icon (simplified, perhaps more abstract)
        if self.is_superstate:
            icon_size = 14 # Larger icon
            icon_margin = 6
            icon_rect_base = QRectF(current_rect.right() - icon_size - icon_margin,
                                    current_rect.top() + icon_margin,
                                    icon_size, icon_size)
            
            painter.setPen(QPen(self.border_color.darker(150), 1.5)) # Slightly thicker icon lines
            
            line_height_part = icon_size / 5.0
            painter.drawLine(QPointF(icon_rect_base.left(), icon_rect_base.top() + line_height_part),
                             QPointF(icon_rect_base.right(), icon_rect_base.top() + line_height_part))
            painter.drawLine(QPointF(icon_rect_base.left(), icon_rect_base.top() + 2.5 * line_height_part),
                             QPointF(icon_rect_base.right(), icon_rect_base.top() + 2.5 * line_height_part))
            painter.drawLine(QPointF(icon_rect_base.left(), icon_rect_base.top() + 4 * line_height_part),
                             QPointF(icon_rect_base.right(), icon_rect_base.top() + 4 * line_height_part))


        # Selection highlight
        if self.isSelected() and not self.is_py_sim_active:
            selection_pen = QPen(QColor(COLOR_ITEM_STATE_SELECTION_BORDER), self._border_pen_width + 1, Qt.DashLine) # Dash line for selection
            selection_brush_color = QColor(COLOR_ITEM_STATE_SELECTION_BG)
            selection_brush_color.setAlpha(80) # Semi-transparent fill for selection
            
            selection_rect = self.boundingRect().adjusted(-2, -2, 2, 2) # Slightly larger highlight rect
            painter.setPen(selection_pen)
            painter.setBrush(QBrush(selection_brush_color)) # Use brush for selection
            painter.drawRoundedRect(selection_rect, border_radius + 2, border_radius + 2)


    def set_py_sim_active_style(self, active: bool):
        if self.is_py_sim_active == active: return
        self.is_py_sim_active = active
        if active: self.original_pen_for_py_sim_restore = QPen(self.pen())
        else: self.setPen(self.original_pen_for_py_sim_restore)
        self.update()

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged and self.scene():
            self.scene().item_moved.emit(self)
        return super().itemChange(change, value)

    def get_data(self):
        return {
            'name': self.text_label, 'x': self.x(), 'y': self.y(),
            'width': self.rect().width(), 'height': self.rect().height(),
            'is_initial': self.is_initial, 'is_final': self.is_final,
            'color': self.base_color.name() if self.base_color else QColor(COLOR_ITEM_STATE_DEFAULT_BG).name(),
            'action_language': self.action_language,
            'entry_action': self.entry_action, 'during_action': self.during_action,
            'exit_action': self.exit_action, 'description': self.description,
            'is_superstate': self.is_superstate,
            'sub_fsm_data': self.sub_fsm_data
        }

    def set_text(self, text):
        if self.text_label != text:
            self.prepareGeometryChange()
            self.text_label = text
            self.update()

    def set_properties(self, name, is_initial, is_final, color_hex=None,
                       action_language=DEFAULT_EXECUTION_ENV, 
                       entry="", during="", exit_a="", desc="",
                       is_superstate_prop=None, sub_fsm_data_prop=None):
        changed = False
        if self.text_label != name: self.text_label = name; changed = True
        if self.is_initial != is_initial: self.is_initial = is_initial; changed = True
        if self.is_final != is_final: self.is_final = is_final; changed = True
        if self.action_language != action_language: self.action_language = action_language; changed = True

        if is_superstate_prop is not None and self.is_superstate != is_superstate_prop:
            self.is_superstate = is_superstate_prop
            changed = True
        
        if sub_fsm_data_prop is not None:
            if isinstance(sub_fsm_data_prop, dict) and \
               all(k in sub_fsm_data_prop for k in ['states', 'transitions', 'comments']) and \
               isinstance(sub_fsm_data_prop['states'], list) and \
               isinstance(sub_fsm_data_prop['transitions'], list) and \
               isinstance(sub_fsm_data_prop['comments'], list):
                if self.sub_fsm_data != sub_fsm_data_prop:
                     self.sub_fsm_data = sub_fsm_data_prop
                     changed = True
            elif self.is_superstate: 
                print(f"Warning: Invalid sub_fsm_data provided for superstate '{name}'. Resetting to empty.")
                pass 

        new_base_color = QColor(color_hex) if color_hex and QColor(color_hex).isValid() else QColor(COLOR_ITEM_STATE_DEFAULT_BG)
        new_border_color = new_base_color.darker(120) if color_hex and QColor(color_hex).isValid() else QColor(COLOR_ITEM_STATE_DEFAULT_BORDER)

        if self.base_color != new_base_color:
            self.base_color = new_base_color
            self.border_color = new_border_color
            self.setBrush(self.base_color)
            new_pen = QPen(self.border_color, self._border_pen_width)
            if not self.is_py_sim_active: self.setPen(new_pen)
            self.original_pen_for_py_sim_restore = new_pen
            changed = True

        if self.entry_action != entry: self.entry_action = entry; changed = True
        if self.during_action != during: self.during_action = during; changed = True
        if self.exit_action != exit_a: self.exit_action = exit_a; changed = True
        if self.description != desc: self.description = desc; changed = True

        if changed:
            self.prepareGeometryChange()
            self.update()


class GraphicsTransitionItem(QGraphicsPathItem):
    Type = QGraphicsItem.UserType + 2
    def type(self): return GraphicsTransitionItem.Type

    def __init__(self, start_item, end_item, event_str="", condition_str="", action_str="",
                 color=None, description="", action_language=DEFAULT_EXECUTION_ENV): 
        super().__init__()
        self.start_item: GraphicsStateItem | None = start_item
        self.end_item: GraphicsStateItem | None = end_item
        self.event_str = event_str
        self.condition_str = condition_str
        self.action_language = action_language 
        self.action_str = action_str
        self.base_color = QColor(color) if color and QColor(color).isValid() else QColor(COLOR_ITEM_TRANSITION_DEFAULT)
        self.description = description
        self.arrow_size = 11 

        self._text_color = QColor(COLOR_TEXT_PRIMARY)
        self._font = QFont(APP_FONT_FAMILY, 8, QFont.Medium) 
        self.control_point_offset = QPointF(0,0)
        self._pen_width = 2.2 

        self.setPen(QPen(self.base_color, self._pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsFocusable, True)
        self.setZValue(-1) 
        self.setAcceptHoverEvents(True)

        self.shadow_effect = QGraphicsDropShadowEffect() 
        self.shadow_effect.setBlurRadius(8)
        self.shadow_effect.setColor(QColor(0, 0, 0, 50))
        self.shadow_effect.setOffset(1.5, 1.5)
        self.setGraphicsEffect(self.shadow_effect)

        self.update_path()

    def _compose_label_string(self):
        parts = []
        if self.event_str: parts.append(self.event_str)
        if self.condition_str: parts.append(f"[{self.condition_str}]")
        if self.action_str: 
            action_display = self.action_str.split('\n')[0] 
            if len(action_display) > 20: action_display = action_display[:17] + "..."
            parts.append(f"/{{{action_display}}}")
        return " ".join(parts)

    def hoverEnterEvent(self, event: QGraphicsSceneMouseEvent):
        self.setPen(QPen(self.base_color.lighter(130), self._pen_width + 0.8)) 
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event: QGraphicsSceneMouseEvent):
        self.setPen(QPen(self.base_color, self._pen_width))
        super().hoverLeaveEvent(event)

    def boundingRect(self):
        extra = (self.pen().widthF() + self.arrow_size) / 2.0 + 30 # Increased extra for text
        path_bounds = self.path().boundingRect()
        current_label = self._compose_label_string()
        if current_label:
            from PyQt5.QtGui import QFontMetrics # Keep import local as it's only for this calculation
            fm = QFontMetrics(self._font)
            # Use an estimated bounding rectangle for the text when calculating combined bounds.
            # Max width for text block is arbitrary but helps give a sensible outer bound.
            # Using a QRectF for the text block calculation with wordWrap.
            text_bounding_rect_for_calculation = QRectF(0,0, 300, 100) # Assume text won't exceed this container for BRect
            text_actual_rect = fm.boundingRect(text_bounding_rect_for_calculation, Qt.TextWordWrap | Qt.AlignCenter, current_label) 
            
            mid_point_on_path = self.path().pointAtPercent(0.5)
            # Position the text's actual rect relative to mid_point_on_path for unioning
            text_render_rect = QRectF(mid_point_on_path.x() - text_actual_rect.width()/2 - 10, # Centered horizontally
                                    mid_point_on_path.y() - text_actual_rect.height() - 10, # Positioned above path
                                    text_actual_rect.width() + 20, text_actual_rect.height() + 20) # Add padding
            path_bounds = path_bounds.united(text_render_rect)
        return path_bounds.adjusted(-extra, -extra, extra, extra)

    def shape(self): 
        path_stroker = QPainterPathStroker()
        path_stroker.setWidth(20 + self.pen().widthF()) 
        path_stroker.setCapStyle(Qt.RoundCap); path_stroker.setJoinStyle(Qt.RoundJoin)
        return path_stroker.createStroke(self.path())

    def update_path(self):
        if not self.start_item or not self.end_item:
            self.setPath(QPainterPath())
            return

        start_center = self.start_item.sceneBoundingRect().center()
        end_center = self.end_item.sceneBoundingRect().center()

        line_to_target = QLineF(start_center, end_center)
        start_point = self._get_intersection_point(self.start_item, line_to_target)
        line_from_target = QLineF(end_center, start_center)
        end_point = self._get_intersection_point(self.end_item, line_from_target)

        if start_point is None: start_point = start_center
        if end_point is None: end_point = end_center

        path = QPainterPath(start_point)
        if self.start_item == self.end_item: 
            rect = self.start_item.sceneBoundingRect()
            loop_radius_x = rect.width() * 0.45
            loop_radius_y = rect.height() * 0.55 
            p1 = QPointF(rect.center().x() + rect.width() * 0.2, rect.top()) 
            p2 = QPointF(rect.center().x() - rect.width() * 0.2, rect.top())
            
            ctrl1 = QPointF(p1.x() + loop_radius_x * 0.8, p1.y() - loop_radius_y * 2.2)
            ctrl2 = QPointF(p2.x() - loop_radius_x * 0.8, p2.y() - loop_radius_y * 2.2)

            path.moveTo(p1); path.cubicTo(ctrl1, ctrl2, p2)
            end_point = p2 
        else:
            mid_x = (start_point.x() + end_point.x()) / 2; mid_y = (start_point.y() + end_point.y()) / 2
            dx = end_point.x() - start_point.x(); dy = end_point.y() - start_point.y()
            length = math.hypot(dx, dy)
            if length < 1e-6 : length = 1e-6 
            perp_x = -dy / length; perp_y = dx / length 
            
            ctrl_pt_x = mid_x + perp_x * self.control_point_offset.x() + (dx/length) * self.control_point_offset.y()
            ctrl_pt_y = mid_y + perp_y * self.control_point_offset.x() + (dy/length) * self.control_point_offset.y()
            ctrl_pt = QPointF(ctrl_pt_x, ctrl_pt_y)
            
            if self.control_point_offset.x() == 0 and self.control_point_offset.y() == 0:
                path.lineTo(end_point)
            else:
                path.quadTo(ctrl_pt, end_point)
        self.setPath(path)
        self.prepareGeometryChange()


    def _get_intersection_point(self, item: QGraphicsRectItem, line: QLineF):
        item_rect = item.sceneBoundingRect()
        
        rect_path = QPainterPath()
        border_radius = 12 
        rect_path.addRoundedRect(item_rect, border_radius, border_radius)

        temp_path = QPainterPath(line.p1())
        temp_path.lineTo(line.p2())
        
        intersect_path = rect_path.intersected(temp_path)
        
        if not intersect_path.isEmpty() and intersect_path.elementCount() > 0:
            current_element = intersect_path.elementAt(0)
            intersection_point = QPointF(current_element.x, current_element.y)
            # If line passes through, it might intersect at two points on the boundary.
            # We need the one "closer" to line.p1() in the direction of the line.
            if intersect_path.elementCount() > 1 : # check multiple elements
                points_on_boundary = []
                for i in range(intersect_path.elementCount()):
                    el = intersect_path.elementAt(i)
                    points_on_boundary.append(QPointF(el.x, el.y))
                
                if points_on_boundary:
                    # Find the point on the boundary that line.p1() "sees" first.
                    # This means the point that forms the shortest segment *from* line.p1() *along* the line direction.
                    original_line_vec = line.unitVector()
                    min_proj = float('inf')
                    best_point = None
                    for pt_boundary in points_on_boundary:
                        vec_to_boundary = pt_boundary - line.p1()
                        projection = QPointF.dotProduct(vec_to_boundary, original_line_vec)
                        if projection >= 0 and projection < min_proj: # Point is "ahead" and closer
                             min_proj = projection
                             best_point = pt_boundary
                    if best_point:
                        return best_point

            return intersection_point # Fallback to the first element if logic above doesn't yield a better point

        # Fallback if path intersection is tricky (e.g. line ends inside) - use simple edge check
        edges = [
            QLineF(item_rect.topLeft(), item_rect.topRight()),
            QLineF(item_rect.topRight(), item_rect.bottomRight()),
            QLineF(item_rect.bottomRight(), item_rect.bottomLeft()),
            QLineF(item_rect.bottomLeft(), item_rect.topLeft())
        ]
        intersect_points = []
        for edge in edges:
            intersection_point_var = QPointF()
            intersect_type = line.intersect(edge, intersection_point_var)
            if intersect_type == QLineF.BoundedIntersection:
                 intersect_points.append(QPointF(intersection_point_var))
        
        if not intersect_points: return item_rect.center()
        
        intersect_points.sort(key=lambda pt: QLineF(line.p1(), pt).length())
        return intersect_points[0]


    def paint(self, painter: QPainter, option, widget):
        if not self.start_item or not self.end_item or self.path().isEmpty(): return
        painter.setRenderHint(QPainter.Antialiasing)
        current_pen = self.pen()
        
        if self.isSelected():
            stroker = QPainterPathStroker(); stroker.setWidth(current_pen.widthF() + 8) 
            stroker.setCapStyle(Qt.RoundCap); stroker.setJoinStyle(Qt.RoundJoin)
            selection_path_shape = stroker.createStroke(self.path())
            
            highlight_color = QColor(COLOR_ITEM_TRANSITION_SELECTION)
            highlight_color.setAlpha(150) 
            painter.setPen(QPen(highlight_color, 1, Qt.SolidLine)) 
            painter.setBrush(highlight_color)
            painter.drawPath(selection_path_shape)

        painter.setPen(current_pen); painter.setBrush(Qt.NoBrush)
        painter.drawPath(self.path())
        
        if self.path().elementCount() < 1 : return
        
        line_end_point = self.path().pointAtPercent(1.0)
        
        path_len = self.path().length()
        tangent_point_percent = max(0.0, 1.0 - (self.arrow_size * 1.2 / (path_len + 1e-6))) 
        if path_len < self.arrow_size * 1.5 : # For very short paths, use an earlier point for tangent
            tangent_point_percent = max(0.0, 0.8 if path_len > 0 else 0.0)

        angle_at_end_rad = -self.path().angleAtPercent(tangent_point_percent) * (math.pi / 180.0)

        arrow_p1 = line_end_point + QPointF(math.cos(angle_at_end_rad - math.pi / 7) * self.arrow_size,
                                            math.sin(angle_at_end_rad - math.pi / 7) * self.arrow_size)
        arrow_p2 = line_end_point + QPointF(math.cos(angle_at_end_rad + math.pi / 7) * self.arrow_size,
                                            math.sin(angle_at_end_rad + math.pi / 7) * self.arrow_size)
        painter.setBrush(current_pen.color())
        painter.drawPolygon(QPolygonF([line_end_point, arrow_p1, arrow_p2]))
        
        current_label = self._compose_label_string()
        if current_label:
            from PyQt5.QtGui import QFontMetrics
            painter.setFont(self._font); fm = QFontMetrics(self._font)
            
            # Define a bounding rect for the text label to wrap
            label_rect_width = 150 # Max width for the label text block
            text_block_rect = QRectF(0, 0, label_rect_width, 100) # Height is generous, boundingRect will calculate actual
            text_rect_original = fm.boundingRect(text_block_rect, Qt.AlignCenter | Qt.TextWordWrap, current_label)
            
            label_path_percent = 0.5
            text_pos_on_path = self.path().pointAtPercent(label_path_percent)
            angle_at_mid_deg = self.path().angleAtPercent(label_path_percent)
            offset_angle_rad = (angle_at_mid_deg - 90.0) * (math.pi / 180.0) 
            
            offset_dist = 12 
            text_center_x = text_pos_on_path.x() + offset_dist * math.cos(offset_angle_rad)
            text_center_y = text_pos_on_path.y() + offset_dist * math.sin(offset_angle_rad)
            
            # Center the calculated text_rect_original at (text_center_x, text_center_y)
            text_final_draw_rect = QRectF(
                text_center_x - text_rect_original.width() / 2,
                text_center_y - text_rect_original.height() / 2,
                text_rect_original.width(),
                text_rect_original.height()
            )
            
            bg_padding = 4 
            bg_rect = text_final_draw_rect.adjusted(-bg_padding, -bg_padding, bg_padding, bg_padding)
            
            label_bg_color = QColor(COLOR_BACKGROUND_DIALOG) 
            label_bg_color.setAlpha(230) # Slightly more opaque
            painter.setBrush(label_bg_color)
            painter.setPen(QPen(QColor(COLOR_BORDER_LIGHT), 0.8)) 
            painter.drawRoundedRect(bg_rect, 4, 4) 
            
            painter.setPen(self._text_color)
            # Draw text within the calculated centered rectangle
            painter.drawText(text_final_draw_rect, Qt.AlignCenter | Qt.TextWordWrap, current_label)

    def get_data(self):
        return {
            'source': self.start_item.text_label if self.start_item else "None",
            'target': self.end_item.text_label if self.end_item else "None",
            'event': self.event_str, 'condition': self.condition_str, 
            'action_language': self.action_language,
            'action': self.action_str,
            'color': self.base_color.name() if self.base_color else QColor(COLOR_ITEM_TRANSITION_DEFAULT).name(),
            'description': self.description,
            'control_offset_x': self.control_point_offset.x(),
            'control_offset_y': self.control_point_offset.y()
        }

    def set_properties(self, event_str="", condition_str="", action_str="",
                       color_hex=None, description="", offset=None, action_language=DEFAULT_EXECUTION_ENV): 
        changed = False
        if self.event_str != event_str: self.event_str = event_str; changed=True
        if self.condition_str != condition_str: self.condition_str = condition_str; changed=True
        if self.action_language != action_language: self.action_language = action_language; changed=True
        if self.action_str != action_str: self.action_str = action_str; changed=True
        if self.description != description: self.description = description; changed=True
        new_color = QColor(color_hex) if color_hex and QColor(color_hex).isValid() else QColor(COLOR_ITEM_TRANSITION_DEFAULT)
        if self.base_color != new_color:
            self.base_color = new_color
            self.setPen(QPen(self.base_color, self._pen_width))
            changed = True
        if offset is not None and self.control_point_offset != offset:
            self.control_point_offset = offset
            changed = True 
        if changed: self.prepareGeometryChange()
        if (offset is not None and changed) or (changed and (self.control_point_offset.x() != 0 or self.control_point_offset.y() != 0)):
            self.update_path()
        self.update() 

    def set_control_point_offset(self, offset: QPointF):
        if self.control_point_offset != offset:
            self.control_point_offset = offset
            self.update_path(); self.update()


class GraphicsCommentItem(QGraphicsTextItem):
    Type = QGraphicsItem.UserType + 3
    def type(self): return GraphicsCommentItem.Type

    def __init__(self, x, y, text="Comment"):
        super().__init__()
        self.setPlainText(text); self.setPos(x, y)
        self.setFont(QFont(APP_FONT_FAMILY, 9, QFont.StyleItalic)) 
        self.setTextInteractionFlags(Qt.TextEditorInteraction)
        self.setFlags(QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsMovable |
                      QGraphicsItem.ItemSendsGeometryChanges | QGraphicsItem.ItemIsFocusable)
        self._default_width = 160; self.setTextWidth(self._default_width) 
        self.border_pen = QPen(QColor(COLOR_ITEM_COMMENT_BORDER), 1.2) 
        self.background_brush = QBrush(QColor(COLOR_ITEM_COMMENT_BG))
        self.shadow_effect = QGraphicsDropShadowEffect()
        self.shadow_effect.setBlurRadius(10); self.shadow_effect.setColor(QColor(0, 0, 0, 40))
        self.shadow_effect.setOffset(2.5, 2.5); self.setGraphicsEffect(self.shadow_effect)
        
        self.setDefaultTextColor(QColor(COLOR_TEXT_PRIMARY).darker(110)) 

        if self.document(): self.document().contentsChanged.connect(self._on_contents_changed)

    def _on_contents_changed(self):
        self.prepareGeometryChange()
        if self.scene(): self.scene().item_moved.emit(self)

    def paint(self, painter, option, widget):
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(self.border_pen); painter.setBrush(self.background_brush)
        rect = self.boundingRect()
        painter.drawRoundedRect(rect.adjusted(0.5,0.5,-0.5,-0.5), 5, 5) 
        
        super().paint(painter, option, widget) 

        if self.isSelected():
            selection_pen = QPen(QColor(COLOR_ACCENT_PRIMARY), 1.8, Qt.DashLine) 
            painter.setPen(selection_pen); painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(self.boundingRect().adjusted(-1,-1,1,1), 6, 6) 

    def get_data(self):
        doc_width = self.document().idealWidth() if self.textWidth() < 0 else self.textWidth()
        return {'text': self.toPlainText(), 'x': self.x(), 'y': self.y(), 'width': doc_width}

    def set_properties(self, text, width=None):
        current_text = self.toPlainText(); text_changed = (current_text != text)
        width_changed = False
        current_text_width = self.textWidth()
        target_width = width if width and width > 0 else self._default_width
        if current_text_width != target_width: width_changed = True
        if text_changed: self.setPlainText(text)
        if width_changed: self.setTextWidth(target_width)
        if text_changed or width_changed : 
            self.prepareGeometryChange() 
            self.update()

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged and self.scene():
            self.scene().item_moved.emit(self)
        return super().itemChange(change, value)
