ROLE_CODES = {'main_admin': 1, 'department_head': 2, 'employee': 3}
ROLE_NAMES = {1: "Главный администратор", 2: "Руководитель", 3: "Сотрудник"}
MAIN_ADMIN_ROLE_ID = ROLE_CODES['main_admin']
DEPT_HEAD_ROLE_ID = ROLE_CODES['department_head']
EMPLOYEE_ROLE_ID = ROLE_CODES['employee']

MIN_PASSWORD_LENGTH = 6
DEFAULT_DEADLINE_DAYS = 30
DEFAULT_PASS_THRESHOLD = 80
MODULES_PER_COURSE = 5

COURSE_TABLE_HEADERS = ["Название", "Отдел", "Создатель", "Срок (дн.)", "Порог %", "Статус"]
STAT_VALUE_STYLE = "font-size: 26px; font-weight: bold; color: {color};"
STAT_TITLE_STYLE = "font-size: 13px; font-weight: bold; color: #2c3e50;"
STAT_DESC_STYLE = "font-size: 11px; color: #7f8c8d;"
STAT_CARD_STYLE = (
    "background: #ffffff; border-radius: 8px; padding: 12px; "
    "margin: 5px; border: 1px solid #bdc3c7;"
)
STAT_COLORS = ("#3498db", "#2ecc71", "#e74c3c", "#9b59b6")

DEPT_STATS_HEADERS = [
    "Отдел", "Сотрудников", "Обучается", "Курсов", "Прогресс", "Успеваемость",
]
COURSE_STATS_HEADERS = [
    "Курс", "Назначено", "Сдано", "Завершено", "Ср. прогресс",
]
ADMIN_COURSE_STATS_HEADERS = [
    "Курс", "Отдел", "Назначено", "Сдано", "Завершено", "Ср. прогресс",
]
EMPLOYEE_STATS_HEADERS = [
    "ФИО", "Должность", "Отдел", "Курсов", "Прогресс", "Оценка",
]
DEPT_EMPLOYEE_STATS_HEADERS = [
    "ФИО", "Должность", "Курсов", "Прогресс", "Оценка",
]
PROBLEM_EMPLOYEE_HEADERS = [
    "ФИО", "Отдел", "Прогресс", "Оценка", "Курсов",
]
HISTORY_HEADERS = [
    "Курс", "Назначен", "Начат", "Завершён", "Прогресс", "Статус",
]

AUDIT_LOG_LIMIT = 200
EVENT_FEED_LIMIT = 8

AUDIT_ACTION_LABELS = {
    "login": "Вход в систему",
    "logout": "Выход из системы",
    "create_user": "Создание пользователя",
    "deactivate_user": "Деактивация пользователя",
    "delete_user": "Удаление пользователя",
    "change_department": "Смена отдела",
    "create_course": "Создание курса",
    "deactivate_course": "Удаление курса",
    "assign_course": "Назначение курса",
    "complete_module": "Пройден модуль",
    "complete_course": "Завершение курса",
}

EVENT_ACTION_ICONS = {
    "login": "→",
    "logout": "←",
    "create_user": "+",
    "deactivate_user": "⚠",
    "delete_user": "⚠",
    "change_department": "↔",
    "create_course": "+",
    "deactivate_course": "⚠",
    "assign_course": "→",
    "complete_module": "→",
    "complete_course": "✓",
}
