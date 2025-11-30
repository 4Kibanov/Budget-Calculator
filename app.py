from flask import Flask, render_template, request, redirect, url_for, jsonify, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = 'qwerty12345'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///budget.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    entries = db.relationship('Entry', backref='user', lazy=True)

class Entry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(10))
    category = db.Column(db.String(50))
    amount = db.Column(db.Float)
    comment = db.Column(db.String(200))
    date = db.Column(db.DateTime, default=datetime.now)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

with app.app_context():
    db.create_all()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        if not username or not password:
            flash('Введите логин и пароль')
            return redirect(url_for('register'))
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Пользователь с таким логином уже существует')
            return redirect(url_for('register'))
        hashed_pw = generate_password_hash(password)
        user = User(username=username, password=hashed_pw)
        db.session.add(user)
        db.session.commit()
        flash('Регистрация успешна! Войдите в систему.')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['username'] = user.username
            return redirect(url_for('index'))
        flash('Неверный логин или пароль')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    user_id = session['user_id']
    entries = Entry.query.filter_by(user_id=user_id).order_by(Entry.date.desc()).all()
    income_sum = db.session.query(db.func.sum(Entry.amount)).filter_by(type='income', user_id=user_id).scalar() or 0
    expense_sum = db.session.query(db.func.sum(Entry.amount)).filter_by(type='expense', user_id=user_id).scalar() or 0
    balance = income_sum - expense_sum

    # Суммы по категориям
    expenses_by_category = db.session.query(
        Entry.category, db.func.sum(Entry.amount)
    ).filter_by(type='expense', user_id=user_id).group_by(Entry.category).all()
    incomes_by_category = db.session.query(
        Entry.category, db.func.sum(Entry.amount)
    ).filter_by(type='income', user_id=user_id).group_by(Entry.category).all()

    return render_template(
        'index.html',
        entries=entries,
        balance=balance,
        income_sum=income_sum,
        expense_sum=expense_sum,
        expenses_by_category=expenses_by_category,
        incomes_by_category=incomes_by_category,
        username=session.get('username')
    )

@app.route('/add', methods=['POST'])
@login_required
def add_entry():
    user_id = session['user_id']
    type_ = request.form['type']
    category = request.form['category']
    amount = float(request.form['amount'])
    comment = request.form['comment']
    entry = Entry(type=type_, category=category, amount=amount, comment=comment, user_id=user_id)
    db.session.add(entry)
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/delete/<int:entry_id>', methods=['POST'])
@login_required
def delete_entry(entry_id):
    entry = Entry.query.get_or_404(entry_id)
    if entry.user_id != session['user_id']:
        flash('Вы не можете удалить эту запись')
        return redirect(url_for('index'))
    db.session.delete(entry)
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/api/export')
@login_required
def export_json():
    user_id = session['user_id']
    entries = Entry.query.filter_by(user_id=user_id).order_by(Entry.date.desc()).all()
    data = [
        {
            'id': e.id,
            'type': e.type,
            'category': e.category,
            'amount': e.amount,
            'comment': e.comment,
            'date': e.date.strftime("%Y-%m-%d %H:%M")
        } for e in entries
    ]
    return jsonify(data)

if __name__ == '__main__':
    app.run(debug=True)