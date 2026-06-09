# Локальный hook для SQLAlchemy 2.x (встроенный hook PyInstaller устарел).
hiddenimports = [
    "sqlalchemy.dialects.sqlite",
    "sqlalchemy.sql.default_comparator",
    "sqlalchemy.orm",
]
excludedimports = ["sqlalchemy.testing"]
