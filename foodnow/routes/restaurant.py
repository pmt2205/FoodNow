from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import os
from foodnow import app, db
from foodnow.models import Restaurant, UserRole

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
            user_id=current_user.id
        )
        db.session.add(restaurant)
        db.session.commit()
        return redirect(url_for('my_restaurant'))

    my_restaurants = Restaurant.query.filter_by(user_id=current_user.id).all()
    return render_template('my_restaurant.html', restaurants=my_restaurants)

@app.route('/edit_restaurant/<int:restaurant_id>', methods=['GET', 'POST'])
def edit_restaurant(restaurant_id):
    restaurant = Restaurant.query.get_or_404(restaurant_id)

    if request.method == 'POST':
        restaurant.name = request.form.get('name')
        restaurant.address = request.form.get('address')
        restaurant.phone = request.form.get('phone')
        restaurant.description = request.form.get('description')

        image = request.files.get('image')
        if image and image.filename != '':
            image_path = f'static/uploads/{image.filename}'
            image.save(image_path)
            restaurant.image = '/' + image_path

        db.session.commit()
        flash('Cập nhật nhà hàng thành công.', 'success')
        return redirect(url_for('my_restaurant'))

    return render_template('edit_restaurant.html', restaurant=restaurant)

@app.route('/delete_restaurant/<int:restaurant_id>', methods=['POST'])
def delete_restaurant(restaurant_id):
    restaurant = Restaurant.query.get_or_404(restaurant_id)
    db.session.delete(restaurant)
    db.session.commit()
    flash('Xóa nhà hàng thành công.', 'success')
    return redirect(url_for('my_restaurant'))