from flask import render_template, redirect, url_for, request
from flask_login import login_required, current_user
from foodnow import app, db
from foodnow.models import CartItem, MenuItem, Order, OrderDetail, OrderStatus

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
    return render_template('cart.html', cart=cart, total_price=total_price, shipping_fee=shipping_fee)

@app.route('/cart/update/<int:cart_id>/<change>')
@login_required
def update_cart_quantity(cart_id, change):
    try:
        change = int(change)
    except ValueError:
        return redirect(url_for('view_cart'))

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

    for item in cart:
        detail = OrderDetail(order_id=order.id,
                             menu_item_id=item.menu_item.id,
                             quantity=item.quantity,
                             price=item.menu_item.price)
        db.session.add(detail)

    order.calculate_total()
    CartItem.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()

    return redirect(url_for('home'))
