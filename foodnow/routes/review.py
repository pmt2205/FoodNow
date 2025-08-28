from flask import request, redirect, url_for, flash, render_template
from flask_login import login_required, current_user
from foodnow import app, db
from foodnow.models import Order, Review

@app.route('/submit-review/<int:restaurant_id>', methods=['POST'])
@login_required
def submit_review(restaurant_id):
    has_ordered = Order.query.filter_by(
        user_id=current_user.id,
        restaurant_id=restaurant_id
    ).first()

    if not has_ordered:
        flash("Bạn chưa đặt hàng từ nhà hàng này.", "danger")
        return redirect(url_for('view_menu', rid=restaurant_id))

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