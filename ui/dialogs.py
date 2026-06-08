from types import SimpleNamespace

from sqlalchemy.orm import joinedload
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit,
    QTextEdit, QComboBox, QSpinBox, QListWidget, QListWidgetItem,
    QDialogButtonBox, QMessageBox, QTableWidget,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from constants import (
    ROLE_NAMES,
    MAIN_ADMIN_ROLE_ID,
    DEPT_HEAD_ROLE_ID,
    EMPLOYEE_ROLE_ID,
    MIN_PASSWORD_LENGTH,
    DEFAULT_DEADLINE_DAYS,
    DEFAULT_PASS_THRESHOLD,
)
from models import Department, User, Course
from utils import (
    load_departments_for_actor,
    build_module_content,
)

from ui.table_helpers import (
    get_selected_course_id,
    populate_department_combo,
)

class ChangeDepartmentDialog(QDialog):
    def __init__(self, db_manager, actor_user, user_service, target_user_id, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.actor_user = actor_user
        self.user_service = user_service
        self.target_user_id = target_user_id

        self.setWindowTitle("Изменить отдел")
        self.setMinimumWidth(420)
        self._init_ui()
        self._load_data()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.user_label = QLabel()
        form.addRow("Пользователь:", self.user_label)

        self.role_label = QLabel()
        form.addRow("Роль:", self.role_label)

        self.current_dept_label = QLabel()
        form.addRow("Текущий отдел:", self.current_dept_label)

        self.department_combo = QComboBox()
        form.addRow("Новый отдел:", self.department_combo)

        layout.addLayout(form)

        hint = QLabel(
            "При смене отдела незавершённые курсы будут отменены, "
            "а курсы нового отдела — назначены автоматически."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Сохранить")
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_data(self):
        with self.db_manager.session_scope() as db:
            target = (
                db.query(User)
                .options(joinedload(User.department), joinedload(User.role))
                .filter(User.id == self.target_user_id)
                .first()
            )
            if not target:
                raise ValueError("Пользователь не найден")
            if not self.user_service.can_change_department(self.actor_user, target):
                raise PermissionError("Недостаточно прав для смены отдела")

            self.user_label.setText(target.full_name)
            self.role_label.setText(target.role.name if target.role else "")
            self.current_dept_label.setText(target.department.name if target.department else "—")

            departments = db.query(Department).order_by(Department.name).all()
            for dept in departments:
                if dept.id != target.department_id:
                    self.department_combo.addItem(dept.name, dept.id)

        if self.department_combo.count() == 0:
            raise ValueError("Нет других отделов для перевода")

    def _on_save(self):
        new_department_id = self.department_combo.currentData()
        try:
            self.user_service.change_department(
                self.actor_user.id,
                self.target_user_id,
                new_department_id,
            )
            self.accept()
        except PermissionError as exc:
            QMessageBox.warning(self, "Доступ запрещён", str(exc))
        except ValueError as exc:
            QMessageBox.warning(self, "Ошибка", str(exc))
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка", f"Не удалось изменить отдел: {exc}")


def confirm_deactivate_user(parent, user_name, is_employee=False):
    if is_employee:
        message = (
            f"Удалить сотрудника «{user_name}»?\n\n"
            "Запись будет полностью удалена из системы вместе с назначениями курсов. "
            "Это действие нельзя отменить."
        )
    else:
        message = (
            f"Удалить пользователя «{user_name}»?\n\n"
            "Аккаунт будет деактивирован и не сможет войти в систему."
        )
    return (
        QMessageBox.question(
            parent,
            "Удаление пользователя",
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        == QMessageBox.StandardButton.Yes
    )


def confirm_deactivate_course(parent, course_title):
    return (
        QMessageBox.question(
            parent,
            "Удаление курса",
            f"Удалить курс «{course_title}»?\n\n"
            "Курс будет деактивирован и исчезнет из списков обучения.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        == QMessageBox.StandardButton.Yes
    )


def deactivate_selected_course(parent, actor_user, course_service, table, on_success):
    course_id = get_selected_course_id(table)
    if not course_id:
        QMessageBox.information(parent, "Удаление", "Выберите курс в таблице")
        return
    row = table.currentRow()
    course_title = table.item(row, 0).text()
    if not confirm_deactivate_course(parent, course_title):
        return
    try:
        course_service.deactivate_course(actor_user.id, course_id)
        QMessageBox.information(parent, "Готово", "Курс удалён")
        on_success()
    except PermissionError as exc:
        QMessageBox.warning(parent, "Доступ запрещён", str(exc))
    except ValueError as exc:
        QMessageBox.warning(parent, "Ошибка", str(exc))
    except Exception as exc:
        QMessageBox.critical(parent, "Ошибка", f"Не удалось удалить курс: {exc}")


class AddUserDialog(QDialog):
    def __init__(
        self,
        db_manager,
        actor_user,
        user_service,
        preset_role_id=None,
        fixed_department_id=None,
        parent=None,
    ):
        super().__init__(parent)
        self.db_manager = db_manager
        self.actor_user = actor_user
        self.user_service = user_service
        self.preset_role_id = preset_role_id
        self.fixed_department_id = fixed_department_id
        self.created_user_id = None

        titles = {
            EMPLOYEE_ROLE_ID: "Добавить сотрудника",
            DEPT_HEAD_ROLE_ID: "Добавить руководителя",
            MAIN_ADMIN_ROLE_ID: "Добавить администратора",
        }
        self.setWindowTitle(titles.get(preset_role_id, "Добавить пользователя"))
        self.setMinimumWidth(420)
        self._init_ui()
        self._load_departments()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.full_name_input = QLineEdit()
        self.full_name_input.setPlaceholderText("Иванов Иван Иванович")
        form.addRow("ФИО:", self.full_name_input)

        self.position_input = QLineEdit()
        self.position_input.setPlaceholderText("Должность")
        form.addRow("Должность:", self.position_input)

        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("user@rami-clinic.ru")
        form.addRow("Email:", self.email_input)

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText(f"Минимум {MIN_PASSWORD_LENGTH} символов")
        form.addRow("Пароль:", self.password_input)

        self.department_combo = QComboBox()
        form.addRow("Отдел:", self.department_combo)

        self.role_combo = QComboBox()
        if self.actor_user.is_role('main_admin'):
            for role_id, label in (
                (EMPLOYEE_ROLE_ID, ROLE_NAMES[EMPLOYEE_ROLE_ID]),
                (DEPT_HEAD_ROLE_ID, ROLE_NAMES[DEPT_HEAD_ROLE_ID]),
                (MAIN_ADMIN_ROLE_ID, ROLE_NAMES[MAIN_ADMIN_ROLE_ID]),
            ):
                self.role_combo.addItem(label, role_id)
        elif self.actor_user.is_role('department_head'):
            self.role_combo.addItem(ROLE_NAMES[EMPLOYEE_ROLE_ID], EMPLOYEE_ROLE_ID)

        if self.preset_role_id is not None:
            index = self.role_combo.findData(self.preset_role_id)
            if index >= 0:
                self.role_combo.setCurrentIndex(index)
        if self.preset_role_id is not None or self.actor_user.is_role('department_head'):
            self.role_combo.setEnabled(False)
        form.addRow("Роль:", self.role_combo)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Создать")
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_departments(self):
        with self.db_manager.session_scope() as db:
            departments = load_departments_for_actor(
                db, self.actor_user, self.fixed_department_id
            )
        populate_department_combo(
            self.department_combo, departments, self.actor_user, self.fixed_department_id
        )

    def _on_save(self):
        role_id = self.role_combo.currentData()
        department_id = self.department_combo.currentData()
        try:
            self.created_user_id = self.user_service.create_user(
                actor_id=self.actor_user.id,
                full_name=self.full_name_input.text(),
                email=self.email_input.text(),
                password=self.password_input.text(),
                position=self.position_input.text(),
                department_id=department_id,
                role_id=role_id,
            )
            self.accept()
        except PermissionError as exc:
            QMessageBox.warning(self, "Доступ запрещён", str(exc))
        except ValueError as exc:
            QMessageBox.warning(self, "Ошибка", str(exc))
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка", f"Не удалось создать пользователя: {exc}")


class AddCourseDialog(QDialog):
    def __init__(self, db_manager, actor_user, course_service, fixed_department_id=None, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.actor_user = actor_user
        self.course_service = course_service
        self.fixed_department_id = fixed_department_id
        self.created_course_id = None

        self.setWindowTitle("Создать курс")
        self.setMinimumWidth(480)
        self._init_ui()
        self._load_departments()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("Например: Адаптация оператора КЦ")
        form.addRow("Название:", self.title_input)

        self.description_input = QTextEdit()
        self.description_input.setPlaceholderText("Описание курса, цели обучения...")
        self.description_input.setMaximumHeight(120)
        form.addRow("Описание:", self.description_input)

        self.department_combo = QComboBox()
        form.addRow("Отдел:", self.department_combo)

        self.deadline_input = QSpinBox()
        self.deadline_input.setRange(1, 365)
        self.deadline_input.setValue(DEFAULT_DEADLINE_DAYS)
        self.deadline_input.setSuffix(" дн.")
        form.addRow("Срок прохождения:", self.deadline_input)

        self.threshold_input = QSpinBox()
        self.threshold_input.setRange(1, 100)
        self.threshold_input.setValue(DEFAULT_PASS_THRESHOLD)
        self.threshold_input.setSuffix(" %")
        form.addRow("Порог сдачи:", self.threshold_input)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Создать")
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_departments(self):
        with self.db_manager.session_scope() as db:
            departments = load_departments_for_actor(
                db, self.actor_user, self.fixed_department_id
            )
        populate_department_combo(
            self.department_combo, departments, self.actor_user, self.fixed_department_id
        )

    def _on_save(self):
        try:
            self.created_course_id = self.course_service.create_course(
                actor_id=self.actor_user.id,
                title=self.title_input.text(),
                description=self.description_input.toPlainText(),
                department_id=self.department_combo.currentData(),
                deadline_days=self.deadline_input.value(),
                pass_threshold=self.threshold_input.value(),
            )
            self.accept()
        except PermissionError as exc:
            QMessageBox.warning(self, "Доступ запрещён", str(exc))
        except ValueError as exc:
            QMessageBox.warning(self, "Ошибка", str(exc))
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка", f"Не удалось создать курс: {exc}")


class AssignCourseDialog(QDialog):
    def __init__(self, db_manager, actor_user, course_service, course_id, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.actor_user = actor_user
        self.course_service = course_service
        self.course_id = course_id
        self._already_assigned = set()

        self.setWindowTitle("Назначить обучение")
        self.setMinimumSize(480, 420)
        self._init_ui()
        self._load_data()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        self.course_label = QLabel()
        self.course_label.setWordWrap(True)
        layout.addWidget(self.course_label)

        hint = QLabel("Отметьте сотрудников, которым нужно назначить курс:")
        layout.addWidget(hint)

        self.employees_list = QListWidget()
        layout.addWidget(self.employees_list)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Назначить")
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_data(self):
        with self.db_manager.session_scope() as db:
            course = (
                db.query(Course)
                .options(joinedload(Course.department))
                .filter(Course.id == self.course_id)
                .first()
            )
            if not course:
                raise ValueError("Курс не найден")
            dept_name = course.department.name if course.department else "—"
            self.course_label.setText(
                f"Курс: {course.title}\nОтдел: {dept_name} | "
                f"Срок: {course.deadline_days} дн. | Порог: {course.pass_threshold}%"
            )

        employees = self.course_service.get_assignable_employees(
            self.actor_user.id, self.course_id
        )
        self.employees_list.clear()
        if not employees:
            self.employees_list.addItem("Нет доступных сотрудников для назначения")
            return

        show_department = self.actor_user.is_role('main_admin')
        for employee in employees:
            label = employee["full_name"]
            if show_department:
                label += f" — {employee['department_name']}"
            if employee["assigned"]:
                label += " (уже назначен)"
                self._already_assigned.add(employee["id"])

            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, employee["id"])
            if employee["assigned"]:
                item.setFlags(Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked)
            else:
                item.setFlags(
                    Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled
                )
                item.setCheckState(Qt.CheckState.Unchecked)
            self.employees_list.addItem(item)

    def _on_save(self):
        selected_ids = []
        for index in range(self.employees_list.count()):
            item = self.employees_list.item(index)
            user_id = item.data(Qt.ItemDataRole.UserRole)
            if user_id is None:
                continue
            if (
                item.checkState() == Qt.CheckState.Checked
                and user_id not in self._already_assigned
            ):
                selected_ids.append(user_id)

        try:
            count = self.course_service.assign_course(
                self.actor_user.id, self.course_id, selected_ids
            )
            QMessageBox.information(
                self, "Готово", f"Курс назначен {count} сотрудникам"
            )
            self.accept()
        except PermissionError as exc:
            QMessageBox.warning(self, "Доступ запрещён", str(exc))
        except ValueError as exc:
            QMessageBox.warning(self, "Ошибка", str(exc))
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка", f"Не удалось назначить курс: {exc}")


def open_assign_course_dialog(parent, actor_user, course_service, course_id=None, on_success=None):
    if not course_id and hasattr(parent, "courses_table"):
        course_id = get_selected_course_id(parent.courses_table)
    if not course_id:
        QMessageBox.information(parent, "Назначение", "Выберите курс в таблице")
        return
    try:
        dialog = AssignCourseDialog(
            parent.db_manager,
            actor_user,
            course_service,
            course_id,
            parent=parent,
        )
    except (PermissionError, ValueError) as exc:
        QMessageBox.warning(parent, "Ошибка", str(exc))
        return

    if dialog.exec() == QDialog.DialogCode.Accepted and on_success:
        on_success()


def offer_assign_after_create(parent, actor_user, course_service, course_id, on_success):
    answer = QMessageBox.question(
        parent,
        "Назначить обучение",
        "Курс создан. Назначить его сотрудникам сейчас?",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.Yes,
    )
    if answer == QMessageBox.StandardButton.Yes:
        try:
            dialog = AssignCourseDialog(
                parent.db_manager,
                actor_user,
                course_service,
                course_id,
                parent=parent,
            )
            if dialog.exec() == QDialog.DialogCode.Accepted and on_success:
                on_success()
        except (PermissionError, ValueError) as exc:
            QMessageBox.warning(parent, "Ошибка", str(exc))


class CoursePassingDialog(QDialog):
    def __init__(self, actor_user, course_service, course_id, on_progress=None, parent=None):
        super().__init__(parent)
        self.actor_user = actor_user
        self.course_service = course_service
        self.course_id = course_id
        self.on_progress = on_progress

        self.setMinimumSize(560, 480)
        self._init_ui()
        self._load_state()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        self.title_label = QLabel()
        self.title_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)

        self.meta_label = QLabel()
        self.meta_label.setWordWrap(True)
        layout.addWidget(self.meta_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(100)
        layout.addWidget(self.progress_bar)

        self.module_label = QLabel()
        layout.addWidget(self.module_label)

        self.content = QTextEdit()
        self.content.setReadOnly(True)
        layout.addWidget(self.content)

        self.advance_btn = QPushButton("Завершить модуль")
        self.advance_btn.clicked.connect(self._on_advance)
        layout.addWidget(self.advance_btn)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

    def _load_state(self):
        try:
            state = self.course_service.get_passing_state(
                self.actor_user.id, self.course_id
            )
        except (PermissionError, ValueError) as exc:
            QMessageBox.warning(self, "Ошибка", str(exc))
            self.reject()
            return

        self._state = state
        self.setWindowTitle(f"Прохождение: {state['title']}")
        self.title_label.setText(state["title"])
        self.meta_label.setText(
            f"Отдел: {state['department_name']} | "
            f"Срок: {state['deadline_days']} дн. | "
            f"Порог сдачи: {state['pass_threshold']}% | "
            f"Статус: {state['status']}"
        )
        self.progress_bar.setValue(int(round(state["progress"])))
        self.progress_bar.setFormat(f"Прогресс: {state['progress']:.0f}%")

        if state["is_completed"]:
            self.module_label.setText(
                f"Курс завершён ({state['modules_completed']}/{state['module_count']} модулей)"
            )
            self.content.setPlainText(
                "Поздравляем! Вы прошли все модули курса.\n\n"
                "При необходимости вы можете просмотреть материалы через кнопку «Просмотр»."
            )
            self.advance_btn.setEnabled(False)
            self.advance_btn.setText("Курс завершён")
            return

        module_index = state["current_module"]
        course_stub = SimpleNamespace(description=state["description"])
        self.module_label.setText(
            f"Модуль {module_index} из {state['module_count']} "
            f"(пройдено: {state['modules_completed']})"
        )
        self.content.setPlainText(
            build_module_content(course_stub, module_index, state["module_count"])
        )
        self.advance_btn.setEnabled(True)
        self.advance_btn.setText(f"Завершить модуль {module_index}")

    def _on_advance(self):
        try:
            new_progress = self.course_service.advance_module(
                self.actor_user.id, self.course_id
            )
        except (PermissionError, ValueError) as exc:
            QMessageBox.warning(self, "Ошибка", str(exc))
            return
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка", f"Не удалось обновить прогресс: {exc}")
            return

        if self.on_progress:
            self.on_progress()

        if new_progress >= 100:
            QMessageBox.information(self, "Готово", "Курс успешно завершён!")
        self._load_state()


def open_course_passing_dialog(actor_user, course_service, course_id, parent, on_success=None):
    dialog = CoursePassingDialog(
        actor_user,
        course_service,
        course_id,
        on_progress=on_success,
        parent=parent,
    )
    dialog.exec()


class CourseDetailsDialog(QDialog):
    def __init__(self, course, progress=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Просмотр курса")
        self.setMinimumWidth(500)

        layout = QVBoxLayout(self)
        info = QTextEdit()
        info.setReadOnly(True)

        lines = [
            f"Название: {course.title}",
            f"Отдел: {course.department.name if course.department else '—'}",
            f"Создатель: {course.creator.full_name if course.creator else '—'}",
            f"Срок прохождения: {course.deadline_days} дн.",
            f"Порог сдачи: {course.pass_threshold}%",
            f"Статус: {'Активен' if course.is_active else 'Неактивен'}",
            f"Создан: {course.created_at.strftime('%d.%m.%Y %H:%M') if course.created_at else '—'}",
        ]
        if progress is not None:
            lines.append(f"Ваш прогресс: {progress:.0f}%")
        lines.append("")
        lines.append("Описание:")
        lines.append(course.description or "Описание не указано")
        info.setPlainText("\n".join(lines))
        layout.addWidget(info)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)


def show_course_details(actor_user, course_service, course_id, parent):
    try:
        course, progress = course_service.get_course_details(actor_user.id, course_id)
    except PermissionError as exc:
        QMessageBox.warning(parent, "Доступ запрещён", str(exc))
        return
    except ValueError as exc:
        QMessageBox.warning(parent, "Ошибка", str(exc))
        return
    CourseDetailsDialog(course, progress, parent=parent).exec()

