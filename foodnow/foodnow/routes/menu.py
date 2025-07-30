from flask import render_template, request, redirect, url_for
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import os
from foodnow import app, db
from foodnow.models import Restaurant, MenuItem, Category

@app.route('/manage-menu/<int:restaurant_id>', methods=['GET', 'POST'])
@login_required
def manage_menu(restaurant_id):
    restaurant = Restaurant.query.get_or_404(restaurant_id)

    if restaurant.user_id != current_user.id:
        return "Bạn không có quyền!", 403

    if request.method == 'POST':
        name = request.form.get('name')
        price = float(request.form.get('price'))
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
    categories = Category.query.all()

    return render_template('manage_menu.html',
                           restaurant=restaurant,
                           menu_items=menu_items,
                           categories=categories)

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
            # TODO: upload image logic here
            pass

        db.session.commit()
        return redirect(url_for('manage_menu', restaurant_id=item.restaurant_id))

    return render_template('edit_menu_item.html', item=item, categories=categories)

@app.route('/menu_item/delete/<int:item_id>', methods=['POST'])
@login_required
def delete_menu_item(item_id):
    item = MenuItem.query.get_or_404(item_id)
    restaurant_id = item.restaurant_id
    db.session.delete(item)
    db.session.commit()
    return redirect(url_for('manage_menu', restaurant_id=restaurant_id))