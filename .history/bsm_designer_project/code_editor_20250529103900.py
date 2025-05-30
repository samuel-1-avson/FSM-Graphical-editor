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

        fm = QFontMetrics(self.font())
        self.setTabStopDistance(fm.horizontalAdvance(' ') * 4)
        self.setLineWrapMode(QPlainTextEdit.NoWrap)

        self.current_highlighter = None

        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)
        self.cursorPositionChanged.connect(self.highlightCurrentLine)
        self.cursorPositionChanged.connect(self.lineNumberArea.update) # Ensure line number area also updates cursor highlight

        self.updateLineNumberAreaWidth(0)
        self.highlightCurrentLine()
        self.set_language("Python") # Default language


    def _is_dark_theme_active(self) -> bool:
        # Check the actual background color of this widget instance
        # This is more reliable if stylesheets are applied specifically by objectName
        editor_bg_color = self.palette().color(QPalette.Base)
        # Compare with the specific dark background color defined in config
        return editor_bg_color == COLOR_EDITOR_DARK_BACKGROUND

    def lineNumberAreaWidth(self):
        digits = 1
        max_val = max(1, self.blockCount())
        while max_val >= 10:
            max_val //= 10
            digits += 1

        fm = self.fontMetrics()
        # Handle case where fontMetrics might not be fully initialized (e.g., headless tests)
        if fm.height() == 0: 
            # Provide a reasonable default if font metrics are not ready
            # This helps prevent division by zero or extremely small sizes
            return 35 

        padding = fm.horizontalAdvance(' ') * 2 # Use fm for padding too
        space = padding + fm.horizontalAdvance('9') * digits
        return space

    def updateLineNumberAreaWidth(self, _=None): # Parameter can be ignored
        self.setViewportMargins(self.lineNumberAreaWidth(), 0, 0, 0)

    def updateLineNumberArea(self, rect, dy):
        if dy:
            self.lineNumberArea.scroll(0, dy)
        else:
            # Ensure update covers the full width of the line number area
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
        # Ensure contentOffset() and blockBoundingGeometry/Rect are valid
        if not block.isValid() or self.document() is None: return

        content_offset_y = self.contentOffset().y()
        top = self.blockBoundingGeometry(block).translated(0, content_offset_y).top()
        bottom = top + self.blockBoundingRect(block).height()
        
        current_line_bg_color_ln = COLOR_EDITOR_DARK_CURRENT_LINE_BG_LN_AREA if is_dark else QColor(COLOR_ACCENT_PRIMARY_LIGHT)
        current_line_num_color_ln = COLOR_EDITOR_DARK_CURRENT_LINE_FG_LN_AREA if is_dark else QColor(COLOR_ACCENT_PRIMARY)
        normal_line_num_color_ln = COLOR_EDITOR_DARK_LINE_NUM_FG if is_dark else QColor(COLOR_TEXT_PRIMARY).darker(130)

        fm = self.fontMetrics()
        if fm.height() == 0: return # Guard against invalid font metrics

        right_padding = fm.horizontalAdvance(' ') // 2 # Small padding from the right edge

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(blockNumber + 1)
                
                temp_font = self.font() # Use a copy of the editor's font
                is_current_block = self.textCursor().blockNumber() == blockNumber

                if is_current_block:
                    painter.fillRect(QRect(0, int(top), self.lineNumberArea.width(), int(fm.height())), current_line_bg_color_ln)
                    painter.setPen(current_line_num_color_ln)
                    temp_font.setBold(True)
                else:
                    painter.setPen(normal_line_num_color_ln)
                    temp_font.setBold(False) # Ensure bold is reset for non-current lines
                painter.setFont(temp_font)

                painter.drawText(0, int(top), self.lineNumberArea.width() - right_padding,
                                 int(fm.height()),
                                 Qt.AlignRight | Qt.AlignVCenter, number)

            block = block.next()
            if not block.isValid(): break # Ensure block is valid before using it
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            blockNumber += 1

    def highlightCurrentLine(self):
        extraSelections = []
        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            is_dark = self._is_dark_theme_active()

            # Use the specific dark theme color for current line in editor, or a lighter version of accent for light theme
            line_color_editor = COLOR_EDITOR_DARK_CURRENT_LINE_BG_EDITOR if is_dark else QColor(COLOR_ACCENT_PRIMARY_LIGHT).lighter(125)

            selection.format.setBackground(line_color_editor)
            selection.format.setProperty(QTextFormat.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection() # Important to prevent selection from interfering
            extraSelections.append(selection)
        self.setExtraSelections(extraSelections)

    def set_language(self, language: str):
        doc = self.document()
        if not doc:
            return

        # Detach the old highlighter
        if self.current_highlighter:
            self.current_highlighter.setDocument(None) # Detach from document
            # self.current_highlighter.deleteLater() # Schedule for deletion if it's a QObject, not standard for QSyntaxHighlighter
        
        self.current_highlighter = None # Reset

        # Set the new highlighter
        if language == "Python":
            self.current_highlighter = PythonHighlighter(doc)
        elif language in ["C/C++ (Arduino)", "C/C++ (Generic)"]:
            self.current_highlighter = CSyntaxHighlighter(doc)
        # Add more languages here as needed
        # elif language == "Text" or language is None:
            # No highlighter needed, current_highlighter remains None

        # Rehighlight or clear formatting if no highlighter
        if self.current_highlighter:
            self.current_highlighter.rehighlight() 
        else:
            # When no highlighter is active, clear previously applied character formats.
            cursor = QTextCursor(doc)
            cursor.beginEditBlock() 
            block = doc.firstBlock()
            while block.isValid():
                cursor.setPosition(block.position())
                cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
                
                empty_format = QTextCharFormat() # Create a default format
                # Set a default text color based on theme. This ensures text visibility
                # if a previous highlighter set a color that contrasts poorly with the new (default) background.
                palette_base_color = self.palette().color(QPalette.Base)
                default_text_color = QColor(Qt.black) # Fallback
                if palette_base_color == COLOR_EDITOR_DARK_BACKGROUND: # Dark theme
                    default_text_color = QColor("#CFD8DC") # Light grey for dark background
                else: # Light theme
                    default_text_color = QColor(COLOR_TEXT_PRIMARY) # Standard text color
                
                empty_format.setForeground(default_text_color)
                # Potentially reset font weight/style if highlighters change them
                # empty_format.setFontWeight(QFont.Normal)
                # empty_format.setFontItalic(False)
                # empty_format.setFontUnderline(False)
                
                cursor.setCharFormat(empty_format)
                block = block.next()
            cursor.endEditBlock()
            
            # After clearing formats, explicitly tell the document layout it changed.
            doc.documentLayout().documentSizeChanged(doc.size())
            self.viewport().update() # Force repaint of the viewport

        # Refresh UI elements that depend on highlighting or content
        self.highlightCurrentLine() # Re-apply current line highlight
        self.lineNumberArea.update() # Refresh line number area


class PythonHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None): 
        super().__init__(parent)

        self.highlightingRules = []

        keywordFormat = QTextCharFormat()
        keywordFormat.setForeground(QColor("#0000FF")) # Blue (VSCode Python keyword color)
        # Note: 'and', 'or', 'is', 'in' are handled by keywords, not operators, for typical Python highlighting.
        keywords = [
            "\\bFalse\\b", "\\bNone\\b", "\\bTrue\\b", "\\band\\b", "\\bas\\b", "\\bassert\\b", 
            "\\basync\\b", "\\bawait\\b", "\\bbreak\\b", "\\bclass\\b", "\\bcontinue\\b", 
            "\\bdef\\b", "\\bdel\\b", "\\belif\\b", "\\belse\\b", "\\bexcept\\b", "\\bfinally\\b", 
            "\\bfor\\b", "\\bfrom\\b", "\\bglobal\\b", "\\bif\\b", "\\bimport\\b", "\\bin\\b", 
            "\\bis\\b", "\\blambda\\b", "\\bnonlocal\\b", "\\bor\\b", "\\bpass\\b", "\\bnot\\b", # Added 'not' as keyword
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
            "\\bException\\b", "\\bTypeError\\b", "\\bValueError\\b", "\\bNameError\\b",
            "\\bKeyboardInterrupt\\b", "\\bSystemExit\\b", "\\bobject\\b", "\\bproperty\\b",
            "\\bstaticmethod\\b", "\\bclassmethod\\b", "\\bchr\\b", "\\bord\\b", "\\bhex\\b",
            "\\boct\\b", "\\bbin\\b", "\\bround\\b", "\\bpow\\b", "\\brepr\\b", "\\bascii\\b",
            "\\bcallable\\b", "\\bcompile\\b", "\\bdelattr\\b", "\\bdir\\b", "\\bdivmod\\b",
            "\\benumerate\\b", "\\beval\\b", "\\bexec\\b", "\\bfilter\\b", "\\bformat\\b",
            "\\bfrozenset\\b", "\\bgetattr\\b", "\\bglobals\\b", "\\bhash\\b", "\\bhelp\\b",
            "\\bid\\b", "\\binput\\b", "\\bissubclass\\b", "\\biter\\b", "\\blocals\\b",
            "\\bmap\\b", "\\bmemoryview\\b", "\\bnext\\b", "\\bopen\\b",
            "\\breversed\\b", "\\bsetattr\\b", "\\bslice\\b", "\\bvars\\b", "\\bzip\\b",
            "\\b__import__\\b"
        ]
        for word in builtins:
            self.highlightingRules.append(HighlightingRule(word, builtinFormat))

        commentFormat = QTextCharFormat()
        commentFormat.setForeground(QColor("#6A9955")) # VSCode Python comment color (green)
        self.highlightingRules.append(HighlightingRule("#[^\n]*", commentFormat))

        stringFormat = QTextCharFormat()
        stringFormat.setForeground(QColor("#CE9178")) # VSCode Python string color (orangey-brown)
        # Rules for single-quoted and double-quoted strings (non-multiline)
        self.highlightingRules.append(HighlightingRule("'[^'\\\\]*(\\.[^'\\\\]*)*'", stringFormat)) # Handles escaped quotes
        self.highlightingRules.append(HighlightingRule("\"[^\"\\\\]*(\\.[^\"\\\\]*)*\"", stringFormat)) # Handles escaped quotes

        numberFormat = QTextCharFormat()
        numberFormat.setForeground(QColor("#B5CEA8")) # VSCode Python number color (light green)
        self.highlightingRules.append(HighlightingRule("\\b[0-9]+\\.?[0-9]*([eE][-+]?[0-9]+)?\\b", numberFormat))
        self.highlightingRules.append(HighlightingRule("\\b0[xX][0-9a-fA-F]+\\b", numberFormat)) # Hex
        self.highlightingRules.append(HighlightingRule("\\b0[oO][0-7]+\\b", numberFormat))    # Octal
        self.highlightingRules.append(HighlightingRule("\\b0[bB][01]+\\b", numberFormat))    # Binary

        definitionFormat = QTextCharFormat()
        definitionFormat.setForeground(QColor("#DCDCAA")) # VSCode Python function definition name (light yellow)
        definitionFormat.setFontWeight(QFont.Normal) 
        self.highlightingRules.append(HighlightingRule("\\bdef\\s+([A-Za-z_][A-Za-z0-9_]*)", definitionFormat, 1, True))
        self.highlightingRules.append(HighlightingRule("\\bclass\\s+([A-Za-z_][A-Za-z0-9_]*)", definitionFormat, 1, True))
        
        operatorFormat = QTextCharFormat()
        operatorFormat.setForeground(QColor("#D4D4D4")) # VSCode default text color for operators
        # Simplified operator regex: 'not', 'and', 'or', 'is', 'in' are keywords.
        operators_regex = (
            "\\+|\\-|\\*|/|%|==|!=|<|>|<=|>=|\\^|\\&|\\||~|<<|>>|//=|\\*\\*=" # Common operators
            "|\\+=|\\-=|\\*=|/=|%=|&=|\\|=|^=|//=|\\*\\*|@" # Augmented assignment and others
        )
        self.highlightingRules.append(HighlightingRule(operators_regex, operatorFormat))

        # Formats for multiline strings
        self.triSingleQuoteFormat = QTextCharFormat()
        self.triSingleQuoteFormat.setForeground(QColor("#CE9178")) # Same as regular strings
        self.triDoubleQuoteFormat = QTextCharFormat()
        self.triDoubleQuoteFormat.setForeground(QColor("#CE9178")) # Same as regular strings

        # Regular expressions for multiline string delimiters
        self.triSingleStartExpression = QRegExp("'''")
        self.triSingleEndExpression = QRegExp("'''")
        self.triDoubleStartExpression = QRegExp("\"\"\"")
        self.triDoubleEndExpression = QRegExp("\"\"\"")


    def highlightBlock(self, text):
        # Apply non-multiline rules first
        for rule in self.highlightingRules:
            expression = rule.pattern
            expression.setMinimal(rule.minimal) # Ensure minimal flag is set from rule
            
            offset = 0
            if rule.nth > 0: # Highlighting a specific capture group
                index = expression.indexIn(text, offset)
                while index >= 0:
                    capture_start = expression.pos(rule.nth) 
                    capture_text = expression.cap(rule.nth)
                    capture_length = len(capture_text)

                    if capture_start != -1 and capture_length > 0:
                        self.setFormat(capture_start, capture_length, rule.format)
                    
                    new_offset = index + expression.matchedLength()
                    if new_offset <= offset : # Prevent infinite loop on zero-length match or no advance
                        new_offset = offset + 1 
                    offset = new_offset
                    if offset >= len(text) or expression.matchedLength() == 0 : 
                        break 
                    index = expression.indexIn(text, offset)
            else: # Highlighting the whole match
                index = expression.indexIn(text, offset)
                while index >= 0:
                    length = expression.matchedLength()
                    if length > 0:
                        self.setFormat(index, length, rule.format)
                    
                    new_offset = index + length
                    if new_offset <= offset : # Prevent infinite loop
                        new_offset = offset + 1
                    offset = new_offset
                    if offset >= len(text) or length == 0: 
                        break
                    index = expression.indexIn(text, offset)
        
        # Multiline string handling
        # States: 0 (normal), 1 (in '''), 2 (in """)
        current_multiline_state = self.previousBlockState()
        startIndex = 0

        if current_multiline_state == 1: # Was in '''
            endIndex = self.triSingleEndExpression.indexIn(text, startIndex)
            if endIndex == -1: # Multiline still open
                self.setCurrentBlockState(1)
                self.setFormat(0, len(text), self.triSingleQuoteFormat)
            else: # Multiline ends in this block
                length = endIndex - startIndex + self.triSingleEndExpression.matchedLength()
                self.setFormat(startIndex, length, self.triSingleQuoteFormat)
                self.setCurrentBlockState(0) 
                # Potentially process rest of the line for other multiline starts
                self.process_remaining_text_for_multiline(text, startIndex + length)
        elif current_multiline_state == 2: # Was in """
            endIndex = self.triDoubleEndExpression.indexIn(text, startIndex)
            if endIndex == -1: # Multiline still open
                self.setCurrentBlockState(2)
                self.setFormat(0, len(text), self.triDoubleQuoteFormat)
            else: # Multiline ends in this block
                length = endIndex - startIndex + self.triDoubleEndExpression.matchedLength()
                self.setFormat(startIndex, length, self.triDoubleQuoteFormat)
                self.setCurrentBlockState(0)
                self.process_remaining_text_for_multiline(text, startIndex + length)
        else: # Not in a multiline string from previous block
            self.process_remaining_text_for_multiline(text, 0)

    def process_remaining_text_for_multiline(self, text, offset):
        # This function checks if a NEW multiline string starts in the text AFTER a previous one might have ended.
        if offset >= len(text): # No more text to process
             if self.currentBlockState() not in [1, 2]: # If not already set by an unclosed multiline
                self.setCurrentBlockState(0)
             return

        startIndex_single = self.triSingleStartExpression.indexIn(text, offset)
        startIndex_double = self.triDoubleStartExpression.indexIn(text, offset)

        # Determine which type of multiline string starts first, if any
        start_expression_instance = None
        start_index = -1
        block_state_to_set = 0
        format_to_apply = None
        end_expression_instance = None

        if startIndex_single != -1 and (startIndex_double == -1 or startIndex_single < startIndex_double):
            start_expression_instance = self.triSingleStartExpression
            start_index = startIndex_single
            block_state_to_set = 1
            format_to_apply = self.triSingleQuoteFormat
            end_expression_instance = self.triSingleEndExpression
        elif startIndex_double != -1:
            start_expression_instance = self.triDoubleStartExpression
            start_index = startIndex_double
            block_state_to_set = 2
            format_to_apply = self.triDoubleQuoteFormat
            end_expression_instance = self.triDoubleEndExpression
        
        if start_index != -1 and start_expression_instance and format_to_apply and end_expression_instance:
            # A multiline string starts here
            endIndex = end_expression_instance.indexIn(text, start_index + start_expression_instance.matchedLength())
            if endIndex == -1: # Does not end in this block
                self.setCurrentBlockState(block_state_to_set)
                self.setFormat(start_index, len(text) - start_index, format_to_apply)
            else: # Ends in this block
                length = endIndex - start_index + end_expression_instance.matchedLength()
                self.setFormat(start_index, length, format_to_apply)
                self.setCurrentBlockState(0) 
                # Recursively process any text remaining AFTER this multiline string
                self.process_remaining_text_for_multiline(text, start_index + length) 
        else: # No new multiline string starts in the remaining text
            if self.currentBlockState() not in [1,2]: # Ensure state is 0 if no multiline is active
                 self.setCurrentBlockState(0)


