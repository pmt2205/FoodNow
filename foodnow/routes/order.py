from flask import render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from foodnow import app, db
from foodnow.models import Restaurant, Order, OrderDetail, CartItem, OrderStatus

@app.route('/checkout', methods=['POST'])
@login_required
def order_checkout():
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

@app.route('/order/<int:order_id>')
@login_required
def order_detail(order_id):
    order = Order.query.filter_by(id=order_id, user_id=current_user.id).first()
    if not order:
        return "Không tìm thấy đơn hàng.", 404
    return render_template('order_detail.html', order=order)

@app.route('/my-orders')
@login_required
def restaurant_orders():
    if current_user.role != OrderStatus.RESTAURANT:
        return "Bạn không có quyền truy cập!", 403

    restaurants = Restaurant.query.filter_by(user_id=current_user.id).all()
    restaurant_ids = [r.id for r in restaurants]

    orders = Order.query.filter(Order.restaurant_id.in_(restaurant_ids)) \
                        .order_by(Order.created_at.desc()).all()

    return render_template('restaurant_orders.html', orders=orders)

@app.route('/update-order-status/<int:order_id>', methods=['POST'])
@login_required
def change_order_status(order_id):
    if current_user.role.name != 'RESTAURANT':
        flash("Không có quyền.", "danger")
        return redirect(url_for('restaurant_orders'))

    order = Order.query.get_or_404(order_id)
    user_restaurant_ids = [r.id for r in current_user.restaurants]

    if order.restaurant_id not in user_restaurant_ids:
        flash("Không thể sửa đơn hàng không thuộc nhà hàng bạn.", "danger")
        return redirect(url_for('restaurant_orders'))

    new_status = request.form.get('status')
    try:
        order.status = OrderStatus[new_status]
        db.session.commit()
        flash("Cập nhật trạng thái thành công.", "success")
    except KeyError:
        flash("Trạng thái không hợp lệ.", "danger")

    return redirect(url_for('restaurant_orders'))