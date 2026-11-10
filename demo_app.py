"""Тестовий застосунок (студенти / дисципліни / оцінки) для перевірки auth.py.
У своїй роботі інтегруйте init_auth(app, get_db) та @login_required у застосунок з ЛР №6."""
import os
import sqlite3
from flask import Flask, abort, g, redirect, render_template_string, request, url_for
import auth
from auth import init_auth, login_required

DB_PATH = os.environ.get("LAB_DB", "demo.db")
if os.environ.get("LAB_TTL"):
    auth.SESSION_TTL = int(os.environ["LAB_TTL"])
app = Flask(__name__)


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


init_auth(app, get_db)

PAGE = """<!doctype html><meta charset="utf-8"><title>Оцінки</title>
{% include '_auth_nav.html' %}
<h1>Оцінки</h1>
<table border="1">{% for r in rows %}<tr><td>{{ r['id'] }}</td><td>{{ r['student'] }}</td>
<td>{{ r['discipline'] }}</td><td>{{ r['value'] }}</td>
<td>{% if g.user %}<form method="post" action="{{ url_for('edit_grade', grade_id=r['id']) }}">
<input type="hidden" name="csrf_token" value="{{ csrf_token }}">
<input name="value" value="{{ r['value'] }}" size="3"><button>Зберегти</button></form>
<form method="post" action="{{ url_for('delete_grade', grade_id=r['id']) }}">
<input type="hidden" name="csrf_token" value="{{ csrf_token }}"><button>Видалити</button></form>{% endif %}</td></tr>
{% endfor %}</table>
{% if g.user %}<form method="post" action="{{ url_for('add_grade') }}">
<input type="hidden" name="csrf_token" value="{{ csrf_token }}">
<input name="student_id" placeholder="id студента"><input name="discipline_id" placeholder="id дисципліни">
<input name="value" placeholder="оцінка"><button>Додати</button></form>{% endif %}"""


@app.route("/")
def index():
    rows = get_db().execute(
        "SELECT g.id, s.name AS student, d.name AS discipline, g.value FROM grades g "
        "JOIN students s ON s.id = g.student_id JOIN disciplines d ON d.id = g.discipline_id "
        "ORDER BY g.id").fetchall()
    return render_template_string(PAGE, rows=rows)


def valid_value(v):
    try:
        v = int(v)
    except (TypeError, ValueError):
        return None
    return v if 0 <= v <= 100 else None


@app.route("/grades/add", methods=["GET", "POST"])
@login_required
def add_grade():
    if request.method == "GET":
        return render_template_string("<p>Форма додавання оцінки</p>")
    db = get_db()
    value = valid_value(request.form.get("value"))
    if value is None:
        abort(400)
    try:
        db.execute("INSERT INTO grades (student_id, discipline_id, value) VALUES (?, ?, ?)",
                   (request.form.get("student_id"), request.form.get("discipline_id"), value))
        db.commit()
    except sqlite3.Error:
        db.rollback()
        abort(400)
    return redirect(url_for("index"), code=303)


@app.route("/grades/<int:grade_id>/edit", methods=["GET", "POST"])
@login_required
def edit_grade(grade_id):
    if request.method == "GET":
        return render_template_string("<p>Форма редагування оцінки {{ i }}</p>", i=grade_id)
    db = get_db()
    value = valid_value(request.form.get("value"))
    if value is None:
        abort(400)
    cur = db.execute("UPDATE grades SET value = ? WHERE id = ?", (value, grade_id))
    db.commit()
    if cur.rowcount == 0:
        abort(404)
    return redirect(url_for("index"), code=303)


@app.post("/grades/<int:grade_id>/delete")
@login_required
def delete_grade(grade_id):
    db = get_db()
    cur = db.execute("DELETE FROM grades WHERE id = ?", (grade_id,))
    db.commit()
    if cur.rowcount == 0:
        abort(404)
    return redirect(url_for("index"), code=303)


if __name__ == "__main__":
    app.run(port=int(os.environ.get("LAB_PORT", 5000)), debug=False)
