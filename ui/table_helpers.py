from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem, QListWidget, QListWidgetItem, QComboBox
from PyQt6.QtCore import Qt

from utils import (
    format_percent,
    format_audit_timestamp,
    audit_action_label,
    format_event_line,
    format_ratio,
    format_history_date,
)

def configure_readonly_table(table, headers):
    table.setColumnCount(len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)


def get_selected_row_id(table):
    row = table.currentRow()
    if row < 0:
        return None
    item = table.item(row, 0)
    return item.data(Qt.ItemDataRole.UserRole) if item else None


get_selected_course_id = get_selected_row_id
get_selected_user_id = get_selected_row_id


def fill_courses_table(table, courses):
    table.setRowCount(len(courses))
    for row, course in enumerate(courses):
        title_item = QTableWidgetItem(course.title)
        title_item.setData(Qt.ItemDataRole.UserRole, course.id)
        table.setItem(row, 0, title_item)
        table.setItem(row, 1, QTableWidgetItem(course.department.name if course.department else ""))
        table.setItem(row, 2, QTableWidgetItem(course.creator.full_name if course.creator else ""))
        table.setItem(row, 3, QTableWidgetItem(str(course.deadline_days)))
        table.setItem(row, 4, QTableWidgetItem(str(course.pass_threshold)))
        table.setItem(row, 5, QTableWidgetItem("Активен" if course.is_active else "Неактивен"))


def fill_users_table(table, users):
    table.setRowCount(len(users))
    for row, user in enumerate(users):
        name_item = QTableWidgetItem(user.full_name)
        name_item.setData(Qt.ItemDataRole.UserRole, user.id)
        table.setItem(row, 0, name_item)
        table.setItem(row, 1, QTableWidgetItem(user.position))
        table.setItem(row, 2, QTableWidgetItem(user.department.name if user.department else ""))
        table.setItem(row, 3, QTableWidgetItem(user.role.name if user.role else ""))
        table.setItem(row, 4, QTableWidgetItem(user.email))
        table.setItem(row, 5, QTableWidgetItem("Активен" if user.is_active else "Неактивен"))


def fill_employees_table(table, employees, progress_map, employee_stats=None):
    stats_by_id = {row["user_id"]: row for row in (employee_stats or [])}
    table.setRowCount(len(employees))
    for row, employee in enumerate(employees):
        stat = stats_by_id.get(employee.id)
        name_item = QTableWidgetItem(employee.full_name)
        name_item.setData(Qt.ItemDataRole.UserRole, employee.id)
        table.setItem(row, 0, name_item)
        table.setItem(row, 1, QTableWidgetItem(employee.position))
        if table.columnCount() >= 5 and stat:
            table.setItem(row, 2, QTableWidgetItem(str(stat["assigned_courses"])))
            table.setItem(row, 3, QTableWidgetItem(format_percent(stat["progress"])))
            table.setItem(row, 4, QTableWidgetItem(stat["performance"]))
        else:
            progress = stat["progress"] if stat else progress_map.get(employee.id, 0)
            table.setItem(row, 2, QTableWidgetItem(format_percent(progress)))
            status = "✅ Активен" if employee.is_active else "Неактивен"
            table.setItem(row, 3, QTableWidgetItem(status))


def fill_events_list(widget, events):
    widget.clear()
    if not events:
        item = QListWidgetItem("Событий пока нет")
        item.setFlags(Qt.ItemFlag.ItemIsEnabled)
        widget.addItem(item)
        return
    for entry in events:
        widget.addItem(QListWidgetItem(format_event_line(entry)))


def fill_audit_table(table, logs):
    table.setRowCount(len(logs))
    for row, entry in enumerate(logs):
        table.setItem(row, 0, QTableWidgetItem(format_audit_timestamp(entry["created_at"])))
        table.setItem(row, 1, QTableWidgetItem(entry["user_name"]))
        table.setItem(row, 2, QTableWidgetItem(entry["department_name"]))
        table.setItem(row, 3, QTableWidgetItem(audit_action_label(entry["action"])))
        table.setItem(row, 4, QTableWidgetItem(entry["details"]))


