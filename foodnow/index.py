import sys, os, utils, requests, uuid, hmac, hashlib
from datetime import datetime
from sqlalchemy.sql import func

from pytz import timezone, utc

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from foodnow import app, db, login
from flask import render_template, request, redirect, url_for, session, flash
from flask_login import login_user, logout_user, login_required, current_user
from foodnow.models import Restaurant, MenuItem, CartItem, User, Order, OrderDetail, UserRole, Category, OrderStatus, Review
from werkzeug.utils import secure_filename
from flask_mail import Mail, Message

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'nguyenphu1999f@gmail.com'         # Thay bằng email của bạn
app.config['MAIL_PASSWORD'] = 'auie bsfh mvee mzvf'            # Mật khẩu ứng dụng (không phải mật khẩu Gmail)

mail = Mail(app)


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

@app.route('/my-restaurant', methods=['GET', 'POST'])
@login_required
def my_restaurant():
    if current_user.role != UserRole.RESTAURANT:
        return "Bạn không có quyền truy cập!", 403

    if request.method == 'POST':
        name = request.form.get('name')
        address = request.form.get('address')
        phone = request.form.get('phone')
        description = request.form.get('description')
        image = request.files.get('image')

        filename = None
        if image and image.filename != '':
            filename = secure_filename(image.filename)
            upload_path = os.path.join('static/images', filename)
            os.makedirs(os.path.dirname(upload_path), exist_ok=True)
            image.save(upload_path)

        restaurant = Restaurant(
            name=name,
            address=address,
            phone=phone,
            description=description,
            image='/' + upload_path if filename else None,
            user_id=current_user.id  # Gán user hiện tại làm chủ
        )
        db.session.add(restaurant)
        db.session.commit()
        return redirect(url_for('my_restaurant'))

    # GET: render form
    my_restaurants = Restaurant.query.filter_by(user_id=current_user.id).all()
    return render_template('my_restaurant.html', restaurants=my_restaurants)

@app.route('/manage-menu/<int:restaurant_id>', methods=['GET', 'POST'])
@login_required
def manage_menu(restaurant_id):
    restaurant = Restaurant.query.get_or_404(restaurant_id)

    if restaurant.user_id != current_user.id:
        return "Bạn không có quyền!", 403

    if request.method == 'POST':
        name = request.form.get('name')
        price = float(request.form.get('price'))  # ép float
        description = request.form.get('description')
        category_id = int(request.form.get('category_id'))

        image = request.files.get('image')
        filename = None
        if image and image.filename != '':
            filename = secure_filename(image.filename)
            upload_path = os.path.join('static/images', filename)
            os.makedirs(os.path.dirname(upload_path), exist_ok=True)
            image.save(upload_path)
            image_path = '/' + upload_path
        else:
            image_path = None

        menu_item = MenuItem(
            name=name,
            price=price,
            description=description,
            category_id=category_id,
            restaurant_id=restaurant.id,
            image=image_path
        )
        db.session.add(menu_item)
        db.session.commit()
        return redirect(url_for('manage_menu', restaurant_id=restaurant.id))

    menu_items = restaurant.menu_items
    categories = utils.load_categories()

    return render_template('manage_menu.html',
                           restaurant=restaurant,
                           menu_items=menu_items,
                           categories=categories)

from sqlalchemy.sql import func

@app.route('/restaurant/<int:rid>')
def view_menu(rid):
    restaurant = Restaurant.query.get_or_404(rid)
    menu = MenuItem.query.filter_by(restaurant_id=rid).all()

    # Tính trung bình sao
    avg_rating = db.session.query(func.avg(Review.rating))\
        .filter(Review.restaurant_id == rid).scalar()
    avg_rating = round(avg_rating, 1) if avg_rating else None

    # Kiểm tra user đã đặt hàng chưa
    has_ordered = False
    if current_user.is_authenticated:
        has_ordered = Order.query.filter_by(user_id=current_user.id, restaurant_id=rid).first() is not None

    return render_template('menu.html',
                           restaurant=restaurant,
                           menu=menu,
                           has_ordered=has_ordered,
                           average_rating=avg_rating)



@app.route('/submit-review/<int:restaurant_id>', methods=['POST'])
@login_required
def submit_review(restaurant_id):
    # Kiểm tra user đã từng đặt hàng tại nhà hàng này chưa
    has_ordered = Order.query.filter_by(
        user_id=current_user.id,
        restaurant_id=restaurant_id
    ).first()

    if not has_ordered:
        flash("Bạn chưa đặt hàng từ nhà hàng này.", "danger")
        return redirect(url_for('view_menu', rid=restaurant_id))

    # Không cần kiểm tra đánh giá trước đó nữa
    rating = int(request.form.get('rating'))
    comment = request.form.get('comment')

    review = Review(
        user_id=current_user.id,
        restaurant_id=restaurant_id,
        rating=rating,
        comment=comment
    )
    db.session.add(review)
    db.session.commit()

    flash("Cảm ơn bạn đã đánh giá!", "success")
    return redirect(url_for('view_menu', rid=restaurant_id))



