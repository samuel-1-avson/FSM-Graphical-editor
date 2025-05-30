# bsm_designer_project/code_editor.py
from PyQt5.QtWidgets import QPlainTextEdit, QWidget, QTextEdit # Import QTextEdit
from PyQt5.QtCore import Qt, QRect, QSize, QRegExp 
from PyQt5.QtGui import QColor, QPainter, QTextFormat, QFont, QSyntaxHighlighter, QTextCharFormat, QFontMetrics
from PyQt5.QtGui import QPalette
# ...other imports...
from config import (
    COLOR_BACKGROUND_MEDIUM, COLOR_ACCENT_PRIMARY_LIGHT, COLOR_TEXT_PRIMARY,
    COLOR_ACCENT_PRIMARY, COLOR_TEXT_EDITOR_DARK_SECONDARY,
    COLOR_BACKGROUND_EDITOR_DARK, COLOR_TEXT_EDITOR_DARK_PRIMARY, APP_FONT_SIZE_EDITOR,
    APP_FONT_FAMILY # Import APP_FONT_FAMILY
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
        
        # Use font size from config, default to Consolas or Courier New
        editor_font_size = 10 
        try:
            editor_font_size_val = int(APP_FONT_SIZE_EDITOR.replace("pt", ""))
            if 8 <= editor_font_size_val <= 24:
                editor_font_size = editor_font_size_val
        except ValueError:
            pass # Keep default 10 if parsing fails
            
        font = QFont("Consolas, 'Courier New', monospace", editor_font_size)
        font.setStyleHint(QFont.Monospace)
        self.setFont(font)
        
        # QFontMetrics needed for tab stop, ensure font is set
        fm = QFontMetrics(self.font()) 
        self.setTabStopDistance(fm.horizontalAdvance(' ') * 4) # Standard 4-space tab
        self.setLineWrapMode(QPlainTextEdit.NoWrap)

        self.current_highlighter = None # Will be set by language change


        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)
        self.cursorPositionChanged.connect(self.highlightCurrentLine)

        self.updateLineNumberAreaWidth(0)
        self.highlightCurrentLine()
        self.set_language("Python") # Default to Python
        
        # Styling based on typical dark editor themes
        # These are often overridden by QSS for specific named editors
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
            return 40 # Fallback width
            
        # Padding: 1 char space left, 1 char space right for numbers
        padding_char_width = fm.horizontalAdvance(' ')
        # Estimate width for max number string
        space = padding_char_width + (fm.horizontalAdvance('9') * digits) + padding_char_width 
        return space + 5 # Extra 5px safety margin

    def updateLineNumberAreaWidth(self, _):
        self.setViewportMargins(self.lineNumberAreaWidth(), 0, 0, 0)

    def updateLineNumberArea(self, rect, dy):
        if dy:
            self.lineNumberArea.scroll(0, dy)
        else:
            # Update the whole visible area of the line number area
            self.lineNumberArea.update(0, rect.y(), self.lineNumberArea.width(), rect.height())

        if rect.contains(self.viewport().rect()):
            self.updateLineNumberAreaWidth(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.lineNumberArea.setGeometry(QRect(cr.left(), cr.top(), self.lineNumberAreaWidth(), cr.height()))

    def lineNumberAreaPaintEvent(self, event):
        painter = QPainter(self.lineNumberArea)
        # Background for line number area, slightly lighter/different from editor's main bg
        # for subtle separation.
        line_number_area_bg = QColor(COLOR_BACKGROUND_EDITOR_DARK).lighter(110)
        painter.fillRect(event.rect(), line_number_area_bg)

        block = self.firstVisibleBlock()
        blockNumber = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()

        current_line_highlight_bg = QColor(COLOR_BACKGROUND_EDITOR_DARK).lighter(130)
        current_line_num_color = QColor(COLOR_ACCENT_PRIMARY_LIGHT) 
        normal_line_num_color = QColor(COLOR_TEXT_EDITOR_DARK_SECONDARY) # Color from config for comments

        fm = self.fontMetrics()
        right_padding = fm.horizontalAdvance(' ') # Padding for the right of the numbers

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(blockNumber + 1)
                
                # Font settings for line number
                temp_font = self.font() 
                temp_font.setPointSize(max(8, self.font().pointSize() -1)) # Slightly smaller line numbers

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
            # Current line highlight color - should be subtle on dark background
            lineColor = QColor(COLOR_BACKGROUND_EDITOR_DARK).lighter(120)
            selection.format.setBackground(lineColor)
            selection.format.setProperty(QTextFormat.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extraSelections.append(selection)
        self.setExtraSelections(extraSelections)

    def set_language(self, language: str):
        if self.current_highlighter:
            self.current_highlighter.setDocument(None) 
            self.current_highlighter = None

        if language == "Python":
            self.current_highlighter = PythonHighlighter(self.document())
        elif language in ["C/C++ (Arduino)", "C/C++ (Generic)"]:
            self.current_highlighter = CSyntaxHighlighter(self.document())
        else: # Text or unknown
            self.current_highlighter = None # No highlighting
        
        if self.current_highlighter:
            self.current_highlighter.rehighlight()
        else: 
            # This sequence forces a full re-evaluation of formatting when highlighter is removed.
            # Directly setting text or HTML would also work but can be heavy.
            # Mark all content as dirty and emit contentsChanged to trigger re-layout/repaint.
            doc = self.document()
            if doc:
                self.blockSignals(True) # Prevent cursor flicker if any during this
                # Force all blocks to be re-formatted with default format
                cursor = self.textCursor()
                cursor.select(QTextCursor.Document)
                default_format = QTextCharFormat() # Ensure it gets base editor's fg/bg colors
                default_format.setForeground(self.palette().color(QPalette.Text))
                default_format.setBackground(self.palette().color(QPalette.Base))
                cursor.setCharFormat(default_format)
                cursor.clearSelection()
                self.blockSignals(False)
                doc.clearUndoRedoStacks()
                # One way to force re-render might be to briefly set it empty and then restore.
                # Or, a simpler approach could be a minimal text modification or forcing rehighlight
                # if there's an API on QPlainTextEdit itself (usually QSyntaxHighlighter does this).
                # A full rehighlight on document level:
                highlighter = QSyntaxHighlighter(doc) # temporary dummy
                highlighter.rehighlight()
                highlighter.setDocument(None)
                self.viewport().update()


class PythonHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None): 
        super().__init__(parent)

        self.highlightingRules = []

        # Using colors suitable for a dark background theme, inspired by common IDEs
        keywordFormat = QTextCharFormat()
        keywordFormat.setForeground(QColor("#C586C0")) # VSCode Python keyword color (magenta/purple)
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
        selfFormat.setForeground(QColor("#9CDCFE")) # VSCode Python 'self' color (light blue)
        self_keywords = ["\\bself\\b", "\\bcls\\b"]
        for word in self_keywords:
            self.highlightingRules.append(HighlightingRule(word, selfFormat))

        builtinFormat = QTextCharFormat()
        builtinFormat.setForeground(QColor("#4EC9B0")) # VSCode Python function/builtin call (teal)
        builtins = [
            "\\bprint\\b", "\\blen\\b", "\\babs\\b", "\\bmin\\b", "\\bmax\\b", 
            "\\bint\\b", "\\bfloat\\b", "\\bstr\\b", "\\bbool\\b", "\\blist\\b", 
            "\\bdict\\b", "\\bset\\b", "\\btuple\\b", "\\brange\\b", "\\bsorted\\b", 
            "\\bsum\\b", "\\ball\\b", "\\bany\\b", "\\bisinstance\\b", "\\bhasattr\\b",
            "\\bException\\b", "\\bTypeError\\b", "\\bValueError\\b", "\\bNameError\\b"
            # Consider adding common library functions if needed, e.g. from 'math', 'os'
        ]
        for word in builtins:
            self.highlightingRules.append(HighlightingRule(word, builtinFormat))

        commentFormat = QTextCharFormat()
        commentFormat.setForeground(QColor("#6A9955")) # VSCode Python comment color (green)
        commentFormat.setFontItalic(True) # Make comments italic
        self.highlightingRules.append(HighlightingRule("#[^\n]*", commentFormat))

        stringFormat = QTextCharFormat()
        stringFormat.setForeground(QColor("#CE9178")) # VSCode Python string color (light orange/brown)
        self.highlightingRules.append(HighlightingRule("'[^']*'", stringFormat))
        self.highlightingRules.append(HighlightingRule("\"[^\"]*\"", stringFormat))

        numberFormat = QTextCharFormat()
        numberFormat.setForeground(QColor("#B5CEA8")) # VSCode Python number color (pale green)
        self.highlightingRules.append(HighlightingRule("\\b[0-9]+\\.?[0-9]*([eE][-+]?[0-9]+)?\\b", numberFormat))
        self.highlightingRules.append(HighlightingRule("\\b0[xX][0-9a-fA-F]+\\b", numberFormat)) # Hex

        definitionFormat = QTextCharFormat() # For 'def' and 'class' names
        definitionFormat.setForeground(QColor("#DCDCAA")) # VSCode Python function/class definition name (light yellow)
        definitionFormat.setFontWeight(QFont.Bold) 
        self.highlightingRules.append(HighlightingRule("\\bdef\\s+([A-Za-z_][A-Za-z0-9_]*)", definitionFormat, 1, True))
        self.highlightingRules.append(HighlightingRule("\\bclass\\s+([A-Za-z_][A-Za-z0-9_]*)", definitionFormat, 1, True))
        
        operatorFormat = QTextCharFormat()
        # Use a more subtle color for operators if the default text color is too strong
        operatorFormat.setForeground(QColor(COLOR_TEXT_EDITOR_DARK_PRIMARY).lighter(110)) # Slightly lighter than main text
        operators_regex = (
            r"(\+|\-|\*|/|%|=|==|!=|<|>|<=|>=|&|\||\^|~|<<|>>|"
            r"\bnot\b|\band\b|\bor\b|\bis\b|\bin\b)" # Added more operators, and ensured keywords are whole words
        )
        self.highlightingRules.append(HighlightingRule(operators_regex, operatorFormat))
        
        # For decorators like @my_decorator
        decoratorFormat = QTextCharFormat()
        decoratorFormat.setForeground(QColor("#4EC9B0")) # Same as builtins for now, can be different
        self.highlightingRules.append(HighlightingRule("@[A-Za-z_][A-Za-z0-9_.]*", decoratorFormat))


        self.triSingleQuoteFormat = QTextCharFormat()
        self.triSingleQuoteFormat.setForeground(QColor("#CE9178")) # Same as stringFormat
        self.triDoubleQuoteFormat = QTextCharFormat()
        self.triDoubleQuoteFormat.setForeground(QColor("#CE9178")) # Same as stringFormat

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

        # Handle multi-line strings (these states will override previous formats)
        self.setCurrentBlockState(0) # Default to normal state for this block
        
        startIndex = 0
        if self.previousBlockState() == 1: # Continuing '''
            startIndex = self.triSingleEndExpression.indexIn(text)
            if startIndex == -1: # Still in ''' string
                self.setCurrentBlockState(1)
                self.setFormat(0, len(text), self.triSingleQuoteFormat)
            else: # ''' string ends in this block
                length = startIndex + self.triSingleEndExpression.matchedLength()
                self.setFormat(0, length, self.triSingleQuoteFormat)
                # Check for more multiline strings after this one in the same block
                self.process_remaining_text_for_multiline(text, length)
        elif self.previousBlockState() == 2: # Continuing """
            startIndex = self.triDoubleEndExpression.indexIn(text)
            if startIndex == -1: # Still in """ string
                self.setCurrentBlockState(2)
                self.setFormat(0, len(text), self.triDoubleQuoteFormat)
            else: # """ string ends in this block
                length = startIndex + self.triDoubleEndExpression.matchedLength()
                self.setFormat(0, length, self.triDoubleQuoteFormat)
                self.process_remaining_text_for_multiline(text, length)
        else: # Not in a multi-line string from previous block, check for new starts
            self.process_remaining_text_for_multiline(text, 0)

    def process_remaining_text_for_multiline(self, text, offset):
        # This function is called to check for new multiline strings
        # after a multiline string has ended, or from the start of a block.
        
        startIndex_single = self.triSingleStartExpression.indexIn(text, offset)
        startIndex_double = self.triDoubleStartExpression.indexIn(text, offset)

        start_expression_used = None
        end_expression_to_use = None
        format_to_use = None
        state_to_set_if_unterminated = 0
        first_start_index = -1

        # Determine which multiline quote starts first (if any)
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
            # A multiline string starts in the remaining text
            match_len_start = start_expression_used.matchedLength()
            endIndex = end_expression_to_use.indexIn(text, first_start_index + match_len_start)

            if endIndex == -1: # Multiline string does not end in this block
                self.setCurrentBlockState(state_to_set_if_unterminated)
                self.setFormat(first_start_index, len(text) - first_start_index, format_to_use)
            else: # Multiline string ends in this block
                match_len_end = end_expression_to_use.matchedLength()
                length = endIndex - first_start_index + match_len_end
                self.setFormat(first_start_index, length, format_to_use)
                # If it ends, current state is 0 unless another multiline starts *after* it
                self.setCurrentBlockState(0) 
                # Recursively check for more multiline strings after this one ends
                self.process_remaining_text_for_multiline(text, first_start_index + length)
        else:
             # No new multiline string started, ensure state is 0 if not already handled by a continuing block
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

        # VSCode-like C/C++ colors for dark theme
        keywordFormat = QTextCharFormat()
        keywordFormat.setForeground(QColor("#569CD6")) # VSCode C++ keyword blue
        keywordFormat.setFontWeight(QFont.Bold)
        keywords = [
            "\\bchar\\b", "\\bclass\\b", "\\bconst\\b", "\\bdouble\\b", "\\benum\\b",
            "\\bexplicit\\b", "\\bextern\\b", "\\bfloat\\b", "\\bfriend\\b", "\\binline\\b",
            "\\bint\\b", "\\blong\\b", "\\bnamespace\\b", "\\boperator\\b", "\\bprivate\\b",
            "\\bprotected\\b", "\\bpublic\\b", "\\bshort\\b", "\\bsignals\\b", "\\bsigned\\b", 
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
            "\\bdynamic_cast\\b", "\\breinterpret_cast\\b", "\\bconst_cast\\b", # Added casts
            "\\bthrow\\b", "\\btry\\b", "\\busing\\b",
            # Arduino specific (often macros or typedefs but common)
            "\\bHIGH\\b", "\\bLOW\\b", "\\bINPUT\\b", "\\bOUTPUT\\b", "\\bINPUT_PULLUP\\b",
            "\\btrue\\b", "\\bfalse\\b", "\\bboolean\\b", "\\bbyte\\b", "\\bword\\b",
            "\\bString\\b",
            # Common types
            "\\buint8_t\\b", "\\bint8_t\\b", "\\buint16_t\\b", "\\bint16_t\\b", 
            "\\buint32_t\\b", "\\bint32_t\\b", "\\buint64_t\\b", "\\bint64_t\\b",
            "\\bsize_t\\b"
        ]
        for word in keywords:
            self.highlightingRules.append(HighlightingRule(word, keywordFormat))

        # Preprocessor directives
        preprocessorFormat = QTextCharFormat()
        preprocessorFormat.setForeground(QColor("#C586C0")) # VSCode C++ macro purple (VSCode often uses #9B9B9B for includes)
                                                        # Let's use a more distinct color: #608B4E (VSCode preproc green-ish)
        preprocessorFormat.setForeground(QColor("#608B4E")) 
        self.highlightingRules.append(HighlightingRule("^\\s*#.*", preprocessorFormat)) 

        # Single-line comments
        singleLineCommentFormat = QTextCharFormat()
        singleLineCommentFormat.setForeground(QColor("#6A9955")) # Green, same as Python
        singleLineCommentFormat.setFontItalic(True)
        self.highlightingRules.append(HighlightingRule("//[^\n]*", singleLineCommentFormat))

        # Multi-line comments (C-style)
        self.multiLineCommentFormat = QTextCharFormat()
        self.multiLineCommentFormat.setForeground(QColor("#6A9955")) # Green
        self.multiLineCommentFormat.setFontItalic(True)
        self.commentStartExpression = QRegExp("/\\*")
        self.commentEndExpression = QRegExp("\\*/")

        # Strings
        stringFormat = QTextCharFormat()
        stringFormat.setForeground(QColor("#CE9178")) # Orangey-brown, same as Python
        self.highlightingRules.append(HighlightingRule("\"(\\\\.|[^\"])*\"", stringFormat)) # Double quotes
        # Character literals
        charFormat = QTextCharFormat()
        charFormat.setForeground(QColor("#D16969")) # A slightly different reddish color for chars
        self.highlightingRules.append(HighlightingRule("'(\\\\.|[^'])'", charFormat))  # Single quotes for single chars

        # Numbers
        numberFormat = QTextCharFormat()
        numberFormat.setForeground(QColor("#B5CEA8")) # Light green, same as Python
        self.highlightingRules.append(HighlightingRule("\\b[0-9]+[ULulFf]?\\b", numberFormat)) # Integers, long, float suffixes
        self.highlightingRules.append(HighlightingRule("\\b0[xX][0-9a-fA-F]+[ULul]?\\b", numberFormat)) # Hex
        self.highlightingRules.append(HighlightingRule("\\b[0-9]*\\.[0-9]+([eE][-+]?[0-9]+)?[fF]?\\b", numberFormat)) # Floating point

        # Function names (general C/C++: word followed by parenthesis)
        functionFormat = QTextCharFormat()
        functionFormat.setForeground(QColor("#DCDCAA")) # Light yellow, same as Python defs
        self.highlightingRules.append(HighlightingRule("\\b[A-Za-z_][A-Za-z0-9_]*(?=\\s*\\()", functionFormat))
        
        # Arduino common functions (re-apply format for emphasis, could be different color)
        arduinoSpecificFunctionFormat = QTextCharFormat()
        arduinoSpecificFunctionFormat.setForeground(QColor("#4EC9B0")) # Teal, like Python builtins
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

        # Handle C-style multi-line comments
        self.setCurrentBlockState(0) # Default state (outside multi-line comment)

        startIndex = 0
        if self.previousBlockState() != 1: # If not already in a comment from previous block
            startIndex = self.commentStartExpression.indexIn(text)
        
        # This loop handles multiple /* ... */ blocks on the same line,
        # or a block that starts on this line and continues.
        while startIndex >= 0:
            endIndex = self.commentEndExpression.indexIn(text, startIndex)
            commentLength = 0
            if endIndex == -1: # Comment continues to next block
                self.setCurrentBlockState(1)
                commentLength = len(text) - startIndex
            else: # Comment ends in this block
                commentLength = endIndex - startIndex + self.commentEndExpression.matchedLength()
                # If it ends, current state becomes 0 again, unless another comment starts
                # This will be handled by the next iteration of the while loop if applicable
            
            self.setFormat(startIndex, commentLength, self.multiLineCommentFormat)
            # Search for the next comment start *after* the current one ends
            startIndex = self.commentStartExpression.indexIn(text, startIndex + commentLength)