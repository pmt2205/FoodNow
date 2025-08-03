import hashlib
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from enum import Enum as RoleEnum
from enum import Enum as RestaurantStatusEnum
from enum import Enum as StatusEnum
from FoodNow import db, app
from flask_login import UserMixin
from datetime import datetime
from sqlalchemy.types import Enum as SQLAlchemyEnum


# Vai trò người dùng
class UserRole(RoleEnum):
    ADMIN = "ADMIN"
    CUSTOMER = "CUSTOMER"
    RESTAURANT = "RESTAURANT"


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
    email = Column(String(100), nullable=False, unique=True)
    address = Column(String(255), nullable=True)
    avatar = Column(String(255), default='https://default-avatar.com/default.jpg')
    role = Column(Enum(UserRole), default=UserRole.CUSTOMER)

    # Quan hệ
    orders = relationship('Order', backref='user', lazy=True)
    cart = relationship('CartItem', backref='user', lazy=True)
    restaurants = relationship('Restaurant', backref='owner', lazy=True)
    reviews = db.relationship('Review', back_populates='user', lazy=True)
    def __str__(self):
        return self.name


class RestaurantStatus(RestaurantStatusEnum):
    PENDING = "Pending"
    APPROVED = "Approved"
    REJECTED = "Rejected"

class Restaurant(BaseModel):
    __tablename__ = 'restaurant'
    name = Column(String(100), nullable=False)
    address = Column(String(255), nullable=False)
    phone = Column(String(20))
    image = Column(String(255), nullable=True)
    description = Column(String(255), nullable=True)
    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    status = Column(SQLAlchemyEnum(RestaurantStatus, name="restaurant_status"), default=RestaurantStatus.PENDING)
    reviews = db.relationship('Review', back_populates='restaurant', lazy=True)
    menu_items = relationship('MenuItem', backref='restaurant', lazy=True)
    orders = relationship('Order', backref='restaurant', lazy=True)

    def __str__(self):
        return self.name

# Danh mục món ăn
class Category(BaseModel):
    __tablename__ = 'category'
    name = Column(String(100), nullable=False, unique=True)

    menu_items = relationship('MenuItem', backref='category', lazy=True)

    def __str__(self):
        return self.name

# Cập nhật MenuItem để thêm category_id
class MenuItem(BaseModel):
    __tablename__ = 'menu_item'
    name = Column(String(100), nullable=False)
    description = Column(String(255), nullable=True)
    price = Column(Float, nullable=False)
    available = Column(Boolean, default=True)
    image = Column(String(255), nullable=True)

    restaurant_id = Column(Integer, ForeignKey('restaurant.id', ondelete='CASCADE'), nullable=False)
    category_id = Column(Integer, ForeignKey('category.id'), nullable=False)

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


class OrderStatus(StatusEnum):
    PENDING = 'Đang xử lý'
    COMPLETED = 'Hoàn tất'
    CANCELLED = 'Đã hủy'
# Đơn hàng
class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey(User.id))
    restaurant_id = db.Column(db.Integer, db.ForeignKey(Restaurant.id))
    status = db.Column(db.Enum(OrderStatus), default=OrderStatus.PENDING, nullable=False)
    total = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    address = db.Column(db.String(255))
    phone = db.Column(db.String(20))

    details = db.relationship('OrderDetail', backref='order', lazy=True)

    def calculate_total(self):
        self.total = sum(d.price * d.quantity for d in self.details)


# Chi tiết đơn hàng
class OrderDetail(BaseModel):
    __tablename__ = 'order_detail'
    quantity = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)  # Đơn giá tại thời điểm đặt

    order_id = Column(Integer, ForeignKey('order.id'), nullable=False)
    menu_item_id = Column(Integer, ForeignKey('menu_item.id', ondelete='SET NULL'), nullable=True)

    def __str__(self):
        return f"{self.quantity} x {self.menu_item.name} = {self.price * self.quantity}"

