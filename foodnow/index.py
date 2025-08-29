import sys, os, utils, requests, uuid, hmac, hashlib
from datetime import datetime,date
from sqlalchemy.sql import func
import re
from pytz import timezone, utc

from foodnow.admin import CouponAdmin

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from foodnow import app, db, login
from flask import render_template, request, redirect, url_for, session, flash, Flask, jsonify
from flask_login import login_user, logout_user, login_required, current_user, LoginManager
from foodnow.models import Restaurant, MenuItem, CartItem, User, Order, OrderDetail, UserRole, Category, OrderStatus, \
    Review,Coupon,Notification,UserCoupon
from werkzeug.utils import secure_filename
from flask_mail import Mail, Message
from flask_dance.contrib.google import make_google_blueprint, google

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'nguyenphu1999f@gmail.com'  # Thay bằng email của bạn
app.config['MAIL_PASSWORD'] = 'auie bsfh mvee mzvf'  # Mật khẩu ứng dụng (không phải mật khẩu Gmail)
mail = Mail(app)
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# Cấu hình Google OAuth
google_bp = make_google_blueprint(

    redirect_to='google_login',
    scope=[
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
        "openid"
    ]
)
app.register_blueprint(google_bp, url_prefix="/login")

login_manager = LoginManager(app)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))  # hoặc get_user_by_id(user_id)

@app.route('/google')
def google_login():
    if not google.authorized:
        return redirect(url_for("google.login"))

    resp = google.get("/oauth2/v2/userinfo")
    if not resp.ok:
        flash("Không thể lấy thông tin từ Google", "danger")
        return redirect(url_for("login"))

    info = resp.json()
    print("Google user info:", info)  # ✅ In ra để debug

    # Xử lý email fallback
    email = info.get("email")
    if not email:
        email = f'{info["id"]}@google.local'  # Tạo email giả nếu thiếu
        flash("Google không cấp email, sử dụng tạm.", "warning")

    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(
            name=info.get("name", "Google User"),
            email=email,
            username=f'google_{info["id"]}',
            password='',  # Không cần mật khẩu
            avatar=info.get("picture")
        )
        db.session.add(user)
        db.session.commit()

    login_user(user)
    return redirect(url_for('home'))

# ===== ZALOPAY (SANDBOX) CONFIG =====
ZALO_APP_ID = 2554
ZALO_KEY1  = "sdngKKJmqEMzvh5QQcdD2A9XBSKUNaYn"
ZALO_KEY2  = "trMrHtvjo6myautxDUiAcYsVtaeQ8nhf"
ZALO_CREATE_ORDER_URL = "https://sb-openapi.zalopay.vn/v2/create"

import json, time

def make_app_trans_id(order_id: int) -> str:
    return datetime.now().strftime("%y%m%d") + "_" + str(order_id)

@app.route("/create_zalopay_payment/<int:order_id>")
@login_required
def create_zalopay_payment(order_id):
    order = Order.query.get_or_404(order_id)

    app_id = ZALO_APP_ID
    app_user = str(current_user.id)
    app_time = int(time.time() * 1000)
    app_trans_id = make_app_trans_id(order.id)
    amount = int(order.total)

    # ZP sẽ redirect về redirecturl trong embed_data sau khi thanh toán
    redirect_url = url_for("payment_return_zalopay", order_id=order.id, _external=True)
    callback_url = url_for("zalopay_ipn", _external=True)

    embed_data = json.dumps({
        "redirecturl": redirect_url,
        # bạn có thể nhét thêm thông tin nhẹ tại đây nếu muốn
    }, ensure_ascii=False)

    # item: danh sách món (chuỗi JSON). Có thể tối giản []
    order_items = []
    for d in OrderDetail.query.filter_by(order_id=order.id).all():
        order_items.append({
            "itemid": d.menu_item_id,
            "itemname": d.menu_item.name,
            "itemprice": int(d.price),
            "itemquantity": int(d.quantity)
        })
    item = json.dumps(order_items, ensure_ascii=False)

    description = f"FoodNow - Order #{order.id}"

    # 2) Tính MAC bằng key1: app_id|app_trans_id|app_user|amount|app_time|embed_data|item
    data_mac = f"{app_id}|{app_trans_id}|{app_user}|{amount}|{app_time}|{embed_data}|{item}"
    mac = hmac.new(ZALO_KEY1.encode("utf-8"), data_mac.encode("utf-8"), hashlib.sha256).hexdigest()

    payload = {
        "app_id": app_id,
        "app_user": app_user,
        "app_time": app_time,
        "amount": amount,
        "app_trans_id": app_trans_id,
        "embed_data": embed_data,
        "item": item,
        "description": description,
        "bank_code": "",           # để trống: cho user chọn trên Gateway
        "callback_url": callback_url,
        "mac": mac
    }

    # 3) Gọi API create order
    try:
        res = requests.post(ZALO_CREATE_ORDER_URL, json=payload, timeout=30).json()
    except Exception as e:
        return f"Lỗi gọi ZaloPay: {e}", 500

    # 4) Nếu OK, redirect sang Gateway (order_url)
    #    Thông thường response có: return_code, order_url, zp_trans_token...
    if res.get("return_code") == 1 and "order_url" in res:
        return redirect(res["order_url"])

    # Trường hợp lỗi -> hiển thị trả về để debug
    return f"Lỗi ZaloPay: {res}", 400

