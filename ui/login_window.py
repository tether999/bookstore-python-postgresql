from PyQt6.QtWidgets import QLineEdit, QMainWindow, QMessageBox, QPushButton

from db import Database
from ui.app_window import AppWindow
from utils import error, message


class LoginWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        try:
            self.db = Database()
        except Exception as exc:
            super().__init__()
            QMessageBox.critical(self, 'Ошибка подключения к PostgreSQL', str(exc))
            raise

        self.setWindowTitle('Библиотека')
        self.setGeometry(400, 200, 800, 500)

        self.login_edit = QLineEdit(self)
        self.password_edit = QLineEdit(self)
        self.login_edit.resize(180, 30)
        self.password_edit.resize(180, 30)
        self.login_edit.move(310, 90)
        self.password_edit.move(310, 130)
        self.login_edit.setPlaceholderText('Логин')
        self.password_edit.setPlaceholderText('Пароль')
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)

        self.email = QLineEdit(self)
        self.email.resize(180, 30)
        self.email.move(310, 170)
        self.email.setPlaceholderText('Email')

        login_btn = QPushButton('Войти', self)
        reg_btn = QPushButton('Зарегистрироваться', self)
        guest_btn = QPushButton('Войти как гость', self)
        login_btn.resize(180, 30)
        reg_btn.resize(180, 30)
        guest_btn.resize(180, 30)
        login_btn.move(310, 220)
        reg_btn.move(310, 250)
        guest_btn.move(310, 280)
        login_btn.clicked.connect(self.login)
        reg_btn.clicked.connect(self.register)
        guest_btn.clicked.connect(self.guest)

    def register(self):
        login = self.login_edit.text().strip()
        password = self.password_edit.text().strip()
        email = self.email.text().strip()
        if not login or not password or not email:
            error(self, 'Для регистрации введите логин, пароль и почту')
            return
        ok, text = self.db.add_user(
            login=login,
            password=password,
            email=email,
        )
        (message if ok else error)(self, 'Регистрация' if ok else text, text) if ok else error(self, text)

    def login(self):
        login = self.login_edit.text().strip()
        password = self.password_edit.text().strip()
        if not login or not password:
            error(self, 'Введите логин и пароль')
            return
        user = self.db.authenticate_user(login, password)
        if not user:
            error(self, 'Неверный логин или пароль')
            return
        self.open_app(user)

    def guest(self):
        self.open_app(None)

    def open_app(self, user):
        self.app_window = AppWindow(self.db, user)
        self.app_window.show()
