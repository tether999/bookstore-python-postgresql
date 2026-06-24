import os

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QVBoxLayout, QWidget


class CatalogTab(QWidget):
    def __init__(self, db, user=None):
        super().__init__()
        self.db = db
        self.user = user
        main = QVBoxLayout(self)

        search_row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText('Поиск по названию, автору, ISBN или издателю')
        find_btn = QPushButton('Найти')
        reset_btn = QPushButton('Сбросить')
        find_btn.clicked.connect(self.load_books)
        reset_btn.clicked.connect(self.reset)
        self.search_input.returnPressed.connect(self.load_books)
        search_row.addWidget(self.search_input)
        search_row.addWidget(find_btn)
        search_row.addWidget(reset_btn)
        main.addLayout(search_row)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.container = QWidget()
        self.cards = QVBoxLayout(self.container)
        self.cards.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(self.container)
        main.addWidget(self.scroll)
        self.load_books()

    def reset(self):
        self.search_input.clear()
        self.load_books()

    def clear_cards(self):
        while self.cards.count():
            item = self.cards.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def load_books(self):
        self.clear_cards()
        books = self.db.get_books(self.search_input.text().strip())
        if not books:
            self.cards.addWidget(QLabel('Книги не найдены'))
            return
        for book in books:
            self.cards.addWidget(self.book_card(book))

    def book_card(self, book):
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.Box)
        row = QHBoxLayout(frame)

        cover = QLabel()
        cover.setFixedSize(100, 130)
        cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
        path = book.get('cover_path')
        if path and os.path.exists(path):
            pix = QPixmap(path)
            cover.setPixmap(pix.scaled(100, 130, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            cover.setText('Нет\nобложки')
        row.addWidget(cover)

        text = QVBoxLayout()
        text.addWidget(QLabel(f"ID {book['id']} — {book['title']}"))
        text.addWidget(QLabel(f"Автор: {book.get('authors') or 'не указан'}"))
        text.addWidget(QLabel(f"Издатель: {book.get('publisher_name') or 'не указан'} | Год: {book.get('publish_year') or ''}"))
        text.addWidget(QLabel(f"ISBN: {book.get('isbn') or ''}"))
        text.addWidget(QLabel(f"Доступно: {book['available_copies']} из {book['total_copies']}"))
        desc = QLabel(book.get('description') or '')
        desc.setWordWrap(True)
        text.addWidget(desc)
        row.addLayout(text)
        return frame
