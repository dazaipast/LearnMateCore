from sqlalchemy.orm import joinedload

from constants import EMPLOYEE_ROLE_ID
from models import User, Department, Course, UserCourse, AuditLog, utc_now
from utils import (
    course_module_count,
    module_progress_step,
    current_module_index,
    modules_completed,
    course_pass_status,
)


class CourseService:
    def __init__(self, db_manager):
        self.db_manager = db_manager

    def can_create(self, actor, department_id):
        if actor.is_role('main_admin'):
            return True
        if actor.is_role('department_head'):
            return department_id == actor.department_id
        return False

    def can_view_course(self, actor, course, db):
        if actor.is_role('main_admin'):
            return True
        if actor.is_role('department_head'):
            return course.department_id == actor.department_id
        if actor.is_role('employee'):
            return db.query(UserCourse).filter(
                UserCourse.user_id == actor.id,
                UserCourse.course_id == course.id,
            ).first() is not None
        return False

    def create_course(self, actor_id, title, description, department_id, deadline_days, pass_threshold):
        title = title.strip()
        description = description.strip() if description else None

        if not title:
            raise ValueError("Введите название курса")
        if deadline_days <= 0:
            raise ValueError("Срок прохождения должен быть больше 0 дней")
        if not 1 <= pass_threshold <= 100:
            raise ValueError("Порог сдачи должен быть от 1 до 100%")

        with self.db_manager.session_scope() as db:
            actor = db.query(User).filter(User.id == actor_id).first()
            if not actor:
                raise ValueError("Текущий пользователь не найден")
            if not self.can_create(actor, department_id):
                raise PermissionError("Недостаточно прав для создания курса в этом отделе")

            department = db.query(Department).filter(Department.id == department_id).first()
            if not department:
                raise ValueError("Отдел не найден")

            course = Course(
                title=title,
                description=description,
                department_id=department_id,
                creator_id=actor.id,
                deadline_days=deadline_days,
                pass_threshold=pass_threshold,
            )
            db.add(course)
            db.flush()
            db.add(AuditLog(
                user_id=actor.id,
                department_id=department_id,
                action="create_course",
                details=(
                    f"Создан курс: {course.title} | отдел: {department.name} | "
                    f"срок: {deadline_days} дн. | порог: {pass_threshold}%"
                ),
            ))
            db.commit()
            return course.id

    def can_deactivate(self, actor, course):
        if not course.is_active:
            return False
        if actor.is_role('main_admin'):
            return True
        if actor.is_role('department_head'):
            return course.department_id == actor.department_id
        return False

    def deactivate_course(self, actor_id, course_id):
        with self.db_manager.session_scope() as db:
            actor = db.query(User).filter(User.id == actor_id).first()
            course = (
                db.query(Course)
                .options(joinedload(Course.department))
                .filter(Course.id == course_id)
                .first()
            )
            if not actor or not course:
                raise ValueError("Курс не найден")
            if not self.can_deactivate(actor, course):
                raise PermissionError("Недостаточно прав для удаления этого курса")

            course.is_active = False
            db.add(AuditLog(
                user_id=actor.id,
                department_id=course.department_id,
                action="deactivate_course",
                details=(
                    f"Удалён курс: {course.title} | "
                    f"отдел: {course.department.name if course.department else '—'}"
                ),
            ))
            db.commit()

    def can_assign_course(self, actor, course):
        if not course.is_active:
            return False
        if actor.is_role('main_admin'):
            return True
        if actor.is_role('department_head'):
            return course.department_id == actor.department_id
        return False

    def can_assign_user(self, actor, course, target_user):
        if not self.can_assign_course(actor, course):
            return False
        if not target_user.is_active or target_user.role_id != EMPLOYEE_ROLE_ID:
            return False
        if actor.is_role('main_admin'):
            return True
        if actor.is_role('department_head'):
            return target_user.department_id == actor.department_id
        return False

    def get_assignable_employees(self, actor_id, course_id):
        with self.db_manager.session_scope() as db:
            actor = db.query(User).filter(User.id == actor_id).first()
            course = (
                db.query(Course)
                .options(joinedload(Course.department))
                .filter(Course.id == course_id)
                .first()
            )
            if not actor or not course:
                raise ValueError("Курс не найден")
            if not self.can_assign_course(actor, course):
                raise PermissionError("Недостаточно прав для назначения этого курса")

            employees_query = (
                db.query(User)
                .options(joinedload(User.department))
                .filter(User.role_id == EMPLOYEE_ROLE_ID, User.is_active.is_(True))
            )
            if actor.is_role('department_head'):
                employees_query = employees_query.filter(User.department_id == actor.department_id)
            employees = employees_query.order_by(User.full_name).all()

            assigned_ids = {
                row[0]
                for row in db.query(UserCourse.user_id)
                .filter(UserCourse.course_id == course_id)
                .all()
            }

            return [
                {
                    "id": employee.id,
                    "full_name": employee.full_name,
                    "department_name": employee.department.name if employee.department else "—",
                    "assigned": employee.id in assigned_ids,
                }
                for employee in employees
            ]

    def assign_course(self, actor_id, course_id, user_ids):
        user_ids = list(dict.fromkeys(user_ids))
        if not user_ids:
            raise ValueError("Выберите хотя бы одного сотрудника")

        with self.db_manager.session_scope() as db:
            actor = db.query(User).filter(User.id == actor_id).first()
            course = (
                db.query(Course)
                .options(joinedload(Course.department))
                .filter(Course.id == course_id)
                .first()
            )
            if not actor or not course:
                raise ValueError("Курс не найден")
            if not self.can_assign_course(actor, course):
                raise PermissionError("Недостаточно прав для назначения этого курса")

            assigned_ids = {
                row[0]
                for row in db.query(UserCourse.user_id)
                .filter(UserCourse.course_id == course_id)
                .all()
            }

            assigned_users = []
            for user_id in user_ids:
                if user_id in assigned_ids:
                    continue
                target = db.query(User).filter(User.id == user_id).first()
                if not target:
                    raise ValueError("Сотрудник не найден")
                if not self.can_assign_user(actor, course, target):
                    raise PermissionError(
                        f"Нельзя назначить курс сотруднику: {target.full_name}"
                    )
                db.add(UserCourse(
                    user_id=target.id,
                    course_id=course.id,
                    progress=0.0,
                    started_at=utc_now(),
                ))
                assigned_users.append(target.full_name)

            if not assigned_users:
                raise ValueError("Выбранные сотрудники уже имеют этот курс")

            db.add(AuditLog(
                user_id=actor.id,
                department_id=course.department_id,
                action="assign_course",
                details=(
                    f"Назначен курс: {course.title} | сотрудникам: "
                    f"{', '.join(assigned_users)}"
                ),
            ))
            db.commit()
            return len(assigned_users)

    def list_courses(self, actor_id, db=None):
        if db is not None:
            actor = db.query(User).filter(User.id == actor_id).first()
            return self._courses_query(db, actor).all() if actor else []
        with self.db_manager.session_scope() as db:
            actor = db.query(User).filter(User.id == actor_id).first()
            if not actor:
                return []
            return self._courses_query(db, actor).all()

    def _get_employee_enrollment(self, db, actor, course_id):
        if not actor.is_role('employee'):
            raise PermissionError("Проходить курс могут только сотрудники")
        course = (
            db.query(Course)
            .options(joinedload(Course.department))
            .filter(Course.id == course_id, Course.is_active.is_(True))
            .first()
        )
        if not course:
            raise ValueError("Курс не найден")
        enrollment = db.query(UserCourse).filter(
            UserCourse.user_id == actor.id,
            UserCourse.course_id == course_id,
        ).first()
        if not enrollment:
            raise PermissionError("Курс вам не назначен")
        return course, enrollment

    def get_passing_state(self, actor_id, course_id):
        with self.db_manager.session_scope() as db:
            actor = db.query(User).filter(User.id == actor_id).first()
            if not actor:
                raise ValueError("Пользователь не найден")
            course, enrollment = self._get_employee_enrollment(db, actor, course_id)
            module_count = course_module_count(course)
            progress = float(enrollment.progress or 0)
            return {
                "course_id": course.id,
                "title": course.title,
                "description": course.description,
                "pass_threshold": course.pass_threshold,
                "deadline_days": course.deadline_days,
                "department_name": course.department.name if course.department else "—",
                "progress": progress,
                "started_at": enrollment.started_at,
                "completed_at": enrollment.completed_at,
                "module_count": module_count,
                "current_module": current_module_index(progress, module_count),
                "modules_completed": modules_completed(progress, module_count),
                "is_completed": progress >= 100,
                "can_advance": progress < 100,
                "status": course_pass_status(progress, course.pass_threshold),
            }

    def advance_module(self, actor_id, course_id):
        with self.db_manager.session_scope() as db:
            actor = db.query(User).filter(User.id == actor_id).first()
            if not actor:
                raise ValueError("Пользователь не найден")
            course, enrollment = self._get_employee_enrollment(db, actor, course_id)
            if enrollment.progress >= 100:
                raise ValueError("Курс уже завершён")

            module_count = course_module_count(course)
            step = module_progress_step(module_count)
            if enrollment.started_at is None:
                enrollment.started_at = utc_now()

            new_progress = min(100.0, round(float(enrollment.progress or 0) + step, 1))
            enrollment.progress = new_progress
            module_no = modules_completed(new_progress, module_count)

            if new_progress >= 100:
                enrollment.completed_at = utc_now()
                details = (
                    f"Завершён курс: {course.title} | прогресс: 100% | "
                    f"модулей: {module_count}"
                )
                action = "complete_course"
            else:
                details = (
                    f"Пройден модуль {module_no}/{module_count} курса «{course.title}» | "
                    f"прогресс: {new_progress:.0f}%"
                )
                action = "complete_module"

            db.add(AuditLog(
                user_id=actor.id,
                department_id=actor.department_id,
                action=action,
                details=details,
            ))
            db.commit()
            return new_progress

    def get_course_details(self, actor_id, course_id):
        with self.db_manager.session_scope() as db:
            actor = db.query(User).filter(User.id == actor_id).first()
            course = (
                db.query(Course)
                .options(joinedload(Course.department), joinedload(Course.creator))
                .filter(Course.id == course_id)
                .first()
            )
            if not course:
                raise ValueError("Курс не найден")
            if not self.can_view_course(actor, course, db):
                raise PermissionError("Нет доступа к этому курсу")

            progress = None
            if actor.is_role('employee'):
                user_course = db.query(UserCourse).filter(
                    UserCourse.user_id == actor.id,
                    UserCourse.course_id == course.id,
                ).first()
                progress = user_course.progress if user_course else 0.0

            db.expunge(course)
            if course.department:
                db.expunge(course.department)
            if course.creator:
                db.expunge(course.creator)
            return course, progress

    def _courses_query(self, db, actor):
        query = (
            db.query(Course)
            .options(joinedload(Course.department), joinedload(Course.creator))
            .filter(Course.is_active.is_(True))
        )
        if actor.is_role('main_admin'):
            return query.order_by(Course.title)
        if actor.is_role('department_head'):
            return query.filter(Course.department_id == actor.department_id).order_by(Course.title)
        if actor.is_role('employee'):
            return (
                query.join(UserCourse, UserCourse.course_id == Course.id)
                .filter(UserCourse.user_id == actor.id)
                .order_by(Course.title)
            )
        return query.filter(False)
