from models import User, AuditLog, utc_now


class AuthManager:
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self._current_user_id = None

    def authenticate(self, email, password):
        with self.db_manager.session_scope() as db:
            user = db.query(User).filter(User.email == email).first()
            if not user or not user.is_active:
                return None
            if user.check_password(password):
                user.last_login_at = utc_now()
                db.add(AuditLog(
                    user_id=user.id,
                    department_id=user.department_id,
                    action="login",
                    details=f"Вход: {user.full_name} | {user.email}",
                ))
                db.commit()
                self._current_user_id = user.id
                return {
                    'id': user.id,
                    'full_name': user.full_name,
                    'email': user.email,
                    'position': user.position,
                    'department_id': user.department_id,
                    'role_id': user.role_id,
                }
            return None

    def get_current_user(self):
        if self._current_user_id is None:
            return None
        return self.db_manager.get_user_safe(self._current_user_id)

    def get_current_user_id(self):
        return self._current_user_id

    def logout(self):
        if self._current_user_id is not None:
            with self.db_manager.session_scope() as db:
                user = db.query(User).filter(User.id == self._current_user_id).first()
                if user and user.is_active:
                    db.add(AuditLog(
                        user_id=user.id,
                        department_id=user.department_id,
                        action="logout",
                        details=f"Выход: {user.full_name} | {user.email}",
                    ))
                    db.commit()
        self._current_user_id = None
