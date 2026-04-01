import urllib.parse
import psycopg2
from psycopg2 import errors
from psycopg2.extras import DictCursor
from fastapi import FastAPI, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from jinja2 import Template
import uvicorn
from passlib.context import CryptContext
from contextlib import asynccontextmanager

# ==========================================
# 0. БАЗА ДАННЫХ И ШИФРОВАНИЕ
# ==========================================
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Обрезаем пароль до 72 байт, чтобы избежать ошибки алгоритма bcrypt
def verify_password(plain_password, hashed_password): 
    return pwd_context.verify(plain_password[:72], hashed_password)

def get_password_hash(password): 
    return pwd_context.hash(password[:72])

DB_HOST = "127.0.0.1"
DB_PORT = "5432"
DB_NAME = "postgres"      
DB_USER = "postgres"      
DB_PASSWORD = "pg12345"   

def get_db_connection():
    return psycopg2.connect(host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("""CREATE TABLE IF NOT EXISTS users (id SERIAL PRIMARY KEY, username VARCHAR(50) UNIQUE NOT NULL, password_hash VARCHAR(255) NOT NULL);""")
            cur.execute("""CREATE TABLE IF NOT EXISTS progress (id SERIAL PRIMARY KEY, user_id INTEGER, course_id VARCHAR(50), score INTEGER, UNIQUE(user_id, course_id));""")
            conn.commit()
        conn.close()
        print("✅ Таблицы БД успешно проверены/созданы.")
    except Exception as e:
        print("❌ Ошибка инициализации БД:", e)
    yield

app = FastAPI(title="LMS Education Platform", lifespan=lifespan)

# ==========================================
# 1. ДАННЫЕ (КАТАЛОГ И СОДЕРЖИМОЕ КУРСОВ)
# ==========================================
ALL_COURSES = [
    {"id": "security_101", "title": "Корпоративная безопасность", "desc": "Основы ИБ, фишинг, пароли.", "duration": "2 часа"},
    {"id": "python_basic", "title": "Основы Python", "desc": "Введение в программирование с нуля.", "duration": "10 часов"},
    {"id": "devops_intro", "title": "Введение в DevOps", "desc": "Docker, Kubernetes, CI/CD для новичков.", "duration": "5 часов"}
]

COURSE_CONTENT = {
    "security_101": {
        "title": "Корпоративная безопасность",
        "modules": [
            {"title": "Модуль 1: Парольные политики", "lessons": [{"id": "sec_l1", "title": "Введение в ИБ", "type": "video"}]},
            {"title": "Модуль 2: Социальная инженерия", "lessons": [{"id": "sec_l2", "title": "Как распознать фишинг", "type": "video"}]}
        ]
    },
    "python_basic": {
        "title": "Основы Python",
        "modules": [
            {"title": "Введение", "lessons": [{"id": "py_l1", "title": "Установка Python", "type": "video"}]}
        ]
    },
    "devops_intro": {
        "title": "Введение в DevOps",
        "modules": [
            {"title": "Контейнеризация", "lessons": [{"id": "dev_l1", "title": "Что такое Docker", "type": "video"}]}
        ]
    }
}

# ==========================================
# 2. CSS И ПЛАШКА НАВИГАЦИИ
# ==========================================
COMMON_STYLE = """
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f7f6; margin: 0; padding: 20px; }
        .header { background: #0056b3; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
        .navbar { background-color: #333; overflow: hidden; border-radius: 8px; margin-bottom: 20px; display: flex; align-items: center;}
        .navbar a { display: block; color: #f2f2f2; text-align: center; padding: 14px 20px; text-decoration: none; font-weight: bold; }
        .navbar a:hover { background-color: #ddd; color: black; }
        .navbar a.right { margin-left: auto; background-color: #28a745; }
        .navbar a.logout { background-color: #6c757d; margin-left: 5px; border-radius: 4px; margin-right: 5px;}
        .alert { background: #ff4444; color: white; padding: 10px; border-radius: 5px; margin-bottom: 20px; font-weight: bold; }
        .success { background: #00C851; color: white; padding: 10px; border-radius: 5px; margin-bottom: 20px; font-weight: bold; }
        .card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-bottom: 20px;}
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 20px; }
        .btn { display: inline-block; padding: 10px 15px; background: #007bff; color: white; text-decoration: none; border-radius: 5px; border: none; cursor: pointer;}
        .btn-outline { background: transparent; color: #007bff; border: 2px solid #007bff; }
        .btn-outline:hover { background: #007bff; color: white; }
        .btn-enroll { background: #28a745; width: 100%; margin-top: 10px; }
        input[type="text"], input[type="password"] { width: 100%; padding: 10px; margin: 8px 0; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; }
        .hidden { display: none; }
    </style>
"""

def get_navbar(username: str = None):
    auth_links = f"""
        <span style="color:white; margin-left: auto; padding-right: 15px;">Студент: <b>{username}</b></span>
        <a href="/profile" class="right" style="margin-left: 0;">👤 Профиль</a>
        <a href="/logout" class="logout">🚪 Выход</a>
    """ if username else """<a href="/login" class="right">🔑 Войти / Регистрация</a>"""
    return f'<div class="navbar"><a href="/">🏠 Главная</a>{auth_links}</div>'

# ==========================================
# 3. HTML ШАБЛОНЫ
# ==========================================
LOGIN_HTML = f"""
<!DOCTYPE html><html lang="ru"><head><meta charset="UTF-8"><title>Вход</title>{COMMON_STYLE}</head><body>
    {{{{ navbar }}}}
    {{% if error %}} <div class="alert">{{{{ error }}}}</div> {{% endif %}}
    {{% if msg %}} <div class="success">{{{{ msg }}}}</div> {{% endif %}}

    <div id="login-container" class="card" style="max-width: 400px; margin: 0 auto;">
        <h2 style="text-align: center;">Вход в LMS</h2>
        <form action="/login" method="post">
            <label>Логин:</label><input type="text" name="username" required>
            <label>Пароль:</label><input type="password" name="password" required>
            <button type="submit" class="btn" style="width: 100%; background: #0056b3;">Войти</button>
        </form>
        <p style="text-align: center; margin-top: 15px;">Нет аккаунта? <a href="#" onclick="toggleForms(event)" style="color: #28a745;">Создать аккаунт</a></p>
    </div>

    <div id="register-container" class="card hidden" style="max-width: 400px; margin: 0 auto; background: #f8f9fa;">
        <h2 style="text-align: center;">Регистрация</h2>
        <form action="/register" method="post">
            <label>Придумайте Логин:</label><input type="text" name="username" required>
            <label>Придумайте Пароль:</label><input type="password" name="password" required>
            <button type="submit" class="btn" style="width: 100%; background: #28a745;">Зарегистрироваться</button>
        </form>
        <p style="text-align: center; margin-top: 15px;">Уже есть аккаунт? <a href="#" onclick="toggleForms(event)">Вернуться ко входу</a></p>
    </div>
    <script>
        function toggleForms(e) {{
            e.preventDefault();
            document.getElementById('login-container').classList.toggle('hidden');
            document.getElementById('register-container').classList.toggle('hidden');
        }}
    </script>
</body></html>
"""

DASHBOARD_HTML = f"""
<!DOCTYPE html><html lang="ru"><head><meta charset="UTF-8"><title>LMS Платформа</title>{COMMON_STYLE}
    <style>.progress-bar {{ background: #e9ecef; border-radius: 5px; height: 15px; margin-top: 10px; overflow: hidden; }} .progress-fill {{ background: #007bff; height: 100%; }}</style>
</head><body>
    {{{{ navbar }}}}
    
    <div class="header"><h1>Образовательная платформа</h1><p>Продолжайте обучение или выберите новый курс.</p></div>

    <h2>📚 Мои курсы (В процессе)</h2>
    {{% if my_courses %}}
        <div class="grid">
            {{% for course in my_courses %}}
            <div class="card">
                <h3>{{{{ course.title }}}}</h3>
                <p style="color: gray; font-size: 14px;">{{{{ course.desc }}}}</p>
                <p>Прогресс: <strong>{{{{ course.score }}}}%</strong></p>
                <div class="progress-bar"><div class="progress-fill" style="width: {{{{ course.score }}}}%;"></div></div>
                <a href="/course/{{{{ course.id }}}}" class="btn" style="width:100%; text-align:center; display:block; box-sizing:border-box;">Продолжить обучение ➔</a>
            </div>
            {{% endfor %}}
        </div>
    {{% else %}}
        <div class="card"><p>Вы еще не записались ни на один курс.</p></div>
    {{% endif %}}

    <hr style="border: 1px solid #ddd; margin: 30px 0;">

    <div style="text-align: center; margin-bottom: 20px;">
        <button onclick="toggleCatalog()" class="btn btn-outline" style="font-size: 18px; padding: 15px 30px;">➕ Показать доступные курсы для записи</button>
    </div>

    <div id="catalog-section" class="hidden">
        <h2>Доступные курсы (Каталог)</h2>
        {{% if available_courses %}}
            <div class="grid">
                {{% for course in available_courses %}}
                <div class="card" style="border-left: 4px solid #28a745;">
                    <h3>{{{{ course.title }}}}</h3>
                    <p>{{{{ course.desc }}}}</p>
                    <p><small>⏱ Объем: {{{{ course.duration }}}}</small></p>
                    <form action="/enroll/{{{{ course.id }}}}" method="post">
                        <button type="submit" class="btn btn-enroll">Записаться на курс</button>
                    </form>
                </div>
                {{% endfor %}}
            </div>
        {{% else %}}
            <div class="card"><p>Вы записаны на все доступные курсы на платформе!</p></div>
        {{% endif %}}
    </div>
    <script>
        function toggleCatalog() {{
            const catalog = document.getElementById('catalog-section');
            catalog.classList.toggle('hidden');
            if (!catalog.classList.contains('hidden')) window.scrollTo({{ top: document.body.scrollHeight, behavior: 'smooth' }});
        }}
    </script>
</body></html>
"""

COURSE_HTML = f"""
<!DOCTYPE html><html lang="ru"><head><meta charset="UTF-8"><title>Оглавление курса</title>{COMMON_STYLE}
    <style>.lesson-row {{ padding: 10px; border-bottom: 1px solid #eee; display: flex; justify-content: space-between; align-items: center;}}</style>
</head><body>
    {{{{ navbar }}}}
    <div class="header"><h1>{{{{ course.title }}}}</h1><p>Структура модулей и уроков</p></div>
    
    {{% for module in course.modules %}}
    <div class="card">
        <h2>{{{{ module.title }}}}</h2>
        {{% for lesson in module.lessons %}}
        <div class="lesson-row">
            <span>{{{{ '🎥' if lesson.type == 'video' else '📝' }}}} {{{{ lesson.title }}}}</span>
            <a href="/course/{{{{ course_id }}}}/lesson/{{{{ lesson.id }}}}" class="btn" style="margin:0; background:#28a745;">Пройти</a>
        </div>
        {{% endfor %}}
    </div>
    {{% endfor %}}
</body></html>
"""

LESSON_HTML = f"""
<!DOCTYPE html><html lang="ru"><head><meta charset="UTF-8"><title>Урок</title>{COMMON_STYLE}
    <style>video {{ width: 100%; border-radius: 8px; background: black; margin-top: 15px;}}</style>
</head><body>
    {{{{ navbar }}}}
    <div class="card" style="max-width: 800px; margin: 0 auto; text-align: center;">
        <div style="text-align: left;"><a href="/course/{{{{ lesson.course_id }}}}" style="color: gray; text-decoration: none;">← Назад к структуре курса</a></div>
        <h2>{{{{ lesson.title }}}}</h2>
        <p style="color: #666;">Внимательно изучите материал</p>
        
        <video controls controlsList="nodownload">
            <source src="{{{{ lesson.video_url }}}}" type="video/mp4">
            Ваш браузер не поддерживает видео.
        </video>
        
        <br><br>
        <a href="/course/{{{{ lesson.course_id }}}}" class="btn" style="background: #28a745; width: 100%; box-sizing: border-box;">Завершить урок (Далее)</a>
    </div>
</body></html>
"""

PROFILE_HTML = f"""
<!DOCTYPE html><html lang="ru"><head><meta charset="UTF-8"><title>Профиль</title>{COMMON_STYLE}
    <style>.cert {{ border-left: 5px solid #ffc107; padding: 15px; background: #fdfdfd; margin-bottom: 10px; border-radius: 4px; border: 1px solid #eee; display: flex; justify-content: space-between; align-items: center;}}</style>
</head><body>
    {{{{ navbar }}}}
    <div class="header" style="background: #17a2b8;"><h1>Личный кабинет</h1><p>Студент: {{{{ username }}}}</p></div>
    
    <div class="card">
        <h2>🎓 Ваши сертификаты</h2>
        <p><i>Выдаются автоматически при прогрессе > 80 баллов.</i></p>
        {{% if certs %}}
            {{% for cert in certs %}}
            <div class="cert">
                <div><h3 style="margin:0 0 5px 0;">{{{{ cert.title }}}}</h3><span style="color:gray">Курс: {{{{ cert.course_id }}}} | Прогресс: {{{{ cert.score }}}}%</span></div>
                <a href="#" class="btn" style="background:#dc3545; margin: 0;">Скачать PDF</a>
            </div>
            {{% endfor %}}
        {{% else %}}
            <p style="color:red;">У вас пока нет сертификатов. Завершите курсы успешно!</p>
        {{% endif %}}
    </div>
</body></html>
"""

# ==========================================
# 4. ЛОГИКА ПРИЛОЖЕНИЯ
# ==========================================
def get_current_user(request: Request):
    return request.cookies.get("session_user")

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, error: str = None, msg: str = None):
    return Template(LOGIN_HTML).render(navbar=get_navbar(), error=error, msg=msg)

