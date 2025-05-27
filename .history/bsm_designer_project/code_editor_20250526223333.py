
# bsm_designer_project/code_editor.py
from PyQt5.QtWidgets import QPlainTextEdit, QWidget
from PyQt5.QtCore import Qt, QRect, QSize, QRegExp
from PyQt5.QtGui import QColor, QPainter, QTextFormat, QFont, QSyntaxHighlighter, QTextCharFormat, QFontMetrics

from config import (
    COLOR_BACKGROUND_MEDIUM, COLOR_ACCENT_PRIMARY_LIGHT, COLOR_TEXT_PRIMARY, COLOR_ACCENT_PRIMARY,
    EXECUTION_ENV_PYTHON_GENERIC, EXECUTION_ENV_ARDUINO_CPP, EXECUTION_ENV_C_GENERIC,
    EXECUTION_ENV_RASPBERRYPI_PYTHON, EXECUTION_ENV_MICROPYTHON
)

class LineNumberArea(QWidget):
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
        self.current_highlighter = None
        self.current_language_mode = None
        
        font = QFont("Consolas, 'Courier New', monospace", 10)
        self.setFont(font)
        
        fm = QFontMetrics(self.font()) 
        self.setTabStopDistance(fm.horizontalAdvance(' ') * 4)
        self.setLineWrapMode(QPlainTextEdit.NoWrap)

        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)
        self.cursorPositionChanged.connect(self.highlightCurrentLine)

        self.updateLineNumberAreaWidth(0)
        self.highlightCurrentLine()
        self.setLanguage(EXECUTION_ENV_PYTHON_GENERIC) # Default language

    def setLanguage(self, language_mode: str):
        if self.current_language_mode == language_mode and self.current_highlighter:
            return

        self.current_language_mode = language_mode
        
        if self.current_highlighter:
            # It seems QSyntaxHighlighter doesn't have a simple 'remove' or 'detach'
            # Re-assigning seems to work if the old one goes out of scope or is deleted
            self.current_highlighter.setDocument(None) # Detach from old document
            # Or simply let garbage collection handle it if it's Python-managed
            # PythonHighlighter(None) or CHighlighter(None) might not be needed if parent is the doc

        if language_mode in [EXECUTION_ENV_PYTHON_GENERIC, EXECUTION_ENV_RASPBERRYPI_PYTHON, EXECUTION_ENV_MICROPYTHON]:
            self.current_highlighter = PythonHighlighter(self.document())
        elif language_mode in [EXECUTION_ENV_ARDUINO_CPP, EXECUTION_ENV_C_GENERIC]:
            self.current_highlighter = CHighlighter(self.document())
        else: # Fallback or no highlighter
            self.current_highlighter = None # Or a BaseHighlighter that does nothing

        if self.current_highlighter:
            self.current_highlighter.rehighlight() # Force rehighlight with new rules
        self.update() # Redraw if necessary

    def lineNumberAreaWidth(self):
        digits = 1
        max_val = max(1, self.blockCount())
        while max_val >= 10:
            max_val //= 10
            digits += 1
        
        fm = self.fontMetrics()
        if fm.height() == 0: 
            return 35 
            
        padding = fm.horizontalAdvance(' ') 
        space = padding + fm.horizontalAdvance('9') * digits + padding
        return space

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
        painter.fillRect(event.rect(), QColor(COLOR_BACKGROUND_MEDIUM))

        block = self.firstVisibleBlock()
        blockNumber = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()

        current_line_bg_color = QColor(COLOR_ACCENT_PRIMARY_LIGHT)
        current_line_num_color = QColor(COLOR_ACCENT_PRIMARY) 
        normal_line_num_color = QColor(COLOR_TEXT_PRIMARY).darker(130)

        fm = self.fontMetrics() 

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(blockNumber + 1)
                
                temp_font = self.font() 
                if self.textCursor().blockNumber() == blockNumber:
                    painter.fillRect(QRect(0, int(top), self.lineNumberArea.width(), int(fm.height())), current_line_bg_color)
                    painter.setPen(current_line_num_color)
                    temp_font.setBold(True)
                else:
                    painter.setPen(normal_line_num_color)
                    temp_font.setBold(False)
                painter.setFont(temp_font)
                
                painter.drawText(0, int(top), self.lineNumberArea.width() - fm.horizontalAdvance(' '), 
                                 int(fm.height()),
                                 Qt.AlignRight, number)

            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            blockNumber += 1

    def highlightCurrentLine(self):
        extraSelections = []
        if not self.isReadOnly():
            selection = QPlainTextEdit.ExtraSelection()
            lineColor = QColor(COLOR_ACCENT_PRIMARY_LIGHT).lighter(125) 
            selection.format.setBackground(lineColor)
            selection.format.setProperty(QTextFormat.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extraSelections.append(selection)
        self.setExtraSelections(extraSelections)

class PythonHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None): 
        super().__init__(parent)
        self.highlightingRules = []

        keywordFormat = QTextCharFormat()
        keywordFormat.setForeground(QColor("#0000FF")) 
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
        definitionFormat.setFontWeight(QFont.Normal)
        self.highlightingRules.append(HighlightingRule("\\bdef\\s+([A-Za-z_][A-Za-z0-9_]*)", definitionFormat, 1, True))
        self.highlightingRules.append(HighlightingRule("\\bclass\\s+([A-Za-z_][A-Za-z0-9_]*)", definitionFormat, 1, True))
        
        operatorFormat = QTextCharFormat()
        operatorFormat.setForeground(QColor("#D4D4D4"))
        operators_regex = "\\+|\\-|\\*|/|%|=|==|!=|<|>|<=|>=|\\bnot\\b|\\band\\b|\\bor\\b|\\bis\\b|\\bin\\b"
        self.highlightingRules.append(HighlightingRule(operators_regex, operatorFormat))

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
                temp_offset = 0 
                while temp_offset <= len(text):
                    match = expression.match(text, temp_offset)
                    if not match.hasMatch() or match.capturedStart(0) == -1 : 
                        break
                    capture_start = match.capturedStart(rule.nth)
                    capture_length = match.capturedLength(rule.nth)
                    if capture_start != -1 and capture_length > 0:
                         self.setFormat(capture_start, capture_length, rule.format)
                    new_offset = match.capturedEnd(0)
                    if new_offset == temp_offset : 
                        new_offset += 1
                    temp_offset = new_offset
                    if temp_offset > len(text) : break
            else: 
                index = expression.indexIn(text, offset)
                while index >= 0:
                    length = expression.matchedLength()
                    if length > 0:
                        self.setFormat(index, length, rule.format)
                    offset = index + length 
                    if offset >= len(text): break
                    index = expression.indexIn(text, offset)

        self.setCurrentBlockState(0)
        # Handle '''
        startIndex = 0
        if self.previousBlockState() != 1:
            startIndex = self.triSingleStartExpression.indexIn(text)
        while startIndex >= 0:
            endIndex = self.triSingleEndExpression.indexIn(text, startIndex + self.triSingleStartExpression.matchedLength())
            if endIndex == -1:
                self.setCurrentBlockState(1)
                length = len(text) - startIndex
            else:
                length = endIndex - startIndex + self.triSingleEndExpression.matchedLength()
            self.setFormat(startIndex, length, self.triSingleQuoteFormat)
            startIndex = self.triSingleStartExpression.indexIn(text, startIndex + length)
        
        # Handle """ only if not in '''
        if self.currentBlockState() == 0:
            startIndex_double = 0
            if self.previousBlockState() != 2:
                startIndex_double = self.triDoubleStartExpression.indexIn(text)
            while startIndex_double >= 0:
                endIndex_double = self.triDoubleEndExpression.indexIn(text, startIndex_double + self.triDoubleStartExpression.matchedLength())
                if endIndex_double == -1:
                    self.setCurrentBlockState(2)
                    length = len(text) - startIndex_double
                else:
                    length = endIndex_double - startIndex_double + self.triDoubleEndExpression.matchedLength()
                self.setFormat(startIndex_double, length, self.triDoubleQuoteFormat)
                startIndex_double = self.triDoubleStartExpression.indexIn(text, startIndex_double + length)

class CHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.highlightingRules = []

        keywordFormat = QTextCharFormat()
        keywordFormat.setForeground(QColor("#569CD6")) # VSCode C++ keyword (blue)
        c_keywords = [
            "\\bauto\\b", "\\bbreak\\b", "\\bcase\\b", "\\bchar\\b", "\\bconst\\b", 
            "\\bcontinue\\b", "\\bdefault\\b", "\\bdo\\b", "\\bdouble\\b", "\\belse\\b", 
            "\\benum\\b", "\\bextern\\b", "\\bfloat\\b", "\\bfor\\b", "\\bgoto\\b", 
            "\\bif\\b", "\\bint\\b", "\\blong\\b", "\\bregister\\b", "\\breturn\\b", 
            "\\bshort\\b", "\\bsigned\\b", "\\bsizeof\\b", "\\bstatic\\b", "\\bstruct\\b", 
            "\\bswitch\\b", "\\btypedef\\b", "\\bunion\\b", "\\bunsigned\\b", "\\bvoid\\b", 
            "\\bvolatile\\b", "\\bwhile\\b",
            # C++ specific
            "\\bclass\\b", "\\bpublic\\b", "\\bprivate\\b", "\\bprotected\\b", "\\bthis\\b",
            "\\bnew\\b", "\\bdelete\\b", "\\bnamespace\\b", "\\btemplate\\b", "\\btypename\\b",
            "\\btrue\\b", "\\bfalse\\b", "\\bnullptr\\b", "\\btry\\b", "\\bcatch\\b", "\\bthrow\\b",
            # Arduino specific commonly used
            "\\bHIGH\\b", "\\bLOW\\b", "\\bINPUT\\b", "\\bOUTPUT\\b", "\\bINPUT_PULLUP\\b",
            "\\bboolean\\b", "\\bbyte\\b", "\\bword\\b", "\\bString\\b", "\\bpinMode\\b",
            "\\bdigitalWrite\\b", "\\bdigitalRead\\b", "\\banalogWrite\\b", "\\banalogRead\\b",
            "\\bdelay\\b", "\\bdelayMicroseconds\\b", "\\bmillis\\b", "\\bmicros\\b",
            "\\bSerial\\b", "\\bsetup\\b", "\\bloop\\b"
        ]
        for word in c_keywords:
            self.highlightingRules.append(HighlightingRule(word, keywordFormat))

        commentFormat = QTextCharFormat()
        commentFormat.setForeground(QColor("#6A9955")) # Green
        self.highlightingRules.append(HighlightingRule("//[^\n]*", commentFormat))

        stringFormat = QTextCharFormat()
        stringFormat.setForeground(QColor("#CE9178")) # Orangey-brown
        self.highlightingRules.append(HighlightingRule("\"([^\"\\\\]|\\\\.)*\"", stringFormat)) # Handles escaped quotes
        self.highlightingRules.append(HighlightingRule("'[^']*'", stringFormat)) # char literal

        preprocessorFormat = QTextCharFormat()
        preprocessorFormat.setForeground(QColor("#C586C0")) # Magenta/Purple
        self.highlightingRules.append(HighlightingRule("^#[^\n]*", preprocessorFormat))

        numberFormat = QTextCharFormat()
        numberFormat.setForeground(QColor("#B5CEA8")) # Light green
        self.highlightingRules.append(HighlightingRule("\\b[0-9]+\\.?[0-9]*([eE][-+]?[0-9]+)?(f|L|ul|UL|u|U|l|LL|ll)?\\b", numberFormat))
        self.highlightingRules.append(HighlightingRule("\\b0[xX][0-9a-fA-F]+(u|U|l|L|ul|UL|ll|LL)?\\b", numberFormat)) # Hex
        self.highlightingRules.append(HighlightingRule("\\b0[0-7]+(u|U|l|L|ul|UL|ll|LL)?\\b", numberFormat)) # Octal
        
        functionFormat = QTextCharFormat()
        functionFormat.setForeground(QColor("#DCDCAA")) # Light yellow (for function calls/definitions)
        # This is a simple regex, true function call highlighting is more complex
        self.highlightingRules.append(HighlightingRule("\\b[A-Za-z_][A-Za-z0-9_]*(?=\\s*\\()", functionFormat)) 


        # Multi-line C-style comment
        self.multiLineCommentFormat = QTextCharFormat()
        self.multiLineCommentFormat.setForeground(QColor("#6A9955"))
        self.commentStartExpression = QRegExp("/\\*")
        self.commentEndExpression = QRegExp("\\*/")

    def highlightBlock(self, text):
        for rule in self.highlightingRules:
            expression = rule.pattern
            expression.setMinimal(rule.minimal)
            offset = 0
            # Simplified logic from PythonHighlighter for single-line rules
            index = expression.indexIn(text, offset)
            while index >= 0:
                length = expression.matchedLength()
                if length > 0:
                    self.setFormat(index, length, rule.format)
                offset = index + length
                if offset >= len(text): break
                index = expression.indexIn(text, offset)

        self.setCurrentBlockState(0) # Default state (outside multi-line comment)

        startIndex = 0
        if self.previousBlockState() != 1: # If not already in a comment
            startIndex = self.commentStartExpression.indexIn(text)

        while startIndex >= 0:
            endIndex = self.commentEndExpression.indexIn(text, startIndex + self.commentStartExpression.matchedLength())
            if endIndex == -1: # Comment continues to next block
                self.setCurrentBlockState(1)
                length = len(text) - startIndex
            else: # Comment ends in this block
                length = endIndex - startIndex + self.commentEndExpression.matchedLength()
            self.setFormat(startIndex, length, self.multiLineCommentFormat)
            # Find next comment start after this one ends
            startIndex = self.commentStartExpression.indexIn(text, startIndex + length)


class HighlightingRule:
    def __init__(self, pattern_str, text_format, nth_capture_group=0, minimal=False):
        self.pattern = QRegExp(pattern_str)
        self.format = text_format
        self.nth = nth_capture_group # Not used by CHighlighter's simplified loop, but kept for compatibility
        self.minimal = minimal
        if self.minimal:
            self.pattern.setMinimal(True)
