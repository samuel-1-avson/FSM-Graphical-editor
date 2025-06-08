# bsm_designer_project/graphics_items.py
# Significant changes to GraphicsStateItem and GraphicsTransitionItem paint methods and properties.

import math
import os # For icon path check
from PyQt5.QtWidgets import (QGraphicsRectItem, QGraphicsPathItem, QGraphicsTextItem,
                             QGraphicsItem, QGraphicsDropShadowEffect, QApplication, QGraphicsSceneMouseEvent,
                             QStyle, QLineEdit, QTextEdit, QGraphicsProxyWidget, QMessageBox)
from PyQt5.QtGui import (QBrush, QColor, QFont, QPen, QPainterPath, QPolygonF, QPainter,
                         QPainterPathStroker, QPixmap, QMouseEvent, QDrag, QPalette, QFocusEvent, QKeyEvent, QIcon) # Added QIcon
from PyQt5.QtCore import Qt, QRectF, QPointF, QMimeData, QPoint, QLineF, QSize, pyqtSignal, QEvent, QObject

from config import (
    COLOR_ITEM_STATE_DEFAULT_BG, COLOR_ITEM_STATE_DEFAULT_BORDER, APP_FONT_FAMILY,
    COLOR_TEXT_PRIMARY, COLOR_ITEM_STATE_SELECTION_BG, COLOR_ITEM_STATE_SELECTION_BORDER,
    COLOR_ITEM_TRANSITION_DEFAULT, COLOR_ITEM_TRANSITION_SELECTION,
    COLOR_ITEM_COMMENT_BG, COLOR_ITEM_COMMENT_BORDER,
    COLOR_PY_SIM_STATE_ACTIVE, COLOR_PY_SIM_STATE_ACTIVE_PEN_WIDTH,
    COLOR_BACKGROUND_LIGHT, COLOR_BORDER_LIGHT, COLOR_ACCENT_PRIMARY, COLOR_ACCENT_PRIMARY_LIGHT,
    DEFAULT_EXECUTION_ENV, COLOR_TEXT_SECONDARY, COLOR_BACKGROUND_DIALOG, COLOR_BORDER_MEDIUM,
    COLOR_TEXT_EDITOR_DARK_PRIMARY, COLOR_BACKGROUND_EDITOR_DARK, COLOR_ACCENT_SECONDARY,
    COLOR_ACCENT_WARNING,
    DEFAULT_STATE_SHAPE, DEFAULT_STATE_BORDER_STYLE, DEFAULT_STATE_BORDER_WIDTH,
    DEFAULT_TRANSITION_LINE_STYLE, DEFAULT_TRANSITION_LINE_WIDTH, DEFAULT_TRANSITION_ARROWHEAD # Added transition defaults
)
from settings_manager import SettingsManager 
from utils import get_standard_icon

import logging
logger = logging.getLogger(__name__)


class StateItemSignals(QObject):
    textChangedViaInlineEdit = pyqtSignal(str, str)

