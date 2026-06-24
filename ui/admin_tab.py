import csv
import os
import shutil
import uuid
from datetime import date

from PyQt6.QtWidgets import QFileDialog, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSpinBox, QTabWidget, QComboBox, QTableWidget, QTextEdit, QVBoxLayout, QWidget

from config import COVERS_DIR
from utils import error, message, fill_table


class AdminTab(QWidget):
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.cover_source = None
        self.report_rows = []
        self.report_headers = []
        main = QVBoxLayout(self)

        self.tabs = QTabWidget()
        main.addWidget(self.tabs)
        self.tabs.addTab(self.books_page(), 'Книги')
        self.tabs.addTab(self.reports_page(), 'Отчеты')

    def books_page(self):
        page = QWidget()
        main = QVBoxLayout(page)
        grid = QGridLayout()
        self.title = QLineEdit()
        self.authors = QLineEdit()
        self.isbn = QLineEdit()
        self.publisher = QLineEdit()
        self.year = QSpinBox(); self.year.setRange(0, 2100); self.year.setValue(date.today().year)
        self.copies = QSpinBox(); self.copies.setRange(1, 10000); self.copies.setValue(1)
        self.description = QTextEdit()
        cover_btn = QPushButton('Выбрать обложку')
        cover_btn.clicked.connect(self.choose_cover)
        add_btn = QPushButton('Добавить книгу')
        add_btn.clicked.connect(self.add_book)
        fields = [
            ('Название', self.title), ('Авторы через запятую', self.authors), ('ISBN', self.isbn),
            ('Издатель', self.publisher), ('Год', self.year), ('Кол-во', self.copies), ('Описание', self.description)
        ]
        for i, (label, widget) in enumerate(fields):
            grid.addWidget(QLabel(label), i, 0)
            grid.addWidget(widget, i, 1)
        grid.addWidget(cover_btn, len(fields), 0)
        grid.addWidget(add_btn, len(fields), 1)
        main.addLayout(grid)

        row = QHBoxLayout()
        self.delete_id = QLineEdit()
        self.delete_id.setPlaceholderText('ID книги для удаления')
        del_btn = QPushButton('Удалить книгу')
        del_btn.clicked.connect(self.delete_book)
        refresh_btn = QPushButton('Обновить список')
        refresh_btn.clicked.connect(self.load_books)
        row.addWidget(self.delete_id)
        row.addWidget(del_btn)
        row.addWidget(refresh_btn)
        main.addLayout(row)

        self.books_table = QTableWidget()
        main.addWidget(self.books_table)
        self.load_books()
        return page

    def reports_page(self):
        page = QWidget()
        main = QVBoxLayout(page)
        row = QHBoxLayout()
        self.report_type = QComboBox()
        self.report_type.addItems(['Должники', 'Популярные книги за месяц', 'Активность библиотекарей', 'Книги не выдавались более года'])
        self.report_year = QSpinBox(); self.report_year.setRange(2000, 2100); self.report_year.setValue(date.today().year)
        self.report_month = QSpinBox(); self.report_month.setRange(1, 12); self.report_month.setValue(date.today().month)
        build_btn = QPushButton('Сформировать')
        save_btn = QPushButton('Сохранить CSV')
        build_btn.clicked.connect(self.build_report)
        save_btn.clicked.connect(self.save_report)
        row.addWidget(self.report_type)
        row.addWidget(QLabel('Год'))
        row.addWidget(self.report_year)
        row.addWidget(QLabel('Месяц'))
        row.addWidget(self.report_month)
        row.addWidget(build_btn)
        row.addWidget(save_btn)
        main.addLayout(row)
        self.report_table = QTableWidget()
        main.addWidget(self.report_table)
        return page

    def choose_cover(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Выберите обложку', '', 'Images (*.png *.jpg *.jpeg *.webp)')
        if path:
            self.cover_source = path
            message(self, 'Обложка', 'Обложка выбрана')

    def save_cover(self):
        if not self.cover_source:
            return None
        ext = os.path.splitext(self.cover_source)[1]
        target = os.path.join(COVERS_DIR, f'{uuid.uuid4().hex}{ext}')
        shutil.copy2(self.cover_source, target)
        return target

    def add_book(self):
        if not self.title.text().strip():
            error(self, 'Введите название книги')
            return
        ok, text = self.db.add_book(
            self.title.text(), self.authors.text(), self.isbn.text(), self.publisher.text(),
            self.year.value(), self.description.toPlainText(), self.copies.value(), self.save_cover()
        )
        (message if ok else error)(self, 'Книга', text) if ok else error(self, text)
        if ok:
            self.title.clear(); self.authors.clear(); self.isbn.clear(); self.publisher.clear(); self.description.clear(); self.cover_source = None
            self.load_books()

    def delete_book(self):
        if not self.delete_id.text().strip().isdigit():
            error(self, 'Введите ID книги')
            return
        ok, text = self.db.delete_book(int(self.delete_id.text()))
        (message if ok else error)(self, 'Удаление', text) if ok else error(self, text)
        self.load_books()

    def load_books(self):
        self.fill_table(self.books_table, ['ID', 'Название', 'Авторы', 'ISBN', 'Издатель', 'Год', 'Описание', 'Всего', 'Доступно', 'Обложка'], self.db.get_books(''))

    def build_report(self):
        kind = self.report_type.currentText()
        if kind == 'Должники':
            headers = ['Логин', 'Читатель', 'Книга', 'Выдана', 'Дедлайн', 'Дней просрочки', 'Штраф']
            rows = self.db.get_debtors_report()
        elif kind == 'Популярные книги за месяц':
            headers = ['Книга', 'Кол-во выдач']
            rows = self.db.get_most_popular_book_report(self.report_year.value(), self.report_month.value())
        elif kind == 'Активность библиотекарей':
            headers = ['Логин', 'Библиотекарь', 'Выдач', 'Приемок']
            rows = self.db.get_librarian_activity_report(self.report_year.value(), self.report_month.value())
        else:
            headers = ['ID', 'Книга', 'Последняя выдача']
            rows = self.db.get_books_not_issued_year_report()
        self.report_headers = headers
        self.report_rows = rows
        self.fill_table(self.report_table, headers, rows)

    def save_report(self):
        if not self.report_rows:
            error(self, 'Сначала сформируйте отчет')
            return
        path, _ = QFileDialog.getSaveFileName(self, 'Сохранить отчет', 'report.csv', 'CSV (*.csv)')
        if not path:
            return
        with open(path, 'w', encoding='utf-8-sig', newline='') as file:
            writer = csv.writer(file, delimiter=';')
            writer.writerow(self.report_headers)
            for row in self.report_rows:
                writer.writerow(list(row.values()))
        message(self, 'Отчет', 'Отчет сохранен')

    def fill_table(self, table, headers, rows):
        fill_table(table, headers, rows)
