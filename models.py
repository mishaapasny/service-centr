from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class Client(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    name = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    registered_at = db.Column(db.DateTime, default=datetime.utcnow)
    orders = db.relationship('Order', backref='client', lazy=True)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=True)
    client_name = db.Column(db.String(100), nullable=False)
    client_phone = db.Column(db.String(20), nullable=False)
    client_email = db.Column(db.String(120))
    device_model = db.Column(db.String(100), nullable=False)
    serial_number = db.Column(db.String(50))
    problem_description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(50), default="Принят")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    photos = db.relationship('OrderPhoto', backref='order', lazy=True)
    checklist = db.relationship('DiagnosticChecklist', backref='order', uselist=False)
    history = db.relationship('RepairHistory', backref='order', lazy=True, order_by="desc(RepairHistory.timestamp)")

class OrderPhoto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    filename = db.Column(db.String(200))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

class DiagnosticChecklist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    power_on = db.Column(db.Boolean, default=False)
    display_ok = db.Column(db.Boolean, default=False)
    touch_ok = db.Column(db.Boolean, default=False)
    buttons_ok = db.Column(db.Boolean, default=False)
    charging_ok = db.Column(db.Boolean, default=False)
    wifi_ok = db.Column(db.Boolean, default=False)
    notes = db.Column(db.Text)

class RepairHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    status_from = db.Column(db.String(50))
    status_to = db.Column(db.String(50))
    comment = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class Part(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    article = db.Column(db.String(100))
    price = db.Column(db.Float, default=0)
    quantity = db.Column(db.Integer, default=0)
    description = db.Column(db.Text)

class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)