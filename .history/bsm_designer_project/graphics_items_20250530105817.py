# bsm_designer_project/graphics_items.py

import math
from PyQt5.QtWidgets import (QGraphicsRectItem, QGraphicsPathItem, QGraphicsTextItem,
                             QGraphicsItem, QGraphicsDropShadowEffect, QApplication, QGraphicsSceneMouseEvent,
                             QStyle, QLineEdit, QTextEdit, QGraphicsProxyWidget, QMessageBox)
from PyQt5.QtGui import (QBrush, QColor, QFont, QPen, QPainterPath, QPolygonF, QPainter,
                         QPainterPathStroker, QPixmap, QMouseEvent, QDrag, QPalette, QFocusEvent, QKeyEvent) 
from PyQt5.QtCore import Qt, QRectF, QPointF, QMimeData, QPoint, QLineF, QSize, pyqtSignal, QEvent

from config import (COLOR_ITEM_STATE_DEFAULT_BG, COLOR_ITEM_STATE_DEFAULT_BORDER, APP_FONT_FAMILY,
                    COLOR_TEXT_PRIMARY, COLOR_ITEM_STATE_SELECTION_BG, COLOR_ITEM_STATE_SELECTION_BORDER,
                    COLOR_ITEM_TRANSITION_DEFAULT, COLOR_ITEM_TRANSITION_SELECTION,
                    COLOR_ITEM_COMMENT_BG, COLOR_ITEM_COMMENT_BORDER,
                    COLOR_PY_SIM_STATE_ACTIVE, COLOR_PY_SIM_STATE_ACTIVE_PEN_WIDTH,
                    COLOR_BACKGROUND_LIGHT, COLOR_BORDER_LIGHT, COLOR_ACCENT_PRIMARY, COLOR_ACCENT_PRIMARY_LIGHT,
                    DEFAULT_EXECUTION_ENV, COLOR_TEXT_SECONDARY, COLOR_BACKGROUND_DIALOG, COLOR_BORDER_MEDIUM,
                    COLOR_TEXT_EDITOR_DARK_PRIMARY, COLOR_BACKGROUND_EDITOR_DARK) 

from utils import get_standard_icon 

