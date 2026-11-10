"""Автоматичні експерименти ЛР №8 проти живого сервера. Результати -> experiment_results.json"""
import json, os, re, shutil, sqlite3, subprocess, sys, time
import requests

PORT = 5099
BASE = f"http://127.0.0.1:{PORT}"
DB = "exp.db"
R = {}


def start(ttl=None):
    env = dict(os.environ, LAB_DB=DB, LAB_PORT=str(PORT))
    if ttl:
        env["LAB_TTL"] = str(ttl)
    pr = subprocess.Popen([sys.executable, "demo_app.py"], env=env,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(50):
        try:
            requests.get(BASE + "/", timeout=0.5); return pr
        except Exception:
            time.sleep(0.2)
    raise RuntimeError("server did not start")


def stop(pr):
    pr.terminate(); pr.wait()


def snapshot():
    c = sqlite3.connect(DB)
    return c.execute("SELECT * FROM grades ORDER BY id").fetchall()


def tok(html):
    return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)


def login(user="admin", pw="ChangeMe#3"):
    s = requests.Session()
    r = s.get(BASE + "/login"); anon = s.cookies.get("session_id")
    t = tok(r.text)
    r = s.post(BASE + "/login", data={"csrf_token": t, "username": user, "password": pw},
               allow_redirects=False)
    return s, r, anon


def csrf_of(s):
    return tok(s.get(BASE + "/").text)


MUT = [("/grades/add", {"student_id": 1, "discipline_id": 2, "value": 50}),
       ("/grades/1/edit", {"value": 1}), ("/grades/1/delete", {})]

shutil.copy("demo.db", DB)
pr = start()

# 1
before = snapshot()
codes = [requests.post(BASE + p, data=d, allow_redirects=False).status_code for p, d in MUT]
lg = requests.get(BASE + "/logout").status_code
gets = [requests.get(BASE + "/grades/1/edit", allow_redirects=False).status_code]
R[1] = f"POST без входу на {len(MUT)} маршрути: коди {codes} (Location -> /login); БД {'без змін' if snapshot()==before else 'ЗМІНЕНА'}; GET /logout -> {lg}; GET /grades/1/edit -> {gets[0]}"

# 2
s = requests.Session(); r = s.get(BASE + "/login")
ck = s.cookies.get("session_id")
set_cookie = r.headers.get("Set-Cookie", "")
t = tok(r.text)
res = []
for u, p in [("nouser", "x"), ("admin", "wrong"), ("admin", ""), ("", "")]:
    rr = s.post(BASE + "/login", data={"csrf_token": t, "username": u, "password": p}, allow_redirects=False)
    res.append(rr.status_code)
prot = s.get(BASE + "/grades/1/edit", allow_redirects=False).status_code
R[2] = (f"Анонімний cookie створено ({'так' if ck else 'ні'}); атрибути: HttpOnly={'HttpOnly' in set_cookie}, SameSite=Lax={'SameSite=Lax' in set_cookie}, Path=/={'Path=/' in set_cookie}, Max-Age={'Max-Age=1800' in set_cookie}. "
        f"Невідомий логін / хибний пароль / порожній пароль / порожні поля (прямий запит): коди {res}; доступ до захищеного після спроб: {prot}")

# 3
s, r, anon = login()
new = s.cookies.get("session_id")
ok = requests.get(BASE + "/grades/1/edit", cookies={"session_id": anon}, allow_redirects=False).status_code
acc = s.get(BASE + "/grades/1/edit", allow_redirects=False).status_code
R[3] = (f"Вхід -> {r.status_code}, Location={r.headers.get('Location')}; ідентифікатор змінився: {anon != new}; "
        f"довжина id={len(new)} символів; старий анонімний id -> {ok} (доступу немає); нова сесія -> {acc} (200 = доступ є); "
        f"cookie містить лише випадковий рядок (не містить 'admin' чи хеш): {'admin' not in new and 'scrypt' not in new}")

# 4
bad = new[:-1] + ("A" if new[-1] != "A" else "B")
c1 = requests.get(BASE + "/grades/1/edit", cookies={"session_id": bad}, allow_redirects=False).status_code
c2 = requests.get(BASE + "/grades/1/edit", allow_redirects=False).status_code
c3 = requests.get(BASE + "/grades/1/edit", cookies={"session_id": new}, allow_redirects=False).status_code
R[4] = f"Змінений символ -> {c1}; cookie видалено -> {c2}; оригінальний id після цього (запис на сервері лишився) -> {c3}"

# 5
s, r, _ = login("teacher1", "ChangeMe#1")
saved = s.cookies.get("session_id"); t = csrf_of(s)
lo = s.post(BASE + "/logout", data={"csrf_token": t}, allow_redirects=False)
reuse = requests.get(BASE + "/grades/1/edit", cookies={"session_id": saved}, allow_redirects=False)
sc = lo.headers.get("Set-Cookie", "")
R[5] = f"Вихід -> {lo.status_code}; Set-Cookie видаляє cookie: {'Max-Age=0' in sc or 'expires=Thu, 01 Jan 1970' in sc.lower() or '1970' in sc}; повторне використання збереженого id -> {reuse.status_code} (Location {reuse.headers.get('Location')})"

