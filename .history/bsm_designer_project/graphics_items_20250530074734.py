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

        # Superstate icon
        if self.is_superstate:
            icon_w, icon_h = 12, 10 # Smaller, more compact icon
            margin = 7
            # Position in bottom-right corner
            base_x = current_rect.right() - icon_w - margin
            base_y = current_rect.bottom() - icon_h - margin
            
            pen_color = self.border_color.darker(150)
            # If base_color is very dark, make icon lines lighter for contrast
            if self.base_color.lightnessF() < 0.3:
                pen_color = self.border_color.lighter(150)
                if pen_color == self.border_color: # Ensure it actually got lighter
                    pen_color = QColor(Qt.white) if self.base_color.lightnessF() < 0.1 else QColor(Qt.lightGray)

            painter.setPen(QPen(pen_color, 1.2))
            painter.setBrush(Qt.NoBrush)
            
            # Draw a small stack of rectangles
            rect1 = QRectF(base_x, base_y, icon_w, icon_h * 0.6)
            rect2 = QRectF(base_x + icon_w * 0.2, base_y + icon_h * 0.3, icon_w * 0.8, icon_h * 0.7)
            painter.drawRect(rect2) # Draw back rectangle first
            painter.drawRect(rect1) # Draw front rectangle


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

    CONTROL_POINT_SIZE = 8 # Diameter of the control point handle

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
        self.control_point_offset = QPointF(0,0) # Offset relative to the midpoint of start->end line, perpendicular and tangential
        self._pen_width = 2.2 

        self.setPen(QPen(self.base_color, self._pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsFocusable, True) # Allow focus for keyboard interaction if needed
        self.setZValue(-1) 
        self.setAcceptHoverEvents(True)

        self.shadow_effect = QGraphicsDropShadowEffect() 
        self.shadow_effect.setBlurRadius(8)
        self.shadow_effect.setColor(QColor(0, 0, 0, 50))
        self.shadow_effect.setOffset(1.5, 1.5)
        self.setGraphicsEffect(self.shadow_effect)

        self._dragging_control_point = False
        self._last_mouse_press_pos_for_cp_drag = QPointF()
        self._initial_cp_offset_on_drag_start = QPointF()

        self.update_path()

    def _get_actual_control_point_scene_pos(self) -> QPointF:
        """Calculates the scene position of the Bezier control point."""
        if not self.start_item or not self.end_item:
            return QPointF() # Should not happen if items are valid

        start_point = self._get_intersection_point(self.start_item, QLineF(self.start_item.sceneBoundingRect().center(), self.end_item.sceneBoundingRect().center()))
        end_point = self._get_intersection_point(self.end_item, QLineF(self.end_item.sceneBoundingRect().center(), self.start_item.sceneBoundingRect().center()))
        if start_point is None or end_point is None: return QPointF()


        if self.start_item == self.end_item: # Self-loop
            rect = self.start_item.sceneBoundingRect()
            # Estimate based on existing self-loop drawing logic, adjust as needed
            # This is a simplified representation; a more accurate one would mirror the cubicTo points.
            # For simplicity, let's place it above the top-center of the state for now.
            # Or, could use the actual control points if they are easily accessible from path.
            # A better approach for self-loops might be to have two control points or a different manipulation.
            # For now, we use the same `control_point_offset` logic, but its interpretation for self-loops needs care.
            # Let's use the midpoint of the cubic bezier's control points.
            p1 = QPointF(rect.center().x() + rect.width() * 0.2, rect.top())
            loop_radius_x = rect.width() * 0.45
            loop_radius_y = rect.height() * 0.55
            ctrl1_x_offset_from_p1 = loop_radius_x * 0.8
            ctrl1_y_offset_from_p1 = -loop_radius_y * 2.2
            
            # Apply the self.control_point_offset to this calculated ctrl1
            # This is a bit arbitrary how it's applied to a self-loop's existing curve structure.
            # It will shift the 'main' control point of the loop.
            return QPointF(p1.x() + ctrl1_x_offset_from_p1 + self.control_point_offset.x(),
                           p1.y() + ctrl1_y_offset_from_p1 + self.control_point_offset.y())

        mid_x = (start_point.x() + end_point.x()) / 2
        mid_y = (start_point.y() + end_point.y()) / 2
        dx = end_point.x() - start_point.x()
        dy = end_point.y() - start_point.y()
        length = math.hypot(dx, dy)
        if length < 1e-6 : length = 1e-6
        
        # Normalized vector perpendicular to the line (start_point -> end_point)
        perp_x = -dy / length 
        perp_y = dx / length
        
        # Actual control point calculation
        # self.control_point_offset.x() is perpendicular offset
        # self.control_point_offset.y() is tangential offset (along the line start->end)
        ctrl_pt_x = mid_x + perp_x * self.control_point_offset.x() + (dx/length) * self.control_point_offset.y()
        ctrl_pt_y = mid_y + perp_y * self.control_point_offset.x() + (dy/length) * self.control_point_offset.y()
        
        return QPointF(ctrl_pt_x, ctrl_pt_y)
        
    def _get_control_point_rect(self) -> QRectF:
        """Returns the bounding rectangle of the control point handle in scene coordinates."""
        if self.control_point_offset.x() == 0 and self.control_point_offset.y() == 0 and self.start_item != self.end_item:
            # If no offset, there's effectively no visible draggable quadratic control point (it's a straight line)
            # However, we might want to allow dragging it *from* the midpoint initially.
            # For now, if no offset, don't draw/interact with a distinct quadratic CP.
            # Let's draw it slightly offset from the line if selected, to make it grabbable.
            if self.isSelected():
                cp_pos = self.path().pointAtPercent(0.5) + QPointF(0, -self.CONTROL_POINT_SIZE) # Slightly above midpoint
                return QRectF(cp_pos.x() - self.CONTROL_POINT_SIZE / 2,
                              cp_pos.y() - self.CONTROL_POINT_SIZE / 2,
                              self.CONTROL_POINT_SIZE, self.CONTROL_POINT_SIZE)
            return QRectF() # Empty if not selected and no offset


        cp_pos = self._get_actual_control_point_scene_pos()
        return QRectF(cp_pos.x() - self.CONTROL_POINT_SIZE / 2, 
                      cp_pos.y() - self.CONTROL_POINT_SIZE / 2,
                      self.CONTROL_POINT_SIZE, self.CONTROL_POINT_SIZE)


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
            text_bounding_rect_for_calculation = QRectF(0,0, 300, 100) 
            text_actual_rect = fm.boundingRect(text_bounding_rect_for_calculation.toRect(), Qt.TextWordWrap | Qt.AlignCenter, current_label) 
            
            mid_point_on_path = self.path().pointAtPercent(0.5)
            text_render_rect = QRectF(mid_point_on_path.x() - text_actual_rect.width()/2 - 10, 
                                    mid_point_on_path.y() - text_actual_rect.height() - 10, 
                                    text_actual_rect.width() + 20, text_actual_rect.height() + 20) 
            path_bounds = path_bounds.united(text_render_rect)
        
        # Include control point rect in bounding rect if visible
        if self.isSelected() and (self.control_point_offset.x() != 0 or self.control_point_offset.y() != 0 or self.start_item == self.end_item):
            cp_rect = self._get_control_point_rect()
            if not cp_rect.isEmpty():
                path_bounds = path_bounds.united(cp_rect)
                
        return path_bounds.adjusted(-extra, -extra, extra, extra)

    def shape(self): 
        path_stroker = QPainterPathStroker()
        path_stroker.setWidth(20 + self.pen().widthF()) 
        path_stroker.setCapStyle(Qt.RoundCap); path_stroker.setJoinStyle(Qt.RoundJoin)
        base_shape = path_stroker.createStroke(self.path())
        
        # Add control point to shape if it's visible and draggable
        if self.isSelected() and (self.control_point_offset.x() != 0 or self.control_point_offset.y() != 0 or self.start_item == self.end_item):
            cp_rect = self._get_control_point_rect()
            if not cp_rect.isEmpty():
                cp_path = QPainterPath()
                cp_path.addEllipse(cp_rect)
                base_shape.addPath(cp_path) # Union the control point's shape
        return base_shape

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
            p1_scene = QPointF(rect.center().x() + rect.width() * 0.2, rect.top()) 
            p2_scene = QPointF(rect.center().x() - rect.width() * 0.2, rect.top())
            
            # Base control points for the loop's curve (aesthetic choice)
            base_ctrl1_x = p1_scene.x() + loop_radius_x * 0.8
            base_ctrl1_y = p1_scene.y() - loop_radius_y * 2.2
            base_ctrl2_x = p2_scene.x() - loop_radius_x * 0.8
            base_ctrl2_y = p2_scene.y() - loop_radius_y * 2.2

            # Apply user's offset to these base control points
            # This interpretation might need refinement for very intuitive control.
            # One way is to consider self.control_point_offset to adjust the "peak" of the loop.
            # Let's assume control_point_offset shifts the midpoint of the two bezier control points.
            ctrl_mid_x = (base_ctrl1_x + base_ctrl2_x) / 2 + self.control_point_offset.x()
            ctrl_mid_y = (base_ctrl1_y + base_ctrl2_y) / 2 + self.control_point_offset.y()
            
            # Maintain relative positions of ctrl1 and ctrl2 from this new midpoint
            half_dx_ctrl = (base_ctrl1_x - base_ctrl2_x) / 2
            half_dy_ctrl = (base_ctrl1_y - base_ctrl2_y) / 2
            
            final_ctrl1 = QPointF(ctrl_mid_x + half_dx_ctrl, ctrl_mid_y + half_dy_ctrl)
            final_ctrl2 = QPointF(ctrl_mid_x - half_dx_ctrl, ctrl_mid_y - half_dy_ctrl)

            path.moveTo(p1_scene); path.cubicTo(final_ctrl1, final_ctrl2, p2_scene)
            end_point = p2_scene # Update end_point for arrow calculation for self-loops
        else:
            # For non-self-loops, use the _get_actual_control_point_scene_pos to find the quadTo point
            if self.control_point_offset.x() == 0 and self.control_point_offset.y() == 0:
                path.lineTo(end_point)
            else:
                ctrl_pt_scene = self._get_actual_control_point_scene_pos()
                path.quadTo(ctrl_pt_scene, end_point)
        
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
            if intersect_path.elementCount() > 1 : 
                points_on_boundary = []
                for i in range(intersect_path.elementCount()):
                    el = intersect_path.elementAt(i)
                    points_on_boundary.append(QPointF(el.x, el.y))
                
                if points_on_boundary:
                    original_line_vec = line.unitVector()
                    min_proj = float('inf')
                    best_point = None
                    for pt_boundary in points_on_boundary:
                        vec_to_boundary = pt_boundary - line.p1()
                        projection = QPointF.dotProduct(vec_to_boundary, original_line_vec)
                        if projection >= 0 and projection < min_proj: 
                             min_proj = projection
                             best_point = pt_boundary
                    if best_point:
                        return best_point
            return intersection_point 

        edges = [
            QLineF(item_rect.topLeft(), item_rect.topRight()),
            QLineF(item_rect.topRight(), item_rect.bottomRight()),
            QLineF(item_rect.bottomRight(), item_rect.bottomLeft()),
            QLineF(item_rect.bottomLeft(), item_rect.topLeft())
        ]
        intersect_points = []
        for edge in edges:
            intersection_point_var = QPointF()
            intersect_type = line.intersect(edge, intersection_point_var) # Old API for Qt < 5.10
            # For Qt >= 5.10, use: intersect_type, intersection_point_var = line.intersects(edge)
            if intersect_type == QLineF.BoundedIntersection: # For older API
            # if intersect_type == QLineF.IntersectionType.BoundedIntersection: # For newer API
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

            # Draw control point handle if selected and it's not a straight line
            if (self.control_point_offset.x() != 0 or self.control_point_offset.y() != 0 or self.start_item == self.end_item):
                cp_rect = self._get_control_point_rect()
                if not cp_rect.isEmpty():
                    painter.setPen(QPen(QColor(COLOR_ACCENT_PRIMARY), 1.5))
                    fill_color = QColor(COLOR_ACCENT_PRIMARY_LIGHT)
                    fill_color.setAlpha(200)
                    painter.setBrush(fill_color)
                    painter.drawEllipse(cp_rect)


        painter.setPen(current_pen); painter.setBrush(Qt.NoBrush)
        painter.drawPath(self.path())
        
        if self.path().elementCount() < 1 : return
        
        line_end_point = self.path().pointAtPercent(1.0)
        
        path_len = self.path().length()
        tangent_point_percent = max(0.0, 1.0 - (self.arrow_size * 1.2 / (path_len + 1e-6))) 
        if path_len < self.arrow_size * 1.5 : 
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
            
            label_rect_width = 150 
            text_block_rect = QRectF(0, 0, label_rect_width, 100) 
            text_rect_original = fm.boundingRect(text_block_rect.toRect(), Qt.AlignCenter | Qt.TextWordWrap, current_label)
            
            label_path_percent = 0.5
            text_pos_on_path = self.path().pointAtPercent(label_path_percent)
            angle_at_mid_deg = self.path().angleAtPercent(label_path_percent)
            offset_angle_rad = (angle_at_mid_deg - 90.0) * (math.pi / 180.0) 
            
            offset_dist = 12 
            text_center_x = text_pos_on_path.x() + offset_dist * math.cos(offset_angle_rad)
            text_center_y = text_pos_on_path.y() + offset_dist * math.sin(offset_angle_rad)
            
            text_final_draw_rect = QRectF(
                text_center_x - text_rect_original.width() / 2,
                text_center_y - text_rect_original.height() / 2,
                text_rect_original.width(),
                text_rect_original.height()
            )
            
            bg_padding = 4 
            bg_rect = text_final_draw_rect.adjusted(-bg_padding, -bg_padding, bg_padding, bg_padding)
            
            label_bg_color = QColor(COLOR_BACKGROUND_DIALOG) 
            label_bg_color.setAlpha(230) 
            painter.setBrush(label_bg_color)
            painter.setPen(QPen(QColor(COLOR_BORDER_LIGHT), 0.8)) 
            painter.drawRoundedRect(bg_rect, 4, 4) 
            
            painter.setPen(self._text_color)
            painter.drawText(text_final_draw_rect, Qt.AlignCenter | Qt.TextWordWrap, current_label)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        if self.isSelected() and event.button() == Qt.LeftButton:
            cp_rect = self._get_control_point_rect()
            if not cp_rect.isEmpty() and cp_rect.contains(event.scenePos()):
                self._dragging_control_point = True
                self._last_mouse_press_pos_for_cp_drag = event.scenePos()
                # Store the initial offset at the start of the drag
                self._initial_cp_offset_on_drag_start = QPointF(self.control_point_offset)
                self.setCursor(Qt.ClosedHandCursor)
                event.accept()
                return
        self._dragging_control_point = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent):
        if self._dragging_control_point:
            if not self.start_item or not self.end_item:
                self._dragging_control_point = False
                self.setCursor(Qt.ArrowCursor) # Or open hand if applicable
                return

            delta_scene = event.scenePos() - self._last_mouse_press_pos_for_cp_drag
            
            # For self-loops, the interpretation of delta needs to be relative to the loop's geometry.
            # A simple delta might not be intuitive. Let's make it simpler: delta directly applies to offset.
            if self.start_item == self.end_item:
                new_offset_x = self._initial_cp_offset_on_drag_start.x() + delta_scene.x()
                new_offset_y = self._initial_cp_offset_on_drag_start.y() + delta_scene.y()
            else: # For non-self-loops
                # Transform delta_scene (which is in scene coordinates) to the transition's local coordinate system
                # where X is perpendicular to the start-end line and Y is tangential.
                start_point_center = self.start_item.sceneBoundingRect().center()
                end_point_center = self.end_item.sceneBoundingRect().center()

                line_vec = end_point_center - start_point_center
                line_len = math.hypot(line_vec.x(), line_vec.y())
                if line_len < 1e-6: line_len = 1e-6

                # Tangential direction (along the line start->end)
                tangent_dir = line_vec / line_len
                # Perpendicular direction (90 deg counter-clockwise from tangent)
                perp_dir = QPointF(-tangent_dir.y(), tangent_dir.x())

                # Project delta_scene onto these basis vectors
                delta_perp = QPointF.dotProduct(delta_scene, perp_dir)
                delta_tang = QPointF.dotProduct(delta_scene, tangent_dir)

                new_offset_x = self._initial_cp_offset_on_drag_start.x() + delta_perp
                new_offset_y = self._initial_cp_offset_on_drag_start.y() + delta_tang

            self.set_control_point_offset(QPointF(new_offset_x, new_offset_y)) # This calls update_path and update
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent):
        if self._dragging_control_point and event.button() == Qt.LeftButton:
            self._dragging_control_point = False
            self.setCursor(Qt.ArrowCursor) # Or open hand if hover is active

            # Create Undo Command
            if self.scene() and hasattr(self.scene(), 'undo_stack'):
                from undo_commands import EditItemPropertiesCommand # Local import
                old_props = self.get_data()
                # Modify old_props to reflect state before drag
                old_props['control_offset_x'] = self._initial_cp_offset_on_drag_start.x()
                old_props['control_offset_y'] = self._initial_cp_offset_on_drag_start.y()
                
                new_props = self.get_data() # Current props after drag

                if old_props != new_props: # Only push if changed
                    cmd = EditItemPropertiesCommand(self, old_props, new_props, "Modify Transition Curve")
                    self.scene().undo_stack.push(cmd)
                    self.scene().set_dirty(True)
            event.accept()
            return
        super().mouseReleaseEvent(event)


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
            self.control_point_offset = QPointF(offset) # Ensure it's QPointF
            changed = True 
        
        if changed: 
            self.prepareGeometryChange() # Important before path/visuals change
            self.update_path() # update_path will also call prepareGeometryChange if path itself changes
            self.update() # Ensure repaint

    def set_control_point_offset(self, offset: QPointF):
        if self.control_point_offset != offset:
            self.control_point_offset = offset
            self.prepareGeometryChange() # Path and thus bounding rect will change
            self.update_path() 
            self.update() # Triggers repaint


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