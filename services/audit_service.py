from sqlalchemy import or_, and_, select
from sqlalchemy.orm import joinedload

from constants import AUDIT_LOG_LIMIT, EVENT_FEED_LIMIT
from models import AuditLog, User


class AuditService:
    def __init__(self, db_manager):
        self.db_manager = db_manager

    def can_view_audit(self, actor):
        return actor.is_role('main_admin') or actor.is_role('department_head')

    def _audit_query(self, db, actor):
        if not self.can_view_audit(actor):
            raise PermissionError("Недостаточно прав для просмотра журнала")

        query = (
            db.query(AuditLog)
            .options(
                joinedload(AuditLog.user).joinedload(User.department),
                joinedload(AuditLog.department),
            )
            .order_by(AuditLog.created_at.desc())
        )
        if actor.is_role('main_admin'):
            return query
        if actor.is_role('department_head'):
            dept_user_ids = select(User.id).where(
                User.department_id == actor.department_id
            )
            return query.filter(
                or_(
                    AuditLog.department_id == actor.department_id,
                    and_(
                        AuditLog.department_id.is_(None),
                        AuditLog.user_id.in_(dept_user_ids),
                    ),
                )
            )
        return query.filter(False)

    def list_logs(self, actor_id, limit=AUDIT_LOG_LIMIT, db=None):
        if db is not None:
            return self._serialize_logs(self._logs_for_actor(db, actor_id, limit))
        with self.db_manager.session_scope() as db:
            return self._serialize_logs(self._logs_for_actor(db, actor_id, limit))

    def list_recent_events(self, actor_id, limit=EVENT_FEED_LIMIT, db=None):
        if db is not None:
            return self._serialize_logs(self._logs_for_actor(db, actor_id, limit))
        with self.db_manager.session_scope() as db:
            return self._serialize_logs(self._logs_for_actor(db, actor_id, limit))

    def _logs_for_actor(self, db, actor_id, limit):
        actor = db.query(User).filter(User.id == actor_id).first()
        if not actor:
            raise ValueError("Пользователь не найден")
        return self._audit_query(db, actor).limit(limit).all()

    def _serialize_logs(self, logs):
        result = []
        for entry in logs:
            actor = entry.user
            department_name = "—"
            if entry.department:
                department_name = entry.department.name
            elif actor and actor.department:
                department_name = actor.department.name

            result.append({
                "id": entry.id,
                "created_at": entry.created_at,
                "action": entry.action,
                "details": entry.details or "",
                "user_name": actor.full_name if actor else "—",
                "department_name": department_name,
            })
        return result
