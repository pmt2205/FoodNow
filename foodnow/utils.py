from foodnow import app, db
from foodnow.models import User, UserRole, Restaurant, MenuItem, CartItem, Order, OrderDetail, Comment
from flask_login import current_user
from sqlalchemy import func
from datetime import datetime
import hashlib
import cloudinary.uploader


# ------------------- NGƯỜI DÙNG ------------------- #

def auth_user(username, password, role=None):
    """Xác thực đăng nhập người dùng"""
    hashed_pw = hashlib.md5(password.strip().encode('utf-8')).hexdigest()
    q = User.query.filter_by(username=username.strip(), password=hashed_pw)

    if role:
        q = q.filter(User.role == role)

    return q.first()


def add_user(name, username, password, phone=None, avatar=None, role=UserRole.CUSTOMER):
    """Đăng ký người dùng mới"""
    hashed_pw = hashlib.md5(password.strip().encode('utf-8')).hexdigest()
    user = User(name=name, username=username.strip(), password=hashed_pw, phone=phone, role=role)

    if avatar:
        res = cloudinary.uploader.upload(avatar)
        user.avatar = res.get('secure_url')

    db.session.add(user)
    db.session.commit()


# ------------------- NHÀ HÀNG & MÓN ĂN ------------------- #

def load_restaurants(keyword=None):
    """Lấy danh sách nhà hàng, lọc theo tên"""
    query = Restaurant.query
    if keyword:
        query = query.filter(Restaurant.name.ilike(f"%{keyword}%"))
    return query.all()


def get_restaurant_by_id(rid):
    """Lấy thông tin nhà hàng theo ID"""
    return Restaurant.query.get(rid)

def get_user_by_id(id):
    return User.query.get(id)


def load_menu_items(restaurant_id=None, keyword=None, price_from=None, price_to=None):
    """Lọc danh sách món ăn theo nhà hàng, từ khóa, giá"""
    query = MenuItem.query.filter_by(available=True)

    if restaurant_id:
        query = query.filter(MenuItem.restaurant_id == restaurant_id)
    if keyword:
        query = query.filter(MenuItem.name.ilike(f"%{keyword}%"))
    if price_from:
        query = query.filter(MenuItem.price >= price_from)
    if price_to:
        query = query.filter(MenuItem.price <= price_to)

    return query.all()


def get_menu_item_by_id(menu_item_id):
    return MenuItem.query.get(menu_item_id)


# ------------------- GIỎ HÀNG ------------------- #

def get_cart(user_id):
    """Lấy các món trong giỏ hàng của người dùng"""
    return CartItem.query.filter_by(user_id=user_id).all()


def add_to_cart(user_id, menu_item_id, quantity=1):
    """Thêm món vào giỏ hàng"""
    cart_item = CartItem.query.filter_by(user_id=user_id, menu_item_id=menu_item_id).first()
    if cart_item:
        cart_item.quantity += quantity
    else:
        cart_item = CartItem(user_id=user_id, menu_item_id=menu_item_id, quantity=quantity)
        db.session.add(cart_item)
    db.session.commit()


def remove_from_cart(user_id, menu_item_id):
    """Xoá món khỏi giỏ hàng"""
    CartItem.query.filter_by(user_id=user_id, menu_item_id=menu_item_id).delete()
    db.session.commit()


def clear_cart(user_id):
    """Xoá toàn bộ giỏ hàng"""
    CartItem.query.filter_by(user_id=user_id).delete()
    db.session.commit()


# ------------------- ĐƠN HÀNG ------------------- #

def save_order(user_id, restaurant_id):
    """Tạo đơn hàng từ giỏ hàng"""
    cart_items = get_cart(user_id)
    if not cart_items:
        return False

    total = sum(item.quantity * item.menu_item.price for item in cart_items)
    order = Order(user_id=user_id, restaurant_id=restaurant_id, total_amount=total)
    db.session.add(order)
    db.session.flush()

    for item in cart_items:
        od = OrderDetail(order_id=order.id, menu_item_id=item.menu_item_id,
                         quantity=item.quantity, price=item.menu_item.price)
        db.session.add(od)

    clear_cart(user_id)
    db.session.commit()
    return True


# ------------------- BÌNH LUẬN / ĐÁNH GIÁ ------------------- #

def load_comments(restaurant_id):
    """Lấy bình luận theo nhà hàng"""
    return Comment.query.filter_by(restaurant_id=restaurant_id).order_by(Comment.created_date.desc()).all()


def add_comment(content, rating, restaurant_id):
    """Thêm bình luận"""
    comment = Comment(content=content, rating=rating, restaurant_id=restaurant_id, user=current_user)
    db.session.add(comment)
    db.session.commit()
    return comment


# ------------------- THỐNG KÊ / ADMIN ------------------- #

def revenue_by_restaurant():
    """Thống kê doanh thu theo nhà hàng"""
    return db.session.query(
        Restaurant.name,
        func.sum(Order.total_amount).label('revenue')
    ).join(Order, Order.restaurant_id == Restaurant.id)\
     .group_by(Restaurant.name).all()


def order_stats_by_month(year=datetime.now().year):
    """Thống kê doanh thu theo tháng"""
    return db.session.query(
        func.extract('month', Order.created_date).label('month'),
        func.sum(Order.total_amount).label('revenue')
    ).filter(func.extract('year', Order.created_date) == year)\
     .group_by(func.extract('month', Order.created_date))\
     .order_by(func.extract('month', Order.created_date)).all()


if __name__ == '__main__':
    with app.app_context():
        print(revenue_time())