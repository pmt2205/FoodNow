import math
from foodnow import app, db, login
from flask import render_template, request, redirect, url_for, session, jsonify
import utils
from flask_login import login_user, logout_user, login_required, current_user
from foodnow.models import Restaurant, MenuItem, CartItem, User, Order, OrderDetail
from datetime import datetime
import json
import requests
import uuid
import hmac
import hashlib


@app.route('/pay/momo')
@login_required
def pay_with_momo():
    endpoint = "https://test-payment.momo.vn/v2/gateway/api/create"
    partner_code = "MOMO"
    access_key = "F8BBA842ECF85"
    secret_key = "K951B6PE1waDMi640xX08PD3vg6EkVlz"

    order_id = str(uuid.uuid4())
    request_id = str(uuid.uuid4())
    amount = "1000"
    order_info = "Thanh toán đơn hàng qua Momo"
    redirect_url = "https://your-ngrok-url.ngrok.io/payment-success"
    ipn_url = "https://your-ngrok-url.ngrok.io/momo_ipn"
    extra_data = ""
    request_type = "captureWallet"

    raw_signature = f"accessKey={access_key}&amount={amount}&extraData={extra_data}&ipnUrl={ipn_url}&orderId={order_id}&orderInfo={order_info}&partnerCode={partner_code}&redirectUrl={redirect_url}&requestId={request_id}&requestType={request_type}"
    signature = hmac.new(secret_key.encode(), raw_signature.encode(), hashlib.sha256).hexdigest()

    data = {
        "partnerCode": partner_code,
        "accessKey": access_key,
        "requestId": request_id,
        "amount": amount,
        "orderId": order_id,
        "orderInfo": order_info,
        "redirectUrl": redirect_url,
        "ipnUrl": ipn_url,
        "extraData": extra_data,
        "requestType": request_type,
        "signature": signature,
        "lang": "vi"
    }

    print("Payload gửi lên:", data)

    response = requests.post(endpoint, json=data)
    res_data = response.json()
    print("Phản hồi từ Momo:", res_data)

    if 'payUrl' not in res_data:
        return f"Lỗi từ Momo: {res_data.get('message', 'Không xác định')} - Chi tiết: {res_data}", 400

    return redirect(res_data['payUrl'])


@app.route('/payment-success')
def payment_success():
    # có thể lấy params từ request.args để xử lý thêm
    return "Thanh toán thành công! 🎉"


@app.route('/momo_ipn', methods=['POST'])
def momo_ipn():
    # Momo sẽ gọi lại endpoint này để xác nhận đơn hàng
    data = request.json
    print("Momo IPN callback:", data)

    # TODO: xác minh chữ ký nếu cần, cập nhật DB đơn hàng v.v.
    return '', 200  # trả về 200 OK để Momo biết đã nhận


@app.route('/')
def home():
    hero_images = [
        "https://images.unsplash.com/photo-1504674900247-0877df9cc836?q=80&w=2070&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1414235077428-338989a2e8c0?q=80&w=2070&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1555939594-58d7cb561ad1?q=80&w=2070&auto=format&fit=crop"
    ]
    return render_template("index.html", hero_images=hero_images)


@app.route('/search', methods=['GET'])
def search():
    keyword = request.args.get('keyword', '').strip()
    price_from = request.args.get('price_from', type=float)
    price_to = request.args.get('price_to', type=float)
    address = request.args.get('address', '').strip()
    category_id = request.args.get('category_id', type=int)

    menu_items = []
    restaurants = []

    if category_id:
        menu_items = utils.load_menu_items(category_id=category_id)
    elif price_from or price_to:
        menu_items = utils.load_menu_items(keyword=keyword, price_from=price_from, price_to=price_to)
    elif address:
        restaurants = utils.load_restaurants(address=address, keyword=keyword)
    elif keyword:
        menu_items = utils.load_menu_items(keyword=keyword)
        restaurants = utils.load_restaurants(keyword=keyword)
    else:
        menu_items = utils.load_menu_items()
        restaurants = utils.load_restaurants()

    categories = utils.load_categories()

    return render_template('search.html',
                           menu_items=menu_items,
                           restaurants=restaurants,
                           categories=categories,
                           selected_category_id=category_id,
                           query=keyword)


@app.route('/restaurant')
def restaurant():
    restaurants = Restaurant.query.all()
    return render_template('restaurant.html', restaurants=restaurants)


@app.route('/restaurant/<int:rid>')
def view_menu(rid):
    res = Restaurant.query.get(rid)
    if not res:
        return "Không tìm thấy nhà hàng!", 404
    return render_template('menu.html', restaurant=res, menu=res.menu_items)


