import hashlib

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from foodnow import db, app
from enum import Enum as RoleEnum
from flask_login import UserMixin
from datetime import datetime

# Vai trò người dùng
class UserRole(RoleEnum):
    ADMIN = 1
    CUSTOMER = 2
    RESTAURANT = 3

class BaseModel(db.Model):
    __abstract__ = True
    id = Column(Integer, primary_key=True, autoincrement=True)

# Người dùng
class User(BaseModel, UserMixin):
    __tablename__ = 'user'
    username = Column(String(100), nullable=False, unique=True)
    password = Column(String(100), nullable=False)
    name = Column(String(100), nullable=False)
    phone = Column(String(20), nullable=True)
    avatar = Column(String(255), default='https://default-avatar.com/default.jpg')
    role = Column(Enum(UserRole), default=UserRole.CUSTOMER)

    # Quan hệ
    orders = relationship('Order', backref='user', lazy=True)
    cart = relationship('CartItem', backref='user', lazy=True)
    comments = relationship('Comment', backref='user', lazy=True)

    def __str__(self):
        return self.name

# Nhà hàng
class Restaurant(BaseModel):
    __tablename__ = 'restaurant'
    name = Column(String(100), nullable=False)
    address = Column(String(255), nullable=False)
    phone = Column(String(20))
    image = Column(String(255), nullable=True)
    description = Column(String(255), nullable=True)

    menu_items = relationship('MenuItem', backref='restaurant', lazy=True)
    orders = relationship('Order', backref='restaurant', lazy=True)
    comments = relationship('Comment', backref='restaurant', lazy=True)

    def __str__(self):
        return self.name

# Món ăn trong menu
class MenuItem(BaseModel):
    __tablename__ = 'menu_item'
    name = Column(String(100), nullable=False)
    description = Column(String(255), nullable=True)
    price = Column(Float, nullable=False)
    available = Column(Boolean, default=True)
    image = Column(String(255), nullable=True)

    restaurant_id = Column(Integer, ForeignKey('restaurant.id'), nullable=False)
    order_details = relationship('OrderDetail', backref='menu_item', lazy=True)
    cart_items = relationship('CartItem', backref='menu_item', lazy=True)

    def __str__(self):
        return self.name

# Giỏ hàng tạm
class CartItem(BaseModel):
    __tablename__ = 'cart_item'
    quantity = Column(Integer, nullable=False, default=1)
    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    menu_item_id = Column(Integer, ForeignKey('menu_item.id'), nullable=False)

    def __str__(self):
        return f"{self.quantity} x {self.menu_item.name}"

# Đơn hàng
class Order(BaseModel):
    __tablename__ = 'order'
    created_date = Column(DateTime, default=datetime.now)
    status = Column(String(50), default='Đang xử lý')  # Đang xử lý, Đã xác nhận, Đang giao, Hoàn tất, Hủy
    total_amount = Column(Float, default=0)

    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    restaurant_id = Column(Integer, ForeignKey('restaurant.id'), nullable=False)

    order_details = relationship('OrderDetail', backref='order', lazy=True)

    def __str__(self):
        return f"Đơn hàng #{self.id} - {self.user.name}"

# Chi tiết đơn hàng
class OrderDetail(BaseModel):
    __tablename__ = 'order_detail'
    quantity = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)  # Đơn giá tại thời điểm đặt

    order_id = Column(Integer, ForeignKey('order.id'), nullable=False)
    menu_item_id = Column(Integer, ForeignKey('menu_item.id'), nullable=False)

    def __str__(self):
        return f"{self.quantity} x {self.menu_item.name} = {self.price * self.quantity}"

# Bình luận / Đánh giá
class Comment(BaseModel):
    __tablename__ = 'comment'
    content = Column(String(255), nullable=False)
    rating = Column(Integer, default=5)  # Số sao (1–5)
    created_date = Column(DateTime, default=datetime.now)

    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    restaurant_id = Column(Integer, ForeignKey('restaurant.id'), nullable=False)

    def __str__(self):
        return f"{self.user.name}: {self.content} ({self.rating}⭐)"

if __name__ == '__main__':
    with app.app_context():
        db.create_all()

        # Tạo admin
        admin = User(
            name='Admin',
            username='admin',
            password=hashlib.md5('123'.encode('utf-8')).hexdigest(),
            role=UserRole.ADMIN
        )
        db.session.add(admin)

        # Tạo khách hàng
        user = User(
            name='Nguyen Van A',
            username='nguyenvana',
            password=hashlib.md5('123456'.encode('utf-8')).hexdigest(),
            role=UserRole.CUSTOMER
        )
        db.session.add(user)

        # Tạo nhà hàng
        nha_hang = Restaurant(
            name='Nhà hàng Bếp Việt',
            address='123 Lê Lợi, Hà Nội',
            phone='0123456789',
            image='https://example.com/image1.jpg',
            description='Chuyên món Việt truyền thống'
        )
        db.session.add(nha_hang)
        db.session.commit()

        # Tạo món ăn
        mon1 = MenuItem(name='Phở bò', description='Phở truyền thống', price=40000, available=True,
                        restaurant_id=nha_hang.id)
        mon2 = MenuItem(name='Bún chả', description='Đặc sản Hà Nội', price=45000, available=True,
                        restaurant_id=nha_hang.id)
        mon3 = MenuItem(name='Nem rán', description='Nem truyền thống giòn tan', price=30000, available=True,
                        restaurant_id=nha_hang.id)
        db.session.add_all([mon1, mon2, mon3])
        db.session.commit()

        print("✅ Dữ liệu mẫu đã được tạo!")

