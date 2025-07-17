import math
from foodnow import app, db, login
from flask import render_template, request, redirect, url_for, session, jsonify
import utils
from flask_login import login_user, logout_user, login_required, current_user

from foodnow.models import Restaurant, MenuItem, CartItem, User, Order, OrderDetail
from datetime import datetime



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
    return render_template('cart.html', cart=cart)

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


@app.context_processor
def inject_common():
    return dict(restaurants=Restaurant.query.all())




if __name__ == '__main__':
    with app.app_context():
        app.run(debug=True)