@app.route('/add-to-cart/<int:menu_id>')
@login_required
def add_to_cart(menu_id):
    item = CartItem.query.filter_by(user_id=current_user.id, menu_item_id=menu_id).first()
    if item:
        item.quantity += 1
    else:
        item = CartItem(user_id=current_user.id, menu_item_id=menu_id, quantity=1)
        db.session.add(item)
    db.session.commit()
    return redirect(url_for('view_cart'))


@app.route('/cart')
@login_required
def view_cart():
    cart = CartItem.query.filter_by(user_id=current_user.id).all()
    total_price = sum(item.menu_item.price * item.quantity for item in cart)
    shipping_fee = 15000
    return render_template('cart.html',
                           cart=cart,
                           total_price=total_price,
                           shipping_fee=shipping_fee)


@app.route('/cart/update/<int:cart_id>/<change>')
@login_required
def update_cart_quantity(cart_id, change):
    try:
        change = int(change)
    except ValueError:
        return redirect(url_for('view_cart'))  # fallback nếu change không hợp lệ

    item = CartItem.query.get_or_404(cart_id)
    item.quantity = max(1, item.quantity + change)
    db.session.commit()
    return redirect(url_for('view_cart'))


@app.route('/cart/remove/<int:cart_id>')
@login_required
def remove_from_cart(cart_id):
    item = CartItem.query.get_or_404(cart_id)

    db.session.delete(item)
    db.session.commit()
    return redirect(url_for('view_cart'))


@app.route('/checkout', methods=['POST'])
@login_required
def checkout():
    cart = CartItem.query.filter_by(user_id=current_user.id).all()
    if not cart:
        return redirect(url_for('home'))

    restaurant_id = cart[0].menu_item.restaurant_id
    order = Order(user_id=current_user.id, restaurant_id=restaurant_id, status='Đang xử lý')
    db.session.add(order)
    db.session.commit()

    for item in cart:
        detail = OrderDetail(
            order_id=order.id,
            menu_item_id=item.menu_item.id,
            quantity=item.quantity,
            price=item.menu_item.price
        )
        db.session.add(detail)

    order.calculate_total()
    CartItem.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()

    return redirect(url_for('home'))


@app.route('/login', methods=['GET', 'POST'])
def login_process():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = utils.auth_user(username=username, password=password)
        if user:
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('home'))

    return render_template('login.html')


@app.route('/logout')
def logout_process():
    logout_user()
    return redirect(url_for('home'))


@app.route('/register', methods=['GET', 'POST'])
def register_process():
    error_msg = ''
    if request.method == 'POST':
        password = request.form.get('password')
        confirm = request.form.get('confirm')

        if password == confirm:
            data = request.form.copy()
            del data['confirm']
            avatar = request.files.get('avatar')
            utils.add_user(avatar=avatar, **data)
            return redirect(url_for('login_process'))
        else:
            error_msg = 'Mật khẩu xác nhận không khớp!'

    return render_template('register.html', err_msg=error_msg)


@login.user_loader
def load_user(user_id):
    return utils.get_user_by_id(user_id)


import os
from werkzeug.utils import secure_filename
import hashlib


@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    tab = request.args.get('tab', 'info')
    user = current_user
    error_msg = ''
    success_msg = ''
    orders = []

    if request.method == 'POST':
        if tab == 'info':
            # Xử lý cập nhật thông tin cá nhân
            name = request.form.get('name')
            phone = request.form.get('phone')
            dob = request.form.get('dob')
            avatar = request.files.get('avatar')

            user.name = name
            user.phone = phone
            user.dob = dob

            if avatar and avatar.filename != '':
                filename = secure_filename(avatar.filename)
                upload_path = os.path.join('static/images', filename)
                os.makedirs(os.path.dirname(upload_path), exist_ok=True)
                avatar.save(upload_path)
                user.avatar = '/' + upload_path

            db.session.commit()
            success_msg = 'Cập nhật thông tin thành công!'

        elif tab == 'security':
            # Xử lý đổi mật khẩu
            old_password = request.form.get('old_password')
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')

            old_hash = hashlib.md5(old_password.encode('utf-8')).hexdigest()
            if user.password != old_hash:
                error_msg = 'Mật khẩu cũ không đúng!'
            elif new_password != confirm_password:
                error_msg = 'Mật khẩu mới không khớp!'
            else:
                user.password = hashlib.md5(new_password.encode('utf-8')).hexdigest()
                db.session.commit()
                success_msg = 'Đổi mật khẩu thành công!'

    if tab == 'orders':
        orders = Order.query.filter_by(user_id=user.id).all()

    return render_template('profile.html', user=user, tab=tab, orders=orders,
                           error_msg=error_msg, success_msg=success_msg)


@app.context_processor
def inject_common():
    return dict(restaurants=Restaurant.query.all())


if __name__ == '__main__':
    with app.app_context():
        app.run(debug=True)
