from PyQt6.QtWidgets import QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTableWidget, QVBoxLayout, QWidget

from utils import error, message, fill_table


class LibrarianTab(QWidget):
    def __init__(self, db, user):
        super().__init__()
        self.db = db
        self.user = user
        main = QVBoxLayout(self)

        issue_box = QFrame()
        issue_box.setFrameShape(QFrame.Shape.Box)
        grid = QGridLayout(issue_box)
        self.user_login = QLineEdit()
        self.book_search = QLineEdit()
        self.book_search.setPlaceholderText('Название, автор или ISBN')
        self.book_combo = QComboBox()
        self.book_combo.setMinimumWidth(420)
        self.condition = QComboBox()

        for condition in self.db.get_loan_conditions():
            self.condition.addItem(f"{condition['name']} ({condition['days_allowed']} дн., {condition['fine_per_day']} руб/день)", condition['id'])

        find_book_btn = QPushButton('Найти книгу')
        reset_book_btn = QPushButton('Сбросить')
        issue_btn = QPushButton('Оформить выдачу')
        find_book_btn.clicked.connect(self.load_books_for_issue)
        reset_book_btn.clicked.connect(self.reset_book_search)
        self.book_search.returnPressed.connect(self.load_books_for_issue)
        issue_btn.clicked.connect(self.issue_book)

        book_search_row = QHBoxLayout()
        book_search_row.addWidget(self.book_search)
        book_search_row.addWidget(find_book_btn)
        book_search_row.addWidget(reset_book_btn)

        grid.addWidget(QLabel('Логин клиента'), 0, 0)
        grid.addWidget(self.user_login, 0, 1)
        grid.addWidget(QLabel('Поиск книги'), 1, 0)
        grid.addLayout(book_search_row, 1, 1)
        grid.addWidget(QLabel('Выберите книгу'), 2, 0)
        grid.addWidget(self.book_combo, 2, 1)
        grid.addWidget(QLabel('Условие'), 3, 0)
        grid.addWidget(self.condition, 3, 1)
        grid.addWidget(issue_btn, 4, 0, 1, 2)
        main.addWidget(issue_box)
        self.load_books_for_issue()

        main.addWidget(QLabel('Запросы возврата'))
        self.requests_table = QTableWidget()
        main.addWidget(self.requests_table)
        row = QHBoxLayout()
        self.request_id = QLineEdit()
        self.request_id.setPlaceholderText('ID запроса')
        accept_btn = QPushButton('Принять возврат')
        reject_btn = QPushButton('Отклонить возврат')
        refresh_btn = QPushButton('Обновить')
        accept_btn.clicked.connect(self.accept_return)
        reject_btn.clicked.connect(self.reject_return)
        refresh_btn.clicked.connect(self.refresh)
        row.addWidget(self.request_id)
        row.addWidget(accept_btn)
        row.addWidget(reject_btn)
        row.addWidget(refresh_btn)
        main.addLayout(row)
        self.refresh()

    def load_books_for_issue(self):
        self.book_combo.clear()
        books = self.db.get_available_books_for_issue(self.book_search.text().strip())
        if not books:
            self.book_combo.addItem('Нет доступных книг', None)
            return
        for book in books:
            authors = book.get('authors') or 'автор не указан'
            isbn = book.get('isbn') or 'без ISBN'
            title = f"{book['title']} — {authors} | {isbn} | доступно: {book['available_copies']}"
            self.book_combo.addItem(title, book['id'])

    def reset_book_search(self):
        self.book_search.clear()
        self.load_books_for_issue()

    def issue_book(self):
        book_id = self.book_combo.currentData()
        if not self.user_login.text().strip():
            error(self, 'Введите логин клиента')
            return
        if not book_id:
            error(self, 'Выберите доступную книгу из списка')
            return
        ok, text = self.db.issue_book(self.user_login.text(), int(book_id), self.user['id'], self.condition.currentData())
        (message if ok else error)(self, 'Выдача', text) if ok else error(self, text)
        if ok:
            self.load_books_for_issue()
        self.refresh()

    def refresh(self):
        self.db.update_overdue_loans_and_fines()
        rows = self.db.get_pending_return_requests()
        self.fill_table(
            self.requests_table,
            ['ID запроса', 'Запрошено', 'ID выдачи', 'Логин', 'Читатель', 'Книга', 'Выдана', 'Дедлайн', 'Дней просрочки', 'Штраф/день', 'Сумма штрафа', 'Информация о штрафе', 'Статус'],
            rows
        )

    def accept_return(self):
        if not self.request_id.text().strip().isdigit():
            error(self, 'Введите ID запроса')
            return
        ok, text = self.db.accept_return_request(int(self.request_id.text()), self.user['id'])
        (message if ok else error)(self, 'Приемка', text) if ok else error(self, text)
        self.refresh()

    def reject_return(self):
        if not self.request_id.text().strip().isdigit():
            error(self, 'Введите ID запроса')
            return
        ok, text = self.db.reject_return_request(int(self.request_id.text()), self.user['id'])
        (message if ok else error)(self, 'Возврат', text) if ok else error(self, text)
        self.refresh()

    def fill_table(self, table, headers, rows):
        fill_table(table, headers, rows)
