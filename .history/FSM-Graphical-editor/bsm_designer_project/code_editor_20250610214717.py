# bsm_designer_project/code_editor.py
from PyQt5.QtWidgets import QPlainTextEdit, QWidget, QTextEdit # Import QTextEdit
from PyQt5.QtCore import Qt, QRect, QSize, QRegExp 
from PyQt5.QtGui import (
    QColor, QPainter, QTextFormat, QFont, QSyntaxHighlighter, QTextCharFormat, QFontMetrics,
    QPalette, QTextCursor 
)

from .config import (
    COLOR_BACKGROUND_MEDIUM, COLOR_ACCENT_PRIMARY_LIGHT, COLOR_TEXT_PRIMARY,
    COLOR_ACCENT_PRIMARY, COLOR_TEXT_EDITOR_DARK_SECONDARY,
    COLOR_BACKGROUND_EDITOR_DARK, COLOR_TEXT_EDITOR_DARK_PRIMARY, APP_FONT_SIZE_EDITOR,
    APP_FONT_FAMILY 
)

class LineNumberArea(QWidget):
# ... (rest of file is unchanged)
    def __init__(self, editor):
        super().__init__(editor)
        self.codeEditor = editor

    def sizeHint(self):
        return QSize(self.codeEditor.lineNumberAreaWidth(), 0)

    def paintEvent(self, event):
        self.codeEditor.lineNumberAreaPaintEvent(event)


