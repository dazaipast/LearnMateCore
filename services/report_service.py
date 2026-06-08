from sqlalchemy.orm import joinedload

from models import User
from services.stats_service import StatsService
from utils import save_csv_report


def _pct(value):
    return f"{round(value or 0):.0f}%"


def _ratio(passed, total):
    return f"{passed}/{total}"


class ReportService:
    def __init__(self, db_manager, stats_service=None):
        self.db_manager = db_manager
        self.stats_service = stats_service or StatsService(db_manager)

    def export_admin_report(self, actor_id, file_path):
        with self.db_manager.session_scope() as db:
            actor = self._require_admin(db, actor_id)
            summary = self.stats_service.get_admin_summary(db)
            dept_rows = self.stats_service.get_department_rows(db)
            course_rows = self.stats_service.get_course_stats(db)
            employee_rows = self.stats_service.get_employee_stats(db)
            problem_rows = self.stats_service.get_problem_employees(db)

            sections = [
                {
                    "name": "СВОДКА",
                    "headers": ["Показатель", "Значение"],
                    "rows": [
                        ["Обучается", summary["learning_count"]],
                        ["Сотрудников", summary["employees"]],
                        ["Руководителей", summary["managers"]],
                        ["Активных курсов", summary["active_courses"]],
                        ["Средний прогресс", _pct(summary["avg_progress"])],
                        ["Успеваемость", _pct(summary["pass_rate"])],
                        ["Назначений", summary["assigned_count"]],
                        ["Завершено на 100%", summary["completed_count"]],
                    ],
                },
                {
                    "name": "СТАТИСТИКА ПО ОТДЕЛАМ",
                    "headers": [
                        "Отдел", "Сотрудников", "Обучается", "Курсов",
                        "Прогресс", "Успеваемость",
                    ],
                    "rows": [
                        [
                            row["department_name"],
                            row["employees"],
                            row["learning_count"],
                            row["courses"],
                            _pct(row["avg_progress"]),
                            _pct(row["pass_rate"]),
                        ]
                        for row in dept_rows
                    ],
                },
                {
                    "name": "СТАТИСТИКА ПО КУРСАМ",
                    "headers": [
                        "Курс", "Отдел", "Назначено", "Сдано", "Завершено", "Ср. прогресс",
                    ],
                    "rows": [
                        [
                            row["title"],
                            row["department_name"],
                            row["assigned"],
                            _ratio(row["passed"], row["assigned"]),
                            _ratio(row["completed"], row["assigned"]),
                            _pct(row["avg_progress"]),
                        ]
                        for row in course_rows
                    ],
                },
                {
                    "name": "РЕЙТИНГ СОТРУДНИКОВ",
                    "headers": [
                        "ФИО", "Должность", "Отдел", "Курсов", "Прогресс", "Оценка",
                    ],
                    "rows": [
                        [
                            row["full_name"],
                            row["position"],
                            row["department_name"],
                            row["assigned_courses"],
                            _pct(row["progress"]),
                            row["performance"],
                        ]
                        for row in employee_rows
                    ],
                },
                {
                    "name": "НУЖНА ПОМОЩЬ",
                    "headers": ["ФИО", "Отдел", "Прогресс", "Оценка", "Курсов"],
                    "rows": [
                        [
                            row["full_name"],
                            row["department_name"],
                            _pct(row["progress"]),
                            row["performance"],
                            row["assigned_courses"],
                        ]
                        for row in problem_rows
                    ],
                },
            ]

            save_csv_report(
                file_path,
                "LearnMate Core — общий отчёт по клинике",
                actor.full_name,
                sections,
            )

    def export_department_report(self, actor_id, file_path):
        with self.db_manager.session_scope() as db:
            actor, department = self._require_department_head(db, actor_id)
            dept_id = actor.department_id
            summary = self.stats_service.get_department_summary(db, dept_id)
            course_rows = self.stats_service.get_course_stats(db, department_id=dept_id)
            employee_rows = self.stats_service.get_employee_stats(db, department_id=dept_id)
            problem_rows = self.stats_service.get_problem_employees(db, department_id=dept_id)

            sections = [
                {
                    "name": f"СВОДКА: {department.name}",
                    "headers": ["Показатель", "Значение"],
                    "rows": [
                        ["Сотрудников", summary["employees"]],
                        ["Обучается", summary["learning_count"]],
                        ["Активных курсов", summary["active_courses"]],
                        ["Средний прогресс", _pct(summary["avg_progress"])],
                        ["Успеваемость", _pct(summary["pass_rate"])],
                        ["Нужна помощь", summary["need_help_count"]],
                        ["Назначений", summary["assigned_count"]],
                        ["Завершено на 100%", summary["completed_count"]],
                    ],
                },
                {
                    "name": "СТАТИСТИКА ПО КУРСАМ",
                    "headers": [
                        "Курс", "Назначено", "Сдано", "Завершено", "Ср. прогресс",
                    ],
                    "rows": [
                        [
                            row["title"],
                            row["assigned"],
                            _ratio(row["passed"], row["assigned"]),
                            _ratio(row["completed"], row["assigned"]),
                            _pct(row["avg_progress"]),
                        ]
                        for row in course_rows
                    ],
                },
                {
                    "name": "РЕЙТИНГ СОТРУДНИКОВ",
                    "headers": ["ФИО", "Должность", "Курсов", "Прогресс", "Оценка"],
                    "rows": [
                        [
                            row["full_name"],
                            row["position"],
                            row["assigned_courses"],
                            _pct(row["progress"]),
                            row["performance"],
                        ]
                        for row in employee_rows
                    ],
                },
                {
                    "name": "НУЖНА ПОМОЩЬ",
                    "headers": ["ФИО", "Должность", "Прогресс", "Оценка", "Курсов"],
                    "rows": [
                        [
                            row["full_name"],
                            row["position"],
                            _pct(row["progress"]),
                            row["performance"],
                            row["assigned_courses"],
                        ]
                        for row in problem_rows
                    ],
                },
            ]

            save_csv_report(
                file_path,
                f"LearnMate Core — отчёт по отделу «{department.name}»",
                actor.full_name,
                sections,
            )

    def _require_admin(self, db, actor_id):
        actor = db.query(User).filter(User.id == actor_id).first()
        if not actor:
            raise ValueError("Пользователь не найден")
        if not actor.is_role("main_admin"):
            raise PermissionError("Недостаточно прав для общего отчёта")
        return actor

    def _require_department_head(self, db, actor_id):
        actor = (
            db.query(User)
            .options(joinedload(User.department))
            .filter(User.id == actor_id)
            .first()
        )
        if not actor:
            raise ValueError("Пользователь не найден")
        if not actor.is_role("department_head"):
            raise PermissionError("Недостаточно прав для отчёта по отделу")
        department = actor.department
        if not department:
            raise ValueError("Отдел пользователя не найден")
        return actor, department