@app.route("/payment-return/zalopay")
@login_required
def payment_return_zalopay():
    order_id = request.args.get("order_id", type=int)
    if not order_id:
        flash("Thiếu thông tin đơn hàng.", "danger")
        return redirect(url_for("home"))

    order = Order.query.get(order_id)
    if not order:
        flash("Không tìm thấy đơn hàng.", "danger")
        return redirect(url_for("home"))

    # Nếu status đang CANCELLED nhưng query param 'status=1' => thanh toán thành công
    zp_status = request.args.get("status")
    if order.status == OrderStatus.CANCELLED and zp_status == "1":
        order.status = OrderStatus.WAITTING
        db.session.commit()
        try:
            send_order_email(order, order.user)
        except Exception as e:
            print("send mail error:", e)

    if order.status == OrderStatus.WAITTING:
        flash("Thanh toán thành công! Email xác nhận đã gửi.", "success")
    elif order.status == OrderStatus.CANCELLED:
        flash("Thanh toán thất bại hoặc đã bị hủy.", "danger")
    else:
        flash("Đơn hàng đang chờ xác nhận thanh toán. Vui lòng chờ ít phút.", "info")

    return redirect(url_for("view_order_detail", order_id=order.id))


@app.route("/zalopay_ipn", methods=["POST"])
def zalopay_ipn():
    try:
        body = request.get_json(force=True, silent=True) or {}
        data_str = body.get("data", "")
        req_mac = body.get("mac", "")

        # Verify MAC bằng key2
        mac_calc = hmac.new(ZALO_KEY2.encode("utf-8"), data_str.encode("utf-8"), hashlib.sha256).hexdigest()
        if mac_calc != req_mac:
            return jsonify({"return_code": -1, "return_message": "invalid mac"}), 400

        data = json.loads(data_str)
        app_trans_id = data.get("app_trans_id", "")

        # Tách order_id từ app_trans_id kiểu YYMMDD_orderId
        try:
            order_id = int(app_trans_id.split("_", 1)[1])
        except Exception:
            return jsonify({"return_code": -1, "return_message": "invalid order"}), 400

        order = Order.query.get(order_id)
        if not order:
            return jsonify({"return_code": -1, "return_message": "order not found"}), 404

        # Nếu IPN báo thành công → cập nhật sang WAITTING
        if str(data.get("status")) == "1":   # 1 = thanh toán thành công
            order.status = OrderStatus.WAITTING
            db.session.commit()

            try:
                send_order_email(order, order.user)
            except Exception as e:
                print("send mail error:", e)
        else:
            order.status = OrderStatus.CANCELLED
            db.session.commit()

        return jsonify({"return_code": 1, "return_message": "OK"}), 200

    except Exception as e:
        print("ZaloPay IPN error:", e)
        return jsonify({"return_code": 0, "return_message": "server error"}), 500

def send_order_email(order, user):
    try:
        # Tạo danh sách chi tiết món
        content_lines = [
            f"{item.menu_item.name} x {item.quantity} = {item.menu_item.price * item.quantity:,} VNĐ"
            for item in OrderDetail.query.filter_by(order_id=order.id).all()
        ]

        msg = Message(
            "Xác nhận đơn hàng - FoodNow",
            sender=app.config['MAIL_USERNAME'],
            recipients=[user.email]
        )

        total = order.total
        address = order.address
        phone = order.phone
        msg.body = f"""Chào {user.name},

Bạn đã đặt hàng thành công tại FoodNow. Chi tiết đơn hàng:

{chr(10).join(content_lines)}
Tổng cộng: {total:,} VNĐ
Địa chỉ giao hàng: {address}
Số điện thoại: {phone}

Cảm ơn bạn đã sử dụng dịch vụ!
"""
        mail.send(msg)
    except Exception as e:
        print("Không gửi được mail:", str(e))

