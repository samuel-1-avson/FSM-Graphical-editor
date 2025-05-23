import math
from PyQt5.QtWidgets import (QGraphicsRectItem, QGraphicsPathItem, QGraphicsTextItem,
                             QGraphicsItem, QGraphicsDropShadowEffect, QApplication, QGraphicsSceneMouseEvent) # Added QGraphicsSceneMouseEvent for type hint
from PyQt5.QtGui import (QBrush, QColor, QFont, QPen, QPainterPath, QPolygonF, QPainter, #Added QPainter
                         QPainterPathStroker, QPixmap, QMouseEvent, QDrag, QPalette) # Added QPixmap, QMouseEvent, QDrag, QPalette
from PyQt5.QtCore import Qt, QRectF, QPointF, QMimeData, QPoint, QLineF, QSize # Added QSize

from config import (COLOR_ITEM_STATE_DEFAULT_BG, COLOR_ITEM_STATE_DEFAULT_BORDER, APP_FONT_FAMILY,
                    COLOR_TEXT_PRIMARY, COLOR_ITEM_STATE_SELECTION, COLOR_ITEM_TRANSITION_DEFAULT,
                    COLOR_ITEM_TRANSITION_SELECTION, COLOR_ITEM_COMMENT_BG, COLOR_ITEM_COMMENT_BORDER,
                    COLOR_PY_SIM_STATE_ACTIVE, COLOR_PY_SIM_STATE_ACTIVE_PEN_WIDTH,
                    COLOR_BACKGROUND_LIGHT, COLOR_BORDER_LIGHT, COLOR_ACCENT_PRIMARY)