@app.route('/add-to-cart/<int:menu_id>')
@login_required
def add_to_cart(menu_id):
    # Tìm xem món đã có trong giỏ chưa
    item = CartItem.query.filter_by(user_id=current_user.id, menu_item_id=menu_id).first()

    is_new_item = False
    if item:
        item.quantity += 1
    else:
        item = CartItem(user_id=current_user.id, menu_item_id=menu_id, quantity=1)
        db.session.add(item)
        is_new_item = True  # 🔸 Đánh dấu là món mới

    db.session.commit()

    # Nếu dùng AJAX bạn có thể return JSON tại đây
    # return jsonify({'new_item': is_new_item, 'cart_count': CartItem.query.filter_by(user_id=current_user.id).count()})

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

from flask_mail import Message

@app.route('/checkout', methods=['POST'])
@login_required
def checkout():
    cart = CartItem.query.filter_by(user_id=current_user.id).all()
    if not cart:
        return redirect(url_for('home'))

    address = request.form.get('address')
    phone = request.form.get('phone')

    restaurant_id = cart[0].menu_item.restaurant_id
    order = Order(user_id=current_user.id,
                  restaurant_id=restaurant_id,
                  status=OrderStatus.PENDING,
                  address=address,
                  phone=phone)
    db.session.add(order)
    db.session.commit()

    total = 0
    content_lines = []

    for item in cart:
        detail = OrderDetail(
            order_id=order.id,
            menu_item_id=item.menu_item.id,
            quantity=item.quantity,
            price=item.menu_item.price
        )
        db.session.add(detail)
        item_total = item.quantity * item.menu_item.price
        total += item_total
        content_lines.append(f"{item.menu_item.name} x {item.quantity} = {item_total:,} VNĐ")

    order.total = total
    db.session.commit()

    # Xóa giỏ hàng
    CartItem.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()

    # --- Gửi Email thông báo đơn hàng ---
    try:
        msg = Message("Xác nhận đơn hàng - FoodNow",
                      sender=app.config['MAIL_USERNAME'],
                      recipients=[current_user.email])
        msg.body = f"""Chào {current_user.name},

Bạn đã đặt hàng thành công tại FoodNow.

Chi tiết đơn hàng:
{chr(10).join(content_lines)}

Tổng cộng: {total:,} VNĐ
Địa chỉ giao hàng: {address}
Số điện thoại: {phone}

Cảm ơn bạn đã sử dụng dịch vụ!
        """
        mail.send(msg)
    except Exception as e:
        print("Không gửi được mail:", str(e))
    flash("Đơn hàng đã được đặt thành công. Vui lòng kiểm tra email để xem chi tiết đơn hàng.", "success")

    return redirect(url_for('home'))

@app.route('/order/<int:order_id>')
@login_required
def view_order_detail(order_id):
    order = Order.query.filter_by(id=order_id, user_id=current_user.id).first()
    if not order:
        return "Không tìm thấy đơn hàng.", 404
    return render_template('order_detail.html', order=order)

@app.route('/my-orders')
@login_required
def my_orders():
    if current_user.role != UserRole.RESTAURANT:
        return "Bạn không có quyền truy cập!", 403

    # Lấy danh sách nhà hàng thuộc user này
    restaurants = Restaurant.query.filter_by(user_id=current_user.id).all()
    restaurant_ids = [r.id for r in restaurants]

    # Lấy đơn hàng thuộc các nhà hàng đó
    orders = Order.query.filter(Order.restaurant_id.in_(restaurant_ids)) \
                        .order_by(Order.created_at.desc()).all()

    return render_template('restaurant_orders.html', orders=orders)

@app.route('/update-order-status/<int:order_id>', methods=['POST'])
@login_required
def update_order_status(order_id):
    if current_user.role.name != 'RESTAURANT':
        flash("Không có quyền.", "danger")
        return redirect(url_for('restaurant_orders'))

    order = Order.query.get_or_404(order_id)

    # Lấy danh sách id nhà hàng của user
    user_restaurant_ids = [r.id for r in current_user.restaurants]

    # Kiểm tra đơn hàng có thuộc nhà hàng của user hay không
    if order.restaurant_id not in user_restaurant_ids:
        flash("Không thể sửa đơn hàng không thuộc nhà hàng bạn.", "danger")
        return redirect(url_for('restaurant_orders'))

    # Lấy trạng thái mới từ form
    new_status = request.form.get('status')
    try:
        order.status = OrderStatus[new_status]
        db.session.commit()
        flash("Cập nhật trạng thái thành công.", "success")
    except KeyError:
        flash("Trạng thái không hợp lệ.", "danger")

    return redirect(url_for('my_orders'))




@app.template_filter('vntime')
def vntime(utc_dt, fmt='%d/%m/%Y %H:%M'):
    if not utc_dt:
        return ''

    # Gắn timezone UTC nếu chưa có (naive datetime)
    if utc_dt.tzinfo is None:
        utc_dt = utc.localize(utc_dt)

    vn = timezone('Asia/Ho_Chi_Minh')
    return utc_dt.astimezone(vn).strftime(fmt)


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

