from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key'


# 初始化数据库
def init_db():
    conn = sqlite3.connect('volunteers.db')
    cursor = conn.cursor()

    # 创建用户表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT NOT NULL UNIQUE,
        created_at TEXT NOT NULL
    )
    ''')

    # 创建活动表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    ''')

    # 创建活动成员表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS event_members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        added_at TEXT NOT NULL,
        FOREIGN KEY (event_id) REFERENCES events (id),
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')

    # 创建签到表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS signins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        signin_time TEXT NOT NULL,
        FOREIGN KEY (event_id) REFERENCES events (id),
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')

    # 创建签到时长表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS signin_durations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            duration INTEGER NOT NULL,
            end_time TEXT NOT NULL,
            FOREIGN KEY (event_id) REFERENCES events (id),
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        ''')

    conn.commit()
    conn.close()


init_db()


# 辅助函数：获取数据库连接
def get_db_connection():
    conn = sqlite3.connect('volunteers.db')
    conn.row_factory = sqlite3.Row
    return conn


# 首页 - 登录
@app.route('/')
def index():
    return render_template('index.html')


# 注册新用户
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        phone = request.form['phone']

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("INSERT INTO users (name, phone, created_at) VALUES (?, ?, ?)",
                           (name, phone, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit()
            flash('注册成功！请登录。')
            return redirect(url_for('index'))
        except sqlite3.IntegrityError:
            flash('该电话号码已注册！请直接登录。')
            return redirect(url_for('index'))
        finally:
            conn.close()
    else:
        # 处理GET请求，显示注册页面
        return render_template('register.html')

# 登录
@app.route('/login', methods=['POST'])
def login():
    name = request.form['name']
    phone = request.form['phone']

    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE name = ? AND phone = ?', (name, phone)).fetchone()
    conn.close()

    if user:
        # 在实际应用中，这里应该使用会话管理
        return redirect(url_for('dashboard', user_id=user['id']))
    else:
        flash('还未有账号，请先注册。')
        return redirect(url_for('index'))


# 主页面
@app.route('/dashboard/<int:user_id>')
def dashboard(user_id):
    return render_template('dashboard.html', user_id=user_id)


# 举办活动
@app.route('/create_event/<int:user_id>')
def create_event(user_id):
    return render_template('create_event.html', user_id=user_id)


# 创建活动
@app.route('/create_event_submit/<int:user_id>', methods=['POST'])
def create_event_submit(user_id):
    event_name = request.form['event_name']

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("INSERT INTO events (name, created_at) VALUES (?, ?)",
                   (event_name, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    event_id = cursor.lastrowid
    conn.commit()
    conn.close()

    # 自动将当前用户添加到活动成员中
    add_member(user_id, event_id)

    return redirect(url_for('dashboard', user_id=user_id))


# 加入人员
@app.route('/add_member/<int:user_id>/<int:event_id>')
def add_member_page(user_id, event_id):
    return render_template('add_member.html', user_id=user_id, event_id=event_id)

# 处理签到结束
@app.route('/end_signin/<int:user_id>/<int:event_id>', methods=['POST'])
def end_signin(user_id, event_id):
    data = request.get_json()
    signin_name = data['name']
    signin_phone = data['phone']
    duration = data['duration']

    conn = get_db_connection()
    cursor = conn.cursor()

    # 检查用户是否存在
    user = conn.execute('SELECT * FROM users WHERE name = ? AND phone = ?', (signin_name, signin_phone)).fetchone()

    if user:
        # 检查用户是否属于该活动
        member = conn.execute('SELECT * FROM event_members WHERE event_id = ? AND user_id = ?',
                              (event_id, user['id'])).fetchone()

        if member:
            # 记录签到时长
            cursor.execute("INSERT INTO signin_durations (event_id, user_id, duration, end_time) VALUES (?, ?, ?, ?)",
                           (event_id, user['id'], duration, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit()
            conn.close()
            return jsonify({'message': '签到时长已记录！'})
        else:
            conn.close()
            return jsonify({'message': '该用户不属于此活动，请先添加为成员。'}), 400
    else:
        conn.close()
        return jsonify({'message': '未找到该用户，请先注册。'}), 400

# 添加成员到活动
def add_member(user_id, event_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("INSERT INTO event_members (event_id, user_id, added_at) VALUES (?, ?, ?)",
                   (event_id, user_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()


# 查看所有人员
@app.route('/view_members/<int:user_id>/<int:event_id>')
def view_members(user_id, event_id):
    conn = get_db_connection()
    members = conn.execute('''
        SELECT u.id, u.name, u.phone, em.added_at
        FROM event_members em
        JOIN users u ON em.user_id = u.id
        WHERE em.event_id = ?
    ''', (event_id,)).fetchall()
    conn.close()

    return render_template('members.html', user_id=user_id, event_id=event_id, members=members)


# 志愿签到
@app.route('/signin/<int:user_id>/<int:event_id>')
def signin_page(user_id, event_id):
    return render_template('signin.html', user_id=user_id, event_id=event_id)


# 处理签到
@app.route('/process_signin/<int:user_id>/<int:event_id>', methods=['POST'])
def process_signin(user_id, event_id):
    signin_name = request.form['signin_name']
    signin_phone = request.form['signin_phone']

    conn = get_db_connection()
    cursor = conn.cursor()

    # 检查用户是否存在
    user = conn.execute('SELECT * FROM users WHERE name = ? AND phone = ?', (signin_name, signin_phone)).fetchone()

    if user:
        # 检查用户是否属于该活动
        member = conn.execute('SELECT * FROM event_members WHERE event_id = ? AND user_id = ?',
                              (event_id, user['id'])).fetchone()

        if member:
            # 记录签到
            cursor.execute("INSERT INTO signins (event_id, user_id, signin_time) VALUES (?, ?, ?)",
                           (event_id, user['id'], datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit()
            flash('签到成功！')
        else:
            flash('该用户不属于此活动，请先添加为成员。')
    else:
        flash('未找到该用户，请先注册。')

    conn.close()
    return redirect(url_for('dashboard', user_id=user_id))


if __name__ == '__main__':
    app.run(host='0.0.0.0',debug=True)