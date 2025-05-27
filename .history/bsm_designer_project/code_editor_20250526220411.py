# bsm_designer_project/code_editor.py
from PyQt5.QtWidgets import QPlainTextEdit, QWidget
from PyQt5.QtCore import Qt, QRect, QSize, QRegExp
from PyQt5.QtGui import QColor, QPainter, QTextFormat, QFont, QSyntaxHighlighter, QTextCharFormat, QFontMetrics

from config import COLOR_BACKGROUND_MEDIUM, COLOR_ACCENT_PRIMARY_LIGHT, COLOR_TEXT_PRIMARY, COLOR_ACCENT_PRIMARY

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
        self.highlighter = PythonHighlighter(self.document())

        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)
        self.cursorPositionChanged.connect(self.highlightCurrentLine)

        self.updateLineNumberAreaWidth(0)
        self.highlightCurrentLine()
        
        font = QFont("Consolas, 'Courier New', monospace", 10)
        self.setFont(font)
        # QFontMetrics needed for tab stop, ensure font is set
        fm = QFontMetrics(self.font()) 
        self.setTabStopDistance(fm.horizontalAdvance(' ') * 4)
        self.setLineWrapMode(QPlainTextEdit.NoWrap)


    def lineNumberAreaWidth(self):
        digits = 1
        max_val = max(1, self.blockCount())
        while max_val >= 10:
            max_val //= 10
            digits += 1
        
        # Ensure font metrics are valid
        fm = self.fontMetrics()
        if fm.height() == 0: # Font not fully loaded/set
            return 30 # Fallback width
            
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

        fm = self.fontMetrics() # Cache font metrics

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(blockNumber + 1)
                
                if self.textCursor().blockNumber() == blockNumber:
                    painter.fillRect(QRect(0, int(top), self.lineNumberArea.width(), int(fm.height())), current_line_bg_color)
                    painter.setPen(current_line_num_color)
                    font = self.font()
                    font.setBold(True)
                    painter.setFont(font)
                else:
                    painter.setPen(normal_line_num_color)
                    painter.setFont(self.font())
                
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
            lineColor = QColor(COLOR_ACCENT_PRIMARY_LIGHT).lighter(120) 
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
            "\\bis\\b", "\\blambda\\b", "\\bnonlocal\\b", "\\bnot\\b", "\\bor\\b", "\\bpass\\b", 
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
        definitionFormat.setFontWeight(QFont.Bold)
        self.highlightingRules.append(HighlightingRule("\\bdef\\s+([A-Za-z_][A-Za-z0-9_]*)", definitionFormat, 1, True))
        self.highlightingRules.append(HighlightingRule("\\bclass\\s+([A-Za-z_][A-Za-z0-9_]*)", definitionFormat, 1, True))
        
        operatorFormat = QTextCharFormat()
        operatorFormat.setForeground(QColor("#D4D4D4"))
        # Basic operators - can be expanded
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
                # Match and highlight a specific capture group
                temp_offset = 0 # Use a temporary offset for match()
                while temp_offset <= len(text):
                    match = expression.match(text, temp_offset)
                    if not match.hasMatch() or match.capturedStart(0) == -1 : # No more matches or invalid match
                        break
                    
                    if match.capturedStart(rule.nth) != -1:
                        index = match.capturedStart(rule.nth)
                        length = match.capturedLength(rule.nth)
                        if length > 0 : # Ensure length is positive
                             self.setFormat(index, length, rule.format)
                    
                    # Advance offset to search after the current full match
                    temp_offset = match.capturedEnd(0)
                    if temp_offset == match.capturedStart(0) and length == 0: # Avoid infinite loop on zero-length match group
                        temp_offset +=1
                    if temp_offset == -1 or temp_offset >= len(text) : break # Check bounds

            else: # Highlight the whole match
                index = expression.indexIn(text, offset)
                while index >= 0:
                    length = expression.matchedLength()
                    if length > 0: # Ensure length is positive
                        self.setFormat(index, length, rule.format)
                    offset = index + length # Continue search from end of this match
                    if offset >= len(text): break
                    index = expression.indexIn(text, offset)


        self.setCurrentBlockState(0) # Default state (outside multi-line string)

        # Multi-line '''
        startIndex = 0
        if self.previousBlockState() != 1: # If not already in a ''' string
            startIndex = self.triSingleStartExpression.indexIn(text)
        
        while startIndex >= 0:
            endIndex = self.triSingleEndExpression.indexIn(text, startIndex + self.triSingleStartExpression.matchedLength())
            if endIndex == -1: # String continues to next block
                self.setCurrentBlockState(1)
                length = len(text) - startIndex
            else: # String ends in this block
                length = endIndex - startIndex + self.triSingleEndExpression.matchedLength()
            self.setFormat(startIndex, length, self.triSingleQuoteFormat)
            startIndex = self.triSingleStartExpression.indexIn(text, startIndex + length)
        
        # Multi-line """ (only if not already in ''' state)
        if self.currentBlockState() == 0:
            startIndex_double = 0
            if self.previousBlockState() != 2: # If not already in a """ string
                startIndex_double = self.triDoubleStartExpression.indexIn(text)

            while startIndex_double >= 0:
                endIndex_double = self.triDoubleEndExpression.indexIn(text, startIndex_double + self.triDoubleStartExpression.matchedLength())
                if endIndex_double == -1: # String continues to next block
                    self.setCurrentBlockState(2)
                    length = len(text) - startIndex_double
                else: # String ends in this block
                    length = endIndex_double - startIndex_double + self.triDoubleEndExpression.matchedLength()
                self.setFormat(startIndex_double, length, self.triDoubleQuoteFormat)
                startIndex_double = self.triDoubleStartExpression.indexIn(text, startIndex_double + length)


class HighlightingRule:
    def __init__(self, pattern_str, text_format, nth_capture_group=0, minimal=False):
        self.pattern = QRegExp(pattern_str)
        self.format = text_format
        self.nth = nth_capture_group
        self.minimal = minimal
        if self.minimal:
            self.pattern.setMinimal(True)