@app.post("/register")
def register_user(username: str = Form(...), password: str = Form(...)):
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("INSERT INTO users (username, password_hash) VALUES (%s, %s)", 
                        (username, get_password_hash(password)))
            conn.commit()
        conn.close()
        
        msg = urllib.parse.quote("Успех! Теперь авторизуйтесь.")
        return RedirectResponse(url=f"/login?msg={msg}", status_code=303)
        
    except errors.UniqueViolation:
        if conn: conn.close()
        error_msg = urllib.parse.quote("Логин занят!")
        return RedirectResponse(url=f"/login?error={error_msg}", status_code=303)
        
    except Exception as e:
        print("❌ Ошибка при регистрации:", e)
        if 'conn' in locals() and conn: conn.close()
        error_msg = urllib.parse.quote("Внутренняя ошибка сервера.")
        return RedirectResponse(url=f"/login?error={error_msg}", status_code=303)

@app.post("/login")
def login_user(username: str = Form(...), password: str = Form(...)):
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute("SELECT id, password_hash FROM users WHERE username = %s", (username,))
            user = cur.fetchone()
        conn.close()

        if user and verify_password(password, user['password_hash']):
            redirect = RedirectResponse(url="/", status_code=303)
            redirect.set_cookie(key="session_user", value=username, max_age=86400) 
            return redirect
            
        error_msg = urllib.parse.quote("Неверный логин или пароль!")
        return RedirectResponse(url=f"/login?error={error_msg}", status_code=303)
    except Exception as e:
        print("❌ Ошибка при входе:", e)
        error_msg = urllib.parse.quote("Ошибка базы данных")
        return RedirectResponse(url=f"/login?error={error_msg}", status_code=303)

