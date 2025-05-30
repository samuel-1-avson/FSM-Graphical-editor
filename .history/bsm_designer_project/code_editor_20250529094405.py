# bsm_designer_project/code_editor.py
from PyQt5.QtWidgets import QPlainTextEdit, QWidget, QTextEdit
from PyQt5.QtCore import Qt, QRect, QSize, QRegExp
from PyQt5.QtGui import (
    QColor, QPainter, QTextFormat, QFont, QSyntaxHighlighter,
    QTextCharFormat, QFontMetrics, QTextCursor, QPalette
)

from config import (
    COLOR_BACKGROUND_MEDIUM, COLOR_ACCENT_PRIMARY_LIGHT, COLOR_TEXT_PRIMARY, COLOR_ACCENT_PRIMARY,
    COLOR_EDITOR_DARK_BACKGROUND, COLOR_EDITOR_DARK_LINE_NUM_BG, COLOR_EDITOR_DARK_LINE_NUM_FG,
    COLOR_EDITOR_DARK_CURRENT_LINE_BG_LN_AREA, COLOR_EDITOR_DARK_CURRENT_LINE_FG_LN_AREA,
    COLOR_EDITOR_DARK_CURRENT_LINE_BG_EDITOR
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

        font = QFont("Consolas, 'Courier New', monospace", 10)
        self.setFont(font)

        fm = QFontMetrics(self.font())
        self.setTabStopDistance(fm.horizontalAdvance(' ') * 4)
        self.setLineWrapMode(QPlainTextEdit.NoWrap)

        self.current_highlighter = None

        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)
        self.cursorPositionChanged.connect(self.highlightCurrentLine)
        self.cursorPositionChanged.connect(self.lineNumberArea.update)

        self.updateLineNumberAreaWidth(0)
        self.highlightCurrentLine()
        self.set_language("Python")


    def _is_dark_theme_active(self) -> bool:
        editor_bg_color = self.palette().color(QPalette.Base)
        return editor_bg_color.lightnessF() < 0.45 or editor_bg_color == COLOR_EDITOR_DARK_BACKGROUND

    def lineNumberAreaWidth(self):
        digits = 1
        max_val = max(1, self.blockCount())
        while max_val >= 10:
            max_val //= 10
            digits += 1

        fm = self.fontMetrics()
        if fm.height() == 0:
            return 35

        padding = fm.horizontalAdvance(' ') * 2
        space = padding + fm.horizontalAdvance('9') * digits
        return space

    def updateLineNumberAreaWidth(self, _=None):
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
        is_dark = self._is_dark_theme_active()

        ln_area_bg_color = COLOR_EDITOR_DARK_LINE_NUM_BG if is_dark else QColor(COLOR_BACKGROUND_MEDIUM)
        painter.fillRect(event.rect(), ln_area_bg_color)

        block = self.firstVisibleBlock()
        blockNumber = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()

        current_line_bg_color_ln = COLOR_EDITOR_DARK_CURRENT_LINE_BG_LN_AREA if is_dark else QColor(COLOR_ACCENT_PRIMARY_LIGHT)
        current_line_num_color_ln = COLOR_EDITOR_DARK_CURRENT_LINE_FG_LN_AREA if is_dark else QColor(COLOR_ACCENT_PRIMARY)
        normal_line_num_color_ln = COLOR_EDITOR_DARK_LINE_NUM_FG if is_dark else QColor(COLOR_TEXT_PRIMARY).darker(130)

        fm = self.fontMetrics()
        right_padding = fm.horizontalAdvance(' ') // 2

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(blockNumber + 1)

                temp_font = self.font()
                if self.textCursor().blockNumber() == blockNumber:
                    painter.fillRect(QRect(0, int(top), self.lineNumberArea.width(), int(fm.height())), current_line_bg_color_ln)
                    painter.setPen(current_line_num_color_ln)
                    temp_font.setBold(True)
                else:
                    painter.setPen(normal_line_num_color_ln)
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
            is_dark = self._is_dark_theme_active()

            line_color_editor = COLOR_EDITOR_DARK_CURRENT_LINE_BG_EDITOR if is_dark else QColor(COLOR_ACCENT_PRIMARY_LIGHT).lighter(125)

            selection.format.setBackground(line_color_editor)
            selection.format.setProperty(QTextFormat.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extraSelections.append(selection)
        self.setExtraSelections(extraSelections)

    def set_language(self, language: str):
        doc = self.document()
        if not doc:
            return

        # Detach the old highlighter
        if self.current_highlighter:
            self.current_highlighter.setDocument(None)
        
        self.current_highlighter = None # Reset

        # Set the new highlighter
        if language == "Python":
            self.current_highlighter = PythonHighlighter(doc)
        elif language in ["C/C++ (Arduino)", "C/C++ (Generic)"]:
            self.current_highlighter = CSyntaxHighlighter(doc)
        # If no specific highlighter, self.current_highlighter remains None

        # Rehighlight
        if self.current_highlighter:
            self.current_highlighter.rehighlight() # Tell the NEW highlighter to process the whole doc
        else:
            # If there's no highlighter, we need to ensure any previous formatting
            # from a prior highlighter is cleared. QSyntaxHighlighter doesn't
            # automatically clear formats when detached if the document isn't
            # re-processed. A common way is to force rehighlight of all blocks.
            # This will cause QPlainTextEdit to request highlighting for blocks,
            # and since no highlighter is active, default formatting applies.
            block = doc.firstBlock()
            while block.isValid():
                block.layout().clearFormats() # Clear direct formatting from layout
                doc.markContentsDirty(block.position(), block.length()) # Mark dirty to ensure repaint
                block = block.next()
            # Trigger a full re-layout and repaint
            # This is a bit heavy-handed, but ensures clearing.
            # A simpler self.viewport().update() might not be enough to clear all formats
            # if they were deeply embedded by the previous highlighter.
            # Another option is to re-set the plain text, but that loses undo history.
            # Forcing rehighlight on all blocks with no active highlighter usually works.
            # Let's try a more Qt-idiomatic way to trigger re-evaluation by the (non-existent) highlighter
            # by rehighlighting all blocks from the document's perspective
            temp_cursor = QTextCursor(doc)
            temp_cursor.select(QTextCursor.Document)
            # Forcing a change and then undoing it can sometimes trigger what we need, but it's a hack.
            # The most direct way is often to rely on the highlighter itself.
            # Since we have no highlighter, we force Qt to re-evaluate all text blocks.
            # QPlainTextEdit internally manages this when its content changes or a highlighter is set.
            # For now, let's make all blocks "dirty" so they get repainted.
            doc.clearUndoRedoStacks() # This is aggressive, but ensures no stale formats.
            self.setPlainText(self.toPlainText()) # This is also aggressive, re-parses everything.
                                                  # It works but loses cursor position and undo.

            # A less aggressive way to clear formats and trigger re-evaluation:
            # Iterate and clear format per block if no highlighter.
            # This is complex. Let's rely on the fact that with no highlighter,
            # new text typed or blocks becoming dirty will not get new formats.
            # The main issue is *existing* formats.
            # The most reliable for clearing is often re-setting the document to the highlighter.
            # Since highlighter is None, this has no direct effect.
            # The QSyntaxHighlighter system should handle this; when a block is
            # re-evaluated and there's no highlighter, previous formats should ideally be gone.
            # If visual artifacts remain, a more direct clearing mechanism is needed.

            # Let's try a simple approach first: tell all blocks to rehighlight.
            # QPlainTextEdit rehighlights blocks when they become visible or are marked dirty.
            # If previous highlighter formats are 'stuck', simply calling update() might not be enough.
            # We ensure all blocks are 're-evaluated' by the highlighting system.
            # Since there's no active highlighter, they should revert to default.
            
            # Simplified:
            # Iterate blocks and trigger their rehighlight individually
            # This is what QSyntaxHighlighter.rehighlight() does internally if it has a document.
            # If we don't have a highlighter, we tell the document to update.
            
            # Try to tell the document that its layout has changed.
            # This is often enough to trigger a full repaint and re-evaluation of styles.
            doc.documentLayout().documentSizeChanged(doc.size()) # Notify layout of a change


        self.viewport().update()
        self.highlightCurrentLine()
        self.lineNumberArea.update()


# ... (rest of PythonHighlighter, HighlightingRule, CSyntaxHighlighter are unchanged) ...

class PythonHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None): 
        super().__init__(parent)

        self.highlightingRules = []

        keywordFormat = QTextCharFormat()
        keywordFormat.setForeground(QColor("#0000FF")) # Blue (VSCode Python keyword color)
        keywords = [
            "\\bFalse\\b", "\\bNone\\b", "\\bTrue\\b", "\\band\\b", "\\bas\\b", "\\bassert\\b", 
            "\\basync\\b", "\\bawait\\b", "\\bbreak\\b", "\\bclass\\b", "\\bcontinue\\b", 
            "\\bdef\\b", "\\bdel\\b", "\\belif\\b", "\\belse\\b", "\\bexcept\\b", "\\bfinally\\b", 
            "\\bfor\\b", "\\bfrom\\b", "\\bglobal\\b", "\\bif\\b", "\\bimport\\b", "\\bin\\b", 
            "\\bis\\b", "\\blambda\\b", "\\bnonlocal\\b", "\\bor\\b", "\\bpass\\b",  # 'not' handled by operator rule
            "\\braise\\b", "\\breturn\\b", "\\btry\\b", "\\bwhile\\b", "\\bwith\\b", "\\byield\\b",
            "\\bsuper\\b"
        ]
        for word in keywords:
            self.highlightingRules.append(HighlightingRule(word, keywordFormat))
        
        selfFormat = QTextCharFormat()
        selfFormat.setForeground(QColor("#9CDCFE")) # VSCode Python parameter color (light blueish)
        self_keywords = ["\\bself\\b", "\\bcls\\b"]
        for word in self_keywords:
            self.highlightingRules.append(HighlightingRule(word, selfFormat))

        builtinFormat = QTextCharFormat()
        builtinFormat.setForeground(QColor("#4EC9B0")) # VSCode Python function call color (tealish)
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
        commentFormat.setForeground(QColor("#6A9955")) # VSCode Python comment color (green)
        self.highlightingRules.append(HighlightingRule("#[^\n]*", commentFormat))

        stringFormat = QTextCharFormat()
        stringFormat.setForeground(QColor("#CE9178")) # VSCode Python string color (orangey-brown)
        self.highlightingRules.append(HighlightingRule("'[^']*'", stringFormat))
        self.highlightingRules.append(HighlightingRule("\"[^\"]*\"", stringFormat))

        numberFormat = QTextCharFormat()
        numberFormat.setForeground(QColor("#B5CEA8")) # VSCode Python number color (light green)
        self.highlightingRules.append(HighlightingRule("\\b[0-9]+\\.?[0-9]*([eE][-+]?[0-9]+)?\\b", numberFormat))
        self.highlightingRules.append(HighlightingRule("\\b0[xX][0-9a-fA-F]+\\b", numberFormat))

        definitionFormat = QTextCharFormat()
        definitionFormat.setForeground(QColor("#DCDCAA")) # VSCode Python function definition name (light yellow)
        definitionFormat.setFontWeight(QFont.Normal) # Usually not bold
        self.highlightingRules.append(HighlightingRule("\\bdef\\s+([A-Za-z_][A-Za-z0-9_]*)", definitionFormat, 1, True))
        self.highlightingRules.append(HighlightingRule("\\bclass\\s+([A-Za-z_][A-Za-z0-9_]*)", definitionFormat, 1, True))
        
        operatorFormat = QTextCharFormat()
        operatorFormat.setForeground(QColor("#D4D4D4")) # VSCode default text color
        # Regex for operators, including keywords like 'not', 'and', 'or', 'is', 'in'
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
        # Apply non-multiline rules first
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
                    if new_offset == offset : 
                        new_offset +=1
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
                    if new_offset == offset : 
                        new_offset +=1
                    offset = new_offset
                    if offset >= len(text) or length == 0: 
                        break
                    index = expression.indexIn(text, offset)
        
        if self.previousBlockState() == 1: 
            current_multiline_state = 1
            startIndex = 0 
        elif self.previousBlockState() == 2: 
            current_multiline_state = 2
            startIndex = 0 
        else: 
            current_multiline_state = 0
            startIndex = -1 

        if current_multiline_state == 1: 
            endIndex = self.triSingleEndExpression.indexIn(text, startIndex)
            if endIndex == -1: 
                self.setCurrentBlockState(1)
                self.setFormat(0, len(text), self.triSingleQuoteFormat)
            else: 
                length = endIndex - startIndex + self.triSingleEndExpression.matchedLength()
                self.setFormat(startIndex, length, self.triSingleQuoteFormat)
                self.setCurrentBlockState(0) 
                self.process_remaining_text_for_multiline(text, startIndex + length)
        elif current_multiline_state == 2: 
            endIndex = self.triDoubleEndExpression.indexIn(text, startIndex)
            if endIndex == -1: 
                self.setCurrentBlockState(2)
                self.setFormat(0, len(text), self.triDoubleQuoteFormat)
            else: 
                length = endIndex - startIndex + self.triDoubleEndExpression.matchedLength()
                self.setFormat(startIndex, length, self.triDoubleQuoteFormat)
                self.setCurrentBlockState(0)
                self.process_remaining_text_for_multiline(text, startIndex + length)
        else: 
            self.process_remaining_text_for_multiline(text, 0)

    def process_remaining_text_for_multiline(self, text, offset):
        startIndex_single = self.triSingleStartExpression.indexIn(text, offset)
        startIndex_double = self.triDoubleStartExpression.indexIn(text, offset)

        if startIndex_single != -1 and (startIndex_double == -1 or startIndex_single < startIndex_double):
            endIndex = self.triSingleEndExpression.indexIn(text, startIndex_single + self.triSingleStartExpression.matchedLength())
            if endIndex == -1:
                self.setCurrentBlockState(1)
                self.setFormat(startIndex_single, len(text) - startIndex_single, self.triSingleQuoteFormat)
            else:
                length = endIndex - startIndex_single + self.triSingleEndExpression.matchedLength()
                self.setFormat(startIndex_single, length, self.triSingleQuoteFormat)
                self.setCurrentBlockState(0) 
                self.process_remaining_text_for_multiline(text, startIndex_single + length) 
        elif startIndex_double != -1:
            endIndex = self.triDoubleEndExpression.indexIn(text, startIndex_double + self.triDoubleStartExpression.matchedLength())
            if endIndex == -1:
                self.setCurrentBlockState(2)
                self.setFormat(startIndex_double, len(text) - startIndex_double, self.triDoubleQuoteFormat)
            else:
                length = endIndex - startIndex_double + self.triDoubleEndExpression.matchedLength()
                self.setFormat(startIndex_double, length, self.triDoubleQuoteFormat)
                self.setCurrentBlockState(0)
                self.process_remaining_text_for_multiline(text, startIndex_double + length) 
        else:
            if self.currentBlockState() not in [1,2]: 
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
            "\\bthrow\\b", "\\btry\\b", "\\busing\\b",
            "\\bHIGH\\b", "\\bLOW\\b", "\\bINPUT\\b", "\\bOUTPUT\\b", "\\bINPUT_PULLUP\\b",
            "\\btrue\\b", "\\bfalse\\b", "\\bboolean\\b", "\\bbyte\\b", "\\bword\\b",
            "\\bString\\b"
        ]
        for word in keywords:
            self.highlightingRules.append(HighlightingRule(word, keywordFormat))

        preprocessorFormat = QTextCharFormat()
        preprocessorFormat.setForeground(QColor("#C586C0")) 
        self.highlightingRules.append(HighlightingRule("^\\s*#.*", preprocessorFormat)) 

        singleLineCommentFormat = QTextCharFormat()
        singleLineCommentFormat.setForeground(QColor("#6A9955")) 
        self.highlightingRules.append(HighlightingRule("//[^\n]*", singleLineCommentFormat))

        self.multiLineCommentFormat = QTextCharFormat()
        self.multiLineCommentFormat.setForeground(QColor("#6A9955")) 
        self.commentStartExpression = QRegExp("/\\*")
        self.commentEndExpression = QRegExp("\\*/")

        stringFormat = QTextCharFormat()
        stringFormat.setForeground(QColor("#CE9178")) 
        self.highlightingRules.append(HighlightingRule("\"(\\\\.|[^\"])*\"", stringFormat)) 
        self.highlightingRules.append(HighlightingRule("'(\\\\.|[^'])*'", stringFormat))   

        numberFormat = QTextCharFormat()
        numberFormat.setForeground(QColor("#B5CEA8")) 
        self.highlightingRules.append(HighlightingRule("\\b[0-9]+[lLfF]?\\b", numberFormat)) 
        self.highlightingRules.append(HighlightingRule("\\b0[xX][0-9a-fA-F]+[lL]?\\b", numberFormat)) 
        self.highlightingRules.append(HighlightingRule("\\b[0-9]*\\.[0-9]+([eE][-+]?[0-9]+)?[fF]?\\b", numberFormat)) 

        functionFormat = QTextCharFormat()
        functionFormat.setForeground(QColor("#DCDCAA")) 
        self.highlightingRules.append(HighlightingRule("\\b[A-Za-z_][A-Za-z0-9_]*(?=\\s*\\()", functionFormat)) 
        arduinoFunctions = ["\\bsetup\\b", "\\bloop\\b", "\\bpinMode\\b", "\\bdigitalWrite\\b", "\\bdigitalRead\\b",
                            "\\banalogRead\\b", "\\banalogWrite\\b", "\\bdelay\\b", "\\bmillis\\b", "\\bmicros\\b",
                            "\\bSerial\\b"] 
        for func in arduinoFunctions:
            self.highlightingRules.append(HighlightingRule(func, functionFormat))


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
                    if new_offset == offset : 
                        new_offset +=1
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
                    if new_offset == offset : 
                        new_offset +=1
                    offset = new_offset
                    if offset >= len(text) or length == 0: 
                        break
                    index = expression.indexIn(text, offset)


        self.setCurrentBlockState(0) 

        startIndex = 0
        if self.previousBlockState() != 1: 
            startIndex = self.commentStartExpression.indexIn(text)

        while startIndex >= 0:
            endIndex = self.commentEndExpression.indexIn(text, startIndex)
            commentLength = 0
            if endIndex == -1: 
                self.setCurrentBlockState(1)
                commentLength = len(text) - startIndex
            else: 
                commentLength = endIndex - startIndex + self.commentEndExpression.matchedLength()
            
            self.setFormat(startIndex, commentLength, self.multiLineCommentFormat)
            startIndex = self.commentStartExpression.indexIn(text, startIndex + commentLength)