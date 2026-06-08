from datetime import datetime, timezone

import bcrypt
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Float
from sqlalchemy.orm import declarative_base, relationship

from constants import ROLE_CODES

Base = declarative_base()


def utc_now():
    """Возвращает текущее время в UTC с часовым поясом"""
    return datetime.now(timezone.utc)


class Department(Base):
    """Модель отдела"""
    __tablename__ = 'departments'

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    head_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    created_at = Column(DateTime, default=utc_now)

    employees = relationship("User", back_populates="department", foreign_keys="User.department_id")
    head = relationship("User", back_populates="managed_department", foreign_keys=[head_id], uselist=False)
    courses = relationship("Course", back_populates="department")


class Role(Base):
    """Модель роли"""
    __tablename__ = 'roles'

    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False, unique=True)
    code = Column(String(20), nullable=False, unique=True)
    permissions = Column(Text, default='{}')

    users = relationship("User", back_populates="role")


class User(Base):
    """Модель пользователя"""
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    full_name = Column(String(150), nullable=False)
    email = Column(String(100), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    position = Column(String(100), nullable=False)
    department_id = Column(Integer, ForeignKey('departments.id'), nullable=False)
    role_id = Column(Integer, ForeignKey('roles.id'), nullable=False)
    manager_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utc_now)
    last_login_at = Column(DateTime, nullable=True)
    b24_id = Column(Integer, nullable=True)

    department = relationship("Department", back_populates="employees", foreign_keys=[department_id])
    role = relationship("Role", back_populates="users")
    manager = relationship("User", remote_side=[id], backref="subordinates", foreign_keys=[manager_id])
    managed_department = relationship(
        "Department", back_populates="head", foreign_keys=[Department.head_id], uselist=False
    )
    created_courses = relationship("Course", back_populates="creator", foreign_keys="Course.creator_id")
    assigned_courses = relationship("UserCourse", back_populates="user")

    def set_password(self, raw_password):
        salt = bcrypt.gensalt()
        self.password_hash = bcrypt.hashpw(raw_password.encode('utf-8'), salt).decode('utf-8')

    def check_password(self, raw_password):
        return bcrypt.checkpw(raw_password.encode('utf-8'), self.password_hash.encode('utf-8'))

    def is_role(self, role_name):
        return self.role_id == ROLE_CODES.get(role_name, -1)


class Course(Base):
    """Модель курса"""
    __tablename__ = 'courses'

    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    department_id = Column(Integer, ForeignKey('departments.id'), nullable=False)
    creator_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    deadline_days = Column(Integer, default=30)
    pass_threshold = Column(Integer, default=80)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utc_now)

    department = relationship("Department", back_populates="courses")
    creator = relationship("User", back_populates="created_courses", foreign_keys=[creator_id])
    user_courses = relationship("UserCourse", back_populates="course")


class UserCourse(Base):
    """Связь пользователя и курса"""
    __tablename__ = 'user_courses'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    course_id = Column(Integer, ForeignKey('courses.id'), nullable=False)
    progress = Column(Float, default=0.0)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    assigned_at = Column(DateTime, default=utc_now)

    user = relationship("User", back_populates="assigned_courses")
    course = relationship("Course", back_populates="user_courses")


class AuditLog(Base):
    """Журнал аудита"""
    __tablename__ = 'audit_logs'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    department_id = Column(Integer, ForeignKey('departments.id'), nullable=True)
    action = Column(String(100), nullable=False)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now)

    user = relationship("User")
    department = relationship("Department")