class CodeEditor(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.lineNumberArea = LineNumberArea(self)
        
        editor_font_size = 10 
        try:
            editor_font_size_val = int(APP_FONT_SIZE_EDITOR.replace("pt", ""))
            if 8 <= editor_font_size_val <= 24:
                editor_font_size = editor_font_size_val
        except ValueError:
            pass 
            
        font = QFont("Consolas, 'Courier New', monospace", editor_font_size)
        font.setStyleHint(QFont.Monospace)
        self.setFont(font)
        
        fm = QFontMetrics(self.font()) 
        self.setTabStopDistance(fm.horizontalAdvance(' ') * 4) 
        self.setLineWrapMode(QPlainTextEdit.NoWrap)

        self.current_highlighter = None 


        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)
        self.cursorPositionChanged.connect(self.highlightCurrentLine)

        self.updateLineNumberAreaWidth(0)
        self.highlightCurrentLine()
        self.set_language("Python") 
        
        palette = self.palette()
        palette.setColor(QPalette.Base, QColor(COLOR_BACKGROUND_EDITOR_DARK))
        palette.setColor(QPalette.Text, QColor(COLOR_TEXT_EDITOR_DARK_PRIMARY))
        self.setPalette(palette)


    def lineNumberAreaWidth(self):
        digits = 1
        max_val = max(1, self.blockCount())
        while max_val >= 10:
            max_val //= 10
            digits += 1
        
        fm = self.fontMetrics()
        if fm.height() == 0: 
            return 40 
            
        padding_char_width = fm.horizontalAdvance(' ')
        space = padding_char_width + (fm.horizontalAdvance('9') * digits) + padding_char_width 
        return space + 5 

    def updateLineNumberAreaWidth(self, _):
        self.setViewportMargins(self.lineNumberAreaWidth(), 0, 0, 0)

    def updateLineNumberArea(self, rect, dy):
        if dy:
            self.lineNumberArea.scroll(0, dy)
        else:
            self.lineNumberArea.update(0, rect.y(), self.lineNumberArea.width(), rect.height())

        if rect.contains(self.viewport().rect()):
            self.updateLineNumberAreaWidth(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.lineNumberArea.setGeometry(QRect(cr.left(), cr.top(), self.lineNumberAreaWidth(), cr.height()))

    def lineNumberAreaPaintEvent(self, event):
        painter = QPainter(self.lineNumberArea)
        line_number_area_bg = QColor(COLOR_BACKGROUND_EDITOR_DARK).lighter(110)
        painter.fillRect(event.rect(), line_number_area_bg)

        block = self.firstVisibleBlock()
        blockNumber = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()

        current_line_highlight_bg = QColor(COLOR_BACKGROUND_EDITOR_DARK).lighter(130)
        current_line_num_color = QColor(COLOR_ACCENT_PRIMARY_LIGHT) 
        normal_line_num_color = QColor(COLOR_TEXT_EDITOR_DARK_SECONDARY) 

        fm = self.fontMetrics()
        right_padding = fm.horizontalAdvance(' ') 

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(blockNumber + 1)
                
                temp_font = self.font() 
                temp_font.setPointSize(max(8, self.font().pointSize() -1)) 

                if self.textCursor().blockNumber() == blockNumber:
                    painter.fillRect(QRect(0, int(top), self.lineNumberArea.width(), int(fm.height())), current_line_highlight_bg)
                    painter.setPen(current_line_num_color)
                    temp_font.setBold(True)
                else:
                    painter.setPen(normal_line_num_color)
                    temp_font.setBold(False)
                painter.setFont(temp_font)
                
                painter.drawText(0, int(top), self.lineNumberArea.width() - right_padding,
                                 int(fm.height()),
                                 Qt.AlignRight | Qt.AlignVCenter, number)

            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            blockNumber += 1

    def highlightCurrentLine(self):
        extraSelections = []
        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection() 
            lineColor = QColor(COLOR_BACKGROUND_EDITOR_DARK).lighter(120)
            selection.format.setBackground(lineColor)
            selection.format.setProperty(QTextFormat.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extraSelections.append(selection)
        self.setExtraSelections(extraSelections)

    def set_language(self, language: str):
        doc = self.document()
        if not doc:
            return

        if self.current_highlighter:
            # Detach the old highlighter
            self.current_highlighter.setDocument(None)
            self.current_highlighter = None

        # Set new highlighter based on language
        if language == "Python":
            self.current_highlighter = PythonHighlighter(doc)
        elif language in ["C/C++ (Arduino)", "C/C++ (Generic)"]:
            self.current_highlighter = CSyntaxHighlighter(doc)
        # else: self.current_highlighter remains None for plain text

        # Whether a new highlighter was set or it was set to None (plain text),
        # we need to force a rehighlight of the entire document.
        if self.current_highlighter:
            self.current_highlighter.rehighlight()
        else:
            # If no highlighter, force a re-format to default.
            # One way to ensure this is to temporarily apply a default format to all text.
            # A simpler approach that often works is to just call rehighlight() on the
            # document or the editor's blocks. QPlainTextEdit doesn't have a direct
            # rehighlight method. QSyntaxHighlighter itself does.
            # If we don't have a custom highlighter, Qt will use its default drawing.
            # We might need to manually reset block formats if switching from highlighted to plain.
            # A common trick:
            cursor = self.textCursor() # Save cursor position
            cursor_pos = cursor.position()
            text = self.toPlainText() # Save current text
            self.setPlainText("")    # Clear text (this also clears formatting)
            self.setPlainText(text)  # Restore text, it will be unhighlighted
            cursor.setPosition(cursor_pos) # Restore cursor position
            self.setTextCursor(cursor)
            doc.clearUndoRedoStacks() # Changing text clears undo stack, desirable here

        self.viewport().update()


class PythonHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None): 
        super().__init__(parent)

        self.highlightingRules = []

        keywordFormat = QTextCharFormat()
        keywordFormat.setForeground(QColor("#C586C0")) 
        keywords = [
            "\\bFalse\\b", "\\bNone\\b", "\\bTrue\\b", "\\band\\b", "\\bas\\b", "\\bassert\\b", 
            "\\basync\\b", "\\bawait\\b", "\\bbreak\\b", "\\bclass\\b", "\\bcontinue\\b", 
            "\\bdef\\b", "\\bdel\\b", "\\belif\\b", "\\belse\\b", "\\bexcept\\b", "\\bfinally\\b", 
            "\\bfor\\b", "\\bfrom\\b", "\\bglobal\\b", "\\bif\\b", "\\bimport\\b", "\\bin\\b", 
            "\\bis\\b", "\\blambda\\b", "\\bnonlocal\\b", "\\bor\\b", "\\bpass\\b",
            "\\braise\\b", "\\breturn\\b", "\\btry\\b", "\\bwhile\\b", "\\bwith\\b", "\\byield\\b",
            "\\bsuper\\b"
        ]
        for word in keywords:
            self.highlightingRules.append(HighlightingRule(word, keywordFormat))
        
        selfFormat = QTextCharFormat()
        selfFormat.setForeground(QColor("#9CDCFE")) 
        self_keywords = ["\\bself\\b", "\\bcls\\b"]
        for word in self_keywords:
            self.highlightingRules.append(HighlightingRule(word, selfFormat))

        builtinFormat = QTextCharFormat()
        builtinFormat.setForeground(QColor("#4EC9B0")) 
        builtins = [
            "\\bprint\\b", "\\blen\\b", "\\babs\\b", "\\bmin\\b", "\\bmax\\b", 
            "\\bint\\b", "\\bfloat\\b", "\\bstr\\b", "\\bbool\\b", "\\blist\\b", 
            "\\bdict\\b", "\\bset\\b", "\\btuple\\b", "\\brange\\b", "\\bsorted\\b", 
            "\\bsum\\b", "\\ball\\b", "\\bany\\b", "\\bisinstance\\b", "\\bhasattr\\b",
            "\\bException\\b", "\\bTypeError\\b", "\\bValueError\\b", "\\bNameError\\b"
        ]
        for word in builtins:
            self.highlightingRules.append(HighlightingRule(word, builtinFormat))

        commentFormat = QTextCharFormat()
        commentFormat.setForeground(QColor("#6A9955")) 
        commentFormat.setFontItalic(True) 
        self.highlightingRules.append(HighlightingRule("#[^\n]*", commentFormat))

        stringFormat = QTextCharFormat()
        stringFormat.setForeground(QColor("#CE9178")) 
        self.highlightingRules.append(HighlightingRule("'[^']*'", stringFormat))
        self.highlightingRules.append(HighlightingRule("\"[^\"]*\"", stringFormat))

        numberFormat = QTextCharFormat()
        numberFormat.setForeground(QColor("#B5CEA8")) 
        self.highlightingRules.append(HighlightingRule("\\b[0-9]+\\.?[0-9]*([eE][-+]?[0-9]+)?\\b", numberFormat))
        self.highlightingRules.append(HighlightingRule("\\b0[xX][0-9a-fA-F]+\\b", numberFormat)) 

        definitionFormat = QTextCharFormat() 
        definitionFormat.setForeground(QColor("#DCDCAA")) 
        definitionFormat.setFontWeight(QFont.Bold) 
        self.highlightingRules.append(HighlightingRule("\\bdef\\s+([A-Za-z_][A-Za-z0-9_]*)", definitionFormat, 1, True))
        self.highlightingRules.append(HighlightingRule("\\bclass\\s+([A-Za-z_][A-Za-z0-9_]*)", definitionFormat, 1, True))
        
        operatorFormat = QTextCharFormat()
        operatorFormat.setForeground(QColor(COLOR_TEXT_EDITOR_DARK_PRIMARY).lighter(110)) 
        operators_regex = (
            # Keywords like 'not', 'and', 'or', 'is', 'in' are handled by keywordFormat
            r"(\+|\-|\*|/|%|=|==|!=|<|>|<=|>=|&|\||\^|~|<<|>>)" 
        )
        self.highlightingRules.append(HighlightingRule(operators_regex, operatorFormat))
        
        decoratorFormat = QTextCharFormat()
        decoratorFormat.setForeground(QColor("#4EC9B0")) 
        self.highlightingRules.append(HighlightingRule("@[A-Za-z_][A-Za-z0-9_.]*", decoratorFormat))


        self.triSingleQuoteFormat = QTextCharFormat()
        self.triSingleQuoteFormat.setForeground(QColor("#CE9178")) 
        self.triDoubleQuoteFormat = QTextCharFormat()
        self.triDoubleQuoteFormat.setForeground(QColor("#CE9178")) 

        self.triSingleStartExpression = QRegExp("'''")
        self.triSingleEndExpression = QRegExp("'''")
        self.triDoubleStartExpression = QRegExp("\"\"\"")
        self.triDoubleEndExpression = QRegExp("\"\"\"")


    def highlightBlock(self, text):
        for rule in self.highlightingRules:
            expression = rule.pattern
            expression.setMinimal(rule.minimal)
            
            offset = 0
            if rule.nth > 0:
                index = expression.indexIn(text, offset)
                while index >= 0:
                    capture_start = expression.pos(rule.nth) 
                    capture_text = expression.cap(rule.nth)
                    capture_length = len(capture_text)

                    if capture_start != -1 and capture_length > 0:
                        self.setFormat(capture_start, capture_length, rule.format)
                    
                    new_offset = index + expression.matchedLength()
                    if new_offset <= offset : 
                        new_offset = offset + 1 
                    offset = new_offset
                    if offset >= len(text) or expression.matchedLength() == 0 : 
                        break 
                    index = expression.indexIn(text, offset)
            else: 
                index = expression.indexIn(text, offset)
                while index >= 0:
                    length = expression.matchedLength()
                    if length > 0:
                        self.setFormat(index, length, rule.format)
                    
                    new_offset = index + length
                    if new_offset <= offset : 
                        new_offset = offset + 1
                    offset = new_offset
                    if offset >= len(text) or length == 0: 
                        break
                    index = expression.indexIn(text, offset)

        self.setCurrentBlockState(0) 
        
        startIndex = 0
        if self.previousBlockState() == 1: 
            startIndex = self.triSingleEndExpression.indexIn(text)
            if startIndex == -1: 
                self.setCurrentBlockState(1)
                self.setFormat(0, len(text), self.triSingleQuoteFormat)
            else: 
                length = startIndex + self.triSingleEndExpression.matchedLength()
                self.setFormat(0, length, self.triSingleQuoteFormat)
                self.process_remaining_text_for_multiline(text, length)
        elif self.previousBlockState() == 2: 
            startIndex = self.triDoubleEndExpression.indexIn(text)
            if startIndex == -1: 
                self.setCurrentBlockState(2)
                self.setFormat(0, len(text), self.triDoubleQuoteFormat)
            else: 
                length = startIndex + self.triDoubleEndExpression.matchedLength()
                self.setFormat(0, length, self.triDoubleQuoteFormat)
                self.process_remaining_text_for_multiline(text, length)
        else: 
            self.process_remaining_text_for_multiline(text, 0)

    def process_remaining_text_for_multiline(self, text, offset):
        startIndex_single = self.triSingleStartExpression.indexIn(text, offset)
        startIndex_double = self.triDoubleStartExpression.indexIn(text, offset)

        start_expression_used = None
        end_expression_to_use = None
        format_to_use = None
        state_to_set_if_unterminated = 0
        first_start_index = -1

        if startIndex_single != -1 and (startIndex_double == -1 or startIndex_single < startIndex_double):
            first_start_index = startIndex_single
            start_expression_used = self.triSingleStartExpression
            end_expression_to_use = self.triSingleEndExpression
            format_to_use = self.triSingleQuoteFormat
            state_to_set_if_unterminated = 1
        elif startIndex_double != -1:
            first_start_index = startIndex_double
            start_expression_used = self.triDoubleStartExpression
            end_expression_to_use = self.triDoubleEndExpression
            format_to_use = self.triDoubleQuoteFormat
            state_to_set_if_unterminated = 2
        
        if first_start_index != -1:
            match_len_start = start_expression_used.matchedLength()
            endIndex = end_expression_to_use.indexIn(text, first_start_index + match_len_start)

            if endIndex == -1: 
                self.setCurrentBlockState(state_to_set_if_unterminated)
                self.setFormat(first_start_index, len(text) - first_start_index, format_to_use)
            else: 
                match_len_end = end_expression_to_use.matchedLength()
                length = endIndex - first_start_index + match_len_end
                self.setFormat(first_start_index, length, format_to_use)
                self.setCurrentBlockState(0) 
                self.process_remaining_text_for_multiline(text, first_start_index + length)
        else:
            if self.currentBlockState() != 1 and self.currentBlockState() != 2:
                 self.setCurrentBlockState(0)


class HighlightingRule:
    def __init__(self, pattern_str, text_format, nth_capture_group=0, minimal=False):
        self.pattern = QRegExp(pattern_str)
        self.format = text_format
        self.nth = nth_capture_group 
        self.minimal = minimal
        if self.minimal:
            self.pattern.setMinimal(True)

class CSyntaxHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.highlightingRules = []

        keywordFormat = QTextCharFormat()
        keywordFormat.setForeground(QColor("#569CD6")) 
        keywordFormat.setFontWeight(QFont.Bold)
        keywords = [
            "\\bchar\\b", "\\bclass\\b", "\\bconst\\b", "\\bdouble\\b", "\\benum\\b",
            "\\bexplicit\\b", "\\bextern\\b", "\\bfloat\\b", "\\bfriend\\b", "\\binline\\b",
            "\\bint\\b", "\\blong\\b", "\\bnamespace\\b", "\\boperator\\b", "\\bprivate\\b",
            "\\bprotected\\b", "\\bpublic\\b", "\\bshort\\b", "\\bsignals\\b", "\\bsigned\\b", 
            "\\bslots\\b", "\\bstatic\\b", "\\bstruct\\b", "\\btemplate\\b", "\\bthis\\b",
            "\\btypedef\\b", "\\btypename\\b", "\\bunion\\b", "\\bunsigned\\b", "\\bvirtual\\b",
            "\\bvoid\\b", "\\bvolatile\\b", "\\bwchar_t\\b",
            "\\bbreak\\b", "\\bcase\\b", "\\bcontinue\\b", "\\bdefault\\b", "\\bdo\\b",
            "\\belse\\b", "\\bfor\\b", "\\bgoto\\b", "\\bif\\b", "\\breturn\\b",
            "\\bswitch\\b", "\\bwhile\\b",
            "\\bauto\\b", "\\bbool\\b", "\\bcatch\\b", "\\bconstexpr\\b", "\\bdecltype\\b",
            "\\bdelete\\b", "\\bfinal\\b", "\\bmutable\\b", "\\bnew\\b", "\\bnoexcept\\b",
            "\\bnullptr\\b", "\\boverride\\b", "\\bstatic_assert\\b", "\\bstatic_cast\\b",
            "\\bdynamic_cast\\b", "\\breinterpret_cast\\b", "\\bconst_cast\\b", 
            "\\bthrow\\b", "\\btry\\b", "\\busing\\b",
            "\\bHIGH\\b", "\\bLOW\\b", "\\bINPUT\\b", "\\bOUTPUT\\b", "\\bINPUT_PULLUP\\b",
            "\\btrue\\b", "\\bfalse\\b", "\\bboolean\\b", "\\bbyte\\b", "\\bword\\b",
            "\\bString\\b",
            "\\buint8_t\\b", "\\bint8_t\\b", "\\buint16_t\\b", "\\bint16_t\\b", 
            "\\buint32_t\\b", "\\bint32_t\\b", "\\buint64_t\\b", "\\bint64_t\\b",
            "\\bsize_t\\b"
        ]
        for word in keywords:
            self.highlightingRules.append(HighlightingRule(word, keywordFormat))

        preprocessorFormat = QTextCharFormat()
        preprocessorFormat.setForeground(QColor("#608B4E")) 
        self.highlightingRules.append(HighlightingRule("^\\s*#.*", preprocessorFormat)) 

        singleLineCommentFormat = QTextCharFormat()
        singleLineCommentFormat.setForeground(QColor("#6A9955")) 
        singleLineCommentFormat.setFontItalic(True)
        self.highlightingRules.append(HighlightingRule("//[^\n]*", singleLineCommentFormat))

        self.multiLineCommentFormat = QTextCharFormat()
        self.multiLineCommentFormat.setForeground(QColor("#6A9955")) 
        self.multiLineCommentFormat.setFontItalic(True)
        self.commentStartExpression = QRegExp("/\\*")
        self.commentEndExpression = QRegExp("\\*/")

        stringFormat = QTextCharFormat()
        stringFormat.setForeground(QColor("#CE9178")) 
        self.highlightingRules.append(HighlightingRule("\"(\\\\.|[^\"])*\"", stringFormat)) 
        charFormat = QTextCharFormat()
        charFormat.setForeground(QColor("#D16969")) 
        self.highlightingRules.append(HighlightingRule("'(\\\\.|[^'])'", charFormat))  

        numberFormat = QTextCharFormat()
        numberFormat.setForeground(QColor("#B5CEA8")) 
        self.highlightingRules.append(HighlightingRule("\\b[0-9]+[ULulFf]?\\b", numberFormat)) 
        self.highlightingRules.append(HighlightingRule("\\b0[xX][0-9a-fA-F]+[ULul]?\\b", numberFormat)) 
        self.highlightingRules.append(HighlightingRule("\\b[0-9]*\\.[0-9]+([eE][-+]?[0-9]+)?[fF]?\\b", numberFormat)) 

        functionFormat = QTextCharFormat()
        functionFormat.setForeground(QColor("#DCDCAA")) 
        self.highlightingRules.append(HighlightingRule("\\b[A-Za-z_][A-Za-z0-9_]*(?=\\s*\\()", functionFormat))
        
        arduinoSpecificFunctionFormat = QTextCharFormat()
        arduinoSpecificFunctionFormat.setForeground(QColor("#4EC9B0")) 
        arduinoFunctions = ["\\bsetup\\b", "\\bloop\\b", "\\bpinMode\\b", "\\bdigitalWrite\\b", "\\bdigitalRead\\b",
                            "\\banalogRead\\b", "\\banalogWrite\\b", "\\bdelay\\b", "\\bmillis\\b", "\\bmicros\\b",
                            "\\bSerial\\b", "\\bWire\\b", "\\bSPI\\b"] 
        for func in arduinoFunctions:
            self.highlightingRules.append(HighlightingRule(func, arduinoSpecificFunctionFormat))


    def highlightBlock(self, text):
        for rule in self.highlightingRules:
            expression = rule.pattern 
            expression.setMinimal(rule.minimal) 
            
            offset = 0
            if rule.nth > 0:
                index = expression.indexIn(text, offset)
                while index >= 0:
                    capture_start = expression.pos(rule.nth)
                    capture_text = expression.cap(rule.nth)
                    capture_length = len(capture_text)

                    if capture_start != -1 and capture_length > 0:
                        self.setFormat(capture_start, capture_length, rule.format)
                    
                    new_offset = index + expression.matchedLength()
                    if new_offset <= offset : 
                        new_offset = offset + 1
                    offset = new_offset
                    if offset >= len(text) or expression.matchedLength() == 0 : 
                        break 
                    index = expression.indexIn(text, offset)
            else: 
                index = expression.indexIn(text, offset)
                while index >= 0:
                    length = expression.matchedLength()
                    if length > 0:
                        self.setFormat(index, length, rule.format)
                    
                    new_offset = index + length
                    if new_offset <= offset : 
                        new_offset = offset + 1
                    offset = new_offset
                    if offset >= len(text) or length == 0: 
                        break
                    index = expression.indexIn(text, offset)

        self.setCurrentBlockState(0) 

        startIndex = 0
        if self.previousBlockState() != 1: 
            startIndex = self.commentStartExpression.indexIn(text)
        
        while startIndex >= 0:
            endIndex = self.commentEndExpression.indexIn(text, startIndex + self.commentStartExpression.matchedLength()) 
            commentLength = 0
            if endIndex == -1: 
                self.setCurrentBlockState(1)
                commentLength = len(text) - startIndex
            else: 
                commentLength = endIndex - startIndex + self.commentEndExpression.matchedLength()
            
            self.setFormat(startIndex, commentLength, self.multiLineCommentFormat)
            startIndex = self.commentStartExpression.indexIn(text, startIndex + commentLength)