class GraphicsStateItem(QGraphicsRectItem):
    Type = QGraphicsItem.UserType + 1
    textChangedViaInlineEdit = pyqtSignal(str, str) 

    def type(self): return GraphicsStateItem.Type

    def __init__(self, x, y, w, h, text, is_initial=False, is_final=False,
                 color=None, entry_action="", during_action="", exit_action="", description="",
                 is_superstate=False, sub_fsm_data=None, action_language=DEFAULT_EXECUTION_ENV):
        super().__init__(x, y, w, h)
        self.signals = StateItemSignals()
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
        self._border_pen_width = 1.8 
        self._superstate_border_pen_width = 2.5 

        self.setPen(QPen(self.border_color, self._border_pen_width))
        self.setBrush(QBrush(self.base_color))

        self.setFlags(QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsMovable |
                      QGraphicsItem.ItemSendsGeometryChanges | QGraphicsItem.ItemIsFocusable)
        self.setAcceptHoverEvents(True)

        self.shadow_effect = QGraphicsDropShadowEffect()
        self.shadow_effect.setBlurRadius(12) 
        self.shadow_effect.setColor(QColor(0, 0, 0, 45)) 
        self.shadow_effect.setOffset(3, 3) 
        self.setGraphicsEffect(self.shadow_effect)

        self.is_py_sim_active = False
        self.original_pen_for_py_sim_restore = self.pen()
        
        self._inline_editor_proxy: QGraphicsProxyWidget | None = None
        self._is_editing_inline = False
        self._inline_edit_aborted = False


    def paint(self, painter: QPainter, option, widget):
        painter.setRenderHint(QPainter.Antialiasing)
        current_rect = self.rect()
        border_radius = 12 
        pass

        current_pen_to_use = QPen(self.pen()) 
        
        if self.is_superstate:
            current_pen_to_use.setWidthF(self._superstate_border_pen_width)
        else:
            current_pen_to_use.setWidthF(self._border_pen_width)

        if self.is_py_sim_active:
            py_sim_pen = QPen(COLOR_PY_SIM_STATE_ACTIVE, COLOR_PY_SIM_STATE_ACTIVE_PEN_WIDTH, Qt.SolidLine) 
            current_pen_to_use = py_sim_pen 

        painter.setPen(current_pen_to_use)
        painter.setBrush(self.brush())
        painter.drawRoundedRect(current_rect, border_radius, border_radius)

        if not self._is_editing_inline: # Only draw item's text if not currently inline editing
            painter.setPen(self._text_color)
            painter.setFont(self._font)
            text_rect = current_rect.adjusted(10, 10, -10, -10) 
            if self.is_superstate:
                text_rect.setRight(text_rect.right() - 18) 
            painter.drawText(text_rect, Qt.AlignCenter | Qt.TextWordWrap, self.text_label)

        if self.is_initial:
            # ... (initial marker drawing code as before) ...
            marker_radius = 7; line_length = 20; marker_color = QColor(COLOR_TEXT_PRIMARY)
            start_marker_center_x = current_rect.left() - line_length - marker_radius / 2
            start_marker_center_y = current_rect.center().y()
            painter.setBrush(marker_color)
            painter.setPen(QPen(marker_color, self._border_pen_width + 0.5)) 
            painter.drawEllipse(QPointF(start_marker_center_x, start_marker_center_y), marker_radius, marker_radius)
            line_start_point = QPointF(start_marker_center_x + marker_radius, start_marker_center_y)
            line_end_point = QPointF(current_rect.left(), start_marker_center_y)
            painter.drawLine(line_start_point, line_end_point)
            arrow_size = 9; angle_rad = 0 
            arrow_p1 = QPointF(line_end_point.x() - arrow_size * math.cos(angle_rad + math.pi / 6),
                               line_end_point.y() - arrow_size * math.sin(angle_rad + math.pi / 6))
            arrow_p2 = QPointF(line_end_point.x() - arrow_size * math.cos(angle_rad - math.pi / 6),
                               line_end_point.y() - arrow_size * math.sin(angle_rad - math.pi / 6))
            painter.drawPolygon(QPolygonF([line_end_point, arrow_p1, arrow_p2]))


        if self.is_final:
            # ... (final marker drawing code as before) ...
            inner_border_pen = QPen(current_pen_to_use.color().darker(130), self._border_pen_width)
            painter.setPen(inner_border_pen)
            inner_rect = current_rect.adjusted(6, 6, -6, -6) 
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(inner_rect, border_radius - 4, border_radius - 4) 


        if self.is_superstate:
            # ... (superstate icon drawing code as before) ...
            icon_size = 16 
            margin = 5    
            icon_rect = QRectF(
                current_rect.right() - icon_size - margin,
                current_rect.top() + margin, 
                icon_size,
                icon_size
            )
            superstate_icon = get_standard_icon(QStyle.SP_FileDialogDetailedView, "Superstate") 
            if not superstate_icon.isNull():
                pixmap = superstate_icon.pixmap(icon_size, icon_size)
                painter.drawPixmap(icon_rect.topLeft(), pixmap)
            else: 
                pen_color = self.border_color.darker(150)
                if self.base_color.lightnessF() < 0.3:
                    pen_color = QColor(Qt.lightGray)
                painter.setPen(QPen(pen_color, 1.5))
                painter.setBrush(Qt.NoBrush)
                r1 = QRectF(icon_rect.left() + 2, icon_rect.top() + 2, icon_rect.width() - 4, icon_rect.height() - 4)
                r2 = QRectF(icon_rect.left(), icon_rect.top(), icon_rect.width() - 4, icon_rect.height() - 4)
                painter.drawRect(r1); painter.drawRect(r2)


        if self.isSelected() and not self.is_py_sim_active: # No selection highlight if also PySim active
            # ... (selection highlight drawing code as before) ...
            selection_pen = QPen(QColor(COLOR_ITEM_STATE_SELECTION_BORDER), self._border_pen_width + 1, Qt.DashLine) 
            selection_brush_color = QColor(COLOR_ITEM_STATE_SELECTION_BG)
            selection_brush_color.setAlpha(80) 
            
            selection_rect = self.boundingRect().adjusted(-2, -2, 2, 2) 
            painter.setPen(selection_pen)
            painter.setBrush(QBrush(selection_brush_color)) 
            painter.drawRoundedRect(selection_rect, border_radius + 2, border_radius + 2)


    def start_inline_edit(self):
        if self._is_editing_inline or not self.scene():
            return

        self._is_editing_inline = True
        self._inline_edit_aborted = False # Reset abort flag
        self.update() 

        editor = QLineEdit(self.text_label)
        editor.setFont(self._font)
        editor.setAlignment(Qt.AlignCenter)
        editor.setStyleSheet(f"""
            QLineEdit {{ 
                background-color: {self.base_color.lighter(110).name()}; 
                color: {self._text_color.name()}; 
                border: 1px solid {self.border_color.name()}; 
                border-radius: {self.rect().height() / 6}px; /* Dynamic radius */
                padding: 5px; 
            }}
        """)
        
        text_rect_local = self.rect().adjusted(8, 8, -8, -8) 
        if self.is_superstate: text_rect_local.setRight(text_rect_local.right() -18)

        editor.selectAll()
        
        # Use editingFinished for QLineEdit
        editor.editingFinished.connect(lambda: self._finish_inline_edit(editor))
        # Custom keyPressEvent for Escape/Enter on the QLineEdit
        editor.keyPressEvent = lambda event: self._handle_editor_key_press(event, editor)

        self._inline_editor_proxy = QGraphicsProxyWidget(self) 
        self._inline_editor_proxy.setWidget(editor)
        self._inline_editor_proxy.setPos(text_rect_local.topLeft())
        editor.setFixedSize(text_rect_local.size().toSize())
        
        editor.setFocus(Qt.MouseFocusReason)

    def _handle_editor_key_press(self, event: QKeyEvent, editor_widget: QLineEdit):
        if event.key() == Qt.Key_Escape:
            self._inline_edit_aborted = True # Set abort flag
            editor_widget.clearFocus() # This will trigger editingFinished
        elif event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            self._inline_edit_aborted = False # Explicitly ensure not aborted on Enter
            editor_widget.clearFocus() # Trigger editingFinished
        else:
            QLineEdit.keyPressEvent(editor_widget, event)


    def _finish_inline_edit(self, editor_widget: QLineEdit | None = None):
        if not self._is_editing_inline: # If already finished/aborted, do nothing
            return
        
        actual_editor = editor_widget if editor_widget else (self._inline_editor_proxy.widget() if self._inline_editor_proxy else None)
        if not actual_editor: 
            self._is_editing_inline = False # Ensure flag is reset
            self.update()
            return

        new_text = actual_editor.text().strip()
        old_text = self.text_label
        
        # Cleanup must happen regardless of commit
        if self._inline_editor_proxy:
            self._inline_editor_proxy.setWidget(None) # Release widget from proxy
            # editor_widget.deleteLater() # Let proxy handle widget deletion if it was set
            if self._inline_editor_proxy.scene():
                 self.scene().removeItem(self._inline_editor_proxy)
            self._inline_editor_proxy.deleteLater()
            self._inline_editor_proxy = None
        
        self._is_editing_inline = False # Crucial: reset state *before* potential QMessageBox

        if not self._inline_edit_aborted and new_text and new_text != old_text:
            if self.scene() and hasattr(self.scene(), 'get_state_by_name'):
                existing_state = self.scene().get_state_by_name(new_text)
                if existing_state and existing_state != self:
                    QMessageBox.warning(None, "Duplicate Name", f"A state named '{new_text}' already exists. Edit cancelled.")
                    self.update() # Redraw original text
                    return 

            old_props = self.get_data()
            self.text_label = new_text 
            new_props = self.get_data()

            if self.scene() and hasattr(self.scene(), 'undo_stack'):
                from undo_commands import EditItemPropertiesCommand 
                cmd = EditItemPropertiesCommand(self, old_props, new_props, "Rename State")
                self.scene().undo_stack.push(cmd)
                self.scene().set_dirty(True)
            self.textChangedViaInlineEdit.emit(old_text, new_text) 
            if self.scene() and hasattr(self.scene(), '_update_transitions_for_renamed_state'):
                 self.scene()._update_transitions_for_renamed_state(old_text, new_text)
        
        self.update() # Redraw the item with its (potentially new) text_label


    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_F2 and self.isSelected() and self.flags() & QGraphicsItem.ItemIsFocusable:
            if not self._is_editing_inline: 
                self.start_inline_edit()
                event.accept()
        else:
            super().keyPressEvent(event)

    def set_py_sim_active_style(self, active: bool): # Unchanged
        if self.is_py_sim_active == active: return
        self.is_py_sim_active = active
        if active: self.original_pen_for_py_sim_restore = QPen(self.pen())
        else: self.setPen(self.original_pen_for_py_sim_restore) 
        self.update()

    def itemChange(self, change, value): # Unchanged
        if change == QGraphicsItem.ItemPositionHasChanged and self.scene():
            self.scene().item_moved.emit(self)
        return super().itemChange(change, value)

    def get_data(self): # Unchanged
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

    def set_text(self, text): # Unchanged
        if self.text_label != text:
            self.prepareGeometryChange()
            self.text_label = text
            self.update()

    def set_properties(self, name, is_initial, is_final, color_hex=None,
                       action_language=DEFAULT_EXECUTION_ENV, 
                       entry="", during="", exit_a="", desc="",
                       is_superstate_prop=None, sub_fsm_data_prop=None): # Unchanged
        changed = False
        if self.text_label != name: self.text_label = name; changed = True
        if self.is_initial != is_initial: self.is_initial = is_initial; changed = True
        if self.is_final != is_final: self.is_final = is_final; changed = True
        if self.action_language != action_language: self.action_language = action_language; changed = True
        if is_superstate_prop is not None and self.is_superstate != is_superstate_prop:
            self.is_superstate = is_superstate_prop; changed = True
        if sub_fsm_data_prop is not None:
            if isinstance(sub_fsm_data_prop, dict) and \
               all(k in sub_fsm_data_prop for k in ['states', 'transitions', 'comments']) and \
               isinstance(sub_fsm_data_prop['states'], list) and \
               isinstance(sub_fsm_data_prop['transitions'], list) and \
               isinstance(sub_fsm_data_prop['comments'], list):
                if self.sub_fsm_data != sub_fsm_data_prop:
                     self.sub_fsm_data = sub_fsm_data_prop; changed = True
            elif self.is_superstate: pass 
        new_base_color = QColor(color_hex) if color_hex and QColor(color_hex).isValid() else QColor(COLOR_ITEM_STATE_DEFAULT_BG)
        new_border_color = new_base_color.darker(120) if color_hex and QColor(color_hex).isValid() else QColor(COLOR_ITEM_STATE_DEFAULT_BORDER)
        if self.base_color != new_base_color:
            self.base_color = new_base_color; self.border_color = new_border_color
            self.setBrush(self.base_color)
            changed = True
        if self.entry_action != entry: self.entry_action = entry; changed = True
        if self.during_action != during: self.during_action = during; changed = True
        if self.exit_action != exit_a: self.exit_action = exit_a; changed = True
        if self.description != desc: self.description = desc; changed = True
        if changed:
            self.prepareGeometryChange()
            current_pen_width = self._superstate_border_pen_width if self.is_superstate else self._border_pen_width
            base_pen = QPen(self.border_color, current_pen_width)
            if not self.is_py_sim_active: self.setPen(base_pen)
            self.original_pen_for_py_sim_restore = base_pen
            self.update()