class GraphicsStateItem(QGraphicsRectItem):
    Type = QGraphicsItem.UserType + 1 # Custom type identifier

    def type(self): return GraphicsStateItem.Type

    def __init__(self, x, y, w, h, text, is_initial=False, is_final=False,
                 color=None, entry_action="", during_action="", exit_action="", description=""):
        super().__init__(x, y, w, h)
        self.text_label = text
        self.is_initial = is_initial
        self.is_final = is_final

        self.base_color = QColor(color) if color else QColor(COLOR_ITEM_STATE_DEFAULT_BG)
        self.border_color = QColor(color).darker(120) if color else QColor(COLOR_ITEM_STATE_DEFAULT_BORDER)
        self.entry_action = entry_action
        self.during_action = during_action
        self.exit_action = exit_action
        self.description = description

        self._text_color = QColor(COLOR_TEXT_PRIMARY)
        self._font = QFont(APP_FONT_FAMILY, 10, QFont.Bold)
        self._border_pen_width = 1.5

        self.setPen(QPen(self.border_color, self._border_pen_width))
        self.setBrush(QBrush(self.base_color))

        self.setFlags(QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsMovable |
                      QGraphicsItem.ItemSendsGeometryChanges | QGraphicsItem.ItemIsFocusable)
        self.setAcceptHoverEvents(True) # For potential hover effects (not currently used in paint)

        # Shadow effect for better visuals
        self.shadow_effect = QGraphicsDropShadowEffect()
        self.shadow_effect.setBlurRadius(10)
        self.shadow_effect.setColor(QColor(0, 0, 0, 60)) # Semi-transparent black
        self.shadow_effect.setOffset(2.5, 2.5)
        self.setGraphicsEffect(self.shadow_effect)

        # --- FOR PYTHON SIMULATION ---
        self.is_py_sim_active = False
        self.original_pen_for_py_sim_restore = self.pen() # Store the initial pen

    def paint(self, painter: QPainter, option, widget):
        painter.setRenderHint(QPainter.Antialiasing)
        current_rect = self.rect()
        border_radius = 10 # For rounded corners

        current_pen_to_use = self.pen() # Start with current pen (could be original or sim_active)
        # --- MODIFIED FOR PY SIM ---
        if self.is_py_sim_active:
            py_sim_pen = QPen(COLOR_PY_SIM_STATE_ACTIVE, COLOR_PY_SIM_STATE_ACTIVE_PEN_WIDTH, Qt.DashLine)
            # Override with sim pen if active
            current_pen_to_use = py_sim_pen

        painter.setPen(current_pen_to_use) # Use modified or original pen
        painter.setBrush(self.brush()) # Current brush (base_color)
        painter.drawRoundedRect(current_rect, border_radius, border_radius)

        # Draw Text (State Name)
        painter.setPen(self._text_color)
        painter.setFont(self._font)
        text_rect = current_rect.adjusted(8, 8, -8, -8) # Padding for text
        painter.drawText(text_rect, Qt.AlignCenter | Qt.TextWordWrap, self.text_label)

        # Draw Initial State Marker (if applicable)
        if self.is_initial:
            marker_radius = 6
            line_length = 18 # Length of line from marker to state edge
            marker_color = Qt.black

            # Center marker vertically, place to the left of the state
            start_marker_center_x = current_rect.left() - line_length - marker_radius / 2
            start_marker_center_y = current_rect.center().y()

            painter.setBrush(marker_color)
            painter.setPen(QPen(marker_color, self._border_pen_width))
            painter.drawEllipse(QPointF(start_marker_center_x, start_marker_center_y), marker_radius, marker_radius)

            # Line from marker to state
            line_start_point = QPointF(start_marker_center_x + marker_radius, start_marker_center_y)
            line_end_point = QPointF(current_rect.left(), start_marker_center_y)
            painter.drawLine(line_start_point, line_end_point)

            # Arrowhead
            arrow_size = 8
            angle_rad = 0 # Points to the right
            arrow_p1 = QPointF(line_end_point.x() - arrow_size * math.cos(angle_rad + math.pi / 6),
                               line_end_point.y() - arrow_size * math.sin(angle_rad + math.pi / 6))
            arrow_p2 = QPointF(line_end_point.x() - arrow_size * math.cos(angle_rad - math.pi / 6),
                               line_end_point.y() - arrow_size * math.sin(angle_rad - math.pi / 6))
            painter.drawPolygon(QPolygonF([line_end_point, arrow_p1, arrow_p2]))


        # Draw Final State Marker (double border)
        if self.is_final:
            painter.setPen(QPen(self.border_color.darker(120), self._border_pen_width + 0.5))
            inner_rect = current_rect.adjusted(5, 5, -5, -5) # Inset second border
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(inner_rect, border_radius - 3, border_radius - 3)

        # Draw Selection Highlight (if selected and not in active PySim mode)
        if self.isSelected() and not self.is_py_sim_active:
            selection_pen = QPen(QColor(COLOR_ITEM_STATE_SELECTION), self._border_pen_width + 1, Qt.SolidLine)
            # Slightly larger rect for selection outline
            selection_rect = self.boundingRect().adjusted(-1, -1, 1, 1)
            painter.setPen(selection_pen)
            painter.setBrush(Qt.NoBrush) # No fill for selection outline
            painter.drawRoundedRect(selection_rect, border_radius + 1, border_radius + 1)


    def set_py_sim_active_style(self, active: bool):
        if self.is_py_sim_active == active:
            return # No change
        self.is_py_sim_active = active

        if active:
            # Store the current "actual" pen before applying sim style
            # This ensures if properties were changed while sim was off, new style is base
            self.original_pen_for_py_sim_restore = QPen(self.pen())
        else:
            # Restore the pen that was active *before* sim styling was applied
            self.setPen(self.original_pen_for_py_sim_restore)
        self.update() # Trigger repaint

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged and self.scene():
            self.scene().item_moved.emit(self) # Notify scene of movement
        return super().itemChange(change, value)

    def get_data(self):
        return {
            'name': self.text_label, 'x': self.x(), 'y': self.y(),
            'width': self.rect().width(), 'height': self.rect().height(),
            'is_initial': self.is_initial, 'is_final': self.is_final,
            'color': self.base_color.name() if self.base_color else QColor(COLOR_ITEM_STATE_DEFAULT_BG).name(),
            'entry_action': self.entry_action, 'during_action': self.during_action,
            'exit_action': self.exit_action, 'description': self.description
        }

    def set_text(self, text): # Primarily for direct name changes if ever needed outside full props
        if self.text_label != text:
            self.prepareGeometryChange()
            self.text_label = text
            self.update()

    def set_properties(self, name, is_initial, is_final, color_hex=None,
                       entry="", during="", exit_a="", desc=""):
        changed = False
        if self.text_label != name: self.text_label = name; changed = True
        if self.is_initial != is_initial: self.is_initial = is_initial; changed = True
        if self.is_final != is_final: self.is_final = is_final; changed = True

        new_base_color = QColor(color_hex) if color_hex else QColor(COLOR_ITEM_STATE_DEFAULT_BG)
        new_border_color = new_base_color.darker(120) if color_hex else QColor(COLOR_ITEM_STATE_DEFAULT_BORDER)

        if self.base_color != new_base_color:
            self.base_color = new_base_color
            self.border_color = new_border_color
            self.setBrush(self.base_color) # Update visual brush

            new_pen = QPen(self.border_color, self._border_pen_width)
            # If Python sim is NOT active, update both current pen and the backup restore pen.
            # If sim IS active, the current visual pen is the sim highlight; only update backup.
            if not self.is_py_sim_active:
                self.setPen(new_pen)
            self.original_pen_for_py_sim_restore = new_pen # Always update this to the new "true" style
            changed = True

        if self.entry_action != entry: self.entry_action = entry; changed = True
        if self.during_action != during: self.during_action = during; changed = True
        if self.exit_action != exit_a: self.exit_action = exit_a; changed = True
        if self.description != desc: self.description = desc; changed = True

        if changed:
            self.prepareGeometryChange() # If name or visual aspects change bounds
            self.update()

