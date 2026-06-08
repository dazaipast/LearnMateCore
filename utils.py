import csv
from datetime import datetime

from sqlalchemy import func

from constants import MODULES_PER_COURSE, AUDIT_ACTION_LABELS, EVENT_ACTION_ICONS
from models import User, UserCourse, Department


def format_percent(value):
    return f"{round(value or 0):.0f}%"


def avg_progress(values):
    return sum(values) / len(values) if values else 0.0


def query_avg_progress(db, user_ids=None, department_id=None):
    query = db.query(func.avg(UserCourse.progress)).join(User, User.id == UserCourse.user_id)
    if user_ids is not None:
        query = query.filter(UserCourse.user_id.in_(user_ids))
    if department_id is not None:
        query = query.filter(User.department_id == department_id, User.is_active.is_(True))
    return float(query.scalar() or 0)


def query_user_progress_map(db, user_ids):
    if not user_ids:
        return {}
    rows = (
        db.query(UserCourse.user_id, func.avg(UserCourse.progress))
        .filter(UserCourse.user_id.in_(user_ids))
        .group_by(UserCourse.user_id)
        .all()
    )
    return {user_id: float(progress) for user_id, progress in rows}


def split_employee_progress(user_courses):
    adapt, know, skill = [], [], []
    for uc in user_courses:
        title = (uc.course.title if uc.course else "").lower()
        if "адаптация" in title:
            adapt.append(uc.progress)
        elif any(keyword in title for keyword in ("услуг", "битрикс", "знан")):
            know.append(uc.progress)
        else:
            skill.append(uc.progress)
    return int(avg_progress(adapt)), int(avg_progress(know)), int(avg_progress(skill))


def course_module_count(_course=None):
    return MODULES_PER_COURSE


def module_progress_step(module_count=None):
    count = module_count or MODULES_PER_COURSE
    return 100.0 / count


def current_module_index(progress, module_count=None):
    count = module_count or MODULES_PER_COURSE
    if progress >= 100:
        return count
    return min(count, int(progress / module_progress_step(count)) + 1)


def modules_completed(progress, module_count=None):
    count = module_count or MODULES_PER_COURSE
    if progress >= 100:
        return count
    return int(progress / module_progress_step(count))


def build_module_content(course, module_index, module_count):
    description = (course.description or "Изучите материалы курса.").strip()
    topics = [
        "Введение и цели обучения",
        "Теоретическая часть",
        "Практические примеры",
        "Типовые ситуации и ошибки",
        "Итоговое закрепление",
    ]
    topic = topics[(module_index - 1) % len(topics)]
    return (
        f"Модуль {module_index} из {module_count}: {topic}\n\n"
        f"{description}\n\n"
        f"Задание: изучите материал и нажмите «Завершить модуль», "
        f"чтобы перейти к следующему этапу."
    )


def employee_performance_label(progress):
    value = float(progress or 0)
    if value >= 95:
        return "отличник"
    if value >= 80:
        return "хорошо"
    if value >= 65:
        return "нормально"
    if value > 0:
        return "нужна помощь"
    return "не начал"


def format_ratio(passed, total):
    return f"{passed}/{total}"


def course_pass_status(progress, pass_threshold):
    if progress >= 100:
        return "Завершён"
    if progress >= pass_threshold:
        return "Сдан"
    if progress > 0:
        return "В процессе"
    return "Не начат"


def format_audit_timestamp(value):
    if not value:
        return "—"
    return value.strftime("%d.%m.%Y %H:%M")


def format_history_date(value):
    if not value:
        return "—"
    return value.strftime("%d.%m.%Y")


def audit_action_label(action):
    return AUDIT_ACTION_LABELS.get(action, action)


def format_event_line(entry):
    icon = EVENT_ACTION_ICONS.get(entry["action"], "•")
    timestamp = format_audit_timestamp(entry.get("created_at"))
    label = audit_action_label(entry["action"]).lower()
    details = entry.get("details") or ""
    if details:
        text = f"{icon} [{timestamp}] {entry['user_name']}: {label} — {details}"
    else:
        text = f"{icon} [{timestamp}] {entry['user_name']}: {label}"
    return text


def save_csv_report(file_path, title, actor_name, sections):
    """Сохраняет отчёт в CSV (UTF-8 с BOM, разделитель ';' для Excel в RU)."""
    with open(file_path, "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow([title])
        writer.writerow([f"Сформирован: {datetime.now().strftime('%d.%m.%Y %H:%M')}"])
        writer.writerow([f"Пользователь: {actor_name}"])
        writer.writerow([])

        for section in sections:
            writer.writerow([section["name"]])
            writer.writerow(section["headers"])
            for row in section["rows"]:
                writer.writerow(row)
            writer.writerow([])


def load_departments_for_actor(db, actor_user, fixed_department_id=None):
    if fixed_department_id:
        query = db.query(Department).filter(Department.id == fixed_department_id)
    elif actor_user.is_role('department_head'):
        query = db.query(Department).filter(Department.id == actor_user.department_id)
    else:
        query = db.query(Department).order_by(Department.name)
    return query.all()
