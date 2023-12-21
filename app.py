from werkzeug.security import check_password_hash, generate_password_hash
from flask import redirect, render_template, request, session, Flask, flash, url_for
import psycopg2
from datetime import datetime, timedelta

app = Flask(__name__)

app.secret_key = "123"
user_db = "artem_knowledge_base"
host_ip = "127.0.0.1"
host_port = "5432"
database_name = "RGZ_WEB"
password="123"


app.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql://{user_db}:{password}@{host_ip}:{host_port}/{database_name}'

def calculate_start_date(year, week_number):
    # Функция для расчета даты начала заданной недели в году
    start_date = datetime.strptime(f'{year}-W{week_number}-1', "%Y-W%W-%w")
    return start_date.date()

def calculate_end_date(year, week_number):
    # Функция для расчета даты окончания заданной недели в году
    start_date = calculate_start_date(year, week_number)
    end_date = start_date + timedelta(days=6)
    return end_date
 
def dbConnect():
   conn = psycopg2.connect(
      host = "127.0.0.1",
      database = "RGZ_WEB",
      user = "artem_knowledge_base",
      password = "123")
   return conn;

def dbClose (cursor, connecttion):
   cursor.close()
   connecttion.close()

def get_username_by_id(user_id):
    conn = dbConnect()
    cur = conn.cursor()

    cur.execute("SELECT username FROM users WHERE id = %s", (user_id,))
    result = cur.fetchone()

    dbClose(cur, conn)

    return result[0] if result else None


def get_weeks(year):
   # Функция для получения списка недель в заданном году
   start_date = datetime(year, 1, 1)
   weeks = [(start_date + timedelta(days=7 * i)).isocalendar()[1] for i in range(52)]
   return weeks

@app.route("/")
def main():
    visible_user = session.get("username")

    if visible_user:
        current_year = datetime.now().year
        weeks = get_weeks(current_year)

        # Получение данных об отпусках пользователя из базы данных
        # (вам нужно изменить схему вашей базы данных соответственно)
        weeks_status = get_weeks_status(current_year, session.get("id"))

        print("Weeks Status:", weeks_status)  # Выводим статус недель в консоль для отладки

        return render_template("vacation_planning.html", username=visible_user, weeks=weeks, weeks_status=weeks_status)
    else:
        return redirect("/login")

def get_weeks_status(year, user_id):
    conn = dbConnect()
    cur = conn.cursor()

    weeks_status = {}
    for week_number in get_weeks(year):
        start_date = calculate_start_date(year, week_number)
        end_date = calculate_end_date(year, week_number)

        cur.execute("SELECT user_id FROM vacation WHERE start_date <= %s AND end_date >= %s", (end_date, start_date))
        result = cur.fetchone()

        if result:
            reserved_user_id = result[0]
            if reserved_user_id == user_id:
                status = "Вы забронировали"
            else:
                reserved_user = get_username_by_id(reserved_user_id)
                status = f"Занято пользователем {reserved_user}"
        else:
            status = "Свободно"

        weeks_status[week_number] = status

    dbClose(cur, conn)
    return weeks_status

     
@app.route('/register', methods=["GET", "POST"])
def registerPage():
    errors = []

    visibleUser = "Anon"
    visibleUser = session.get("username")
   
    if request.method == "GET": 
        return render_template("register.html", errors=errors, username=visibleUser)

    username = request.form.get("username") 
    password = request.form.get("password")

    if not (username or password): 
        errors.append("Пожалуйста, заполните все поля") 
        print(errors) 
        return render_template("register.html", errors=errors, username=visibleUser)

    hashPassword = generate_password_hash(password)
   
    conn = dbConnect()
    cur = conn.cursor()

    cur.execute(f"SELECT username FROM users WHERE username = %s;", (username,))

    if cur.fetchone() is not None:
        errors.append("Пользователь с данным именем уже существует")
        dbClose(cur, conn) 
        flash("Ошибка при регистрации: Пользователь с данным именем уже существует", "error")
        return render_template("register.html", errors=errors, username=visibleUser)

    cur.execute(f"INSERT INTO users (username, password) VALUES (%s,%s);", (username, hashPassword,))  

    conn.commit()
    dbClose(cur, conn)

    return redirect("/login")


