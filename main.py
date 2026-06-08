"""
LearnMate Core — система адаптивного обучения для Клиники РАМИ.
Версия: 3.0
"""

import sys

from PyQt6.QtWidgets import QApplication

from database import DatabaseManager
from services import AuthManager
from ui.windows import LoginWindow, MainWindow


def main():
    app = QApplication(sys.argv)
    db_manager = DatabaseManager()
    db_manager.init_test_data()
    auth_manager = AuthManager(db_manager)

    login = LoginWindow(auth_manager)
    main_window = None

    def on_login():
        nonlocal main_window
        main_window = MainWindow(auth_manager, db_manager)
        main_window.show()

    login.login_success.connect(on_login)
    login.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
