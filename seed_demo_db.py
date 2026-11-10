"""Створює тестову БД demo.db (студенти, дисципліни, оцінки) і користувачів."""
import os, sqlite3
from werkzeug.security import generate_password_hash
path = os.environ.get("LAB_DB", "demo.db")
if os.path.exists(path):
    os.remove(path)
db = sqlite3.connect(path)
db.executescript("""
CREATE TABLE students (id INTEGER PRIMARY KEY, name TEXT NOT NULL);
CREATE TABLE disciplines (id INTEGER PRIMARY KEY, name TEXT NOT NULL);
CREATE TABLE grades (id INTEGER PRIMARY KEY, student_id INTEGER NOT NULL REFERENCES students(id),
  discipline_id INTEGER NOT NULL REFERENCES disciplines(id), value INTEGER NOT NULL);
CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL);
INSERT INTO students (name) VALUES ('Іваненко Олена'),('Петренко Андрій'),('Коваль Марія');
INSERT INTO disciplines (name) VALUES ('Вебтехнології'),('Бази даних');
INSERT INTO grades (student_id, discipline_id, value) VALUES (1,1,90),(2,1,75),(3,2,82);
""")
for u, p in [("teacher1", "ChangeMe#1"), ("викладач", "ChangeMe#2"), ("admin", "ChangeMe#3")]:
    db.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)",
               (u, generate_password_hash(p, method="scrypt")))
db.commit()