@app.route('/login', methods=["GET", "POST"])
def loginPage():
    errors = []
    visibleUser = "Anon"
    visibleUser = session.get("username")

    if request.method == "GET":
        return render_template("login.html", errors=errors, username = visibleUser)

    username = request.form.get("username")
    password = request.form.get("password")

    if not (username or password):
        errors.append("Пожалуйста заполните все поля")
        return render_template("login.html", errors=errors, username = visibleUser)

    conn = dbConnect()
    cur = conn.cursor()

    cur.execute("SELECT id, password FROM users WHERE username = %s;", (username,))

    result = cur.fetchone()

    if result is None:
        errors.append("Неправильный логин или пароль")
        dbClose(cur, conn)
        return render_template("login.html", errors=errors, username = visibleUser)


    userID, hashPassword = result


    if check_password_hash(hashPassword, password):
 
        session['id'] = userID
        session['username'] = username
        dbClose(cur, conn)
        return redirect("/")

    else:
        errors.append("Неправильный логин или пароль")
        return render_template("login.html", errors=errors, username = visibleUser)
    
@app.route('/vacation_schedule', methods=["POST"])
def vacation_schedule():
    # Обработка запросов на планирование отпусков
    if not session.get("username"):
        # Перенаправление на страницу входа, если пользователь не аутентифицирован
        return redirect("/login")

    # Получение данных пользователя из формы
    selected_weeks = request.form.getlist("selected_weeks")

    # Проверка, что пользователь выбрал ровно 4 недели
    if len(selected_weeks) != 4:
        flash("Пожалуйста, выберите ровно 4 недели для отпуска", "error")
        return redirect("/")

    # Получение пользователя из сессии
    user_id = session.get("id")

    # Сохранение графика отпусков пользователя в базе данных
    conn = dbConnect()
    cur = conn.cursor()
    
    current_year = datetime.now().year

    try:
        for week_number in selected_weeks:
            start_date = calculate_start_date(current_year, int(week_number))
            end_date = calculate_end_date(current_year, int(week_number))
            
            query = "INSERT INTO vacation (user_id, start_date, end_date) VALUES (%s, %s, %s);"
            data = (user_id, start_date, end_date)

            print("Executing query:", cur.mogrify(query, data))  # Вывод запроса в консоль
            cur.execute(query, data)

        flash("График отпусков успешно сохранен", "success")
        return redirect(url_for('main')) 

    except Exception as e:
        # В случае ошибки выводим сообщение в консоль
        print("Error during vacation scheduling:", str(e))
        flash("Произошла ошибка при сохранении графика отпусков", "error")
        return redirect("/")
    finally:
        # Важно закрыть соединение в блоке finally, чтобы избежать утечек ресурсов
        dbClose(cur, conn)


@app.route("/vacation_status")
def vacation_status():
    if not session.get("username"):
        return redirect("/login")

    current_year = datetime.now().year
    user_id = session.get("id")

    conn = dbConnect()
    cur = conn.cursor()

    weeks_status = {}
    for week_number in get_weeks(current_year):
        start_date = calculate_start_date(current_year, week_number)
        end_date = calculate_end_date(current_year, week_number)

        cur.execute("SELECT user_id FROM vacation WHERE start_date <= %s AND end_date >= %s", (end_date, start_date))
        result = cur.fetchone()

        if result:
            reserved_user_id = result[0]
            if reserved_user_id == user_id:
                status = "Вы забронировали"
            else:
                reserved_user = get_username_by_id(reserved_user_id)
                status = f"Занято пользователем {reserved_user}"
        else:
            status = "Свободно"

        weeks_status[week_number] = status

    dbClose(cur, conn)

    weeks = get_weeks(current_year)
    return render_template("vacation_planning.html", username=session["username"], weeks=weeks, weeks_status=weeks_status)


@app.route("/logout")
def logout():
    session.clear()
    return redirect('/login')

   