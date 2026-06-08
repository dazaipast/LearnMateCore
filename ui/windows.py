import sys

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QFormLayout, QLabel, QLineEdit,
    QPushButton, QMessageBox, QStatusBar,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QAction

from constants import ROLE_NAMES
from services import (
    UserService,
    CourseService,
    AuditService,
    StatsService,
    LearningService,
    ReportService,
)
from ui.dashboards import AdminDashboardWidget, DepartmentHeadDashboardWidget
from ui.employee import EmployeeLearningWidget

class LoginWindow(QMainWindow):
    login_success = pyqtSignal()
    
    def __init__(self, auth_manager):
        super().__init__()
        self.auth_manager = auth_manager
        self.setWindowTitle("LearnMate Core - Вход")
        self.setFixedSize(400, 350)
        self._init_ui()
    
    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(40, 40, 40, 40)
        
        title = QLabel("LearnMate Core")
        title.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        subtitle = QLabel("Клиника РАМИ")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)
        layout.addSpacing(30)
        
        form = QFormLayout()
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("Введите email")
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Введите пароль")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Email:", self.email_input)
        form.addRow("Пароль:", self.password_input)
        layout.addLayout(form)
        layout.addSpacing(20)
        
        self.login_btn = QPushButton("Войти")
        self.login_btn.clicked.connect(self._attempt_login)
        layout.addWidget(self.login_btn)
        layout.addStretch()
    
    def _attempt_login(self):
        email = self.email_input.text().strip()
        password = self.password_input.text()
        if not email or not password:
            QMessageBox.warning(self, "Ошибка", "Введите email и пароль")
            return
        if self.auth_manager.authenticate(email, password):
            self.login_success.emit()
            self.close()
        else:
            QMessageBox.critical(self, "Ошибка", "Неверный email или пароль")


class MainWindow(QMainWindow):
    def __init__(self, auth_manager, db_manager):
        super().__init__()
        self.auth_manager = auth_manager
        self.db_manager = db_manager
        self.current_user = auth_manager.get_current_user()
        
        if not self.current_user:
            QMessageBox.critical(self, "Ошибка", "Пользователь не найден")
            sys.exit(1)
        
        self.setWindowTitle(f"LearnMate Core - {self.current_user.full_name}")
        self.setGeometry(100, 100, 1200, 800)
        self._init_ui()
    
    def _init_ui(self):
        self._create_menu()
        self._create_status_bar()
        self._create_central_widget()
    
    def _create_menu(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("Файл")
        logout_action = QAction("Выход", self)
        logout_action.triggered.connect(self._logout)
        file_menu.addAction(logout_action)
        
        help_menu = menubar.addMenu("Помощь")
        about_action = QAction("О программе", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)
    
    def _create_status_bar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage(
            f"{self.current_user.full_name} | {self.current_user.position} | "
            f"{ROLE_NAMES.get(self.current_user.role_id, '')}"
        )
    
    def _create_central_widget(self):
        user_service = UserService(self.db_manager)
        course_service = CourseService(self.db_manager)
        audit_service = AuditService(self.db_manager)
        stats_service = StatsService(self.db_manager)
        report_service = ReportService(self.db_manager, stats_service)
        if self.current_user.is_role('main_admin'):
            widget = AdminDashboardWidget(
                self.current_user,
                self.db_manager,
                user_service,
                course_service,
                audit_service,
                stats_service,
                report_service,
            )
        elif self.current_user.is_role('department_head'):
            widget = DepartmentHeadDashboardWidget(
                self.current_user,
                self.db_manager,
                user_service,
                course_service,
                audit_service,
                stats_service,
                report_service,
            )
        else:
            widget = EmployeeLearningWidget(
                self.current_user,
                self.db_manager,
                course_service,
                LearningService(self.db_manager),
            )
        self.setCentralWidget(widget)
    
    def _logout(self):
        if QMessageBox.question(self, 'Выход', 'Вы уверены?') == QMessageBox.StandardButton.Yes:
            self.auth_manager.logout()
            self.close()
    
    def _show_about(self):
        QMessageBox.about(self, "О программе", f"LearnMate Core v2.1\nКлиника РАМИ\nПользователь: {self.current_user.full_name}")


