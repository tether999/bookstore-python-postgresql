from PyQt6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton, QTableWidget, QVBoxLayout, QWidget

from utils import error, message, fill_table


class AccountTab(QWidget):
    def __init__(self, db, user):
        super().__init__()
        self.db = db
        self.user = user
        main = QVBoxLayout(self)

        main.addWidget(QLabel('Активные книги'))
        self.active_table = QTableWidget()
        main.addWidget(self.active_table)

        btn_row = QHBoxLayout()
        self.loan_id_edit = QLineEdit()
        self.loan_id_edit.setPlaceholderText('ID выдачи для возврата')
        return_btn = QPushButton('Запросить возврат')
        return_btn.clicked.connect(self.request_return)
        btn_row.addWidget(self.loan_id_edit)
        btn_row.addWidget(return_btn)
        main.addLayout(btn_row)

        main.addWidget(QLabel('История'))
        self.history_table = QTableWidget()
        main.addWidget(self.history_table)

        main.addWidget(QLabel('Уведомления'))
        self.notifications_table = QTableWidget()
        main.addWidget(self.notifications_table)
        self.refresh()

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh()

    def refresh(self):
        self.fill_table(self.active_table, ['ID выдачи', 'Книга', 'Авторы', 'Выдана', 'Дедлайн', 'Статус', 'Запрос', 'Дней просрочки', 'Штраф'], self.db.get_active_loans(self.user['id']))
        self.fill_table(self.history_table, ['Книга', 'Авторы', 'Выдана', 'Возвращена', 'Статус'], self.db.get_loan_history(self.user['id']))
        self.fill_table(self.notifications_table, ['Дата', 'Заголовок', 'Сообщение', 'Прочитано'], self.db.get_notifications(self.user['id']))
        self.db.mark_notifications_read(self.user['id'])

    def request_return(self):
        if not self.loan_id_edit.text().strip().isdigit():
            error(self, 'Введите ID выдачи')
            return
        ok, text = self.db.add_return_request(int(self.loan_id_edit.text()), self.user['id'])
        (message if ok else error)(self, 'Возврат', text) if ok else error(self, text)
        self.refresh()

    def fill_table(self, table, headers, rows):
        fill_table(table, headers, rows)
