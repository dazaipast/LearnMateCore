from sqlalchemy.orm import joinedload
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QMessageBox, QGroupBox, QListWidget, QScrollArea,
    QProgressBar,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from constants import HISTORY_HEADERS
from models import User, UserCourse, Course
from utils import format_percent, course_pass_status, split_employee_progress
from ui.table_helpers import (
    configure_readonly_table,
    fill_text_list,
    fill_history_table,
    get_selected_course_id,
)
from ui.dialogs import open_course_passing_dialog, show_course_details

EMPLOYEE_COURSE_HEADERS = ["Название", "Прогресс", "Срок (дн.)", "Порог %", "Статус"]


class EmployeeLearningWidget(QWidget):
    def __init__(self, actor_user, db_manager, course_service, learning_service):
        super().__init__()
        self.actor_user = actor_user
        self.db_manager = db_manager
        self.course_service = course_service
        self.learning_service = learning_service
        self._init_ui()
        self._load_data()
    
    def _init_ui(self):
        outer_layout = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)

        self.welcome_label = QLabel()
        self.welcome_label.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        layout.addWidget(self.welcome_label)

        self.position_label = QLabel()
        self.dept_label = QLabel()
        layout.addWidget(self.position_label)
        layout.addWidget(self.dept_label)
        layout.addSpacing(12)

        prog_group = QGroupBox("ВАШ ПРОГРЕСС")
        prog_layout = QVBoxLayout()

        self.adapt_progress = QProgressBar()
        self.adapt_progress.setMaximum(100)
        self.adapt_progress.setFormat("Адаптация: %p%")

        self.know_progress = QProgressBar()
        self.know_progress.setMaximum(100)
        self.know_progress.setFormat("Общие знания: %p%")

        self.skill_progress = QProgressBar()
        self.skill_progress.setMaximum(100)
        self.skill_progress.setFormat("Специальные навыки: %p%")

        prog_layout.addWidget(self.adapt_progress)
        prog_layout.addWidget(self.know_progress)
        prog_layout.addWidget(self.skill_progress)
        prog_group.setLayout(prog_layout)
        layout.addWidget(prog_group)

        today_group = QGroupBox("СЕГОДНЯ ВАМ")
        today_layout = QVBoxLayout()
        self.today_list = QListWidget()
        self.today_list.setMaximumHeight(110)
        today_layout.addWidget(self.today_list)
        today_group.setLayout(today_layout)
        layout.addWidget(today_group)

        rec_group = QGroupBox("РЕКОМЕНДАЦИИ")
        rec_layout = QVBoxLayout()
        self.recommendations_list = QListWidget()
        self.recommendations_list.setMaximumHeight(110)
        rec_layout.addWidget(self.recommendations_list)
        rec_group.setLayout(rec_layout)
        layout.addWidget(rec_group)

        courses_group = QGroupBox("ДОСТУПНЫЕ КУРСЫ")
        courses_layout = QVBoxLayout()

        course_actions = QHBoxLayout()
        pass_course_btn = QPushButton("Пройти курс")
        pass_course_btn.clicked.connect(self._open_pass_course_dialog)
        view_course_btn = QPushButton("Просмотр")
        view_course_btn.clicked.connect(self._open_view_course_dialog)
        course_actions.addWidget(pass_course_btn)
        course_actions.addWidget(view_course_btn)
        course_actions.addStretch()
        courses_layout.addLayout(course_actions)

        self.courses_table = QTableWidget()
        configure_readonly_table(self.courses_table, EMPLOYEE_COURSE_HEADERS)
        self.courses_table.doubleClicked.connect(self._open_pass_course_dialog)
        courses_layout.addWidget(self.courses_table)
        courses_group.setLayout(courses_layout)
        layout.addWidget(courses_group)

        history_group = QGroupBox("ИСТОРИЯ ОБУЧЕНИЯ")
        history_layout = QVBoxLayout()
        self.history_table = QTableWidget()
        configure_readonly_table(self.history_table, HISTORY_HEADERS)
        self.history_table.setMinimumHeight(140)
        history_layout.addWidget(self.history_table)
        history_group.setLayout(history_layout)
        layout.addWidget(history_group)

        scroll.setWidget(content)
        outer_layout.addWidget(scroll)

    def _open_pass_course_dialog(self):
        course_id = get_selected_course_id(self.courses_table)
        if not course_id:
            QMessageBox.information(self, "Прохождение", "Выберите курс в таблице")
            return
        open_course_passing_dialog(
            self.actor_user,
            self.course_service,
            course_id,
            self,
            on_success=self._load_data,
        )

    def _open_view_course_dialog(self):
        course_id = get_selected_course_id(self.courses_table)
        if not course_id:
            QMessageBox.information(self, "Просмотр", "Выберите курс в таблице")
            return
        show_course_details(self.actor_user, self.course_service, course_id, self)

    def _load_data(self):
        with self.db_manager.session_scope() as db:
            user = (
                db.query(User)
                .options(joinedload(User.department))
                .filter(User.id == self.actor_user.id)
                .first()
            )
            if user:
                first_name = user.full_name.split(maxsplit=1)[0]
                self.welcome_label.setText(f"Добрый день, {first_name}!")
                self.position_label.setText(f"Должность: {user.position}")
                self.dept_label.setText(f"Отдел: {user.department.name if user.department else ''}")

            user_courses = (
                db.query(UserCourse)
                .options(joinedload(UserCourse.course))
                .join(Course, UserCourse.course_id == Course.id)
                .filter(
                    UserCourse.user_id == self.actor_user.id,
                    Course.is_active.is_(True),
                )
                .all()
            )

            active_courses = [
                uc for uc in user_courses if uc.course and uc.course.is_active
            ]
            self.courses_table.setRowCount(len(active_courses))
            for row, uc in enumerate(active_courses):
                title_item = QTableWidgetItem(uc.course.title)
                title_item.setData(Qt.ItemDataRole.UserRole, uc.course.id)
                status = course_pass_status(uc.progress, uc.course.pass_threshold)
                self.courses_table.setItem(row, 0, title_item)
                self.courses_table.setItem(row, 1, QTableWidgetItem(format_percent(uc.progress)))
                self.courses_table.setItem(row, 2, QTableWidgetItem(str(uc.course.deadline_days)))
                self.courses_table.setItem(row, 3, QTableWidgetItem(str(uc.course.pass_threshold)))
                self.courses_table.setItem(row, 4, QTableWidgetItem(status))

            if active_courses:
                adapt, know, skill = split_employee_progress(active_courses)
            else:
                adapt = know = skill = 0
            self.adapt_progress.setValue(adapt)
            self.know_progress.setValue(know)
            self.skill_progress.setValue(skill)

            fill_text_list(
                self.today_list,
                self.learning_service.get_today_tasks(self.actor_user.id, db=db),
            )
            fill_text_list(
                self.recommendations_list,
                self.learning_service.get_recommendations(self.actor_user.id, db=db),
            )
            fill_history_table(
                self.history_table,
                self.learning_service.get_learning_history(self.actor_user.id, db=db),
            )



