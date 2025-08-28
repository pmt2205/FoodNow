from flask import render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
import hashlib, os
from werkzeug.utils import secure_filename
from foodnow import app, db, login
import utils
from foodnow.models import UserRole, Order

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
            utils.add_user(avatar=avatar, **data)
            return redirect(url_for('login_process'))
        else:
            error_msg = 'Mật khẩu xác nhận không khớp!'

    return render_template('register.html', err_msg=error_msg)

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