from sqlalchemy.orm import joinedload

from constants import (
    ROLE_NAMES,
    MAIN_ADMIN_ROLE_ID,
    DEPT_HEAD_ROLE_ID,
    EMPLOYEE_ROLE_ID,
    MIN_PASSWORD_LENGTH,
)
from models import User, Department, Course, UserCourse, AuditLog


class UserService:
    def __init__(self, db_manager):
        self.db_manager = db_manager

    def can_create(self, actor, role_id, department_id):
        if actor.is_role('main_admin'):
            return True
        if actor.is_role('department_head'):
            return role_id == EMPLOYEE_ROLE_ID and department_id == actor.department_id
        return False

    def create_user(self, actor_id, full_name, email, password, position, department_id, role_id):
        full_name = full_name.strip()
        email = email.strip().lower()
        position = position.strip()

        if not full_name or not email or not position or not password:
            raise ValueError("Заполните все обязательные поля")
        if len(password) < MIN_PASSWORD_LENGTH:
            raise ValueError(f"Пароль должен быть не короче {MIN_PASSWORD_LENGTH} символов")
        if "@" not in email:
            raise ValueError("Введите корректный email")

        with self.db_manager.session_scope() as db:
            actor = db.query(User).filter(User.id == actor_id).first()
            if not actor:
                raise ValueError("Текущий пользователь не найден")
            if not self.can_create(actor, role_id, department_id):
                raise PermissionError("Недостаточно прав для создания этого пользователя")

            department = db.query(Department).filter(Department.id == department_id).first()
            if not department:
                raise ValueError("Отдел не найден")
            if db.query(User).filter(User.email == email).first():
                raise ValueError("Пользователь с таким email уже существует")

            user = User(
                full_name=full_name,
                email=email,
                position=position,
                department_id=department_id,
                role_id=role_id,
                manager_id=self._resolve_manager(db, actor, department, role_id),
            )
            user.set_password(password)
            db.add(user)
            db.flush()

            if role_id == DEPT_HEAD_ROLE_ID:
                department.head_id = user.id

            db.add(AuditLog(
                user_id=actor.id,
                department_id=department_id,
                action="create_user",
                details=(
                    f"Создан: {user.full_name} | {ROLE_NAMES[role_id]} | "
                    f"отдел: {department.name} | email: {user.email}"
                ),
            ))
            db.commit()
            return user.id

    def _resolve_manager(self, db, actor, department, role_id):
        if role_id == EMPLOYEE_ROLE_ID:
            if actor.is_role('department_head'):
                return actor.id
            if department.head_id:
                return department.head_id
        if actor.is_role('main_admin'):
            return actor.id
        return None

    def can_deactivate(self, actor, target):
        if actor.id == target.id:
            return False
        if target.role_id == MAIN_ADMIN_ROLE_ID:
            return False
        if target.role_id == EMPLOYEE_ROLE_ID:
            if actor.is_role('main_admin'):
                return True
            if actor.is_role('department_head'):
                return target.department_id == actor.department_id
            return False
        if not target.is_active:
            return False
        if actor.is_role('main_admin'):
            return True
        return False

    def can_change_department(self, actor, target):
        if not actor.is_role('main_admin'):
            return False
        if not target.is_active:
            return False
        if target.role_id == MAIN_ADMIN_ROLE_ID:
            return False
        return target.role_id in (EMPLOYEE_ROLE_ID, DEPT_HEAD_ROLE_ID)

    def deactivate_user(self, actor_id, target_user_id):
        with self.db_manager.session_scope() as db:
            actor = db.query(User).filter(User.id == actor_id).first()
            target = db.query(User).options(joinedload(User.department)).filter(
                User.id == target_user_id
            ).first()
            if not actor or not target:
                raise ValueError("Пользователь не найден")
            if not self.can_deactivate(actor, target):
                raise PermissionError("Недостаточно прав для удаления этого пользователя")

            if target.role_id == EMPLOYEE_ROLE_ID:
                self._hard_delete_employee(db, actor, target)
            else:
                target.is_active = False
                if target.role_id == DEPT_HEAD_ROLE_ID:
                    dept = db.query(Department).filter(Department.head_id == target.id).first()
                    if dept:
                        dept.head_id = None
                db.add(AuditLog(
                    user_id=actor.id,
                    department_id=target.department_id,
                    action="deactivate_user",
                    details=(
                        f"Деактивирован: {target.full_name} | {ROLE_NAMES[target.role_id]} | "
                        f"отдел: {target.department.name if target.department else '—'}"
                    ),
                ))
            db.commit()

    def _hard_delete_employee(self, db, actor, target):
        removed_courses = (
            db.query(UserCourse)
            .filter(UserCourse.user_id == target.id)
            .delete(synchronize_session=False)
        )
        db.query(AuditLog).filter(AuditLog.user_id == target.id).delete(synchronize_session=False)
        db.query(User).filter(User.manager_id == target.id).update(
            {User.manager_id: None},
            synchronize_session=False,
        )

        department_name = target.department.name if target.department else "—"
        db.add(AuditLog(
            user_id=actor.id,
            department_id=target.department_id,
            action="delete_user",
            details=(
                f"Удалён: {target.full_name} | {ROLE_NAMES[target.role_id]} | "
                f"отдел: {department_name} | снято назначений: {removed_courses}"
            ),
        ))
        db.delete(target)

    def change_department(self, actor_id, target_user_id, new_department_id):
        with self.db_manager.session_scope() as db:
            actor = db.query(User).filter(User.id == actor_id).first()
            target = (
                db.query(User)
                .options(joinedload(User.department))
                .filter(User.id == target_user_id)
                .first()
            )
            new_department = db.query(Department).filter(Department.id == new_department_id).first()
            if not actor or not target or not new_department:
                raise ValueError("Пользователь или отдел не найден")
            if not self.can_change_department(actor, target):
                raise PermissionError("Недостаточно прав для смены отдела")
            if target.department_id == new_department_id:
                raise ValueError("Пользователь уже состоит в этом отделе")

            old_department_name = target.department.name if target.department else "—"
            cancelled = self._cancel_incomplete_courses(db, target.id)

            if target.role_id == DEPT_HEAD_ROLE_ID:
                old_dept = db.query(Department).filter(Department.head_id == target.id).first()
                if old_dept:
                    old_dept.head_id = None
                new_department.head_id = target.id
                target.manager_id = actor.id
            else:
                target.manager_id = new_department.head_id or actor.id

            target.department_id = new_department_id
            assigned = self._assign_department_courses(db, target.id, new_department_id)

            db.add(AuditLog(
                user_id=actor.id,
                department_id=new_department_id,
                action="change_department",
                details=(
                    f"Перевод: {target.full_name} | {ROLE_NAMES[target.role_id]} | "
                    f"{old_department_name} → {new_department.name} | "
                    f"отменено курсов: {cancelled} | назначено курсов: {assigned}"
                ),
            ))
            db.commit()

    def _cancel_incomplete_courses(self, db, user_id):
        return (
            db.query(UserCourse)
            .filter(UserCourse.user_id == user_id, UserCourse.progress < 100)
            .delete(synchronize_session=False)
        )

    def _assign_department_courses(self, db, user_id, department_id):
        active_courses = (
            db.query(Course.id)
            .filter(Course.department_id == department_id, Course.is_active.is_(True))
            .all()
        )
        if not active_courses:
            return 0

        existing_ids = {
            row[0]
            for row in db.query(UserCourse.course_id)
            .filter(UserCourse.user_id == user_id)
            .all()
        }
        assigned = 0
        for (course_id,) in active_courses:
            if course_id not in existing_ids:
                db.add(UserCourse(user_id=user_id, course_id=course_id, progress=0.0))
                assigned += 1
        return assigned