@app.route("/checkout", methods=["POST"])
@login_required
def checkout():
    selected_items = request.form.getlist("selected_items")
    if not selected_items:
        flash("Vui lòng chọn ít nhất một món để thanh toán!", "danger")
        return redirect(url_for("view_cart"))

    selected_ids = []
    for item in selected_items:
        selected_ids.extend([int(x) for x in item.split(',') if x.strip().isdigit()])

    cart = CartItem.query.filter(
        CartItem.user_id == current_user.id,
        CartItem.id.in_(selected_ids)
    ).all()

    if not cart:
        flash("Giỏ hàng trống!", "danger")
        return redirect(url_for("view_cart"))

    address = request.form.get("address")
    phone = request.form.get("phone")
    payment_method = request.form.get("payment_method")
    coupon_code = session.get("applied_coupon")
    coupon = None
    if coupon_code:
        coupon = Coupon.query.filter_by(code=coupon_code.strip().upper()).first()
        if coupon:
            used = UserCoupon.query.filter_by(user_id=current_user.id, coupon_id=coupon.id).first()
            subtotal_temp = sum(item.menu_item.price * item.quantity for item in cart)
            if used or not coupon.is_valid(subtotal=subtotal_temp):
                coupon = None
                coupon_code = None
    # Tính tổng tiền
    subtotal, discount, total_price = utils.calculate_total_price(cart, current_user.id,coupon_code)
    for item in cart:
        menu_item = item.menu_item
        if item.quantity > menu_item.stock:
            flash(f"{menu_item.name} chỉ còn {menu_item.stock} phần!", "danger")
            return redirect(url_for("view_cart"))
        menu_item.stock -= item.quantity
        item_discount = 0
        if discount > 0:
            item_discount = (item.menu_item.price * item.quantity / subtotal) * discount
        item.discount = item_discount

    restaurant_id = cart[0].menu_item.restaurant_id
    status = OrderStatus.WAITTING if payment_method == "cod" else OrderStatus.CANCELLED
    note = request.form.get("note", "").strip()
    if not note:
        note = ""
    order = Order(
        user_id=current_user.id,
        restaurant_id=restaurant_id,
        address=address,
        phone=phone,
        total=total_price,
        status=status,
        payment_method=payment_method,
        note=note
    )
    db.session.add(order)
    db.session.commit()

    # Lưu chi tiết
    for item in cart:
        detail = OrderDetail(
            order_id=order.id,
            menu_item_id=item.menu_item.id,
            quantity=item.quantity,
            price=item.menu_item.price,
            discount=getattr(item, 'discount', 0)
        )
        db.session.add(detail)

    # Xóa giỏ hàng
    CartItem.query.filter(
        CartItem.user_id == current_user.id,
        CartItem.id.in_(selected_ids)
    ).delete(synchronize_session=False)
    if coupon_code and coupon:
        user_coupon = UserCoupon(user_id=current_user.id, coupon_id=coupon.id)
        db.session.add(user_coupon)
        coupon.used_count += 1
    notification = Notification(
        user_id=current_user.id,
        message=f"Đơn hàng #{order.id} của bạn đã được đặt thành công!",
        order_id=order.id
    )
    db.session.add(notification)
    db.session.commit()
    session.pop("applied_coupon", None)
    session.pop("discount_code", None)

    db.session.commit()
    # Nếu COD -> gửi mail ngay
    if payment_method == "cod":
        send_order_email(order, current_user)
        flash("Đơn hàng đã được đặt thành công.", "success")
        return redirect(url_for("view_order_detail", order_id=order.id))
    elif payment_method == "momo":
        return redirect(url_for("create_momo_payment", order_id=order.id))
    elif payment_method == "zalopay":
        return redirect(url_for("create_zalopay_payment", order_id=order.id))
    else:
        flash("Phương thức thanh toán không hợp lệ", "danger")
        return redirect(url_for("view_cart"))


