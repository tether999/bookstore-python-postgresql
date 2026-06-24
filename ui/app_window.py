from PyQt6.QtWidgets import QHBoxLayout, QLabel, QMainWindow, QPushButton, QTabWidget, QVBoxLayout, QWidget

from ui.catalog_tab import CatalogTab
from ui.account_tab import AccountTab
from ui.librarian_tab import LibrarianTab
from ui.admin_tab import AdminTab


class AppWindow(QMainWindow):
    def __init__(self, db, user):
        super().__init__()
        self.db = db
        self.user = user
        self.setWindowTitle('Библиотека')
        self.setGeometry(150, 80, 1100, 700)

        central = QWidget(self)
        self.setCentralWidget(central)
        main = QVBoxLayout(central)

        top = QHBoxLayout()
        role_text = 'Гость' if not user else f"{user['login']} / {user['role_name']}"
        top.addWidget(QLabel('Library project'))
        top.addStretch()
        top.addWidget(QLabel(f'Пользователь: {role_text}'))
        close_btn = QPushButton('Выход')
        close_btn.clicked.connect(self.close)
        top.addWidget(close_btn)
        main.addLayout(top)

        self.tabs = QTabWidget()
        main.addWidget(self.tabs)
        self.tabs.addTab(CatalogTab(self.db, self.user), 'Каталог')
        # Личный кабинет нужен только читателю.
        # У администратора и библиотекаря эта вкладка убрана, чтобы не показывать лишние уведомления.
        if self.user and self.user['role_name'] == 'client':
            self.tabs.addTab(AccountTab(self.db, self.user), 'Личный кабинет')
        if self.user and self.user['role_name'] in ('librarian', 'admin'):
            self.tabs.addTab(LibrarianTab(self.db, self.user), 'Библиотекарь')
        if self.user and self.user['role_name'] == 'admin':
            self.tabs.addTab(AdminTab(self.db), 'Админ')