@app.route('/login-admin', methods=['post'])
def login_admin_process():
    username = request.form.get('username')
    password = request.form.get('password')
    user = utils.auth_user(username=username, password=password, role=UserRole.ADMIN)
    if user:
        login_user(user)

    return redirect('/admin')

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

            role = data.get('role')
            if role == 'ADMIN':
                error_msg = 'Không thể đăng ký tài khoản Admin!'
                return render_template('register.html', err_msg=error_msg)

            avatar = request.files.get('avatar')

            try:
                utils.add_user(avatar=avatar, **data)  # data sẽ có cả email
                return redirect(url_for('login_process'))
            except Exception as ex:
                error_msg = f'Lỗi khi đăng ký: {ex}'
        else:
            error_msg = 'Mật khẩu xác nhận không khớp!'

    return render_template('register.html', err_msg=error_msg)

@login.user_loader
def load_user(user_id):
    return utils.get_user_by_id(user_id)

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
            name = request.form.get('name')
            phone = request.form.get('phone')
            dob = request.form.get('dob')
            email = request.form.get('email', '').strip()

            if not email:
                error_msg = 'Email không được để trống!'
            else:
                # Kiểm tra email đã được tài khoản khác sử dụng chưa
                existing_user = User.query.filter(User.email == email, User.id != user.id).first()
                if existing_user:
                    error_msg = 'Đã có tài khoản sử dụng địa chỉ email này!'
                else:
                    user.name = name
                    user.phone = phone
                    user.dob = dob
                    user.email = email

                    avatar = request.files.get('avatar')
                    if avatar and avatar.filename != '':
                        filename = secure_filename(avatar.filename)
                        upload_path = os.path.join('static/images', filename)
                        os.makedirs(os.path.dirname(upload_path), exist_ok=True)
                        avatar.save(upload_path)
                        user.avatar = '/' + upload_path

                    db.session.commit()
                    success_msg = 'Cập nhật thông tin thành công!'

    if tab == 'orders':
        orders = Order.query.filter_by(user_id=user.id).all()
    return render_template('profile.html', user=user, tab=tab, orders=orders,
                           error_msg=error_msg, success_msg=success_msg)


@app.route('/menu_item/edit/<int:item_id>', methods=['GET', 'POST'])
@login_required
def edit_menu_item(item_id):
    item = MenuItem.query.get_or_404(item_id)
    categories = Category.query.all()

    if request.method == 'POST':
        item.name = request.form['name']
        item.price = request.form['price']
        item.description = request.form['description']
        item.category_id = request.form['category_id']

        image_file = request.files.get('image')
        if image_file and image_file.filename != '':
            # TODO: upload image logic here (cloudinary or local) then set item.image
            pass

        db.session.commit()
        return redirect(url_for('manage_menu', restaurant_id=item.restaurant_id))

    return render_template('edit_menu_item.html', item=item, categories=categories)

@app.route('/edit_restaurant/<int:restaurant_id>', methods=['GET', 'POST'])
def edit_restaurant(restaurant_id):
    restaurant = Restaurant.query.get_or_404(restaurant_id)

    if request.method == 'POST':
        restaurant.name = request.form.get('name')
        restaurant.address = request.form.get('address')
        restaurant.phone = request.form.get('phone')
        restaurant.description = request.form.get('description')

        # Nếu có upload ảnh mới
        image = request.files.get('image')
        if image and image.filename != '':
            # ⚠️ Triển khai upload lên Cloudinary/S3 hoặc lưu local tuỳ dự án
            # Ví dụ lưu local:
            image_path = f'static/uploads/{image.filename}'
            image.save(image_path)
            restaurant.image = '/' + image_path

        db.session.commit()
        flash('Cập nhật nhà hàng thành công.', 'success')
        return redirect(url_for('my_restaurant'))

    return render_template('edit_restaurant.html', restaurant=restaurant)

@app.route('/menu_item/delete/<int:item_id>', methods=['POST'])
@login_required
def delete_menu_item(item_id):
    item = MenuItem.query.get_or_404(item_id)
    restaurant_id = item.restaurant_id
    db.session.delete(item)
    db.session.commit()
    return redirect(url_for('manage_menu', restaurant_id=restaurant_id))

@app.route('/delete_restaurant/<int:restaurant_id>', methods=['POST'])
def delete_restaurant(restaurant_id):
    restaurant = Restaurant.query.get_or_404(restaurant_id)
    db.session.delete(restaurant)
    db.session.commit()
    flash('Xóa nhà hàng thành công.', 'success')
    return redirect(url_for('my_restaurant'))

@app.context_processor
def inject_common():
    return dict(restaurants=Restaurant.query.all())

@app.context_processor
def inject_cart_count():
    count = 0
    if current_user.is_authenticated:
        count = CartItem.query.filter_by(user_id=current_user.id).count()
    return dict(cart_count=count)


if __name__ == '__main__':
    with app.app_context():
        from foodnow import admin
        app.run(debug=True)
