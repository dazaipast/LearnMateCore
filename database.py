from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, text, event, inspect
from sqlalchemy.orm import sessionmaker, joinedload

from models import (
    Base, Department, Role, User, Course, UserCourse, AuditLog,
)

APP_DIR = Path(__file__).resolve().parent


def _configure_sqlite_connection(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


class DatabaseManager:
    def __init__(self):
        self.db_path = APP_DIR / "learnmate_core.db"
        self.SQLALCHEMY_DATABASE_URL = f"sqlite:///{self.db_path.as_posix()}"
        self.engine = create_engine(
            self.SQLALCHEMY_DATABASE_URL,
            connect_args={"check_same_thread": False},
            echo=False,
        )
        event.listen(self.engine, "connect", _configure_sqlite_connection)

        self._run_migrations()

        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    def _run_migrations(self):
        """Применяет миграции к существующей БД"""
        if not self.db_path.exists():
            return
        try:
            inspector = inspect(self.engine)
            table_names = set(inspector.get_table_names())
            migrations = []

            if 'departments' in table_names:
                dept_columns = {col['name'] for col in inspector.get_columns('departments')}
                if 'head_id' not in dept_columns:
                    migrations.append(
                        "ALTER TABLE departments ADD COLUMN head_id INTEGER REFERENCES users(id)"
                    )

            if 'audit_logs' in table_names:
                audit_columns = {col['name'] for col in inspector.get_columns('audit_logs')}
                if 'department_id' not in audit_columns:
                    migrations.append(
                        "ALTER TABLE audit_logs ADD COLUMN department_id INTEGER "
                        "REFERENCES departments(id)"
                    )

            if not migrations:
                return

            print("Обнаружена старая версия БД. Выполняется миграция...")
            with self.engine.begin() as conn:
                for statement in migrations:
                    conn.execute(text(statement))
            print("Миграция выполнена успешно!")
        except Exception as exc:
            print(f"Ошибка миграции БД: {exc}")

    def get_session(self):
        return self.SessionLocal()

    @contextmanager
    def session_scope(self):
        db = self.get_session()
        try:
            yield db
        finally:
            db.close()

    def get_user_safe(self, user_id):
        """Безопасное получение пользователя с загрузкой всех связей"""
        db = self.get_session()
        try:
            user = db.query(User).options(
                joinedload(User.department),
                joinedload(User.role),
            ).filter(User.id == user_id).first()
            if user:
                db.expunge(user)
            return user
        finally:
            db.close()

    def init_test_data(self):
        """Инициализация тестовых данных"""
        db = self.get_session()
        try:
            if db.query(Role).count() == 0:
                roles = [
                    Role(id=1, name="Главный администратор", code="main_admin"),
                    Role(id=2, name="Руководитель подразделения", code="department_head"),
                    Role(id=3, name="Сотрудник", code="employee"),
                ]
                for role in roles:
                    db.add(role)

                departments = [
                    Department(id=1, name="Контакт-центр"),
                    Department(id=2, name="Пластическая хирургия"),
                    Department(id=3, name="Администрация ресепшен"),
                    Department(id=4, name="Терапевтическое отделение"),
                    Department(id=5, name="Лаборатория"),
                ]
                for dept in departments:
                    db.add(dept)
                db.commit()

                admin_user = User(
                    full_name="Маканина Наталья Николаевна",
                    email="n.makanina@rami-clinic.ru",
                    position="Руководитель контакт-центра",
                    department_id=1,
                    role_id=1,
                )
                admin_user.set_password("admin123")

                manager_user = User(
                    full_name="Иванов Иван Иванович",
                    email="i.ivanov@rami-clinic.ru",
                    position="Руководитель отдела сервиса и продаж",
                    department_id=2,
                    role_id=2,
                )
                manager_user.set_password("manager123")

                employee_user = User(
                    full_name="Петрова Анна Сергеевна",
                    email="a.petrova@rami-clinic.ru",
                    position="Менеджер пластической хирургии",
                    department_id=2,
                    role_id=3,
                )
                employee_user.set_password("employee123")

                db.add_all([admin_user, manager_user, employee_user])
                db.commit()

                manager_user.manager_id = admin_user.id
                employee_user.manager_id = manager_user.id

                dept1 = db.query(Department).filter(Department.id == 1).first()
                dept1.head_id = admin_user.id
                dept2 = db.query(Department).filter(Department.id == 2).first()
                dept2.head_id = manager_user.id

                courses = [
                    Course(
                        title="Адаптация оператора КЦ",
                        description="Базовое обучение",
                        department_id=1,
                        creator_id=admin_user.id,
                    ),
                    Course(
                        title="Продажи в пластической хирургии",
                        description="VIP-обслуживание",
                        department_id=2,
                        creator_id=manager_user.id,
                    ),
                    Course(
                        title="Работа с возражениями",
                        description="Техники работы",
                        department_id=2,
                        creator_id=manager_user.id,
                    ),
                ]
                for course in courses:
                    db.add(course)
                db.commit()

                courses_db = db.query(Course).all()
                if len(courses_db) >= 2:
                    user_courses = [
                        UserCourse(user_id=employee_user.id, course_id=courses_db[1].id, progress=65.0),
                        UserCourse(user_id=employee_user.id, course_id=courses_db[2].id, progress=30.0),
                    ]
                    for uc in user_courses:
                        db.add(uc)

                db.commit()
                print("Тестовые данные успешно созданы!")
        except Exception as e:
            db.rollback()
            print(f"Ошибка при создании тестовых данных: {e}")
        finally:
            db.close()