class GraphicsTransitionItem(QGraphicsPathItem):
    Type = QGraphicsItem.UserType + 2
    def type(self): return GraphicsTransitionItem.Type

    def __init__(self, start_item, end_item, event_str="", condition_str="", action_str="",
                 color=None, description=""):
        super().__init__()
        self.start_item: GraphicsStateItem | None = start_item
        self.end_item: GraphicsStateItem | None = end_item
        self.event_str = event_str
        self.condition_str = condition_str
        self.action_str = action_str
        self.base_color = QColor(color) if color else QColor(COLOR_ITEM_TRANSITION_DEFAULT)
        self.description = description
        self.arrow_size = 10

        self._text_color = QColor(COLOR_TEXT_PRIMARY)
        self._font = QFont(APP_FONT_FAMILY, 8) # Smaller font for transition labels
        self.control_point_offset = QPointF(0,0) # For Bezier curve, (perp_offset, tangent_offset)
        self._pen_width = 2.0

        self.setPen(QPen(self.base_color, self._pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsFocusable, True)
        self.setZValue(-1) # Draw behind states by default
        self.setAcceptHoverEvents(True)
        self.update_path()

    def _compose_label_string(self):
        parts = []
        if self.event_str: parts.append(self.event_str)
        if self.condition_str: parts.append(f"[{self.condition_str}]")
        if self.action_str: parts.append(f"/{{{self.action_str}}}") # Stateflow-like action syntax
        return " ".join(parts)

    def hoverEnterEvent(self, event: QGraphicsSceneMouseEvent): # QGraphicsSceneHoverEvent
        self.setPen(QPen(self.base_color.lighter(130), self._pen_width + 0.5))
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event: QGraphicsSceneMouseEvent): # QGraphicsSceneHoverEvent
        self.setPen(QPen(self.base_color, self._pen_width))
        super().hoverLeaveEvent(event)

    def boundingRect(self):
        # Extra padding for pen width, arrow, and text label area
        extra = (self.pen().widthF() + self.arrow_size) / 2.0 + 25 # Generous padding
        path_bounds = self.path().boundingRect()

        # Consider text label for bounding rect calculation
        current_label = self._compose_label_string()
        if current_label:
            from PyQt5.QtGui import QFontMetrics # Moved import to avoid circular dep during early class def
            fm = QFontMetrics(self._font)
            text_rect = fm.boundingRect(current_label)
            mid_point_on_path = self.path().pointAtPercent(0.5)
            # Approximate area where text might be rendered relative to path midpoint
            # This needs to be generous to cover text placement logic in paint()
            text_render_rect = QRectF(mid_point_on_path.x() - text_rect.width() - 10,
                                    mid_point_on_path.y() - text_rect.height() - 10,
                                    text_rect.width()*2 + 20, text_rect.height()*2 + 20)
            path_bounds = path_bounds.united(text_render_rect)

        return path_bounds.adjusted(-extra, -extra, extra, extra)

    def shape(self): # For more accurate hit detection
        path_stroker = QPainterPathStroker()
        path_stroker.setWidth(18 + self.pen().widthF()) # Make clickable area wider than visible line
        path_stroker.setCapStyle(Qt.RoundCap)
        path_stroker.setJoinStyle(Qt.RoundJoin)
        return path_stroker.createStroke(self.path())

    def update_path(self):
        if not self.start_item or not self.end_item:
            self.setPath(QPainterPath()) # Clear path if items are invalid
            return

        start_center = self.start_item.sceneBoundingRect().center()
        end_center = self.end_item.sceneBoundingRect().center()

        # Get intersection points with item boundaries for cleaner connections
        line_to_target = QLineF(start_center, end_center)
        start_point = self._get_intersection_point(self.start_item, line_to_target)

        line_from_target = QLineF(end_center, start_center)
        end_point = self._get_intersection_point(self.end_item, line_from_target)

        # Fallback if intersection fails (e.g., items overlap perfectly)
        if start_point is None: start_point = start_center
        if end_point is None: end_point = end_center

        path = QPainterPath(start_point)

        if self.start_item == self.end_item: # Self-transition (loop)
            rect = self.start_item.sceneBoundingRect()
            loop_radius_x = rect.width() * 0.40
            loop_radius_y = rect.height() * 0.40
            # Define loop points on top edge of state
            p1 = QPointF(rect.center().x() + loop_radius_x * 0.35, rect.top())
            p2 = QPointF(rect.center().x() - loop_radius_x * 0.35, rect.top())
            # Control points for a nice arc above the state
            ctrl1 = QPointF(rect.center().x() + loop_radius_x * 1.6, rect.top() - loop_radius_y * 2.8)
            ctrl2 = QPointF(rect.center().x() - loop_radius_x * 1.6, rect.top() - loop_radius_y * 2.8)
            path.moveTo(p1)
            path.cubicTo(ctrl1, ctrl2, p2)
            end_point = p2 # End point for arrow calculation is one end of loop
        else: # Transition between different states
            mid_x = (start_point.x() + end_point.x()) / 2
            mid_y = (start_point.y() + end_point.y()) / 2
            dx = end_point.x() - start_point.x()
            dy = end_point.y() - start_point.y()
            length = math.hypot(dx, dy)
            if length == 0: length = 1 # Avoid division by zero

            # Normalized perpendicular vector
            perp_x = -dy / length
            perp_y = dx / length

            # Control point calculation based on offset
            ctrl_pt_x = mid_x + perp_x * self.control_point_offset.x() + (dx/length) * self.control_point_offset.y()
            ctrl_pt_y = mid_y + perp_y * self.control_point_offset.x() + (dy/length) * self.control_point_offset.y()
            ctrl_pt = QPointF(ctrl_pt_x, ctrl_pt_y)

            if self.control_point_offset.x() == 0 and self.control_point_offset.y() == 0:
                path.lineTo(end_point) # Straight line
            else:
                path.quadTo(ctrl_pt, end_point) # Quadratic Bezier curve

        self.setPath(path)
        self.prepareGeometryChange() # Notify system of potential bounding rect change

    def _get_intersection_point(self, item: QGraphicsRectItem, line: QLineF):
        item_rect = item.sceneBoundingRect() # Use sceneBoundingRect for global coords
        # Define the four edges of the item's bounding rectangle
        edges = [
            QLineF(item_rect.topLeft(), item_rect.topRight()),
            QLineF(item_rect.topRight(), item_rect.bottomRight()),
            QLineF(item_rect.bottomRight(), item_rect.bottomLeft()),
            QLineF(item_rect.bottomLeft(), item_rect.topLeft())
        ]
        intersect_points = []
        for edge in edges:
            intersection_point_var = QPointF() # QLineF.intersect requires a QPointF reference
            intersect_type = line.intersect(edge, intersection_point_var)

            # Check for bounded intersection (within both line segments)
            if intersect_type == QLineF.BoundedIntersection:
                 # Additional check if intersect_type is UnboundedIntersection sometimes gives points far away
                 # but QLineF's intersect_type=BoundedIntersection should already handle this for the edge segment
                edge_rect_for_check = QRectF(edge.p1(), edge.p2()).normalized()
                epsilon = 1e-3 # Tolerance for floating point comparisons
                if (edge_rect_for_check.left() - epsilon <= intersection_point_var.x() <= edge_rect_for_check.right() + epsilon and
                    edge_rect_for_check.top() - epsilon <= intersection_point_var.y() <= edge_rect_for_check.bottom() + epsilon):
                     intersect_points.append(QPointF(intersection_point_var)) # Create new QPointF instance

        if not intersect_points:
            return item_rect.center() # Fallback: connect to center if no edge intersection found

        # Find the intersection point closest to the line's starting point (p1)
        # This usually gives the most "natural" connection point from the perspective of the line's origin.
        closest_point = intersect_points[0]
        min_dist_sq = (QLineF(line.p1(), closest_point).length())**2 # Squared length for efficiency
        for pt in intersect_points[1:]:
            dist_sq = (QLineF(line.p1(), pt).length())**2
            if dist_sq < min_dist_sq:
                min_dist_sq = dist_sq
                closest_point = pt
        return closest_point


    def paint(self, painter: QPainter, option, widget):
        if not self.start_item or not self.end_item or self.path().isEmpty():
            return

        painter.setRenderHint(QPainter.Antialiasing)
        current_pen = self.pen() # Could be modified by hover state

        if self.isSelected():
            # Draw a wider, different colored path underneath for selection indication
            stroker = QPainterPathStroker()
            stroker.setWidth(current_pen.widthF() + 6) # Selection outline is thicker
            stroker.setCapStyle(Qt.RoundCap)
            stroker.setJoinStyle(Qt.RoundJoin)
            selection_path_shape = stroker.createStroke(self.path())

            painter.setPen(Qt.NoPen) # No border for the selection highlight itself
            painter.setBrush(QColor(COLOR_ITEM_TRANSITION_SELECTION))
            painter.drawPath(selection_path_shape)

        painter.setPen(current_pen)
        painter.setBrush(Qt.NoBrush) # Path itself is not filled
        painter.drawPath(self.path())

        # Draw Arrowhead
        if self.path().elementCount() < 1 : return # Path must exist

        # Ensure pointAtPercent uses a value slightly less than 1 for angle calculation if length is small
        percent_at_end = 0.999
        if self.path().length() < 1 : percent_at_end = 0.9 # Use a smaller percent if path is very short

        line_end_point = self.path().pointAtPercent(1.0) # Arrow tip is exactly at the end
        angle_at_end_rad = -self.path().angleAtPercent(percent_at_end) * (math.pi / 180.0) # Convert to radians, negate for correct visual angle

        # Arrow points
        arrow_p1 = line_end_point + QPointF(math.cos(angle_at_end_rad - math.pi / 7) * self.arrow_size,
                                            math.sin(angle_at_end_rad - math.pi / 7) * self.arrow_size)
        arrow_p2 = line_end_point + QPointF(math.cos(angle_at_end_rad + math.pi / 7) * self.arrow_size,
                                            math.sin(angle_at_end_rad + math.pi / 7) * self.arrow_size)
        painter.setBrush(current_pen.color()) # Fill arrow with line color
        painter.drawPolygon(QPolygonF([line_end_point, arrow_p1, arrow_p2]))

        # Draw Label Text
        current_label = self._compose_label_string()
        if current_label:
            from PyQt5.QtGui import QFontMetrics # Local import
            painter.setFont(self._font)
            fm = QFontMetrics(self._font)
            text_rect_original = fm.boundingRect(current_label)

            text_pos_on_path = self.path().pointAtPercent(0.5) # Position text at path midpoint
            angle_at_mid_deg = self.path().angleAtPercent(0.5)

            # Offset text slightly perpendicular to the path for readability
            offset_angle_rad = (angle_at_mid_deg - 90.0) * (math.pi / 180.0) # 90 deg offset from tangent
            offset_dist = 10 # Pixels to offset
            text_center_x = text_pos_on_path.x() + offset_dist * math.cos(offset_angle_rad)
            text_center_y = text_pos_on_path.y() + offset_dist * math.sin(offset_angle_rad)

            text_final_pos = QPointF(text_center_x - text_rect_original.width() / 2,
                                     text_center_y - text_rect_original.height() / 2)

            # Draw a slightly lighter background under the text
            bg_padding = 2
            bg_rect = QRectF(text_final_pos.x() - bg_padding,
                             text_final_pos.y() - bg_padding,
                             text_rect_original.width() + 2 * bg_padding,
                             text_rect_original.height() + 2 * bg_padding)
            painter.setBrush(QColor(COLOR_BACKGROUND_LIGHT).lighter(102)) # A bit lighter than main background
            painter.setPen(QPen(QColor(COLOR_BORDER_LIGHT), 0.5)) # Faint border for text BG
            painter.drawRoundedRect(bg_rect, 3, 3)

            painter.setPen(self._text_color)
            painter.drawText(text_final_pos, current_label)


    def get_data(self):
        return {
            'source': self.start_item.text_label if self.start_item else "None",
            'target': self.end_item.text_label if self.end_item else "None",
            'event': self.event_str, 'condition': self.condition_str, 'action': self.action_str,
            'color': self.base_color.name() if self.base_color else QColor(COLOR_ITEM_TRANSITION_DEFAULT).name(),
            'description': self.description,
            'control_offset_x': self.control_point_offset.x(), # Bezier curve offset
            'control_offset_y': self.control_point_offset.y()
        }

    def set_properties(self, event_str="", condition_str="", action_str="",
                       color_hex=None, description="", offset=None):
        changed = False
        if self.event_str != event_str: self.event_str = event_str; changed=True
        if self.condition_str != condition_str: self.condition_str = condition_str; changed=True
        if self.action_str != action_str: self.action_str = action_str; changed=True
        if self.description != description: self.description = description; changed=True

        new_color = QColor(color_hex) if color_hex else QColor(COLOR_ITEM_TRANSITION_DEFAULT)
        if self.base_color != new_color:
            self.base_color = new_color
            self.setPen(QPen(self.base_color, self._pen_width)) # Update visual pen
            changed = True

        if offset is not None and self.control_point_offset != offset:
            self.control_point_offset = offset
            changed = True # Path will need update

        if changed:
            self.prepareGeometryChange() # For label or color changes

        if offset is not None : # Specific handling for path geometry if offset changed
            self.update_path() # This also calls prepareGeometryChange and updates

        self.update() # Generic repaint if any visual prop changed

    def set_control_point_offset(self, offset: QPointF): # For direct manipulation of curve
        if self.control_point_offset != offset:
            self.control_point_offset = offset
            self.update_path()
            self.update()


