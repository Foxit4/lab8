"""Одноразове створення таблиці users і тестових облікових записів.
Запуск:  python create_users.py  (перед цим зробіть копію БД!)
Змініть DB_PATH і паролі на свої."""
import sqlite3
from werkzeug.security import check_password_hash, generate_password_hash

DB_PATH = "database.db"  # <-- шлях до вашої навчальної БД
USERS = [
    ("teacher1", "ChangeMe#1"),
    ("teacher2", "ChangeMe#2"),
    ("admin", "ChangeMe#3"),
]

db = sqlite3.connect(DB_PATH)
db.execute("""CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL)""")
for username, password in USERS:
    h = generate_password_hash(password, method="scrypt")
    assert check_password_hash(h, password)
    try:
        db.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)",
                   (username.strip(), h))
    except sqlite3.IntegrityError:
        print("Уже існує:", username)
db.commit()
for row in db.execute("SELECT id, username, substr(password_hash, 1, 28) FROM users"):
    print(row)
db.close()