@app.route("/create_momo_payment/<int:order_id>")
@login_required
def create_momo_payment(order_id):
    import time
    order = Order.query.get_or_404(order_id)

    endpoint = "https://test-payment.momo.vn/v2/gateway/api/create"
    partnerCode = "MOMO"
    accessKey = "F8BBA842ECF85"
    secretKey = "K951B6PE1waDMi640xX08PD3vg6EkVlz"

    orderId = str(int(time.time()))
    requestId = str(int(time.time() * 1000))
    orderInfo = f"Thanh toán MoMo cho đơn #{order.id}"

    redirectUrl = url_for("payment_return", _external=True)
    ipnUrl = url_for("momo_ipn", _external=True)
    extraData = str(order.id)
    requestType = "captureWallet"

    raw_signature = (
        f"accessKey={accessKey}"
        f"&amount={int(order.total)}"
        f"&extraData={extraData}"
        f"&ipnUrl={ipnUrl}"
        f"&orderId={orderId}"
        f"&orderInfo={orderInfo}"
        f"&partnerCode={partnerCode}"
        f"&redirectUrl={redirectUrl}"
        f"&requestId={requestId}"
        f"&requestType={requestType}"
    )

    signature = hmac.new(secretKey.encode("utf-8"),
                         raw_signature.encode("utf-8"),
                         hashlib.sha256).hexdigest()

    payload = {
        "partnerCode": partnerCode,
        "accessKey": accessKey,
        "requestId": requestId,
        "amount": str(int(order.total)),
        "orderId": orderId,
        "orderInfo": orderInfo,
        "redirectUrl": redirectUrl,
        "ipnUrl": ipnUrl,
        "extraData": extraData,
        "requestType": requestType,
        "signature": signature,
        "lang": "vi"
    }

    res = requests.post(endpoint, json=payload).json()
    if res.get("resultCode") == 0 and "payUrl" in res:
        return redirect(res["payUrl"])
    else:
        return f"Lỗi MoMo: {res}", 400


@app.route("/payment_return")
def payment_return():
    result_code = request.args.get("resultCode")
    message = request.args.get("message", "")
    extra_data = request.args.get("extraData")  # chính là order_id mình truyền
    order_id = extra_data if extra_data else None

    if result_code == "0" and order_id:
        order = Order.query.get(order_id)
        if order:
            order.status = OrderStatus.WAITTING
            db.session.commit()
            send_order_email(order, order.user)  # Gửi mail sau khi thanh toán MoMo thành công
        return redirect(url_for("view_order_detail", order_id=order_id))
    else:
        return redirect(url_for("view_order_detail", order_id=order_id))

@app.route("/momo_ipn", methods=["POST"])
def momo_ipn():
    data = request.get_json(force=True, silent=True) or {}
    order_id = data.get("extraData")
    order = Order.query.get(order_id)

    if not order:
        return "order not found", 404

    # Xác minh chữ ký (giữ nguyên code cũ của bạn)

    if str(data.get("resultCode")) == "0":
        order.status = OrderStatus.WAITTING   # thanh toán ok → chờ xử lý
        db.session.commit()
        send_order_email(order, order.user)
    else:
        order.status = OrderStatus.CANCELLED  # giữ nguyên là hủy
        db.session.commit()

    return "ok", 200


@app.route("/confirm_received/<int:order_id>", methods=["POST"])
@login_required
def confirm_received(order_id):
    order = Order.query.get_or_404(order_id)

    # Kiểm tra quyền
    if order.user_id != current_user.id:
        flash("Bạn không có quyền xác nhận đơn này.", "danger")
        return redirect(url_for("view_order_detail", order_id=order.id))

    # Chỉ cho xác nhận khi đang giao
    if order.status != OrderStatus.DELIVERING:
        flash("Đơn hàng chưa đến trạng thái 'Đang giao'.", "warning")
        return redirect(url_for("view_order_detail", order_id=order.id))

    # Cập nhật trạng thái
    order.status = OrderStatus.COMPLETED
    db.session.commit()

    flash("Xác nhận đơn hàng thành công. Cảm ơn bạn!", "success")
    return redirect(url_for("view_menu", rid=order.restaurant_id)+ "#review-section")



