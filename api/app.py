import os
from datetime import datetime, timedelta
from flask import Flask, render_template, redirect, url_for, request, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from sqlalchemy.engine import URL

# Настройка путей для Vercel
base_dir = os.path.dirname(os.path.abspath(__file__))
template_dir = os.path.join(base_dir, '..', 'templates')
static_dir = os.path.join(base_dir, '..', 'static')

app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
app.config['SECRET_KEY'] = 'neon-secret-key-2026'

# --- ПОДКЛЮЧЕНИЕ ЧЕРЕЗ ПУЛЕР (6543) ---
db_url = URL.create(
    drivername="postgresql+pg8000",
    username="postgres.tvnrmmarvwumojnolubs",
    password="NEON111vrqw",
    host="aws-1-eu-west-1.pooler.supabase.com",
    port=6543,
    database="postgres"
)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# ОПТИМИЗИРОВАННЫЙ ПУЛ ДЛЯ БЫСТРОГО ЧАТА
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "pool_size": 3,           # Разрешаем 3 параллельных соединения
    "max_overflow": 2,        # +2 в запасе при пиках
    "pool_recycle": 15,       # Сброс каждые 15 сек
    "pool_pre_ping": True     # Проверка связи
}

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- ОЧИСТКА СОЕДИНЕНИЙ (ВАЖНО ДЛЯ VERCEL) ---
@app.teardown_appcontext
def shutdown_session(exception=None):
    db.session.remove()

# Модели
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    display_name = db.Column(db.String(50))
    password = db.Column(db.String(100), nullable=False)
    is_banned = db.Column(db.Boolean, default=False)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(500), nullable=False)
    timestamp = db.Column(db.DateTime)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    user = db.relationship('User', backref='messages')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Инициализация
with app.app_context():
    db.create_all()
    if not User.query.filter_by(username='!vatoxa!').first():
        db.session.add(User(username='!vatoxa!', display_name='!vatoxa!', password='2026'))
        db.session.commit()

# --- МАРШРУТЫ ---
@app.route('/')
@login_required
def index():
    if current_user.is_banned:
        logout_user()
        return redirect(url_for('login'))
    return render_template('index.html')

@app.route('/api/messages')
@login_required
def get_messages():
    try:
        messages = Message.query.order_by(Message.timestamp.asc()).all()
        return jsonify([{"id": m.id, "user": m.user.display_name or m.user.username, "raw_user": m.user.username, "content": m.content, "time": m.timestamp.strftime('%H:%M') if m.timestamp else '--:--'} for m in messages])
    except: 
        db.session.rollback()
        return jsonify([])

@app.route('/send', methods=['POST'])
@login_required
def send_message():
    content = request.form.get('content')
    if content and content.strip() and not current_user.is_banned:
        local_time = datetime.utcnow() + timedelta(hours=7)
        db.session.add(Message(content=content, user_id=current_user.id, timestamp=local_time))
        db.session.commit()
    return "", 204

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username')).first()
        if user and user.password == request.form.get('password'):
            if not user.is_banned:
                login_user(user)
                return redirect(url_for('index'))
            flash('Бан 🚫')
        else: flash('Ошибка входа')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('username')
        if not User.query.filter_by(username=name).first():
            db.session.add(User(username=name, display_name=name, password=request.form.get('password')))
            db.session.commit()
            return redirect(url_for('login'))
        flash('Имя занято')
    return render_template('register.html')

# --- АДМИНКА ---
@app.route('/admin')
@login_required
def admin_panel():
    if current_user.username != '!vatoxa!': return "403 Forbidden", 403
    return render_template('admin.html', users=User.query.all(), count=Message.query.count())

@app.route('/admin/clear', methods=['POST'])
@login_required
def clear_chat():
    if current_user.username == '!vatoxa!':
        Message.query.delete()
        db.session.commit()
    return redirect(url_for('admin_panel'))

@app.route('/admin/delete_msg/<int:msg_id>', methods=['POST'])
@login_required
def delete_msg(msg_id):
    if current_user.username == '!vatoxa!':
        m = Message.query.get(msg_id)
        if m: db.session.delete(m); db.session.commit()
    return "", 204

@app.route('/admin/rename/<int:user_id>', methods=['POST'])
@login_required
def rename_user(user_id):
    if current_user.username == '!vatoxa!':
        u = User.query.get(user_id)
        n = request.form.get('new_name')
        if u and n: u.display_name = n; db.session.commit()
    return redirect(url_for('admin_panel'))

@app.route('/admin/ban/<int:user_id>', methods=['POST'])
@login_required
def ban_user(user_id):
    if current_user.username == '!vatoxa!':
        u = User.query.get(user_id)
        if u and u.username != '!vatoxa!': u.is_banned = not u.is_banned; db.session.commit()
    return redirect(url_for('admin_panel'))

# Vercel app
app = app

if __name__ == '__main__':
    app.run()
