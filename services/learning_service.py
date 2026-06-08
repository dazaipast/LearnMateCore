from sqlalchemy.orm import joinedload

from models import User, Course, UserCourse
from utils import (
    course_pass_status,
    current_module_index,
    course_module_count,
)


class LearningService:
    def __init__(self, db_manager):
        self.db_manager = db_manager

    def _get_employee(self, db, actor_id):
        actor = db.query(User).filter(User.id == actor_id).first()
        if not actor:
            raise ValueError("Пользователь не найден")
        if not actor.is_role('employee'):
            raise PermissionError("Доступно только сотрудникам")
        return actor

    def _get_enrollments(self, db, actor_id, active_only=False):
        self._get_employee(db, actor_id)
        query = (
            db.query(UserCourse)
            .options(joinedload(UserCourse.course))
            .join(Course, UserCourse.course_id == Course.id)
            .filter(UserCourse.user_id == actor_id)
            .order_by(UserCourse.assigned_at.desc())
        )
        if active_only:
            query = query.filter(Course.is_active.is_(True))
        return query.all()

    def get_learning_history(self, actor_id, db=None):
        if db is not None:
            return self._serialize_history(self._get_enrollments(db, actor_id))
        with self.db_manager.session_scope() as db:
            return self._serialize_history(self._get_enrollments(db, actor_id))

    def get_today_tasks(self, actor_id, db=None):
        if db is not None:
            return self._build_today_tasks(self._get_enrollments(db, actor_id, active_only=True))
        with self.db_manager.session_scope() as db:
            return self._build_today_tasks(self._get_enrollments(db, actor_id, active_only=True))

    def get_recommendations(self, actor_id, db=None):
        if db is not None:
            return self._build_recommendations(self._get_enrollments(db, actor_id, active_only=True))
        with self.db_manager.session_scope() as db:
            return self._build_recommendations(self._get_enrollments(db, actor_id, active_only=True))

    def _serialize_history(self, enrollments):
        rows = []
        for enrollment in enrollments:
            course = enrollment.course
            if not course:
                continue
            progress = float(enrollment.progress or 0)
            rows.append({
                "course_id": course.id,
                "title": course.title,
                "assigned_at": enrollment.assigned_at,
                "started_at": enrollment.started_at,
                "completed_at": enrollment.completed_at,
                "progress": progress,
                "status": course_pass_status(progress, course.pass_threshold),
                "is_active": course.is_active,
            })
        return rows

    def _build_today_tasks(self, enrollments):
        tasks = []
        for enrollment in enrollments:
            course = enrollment.course
            if not course:
                continue
            progress = float(enrollment.progress or 0)
            title = course.title
            if progress >= 100:
                continue
            if progress == 0:
                tasks.append({
                    "kind": "start",
                    "text": f"Начать курс: «{title}» (~{min(course.deadline_days, 30)} мин)",
                })
                continue

            module_no = current_module_index(progress, course_module_count(course))
            tasks.append({
                "kind": "module",
                "text": (
                    f"Модуль {module_no}: «{title}» "
                    f"(прогресс {progress:.0f}%, ~15 мин)"
                ),
            })
            if progress >= course.pass_threshold:
                tasks.append({
                    "kind": "test",
                    "text": f"Итоговое закрепление: «{title}» (~10 мин)",
                })

        if not tasks:
            return [{
                "kind": "done",
                "text": "На сегодня активных заданий нет — можно повторить пройденные материалы.",
            }]
        return tasks[:3]

    def _build_recommendations(self, enrollments):
        recommendations = []
        in_progress = []
        not_started = []
        completed = []

        for enrollment in enrollments:
            course = enrollment.course
            if not course:
                continue
            progress = float(enrollment.progress or 0)
            title = course.title
            if progress >= 100:
                completed.append(title)
            elif progress == 0:
                not_started.append(title)
            elif progress < course.pass_threshold:
                in_progress.append((title, progress, course.pass_threshold))
            else:
                recommendations.append({
                    "kind": "good",
                    "text": (
                        f"Хороший темп по курсу «{title}» — осталось завершить "
                        f"последние модули."
                    ),
                })

        for title, progress, threshold in sorted(in_progress, key=lambda row: row[1]):
            recommendations.append({
                "kind": "repeat",
                "text": (
                    f"Повторите материал курса «{title}» — прогресс {progress:.0f}% "
                    f"(нужно {threshold}%)."
                ),
            })

        for title in not_started[:2]:
            recommendations.append({
                "kind": "start",
                "text": f"Вам назначен курс «{title}» — начните обучение как можно скорее.",
            })

        if completed:
            recommendations.append({
                "kind": "praise",
                "text": f"Отлично справляетесь! Завершён курс «{completed[0]}».",
            })
        elif enrollments and not recommendations:
            recommendations.append({
                "kind": "praise",
                "text": "Вы стабильно проходите обучение — продолжайте в том же темпе!",
            })

        if not recommendations:
            recommendations.append({
                "kind": "info",
                "text": "Рекомендации появятся после назначения курсов руководителем.",
            })

        return recommendations[:4]
