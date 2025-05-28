
# bsm_designer_project/code_editor.py
from PyQt5.QtWidgets import QPlainTextEdit, QWidget, QTextEdit # Import QTextEdit
from PyQt5.QtCore import Qt, QRect, QSize, QRegExp 
from PyQt5.QtGui import QColor, QPainter, QTextFormat, QFont, QSyntaxHighlighter, QTextCharFormat, QFontMetrics
import re # Import re for CSyntaxHighlighter operators
from PyQt5.QtGui import QTextCursor

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
        
        # QFontMetrics needed for tab stop, ensure font is set
        fm = QFontMetrics(self.font()) 
        self.setTabStopDistance(fm.horizontalAdvance(' ') * 4)
        self.setLineWrapMode(QPlainTextEdit.NoWrap)

        self.current_highlighter = None # Will be set by language change


        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)
        self.cursorPositionChanged.connect(self.highlightCurrentLine)

        self.updateLineNumberAreaWidth(0)
        self.highlightCurrentLine()
        self.set_language("Python") # Default to Python


    def lineNumberAreaWidth(self):
        digits = 1
        max_val = max(1, self.blockCount())
        while max_val >= 10:
            max_val //= 10
            digits += 1
        
        fm = self.fontMetrics()
        if fm.height() == 0: 
            return 35 # Fallback width, e.g., 3 digits + padding
            
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
                
                temp_font = self.font() # Get a copy of the editor's current font
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
            selection = QTextEdit.ExtraSelection() # Corrected: Use QTextEdit.ExtraSelection
            lineColor = QColor(COLOR_ACCENT_PRIMARY_LIGHT).lighter(125) 
            selection.format.setBackground(lineColor)
            selection.format.setProperty(QTextFormat.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extraSelections.append(selection)
        self.setExtraSelections(extraSelections)

    def set_language(self, language: str):
        if self.current_highlighter:
            # QSyntaxHighlighter doesn't have an explicit 'disable' or 'remove'.
            # Setting its document to None effectively detaches it.
            self.current_highlighter.setDocument(None) 
            # It's good practice to delete the old highlighter if it's no longer needed,
            # though Python's garbage collection might handle it once no references exist.
            # self.current_highlighter.deleteLater() # Or just let GC handle it
            self.current_highlighter = None

        if language == "Python":
            self.current_highlighter = PythonHighlighter(self.document())
        elif language in ["C/C++ (Arduino)", "C/C++ (Generic)"]:
            self.current_highlighter = CSyntaxHighlighter(self.document())
        else: # Text or unknown
            self.current_highlighter = None # No highlighting
        
        # Force re-highlighting of the entire document
        if self.document():
            # Trigger rehighlight on all blocks.
            # One way is to mark the entire document as dirty.
            # Or, more directly with QSyntaxHighlighter:
            if self.current_highlighter:
                 self.current_highlighter.rehighlight()
            else:
                # If no highlighter, we need to clear existing formats.
                # This can be done by applying a default format to all blocks.
                cursor = self.textCursor()
                cursor.select(QTextCursor.Document)  # Corrected attribute # QTextEdit.SelectAll equivalent for QPlainTextEdit
                default_format = QTextCharFormat() # Create a default format
                # Set default foreground (and background if needed, though editor style might handle bg)
                # default_format.setForeground(self.palette().color(QPalette.Text)) 
                # Or use a color from your config.py
                default_format.setForeground(QColor(COLOR_TEXT_PRIMARY)) 
                
                # For QPlainTextEdit, there isn't a direct equivalent of
                # QTextCursor.setCharFormat for the entire selection easily.
                # The most reliable way to clear formats when removing a highlighter
                # is often to re-parse or re-set the text, or iterate through blocks.
                # A simpler approach for now is to just rehighlight, assuming the
                # new (or None) highlighter will correctly override/clear.
                # If formats persist, a more aggressive clear is needed.
                self.document().markContentsDirty(0, len(self.document().toPlainText()))  # Use len() instead of .length()
                self.viewport().update()


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
                # For rules that target a specific capture group (e.g., function/class names)
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
                # For rules that highlight the whole match
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

        # Handle multi-line strings (these states will override previous formats)
        # State 0: Normal, State 1: In ''' string, State 2: In """ string
        
        if self.previousBlockState() == 1: # Continuing a ''' string
            endIndex = self.triSingleEndExpression.indexIn(text, 0)
            if endIndex == -1: # Still in ''' string
                self.setCurrentBlockState(1)
                self.setFormat(0, len(text), self.triSingleQuoteFormat)
            else: # ''' string ends in this block
                length = endIndex + self.triSingleEndExpression.matchedLength()
                self.setFormat(0, length, self.triSingleQuoteFormat)
                self.setCurrentBlockState(0) 
                self.process_remaining_text_for_multiline(text, length) # Check after this one ends
        elif self.previousBlockState() == 2: # Continuing a """ string
            endIndex = self.triDoubleEndExpression.indexIn(text, 0)
            if endIndex == -1: # Still in """ string
                self.setCurrentBlockState(2)
                self.setFormat(0, len(text), self.triDoubleQuoteFormat)
            else: # """ string ends in this block
                length = endIndex + self.triDoubleEndExpression.matchedLength()
                self.setFormat(0, length, self.triDoubleQuoteFormat)
                self.setCurrentBlockState(0)
                self.process_remaining_text_for_multiline(text, length) # Check after this one ends
        else: # Not in a multi-line string from previous block, check for new starts
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
            # If we are here and current block state is not already a multiline continuation, it's normal
            if self.currentBlockState() not in [1, 2]:
                 self.setCurrentBlockState(0)


class HighlightingRule:
    def __init__(self, pattern_str, text_format, nth_capture_group=0, minimal=False):
        self.pattern = QRegExp(pattern_str)
        self.format = text_format
        self.nth = nth_capture_group # The capture group to highlight (1-based for QRegExp.cap())
        self.minimal = minimal
        if self.minimal:
            self.pattern.setMinimal(True)

class CSyntaxHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.highlightingRules = []

        # Keywords (C/C++) - using VSCode-like colors
        keywordFormat = QTextCharFormat()
        keywordFormat.setForeground(QColor("#569CD6")) # VSCode C++ keyword blue
        keywords = [
            "\\bchar\\b", "\\bclass\\b", "\\bconst\\b", "\\bdouble\\b", "\\benum\\b",
            "\\bexplicit\\b", "\\bextern\\b", "\\bfloat\\b", "\\bfriend\\b", "\\binline\\b",
            "\\bint\\b", "\\blong\\b", "\\bnamespace\\b", "\\boperator\\b", "\\bprivate\\b",
            "\\bprotected\\b", "\\bpublic\\b", "\\bshort\\b", 
            "\\bsignals\\b", # Qt specific
            "\\bslots\\b", "\\bstatic\\b", "\\bstruct\\b", "\\btemplate\\b", "\\bthis\\b",
            "\\btypedef\\b", "\\btypename\\b", "\\bunion\\b", "\\bunsigned\\b", "\\bvirtual\\b",
            "\\bvoid\\b", "\\bvolatile\\b", "\\bwchar_t\\b",
            # Control flow
            "\\bbreak\\b", "\\bcase\\b", "\\bcontinue\\b", "\\bdefault\\b", "\\bdo\\b",
            "\\belse\\b", "\\bfor\\b", "\\bgoto\\b", "\\bif\\b", "\\breturn\\b",
            "\\bswitch\\b", "\\bwhile\\b",
            # C++ specific
            "\\bauto\\b", "\\bbool\\b", "\\bcatch\\b", "\\bconstexpr\\b", "\\bdecltype\\b",
            "\\bdelete\\b", "\\bfinal\\b", "\\bmutable\\b", "\\bnew\\b", "\\bnoexcept\\b",
            "\\bnullptr\\b", "\\boverride\\b", "\\bstatic_assert\\b", 
            "\\bstatic_cast\\b", "\\bdynamic_cast\\b", "\\breinterpret_cast\\b", "\\bconst_cast\\b",
            "\\bthrow\\b", "\\btry\\b", "\\busing\\b",
            # Arduino specific (often macros or typedefs but common)
            "\\bHIGH\\b", "\\bLOW\\b", "\\bINPUT\\b", "\\bOUTPUT\\b", "\\bINPUT_PULLUP\\b",
            "\\bLED_BUILTIN\\b",
            "\\btrue\\b", "\\bfalse\\b", "\\bboolean\\b", "\\bbyte\\b", "\\bword\\b",
            "\\bString\\b"
        ]
        for word in keywords:
            self.highlightingRules.append(HighlightingRule(word, keywordFormat))

        # Preprocessor directives
        preprocessorFormat = QTextCharFormat()
        preprocessorFormat.setForeground(QColor("#C586C0")) # VSCode C++ macro purple
        self.highlightingRules.append(HighlightingRule("^\\s*#\\s*[A-Za-z_]+", preprocessorFormat)) # More specific: # followed by word

        # Single-line comments
        singleLineCommentFormat = QTextCharFormat()
        singleLineCommentFormat.setForeground(QColor("#6A9955")) # Green
        self.highlightingRules.append(HighlightingRule("//[^\n]*", singleLineCommentFormat))

        # Multi-line comments (C-style)
        self.multiLineCommentFormat = QTextCharFormat()
        self.multiLineCommentFormat.setForeground(QColor("#6A9955")) # Green
        self.commentStartExpression = QRegExp("/\\*")
        self.commentEndExpression = QRegExp("\\*/")

        # Strings
        stringFormat = QTextCharFormat()
        stringFormat.setForeground(QColor("#CE9178")) # Orangey-brown
        # Rule for double-quoted strings, handles escaped quotes
        self.highlightingRules.append(HighlightingRule("\"[^\"\\\\]*(\\\\.[^\"\\\\]*)*\"", stringFormat))
        # Rule for single-quoted char literals, handles escaped quotes
        self.highlightingRules.append(HighlightingRule("'[^'\\\\]*(\\\\.[^'\\\\]*)*'", stringFormat))

        # Numbers
        numberFormat = QTextCharFormat()
        numberFormat.setForeground(QColor("#B5CEA8")) # Light green
        # Integer, long, unsigned, float, double suffixes
        self.highlightingRules.append(HighlightingRule("\\b[0-9]+[uUlLfF]?\\b", numberFormat)) 
        self.highlightingRules.append(HighlightingRule("\\b0[xX][0-9a-fA-F]+[uUlL]?\\b", numberFormat)) # Hex
        self.highlightingRules.append(HighlightingRule("\\b[0-9]*\\.[0-9]+([eE][-+]?[0-9]+)?[fFlL]?\\b", numberFormat)) # Floating point
        self.highlightingRules.append(HighlightingRule("\\b[0-9]+\\.([eE][-+]?[0-9]+)?[fFlL]?\\b", numberFormat)) # e.g. 1.e2

        # Operators
        operatorFormat = QTextCharFormat()
        operatorFormat.setForeground(QColor("#D4D4D4")) # VSCode default text color
        operators = ['==', '!=', '<=', '>=', '&&', '\\|\\|', '\\+', '-', '\\*', '/', '%', '&', '\\|', '\\^', '~', '!', '<', '>',
                     '\\+=', '-=', '\\*=', '/=', '%=', '&=', '\\|=', '\\^=', '<<=', '>>=', '\\+\\+', '--', '->', '\\.', '::']
        for op_str in operators:
            # For symbolic operators, direct escape. For word operators (if any were here), use boundaries.
            # Since C/C++ operators are mostly symbolic, re.escape is generally fine.
            self.highlightingRules.append(HighlightingRule(re.escape(op_str), operatorFormat))


        # Function names (basic: after a type and space, or common Arduino functions)
        functionFormat = QTextCharFormat()
        functionFormat.setForeground(QColor("#DCDCAA")) # VSCode function name yellow
        self.highlightingRules.append(HighlightingRule("\\b[A-Za-z_][A-Za-z0-9_]*(?=\\s*\\()", functionFormat)) # Word followed by (
        # Arduino common functions
        arduinoFunctions = ["\\bsetup\\b", "\\bloop\\b", "\\bpinMode\\b", "\\bdigitalWrite\\b", "\\bdigitalRead\\b",
                            "\\banalogRead\\b", "\\banalogWrite\\b", "\\bdelay\\b", "\\bmillis\\b", "\\bmicros\\b",
                            "\\bSerial\\b"] # Serial is an object but often used like a function namespace
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


        self.setCurrentBlockState(0) # Default state (outside multi-line comment)

        startIndex = 0
        if self.previousBlockState() != 1: # If not already in a comment
            startIndex = self.commentStartExpression.indexIn(text)

        while startIndex >= 0:
            endIndex = self.commentEndExpression.indexIn(text, startIndex + self.commentStartExpression.matchedLength())
            commentLength = 0
            if endIndex == -1: # Comment continues to next block
                self.setCurrentBlockState(1)
                commentLength = len(text) - startIndex
            else: # Comment ends in this block
                commentLength = endIndex - startIndex + self.commentEndExpression.matchedLength()
            
            self.setFormat(startIndex, commentLength, self.multiLineCommentFormat)
            startIndex = self.commentStartExpression.indexIn(text, startIndex + commentLength)