class HighlightingRule:
    def __init__(self, pattern_str, text_format, nth_capture_group=0, minimal=False):
        self.pattern = QRegExp(pattern_str)
        self.format = text_format
        self.nth = nth_capture_group # Which capture group to highlight (0 for whole match)
        self.minimal = minimal       # Whether to use minimal (non-greedy) matching
        if self.minimal:
            self.pattern.setMinimal(True)

class CSyntaxHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.highlightingRules = []

        keywordFormat = QTextCharFormat()
        keywordFormat.setForeground(QColor("#569CD6")) # VSCode C++ keyword color (blueish)
        # Common C/C++ keywords including Arduino specifics
        keywords = [
            "\\bchar\\b", "\\bclass\\b", "\\bconst\\b", "\\bdouble\\b", "\\benum\\b",
            "\\bexplicit\\b", "\\bextern\\b", "\\bfloat\\b", "\\bfriend\\b", "\\binline\\b",
            "\\bint\\b", "\\blong\\b", "\\bnamespace\\b", "\\boperator\\b", "\\bprivate\\b",
            "\\bprotected\\b", "\\bpublic\\b", "\\bshort\\b", "\\bsignals\\b", "\\bsigned\\b", # Qt specific
            "\\bslots\\b", "\\bstatic\\b", "\\bstruct\\b", "\\btemplate\\b", "\\bthis\\b", # Qt specific
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
            "\\bdynamic_cast\\b", "\\breinterpret_cast\\b", "\\bconst_cast\\b",
            "\\bthrow\\b", "\\btry\\b", "\\busing\\b",
            # Arduino specific
            "\\bHIGH\\b", "\\bLOW\\b", "\\bINPUT\\b", "\\bOUTPUT\\b", "\\bINPUT_PULLUP\\b",
            "\\btrue\\b", "\\bfalse\\b", "\\bboolean\\b", "\\bbyte\\b", "\\bword\\b",
            "\\bString\\b", "\\bKeyboard\\b", "\\bMouse\\b", "\\bSerial\\b", "\\bStream\\b",
            "\\bServer\\b", "\\bClient\\b", "\\bFile\\b", "\\bLiquidCrystal\\b",
            "\\bEthernet\\b", "\\bSD\\b", "\\bSPI\\b", "\\bWire\\b", # Common Arduino libraries
            "\\bpinMode\\b", "\\bdigitalWrite\\b", "\\bdigitalRead\\b",
            "\\banalogRead\\b", "\\banalogWrite\\b", "\\bdelay\\b", "\\bmillis\\b", "\\bmicros\\b",
            "\\bsetup\\b", "\\bloop\\b"
        ]
        for word in keywords:
            self.highlightingRules.append(HighlightingRule(word, keywordFormat))

        preprocessorFormat = QTextCharFormat()
        preprocessorFormat.setForeground(QColor("#C586C0")) # VSCode C++ preprocessor (purple)
        self.highlightingRules.append(HighlightingRule("^\\s*#.*", preprocessorFormat)) # Match lines starting with #

        singleLineCommentFormat = QTextCharFormat()
        singleLineCommentFormat.setForeground(QColor("#6A9955")) # VSCode C++ comment (green)
        self.highlightingRules.append(HighlightingRule("//[^\n]*", singleLineCommentFormat))

        self.multiLineCommentFormat = QTextCharFormat()
        self.multiLineCommentFormat.setForeground(QColor("#6A9955")) # Green for comments
        self.commentStartExpression = QRegExp("/\\*")
        self.commentEndExpression = QRegExp("\\*/")

        stringFormat = QTextCharFormat()
        stringFormat.setForeground(QColor("#CE9178")) # VSCode C++ string (orangey-brown)
        self.highlightingRules.append(HighlightingRule("\"(\\\\.|[^\"])*\"", stringFormat)) # Double-quoted strings
        self.highlightingRules.append(HighlightingRule("'(\\\\.|[^'])*'", stringFormat))   # Single-quoted char/string

        numberFormat = QTextCharFormat()
        numberFormat.setForeground(QColor("#B5CEA8")) # VSCode C++ number (light green)
        # Integer, float, hex, octal, binary
        self.highlightingRules.append(HighlightingRule("\\b[0-9]+[ULul]*\\b", numberFormat)) # Decimal int
        self.highlightingRules.append(HighlightingRule("\\b0[xX][0-9a-fA-F]+[ULul]*\\b", numberFormat)) # Hex int
        self.highlightingRules.append(HighlightingRule("\\b0[0-7]+[ULul]*\\b", numberFormat))       # Octal int
        self.highlightingRules.append(HighlightingRule("\\b0[bB][01]+[ULul]*\\b", numberFormat))      # Binary int
        self.highlightingRules.append(HighlightingRule("\\b[0-9]*\\.[0-9]+([eE][-+]?[0-9]+)?[fFlL]?\\b", numberFormat)) # Float
        self.highlightingRules.append(HighlightingRule("\\b[0-9]+\\.([eE][-+]?[0-9]+)?[fFlL]?\\b", numberFormat)) # Float (e.g. 1.e2)
        self.highlightingRules.append(HighlightingRule("\\b[0-9]+[eE][-+]?[0-9]+[fFlL]?\\b", numberFormat)) # Float (e.g. 1e2)


        functionFormat = QTextCharFormat()
        functionFormat.setForeground(QColor("#DCDCAA")) # VSCode C++ function name (light yellow)
        # General function call pattern
        self.highlightingRules.append(HighlightingRule("\\b[A-Za-z_][A-Za-z0-9_]*(?=\\s*\\()", functionFormat)) 
        # Arduino specific functions were added to keywords, this will catch general calls


    def highlightBlock(self, text):
        # Apply single-line rules
        for rule in self.highlightingRules:
            expression = rule.pattern 
            expression.setMinimal(rule.minimal) 
            
            offset = 0
            if rule.nth > 0: # Specific capture group
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
            else: # Whole match
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

        # Multi-line comment handling
        self.setCurrentBlockState(0) # Default state is 0 (no multiline comment)

        startIndex = 0
        if self.previousBlockState() != 1: # If not already in a multiline comment
            startIndex = self.commentStartExpression.indexIn(text)

        while startIndex >= 0:
            endIndex = self.commentEndExpression.indexIn(text, startIndex)
            commentLength = 0
            if endIndex == -1: # Comment doesn't end in this block
                self.setCurrentBlockState(1) # Mark block as inside a multiline comment
                commentLength = len(text) - startIndex
            else: # Comment ends in this block
                commentLength = endIndex - startIndex + self.commentEndExpression.matchedLength()
            
            self.setFormat(startIndex, commentLength, self.multiLineCommentFormat)
            # Check for more comments in the same block after this one ends
            startIndex = self.commentStartExpression.indexIn(text, startIndex + commentLength)