class GraphicsStateItem(QGraphicsRectItem):
    Type = QGraphicsItem.UserType + 1

    def type(self): return GraphicsStateItem.Type

    def __init__(self, x, y, w, h, text, is_initial=False, is_final=False,
                 color=None, entry_action="", during_action="", exit_action="", description="",
                 is_superstate=False, sub_fsm_data=None, action_language=DEFAULT_EXECUTION_ENV,
                 shape_type=None, font_family=None, font_size=None, font_bold=None, font_italic=None,
                 border_style_qt=None, custom_border_width=None, icon_path=None
                 ):
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

        settings = QApplication.instance().settings_manager if QApplication.instance() and hasattr(QApplication.instance(), 'settings_manager') else None

        self.shape_type = shape_type if shape_type is not None else (settings.get("state_default_shape") if settings else DEFAULT_STATE_SHAPE)
        
        _font_family = font_family if font_family is not None else (settings.get("state_default_font_family") if settings else APP_FONT_FAMILY)
        _font_size = font_size if font_size is not None else (settings.get("state_default_font_size") if settings else 10)
        _font_bold = font_bold if font_bold is not None else (settings.get("state_default_font_bold") if settings else True)
        _font_italic = font_italic if font_italic is not None else (settings.get("state_default_font_italic") if settings else False)
        self._font = QFont(_font_family, _font_size)
        if _font_bold: self._font.setBold(True)
        if _font_italic: self._font.setItalic(True)

        self.custom_border_width = custom_border_width if custom_border_width is not None else (settings.get("state_default_border_width") if settings else DEFAULT_STATE_BORDER_WIDTH)
        
        if border_style_qt is not None:
            self.border_style_qt = border_style_qt
        elif settings:
            style_str = settings.get("state_default_border_style_str")
            self.border_style_qt = SettingsManager.STRING_TO_QT_PEN_STYLE.get(style_str, DEFAULT_STATE_BORDER_STYLE)
        else:
            self.border_style_qt = DEFAULT_STATE_BORDER_STYLE


        self.icon_path = icon_path
        self._q_icon: QPixmap | None = None
        self._load_custom_icon()

        self.base_color = QColor(color) if color and QColor(color).isValid() else QColor(COLOR_ITEM_STATE_DEFAULT_BG)
        self.border_color = QColor(color).darker(120) if color and QColor(color).isValid() else QColor(COLOR_ITEM_STATE_DEFAULT_BORDER)

        self.action_language = action_language
        self.entry_action = entry_action
        self.during_action = during_action
        self.exit_action = exit_action
        self.description = description

        self._text_color = QColor(COLOR_TEXT_PRIMARY) 
        self._superstate_border_pen_width_multiplier = 1.3 
        self.original_pen = QPen(self.border_color, self.custom_border_width, self.border_style_qt)
        self.setPen(QPen(self.original_pen))
        self.setBrush(QBrush(self.base_color))

        self.setFlags(QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsMovable |
                      QGraphicsItem.ItemSendsGeometryChanges | QGraphicsItem.ItemIsFocusable)
        self.setAcceptHoverEvents(True)
        self.setToolTip(self.description or self.text_label) 

        self.shadow_effect = QGraphicsDropShadowEffect()
        self.shadow_effect.setBlurRadius(12)
        self.shadow_effect.setColor(QColor(0, 0, 0, 45))
        self.shadow_effect.setOffset(3, 3)
        self.setGraphicsEffect(self.shadow_effect)


        self.is_py_sim_active = False
        self._is_problematic = False
        self._problem_tooltip_text = ""
        self._is_potential_transition_target = False # New flag

        self._inline_editor_proxy: QGraphicsProxyWidget | None = None
        self._is_editing_inline = False
        self._inline_edit_aborted = False

    def _load_custom_icon(self):
        if self.icon_path and os.path.exists(self.icon_path): # Check if path exists
            self._q_icon = QPixmap(self.icon_path)
            if self._q_icon.isNull():
                logger.warning(f"Failed to load custom icon for state '{self.text_label}' from path: {self.icon_path}")
                self._q_icon = None
        else:
            self._q_icon = None


    def _determine_current_pen(self) -> QPen:
        current_base_width = self.custom_border_width
        if self.is_superstate:
            current_base_width *= self._superstate_border_pen_width_multiplier
        
        current_base_style = self.border_style_qt
        current_base_color = self.border_color

        pen_to_use = QPen(current_base_color, current_base_width, current_base_style)

        if self.is_py_sim_active:
            pen_to_use.setColor(COLOR_PY_SIM_STATE_ACTIVE)
            pen_to_use.setWidthF(max(current_base_width, COLOR_PY_SIM_STATE_ACTIVE_PEN_WIDTH)) 
            pen_to_use.setStyle(Qt.SolidLine) 
        elif self._is_problematic:
            pen_to_use.setColor(QColor(COLOR_ACCENT_WARNING))
            pen_to_use.setWidthF(current_base_width + 0.7)
            pen_to_use.setStyle(Qt.DashDotLine)
        
        return pen_to_use

    def paint(self, painter: QPainter, option, widget):
        painter.setRenderHint(QPainter.Antialiasing)
        current_rect = self.rect()
        border_radius = 12 

        current_pen_for_drawing = self._determine_current_pen()
        current_brush_for_drawing = self.brush() # Start with base brush

        # Apply potential transition target highlight
        if self._is_potential_transition_target and not self.isSelected() and not self.is_py_sim_active:
            # Use a distinct highlight color and slightly thicker pen or overlay
            highlight_color = QColor(COLOR_ACCENT_PRIMARY)
            current_pen_for_drawing = QPen(highlight_color, current_pen_for_drawing.widthF() + 1, Qt.SolidLine)
            # Optionally, slightly change brush for overlay effect
            overlay_brush_color = QColor(highlight_color)
            overlay_brush_color.setAlpha(50) # Translucent overlay
            current_brush_for_drawing = QBrush(overlay_brush_color)


        painter.setPen(current_pen_for_drawing)
        painter.setBrush(current_brush_for_drawing)


        if self.shape_type == "ellipse":
            painter.drawEllipse(current_rect)
        else: 
            painter.drawRoundedRect(current_rect, border_radius, border_radius)


        if not self._is_editing_inline:
            painter.setPen(self._text_color) 
            painter.setFont(self._font) 
            text_rect = current_rect.adjusted(10, 10, -10, -10)
            if self.is_superstate or self._q_icon: 
                text_rect.setRight(text_rect.right() - 18)
            
            if self.shape_type == "ellipse":
                ellipse_text_margin_x = current_rect.width() * 0.2
                ellipse_text_margin_y = current_rect.height() * 0.2
                text_rect = current_rect.adjusted(ellipse_text_margin_x, ellipse_text_margin_y,
                                                  -ellipse_text_margin_x, -ellipse_text_margin_y)

            painter.drawText(text_rect, Qt.AlignCenter | Qt.TextWordWrap, self.text_label)

        if self._q_icon and not self._q_icon.isNull():
            icon_size = 16; margin = 5
            icon_x = current_rect.right() - icon_size - margin
            if self.is_superstate:
                icon_x -= (icon_size + margin / 2) 
            
            icon_rect = QRectF(icon_x, current_rect.top() + margin, icon_size, icon_size)
            painter.drawPixmap(icon_rect.topLeft(), self._q_icon.scaled(icon_size, icon_size, Qt.KeepAspectRatio, Qt.SmoothTransformation))


        if self.is_initial:
            marker_radius = 7; line_length = 20; marker_color = QColor(COLOR_TEXT_PRIMARY) 
            start_marker_center_x = current_rect.left() - line_length - marker_radius / 2
            start_marker_center_y = current_rect.center().y()
            painter.setBrush(marker_color); painter.setPen(QPen(marker_color, self.custom_border_width + 0.5)) 
            painter.drawEllipse(QPointF(start_marker_center_x, start_marker_center_y), marker_radius, marker_radius)
            line_start_point = QPointF(start_marker_center_x + marker_radius, start_marker_center_y)
            line_end_point = QPointF(current_rect.left(), start_marker_center_y)
            painter.drawLine(line_start_point, line_end_point)
            arrow_size = 9; angle_rad = 0
            arrow_p1 = QPointF(line_end_point.x() - arrow_size * math.cos(angle_rad + math.pi / 6), line_end_point.y() - arrow_size * math.sin(angle_rad + math.pi / 6))
            arrow_p2 = QPointF(line_end_point.x() - arrow_size * math.cos(angle_rad - math.pi / 6), line_end_point.y() - arrow_size * math.sin(angle_rad - math.pi / 6))
            painter.drawPolygon(QPolygonF([line_end_point, arrow_p1, arrow_p2]))


        if self.is_final:
            inner_border_color = current_pen_for_drawing.color().darker(130)
            inner_border_pen = QPen(inner_border_color, self.custom_border_width) 
            painter.setPen(inner_border_pen)
            
            inner_margin = 6
            if self.shape_type == "ellipse":
                inner_rect_ellipse = current_rect.adjusted(inner_margin, inner_margin, -inner_margin, -inner_margin)
                painter.drawEllipse(inner_rect_ellipse)
            else:
                inner_rect_rounded = current_rect.adjusted(inner_margin, inner_margin, -inner_margin, -inner_margin)
                painter.drawRoundedRect(inner_rect_rounded, border_radius - 4, border_radius - 4)


        if self.is_superstate:
            icon_size = 16; margin = 5
            icon_rect = QRectF(current_rect.right() - icon_size - margin, current_rect.top() + margin, icon_size, icon_size)
            superstate_icon = get_standard_icon(QStyle.SP_FileDialogDetailedView, "Superstate")
            if not superstate_icon.isNull():
                painter.drawPixmap(icon_rect.topLeft(), superstate_icon.pixmap(icon_size, icon_size))

        # Selection highlight drawn on top of potential target highlight
        if self.isSelected() and not self.is_py_sim_active:
            selection_pen_width = self.custom_border_width + 0.5 # Use custom_border_width for consistency
            selection_pen = QPen(QColor(COLOR_ITEM_STATE_SELECTION_BORDER), selection_pen_width, Qt.DashLine)
            selection_brush_color = QColor(COLOR_ITEM_STATE_SELECTION_BG); selection_brush_color.setAlpha(80)
            selection_rect = self.boundingRect().adjusted(-1, -1, 1, 1)
            painter.setPen(selection_pen); painter.setBrush(QBrush(selection_brush_color))
            if self.shape_type == "ellipse":
                painter.drawEllipse(selection_rect)
            else:
                painter.drawRoundedRect(selection_rect, border_radius + 1, border_radius + 1)

    def set_potential_transition_target_style(self, is_target: bool):
        if self._is_potential_transition_target == is_target:
            return
        self._is_potential_transition_target = is_target
        self.update()


    def set_problematic_style(self, is_problematic: bool, problem_description: str = ""):
        if self._is_problematic == is_problematic and self._problem_tooltip_text == problem_description:
            return

        self._is_problematic = is_problematic
        self._problem_tooltip_text = problem_description if is_problematic else ""

        tooltip_to_set = self._problem_tooltip_text
        if not tooltip_to_set: 
            tooltip_to_set = self.description or self.text_label
        self.setToolTip(tooltip_to_set)
        self.update()

    def set_py_sim_active_style(self, active: bool):
        if self.is_py_sim_active == active: return
        self.is_py_sim_active = active
        self.update()

    def set_properties(self, name, is_initial, is_final, color_hex=None,
                       action_language=DEFAULT_EXECUTION_ENV,
                       entry="", during="", exit_a="", desc="",
                       is_superstate_prop=None, sub_fsm_data_prop=None,
                       shape_type_prop=None, font_family_prop=None, font_size_prop=None,
                       font_bold_prop=None, font_italic_prop=None,
                       border_style_str_prop=None, border_width_prop=None, icon_path_prop=None
                       ):
        changed = False
        
        new_base_color = QColor(color_hex) if color_hex and QColor(color_hex).isValid() else QColor(COLOR_ITEM_STATE_DEFAULT_BG)
        new_border_color = new_base_color.darker(120) if color_hex and QColor(color_hex).isValid() else QColor(COLOR_ITEM_STATE_DEFAULT_BORDER)

        if self.text_label != name: self.text_label = name; changed = True
        if self.is_initial != is_initial: self.is_initial = is_initial; changed = True
        if self.is_final != is_final: self.is_final = is_final; changed = True
        if self.action_language != action_language: self.action_language = action_language; changed = True
        
        current_is_superstate = self.is_superstate
        if is_superstate_prop is not None and self.is_superstate != is_superstate_prop:
            self.is_superstate = is_superstate_prop; changed = True
        
        if self.base_color != new_base_color or self.border_color != new_border_color:
            self.base_color = new_base_color
            self.border_color = new_border_color 
            self.setBrush(self.base_color)
            changed = True
        
        if sub_fsm_data_prop is not None:
             if self.sub_fsm_data != sub_fsm_data_prop: self.sub_fsm_data = sub_fsm_data_prop; changed = True

        if self.entry_action != entry: self.entry_action = entry; changed = True
        if self.during_action != during: self.during_action = during; changed = True
        if self.exit_action != exit_a: self.exit_action = exit_a; changed = True
        if self.description != desc: self.description = desc; self.setToolTip(self._problem_tooltip_text or self.description or self.text_label); changed = True

        # --- Apply new visual properties ---
        if shape_type_prop is not None and self.shape_type != shape_type_prop:
            self.shape_type = shape_type_prop; changed = True
        
        current_font = self._font
        new_font_family = font_family_prop if font_family_prop is not None else current_font.family()
        new_font_size = font_size_prop if font_size_prop is not None else current_font.pointSize()
        new_font_bold = font_bold_prop if font_bold_prop is not None else current_font.bold()
        new_font_italic = font_italic_prop if font_italic_prop is not None else current_font.italic()

        if current_font.family() != new_font_family or \
           current_font.pointSize() != new_font_size or \
           current_font.bold() != new_font_bold or \
           current_font.italic() != new_font_italic:
            self._font = QFont(new_font_family, new_font_size)
            if new_font_bold: self._font.setBold(True)
            if new_font_italic: self._font.setItalic(True)
            changed = True
            
        if border_width_prop is not None and self.custom_border_width != border_width_prop:
            self.custom_border_width = border_width_prop; changed = True
        
        if border_style_str_prop is not None:
            new_qt_style = SettingsManager.STRING_TO_QT_PEN_STYLE.get(border_style_str_prop, Qt.SolidLine)
            if self.border_style_qt != new_qt_style:
                self.border_style_qt = new_qt_style; changed = True
        
        if icon_path_prop != self.icon_path: # Handles None vs path and path changes
            self.icon_path = icon_path_prop
            self._load_custom_icon() # Reload or clear the QPixmap
            changed = True
        
        if changed: 
            self.original_pen = QPen(self.border_color, self.custom_border_width, self.border_style_qt)
            self.prepareGeometryChange()
            self.update()

    def get_data(self):
        base_data = {
            'name': self.text_label, 'x': self.x(), 'y': self.y(), 
            'width': self.rect().width(), 'height': self.rect().height(),
            'is_initial': self.is_initial, 'is_final': self.is_final, 
            'color': self.base_color.name() if self.base_color else QColor(COLOR_ITEM_STATE_DEFAULT_BG).name(),
            'action_language': self.action_language, 'entry_action': self.entry_action, 
            'during_action': self.during_action, 'exit_action': self.exit_action, 
            'description': self.description, 
            'is_superstate': self.is_superstate, 'sub_fsm_data': self.sub_fsm_data,
            'shape_type': self.shape_type,
            'font_family': self._font.family(),
            'font_size': self._font.pointSize(),
            'font_bold': self._font.bold(),
            'font_italic': self._font.italic(),
            'border_style_str': SettingsManager.QT_PEN_STYLE_TO_STRING.get(self.border_style_qt, "Solid"),
            'border_width': self.custom_border_width,
            'icon_path': self.icon_path
        }
        return base_data

    def start_inline_edit(self): 
        if self._is_editing_inline or not self.scene(): return
        self._is_editing_inline = True; self._inline_edit_aborted = False; self.update()
        editor = QLineEdit(self.text_label); editor.setFont(self._font); editor.setAlignment(Qt.AlignCenter) 
        editor.setStyleSheet(f"QLineEdit {{ background-color: {self.base_color.lighter(110).name()}; color: {self._text_color.name()}; border: 1px solid {self.border_color.name()}; border-radius: {self.rect().height() / 6}px; padding: 5px; }}")
        text_rect_local = self.rect().adjusted(8, 8, -8, -8)
        if self.is_superstate or self._q_icon: text_rect_local.setRight(text_rect_local.right() -18)
        editor.selectAll(); editor.editingFinished.connect(lambda: self._finish_inline_edit(editor)); editor.keyPressEvent = lambda event: self._handle_editor_key_press(event, editor)
        self._inline_editor_proxy = QGraphicsProxyWidget(self); self._inline_editor_proxy.setWidget(editor); self._inline_editor_proxy.setPos(text_rect_local.topLeft())
        editor.setFixedSize(text_rect_local.size().toSize()); editor.setFocus(Qt.MouseFocusReason)

    def _handle_editor_key_press(self, event: QKeyEvent, editor_widget: QLineEdit):
        if event.key() == Qt.Key_Escape: self._inline_edit_aborted = True; editor_widget.clearFocus()
        elif event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter: self._inline_edit_aborted = False; editor_widget.clearFocus()
        else: QLineEdit.keyPressEvent(editor_widget, event)

    def _finish_inline_edit(self, editor_widget: QLineEdit | None = None):
        if not self._is_editing_inline: return
        actual_editor = editor_widget if editor_widget else (self._inline_editor_proxy.widget() if self._inline_editor_proxy else None)
        if not actual_editor: self._is_editing_inline = False; self.update(); return
        new_text = actual_editor.text().strip(); old_text = self.text_label
        if self._inline_editor_proxy:
            self._inline_editor_proxy.setWidget(None)
            if self._inline_editor_proxy.scene(): self.scene().removeItem(self._inline_editor_proxy)
            self._inline_editor_proxy.deleteLater(); self._inline_editor_proxy = None
        self._is_editing_inline = False
        if self._inline_edit_aborted: self.update(); return
        if not new_text: QMessageBox.warning(None, "Invalid Name", "State name cannot be empty."); self.update(); return
        if new_text != old_text:
            if self.scene() and hasattr(self.scene(), 'get_state_by_name'):
                existing_state = self.scene().get_state_by_name(new_text)
                if existing_state and existing_state != self: QMessageBox.warning(None, "Duplicate Name", f"A state named '{new_text}' already exists. Edit cancelled."); self.update(); return
            old_props = self.get_data(); self.text_label = new_text; new_props = self.get_data()
            if self.scene() and hasattr(self.scene(), 'undo_stack'):
                from undo_commands import EditItemPropertiesCommand # Local import
                cmd = EditItemPropertiesCommand(self, old_props, new_props, "Rename State"); self.scene().undo_stack.push(cmd); self.scene().set_dirty(True)
            if hasattr(self.signals, 'textChangedViaInlineEdit'): self.signals.textChangedViaInlineEdit.emit(old_text, new_text)
            if self.scene() and hasattr(self.scene(), '_update_transitions_for_renamed_state'): self.scene()._update_transitions_for_renamed_state(old_text, new_text)
        self.setToolTip(self._problem_tooltip_text or self.description or self.text_label) 
        self.update()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_F2 and self.isSelected() and self.flags() & QGraphicsItem.ItemIsFocusable:
            if not self._is_editing_inline: self.start_inline_edit(); event.accept()
        else: super().keyPressEvent(event)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged and self.scene(): self.scene().item_moved.emit(self)
        return super().itemChange(change, value)

    def set_text(self, text):
        if self.text_label != text: self.prepareGeometryChange(); self.text_label = text; self.setToolTip(self._problem_tooltip_text or self.description or self.text_label); self.update()