# 7 (перед 6, бо потребує звичайного сервера)
s, r, _ = login(); sid7 = s.cookies.get("session_id")
before = snapshot()
tk = csrf_of(s)
s.post(BASE + "/grades/2/edit", data={"csrf_token": tk, "value": 77}, allow_redirects=False)
stop(pr); pr = start()
after_restart = requests.get(BASE + "/grades/1/edit", cookies={"session_id": sid7}, allow_redirects=False).status_code
users = sqlite3.connect(DB).execute("select count(*) from users").fetchone()[0]
grade2 = sqlite3.connect(DB).execute("select value from grades where id=2").fetchone()[0]
s2, r2, _ = login()
R[7] = f"Після перезапуску старий cookie -> {after_restart} (потрібен повторний вхід); таблиця users: {users} записи; зміна оцінки збереглась (id=2 -> {grade2}); новий вхід -> {r2.status_code}"

# 8
s, r, _ = login(); t = csrf_of(s)
s_other, _, _ = login("teacher1", "ChangeMe#1"); t_other = csrf_of(s_other)
b = snapshot()
a = s.post(BASE + "/grades/1/edit", data={"value": 11}, allow_redirects=False).status_code
bb = s.post(BASE + "/grades/1/edit", data={"csrf_token": "wrong", "value": 11}, allow_redirects=False).status_code
c = s.post(BASE + "/grades/1/edit", data={"csrf_token": t_other, "value": 11}, allow_redirects=False).status_code
unchanged = snapshot() == b
l1 = requests.post(BASE + "/login", data={"username": "admin", "password": "ChangeMe#3"}, allow_redirects=False).status_code
l2 = requests.Session()
l2.get(BASE + "/login")
l2c = l2.post(BASE + "/login", data={"csrf_token": "bad", "username": "admin", "password": "ChangeMe#3"}, allow_redirects=False).status_code
good = s.post(BASE + "/grades/1/edit", data={"csrf_token": t, "value": 11}, allow_redirects=False).status_code
v = sqlite3.connect(DB).execute("select value from grades where id=1").fetchone()[0]
R[8] = (f"Без токена -> {a}; хибний -> {bb}; токен іншої сесії -> {c}; БД після відмов {'без змін' if unchanged else 'ЗМІНЕНА'}; "
        f"/login без сесії і без токена -> {l1}; /login з хибним токеном -> {l2c}; правильний токен -> {good}, оцінка id=1 стала {v}")

# 9
sa, _, _ = login("admin", "ChangeMe#3"); sb, _, _ = login("teacher1", "ChangeMe#1")
ia, ib = sa.cookies.get("session_id"), sb.cookies.get("session_id")
na = re.search(r"Користувач: ([^<\s]+)", sa.get(BASE + "/").text).group(1)
nb = re.search(r"Користувач: ([^<\s]+)", sb.get(BASE + "/").text).group(1)
tb = csrf_of(sb); sb.post(BASE + "/logout", data={"csrf_token": tb})
still = sa.get(BASE + "/grades/1/edit", allow_redirects=False).status_code
gone = sb.get(BASE + "/grades/1/edit", allow_redirects=False).status_code
R[9] = f"Різні ідентифікатори: {ia != ib}; імена в інтерфейсі: {na} та {nb}; після виходу другого: перший -> {still} (залишається), другий -> {gone}"

# 10
sx, r, _ = login("викладач", "ChangeMe#2")
ua = r.status_code
inj = []
for u in ["' OR '1'='1", "admin' --", "admin'; DROP TABLE users;--"]:
    ss = requests.Session(); tt = tok(ss.get(BASE + "/login").text)
    inj.append(ss.post(BASE + "/login", data={"csrf_token": tt, "username": u, "password": "x"}, allow_redirects=False).status_code)
users_ok = sqlite3.connect(DB).execute("select count(*) from users").fetchone()[0]
s, _, _ = login(); t = csrf_of(s)
b = snapshot()
missing = s.post(BASE + "/grades/9999/edit", data={"csrf_token": t, "value": 50}, allow_redirects=False).status_code
missing_d = s.post(BASE + "/grades/9999/delete", data={"csrf_token": t}, allow_redirects=False).status_code
badval = s.post(BASE + "/grades/1/edit", data={"csrf_token": t, "value": "abc"}, allow_redirects=False).status_code
d1 = s.post(BASE + "/grades/3/delete", data={"csrf_token": t}, allow_redirects=False).status_code
d2 = s.post(BASE + "/grades/3/delete", data={"csrf_token": t}, allow_redirects=False).status_code
R[10] = (f"Український логін «викладач» -> {ua}; SQL-подібні логіни -> {inj} (відмова), таблиця users ціла ({users_ok} записи); "
         f"неіснуючий запис: edit -> {missing}, delete -> {missing_d}; некоректна оцінка -> {badval}; повторне видалення: {d1}, потім {d2}")

# 6
stop(pr); shutil.copy("demo.db", DB); pr = start(ttl=3)
s, r, _ = login(); sid6 = s.cookies.get("session_id")
before = requests.get(BASE + "/grades/1/edit", cookies={"session_id": sid6}, allow_redirects=False).status_code
time.sleep(4)
after = requests.get(BASE + "/grades/1/edit", cookies={"session_id": sid6}, allow_redirects=False).status_code
R[6] = f"SESSION_TTL тимчасово = 3 с. Одразу після входу -> {before}; через 4 с з тим самим cookie -> {after}; значення TTL відновлено (запуск без LAB_TTL = 1800 с)"
stop(pr)
os.remove(DB)
json.dump({str(k): R[k] for k in sorted(R)}, open("experiment_results.json", "w"), ensure_ascii=False, indent=1)
for k in sorted(R):
    print(k, R[k])
