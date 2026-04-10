import os
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_mail import Mail, Message
from flask_uploads import UploadSet, IMAGES, configure_uploads, patch_request_class
from flask_migrate import Migrate
from flask_restful import Api, Resource
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, Client, Order, OrderPhoto, DiagnosticChecklist, RepairHistory, Part, Admin
from config import Config
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
migrate = Migrate(app, db)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Пожалуйста, войдите для доступа к этой странице.'
mail = Mail(app)
api = Api(app)

# Настройка загрузки изображений
photos = UploadSet('photos', IMAGES)
configure_uploads(app, photos)
patch_request_class(app, 16 * 1024 * 1024)  # 16 MB max

@login_manager.user_loader
def load_user(user_id):
    return Client.query.get(int(user_id))

# Декоратор для админа
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin' not in session:
            flash('Войдите в админ-панель', 'error')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# --- Главная ---
@app.route('/')
def index():
    return render_template('index.html')

# --- Аутентификация клиентов ---
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        name = request.form['name']
        phone = request.form['phone']

        if Client.query.filter_by(email=email).first():
            flash('Пользователь с таким email уже существует', 'error')
            return redirect(url_for('register'))

        client = Client(
            email=email,
            password=generate_password_hash(password),
            name=name,
            phone=phone
        )
        db.session.add(client)
        db.session.commit()
        login_user(client)
        flash('Регистрация успешна! Добро пожаловать в личный кабинет.', 'success')
        return redirect(url_for('cabinet'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        client = Client.query.filter_by(email=email).first()
        if client and check_password_hash(client.password, password):
            login_user(client)
            next_page = request.args.get('next')
            flash('Вы успешно вошли', 'success')
            return redirect(next_page or url_for('cabinet'))
        flash('Неверный email или пароль', 'error')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('index'))

@app.route('/cabinet')
@login_required
def cabinet():
    orders = Order.query.filter_by(client_id=current_user.id).order_by(Order.created_at.desc()).all()
    return render_template('cabinet.html', orders=orders)

# --- Заявки ---
@app.route('/create_order', methods=['GET', 'POST'])
def create_order():
    if request.method == 'POST':
        # Создаём заявку
        order = Order(
            client_id=current_user.id if current_user.is_authenticated else None,
            client_name=request.form['name'],
            client_phone=request.form['phone'],
            client_email=request.form.get('email') or (current_user.email if current_user.is_authenticated else None),
            device_model=request.form['model'],
            serial_number=request.form.get('serial'),
            problem_description=request.form['problem']
        )
        db.session.add(order)
        db.session.flush()  # получаем order.id

        # Сохраняем фотографии
        if 'photos' in request.files:
            files = request.files.getlist('photos')
            for file in files:
                if file and file.filename:
                    filename = photos.save(file)
                    photo = OrderPhoto(order_id=order.id, filename=filename)
                    db.session.add(photo)

        db.session.commit()
        flash(f'Заявка №{order.id} успешно создана! Мы свяжемся с вами в ближайшее время.', 'success')
        return redirect(url_for('index'))
    return render_template('create_order.html')

@app.route('/orders')
def public_orders():
    """Публичная страница для просмотра статуса по номеру заказа (без авторизации)"""
    order_id = request.args.get('id')
    order = None
    if order_id:
        order = Order.query.get_or_404(order_id)
    return render_template('public_order_status.html', order=order)

@app.route('/order/<int:order_id>')
def order_detail(order_id):
    order = Order.query.get_or_404(order_id)
    # Доступ разрешён либо админу, либо владельцу заявки (если авторизован)
    if 'admin' in session:
        return render_template('order_detail.html', order=order)
    if current_user.is_authenticated and order.client_id == current_user.id:
        return render_template('order_detail.html', order=order)
    flash('У вас нет доступа к этой заявке', 'error')
    return redirect(url_for('index'))

# --- Каталог запчастей ---
@app.route('/parts')
def parts():
    all_parts = Part.query.all()
    return render_template('parts.html', parts=all_parts)

# --- Админка ---
@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        admin = Admin.query.filter_by(username=username, password=password).first()
        if admin:
            session['admin'] = username
            flash('Вход в админ-панель выполнен', 'success')
            return redirect(url_for('admin_panel'))
        flash('Неверный логин или пароль', 'error')
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    flash('Вы вышли из админ-панели', 'info')
    return redirect(url_for('index'))

@app.route('/admin/panel')
@admin_required
def admin_panel():
    orders_count = Order.query.count()
    parts_count = Part.query.count()
    recent_orders = Order.query.order_by(Order.created_at.desc()).limit(15).all()
    # Поиск
    search_query = request.args.get('q', '')
    if search_query:
        recent_orders = Order.query.filter(
            (Order.id == search_query) if search_query.isdigit() else
            (Order.client_name.contains(search_query) | Order.client_phone.contains(search_query))
        ).order_by(Order.created_at.desc()).all()
    return render_template('admin_panel.html',
                         orders_count=orders_count,
                         parts_count=parts_count,
                         recent_orders=recent_orders,
                         search_query=search_query)

@app.route('/admin/order/<int:order_id>')
@admin_required
def admin_order_detail(order_id):
    order = Order.query.get_or_404(order_id)
    checklist = DiagnosticChecklist.query.filter_by(order_id=order_id).first()
    if not checklist:
        checklist = DiagnosticChecklist(order_id=order_id)
        db.session.add(checklist)
        db.session.commit()
    return render_template('admin_order_detail.html', order=order, checklist=checklist)

@app.route('/admin/order/<int:order_id>/checklist', methods=['POST'])
@admin_required
def update_checklist(order_id):
    checklist = DiagnosticChecklist.query.filter_by(order_id=order_id).first()
    if not checklist:
        checklist = DiagnosticChecklist(order_id=order_id)
        db.session.add(checklist)
    checklist.power_on = 'power_on' in request.form
    checklist.display_ok = 'display_ok' in request.form
    checklist.touch_ok = 'touch_ok' in request.form
    checklist.buttons_ok = 'buttons_ok' in request.form
    checklist.charging_ok = 'charging_ok' in request.form
    checklist.wifi_ok = 'wifi_ok' in request.form
    checklist.notes = request.form.get('notes', '')
    db.session.commit()
    flash('Чек-лист диагностики обновлён', 'success')
    return redirect(url_for('admin_order_detail', order_id=order_id))

@app.route('/admin/order/<int:order_id>/status', methods=['POST'])
@admin_required
def update_status(order_id):
    order = Order.query.get_or_404(order_id)
    old_status = order.status
    new_status = request.form['status']
    comment = request.form.get('comment', '')

    if old_status != new_status:
        order.status = new_status
        history = RepairHistory(
            order_id=order_id,
            status_from=old_status,
            status_to=new_status,
            comment=comment
        )
        db.session.add(history)
        db.session.commit()

        # Отправка email клиенту
        if order.client_email and app.config['MAIL_USERNAME']:
            try:
                msg = Message(
                    f'Статус заявки №{order.id} изменён',
                    recipients=[order.client_email]
                )
                msg.body = f"""Уважаемый(ая) {order.client_name}!

Статус вашей заявки на ремонт устройства {order.device_model} изменён:
"{old_status}" → "{new_status}"

Комментарий мастера: {comment if comment else 'нет'}

С уважением,
Сервисный центр «ТехноСервис»
"""
                mail.send(msg)
                flash('Статус обновлён, клиент уведомлен по email', 'success')
            except Exception as e:
                flash(f'Статус обновлён, но письмо не отправлено: {e}', 'warning')
        else:
            flash('Статус обновлён', 'success')
    else:
        flash('Статус не изменился', 'info')
    return redirect(url_for('admin_order_detail', order_id=order_id))

@app.route('/admin/part/add', methods=['POST'])
@admin_required
def add_part():
    part = Part(
        name=request.form['name'],
        article=request.form.get('article', ''),
        price=float(request.form.get('price', 0)),
        quantity=int(request.form.get('quantity', 0)),
        description=request.form.get('description', '')
    )
    db.session.add(part)
    db.session.commit()
    flash('Комплектующее добавлено', 'success')
    return redirect(url_for('admin_panel'))

@app.route('/admin/part/delete/<int:part_id>')
@admin_required
def delete_part(part_id):
    part = Part.query.get_or_404(part_id)
    db.session.delete(part)
    db.session.commit()
    flash('Комплектующее удалено', 'success')
    return redirect(url_for('admin_panel'))

# --- API ---
class OrderListResource(Resource):
    def get(self):
        orders = Order.query.all()
        return jsonify([{
            'id': o.id,
            'client': o.client_name,
            'device': o.device_model,
            'status': o.status,
            'created': o.created_at.isoformat()
        } for o in orders])

api.add_resource(OrderListResource, '/api/orders')

# --- Создание админа по умолчанию (если нет) ---
def create_default_admin():
    with app.app_context():
        db.create_all()
        if not Admin.query.first():
            admin = Admin(username='admin', password='admin123')
            db.session.add(admin)
            db.session.commit()
            print('✅ Администратор создан: admin / admin123')

if __name__ == '__main__':
    create_default_admin()
    app.run(debug=False, host='0.0.0.0')