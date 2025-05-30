# bsm_designer_project/code_editor.py
from PyQt5.QtWidgets import QPlainTextEdit, QWidget, QTextEdit
from PyQt5.QtCore import Qt, QRect, QSize, QRegExp 
from PyQt5.QtGui import (
    QColor, QPainter, QTextFormat, QFont, QSyntaxHighlighter, 
    QTextCharFormat, QFontMetrics, QTextCursor, QPalette
)

from config import (
    COLOR_BACKGROUND_MEDIUM, COLOR_ACCENT_PRIMARY_LIGHT, COLOR_TEXT_PRIMARY, COLOR_ACCENT_PRIMARY,
    # Import new dark theme editor colors
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
        
        # QFontMetrics needed for tab stop, ensure font is set
        fm = QFontMetrics(self.font()) 
        self.setTabStopDistance(fm.horizontalAdvance(' ') * 4)
        self.setLineWrapMode(QPlainTextEdit.NoWrap)

        self.current_highlighter = None # Will be set by language change


        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)
        self.cursorPositionChanged.connect(self.highlightCurrentLine)
        self.cursorPositionChanged.connect(self.lineNumberArea.update) # Ensure line number area updates on cursor move for current line highlight

        self.updateLineNumberAreaWidth(0)
        # Initial highlightCurrentLine might be called before stylesheets fully apply,
        # so it's also called after language set and in paint events or cursor moves.
        self.highlightCurrentLine() 
        self.set_language("Python") # Default to Python


    def _is_dark_theme_active(self) -> bool:
        # Check the lightness of the base background color of the editor's palette.
        # This assumes that if a dark stylesheet is applied, it correctly sets the QPalette.Base.
        editor_bg_color = self.palette().color(QPalette.Base)
        
        # A common threshold for "dark" is lightness < 0.5.
        # We also explicitly check against our defined dark background color from config
        # in case the palette update from stylesheet isn't direct for QPalette.Base.
        return editor_bg_color.lightnessF() < 0.45 or editor_bg_color == COLOR_EDITOR_DARK_BACKGROUND

    def lineNumberAreaWidth(self):
        digits = 1
        max_val = max(1, self.blockCount())
        while max_val >= 10:
            max_val //= 10
            digits += 1
        
        fm = self.fontMetrics()
        if fm.height() == 0: 
            return 35 # Fallback width, e.g., 3 digits + padding
            
        padding = fm.horizontalAdvance(' ') * 2 # Added a bit more padding
        space = padding + fm.horizontalAdvance('9') * digits
        return space

    def updateLineNumberAreaWidth(self, _=None): # Allow calling without arg
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
        # viewport().geometry().top() is 0, use contentOffset for correct calculation
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()

        current_line_bg_color_ln = COLOR_EDITOR_DARK_CURRENT_LINE_BG_LN_AREA if is_dark else QColor(COLOR_ACCENT_PRIMARY_LIGHT)
        current_line_num_color_ln = COLOR_EDITOR_DARK_CURRENT_LINE_FG_LN_AREA if is_dark else QColor(COLOR_ACCENT_PRIMARY) 
        normal_line_num_color_ln = COLOR_EDITOR_DARK_LINE_NUM_FG if is_dark else QColor(COLOR_TEXT_PRIMARY).darker(130)

        fm = self.fontMetrics() 
        right_padding = fm.horizontalAdvance(' ') // 2 # Small padding from the right edge

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(blockNumber + 1)
                
                temp_font = self.font() # Get a copy of the editor's current font
                if self.textCursor().blockNumber() == blockNumber:
                    painter.fillRect(QRect(0, int(top), self.lineNumberArea.width(), int(fm.height())), current_line_bg_color_ln)
                    painter.setPen(current_line_num_color_ln)
                    temp_font.setBold(True)
                else:
                    painter.setPen(normal_line_num_color_ln)
                    temp_font.setBold(False)
                painter.setFont(temp_font)
                
                # Draw text slightly offset from the right edge for padding
                painter.drawText(0, int(top), self.lineNumberArea.width() - right_padding,
                                 int(fm.height()),
                                 Qt.AlignRight | Qt.AlignVCenter, number) # Added AlignVCenter

            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            blockNumber += 1

    def highlightCurrentLine(self):
        extraSelections = []
        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection() # Corrected: Use QTextEdit.ExtraSelection
            is_dark = self._is_dark_theme_active()
            
            # Color for the current line background in the editor area
            line_color_editor = COLOR_EDITOR_DARK_CURRENT_LINE_BG_EDITOR if is_dark else QColor(COLOR_ACCENT_PRIMARY_LIGHT).lighter(125)
            
            selection.format.setBackground(line_color_editor)
            selection.format.setProperty(QTextFormat.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extraSelections.append(selection)
        self.setExtraSelections(extraSelections)
        # self.lineNumberArea.update() # Already connected to cursorPositionChanged

    def set_language(self, language: str):
        if self.current_highlighter:
            # QSyntaxHighlighter doesn't have an explicit 'disable' or 'remove'.
            # Setting its document to None effectively detaches it.
            self.current_highlighter.setDocument(None) 
            self.current_highlighter = None

        doc = self.document()
        if language == "Python":
            self.current_highlighter = PythonHighlighter(doc)
        elif language in ["C/C++ (Arduino)", "C/C++ (Generic)"]:
            self.current_highlighter = CSyntaxHighlighter(doc)
        # else: # Text or unknown, current_highlighter remains None
        
        # Trigger a rehighlight of the entire document to apply the new
        # highlighter (or clear existing highlights if no new highlighter is set).
        if doc:
            doc.rehighlight()
            # The viewport update might still be beneficial in some edge cases
            # or if rehighlight itself doesn't force an immediate repaint.
            self.viewport().update()
            self.highlightCurrentLine() # Re-apply current line highlight in case its color scheme needs to change
            self.lineNumberArea.update() # And update the line number area too

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
                # We need to find the overall match first, then get the captured group.
                index = expression.indexIn(text, offset)
                while index >= 0:
                    # Get the start and length of the Nth capture group
                    # QRegExp.pos(nth) returns the start position of the nth captured text.
                    # QRegExp.cap(nth) returns the string of the nth captured text.
                    capture_start = expression.pos(rule.nth) 
                    capture_text = expression.cap(rule.nth)
                    capture_length = len(capture_text)

                    if capture_start != -1 and capture_length > 0:
                        self.setFormat(capture_start, capture_length, rule.format)
                    
                    # Advance offset to search after the current full match
                    new_offset = index + expression.matchedLength()
                    if new_offset == offset : # Prevent infinite loop if match is zero-length or not advancing
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
                    if new_offset == offset : # Prevent infinite loop
                        new_offset +=1
                    offset = new_offset
                    if offset >= len(text) or length == 0: 
                        break
                    index = expression.indexIn(text, offset)

        # Handle multi-line strings (these states will override previous formats)
        # State 0: Normal, State 1: In ''' string, State 2: In """ string
        
        # Determine initial state for this block
        if self.previousBlockState() == 1: # Continuing a ''' string
            current_multiline_state = 1
            startIndex = 0 # Search for end from beginning of block
        elif self.previousBlockState() == 2: # Continuing a """ string
            current_multiline_state = 2
            startIndex = 0 # Search for end from beginning of block
        else: # Not in a multi-line string from previous block
            current_multiline_state = 0
            startIndex = -1 # Will be set by start expression match

        # Process based on state
        if current_multiline_state == 1: # Continuing or ending '''
            endIndex = self.triSingleEndExpression.indexIn(text, startIndex)
            if endIndex == -1: # Still in ''' string
                self.setCurrentBlockState(1)
                self.setFormat(0, len(text), self.triSingleQuoteFormat)
            else: # ''' string ends in this block
                length = endIndex - startIndex + self.triSingleEndExpression.matchedLength()
                self.setFormat(startIndex, length, self.triSingleQuoteFormat)
                self.setCurrentBlockState(0) # Reset to normal state
                # Check if another """ or ''' starts after this one in the same block
                self.process_remaining_text_for_multiline(text, startIndex + length)
        elif current_multiline_state == 2: # Continuing or ending """
            endIndex = self.triDoubleEndExpression.indexIn(text, startIndex)
            if endIndex == -1: # Still in """ string
                self.setCurrentBlockState(2)
                self.setFormat(0, len(text), self.triDoubleQuoteFormat)
            else: # """ string ends in this block
                length = endIndex - startIndex + self.triDoubleEndExpression.matchedLength()
                self.setFormat(startIndex, length, self.triDoubleQuoteFormat)
                self.setCurrentBlockState(0)
                self.process_remaining_text_for_multiline(text, startIndex + length)
        else: # Not in a multi-line string from previous block, check for new starts
            self.process_remaining_text_for_multiline(text, 0)

    def process_remaining_text_for_multiline(self, text, offset):
        # This function is called to check for new multiline strings
        # after a multiline string has ended, or from the start of a block.
        
        # Check for '''
        startIndex_single = self.triSingleStartExpression.indexIn(text, offset)
        # Check for """
        startIndex_double = self.triDoubleStartExpression.indexIn(text, offset)

        if startIndex_single != -1 and (startIndex_double == -1 or startIndex_single < startIndex_double):
            # ''' starts first or """ not found
            endIndex = self.triSingleEndExpression.indexIn(text, startIndex_single + self.triSingleStartExpression.matchedLength())
            if endIndex == -1:
                self.setCurrentBlockState(1)
                self.setFormat(startIndex_single, len(text) - startIndex_single, self.triSingleQuoteFormat)
            else:
                length = endIndex - startIndex_single + self.triSingleEndExpression.matchedLength()
                self.setFormat(startIndex_single, length, self.triSingleQuoteFormat)
                self.setCurrentBlockState(0) # Ends in this block
                self.process_remaining_text_for_multiline(text, startIndex_single + length) # Recurse for more
        elif startIndex_double != -1:
            # """ starts first or ''' not found (or ''' was after current search point)
            endIndex = self.triDoubleEndExpression.indexIn(text, startIndex_double + self.triDoubleStartExpression.matchedLength())
            if endIndex == -1:
                self.setCurrentBlockState(2)
                self.setFormat(startIndex_double, len(text) - startIndex_double, self.triDoubleQuoteFormat)
            else:
                length = endIndex - startIndex_double + self.triDoubleEndExpression.matchedLength()
                self.setFormat(startIndex_double, length, self.triDoubleQuoteFormat)
                self.setCurrentBlockState(0)
                self.process_remaining_text_for_multiline(text, startIndex_double + length) # Recurse for more
        else:
             # No new multiline string started, ensure state is 0 if not already handled
            if self.currentBlockState() not in [1,2]: #Only if not set by a previous ending multiline that extends
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
            "\\bprotected\\b", "\\bpublic\\b", "\\bshort\\b", "\\bsignals\\b", "\\bsigned\\b", # Qt specific
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
            "\\bnullptr\\b", "\\boverride\\b", "\\bstatic_assert\\b", "\\bstatic_cast\\b",
            "\\bthrow\\b", "\\btry\\b", "\\busing\\b",
            # Arduino specific (often macros or typedefs but common)
            "\\bHIGH\\b", "\\bLOW\\b", "\\bINPUT\\b", "\\bOUTPUT\\b", "\\bINPUT_PULLUP\\b",
            "\\btrue\\b", "\\bfalse\\b", "\\bboolean\\b", "\\bbyte\\b", "\\bword\\b",
            "\\bString\\b"
        ]
        for word in keywords:
            self.highlightingRules.append(HighlightingRule(word, keywordFormat))

        # Preprocessor directives
        preprocessorFormat = QTextCharFormat()
        preprocessorFormat.setForeground(QColor("#C586C0")) # VSCode C++ macro purple
        self.highlightingRules.append(HighlightingRule("^\\s*#.*", preprocessorFormat)) # Matches lines starting with #

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
        self.highlightingRules.append(HighlightingRule("\"(\\\\.|[^\"])*\"", stringFormat)) # Double quotes
        self.highlightingRules.append(HighlightingRule("'(\\\\.|[^'])*'", stringFormat))   # Single quotes (char literals)

        # Numbers
        numberFormat = QTextCharFormat()
        numberFormat.setForeground(QColor("#B5CEA8")) # Light green
        self.highlightingRules.append(HighlightingRule("\\b[0-9]+[lLfF]?\\b", numberFormat)) # Integers, long, float
        self.highlightingRules.append(HighlightingRule("\\b0[xX][0-9a-fA-F]+[lL]?\\b", numberFormat)) # Hex
        self.highlightingRules.append(HighlightingRule("\\b[0-9]*\\.[0-9]+([eE][-+]?[0-9]+)?[fF]?\\b", numberFormat)) # Floating point

        # Function names (basic: after a type and space, or common Arduino functions)
        functionFormat = QTextCharFormat()
        functionFormat.setForeground(QColor("#DCDCAA")) # Light yellow
        self.highlightingRules.append(HighlightingRule("\\b[A-Za-z_][A-Za-z0-9_]*(?=\\s*\\()", functionFormat)) # Word followed by (
        # Arduino common functions
        arduinoFunctions = ["\\bsetup\\b", "\\bloop\\b", "\\bpinMode\\b", "\\bdigitalWrite\\b", "\\bdigitalRead\\b",
                            "\\banalogRead\\b", "\\banalogWrite\\b", "\\bdelay\\b", "\\bmillis\\b", "\\bmicros\\b",
                            "\\bSerial\\b"] # Serial is an object but often used like a function namespace
        for func in arduinoFunctions:
            self.highlightingRules.append(HighlightingRule(func, functionFormat))


    def highlightBlock(self, text):
        for rule in self.highlightingRules:
            expression = rule.pattern # QRegExp is already created in HighlightingRule
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
            endIndex = self.commentEndExpression.indexIn(text, startIndex)
            commentLength = 0
            if endIndex == -1: # Comment continues to next block
                self.setCurrentBlockState(1)
                commentLength = len(text) - startIndex
            else: # Comment ends in this block
                commentLength = endIndex - startIndex + self.commentEndExpression.matchedLength()
            
            self.setFormat(startIndex, commentLength, self.multiLineCommentFormat)
            startIndex = self.commentStartExpression.indexIn(text, startIndex + commentLength)