@app.get("/logout")
def logout_user():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("session_user")
    return response

@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    username = get_current_user(request)
    if not username: 
        return RedirectResponse(url="/login", status_code=303)

    my_courses, available_courses = [], []
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute("SELECT id FROM users WHERE username = %s", (username,))
            user_row = cur.fetchone()
            
            if not user_row:
                conn.close()
                response = RedirectResponse(url="/login", status_code=303)
                response.delete_cookie("session_user")
                return response
                
            user_id = user_row['id']
            cur.execute("SELECT course_id, score FROM progress WHERE user_id = %s", (user_id,))
            progress_dict = {row['course_id']: row['score'] for row in cur.fetchall()}
            
            for c in ALL_COURSES:
                if c['id'] in progress_dict:
                    course_data = c.copy()
                    course_data['score'] = progress_dict[c['id']]
                    my_courses.append(course_data)
                else:
                    available_courses.append(c)
        conn.close()
    except Exception as e: 
        print("❌ Ошибка при загрузке главной страницы:", e)

    return Template(DASHBOARD_HTML).render(navbar=get_navbar(username), my_courses=my_courses, available_courses=available_courses)

@app.post("/enroll/{course_id}")
def enroll_course(request: Request, course_id: str):
    username = get_current_user(request)
    if not username: return RedirectResponse(url="/login", status_code=303)
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE username = %s", (username,))
            user_row = cur.fetchone()
            if user_row:
                test_score = 85 if course_id == 'security_101' else 0 
                cur.execute("INSERT INTO progress (user_id, course_id, score) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING", (user_row['id'], course_id, test_score))
                conn.commit()
        conn.close()
    except Exception as e: print("Enroll error:", e)
    return RedirectResponse(url="/", status_code=303)

