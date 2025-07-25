from PyQt5.QtGui import (QTextCharFormat, QColor, QSyntaxHighlighter)
from PyQt5.QtCore import QRegularExpression

class MikroTikHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.highlighting_rules = []
        self.setup_rules()
    
    def setup_rules(self):
        command_format = QTextCharFormat()
        command_format.setForeground(QColor(0, 0, 255))
        commands = [
            r':global', r':set', r':if', r':else', r':foreach', 
            r':do', r':while', r':return', r':error'
        ]
        for cmd in commands:
            pattern = QRegularExpression(fr'\b{cmd}\b')
            self.highlighting_rules.append((pattern, command_format))
        
        var_format = QTextCharFormat()
        var_format.setForeground(QColor(139, 0, 139))
        pattern = QRegularExpression(r'\$\w+')
        self.highlighting_rules.append((pattern, var_format))
        
        string_format = QTextCharFormat()
        string_format.setForeground(QColor(0, 128, 0))
        pattern = QRegularExpression(r'"[^"]*"')
        self.highlighting_rules.append((pattern, string_format))
        
        number_format = QTextCharFormat()
        number_format.setForeground(QColor(255, 0, 0))
        pattern = QRegularExpression(r'\b\d+\b')
        self.highlighting_rules.append((pattern, number_format))
        
        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor(128, 128, 128))
        pattern = QRegularExpression(r'#[^\n]*')
        self.highlighting_rules.append((pattern, comment_format))

    def highlightBlock(self, text):
        for pattern, fmt in self.highlighting_rules:
            match_iterator = pattern.globalMatch(text)
            while match_iterator.hasNext():
                match = match_iterator.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), fmt)