class GraphicsCommentItem(QGraphicsTextItem):
    Type = QGraphicsItem.UserType + 3
    def type(self): return GraphicsCommentItem.Type

    def __init__(self, x, y, text="Comment"):
        super().__init__()
        self.setPlainText(text)
        self.setPos(x, y)
        self.setFont(QFont(APP_FONT_FAMILY, 9))
        self.setTextInteractionFlags(Qt.TextEditorInteraction) # Allow editing text
        self.setFlags(QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsMovable |
                      QGraphicsItem.ItemSendsGeometryChanges | QGraphicsItem.ItemIsFocusable)

        self._default_width = 150 # Default width for new comments
        self.setTextWidth(self._default_width) # Enable word wrap by setting a width

        self.border_pen = QPen(QColor(COLOR_ITEM_COMMENT_BORDER), 1)
        self.background_brush = QBrush(QColor(COLOR_ITEM_COMMENT_BG))

        self.shadow_effect = QGraphicsDropShadowEffect()
        self.shadow_effect.setBlurRadius(8)
        self.shadow_effect.setColor(QColor(0, 0, 0, 50))
        self.shadow_effect.setOffset(2, 2)
        self.setGraphicsEffect(self.shadow_effect)

        # --- ADD THIS CONNECTION ---
        if self.document():
            self.document().contentsChanged.connect(self._on_contents_changed)
        # --- END ADDED CONNECTION ---

    # --- ADD THIS METHOD ---
    def _on_contents_changed(self):
        """Called when the text document's content changes."""
        self.prepareGeometryChange()
        # Optional: self.update() if prepareGeometryChange alone isn't enough visually for some edge cases
        if self.scene(): # If item is on a scene, notify that it might have moved/resized
            self.scene().item_moved.emit(self) # Or a more specific signal like item_geometry_changed
    # --- END ADDED METHOD ---

    def paint(self, painter, option, widget):
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(self.border_pen)
        painter.setBrush(self.background_brush)
        rect = self.boundingRect()
        painter.drawRoundedRect(rect.adjusted(0.5,0.5,-0.5,-0.5), 4, 4)

        self.setDefaultTextColor(QColor(COLOR_TEXT_PRIMARY))
        super().paint(painter, option, widget)

        if self.isSelected():
            selection_pen = QPen(QColor(COLOR_ACCENT_PRIMARY), 1.5, Qt.DashLine)
            painter.setPen(selection_pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(self.boundingRect())

    def get_data(self):
        doc_width = self.document().idealWidth() if self.textWidth() < 0 else self.textWidth()
        return {
            'text': self.toPlainText(),
            'x': self.x(), 'y': self.y(),
            'width': doc_width
        }

    def set_properties(self, text, width=None):
        current_text = self.toPlainText()
        text_changed = (current_text != text)
        
        width_changed = False
        current_text_width = self.textWidth()
        target_width = width if width and width > 0 else self._default_width
        if current_text_width != target_width:
            width_changed = True
            
        if text_changed:
            self.setPlainText(text) # This will trigger contentsChanged -> _on_contents_changed
        
        if width_changed:
            self.setTextWidth(target_width) # This will also affect geometry

        if text_changed or width_changed : # Update if anything visual might have changed due to these properties
             self.update()


    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged and self.scene():
            self.scene().item_moved.emit(self) # Signal item movement for transitions etc.

        # --- REMOVE/COMMENT OUT THE PROBLEMATIC BLOCK ---
        # if change == QGraphicsItem.ItemUserType + 6 and self.document():
        #     self.prepareGeometryChange()
        # --- END REMOVAL ---

        return super().itemChange(change, value)