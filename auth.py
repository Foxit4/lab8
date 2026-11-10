"""Серверні сесії в пам'яті, автентифікація, CSRF та контроль доступу (ЛР №8)."""
import secrets
from functools import wraps
from threading import RLock
from time import time

from flask import abort, current_app, g, redirect, render_template, request, url_for
from werkzeug.security import check_password_hash

COOKIE_NAME = "session_id"
SESSION_TTL = 30 * 60  # абсолютний тайм-аут сесії, секунди
sessions = {}
sessions_lock = RLock()


def create_session(user_id=None):
    sid = secrets.token_urlsafe(32)
    state = {
        "user_id": user_id,
        "csrf_token": secrets.token_urlsafe(32),
        "expires_at": time() + SESSION_TTL,
    }
    with sessions_lock:
        sessions[sid] = state
    return sid, state.copy()


def remove_session(sid):
    with sessions_lock:
        sessions.pop(sid, None)


def set_session_cookie(response, sid):
    response.set_cookie(
        COOKIE_NAME, sid, max_age=SESSION_TTL, httponly=True,
        secure=current_app.config.get("SESSION_COOKIE_SECURE", False),
        samesite="Lax", path="/",
    )


def require_csrf():
    token = request.form.get("csrf_token", "")
    if (not g.auth_session or not token or not token.isascii()
            or not secrets.compare_digest(token, g.auth_session["csrf_token"])):
        abort(403)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("login"), code=303)
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            require_csrf()
        return view(*args, **kwargs)
    return wrapped


def init_auth(app, get_db):
    # Для HTTPS встановіть True
    app.config.setdefault("SESSION_COOKIE_SECURE", False)

    @app.before_request
    def load_current_user():
        g.sid = request.cookies.get(COOKIE_NAME)
        g.auth_session = None
        g.user = None
        now = time()
        with sessions_lock:
            expired = [s for s, st in sessions.items() if st["expires_at"] <= now]
            for s in expired:
                sessions.pop(s, None)
            state = sessions.get(g.sid)
            if state is not None:
                g.auth_session = state.copy()
        if g.auth_session and g.auth_session["user_id"] is not None:
            g.user = get_db().execute(
                "SELECT id, username FROM users WHERE id = ?",
                (g.auth_session["user_id"],),
            ).fetchone()
            if g.user is None:
                remove_session(g.sid)
                g.auth_session = None

    @app.context_processor
    def session_template_data():
        return {"csrf_token": g.auth_session["csrf_token"] if g.auth_session else ""}

    @app.after_request
    def prevent_sensitive_caching(response):
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "GET":
            new_sid = None
            if g.auth_session is None:
                new_sid, g.auth_session = create_session()
            response = app.make_response(render_template("login.html", error=None))
            if new_sid:
                set_session_cookie(response, new_sid)
            return response

        require_csrf()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = get_db().execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        if (not username or not password or user is None
                or not check_password_hash(user["password_hash"], password)):
            return render_template(
                "login.html", error="Неправильний логін або пароль"), 401

        remove_session(g.sid)                 # захист від session fixation
        sid, _ = create_session(user["id"])
        response = redirect(url_for("index"), code=303)
        set_session_cookie(response, sid)
        return response

    @app.post("/logout")
    @login_required
    def logout():
        remove_session(g.sid)
        response = redirect(url_for("index"), code=303)
        response.delete_cookie(
            COOKIE_NAME, path="/", httponly=True,
            secure=app.config["SESSION_COOKIE_SECURE"], samesite="Lax",
        )
        return response