class GraphicsTransitionItem(QGraphicsPathItem):
    Type = QGraphicsItem.UserType + 2
    def type(self): return GraphicsTransitionItem.Type
    CONTROL_POINT_SIZE = 8
    def __init__(self, start_item, end_item, event_str="", condition_str="", action_str="", color=None, description="", action_language=DEFAULT_EXECUTION_ENV,
                 line_style_qt=None, custom_line_width=None, arrowhead_style=None,
                 label_font_family=None, label_font_size=None):
        super().__init__()
        self.start_item: GraphicsStateItem | None = start_item; self.end_item: GraphicsStateItem | None = end_item
        self.event_str = event_str; self.condition_str = condition_str; self.action_language = action_language; self.action_str = action_str
        self.base_color = QColor(color) if color and QColor(color).isValid() else QColor(COLOR_ITEM_TRANSITION_DEFAULT)
        self.description = description
        self.arrow_size = 11
        
        settings = QApplication.instance().settings_manager if QApplication.instance() and hasattr(QApplication.instance(), 'settings_manager') else None

        _label_font_family = label_font_family if label_font_family is not None else (settings.get("transition_default_font_family") if settings else APP_FONT_FAMILY)
        _label_font_size = label_font_size if label_font_size is not None else (settings.get("transition_default_font_size") if settings else 8)
        self._font = QFont(_label_font_family, _label_font_size) 

        self.custom_line_width = custom_line_width if custom_line_width is not None else (settings.get("transition_default_line_width") if settings else DEFAULT_TRANSITION_LINE_WIDTH)
        
        if line_style_qt is not None:
            self.line_style_qt = line_style_qt
        elif settings:
            style_str = settings.get("transition_default_line_style_str")
            self.line_style_qt = SettingsManager.STRING_TO_QT_PEN_STYLE.get(style_str, DEFAULT_TRANSITION_LINE_STYLE)
        else:
            self.line_style_qt = DEFAULT_TRANSITION_LINE_STYLE
            
        self.arrowhead_style = arrowhead_style if arrowhead_style is not None else (settings.get("transition_default_arrowhead_style") if settings else DEFAULT_TRANSITION_ARROWHEAD)

        self._text_color = QColor(COLOR_TEXT_PRIMARY) 
        self.control_point_offset = QPointF(0,0)
        
        self.original_pen = QPen(self.base_color, self.custom_line_width, self.line_style_qt, Qt.RoundCap, Qt.RoundJoin)
        self.setPen(QPen(self.original_pen))
        
        self.setFlag(QGraphicsItem.ItemIsSelectable, True); self.setFlag(QGraphicsItem.ItemIsFocusable, True)
        self.setZValue(-1); self.setAcceptHoverEvents(True)
        self.setToolTip(self.description or self._compose_label_string())
        self.shadow_effect = QGraphicsDropShadowEffect(); self.shadow_effect.setBlurRadius(8); self.shadow_effect.setColor(QColor(0, 0, 0, 50)); self.shadow_effect.setOffset(1.5, 1.5); self.setGraphicsEffect(self.shadow_effect)
        self._dragging_control_point = False; self._last_mouse_press_pos_for_cp_drag = QPointF(); self._initial_cp_offset_on_drag_start = QPointF()
        self.is_py_sim_active = False
        self._is_problematic = False
        self._problem_tooltip_text = ""
        self.update_path()

    def _determine_current_pen(self) -> QPen:
        pen_to_use = QPen(self.base_color, self.custom_line_width, self.line_style_qt, Qt.RoundCap, Qt.RoundJoin)
        if self.is_py_sim_active:
            highlight_color = QColor(COLOR_PY_SIM_STATE_ACTIVE).lighter(110)
            if highlight_color == self.base_color : highlight_color = QColor(COLOR_ACCENT_SECONDARY)
            pen_to_use.setColor(highlight_color)
            pen_to_use.setWidthF(self.custom_line_width + 1.2)
            pen_to_use.setStyle(Qt.SolidLine) 
        elif self._is_problematic:
            pen_to_use.setColor(QColor(COLOR_ACCENT_WARNING))
            pen_to_use.setWidthF(self.custom_line_width + 0.7)
            pen_to_use.setStyle(Qt.DashDotLine)
        return pen_to_use
    
    def paint(self, painter: QPainter, option, widget):
        if not self.start_item or not self.end_item or self.path().isEmpty(): return
        painter.setRenderHint(QPainter.Antialiasing)
        current_pen_for_drawing = self._determine_current_pen()

        if self.isSelected() and not self.is_py_sim_active:
            stroker = QPainterPathStroker(); stroker.setWidth(current_pen_for_drawing.widthF() + 8); stroker.setCapStyle(Qt.RoundCap); stroker.setJoinStyle(Qt.RoundJoin)
            selection_path_shape = stroker.createStroke(self.path()); highlight_color = QColor(COLOR_ITEM_TRANSITION_SELECTION); highlight_color.setAlpha(150)
            painter.setPen(QPen(highlight_color, 1, Qt.SolidLine)); painter.setBrush(highlight_color); painter.drawPath(selection_path_shape)
            cp_rect = self._get_control_point_rect()
            if not cp_rect.isEmpty(): painter.setPen(QPen(QColor(COLOR_ACCENT_PRIMARY), 1.5)); fill_color = QColor(COLOR_ACCENT_PRIMARY_LIGHT); fill_color.setAlpha(200); painter.setBrush(fill_color); painter.drawEllipse(cp_rect)


        painter.setPen(current_pen_for_drawing)
        painter.setBrush(Qt.NoBrush) 
        painter.drawPath(self.path())

        if self.path().elementCount() < 1 or self.arrowhead_style == "none": return 
        
        line_end_point = self.path().pointAtPercent(1.0); path_len = self.path().length()
        tangent_point_percent = max(0.0, 1.0 - (self.arrow_size * 1.2 / (path_len + 1e-6)))
        if path_len < self.arrow_size * 1.5 : tangent_point_percent = max(0.0, 0.8 if path_len > 0 else 0.0)
        angle_at_end_rad = -self.path().angleAtPercent(tangent_point_percent) * (math.pi / 180.0)
        
        arrow_polygon = QPolygonF()
        arrow_polygon.append(line_end_point)
        arrow_polygon.append(line_end_point + QPointF(math.cos(angle_at_end_rad - math.pi / 7) * self.arrow_size, math.sin(angle_at_end_rad - math.pi / 7) * self.arrow_size))
        arrow_polygon.append(line_end_point + QPointF(math.cos(angle_at_end_rad + math.pi / 7) * self.arrow_size, math.sin(angle_at_end_rad + math.pi / 7) * self.arrow_size))
        
        painter.setPen(current_pen_for_drawing) 
        if self.arrowhead_style == "filled":
            painter.setBrush(current_pen_for_drawing.color())
        else: 
            painter.setBrush(Qt.NoBrush)
        painter.drawPolygon(arrow_polygon)


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


    def set_properties(self, event_str="", condition_str="", action_str="", color_hex=None, description="", offset=None, action_language=DEFAULT_EXECUTION_ENV,
                       line_style_str_prop=None, line_width_prop=None, arrowhead_style_prop=None,
                       label_font_family_prop=None, label_font_size_prop=None):
        changed = False
        
        new_color = QColor(color_hex) if color_hex and QColor(color_hex).isValid() else QColor(COLOR_ITEM_TRANSITION_DEFAULT)
        if self.base_color != new_color:
            self.base_color = new_color; changed = True

        if self.event_str != event_str: self.event_str = event_str; changed=True
        if self.condition_str != condition_str: self.condition_str = condition_str; changed=True
        if self.action_language != action_language: self.action_language = action_language; changed=True
        if self.action_str != action_str: self.action_str = action_str; changed=True
        if self.description != description: self.description = description; self.setToolTip(self._problem_tooltip_text or self.description or self._compose_label_string()) ; changed=True
        if offset is not None and self.control_point_offset != QPointF(offset):
             self.control_point_offset = QPointF(offset); changed = True
        
        current_font = self._font
        new_label_font_family = label_font_family_prop if label_font_family_prop is not None else current_font.family()
        new_label_font_size = label_font_size_prop if label_font_size_prop is not None else current_font.pointSize()
        if current_font.family() != new_label_font_family or current_font.pointSize() != new_label_font_size:
            self._font = QFont(new_label_font_family, new_label_font_size); changed = True
            
        if line_width_prop is not None and self.custom_line_width != line_width_prop:
            self.custom_line_width = line_width_prop; changed = True
            
        if line_style_str_prop is not None:
            new_qt_style = SettingsManager.STRING_TO_QT_PEN_STYLE.get(line_style_str_prop, Qt.SolidLine)
            if self.line_style_qt != new_qt_style:
                self.line_style_qt = new_qt_style; changed = True
                
        if arrowhead_style_prop is not None and self.arrowhead_style != arrowhead_style_prop:
            self.arrowhead_style = arrowhead_style_prop; changed = True

        if changed: 
            self.original_pen = QPen(self.base_color, self.custom_line_width, self.line_style_qt, Qt.RoundCap, Qt.RoundJoin)
            self.prepareGeometryChange()
            self.update_path() 
            self.update()
    
    def get_data(self):
        return {
            'source': self.start_item.text_label if self.start_item else "None", 
            'target': self.end_item.text_label if self.end_item else "None", 
            'event': self.event_str, 'condition': self.condition_str, 
            'action_language': self.action_language, 'action': self.action_str, 
            'color': self.base_color.name() if self.base_color else QColor(COLOR_ITEM_TRANSITION_DEFAULT).name(), 
            'description': self.description, 
            'control_offset_x': self.control_point_offset.x(), 
            'control_offset_y': self.control_point_offset.y(),
            'line_style_str': SettingsManager.QT_PEN_STYLE_TO_STRING.get(self.line_style_qt, "Solid"),
            'line_width': self.custom_line_width,
            'arrowhead_style': self.arrowhead_style,
            'label_font_family': self._font.family(),
            'label_font_size': self._font.pointSize()
        }

    def set_problematic_style(self, is_problematic: bool, problem_description: str = ""):
        if self._is_problematic == is_problematic and self._problem_tooltip_text == problem_description: return
        self._is_problematic = is_problematic; self._problem_tooltip_text = problem_description if is_problematic else ""
        tooltip_to_set = self._problem_tooltip_text or self.description or self._compose_label_string()
        self.setToolTip(tooltip_to_set); self.update()
    def set_py_sim_active_style(self, active: bool):
        if self.is_py_sim_active == active: return
        self.is_py_sim_active = active; self.update()
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
        length = math.hypot(dx, dy); length = 1e-6 if length < 1e-6 else length
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
    def hoverEnterEvent(self, event: QGraphicsSceneMouseEvent): self.update(); super().hoverEnterEvent(event) 
    def hoverLeaveEvent(self, event: QGraphicsSceneMouseEvent): self.update(); super().hoverLeaveEvent(event) 
    def boundingRect(self): 
        extra = (self._determine_current_pen().widthF() + self.arrow_size) / 2.0 + 30; path_bounds = self.path().boundingRect()
        current_label = self._compose_label_string()
        if current_label:
            from PyQt5.QtGui import QFontMetrics; fm = QFontMetrics(self._font); text_bounding_rect_for_calculation = QRectF(0,0, 300, 100)
            text_actual_rect = fm.boundingRect(text_bounding_rect_for_calculation.toRect(), Qt.TextWordWrap | Qt.AlignCenter, current_label)
            mid_point_on_path = self.path().pointAtPercent(0.5); text_render_rect = QRectF(mid_point_on_path.x() - text_actual_rect.width()/2 - 10, mid_point_on_path.y() - text_actual_rect.height() - 10, text_actual_rect.width() + 20, text_actual_rect.height() + 20)
            path_bounds = path_bounds.united(text_render_rect)
        cp_rect = self._get_control_point_rect()
        if not cp_rect.isEmpty(): path_bounds = path_bounds.united(cp_rect.adjusted(-self.CONTROL_POINT_SIZE, -self.CONTROL_POINT_SIZE, self.CONTROL_POINT_SIZE, self.CONTROL_POINT_SIZE))
        return path_bounds.adjusted(-extra, -extra, extra, extra)
    def shape(self): 
        path_stroker = QPainterPathStroker(); path_stroker.setWidth(20 + self._determine_current_pen().widthF()); path_stroker.setCapStyle(Qt.RoundCap); path_stroker.setJoinStyle(Qt.RoundJoin)
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
        item_rect = item.sceneBoundingRect(); 
        
        if isinstance(item, GraphicsStateItem) and item.shape_type == "ellipse":
            ellipse_path = QPainterPath()
            ellipse_path.addEllipse(item_rect)
            temp_path = QPainterPath(line.p1()); temp_path.lineTo(line.p2())
            intersect_path = ellipse_path.intersected(temp_path)
            if not intersect_path.isEmpty() and intersect_path.elementCount() > 0:
                return QPointF(intersect_path.elementAt(0).x, intersect_path.elementAt(0).y)
            return item_rect.center() 


        rect_path = QPainterPath(); 
        if isinstance(item, GraphicsStateItem) and item.shape_type == "rectangle":
            rect_path.addRoundedRect(item_rect, 12, 12) 
        else: 
            rect_path.addRect(item_rect)


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
            intersection_point_var = QPointF();
            intersect_type = line.intersect(edge, intersection_point_var)
            if intersect_type == QLineF.BoundedIntersection: intersect_points.append(QPointF(intersection_point_var))
        if not intersect_points: return item_rect.center()
        intersect_points.sort(key=lambda pt: QLineF(line.p1(), pt).length()); return intersect_points[0]

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
    
    def set_control_point_offset(self, offset: QPointF):
        if self.control_point_offset != offset: self.control_point_offset = offset; self.prepareGeometryChange(); self.update_path(); self.update()