class GraphicsTransitionItem(QGraphicsPathItem): # Unchanged
    Type = QGraphicsItem.UserType + 2
    def type(self): return GraphicsTransitionItem.Type
    CONTROL_POINT_SIZE = 8 
    def __init__(self, start_item, end_item, event_str="", condition_str="", action_str="", color=None, description="", action_language=DEFAULT_EXECUTION_ENV): 
        super().__init__()
        self.start_item: GraphicsStateItem | None = start_item; self.end_item: GraphicsStateItem | None = end_item
        self.event_str = event_str; self.condition_str = condition_str; self.action_language = action_language; self.action_str = action_str
        self.base_color = QColor(color) if color and QColor(color).isValid() else QColor(COLOR_ITEM_TRANSITION_DEFAULT); self.description = description
        self.arrow_size = 11; self._text_color = QColor(COLOR_TEXT_PRIMARY); self._font = QFont(APP_FONT_FAMILY, 8, QFont.Medium) 
        self.control_point_offset = QPointF(0,0); self._pen_width = 2.2 
        self.setPen(QPen(self.base_color, self._pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)); self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsFocusable, True); self.setZValue(-1); self.setAcceptHoverEvents(True)
        self.shadow_effect = QGraphicsDropShadowEffect(); self.shadow_effect.setBlurRadius(8); self.shadow_effect.setColor(QColor(0, 0, 0, 50)); self.shadow_effect.setOffset(1.5, 1.5); self.setGraphicsEffect(self.shadow_effect)
        self._dragging_control_point = False; self._last_mouse_press_pos_for_cp_drag = QPointF(); self._initial_cp_offset_on_drag_start = QPointF()
        self.update_path()
    def _get_actual_control_point_scene_pos(self) -> QPointF:
        if not self.start_item or not self.end_item: return QPointF()
        start_rect_center = self.start_item.sceneBoundingRect().center(); end_rect_center = self.end_item.sceneBoundingRect().center()
        start_point = self._get_intersection_point(self.start_item, QLineF(start_rect_center, end_rect_center)); end_point = self._get_intersection_point(self.end_item, QLineF(end_rect_center, start_rect_center))
        if start_point is None: start_point = start_rect_center
        if end_point is None: end_point = end_rect_center
        if self.start_item == self.end_item:
            rect = self.start_item.sceneBoundingRect(); p1_scene = QPointF(rect.center().x() + rect.width() * 0.2, rect.top()); loop_radius_y = rect.height() * 0.55
            base_cp_x = p1_scene.x(); base_cp_y = p1_scene.y() - loop_radius_y * 1.5 
            return QPointF(base_cp_x + self.control_point_offset.x(), base_cp_y + self.control_point_offset.y())
        mid_x = (start_point.x() + end_point.x()) / 2; mid_y = (start_point.y() + end_point.y()) / 2; dx = end_point.x() - start_point.x(); dy = end_point.y() - start_point.y()
        length = math.hypot(dx, dy)
        if length < 1e-6 : length = 1e-6
        perp_x = -dy / length; perp_y = dx / length
        ctrl_pt_x = mid_x + perp_x * self.control_point_offset.x() + (dx/length) * self.control_point_offset.y(); ctrl_pt_y = mid_y + perp_y * self.control_point_offset.x() + (dy/length) * self.control_point_offset.y()
        return QPointF(ctrl_pt_x, ctrl_pt_y)
    def _get_control_point_rect(self) -> QRectF:
        if not self.isSelected(): return QRectF()
        cp_pos = self._get_actual_control_point_scene_pos()
        if self.start_item != self.end_item and self.control_point_offset.x() == 0 and self.control_point_offset.y() == 0:
            if self.path().elementCount() > 0:
                mid_point = self.path().pointAtPercent(0.5); default_offset_dist = -self.CONTROL_POINT_SIZE * 1.5 
                if self.start_item and self.end_item: 
                    start_center = self.start_item.sceneBoundingRect().center(); end_center = self.end_item.sceneBoundingRect().center(); line_vec = end_center - start_center
                    line_len_for_perp = math.hypot(line_vec.x(), line_vec.y())
                    if line_len_for_perp > 1e-6: perp_vec_normalized = QPointF(-line_vec.y(), line_vec.x()) / line_len_for_perp; cp_pos = mid_point + perp_vec_normalized * default_offset_dist
                    else: cp_pos = mid_point + QPointF(0, default_offset_dist) 
                else: cp_pos = mid_point + QPointF(0, default_offset_dist)
            else: return QRectF()
        return QRectF(cp_pos.x() - self.CONTROL_POINT_SIZE / 2, cp_pos.y() - self.CONTROL_POINT_SIZE / 2, self.CONTROL_POINT_SIZE, self.CONTROL_POINT_SIZE)
    def _compose_label_string(self):
        parts = []; event_str, cond_str, action_str = self.event_str, self.condition_str, self.action_str
        if event_str: parts.append(event_str)
        if cond_str: parts.append(f"[{cond_str}]")
        if action_str: action_display = action_str.split('\n')[0]; parts.append(f"/{{{action_display[:17] + '...' if len(action_display) > 20 else action_display}}}")
        return " ".join(parts)
    def hoverEnterEvent(self, event: QGraphicsSceneMouseEvent): self.setPen(QPen(self.base_color.lighter(130), self._pen_width + 0.8)); self.update(); super().hoverEnterEvent(event)
    def hoverLeaveEvent(self, event: QGraphicsSceneMouseEvent): self.setPen(QPen(self.base_color, self._pen_width)); self.update(); super().hoverLeaveEvent(event)
    def boundingRect(self):
        extra = (self.pen().widthF() + self.arrow_size) / 2.0 + 30; path_bounds = self.path().boundingRect()
        current_label = self._compose_label_string()
        if current_label:
            from PyQt5.QtGui import QFontMetrics; fm = QFontMetrics(self._font); text_bounding_rect_for_calculation = QRectF(0,0, 300, 100) 
            text_actual_rect = fm.boundingRect(text_bounding_rect_for_calculation.toRect(), Qt.TextWordWrap | Qt.AlignCenter, current_label) 
            mid_point_on_path = self.path().pointAtPercent(0.5); text_render_rect = QRectF(mid_point_on_path.x() - text_actual_rect.width()/2 - 10, mid_point_on_path.y() - text_actual_rect.height() - 10, text_actual_rect.width() + 20, text_actual_rect.height() + 20) 
            path_bounds = path_bounds.united(text_render_rect)
        cp_rect = self._get_control_point_rect() 
        if not cp_rect.isEmpty(): path_bounds = path_bounds.united(cp_rect.adjusted(-self.CONTROL_POINT_SIZE, -self.CONTROL_POINT_SIZE, self.CONTROL_POINT_SIZE, self.CONTROL_POINT_SIZE)) 
        return path_bounds.adjusted(-extra, -extra, extra, extra)
        pass
    def shape(self): 
        path_stroker = QPainterPathStroker(); path_stroker.setWidth(20 + self.pen().widthF()); path_stroker.setCapStyle(Qt.RoundCap); path_stroker.setJoinStyle(Qt.RoundJoin)
        base_shape = path_stroker.createStroke(self.path())
        cp_rect = self._get_control_point_rect()
        if not cp_rect.isEmpty(): cp_path = QPainterPath(); cp_interaction_rect = cp_rect.adjusted(-2,-2,2,2); cp_path.addEllipse(cp_interaction_rect); base_shape.addPath(cp_path)
        return base_shape
    def update_path(self):
        if not self.start_item or not self.end_item: self.setPath(QPainterPath()); return
        start_rect_center = self.start_item.sceneBoundingRect().center(); end_rect_center = self.end_item.sceneBoundingRect().center()
        start_point = self._get_intersection_point(self.start_item, QLineF(start_rect_center, end_rect_center)); end_point = self._get_intersection_point(self.end_item, QLineF(end_rect_center, start_rect_center))
        if start_point is None: start_point = start_rect_center
        if end_point is None: end_point = end_rect_center
        path = QPainterPath(start_point)
        if self.start_item == self.end_item: 
            rect = self.start_item.sceneBoundingRect(); p1_scene = QPointF(rect.center().x() + rect.width() * 0.2, rect.top()); p2_scene = QPointF(rect.center().x() - rect.width() * 0.2, rect.top())
            user_manipulated_cp = self._get_actual_control_point_scene_pos(); ctrl1_x = user_manipulated_cp.x() - (user_manipulated_cp.x() - p1_scene.x()) * 0.5; ctrl1_y = user_manipulated_cp.y()
            ctrl2_x = user_manipulated_cp.x() + (p2_scene.x() - user_manipulated_cp.x()) * 0.5; ctrl2_y = user_manipulated_cp.y()
            final_ctrl1 = QPointF(ctrl1_x, ctrl1_y); final_ctrl2 = QPointF(ctrl2_x, ctrl2_y)
            path.moveTo(p1_scene); path.cubicTo(final_ctrl1, final_ctrl2, p2_scene); end_point = p2_scene 
        else:
            if self.control_point_offset.x() == 0 and self.control_point_offset.y() == 0: path.lineTo(end_point)
            else: ctrl_pt_scene = self._get_actual_control_point_scene_pos(); path.quadTo(ctrl_pt_scene, end_point)
        self.setPath(path); self.prepareGeometryChange()
    def _get_intersection_point(self, item: QGraphicsRectItem, line: QLineF):
        item_rect = item.sceneBoundingRect(); rect_path = QPainterPath(); rect_path.addRoundedRect(item_rect, 12, 12)
        temp_path = QPainterPath(line.p1()); temp_path.lineTo(line.p2()); intersect_path = rect_path.intersected(temp_path)
        if not intersect_path.isEmpty() and intersect_path.elementCount() > 0:
            points_on_boundary = []
            for i in range(intersect_path.elementCount()):
                el = intersect_path.elementAt(i); points_on_boundary.append(QPointF(el.x, el.y))
                if el.isLineTo() and i > 0 and intersect_path.elementAt(i-1).isMoveTo(): prev_el = intersect_path.elementAt(i-1); points_on_boundary.append(QPointF(prev_el.x, prev_el.y))
            if points_on_boundary:
                original_line_actual_vector = line.p2() - line.p1(); line_length = math.hypot(original_line_actual_vector.x(), original_line_actual_vector.y())
                if line_length < 1e-6: points_on_boundary.sort(key=lambda pt: QLineF(line.p1(), pt).length()); return points_on_boundary[0] if points_on_boundary else item_rect.center()
                direction_vector_qpointf = original_line_actual_vector / line_length; min_proj = float('inf'); best_point = None
                for pt_boundary in points_on_boundary:
                    vec_to_boundary = pt_boundary - line.p1(); projection = QPointF.dotProduct(vec_to_boundary, direction_vector_qpointf)
                    if 0 <= projection < min_proj : min_proj = projection; best_point = pt_boundary
                if best_point: return best_point
            if intersect_path.elementCount() > 0: return QPointF(intersect_path.elementAt(0).x, intersect_path.elementAt(0).y)
        edges = [QLineF(item_rect.topLeft(), item_rect.topRight()), QLineF(item_rect.topRight(), item_rect.bottomRight()), QLineF(item_rect.bottomRight(), item_rect.bottomLeft()), QLineF(item_rect.bottomLeft(), item_rect.topLeft())]
        intersect_points = []
        for edge in edges:
            intersection_point_var = QPointF(); intersect_type = line.intersect(edge, intersection_point_var)
            if intersect_type == QLineF.BoundedIntersection: intersect_points.append(QPointF(intersection_point_var))
        if not intersect_points: return item_rect.center() 
        intersect_points.sort(key=lambda pt: QLineF(line.p1(), pt).length()); return intersect_points[0]
    def paint(self, painter: QPainter, option, widget):
        if not self.start_item or not self.end_item or self.path().isEmpty(): return
        painter.setRenderHint(QPainter.Antialiasing); current_pen = self.pen()
        if self.isSelected():
            stroker = QPainterPathStroker(); stroker.setWidth(current_pen.widthF() + 8); stroker.setCapStyle(Qt.RoundCap); stroker.setJoinStyle(Qt.RoundJoin)
            selection_path_shape = stroker.createStroke(self.path()); highlight_color = QColor(COLOR_ITEM_TRANSITION_SELECTION); highlight_color.setAlpha(150) 
            painter.setPen(QPen(highlight_color, 1, Qt.SolidLine)); painter.setBrush(highlight_color); painter.drawPath(selection_path_shape)
            cp_rect = self._get_control_point_rect() 
            if not cp_rect.isEmpty(): painter.setPen(QPen(QColor(COLOR_ACCENT_PRIMARY), 1.5)); fill_color = QColor(COLOR_ACCENT_PRIMARY_LIGHT); fill_color.setAlpha(200); painter.setBrush(fill_color); painter.drawEllipse(cp_rect)
        painter.setPen(current_pen); painter.setBrush(Qt.NoBrush); painter.drawPath(self.path())
        if self.path().elementCount() < 1 : return
        line_end_point = self.path().pointAtPercent(1.0); path_len = self.path().length()
        tangent_point_percent = max(0.0, 1.0 - (self.arrow_size * 1.2 / (path_len + 1e-6))) 
        if path_len < self.arrow_size * 1.5 : tangent_point_percent = max(0.0, 0.8 if path_len > 0 else 0.0)
        angle_at_end_rad = -self.path().angleAtPercent(tangent_point_percent) * (math.pi / 180.0)
        arrow_p1 = line_end_point + QPointF(math.cos(angle_at_end_rad - math.pi / 7) * self.arrow_size, math.sin(angle_at_end_rad - math.pi / 7) * self.arrow_size)
        arrow_p2 = line_end_point + QPointF(math.cos(angle_at_end_rad + math.pi / 7) * self.arrow_size, math.sin(angle_at_end_rad + math.pi / 7) * self.arrow_size)
        painter.setBrush(current_pen.color()); painter.drawPolygon(QPolygonF([line_end_point, arrow_p1, arrow_p2]))
        current_label = self._compose_label_string()
        if current_label:
            from PyQt5.QtGui import QFontMetrics; painter.setFont(self._font); fm = QFontMetrics(self._font)
            label_rect_width = 150; text_block_rect = QRectF(0, 0, label_rect_width, 100); text_rect_original = fm.boundingRect(text_block_rect.toRect(), Qt.AlignCenter | Qt.TextWordWrap, current_label)
            label_path_percent = 0.5; text_pos_on_path = self.path().pointAtPercent(label_path_percent); angle_at_mid_deg = self.path().angleAtPercent(label_path_percent)
            offset_angle_rad = (angle_at_mid_deg - 90.0) * (math.pi / 180.0); offset_dist = 12 
            text_center_x = text_pos_on_path.x() + offset_dist * math.cos(offset_angle_rad); text_center_y = text_pos_on_path.y() + offset_dist * math.sin(offset_angle_rad)
            text_final_draw_rect = QRectF(text_center_x - text_rect_original.width() / 2, text_center_y - text_rect_original.height() / 2, text_rect_original.width(), text_rect_original.height())
            bg_padding = 4; bg_rect = text_final_draw_rect.adjusted(-bg_padding, -bg_padding, bg_padding, bg_padding)
            label_bg_color = QColor(COLOR_BACKGROUND_DIALOG); label_bg_color.setAlpha(230); painter.setBrush(label_bg_color)
            painter.setPen(QPen(QColor(COLOR_BORDER_LIGHT), 0.8)); painter.drawRoundedRect(bg_rect, 4, 4) 
            painter.setPen(self._text_color); painter.drawText(text_final_draw_rect, Qt.AlignCenter | Qt.TextWordWrap, current_label)
    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        if self.isSelected() and event.button() == Qt.LeftButton:
            cp_rect = self._get_control_point_rect()
            if not cp_rect.isEmpty() and cp_rect.contains(event.scenePos()): 
                self._dragging_control_point = True; self._last_mouse_press_pos_for_cp_drag = event.scenePos(); self._initial_cp_offset_on_drag_start = QPointF(self.control_point_offset)
                self.setCursor(Qt.ClosedHandCursor); event.accept(); return 
        self._dragging_control_point = False; super().mousePressEvent(event) 
    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent):
        if self._dragging_control_point:
            if not self.start_item or not self.end_item: self._dragging_control_point = False; self.setCursor(Qt.ArrowCursor); return
            delta_scene = event.scenePos() - self._last_mouse_press_pos_for_cp_drag
            if self.start_item == self.end_item: new_offset_x = self._initial_cp_offset_on_drag_start.x() + delta_scene.x(); new_offset_y = self._initial_cp_offset_on_drag_start.y() + delta_scene.y()
            else: 
                start_rect_center = self.start_item.sceneBoundingRect().center(); end_rect_center = self.end_item.sceneBoundingRect().center(); line_vec = end_rect_center - start_rect_center
                line_len = math.hypot(line_vec.x(), line_vec.y()); line_len = 1e-6 if line_len < 1e-6 else line_len
                tangent_dir = line_vec / line_len if line_len > 0 else QPointF(1,0); perp_dir = QPointF(-tangent_dir.y(), tangent_dir.x())
                delta_perp = QPointF.dotProduct(delta_scene, perp_dir); delta_tang = QPointF.dotProduct(delta_scene, tangent_dir)
                new_offset_x = self._initial_cp_offset_on_drag_start.x() + delta_perp; new_offset_y = self._initial_cp_offset_on_drag_start.y() + delta_tang
            self.set_control_point_offset(QPointF(new_offset_x, new_offset_y)); event.accept(); return
        super().mouseMoveEvent(event)
    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent):
        if self._dragging_control_point and event.button() == Qt.LeftButton:
            self._dragging_control_point = False; self.setCursor(Qt.ArrowCursor) 
            if self.scene() and hasattr(self.scene(), 'undo_stack'):
                from undo_commands import EditItemPropertiesCommand; old_props = self.get_data(); old_props['control_offset_x'] = self._initial_cp_offset_on_drag_start.x(); old_props['control_offset_y'] = self._initial_cp_offset_on_drag_start.y()
                new_props = self.get_data() 
                if old_props['control_offset_x'] != new_props['control_offset_x'] or old_props['control_offset_y'] != new_props['control_offset_y']:
                    cmd = EditItemPropertiesCommand(self, old_props, new_props, "Modify Transition Curve"); self.scene().undo_stack.push(cmd); self.scene().set_dirty(True) 
            event.accept(); return
        super().mouseReleaseEvent(event)
    def get_data(self): return {'source': self.start_item.text_label if self.start_item else "None", 'target': self.end_item.text_label if self.end_item else "None", 'event': self.event_str, 'condition': self.condition_str, 'action_language': self.action_language, 'action': self.action_str, 'color': self.base_color.name() if self.base_color else QColor(COLOR_ITEM_TRANSITION_DEFAULT).name(), 'description': self.description, 'control_offset_x': self.control_point_offset.x(), 'control_offset_y': self.control_point_offset.y()}
    def set_properties(self, event_str="", condition_str="", action_str="", color_hex=None, description="", offset=None, action_language=DEFAULT_EXECUTION_ENV): 
        changed = False
        if self.event_str != event_str: self.event_str = event_str; changed=True
        if self.condition_str != condition_str: self.condition_str = condition_str; changed=True
        if self.action_language != action_language: self.action_language = action_language; changed=True
        if self.action_str != action_str: self.action_str = action_str; changed=True
        if self.description != description: self.description = description; changed=True
        new_color = QColor(color_hex) if color_hex and QColor(color_hex).isValid() else QColor(COLOR_ITEM_TRANSITION_DEFAULT)
        if self.base_color != new_color: self.base_color = new_color; self.setPen(QPen(self.base_color, self._pen_width)); changed = True
        if offset is not None and self.control_point_offset != QPointF(offset): self.control_point_offset = QPointF(offset); changed = True 
        if changed: self.prepareGeometryChange(); self.update_path(); self.update() 
    def set_control_point_offset(self, offset: QPointF):
        if self.control_point_offset != offset: self.control_point_offset = offset; self.prepareGeometryChange(); self.update_path(); self.update() 

