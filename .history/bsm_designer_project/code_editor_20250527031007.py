
# bsm_designer_project/code_editor.py
from PyQt5.QtWidgets import QPlainTextEdit, QWidget, QTextEdit, QCompleter # Import QCompleter
from PyQt5.QtCore import Qt, QRect, QSize, QRegExp, QStringListModel # Import QStringListModel
from PyQt5.QtGui import QColor, QPainter, QTextFormat, QFont, QSyntaxHighlighter, QTextCharFormat, QFontMetrics, QPalette, QKeyEvent, QTextCursor
import re # Import re for CSyntaxHighlighter operators

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
        
        font = QFont("Consolas, 'Courier New', monospace", 10)
        self.setFont(font)
        
        fm = QFontMetrics(self.font()) 
        self.setTabStopDistance(fm.horizontalAdvance(' ') * 4)
        self.setLineWrapMode(QPlainTextEdit.NoWrap)

        self.current_highlighter = None 
        self.completer = None


        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)
        self.cursorPositionChanged.connect(self.highlightCurrentLine)

        # print(f"CodeEditor {id(self)} isReadOnly: {self.isReadOnly()}") # DEBUG

        self.updateLineNumberAreaWidth(0)
        self.highlightCurrentLine()
        self.set_language("Python") 


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
            selection = QTextEdit.ExtraSelection() 
            lineColor = QColor(COLOR_ACCENT_PRIMARY_LIGHT).lighter(125) 
            selection.format.setBackground(lineColor)
            selection.format.setProperty(QTextFormat.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extraSelections.append(selection)
        self.setExtraSelections(extraSelections)

    def _setup_python_completer(self):
        if self.completer: 
            self.completer.setWidget(None)
        
        self.completer = QCompleter(self)
        self.completer.setWidget(self) 
        self.completer.setCompletionMode(QCompleter.PopupCompletion)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive) 

        python_keywords = [
            "False", "None", "True", "and", "as", "assert", "async", "await", 
            "break", "class", "continue", "def", "del", "elif", "else", 
            "except", "finally", "for", "from", "global", "if", "import", 
            "in", "is", "lambda", "nonlocal", "not", "or", "pass", "raise", 
            "return", "try", "while", "with", "yield", "self", "cls", "super"
        ]
        python_builtins = [
            "print", "len", "abs", "min", "max", "int", "float", "str", "bool", 
            "list", "dict", "set", "tuple", "range", "sorted", "sum", "all", 
            "any", "isinstance", "hasattr", "Exception", "TypeError", "ValueError", "NameError"
        ]
        completion_list = sorted(list(set(python_keywords + python_builtins))) 
        
        model = QStringListModel(completion_list, self.completer)
        self.completer.setModel(model)
        self.completer.activated[str].connect(self.insert_completion)

    def insert_completion(self, completion):
        tc = self.textCursor()
        prefix_len = len(self.completer.completionPrefix())
        tc.insertText(completion[prefix_len:])
        self.setTextCursor(tc)
        self.completer.popup().hide() 


    def set_language(self, language: str):
        if self.current_highlighter:
            self.current_highlighter.setDocument(None) 
            self.current_highlighter = None
        
        if self.completer: 
            self.completer.setWidget(None)
            self.completer = None

        doc = self.document()
        if language == "Python":
            self.current_highlighter = PythonHighlighter(doc)
            self._setup_python_completer()
        elif language in ["C/C++ (Arduino)", "C/C++ (Generic)"]:
            self.current_highlighter = CSyntaxHighlighter(doc)
        else: 
            self.current_highlighter = None 
        
        if self.current_highlighter: 
             self.current_highlighter.rehighlight()
        elif doc: 
            cursor = self.textCursor()
            cursor.select(QTextCursor.Document) 
            default_format = QTextCharFormat() 
            default_format.setForeground(self.palette().color(QPalette.Text))
            cursor.setCharFormat(default_format) 
            cursor.clearSelection()
            self.setTextCursor(cursor) 
            doc.markContentsDirty(0, doc.toPlainText().length())
            self.viewport().update() 

    def textUnderCursor(self) -> str:
        tc = self.textCursor()
        pos_in_block = tc.positionInBlock()
        text = tc.block().text()
        start_of_word = pos_in_block
        # Iterate backwards from cursor to find start of current word part
        while start_of_word > 0 and (text[start_of_word - 1].isalnum() or text[start_of_word -1] == '_'):
            start_of_word -=1
        
        # Create a new cursor to select text without moving the main editor cursor yet
        temp_tc = QTextCursor(tc.block())
        temp_tc.setPosition(tc.block().position() + start_of_word)
        temp_tc.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, pos_in_block - start_of_word)
        return temp_tc.selectedText()


    def keyPressEvent(self, event: QKeyEvent):
        if self.completer and self.completer.popup().isVisible():
            if event.key() in [Qt.Key_Enter, Qt.Key_Return, Qt.Key_Escape, Qt.Key_Tab, Qt.Key_Backtab]:
                event.ignore() 
                return 
            # Let QCompleter handle Up/Down arrows if popup is visible
            elif event.key() in [Qt.Key_Up, Qt.Key_Down]:
                 pass # QCompleter will handle this if event is not ignored before super call

        super().keyPressEvent(event) 

        if self.completer:
            ctrlOrShift = event.modifiers() & (Qt.ControlModifier | Qt.ShiftModifier)
            current_char = event.text() # Character that was just inserted by super().keyPressEvent

            # Don't complete on space, or if popup is already visible and an ignored key was pressed (already handled)
            # Also, don't pop up immediately after a non-alphanumeric char (except perhaps '_')
            if current_char and (current_char.isalnum() or current_char == '_') and not ctrlOrShift:
                prefix = self.textUnderCursor()
                
                if len(prefix) >= 1:  # Trigger completion for prefix of 1 or more
                    if prefix != self.completer.completionPrefix():
                        self.completer.setCompletionPrefix(prefix)
                    
                    if self.completer.model().rowCount() > 0 : # Check if model has any matches
                        popup = self.completer.popup()
                        # popup.setCurrentIndex(self.completer.completionModel().index(0,0)) # Option: Select first item
                        cr = self.cursorRect()
                        cr.setWidth(self.completer.popup().sizeHintForColumn(0) 
                                    + self.completer.popup().verticalScrollBar().sizeHint().width())
                        self.completer.complete(cr) 
                    else:
                        self.completer.popup().hide()
                else:
                    self.completer.popup().hide() 
            # Hide on backspace/delete or if the prefix becomes empty
            elif event.key() == Qt.Key_Backspace or event.key() == Qt.Key_Delete or not self.textUnderCursor():
                 self.completer.popup().hide()


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
            endIndex = self.triSingleEndExpression.indexIn(text, 0)
            if endIndex == -1: 
                self.setCurrentBlockState(1)
                self.setFormat(0, len(text), self.triSingleQuoteFormat)
            else: 
                length = endIndex + self.triSingleEndExpression.matchedLength()
                self.setFormat(0, length, self.triSingleQuoteFormat)
                self.setCurrentBlockState(0) 
                self.process_remaining_text_for_multiline(text, length) 
        elif self.previousBlockState() == 2: 
            endIndex = self.triDoubleEndExpression.indexIn(text, 0)
            if endIndex == -1: 
                self.setCurrentBlockState(2)
                self.setFormat(0, len(text), self.triDoubleQuoteFormat)
            else: 
                length = endIndex + self.triDoubleEndExpression.matchedLength()
                self.setFormat(0, length, self.triDoubleQuoteFormat)
                self.setCurrentBlockState(0)
                self.process_remaining_text_for_multiline(text, length) 
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
            if self.currentBlockState() not in [1, 2]:
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
            "\\bprotected\\b", "\\bpublic\\b", "\\bshort\\b", 
            "\\bsignals\\b", 
            "\\bslots\\b", "\\bstatic\\b", "\\bstruct\\b", "\\btemplate\\b", "\\bthis\\b",
            "\\btypedef\\b", "\\btypename\\b", "\\bunion\\b", "\\bunsigned\\b", "\\bvirtual\\b",
            "\\bvoid\\b", "\\bvolatile\\b", "\\bwchar_t\\b",
            "\\bbreak\\b", "\\bcase\\b", "\\bcontinue\\b", "\\bdefault\\b", "\\bdo\\b",
            "\\belse\\b", "\\bfor\\b", "\\bgoto\\b", "\\bif\\b", "\\breturn\\b",
            "\\bswitch\\b", "\\bwhile\\b",
            "\\bauto\\b", "\\bbool\\b", "\\bcatch\\b", "\\bconstexpr\\b", "\\bdecltype\\b",
            "\\bdelete\\b", "\\bfinal\\b", "\\bmutable\\b", "\\bnew\\b", "\\bnoexcept\\b",
            "\\bnullptr\\b", "\\boverride\\b", "\\bstatic_assert\\b", 
            "\\bstatic_cast\\b", "\\bdynamic_cast\\b", "\\breinterpret_cast\\b", "\\bconst_cast\\b",
            "\\bthrow\\b", "\\btry\\b", "\\busing\\b",
            "\\bHIGH\\b", "\\bLOW\\b", "\\bINPUT\\b", "\\bOUTPUT\\b", "\\bINPUT_PULLUP\\b",
            "\\bLED_BUILTIN\\b",
            "\\btrue\\b", "\\bfalse\\b", "\\bboolean\\b", "\\bbyte\\b", "\\bword\\b",
            "\\bString\\b"
        ]
        for word in keywords:
            self.highlightingRules.append(HighlightingRule(word, keywordFormat))

        preprocessorFormat = QTextCharFormat()
        preprocessorFormat.setForeground(QColor("#C586C0")) 
        self.highlightingRules.append(HighlightingRule("^\\s*#\\s*[A-Za-z_]+", preprocessorFormat)) 

        singleLineCommentFormat = QTextCharFormat()
        singleLineCommentFormat.setForeground(QColor("#6A9955")) 
        self.highlightingRules.append(HighlightingRule("//[^\n]*", singleLineCommentFormat))

        self.multiLineCommentFormat = QTextCharFormat()
        self.multiLineCommentFormat.setForeground(QColor("#6A9955")) 
        self.commentStartExpression = QRegExp("/\\*")
        self.commentEndExpression = QRegExp("\\*/")

        stringFormat = QTextCharFormat()
        stringFormat.setForeground(QColor("#CE9178")) 
        self.highlightingRules.append(HighlightingRule("\"[^\"\\\\]*(\\\\.[^\"\\\\]*)*\"", stringFormat))
        self.highlightingRules.append(HighlightingRule("'[^'\\\\]*(\\\\.[^'\\\\]*)*'", stringFormat))   

        numberFormat = QTextCharFormat()
        numberFormat.setForeground(QColor("#B5CEA8")) 
        self.highlightingRules.append(HighlightingRule("\\b[0-9]+[uUlLfF]?\\b", numberFormat)) 
        self.highlightingRules.append(HighlightingRule("\\b0[xX][0-9a-fA-F]+[uUlL]?\\b", numberFormat)) 
        self.highlightingRules.append(HighlightingRule("\\b[0-9]*\\.[0-9]+([eE][-+]?[0-9]+)?[fFlL]?\\b", numberFormat)) 
        self.highlightingRules.append(HighlightingRule("\\b[0-9]+\\.([eE][-+]?[0-9]+)?[fFlL]?\\b", numberFormat)) 

        operatorFormat = QTextCharFormat()
        operatorFormat.setForeground(QColor("#D4D4D4")) 
        operators = ['==', '!=', '<=', '>=', '&&', '\\|\\|', '\\+', '-', '\\*', '/', '%', '&', '\\|', '\\^', '~', '!', '<', '>',
                     '\\+=', '-=', '\\*=', '/=', '%=', '&=', '\\|=', '\\^=', '<<=', '>>=', '\\+\\+', '--', '->', '\\.', '::']
        for op_str in operators:
            self.highlightingRules.append(HighlightingRule(re.escape(op_str), operatorFormat))


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
            endIndex = self.commentEndExpression.indexIn(text, startIndex + self.commentStartExpression.matchedLength())
            commentLength = 0
            if endIndex == -1: 
                self.setCurrentBlockState(1)
                commentLength = len(text) - startIndex
            else: 
                commentLength = endIndex - startIndex + self.commentEndExpression.matchedLength()
            
            self.setFormat(startIndex, commentLength, self.multiLineCommentFormat)
            startIndex = self.commentStartExpression.indexIn(text, startIndex + commentLength)