def fill_department_stats_table(table, rows):
    table.setRowCount(len(rows))
    for row_index, row in enumerate(rows):
        table.setItem(row_index, 0, QTableWidgetItem(row["department_name"]))
        table.setItem(row_index, 1, QTableWidgetItem(str(row["employees"])))
        table.setItem(row_index, 2, QTableWidgetItem(str(row["learning_count"])))
        table.setItem(row_index, 3, QTableWidgetItem(str(row["courses"])))
        table.setItem(row_index, 4, QTableWidgetItem(format_percent(row["avg_progress"])))
        table.setItem(row_index, 5, QTableWidgetItem(format_percent(row["pass_rate"])))


def fill_course_stats_table(table, rows, include_department=False):
    table.setRowCount(len(rows))
    for row_index, row in enumerate(rows):
        col = 0
        table.setItem(row_index, col, QTableWidgetItem(row["title"]))
        col += 1
        if include_department:
            table.setItem(row_index, col, QTableWidgetItem(row["department_name"]))
            col += 1
        table.setItem(row_index, col, QTableWidgetItem(str(row["assigned"])))
        table.setItem(row_index, col + 1, QTableWidgetItem(format_ratio(row["passed"], row["assigned"])))
        table.setItem(row_index, col + 2, QTableWidgetItem(format_ratio(row["completed"], row["assigned"])))
        table.setItem(row_index, col + 3, QTableWidgetItem(format_percent(row["avg_progress"])))


def fill_employee_stats_table(table, rows, include_department=False):
    table.setRowCount(len(rows))
    for row_index, row in enumerate(rows):
        col = 0
        table.setItem(row_index, col, QTableWidgetItem(row["full_name"]))
        col += 1
        table.setItem(row_index, col, QTableWidgetItem(row["position"]))
        col += 1
        if include_department:
            table.setItem(row_index, col, QTableWidgetItem(row["department_name"]))
            col += 1
        table.setItem(row_index, col, QTableWidgetItem(str(row["assigned_courses"])))
        table.setItem(row_index, col + 1, QTableWidgetItem(format_percent(row["progress"])))
        table.setItem(row_index, col + 2, QTableWidgetItem(row["performance"]))


def fill_text_list(widget, items):
    widget.clear()
    if not items:
        item = QListWidgetItem("Нет данных")
        item.setFlags(Qt.ItemFlag.ItemIsEnabled)
        widget.addItem(item)
        return
    for entry in items:
        text = entry["text"] if isinstance(entry, dict) else str(entry)
        widget.addItem(QListWidgetItem(text))


def fill_history_table(table, rows):
    table.setRowCount(len(rows))
    for row_index, row in enumerate(rows):
        title = row["title"]
        if not row.get("is_active", True):
            title += " (архив)"
        table.setItem(row_index, 0, QTableWidgetItem(title))
        table.setItem(row_index, 1, QTableWidgetItem(format_history_date(row["assigned_at"])))
        table.setItem(row_index, 2, QTableWidgetItem(format_history_date(row["started_at"])))
        table.setItem(row_index, 3, QTableWidgetItem(format_history_date(row["completed_at"])))
        table.setItem(row_index, 4, QTableWidgetItem(format_percent(row["progress"])))
        table.setItem(row_index, 5, QTableWidgetItem(row["status"]))


def fill_problem_employees_table(table, rows):
    table.setRowCount(len(rows))
    for row_index, row in enumerate(rows):
        table.setItem(row_index, 0, QTableWidgetItem(row["full_name"]))
        table.setItem(row_index, 1, QTableWidgetItem(row["department_name"]))
        table.setItem(row_index, 2, QTableWidgetItem(format_percent(row["progress"])))
        table.setItem(row_index, 3, QTableWidgetItem(row["performance"]))
        table.setItem(row_index, 4, QTableWidgetItem(str(row["assigned_courses"])))


def populate_department_combo(combo, departments, actor_user, fixed_department_id=None):
    combo.clear()
    for dept in departments:
        combo.addItem(dept.name, dept.id)
    if fixed_department_id or actor_user.is_role('department_head'):
        combo.setEnabled(False)