class GraphicsCommentItem(QGraphicsTextItem):
    Type = QGraphicsItem.UserType + 3
    textChangedViaInlineEdit = pyqtSignal(str, str)
    def type(self): return GraphicsCommentItem.Type
    def __init__(self, x, y, text="Comment",
                 font_family=None, font_size=None, font_italic=None):
        super().__init__(); self.setPlainText(text); self.setPos(x, y)
        
        settings = QApplication.instance().settings_manager if QApplication.instance() and hasattr(QApplication.instance(), 'settings_manager') else None
        _font_family = font_family if font_family is not None else (settings.get("comment_default_font_family") if settings else APP_FONT_FAMILY)
        _font_size = font_size if font_size is not None else (settings.get("comment_default_font_size") if settings else 9)
        _font_italic = font_italic if font_italic is not None else (settings.get("comment_default_font_italic") if settings else True)
        self._custom_font = QFont(_font_family, _font_size)
        if _font_italic: self._custom_font.setItalic(True)
        self.setFont(self._custom_font) 
        
        self.setTextInteractionFlags(Qt.TextEditorInteraction)
        self.setFlags(QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemSendsGeometryChanges | QGraphicsItem.ItemIsFocusable)
        self._default_width = 160; self.setTextWidth(self._default_width)
        self.original_border_pen = QPen(QColor(COLOR_ITEM_COMMENT_BORDER), 1.2)
        self.border_pen = QPen(self.original_border_pen)
        self.background_brush = QBrush(QColor(COLOR_ITEM_COMMENT_BG))
        self.shadow_effect = QGraphicsDropShadowEffect(); self.shadow_effect.setBlurRadius(10); self.shadow_effect.setColor(QColor(0, 0, 0, 40)); self.shadow_effect.setOffset(2.5, 2.5); self.setGraphicsEffect(self.shadow_effect)
        self.setDefaultTextColor(QColor(COLOR_TEXT_PRIMARY).darker(110)) 
        if self.document(): self.document().contentsChanged.connect(self._on_contents_changed)
        self._inline_editor_proxy: QGraphicsProxyWidget | None = None; self._is_editing_inline = False
        self.setFlag(QGraphicsItem.ItemIsFocusable, True)
        self._inline_edit_aborted = False
        self._is_problematic = False
        self._problem_tooltip_text = ""
        self.description = text 
        self.setToolTip(self.description)

    def _determine_current_pen(self) -> QPen:
        if self._is_problematic:
            return QPen(QColor(COLOR_ACCENT_WARNING), self.original_border_pen.widthF() + 0.5, Qt.DashDotLine)
        return QPen(self.original_border_pen)

    def paint(self, painter, option, widget):
        painter.setRenderHint(QPainter.Antialiasing)
        current_pen_for_drawing = self._determine_current_pen()
        painter.setPen(current_pen_for_drawing)
        painter.setBrush(self.background_brush)
        rect = self.boundingRect(); painter.drawRoundedRect(rect.adjusted(0.5,0.5,-0.5,-0.5), 5, 5)
        if not self._is_editing_inline:
            super().paint(painter, option, widget)
        if self.isSelected() and not self._is_editing_inline:
            selection_pen = QPen(QColor(COLOR_ACCENT_PRIMARY), 1.8, Qt.DashLine)
            painter.setPen(selection_pen); painter.setBrush(Qt.NoBrush); painter.drawRoundedRect(self.boundingRect().adjusted(-1,-1,1,1), 6, 6)

    def set_properties(self, text, width=None,
                       font_family_prop=None, font_size_prop=None, font_italic_prop=None):
        current_text = self.toPlainText(); text_changed = (current_text != text)
        width_changed = False
        target_width = float(width) if width is not None and float(width) > 0 else -1
        current_actual_width = self.textWidth()
        if current_actual_width < 0: current_actual_width = self.document().idealWidth() if self.document() else self._default_width
        if abs(current_actual_width - (target_width if target_width >0 else (self.document().idealWidth() if self.document() else self._default_width))) > 1e-3 :
            width_changed = True

        if text_changed: self.setPlainText(text); self.description = text; self.setToolTip(self._problem_tooltip_text or self.description)
        if width_changed or (text_changed and target_width < 0) : self.setTextWidth(target_width)
        
        font_props_changed = False
        current_font = self.font() 
        new_font_family = font_family_prop if font_family_prop is not None else current_font.family()
        new_font_size = font_size_prop if font_size_prop is not None else current_font.pointSize()
        new_font_italic = font_italic_prop if font_italic_prop is not None else current_font.italic()

        if current_font.family() != new_font_family or \
           current_font.pointSize() != new_font_size or \
           current_font.italic() != new_font_italic:
            self._custom_font = QFont(new_font_family, new_font_size)
            if new_font_italic: self._custom_font.setItalic(True)
            self.setFont(self._custom_font)
            font_props_changed = True
        
        if text_changed or width_changed or font_props_changed : 
            self.prepareGeometryChange(); self.update()

    def get_data(self):
        doc_width = self.textWidth()
        if doc_width < 0 : doc_width = self.document().idealWidth() if self.document() else self._default_width
        current_font = self.font()
        return {
            'text': self.toPlainText(), 'x': self.x(), 'y': self.y(), 'width': doc_width,
            'font_family': current_font.family(),
            'font_size': current_font.pointSize(),
            'font_italic': current_font.italic()
        }
    def set_problematic_style(self, is_problematic: bool, problem_description: str = ""):
        if self._is_problematic == is_problematic and self._problem_tooltip_text == problem_description: return
        self._is_problematic = is_problematic; self._problem_tooltip_text = problem_description if is_problematic else ""
        tooltip_to_set = self._problem_tooltip_text or self.toPlainText()
        self.setToolTip(tooltip_to_set); self.border_pen = self._determine_current_pen(); self.update()
    def _on_contents_changed(self): self.prepareGeometryChange(); self.update()
    def start_inline_edit(self): 
        if self._is_editing_inline or not self.scene(): return
        self._is_editing_inline = True; self._inline_edit_aborted = False; self.update()
        editor = QTextEdit(self.toPlainText()); editor.setFont(self.font()) 
        current_doc_width = self.document().idealWidth() if self.textWidth() < 0 else self.textWidth()
        current_doc_height = self.document().size().height()
        editor_width = int(max(current_doc_width, self._default_width * 0.8)) + 20
        editor_height = int(current_doc_height) + 20
        editor.setFixedSize(editor_width, editor_height)
        editor.setStyleSheet(f"QTextEdit {{ background-color: {QColor(COLOR_ITEM_COMMENT_BG).lighter(102).name()}; color: {self.defaultTextColor().name()}; border: 1px solid {QColor(COLOR_ITEM_COMMENT_BORDER).darker(110).name()}; border-radius: 3px; padding: 4px; }}")
        editor.installEventFilter(self); self._inline_editor_proxy = QGraphicsProxyWidget(self); self._inline_editor_proxy.setWidget(editor)
        self._inline_editor_proxy.setPos(0,0); editor.setFocus(Qt.MouseFocusReason)
        cursor = editor.textCursor(); cursor.movePosition(cursor.End); editor.setTextCursor(cursor)
    def eventFilter(self, watched_object, event): 
        if self._is_editing_inline and self._inline_editor_proxy and watched_object == self._inline_editor_proxy.widget():
            if event.type() == QEvent.FocusOut: self._finish_inline_edit(self._inline_editor_proxy.widget()); return True
            elif event.type() == QEvent.KeyPress:
                key_event = QKeyEvent(event)
                if key_event.key() == Qt.Key_Escape: self._inline_edit_aborted = True; self._inline_editor_proxy.widget().clearFocus(); return True
                elif key_event.key() in (Qt.Key_Return, Qt.Key_Enter) and not (key_event.modifiers() & Qt.ShiftModifier): self._inline_edit_aborted = False; self._inline_editor_proxy.widget().clearFocus(); return True
        return super().eventFilter(watched_object, event)
    def _finish_inline_edit(self, editor_widget: QTextEdit | None = None): 
        if not self._is_editing_inline: return
        actual_editor = editor_widget if editor_widget else (self._inline_editor_proxy.widget() if self._inline_editor_proxy else None)
        if not actual_editor: self._is_editing_inline = False; self.update(); return
        new_text = actual_editor.toPlainText(); old_text = self.toPlainText()
        if self._inline_editor_proxy:
            actual_editor.removeEventFilter(self); self._inline_editor_proxy.setWidget(None); actual_editor.deleteLater()
            if self._inline_editor_proxy.scene(): self.scene().removeItem(self._inline_editor_proxy)
            self._inline_editor_proxy.deleteLater(); self._inline_editor_proxy = None
        self._is_editing_inline = False
        if self._inline_edit_aborted:
            if new_text.strip() != old_text.strip(): self.setPlainText(old_text)
            self.update(); return
        if not new_text.strip() and old_text.strip(): QMessageBox.warning(None, "Empty Comment", "Comment text cannot be empty if it previously had content. Edit cancelled."); self.setPlainText(old_text); self.update(); return
        elif not new_text.strip() and not old_text.strip(): self.update(); return
        if new_text.strip() != old_text.strip():
            old_props = self.get_data(); self.setPlainText(new_text); self.description = new_text
            if self.textWidth() < 0 : self.setTextWidth(-1) 
            new_props = self.get_data()
            if self.scene() and hasattr(self.scene(), 'undo_stack'):
                from undo_commands import EditItemPropertiesCommand 
                cmd = EditItemPropertiesCommand(self, old_props, new_props, "Edit Comment Text"); self.scene().undo_stack.push(cmd); self.scene().set_dirty(True)
            if hasattr(self, 'textChangedViaInlineEdit') and isinstance(self.textChangedViaInlineEdit, pyqtSignal):
                self.textChangedViaInlineEdit.emit(old_text, new_text)
        self.setToolTip(self._problem_tooltip_text or self.description)
        self.update()
    def keyPressEvent(self, event: QKeyEvent): 
        if event.key() == Qt.Key_F2 and self.isSelected() and self.flags() & QGraphicsItem.ItemIsFocusable:
            if not self._is_editing_inline: self.start_inline_edit(); event.accept()
            return
        if self.textInteractionFlags() & Qt.TextEditorInteraction and self.hasFocus() and not self._is_editing_inline:
            if event.text() and not event.modifiers() & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier):
                 self.start_inline_edit()
                 if self._inline_editor_proxy and self._inline_editor_proxy.widget(): QApplication.sendEvent(self._inline_editor_proxy.widget(), event)
                 event.accept(); return
            else: super().keyPressEvent(event)
        elif not event.isAccepted(): QGraphicsItem.keyPressEvent(self,event)
    def itemChange(self, change, value): 
        if change == QGraphicsItem.ItemPositionHasChanged and self.scene(): self.scene().item_moved.emit(self)
        elif change == QGraphicsItem.ItemSelectedHasChanged and not value and self._is_editing_inline and self._inline_editor_proxy and self._inline_editor_proxy.widget():
            self._inline_edit_aborted = False; self._inline_editor_proxy.widget().clearFocus()
        return super().itemChange(change, value)