class GraphicsCommentItem(QGraphicsTextItem): 
    Type = QGraphicsItem.UserType + 3
    textChangedViaInlineEdit = pyqtSignal(str, str)
    def type(self): return GraphicsCommentItem.Type
    def __init__(self, x, y, text="Comment"):
        super().__init__(); self.setPlainText(text); self.setPos(x, y)
        self.setFont(QFont(APP_FONT_FAMILY, 9, QFont.StyleItalic)); self.setTextInteractionFlags(Qt.TextEditorInteraction)
        self.setFlags(QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemSendsGeometryChanges | QGraphicsItem.ItemIsFocusable)
        self._default_width = 160; self.setTextWidth(self._default_width) 
        self.border_pen = QPen(QColor(COLOR_ITEM_COMMENT_BORDER), 1.2); self.background_brush = QBrush(QColor(COLOR_ITEM_COMMENT_BG))
        self.shadow_effect = QGraphicsDropShadowEffect(); self.shadow_effect.setBlurRadius(10); self.shadow_effect.setColor(QColor(0, 0, 0, 40)); self.shadow_effect.setOffset(2.5, 2.5); self.setGraphicsEffect(self.shadow_effect)
        self.setDefaultTextColor(QColor(COLOR_TEXT_PRIMARY).darker(110)) 
        if self.document(): self.document().contentsChanged.connect(self._on_contents_changed)
        self._inline_editor_proxy: QGraphicsProxyWidget | None = None; self._is_editing_inline = False
        self.setFlag(QGraphicsItem.ItemIsFocusable, True)
        self._inline_edit_aborted = False


    def _on_contents_changed(self): self.prepareGeometryChange(); self.update(); # Updated to call update for geometry change
        # if self.scene(): self.scene().item_moved.emit(self) # This might be too frequent, handled by move command

    def paint(self, painter, option, widget):
        painter.setRenderHint(QPainter.Antialiasing); painter.setPen(self.border_pen); painter.setBrush(self.background_brush)
        rect = self.boundingRect(); painter.drawRoundedRect(rect.adjusted(0.5,0.5,-0.5,-0.5), 5, 5)
        if not self._is_editing_inline: super().paint(painter, option, widget) 
        if self.isSelected() and not self._is_editing_inline: 
            selection_pen = QPen(QColor(COLOR_ACCENT_PRIMARY), 1.8, Qt.DashLine) 
            painter.setPen(selection_pen); painter.setBrush(Qt.NoBrush); painter.drawRoundedRect(self.boundingRect().adjusted(-1,-1,1,1), 6, 6) 

    def start_inline_edit(self):
        if self._is_editing_inline or not self.scene(): return
        self._is_editing_inline = True; self._inline_edit_aborted = False; self.update() 
        editor = QTextEdit(self.toPlainText()); editor.setFont(self.font()) 
        current_doc_width = self.document().idealWidth() if self.textWidth() < 0 else self.textWidth()
        current_doc_height = self.document().size().height()
        editor_width = int(max(current_doc_width, self._default_width * 0.8)) + 15 # Add padding
        editor_height = int(current_doc_height) + 15 # Add padding
        editor.setFixedSize(editor_width, editor_height)
        editor.setStyleSheet(f"""
            QTextEdit {{ 
                background-color: {QColor(COLOR_ITEM_COMMENT_BG).lighter(102).name()}; 
                color: {self.defaultTextColor().name()}; 
                border: 1px solid {QColor(COLOR_ITEM_COMMENT_BORDER).darker(110).name()};
                border-radius: 3px; padding: 4px; 
            }}""")
        editor.focusOutEvent = lambda event: self._handle_comment_editor_focus_out(event, editor)
        editor.keyPressEvent = lambda event: self._handle_comment_editor_key_press(event, editor)
        self._inline_editor_proxy = QGraphicsProxyWidget(self); self._inline_editor_proxy.setWidget(editor)
        self._inline_editor_proxy.setPos(0,0); editor.setFocus(Qt.MouseFocusReason)
        cursor = editor.textCursor(); cursor.movePosition(cursor.End); editor.setTextCursor(cursor)

    def _handle_comment_editor_focus_out(self, event: QFocusEvent, editor_widget: QTextEdit):
        self._finish_inline_edit(editor_widget) # Pass editor
        # QTextEdit.focusOutEvent(editor_widget, event) # Avoid, can cause re-entry issues

    def _handle_comment_editor_key_press(self, event: QKeyEvent, editor_widget: QTextEdit):
        if event.key() == Qt.Key_Escape:
            self._inline_edit_aborted = True; editor_widget.clearFocus() 
        elif event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            if not (event.modifiers() & Qt.ShiftModifier): 
                self._inline_edit_aborted = False; editor_widget.clearFocus(); return 
        QTextEdit.keyPressEvent(editor_widget, event) 

    def _finish_inline_edit(self, editor_widget: QTextEdit | None = None):
        if not self._is_editing_inline: return # Already finished or aborted via another path

        actual_editor = editor_widget if editor_widget else (self._inline_editor_proxy.widget() if self._inline_editor_proxy else None)
        if not actual_editor:
            self._is_editing_inline = False; self.update(); return

        new_text = actual_editor.toPlainText() # Keep original newlines for comments
        old_text = self.toPlainText() 

        commit_changes = not self._inline_edit_aborted
        
        if self._inline_editor_proxy:
            self._inline_editor_proxy.setWidget(None); actual_editor.deleteLater()
            if self._inline_editor_proxy.scene(): self.scene().removeItem(self._inline_editor_proxy)
            self._inline_editor_proxy.deleteLater(); self._inline_editor_proxy = None
        
        self._is_editing_inline = False
        
        if commit_changes and new_text.strip() != old_text.strip(): # Compare stripped for actual content change
            old_props = self.get_data(); self.setPlainText(new_text) 
            if self.textWidth() < 0 : self.setTextWidth(-1) # Recalculate idealWidth for comment
            new_props = self.get_data()
            if self.scene() and hasattr(self.scene(), 'undo_stack'):
                from undo_commands import EditItemPropertiesCommand 
                cmd = EditItemPropertiesCommand(self, old_props, new_props, "Edit Comment Text")
                self.scene().undo_stack.push(cmd); self.scene().set_dirty(True)
            self.textChangedViaInlineEdit.emit(old_text, new_text)
        elif self._inline_edit_aborted and new_text != old_text: # Revert if aborted and text was typed
            self.setPlainText(old_text) # Ensure item visually reverts
            
        self.update() 

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_F2 and self.isSelected() and self.flags() & QGraphicsItem.ItemIsFocusable:
            if not self._is_editing_inline: self.start_inline_edit(); event.accept()
        elif self.textInteractionFlags() & Qt.TextEditorInteraction and self.hasFocus():
            super().keyPressEvent(event) # Let QGraphicsTextItem handle typing if text interaction is on
        elif not event.isAccepted():
            QGraphicsItem.keyPressEvent(self,event) 
            
    def get_data(self):
        doc_width = self.textWidth()
        if doc_width < 0 : doc_width = self.document().idealWidth() if self.document() else self._default_width
        return {'text': self.toPlainText(), 'x': self.x(), 'y': self.y(), 'width': doc_width}

    def set_properties(self, text, width=None):
        current_text = self.toPlainText(); text_changed = (current_text != text)
        width_changed = False
        target_width = float(width) if width is not None and float(width) > 0 else -1 # Use -1 for auto-width from content
        
        current_actual_width = self.textWidth()
        if current_actual_width < 0: current_actual_width = self.document().idealWidth()

        if abs(current_actual_width - (target_width if target_width >0 else self.document().idealWidth())) > 1e-3 :
            width_changed = True

        if text_changed: self.setPlainText(text)
        # If target_width is -1, it means auto-width based on new text.
        # If target_width is positive, set fixed width.
        if width_changed or (text_changed and target_width < 0) : self.setTextWidth(target_width)

        if text_changed or width_changed : self.prepareGeometryChange(); self.update()

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged and self.scene():
            self.scene().item_moved.emit(self)
        return super().itemChange(change, value)