# Bình luận / Đánh giá
class Review(BaseModel):
    __tablename__ = 'review'
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    restaurant_id = db.Column(db.Integer, db.ForeignKey('restaurant.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


    user = relationship('User', back_populates='reviews')
    restaurant = relationship('Restaurant', back_populates='reviews')



if __name__ == '__main__':
    with app.app_context():
        db.create_all()

        # Tạo admin
        admin = User(
            name='Admin',
            username='admin',
            password=hashlib.md5('123'.encode('utf-8')).hexdigest(),
            email='admin@gmail.com',
            role=UserRole.ADMIN
        )
        db.session.add(admin)

        # Tạo khách hàng
        user = User(
            name='Nguyen Van A',
            username='nguyenvana',
            password=hashlib.md5('123456'.encode('utf-8')).hexdigest(),
            email='nguyenvana@gmail.com',
            role=UserRole.CUSTOMER
        )
        db.session.add(user)

        user1 = User(
            name='Nguyen Van A',
            username='res1',
            password=hashlib.md5('123'.encode('utf-8')).hexdigest(),
            email='nguyenvanaa@gmail.com',
            role=UserRole.RESTAURANT
        )
        db.session.add(user1)


        # Tạo danh mục món ăn
        cat_viet = Category(name='Món Việt')
        cat_trang_mieng = Category(name='Tráng miệng')
        cat_nuoc_uong = Category(name='Nước uống')
        db.session.add_all([cat_viet, cat_trang_mieng, cat_nuoc_uong])
        db.session.commit()

        # Tạo nhà hàng
        nha_hang = Restaurant(
            name='Nhà hàng Bếp Việt',
            address='123 Lê Lợi, Hà Nội',
            phone='0123456789',
            image='...',
            description='Chuyên món Việt truyền thống',
            user_id=user1.id
        )

        db.session.add(nha_hang)
        db.session.commit()
        #
        # # Thêm 6 nhà hàng mới
        # nha_hang2 = Restaurant(
        #     name='Nhà hàng Sushi Tokyo',
        #     address='45 Trần Hưng Đạo, Hà Nội',
        #     phone='0987654321',
        #     image='https://res.cloudinary.com/dwc0l2bty/image/upload/v1753116484/97c57bbf0035f16ba8241-min_h4tu9i.jpg',
        #     description='Sushi Nhật Bản tươi ngon'
        # )
        #
        # nha_hang3 = Restaurant(
        #     name='Nhà hàng Pizza Ý',
        #     address='78 Nguyễn Huệ, TP HCM',
        #     phone='0912345678',
        #     image='https://res.cloudinary.com/dwc0l2bty/image/upload/v1753116564/nha-hang-y-pizza-company_ciwvnd.jpg',
        #     description='Pizza phong cách Ý đích thực'
        # )
        #
        # nha_hang4 = Restaurant(
        #     name='Nhà hàng Lẩu Thái',
        #     address='12 Lê Duẩn, Đà Nẵng',
        #     phone='0933221144',
        #     image='https://res.cloudinary.com/dwc0l2bty/image/upload/v1753116564/nha-hang-thai-blah-blah-5-_2_f3ko7s.jpg',
        #     description='Lẩu Thái chua cay đặc trưng'
        # )
        #
        # nha_hang5 = Restaurant(
        #     name='Nhà hàng Chay An Lạc',
        #     address='56 Phan Đình Phùng, Huế',
        #     phone='0977554433',
        #     image='https://res.cloudinary.com/dwc0l2bty/image/upload/v1753116562/photo3jpg_v9dhfw.jpg',
        #     description='Ẩm thực chay thanh tịnh'
        # )
        #
        # nha_hang6 = Restaurant(
        #     name='Nhà hàng Bún Đậu Mắm Tôm',
        #     address='34 Hoàng Diệu, Hà Nội',
        #     phone='0909888777',
        #     image='https://res.cloudinary.com/dwc0l2bty/image/upload/v1753116603/top-16-quan-bun-dau-mam-tom-ngon-ngat-ngay-luon-dong-khach-o-tphcm-202206021518475117_qhdijg.jpg',
        #     description='Đặc sản bún đậu mắm tôm miền Bắc'
        # )
        #
        # nha_hang7 = Restaurant(
        #     name='Nhà hàng BBQ Hàn Quốc',
        #     address='89 Cách Mạng Tháng 8, TP HCM',
        #     phone='0944665588',
        #     image='https://res.cloudinary.com/dwc0l2bty/image/upload/v1753116604/tong-hop-10-quan-do-nuong-han-quoc-noi-tieng-o-sai-gon-ma-ban-can-phai-biet-202108281532058402_tnqcqo.jpg',
        #     description='Thịt nướng Hàn Quốc chuẩn vị'
        # )
        #
        # db.session.add_all([nha_hang2, nha_hang3, nha_hang4, nha_hang5, nha_hang6, nha_hang7])
        # db.session.commit()
        #
        # # Thêm 10 món ăn mới với ảnh mới
        # mon4 = MenuItem(
        #     name='Sushi cá hồi', description='Sushi tươi ngon', price=60000, available=True,
        #     image='https://images.unsplash.com/photo-1562158070-57f8a5f9aeb2',
        #     restaurant_id=nha_hang2.id, category_id=cat_viet.id)
        #
        # mon5 = MenuItem(
        #     name='Pizza Margherita', description='Pizza truyền thống Ý', price=80000, available=True,
        #     image='https://images.unsplash.com/photo-1601925269935-1cdd60b1aa81',
        #     restaurant_id=nha_hang3.id, category_id=cat_viet.id)
        #
        # mon6 = MenuItem(
        #     name='Lẩu Thái Tomyum', description='Lẩu Tomyum cay nồng', price=120000, available=True,
        #     image='https://images.unsplash.com/photo-1613145991022-66f1a3e6a0eef',
        #     restaurant_id=nha_hang4.id, category_id=cat_viet.id)
        #
        # mon7 = MenuItem(
        #     name='Đậu hũ kho nấm', description='Món chay thanh đạm', price=30000, available=True,
        #     image='https://images.unsplash.com/photo-1590402494682-cd6846dbcf57',
        #     restaurant_id=nha_hang5.id, category_id=cat_viet.id)
        #
        # mon8 = MenuItem(
        #     name='Bún đậu mắm tôm', description='Đặc sản Hà Nội', price=35000, available=True,
        #     image='https://images.unsplash.com/photo-1615626713525-4e0d0a09e384',
        #     restaurant_id=nha_hang6.id, category_id=cat_viet.id)
        #
        # mon9 = MenuItem(
        #     name='Thịt ba chỉ nướng', description='Ba chỉ nướng kiểu Hàn', price=90000, available=True,
        #     image='https://images.unsplash.com/photo-1562059390-a761a084768e',
        #     restaurant_id=nha_hang7.id, category_id=cat_viet.id)
        #
        # mon10 = MenuItem(
        #     name='Canh rong biển', description='Canh rong biển Hàn Quốc', price=25000, available=True,
        #     image='https://images.unsplash.com/photo-1635827864807-f85f8b7d2e0b',
        #     restaurant_id=nha_hang7.id, category_id=cat_viet.id)
        #
        # mon11 = MenuItem(
        #     name='Kimchi', description='Kimchi cay Hàn Quốc', price=15000, available=True,
        #     image='https://images.unsplash.com/photo-1589302168068-964664d93dc0',
        #     restaurant_id=nha_hang7.id, category_id=cat_viet.id)

        mon12 = MenuItem(
            name='Chè khúc bạch', description='Tráng miệng mát lạnh', price=25000, available=True,
            image='https://images.unsplash.com/photo-1609758560942-986c697b84da',
            restaurant_id=nha_hang.id, category_id=cat_trang_mieng.id)

        mon13 = MenuItem(
            name='Sinh tố bơ', description='Sinh tố bơ béo ngậy', price=30000, available=True,
            image='https://images.unsplash.com/photo-1615486369604-6cc8e9ae4a8b',
            restaurant_id=nha_hang.id, category_id=cat_nuoc_uong.id)
        # mon4, mon5, mon6, mon7, mon8, mon9, mon10, mon11,
        db.session.add_all([ mon12, mon13])
        db.session.commit()

        print("✅ Đã thêm 6 nhà hàng và 10 món ăn mới!")