@app.route("/apply_coupon", methods=["POST"])
@login_required
def apply_coupon():
    code = request.form.get("coupon", "").strip().upper()
    cart = CartItem.query.filter_by(user_id=current_user.id).all()

    if not cart:
        flash("Giỏ hàng trống, không thể áp dụng mã!", "danger")
        return redirect(url_for("view_cart"))

    if not code:
        flash("Vui lòng nhập mã giảm giá!", "warning")
        return redirect(url_for("view_cart"))

    coupon = Coupon.query.filter_by(code=code).first()
    if not coupon:
        flash("Mã giảm giá không tồn tại!", "danger")
        return redirect(url_for("view_cart"))

    # Kiểm tra user đã dùng coupon này chưa
    used = UserCoupon.query.filter_by(user_id=current_user.id, coupon_id=coupon.id).first()
    if used:
        flash("Bạn đã sử dụng mã này rồi!", "warning")
        return redirect(url_for("view_cart"))

    subtotal = sum(item.menu_item.price * item.quantity for item in cart)

    if subtotal < coupon.min_order_value:
        flash(f"Đơn hàng phải tối thiểu {coupon.min_order_value} VNĐ mới được áp dụng mã!", "warning")
        return redirect(url_for("view_cart"))

    # Lưu coupon vào session
    session["applied_coupon"] = coupon.code

    # Tính giảm giá tạm thời cho từng item để hiển thị ngay
    total_discount = subtotal * (coupon.discount_percent / 100)
    discount_per_item = total_discount / len(cart)
    for item in cart:
        item.discount = discount_per_item  # chỉ tạm thời, không lưu DB

    flash(f"Áp dụng mã {coupon.code} thành công! Giảm {coupon.discount_percent}%!", "success")
    return redirect(url_for("view_cart"))

@app.context_processor
def inject_notifications():
    if current_user.is_authenticated:
        notifications = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).all()
        unread_count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    else:
        notifications = []
        unread_count = 0
    return dict(notifications=notifications, unread_count=unread_count)



@app.route('/')
def home():
    hero_images = [
        "https://images.unsplash.com/photo-1504674900247-0877df9cc836?q=80&w=2070&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1414235077428-338989a2e8c0?q=80&w=2070&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1555939594-58d7cb561ad1?q=80&w=2070&auto=format&fit=crop"
    ]

    # Lấy thông báo chưa đọc của user hiện tại
    if current_user.is_authenticated:
        notifications = Notification.query.filter_by(user_id=current_user.id, is_read=False).order_by(
            Notification.created_at.desc()).all()
        unread_count = len(notifications)
    else:
        notifications = []
        unread_count = 0

    return render_template("index.html",
                           hero_images=hero_images,
                           notifications=notifications,
                           unread_count=unread_count)



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
        stock = float(request.form.get('stock'))
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
            stock=stock,
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
    avg_rating = db.session.query(func.avg(Review.rating)) \
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
    # Lấy món ăn từ DB
    menu_item = MenuItem.query.get_or_404(menu_id)

    # Nếu món đã hết hàng
    if menu_item.stock <= 0:
        flash(f"{menu_item.name} đã hết hàng!", "danger")
        return redirect(url_for("view_cart"))

    # Tìm xem món đã có trong giỏ chưa
    item = CartItem.query.filter_by(user_id=current_user.id, menu_item_id=menu_id).first()
    is_new_item = False

    if item:
        # Nếu số lượng trong giỏ đã bằng stock thì không cho thêm nữa
        if item.quantity >= menu_item.stock:
            flash(f"Bạn đã chọn tối đa {menu_item.stock} phần cho {menu_item.name}", "warning")
            return redirect(url_for("view_cart"))
        item.quantity += 1
    else:
        item = CartItem(user_id=current_user.id, menu_item_id=menu_id, quantity=1)
        db.session.add(item)
        is_new_item = True  #Đánh dấu là món mới

    db.session.commit()

    flash(f"Đã thêm {menu_item.name} vào giỏ hàng!", "success")
    return redirect(url_for("view_cart"))


from flask_login import LoginManager

login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.init_app(app)   # quan trọng: bind với Flask app
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@login_manager.unauthorized_handler
def unauthorized_callback():
    flash("Bạn cần đăng nhập để thêm món ăn vào giỏ hàng.", "warning")
    return redirect(url_for("login_process"))