@app.get("/course/{course_id}", response_class=HTMLResponse)
def view_course(request: Request, course_id: str):
    username = get_current_user(request)
    if not username: return RedirectResponse(url="/login", status_code=303)
    course_data = COURSE_CONTENT.get(course_id, {"title": "Неизвестный курс", "modules": []})
    return Template(COURSE_HTML).render(navbar=get_navbar(username), course=course_data, course_id=course_id)

@app.get("/course/{course_id}/lesson/{lesson_id}", response_class=HTMLResponse)
def view_lesson(request: Request, course_id: str, lesson_id: str):
    username = get_current_user(request)
    if not username: return RedirectResponse(url="/login", status_code=303)

    lesson_title = "Урок"
    course_data = COURSE_CONTENT.get(course_id, {})
    for mod in course_data.get("modules", []):
        for les in mod.get("lessons", []):
            if les["id"] == lesson_id:
                lesson_title = les["title"]

    lesson_data = {
        "course_id": course_id,
        "title": lesson_title,
        "video_url": f"/api/video/{lesson_id}" 
    }
    return Template(LESSON_HTML).render(navbar=get_navbar(username), lesson=lesson_data)

@app.get("/api/video/{video_id}")
def get_video_link(video_id: str):
    return RedirectResponse(url="https://www.w3schools.com/html/mov_bbb.mp4")

@app.get("/profile", response_class=HTMLResponse)
def profile_page(request: Request):
    username = get_current_user(request)
    if not username: return RedirectResponse(url="/login", status_code=303)

    certificates = []
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute("SELECT id FROM users WHERE username = %s", (username,))
            user_row = cur.fetchone()
            if user_row:
                cur.execute("SELECT course_id, score FROM progress WHERE user_id = %s", (user_row['id'],))
                for row in cur.fetchall():
                    if row['score'] >= 80: 
                        title = next((c['title'] for c in ALL_COURSES if c['id'] == row['course_id']), "Неизвестный курс")
                        certificates.append({"course_id": title, "score": row['score'], "title": "Сертификат об окончании"})
        conn.close()
    except: pass
        
    return Template(PROFILE_HTML).render(navbar=get_navbar(username), username=username, certs=certificates)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)

