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
            
            # Simple "stack" icon: three horizontal lines
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
        self.arrow_size = 11 # Slightly larger arrow

        self._text_color = QColor(COLOR_TEXT_PRIMARY)
        self._font = QFont(APP_FONT_FAMILY, 8, QFont.Medium) # Medium weight for transition labels
        self.control_point_offset = QPointF(0,0)
        self._pen_width = 2.2 # Slightly thicker transitions

        self.setPen(QPen(self.base_color, self._pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsFocusable, True)
        self.setZValue(-1) # Keep transitions below states
        self.setAcceptHoverEvents(True)

        self.shadow_effect = QGraphicsDropShadowEffect() # Shadow for transitions
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
            # Limit displayed action length for brevity on diagram
            action_display = self.action_str.split('\n')[0] # First line only
            if len(action_display) > 20: action_display = action_display[:17] + "..."
            parts.append(f"/{{{action_display}}}")
        return " ".join(parts)

    def hoverEnterEvent(self, event: QGraphicsSceneMouseEvent):
        self.setPen(QPen(self.base_color.lighter(130), self._pen_width + 0.8)) # More pronounced hover
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event: QGraphicsSceneMouseEvent):
        self.setPen(QPen(self.base_color, self._pen_width))
        super().hoverLeaveEvent(event)

    def boundingRect(self):
        extra = (self.pen().widthF() + self.arrow_size) / 2.0 + 30 # Increased extra for text
        path_bounds = self.path().boundingRect()
        current_label = self._compose_label_string()
        if current_label:
            from PyQt5.QtGui import QFontMetrics
            fm = QFontMetrics(self._font)
            text_rect = fm.boundingRect(QRectF(0,0, 300, 100), Qt.TextWordWrap, current_label) # Assume max width for calc
            
            mid_point_on_path = self.path().pointAtPercent(0.5)
            text_render_rect = QRectF(mid_point_on_path.x() - text_rect.width()/2 - 10,
                                    mid_point_on_path.y() - text_rect.height()/2 - 10,
                                    text_rect.width() + 20, text_rect.height() + 20)
            path_bounds = path_bounds.united(text_render_rect)
        return path_bounds.adjusted(-extra, -extra, extra, extra)

    def shape(self): # Make shape slightly wider for easier selection
        path_stroker = QPainterPathStroker()
        path_stroker.setWidth(20 + self.pen().widthF()) # Increased width for hit testing
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
        if self.start_item == self.end_item: # Self-loop
            rect = self.start_item.sceneBoundingRect()
            # Control points for a nice circular loop above the state
            loop_radius_x = rect.width() * 0.45
            loop_radius_y = rect.height() * 0.55 
            # Adjusted points for a tighter loop starting/ending closer to top-middle
            p1 = QPointF(rect.center().x() + rect.width() * 0.2, rect.top()) 
            p2 = QPointF(rect.center().x() - rect.width() * 0.2, rect.top())
            
            ctrl1 = QPointF(p1.x() + loop_radius_x * 0.8, p1.y() - loop_radius_y * 2.2)
            ctrl2 = QPointF(p2.x() - loop_radius_x * 0.8, p2.y() - loop_radius_y * 2.2)

            path.moveTo(p1); path.cubicTo(ctrl1, ctrl2, p2)
            end_point = p2 # Target for arrowhead
        else:
            mid_x = (start_point.x() + end_point.x()) / 2; mid_y = (start_point.y() + end_point.y()) / 2
            dx = end_point.x() - start_point.x(); dy = end_point.y() - start_point.y()
            length = math.hypot(dx, dy)
            if length < 1e-6 : length = 1e-6 # Avoid division by zero
            perp_x = -dy / length; perp_y = dx / length # Perpendicular vector
            
            # Control point uses both offsets for more flexible curves
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
        
        # Calculate intersection with rounded rect path for accuracy
        # This is more complex but better for rounded corners
        rect_path = QPainterPath()
        border_radius = 12 # Assuming same radius as state item paint
        rect_path.addRoundedRect(item_rect, border_radius, border_radius)

        temp_path = QPainterPath(line.p1())
        temp_path.lineTo(line.p2())
        
        intersect_path = rect_path.intersected(temp_path)
        
        # If multiple intersection points, choose the one closest to line.p1()
        # The intersection path might be a line segment if the line passes through.
        # We need to find the point on this segment closest to the other state.
        
        if not intersect_path.isEmpty() and intersect_path.elementCount() > 0:
            # A simple way: check line segment ends of the intersection path.
            # If it's a simple line intersection, it might have 2 points.
            # We are interested in the point on the item's boundary that the line hits.
            
            # Heuristic: Iterate through a few points on the item_rect border
            # and find the one closest to line.p2() (target of the arrow)
            # This is simpler than full path intersection math for now.
            possible_points = []
            center = item_rect.center()
            for i in range(8): # Check 8 points around the rect (corners and midpoints)
                angle_rad = i * math.pi / 4
                test_line = QLineF(center, line.p2()) # Line from center towards other state
                test_line.setLength(max(item_rect.width(), item_rect.height())) # Extend beyond item

                # Get intersection with the actual item's boundary
                edges = [
                    QLineF(item_rect.topLeft(), item_rect.topRight()), QLineF(item_rect.topRight(), item_rect.bottomRight()),
                    QLineF(item_rect.bottomRight(), item_rect.bottomLeft()), QLineF(item_rect.bottomLeft(), item_rect.topLeft())
                ]
                for edge in edges:
                    intersection_point_var = QPointF()
                    intersect_type = test_line.intersect(edge, intersection_point_var)
                    if intersect_type == QLineF.BoundedIntersection:
                         possible_points.append(QPointF(intersection_point_var))
            
            if not possible_points: return item_rect.center() # Fallback
            
            # Find point on item's edge that forms the shortest line segment to line.p1()
            # when traveling along the original 'line'
            main_line_vec = line.unitVector()
            item_center_proj_onto_line = QPointF.dotProduct(item_rect.center() - line.p1(), main_line_vec)
            
            best_point = item_rect.center()
            min_dist_to_line_start = float('inf')
            
            for x_off in [-item_rect.width()/2, 0, item_rect.width()/2]:
                for y_off in [-item_rect.height()/2, 0, item_rect.height()/2]:
                    if x_off == 0 and y_off == 0: continue # skip center

                    edge_point = item_rect.center() + QPointF(x_off, y_off)
                    
                    # Ensure the point is reasonably on the original line's direction
                    vec_to_edge_point = edge_point - line.p1()
                    if QPointF.dotProduct(vec_to_edge_point, main_line_vec) < 0: # Point is "behind" line start
                        continue

                    dist_sq = QLineF(line.p1(), edge_point).length()
                    
                    # Refine point to be on boundary if using simplified check
                    p_list = []
                    for i in range(4): # Test against 4 straight edges of the bounding box
                        p = QPointF()
                        edge = [QLineF(item_rect.topLeft(), item_rect.topRight()), 
                                QLineF(item_rect.topRight(), item_rect.bottomRight()),
                                QLineF(item_rect.bottomRight(), item_rect.bottomLeft()),
                                QLineF(item_rect.bottomLeft(), item_rect.topLeft())][i]
                        if line.intersect(edge, p) == QLineF.BoundedIntersection:
                            p_list.append(p)
                    
                    if p_list:
                        p_list.sort(key=lambda pt: QLineF(line.p1(), pt).length())
                        refined_edge_point = p_list[0]
                        dist_sq = QLineF(line.p1(), refined_edge_point).length()
                        if dist_sq < min_dist_to_line_start:
                            min_dist_to_line_start = dist_sq
                            best_point = refined_edge_point

            return best_point

        return item_rect.center() # Fallback


    def paint(self, painter: QPainter, option, widget):
        if not self.start_item or not self.end_item or self.path().isEmpty(): return
        painter.setRenderHint(QPainter.Antialiasing)
        current_pen = self.pen()
        
        # Selection highlight
        if self.isSelected():
            stroker = QPainterPathStroker(); stroker.setWidth(current_pen.widthF() + 8) # Wider highlight
            stroker.setCapStyle(Qt.RoundCap); stroker.setJoinStyle(Qt.RoundJoin)
            selection_path_shape = stroker.createStroke(self.path())
            
            highlight_color = QColor(COLOR_ITEM_TRANSITION_SELECTION)
            highlight_color.setAlpha(150) # Make it semi-transparent
            painter.setPen(QPen(highlight_color, 1, Qt.SolidLine)) # Thin border for highlight
            painter.setBrush(highlight_color)
            painter.drawPath(selection_path_shape)

        painter.setPen(current_pen); painter.setBrush(Qt.NoBrush)
        painter.drawPath(self.path())
        
        if self.path().elementCount() < 1 : return
        percent_at_end = 0.99 if self.path().length() > 1 else 0.9
        
        #Arrowhead calculation
        line_end_point = self.path().pointAtPercent(1.0)
        # Ensure path has enough length to get a valid angle
        tangent_point_percent = max(0, 1.0 - (self.arrow_size * 1.5) / (self.path().length() + 1e-6) ) # Go back a bit for tangent
        
        angle_at_end_rad = -self.path().angleAtPercent(tangent_point_percent) * (math.pi / 180.0)

        arrow_p1 = line_end_point + QPointF(math.cos(angle_at_end_rad - math.pi / 7) * self.arrow_size,
                                            math.sin(angle_at_end_rad - math.pi / 7) * self.arrow_size)
        arrow_p2 = line_end_point + QPointF(math.cos(angle_at_end_rad + math.pi / 7) * self.arrow_size,
                                            math.sin(angle_at_end_rad + math.pi / 7) * self.arrow_size)
        painter.setBrush(current_pen.color())
        painter.drawPolygon(QPolygonF([line_end_point, arrow_p1, arrow_p2]))
        
        # Label drawing
        current_label = self._compose_label_string()
        if current_label:
            from PyQt5.QtGui import QFontMetrics
            painter.setFont(self._font); fm = QFontMetrics(self._font)
            text_rect_original = fm.boundingRect(QRectF(0, 0, 300, 100), Qt.AlignCenter | Qt.TextWordWrap, current_label) # Max width 300px for label
            
            # Position label slightly off the curve
            label_path_percent = 0.5
            text_pos_on_path = self.path().pointAtPercent(label_path_percent)
            angle_at_mid_deg = self.path().angleAtPercent(label_path_percent)
            offset_angle_rad = (angle_at_mid_deg - 90.0) * (math.pi / 180.0) # Perpendicular upwards
            
            offset_dist = 12 # Distance from curve
            text_center_x = text_pos_on_path.x() + offset_dist * math.cos(offset_angle_rad)
            text_center_y = text_pos_on_path.y() + offset_dist * math.sin(offset_angle_rad)
            
            text_final_pos = QPointF(text_center_x - text_rect_original.width() / 2,
                                     text_center_y - text_rect_original.height() / 2)
            
            # Background for label
            bg_padding = 4 # More padding
            bg_rect = QRectF(text_final_pos.x() - bg_padding, text_final_pos.y() - bg_padding,
                             text_rect_original.width() + 2 * bg_padding, text_rect_original.height() + 2 * bg_padding)
            
            label_bg_color = QColor(COLOR_BACKGROUND_DIALOG) # White background for labels
            label_bg_color.setAlpha(220) # Slightly transparent
            painter.setBrush(label_bg_color)
            painter.setPen(QPen(QColor(COLOR_BORDER_LIGHT), 0.8)) # Subtle border for label bg
            painter.drawRoundedRect(bg_rect, 4, 4) # Rounded background
            
            painter.setPen(self._text_color)
            painter.drawText(text_final_pos - QPointF(0,0), current_label) # Draw text in bounding rect centered

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
        # Always update path if offset might have changed or if it's curved.
        # If not curved, update_path might still be needed if connected items moved etc.
        # Here, explicitly update path if offset changed or any other property made it 'changed'.
        if (offset is not None and changed) or (changed and (self.control_point_offset.x() != 0 or self.control_point_offset.y() != 0)):
            self.update_path()
        self.update() # General update for text label changes etc.

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
        self.setFont(QFont(APP_FONT_FAMILY, 9, QFont.StyleItalic)) # Italic comments
        self.setTextInteractionFlags(Qt.TextEditorInteraction)
        self.setFlags(QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsMovable |
                      QGraphicsItem.ItemSendsGeometryChanges | QGraphicsItem.ItemIsFocusable)
        self._default_width = 160; self.setTextWidth(self._default_width) # Slightly wider
        self.border_pen = QPen(QColor(COLOR_ITEM_COMMENT_BORDER), 1.2) # Thicker border
        self.background_brush = QBrush(QColor(COLOR_ITEM_COMMENT_BG))
        self.shadow_effect = QGraphicsDropShadowEffect()
        self.shadow_effect.setBlurRadius(10); self.shadow_effect.setColor(QColor(0, 0, 0, 40))
        self.shadow_effect.setOffset(2.5, 2.5); self.setGraphicsEffect(self.shadow_effect)
        
        self.setDefaultTextColor(QColor(COLOR_TEXT_PRIMARY).darker(110)) # Darker text for comments

        if self.document(): self.document().contentsChanged.connect(self._on_contents_changed)

    def _on_contents_changed(self):
        self.prepareGeometryChange()
        if self.scene(): self.scene().item_moved.emit(self)

    def paint(self, painter, option, widget):
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(self.border_pen); painter.setBrush(self.background_brush)
        rect = self.boundingRect()
        painter.drawRoundedRect(rect.adjusted(0.5,0.5,-0.5,-0.5), 5, 5) # More rounded
        
        super().paint(painter, option, widget) # Let QGraphicsTextItem draw the text

        if self.isSelected():
            selection_pen = QPen(QColor(COLOR_ACCENT_PRIMARY), 1.8, Qt.DashLine) # Thicker dash
            painter.setPen(selection_pen); painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(self.boundingRect().adjusted(-1,-1,1,1), 6, 6) # Match rounding

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
            self.prepareGeometryChange() # Important for bounding rect changes
            self.update()

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged and self.scene():
            self.scene().item_moved.emit(self)
        return super().itemChange(change, value)