@app.route('/cart')
@login_required
def view_cart():
    cart = CartItem.query.filter_by(user_id=current_user.id).all()
    coupon_code = session.get("applied_coupon")  # lấy coupon từ session nếu có
    phone = request.form.get("phone")
    address = request.form.get("address")
    subtotal, discount, total_price = utils.calculate_total_price(cart,current_user.id,coupon_code)

    return render_template('cart.html',
                           cart=cart,
                           subtotal=subtotal,
                           discount=discount,
                           total_price=total_price,
                           coupon_code=coupon_code,
                           )


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


@app.route('/order/<int:order_id>')
@login_required
def view_order_detail(order_id):
    order = Order.query.get_or_404(order_id)

    if order.user_id != current_user.id and current_user.role != UserRole.ADMIN:
        flash("Bạn không có quyền xem đơn hàng này", "danger")
        return redirect(url_for("home"))

    return render_template('order_detail.html', order=order,OrderStatus=OrderStatus)

@app.route('/notification/mark_read/<int:notification_id>', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    note = Notification.query.filter_by(id=notification_id, user_id=current_user.id).first()
    if note:
        note.is_read = True
        db.session.commit()
        return '', 204
    return 'Not found', 404




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
        name = request.form.get("name")
        password = request.form.get('password')
        confirm = request.form.get('confirm')
        username = request.form.get('username')
        email = request.form.get('email')
        pattern = r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$'

        if not password:
            flash("Mật khẩu không được để trống!", "error")
        if User.query.filter_by(email=email).first():
            return render_template("register.html",form=request.form, err_msg="Email đã được sử dụng!")
        if User.query.filter_by(username=username).first():
            return render_template("register.html",form=request.form, err_msg="Tên đăng nhập đã tồn tại!")
        elif not re.match(pattern, password):
            return render_template("register.html",form=request.form, err_msg="Mật khẩu phải ≥8 ký tự, có chữ hoa, chữ thường, số và ký tự đặc biệt!")
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

    return render_template('register.html',form={}, err_msg=error_msg)


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
            address = request.form.get('address', '').strip()
            if dob:
                try:
                    dob = datetime.strptime(dob, "%Y-%m-%d").date()
                    if dob > date.today():
                        flash("Ngày sinh không được lớn hơn ngày hiện tại!", "danger")
                        return redirect(url_for("profile"))
                    current_user.dob = dob
                except ValueError:
                    flash("Ngày sinh không hợp lệ!", "danger")
                    return redirect(url_for("profile"))
            else:
                current_user.dob = None
            if not email:
                error_msg = 'Email không được để trống!'
            elif not re.match(r"^0\d{9}$", phone or ""):
                error_msg = 'Số điện thoại không hợp lệ! Phải bắt đầu bằng 0 và có đúng 10 số.'
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
                    user.address = address
                    avatar = request.files.get('avatar')
                    if avatar and avatar.filename != '':
                        filename = secure_filename(avatar.filename)
                        upload_path = os.path.join('static/images', filename)
                        os.makedirs(os.path.dirname(upload_path), exist_ok=True)
                        avatar.save(upload_path)
                        user.avatar = '/' + upload_path

                    db.session.commit()
                    success_msg = 'Cập nhật thông tin thành công!'
        if tab == 'security':
            old_password = request.form.get('old_password', '').strip()
            new_password = request.form.get('new_password', '').strip()
            confirm_password = request.form.get('confirm_password', '').strip()

            # Hash mật khẩu cũ nhập từ form
            old_hash = hashlib.md5(old_password.encode('utf-8')).hexdigest()
            pattern = r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$'

            if old_hash != current_user.password:
                error_msg = "Mật khẩu cũ không đúng."
            elif new_password != confirm_password:
                error_msg = "Mật khẩu mới và xác nhận không khớp."
            elif not re.match(pattern, new_password):
                error_msg = "Mật khẩu phải ≥8 ký tự, có chữ hoa, chữ thường, số và ký tự đặc biệt."
            else:
                # Lưu mật khẩu mới
                current_user.password = hashlib.md5(new_password.encode('utf-8')).hexdigest()
                db.session.commit()
                success_msg = "Đổi mật khẩu thành công."
                print("DEBUG - New hash saved:", current_user.password)

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

@app.route('/remove_coupon')
@login_required
def remove_coupon():
    session.pop('applied_coupon', None)  # xóa mã trong session
    flash("Đã hủy mã giảm giá!", "info")
    return redirect(url_for('view_cart'))

if __name__ == '__main__':
    with app.app_context():
        from foodnow import admin
        app.run(debug=True, host="0.0.0.0", port=80)
