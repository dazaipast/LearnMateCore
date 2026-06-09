import shutil
import uuid
from pathlib import Path

from sqlalchemy.orm import joinedload

from constants import PRACTICE_COURSE_TYPE, QUIZ_FILE_EXTENSION
from models import User, Course, CourseMaterial, AuditLog
from quiz_parser import parse_quiz_file, quiz_to_json, quiz_from_json, quiz_public_view
from utils import (
    validate_material_file,
    material_extension,
    course_module_count,
    validate_module_count,
    validate_module_index,
)


class MaterialService:
    def __init__(self, db_manager):
        self.db_manager = db_manager

    def can_manage_materials(self, actor, course):
        if not course.is_active:
            return False
        if actor.is_role('main_admin'):
            return True
        if actor.is_role('department_head'):
            return course.department_id == actor.department_id
        return False

    def can_view_materials(self, actor, course, db):
        if actor.is_role('main_admin'):
            return True
        if actor.is_role('department_head'):
            return course.department_id == actor.department_id
        if actor.is_role('employee'):
            from models import UserCourse
            return db.query(UserCourse).filter(
                UserCourse.user_id == actor.id,
                UserCourse.course_id == course.id,
            ).first() is not None
        return False

    def _get_course(self, db, course_id):
        course = (
            db.query(Course)
            .options(joinedload(Course.department))
            .filter(Course.id == course_id)
            .first()
        )
        if not course:
            raise ValueError("Курс не найден")
        return course

    def _course_materials_dir(self, course_id):
        path = self.db_manager.materials_dir / str(course_id)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _serialize_material(self, item):
        question_count = 0
        if item.content_kind == "quiz" and item.quiz_data:
            question_count = len(quiz_from_json(item.quiz_data))
        display_name = item.original_name
        if item.content_kind == "quiz":
            display_name = f"Тест ({question_count} вопр.)"
        return {
            "id": item.id,
            "module_index": item.module_index,
            "original_name": item.original_name,
            "display_name": display_name,
            "file_size": item.file_size,
            "content_kind": item.content_kind,
            "question_count": question_count,
            "created_at": item.created_at,
            "uploaded_by": item.uploaded_by.full_name if item.uploaded_by else "—",
        }

    def _build_modules_payload(self, course, materials):
        by_module = {item.module_index: item for item in materials}
        modules = []
        for module_index in range(1, course_module_count(course) + 1):
            item = by_module.get(module_index)
            modules.append({
                "module_index": module_index,
                "material": self._serialize_material(item) if item else None,
            })
        return modules

    def list_materials(self, actor_id, course_id, module_index=None, db=None):
        if db is not None:
            return self._serialize_materials(db, actor_id, course_id, module_index)
        with self.db_manager.session_scope() as db:
            return self._serialize_materials(db, actor_id, course_id, module_index)

    def _serialize_materials(self, db, actor_id, course_id, module_index=None):
        actor = db.query(User).filter(User.id == actor_id).first()
        course = self._get_course(db, course_id)
        if not actor:
            raise ValueError("Пользователь не найден")
        if not self.can_view_materials(actor, course, db):
            raise PermissionError("Нет доступа к материалам этого курса")

        query = (
            db.query(CourseMaterial)
            .options(joinedload(CourseMaterial.uploaded_by))
            .filter(CourseMaterial.course_id == course_id)
            .order_by(CourseMaterial.module_index)
        )
        if module_index is not None:
            validate_module_index(module_index, course_module_count(course))
            query = query.filter(CourseMaterial.module_index == module_index)

        materials = query.all()
        modules = self._build_modules_payload(course, materials)
        attached_count = sum(1 for row in modules if row["material"])

        payload = {
            "course_id": course.id,
            "course_title": course.title,
            "course_type": course.course_type,
            "is_practice": course.course_type == PRACTICE_COURSE_TYPE,
            "module_count": course_module_count(course),
            "attached_count": attached_count,
            "can_manage": self.can_manage_materials(actor, course),
            "modules": modules,
        }
        if module_index is not None:
            row = next(
                (item for item in modules if item["module_index"] == module_index),
                None,
            )
            payload["current_module"] = row
        return payload

    def _remove_material_record(self, db, material, actor, course):
        file_path = self._course_materials_dir(course.id) / material.stored_name
        db.delete(material)
        db.add(AuditLog(
            user_id=actor.id,
            department_id=course.department_id,
            action="delete_course_material",
            details=(
                f"Курс: {course.title} | этап {material.module_index} | "
                f"файл: {material.original_name}"
            ),
        ))
        db.commit()
        if file_path.exists():
            file_path.unlink()
        return file_path

    def _get_module_quiz_material(self, db, course_id, module_index):
        return (
            db.query(CourseMaterial)
            .filter(
                CourseMaterial.course_id == course_id,
                CourseMaterial.module_index == module_index,
                CourseMaterial.content_kind == "quiz",
            )
            .first()
        )

    def get_module_quiz(self, actor_id, course_id, module_index):
        with self.db_manager.session_scope() as db:
            actor = db.query(User).filter(User.id == actor_id).first()
            course = self._get_course(db, course_id)
            if not actor:
                raise ValueError("Пользователь не найден")
            if not self.can_view_materials(actor, course, db):
                raise PermissionError("Нет доступа к тесту")

            module_index = validate_module_index(
                module_index, course_module_count(course)
            )
            material = self._get_module_quiz_material(db, course_id, module_index)
            if not material or not material.quiz_data:
                return {"has_quiz": False, "questions": [], "question_count": 0}

            questions = quiz_from_json(material.quiz_data)
            return {
                "has_quiz": True,
                "questions": quiz_public_view(questions),
                "question_count": len(questions),
            }

    def get_module_quiz_answers(self, db, course_id, module_index):
        material = self._get_module_quiz_material(db, course_id, module_index)
        if not material or not material.quiz_data:
            return None
        return quiz_from_json(material.quiz_data)

    def add_material(self, actor_id, course_id, module_index, source_path):
        source = Path(source_path)
        file_size = validate_material_file(source)

        with self.db_manager.session_scope() as db:
            actor = db.query(User).filter(User.id == actor_id).first()
            course = self._get_course(db, course_id)
            if not actor:
                raise ValueError("Пользователь не найден")
            if not self.can_manage_materials(actor, course):
                raise PermissionError("Недостаточно прав для добавления материалов")

            module_index = validate_module_index(
                module_index, course_module_count(course)
            )
            existing = (
                db.query(CourseMaterial)
                .filter(
                    CourseMaterial.course_id == course_id,
                    CourseMaterial.module_index == module_index,
                )
                .first()
            )

            is_practice = course.course_type == PRACTICE_COURSE_TYPE
            content_kind = "file"
            quiz_data = None
            if is_practice:
                if material_extension(source) != QUIZ_FILE_EXTENSION:
                    raise ValueError(
                        "Для курса типа «Практика» прикрепите файл Word (.docx) "
                        "с вопросами и ответами"
                    )
                questions = parse_quiz_file(source)
                content_kind = "quiz"
                quiz_data = quiz_to_json(questions)

            stored_name = f"{uuid.uuid4().hex}{material_extension(source)}"
            target_path = self._course_materials_dir(course_id) / stored_name

            if existing:
                old_path = self._course_materials_dir(course_id) / existing.stored_name
                db.delete(existing)
                db.flush()
                if old_path.exists():
                    old_path.unlink()

            material = CourseMaterial(
                course_id=course.id,
                module_index=module_index,
                original_name=source.name,
                stored_name=stored_name,
                file_size=file_size,
                content_kind=content_kind,
                quiz_data=quiz_data,
                uploaded_by_id=actor.id,
            )
            db.add(material)
            db.flush()

            try:
                shutil.copy2(source, target_path)
            except OSError as exc:
                raise ValueError(f"Не удалось сохранить файл: {exc}") from exc

            if content_kind == "quiz":
                question_count = len(quiz_from_json(quiz_data))
                details = (
                    f"Курс: {course.title} | этап {module_index} | "
                    f"тест: {material.original_name} | вопросов: {question_count}"
                )
            else:
                details = (
                    f"Курс: {course.title} | этап {module_index} | "
                    f"файл: {material.original_name} | размер: {file_size} байт"
                )
            db.add(AuditLog(
                user_id=actor.id,
                department_id=course.department_id,
                action="add_course_material",
                details=details,
            ))
            db.commit()
            return material.id

    def delete_material(self, actor_id, material_id):
        with self.db_manager.session_scope() as db:
            actor = db.query(User).filter(User.id == actor_id).first()
            material = (
                db.query(CourseMaterial)
                .options(joinedload(CourseMaterial.course))
                .filter(CourseMaterial.id == material_id)
                .first()
            )
            if not actor or not material:
                raise ValueError("Материал не найден")

            course = material.course
            if not course or not self.can_manage_materials(actor, course):
                raise PermissionError("Недостаточно прав для удаления материала")

            self._remove_material_record(db, material, actor, course)

    def delete_material_for_module(self, actor_id, course_id, module_index):
        with self.db_manager.session_scope() as db:
            actor = db.query(User).filter(User.id == actor_id).first()
            course = self._get_course(db, course_id)
            if not actor:
                raise ValueError("Пользователь не найден")
            if not self.can_manage_materials(actor, course):
                raise PermissionError("Недостаточно прав для удаления материала")

            module_index = validate_module_index(
                module_index, course_module_count(course)
            )
            material = (
                db.query(CourseMaterial)
                .filter(
                    CourseMaterial.course_id == course_id,
                    CourseMaterial.module_index == module_index,
                )
                .first()
            )
            if not material:
                raise ValueError("Для этого этапа материал не прикреплён")
            self._remove_material_record(db, material, actor, course)

    def get_material_path(self, actor_id, material_id):
        with self.db_manager.session_scope() as db:
            actor = db.query(User).filter(User.id == actor_id).first()
            material = (
                db.query(CourseMaterial)
                .options(joinedload(CourseMaterial.course))
                .filter(CourseMaterial.id == material_id)
                .first()
            )
            if not actor or not material or not material.course:
                raise ValueError("Материал не найден")
            if not self.can_view_materials(actor, material.course, db):
                raise PermissionError("Нет доступа к этому материалу")

            file_path = self._course_materials_dir(material.course_id) / material.stored_name
            if not file_path.is_file():
                raise ValueError("Файл материала не найден на диске")
            return file_path

    def get_module_material_path(self, actor_id, course_id, module_index):
        payload = self.list_materials(actor_id, course_id, module_index=module_index)
        row = payload.get("current_module")
        if not row or not row.get("material"):
            raise ValueError("Для этого этапа материал не прикреплён")
        return self.get_material_path(actor_id, row["material"]["id"])

    def update_module_count(self, actor_id, course_id, module_count):
        module_count = validate_module_count(module_count)

        with self.db_manager.session_scope() as db:
            actor = db.query(User).filter(User.id == actor_id).first()
            course = self._get_course(db, course_id)
            if not actor:
                raise ValueError("Пользователь не найден")
            if not self.can_manage_materials(actor, course):
                raise PermissionError("Недостаточно прав для изменения курса")

            old_count = course_module_count(course)
            if module_count == old_count:
                return module_count

            if module_count < old_count:
                extras = (
                    db.query(CourseMaterial)
                    .filter(
                        CourseMaterial.course_id == course_id,
                        CourseMaterial.module_index > module_count,
                    )
                    .all()
                )
                for material in extras:
                    file_path = self._course_materials_dir(course_id) / material.stored_name
                    db.delete(material)
                    if file_path.exists():
                        file_path.unlink()

            course.module_count = module_count
            db.add(AuditLog(
                user_id=actor.id,
                department_id=course.department_id,
                action="update_course",
                details=(
                    f"Курс: {course.title} | этапов: {old_count} → {module_count}"
                ),
            ))
            db.commit()
            return module_count

    def count_materials(self, course_id, db):
        return (
            db.query(CourseMaterial)
            .filter(CourseMaterial.course_id == course_id)
            .count()
        )
