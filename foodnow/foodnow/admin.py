from foodnow import app, db, utils
from foodnow.models import Restaurant, MenuItem, User, Order, OrderDetail, UserRole
from flask_admin import Admin, BaseView, expose, AdminIndexView
from flask_admin.contrib.sqla import ModelView
from flask_login import current_user, logout_user
from flask import redirect
from wtforms import SelectField
from foodnow.models import RestaurantStatus


class MyAdminIndexView(AdminIndexView):
    @expose('/')
    def index(self):
        return self.render('admin/index.html')

admin = Admin(app=app, name="FoodNow Admin", template_mode="bootstrap4", index_view=MyAdminIndexView())

class AdminView(ModelView):
    def is_accessible(self):
        return current_user.is_authenticated and current_user.role == UserRole.ADMIN

class RestaurantView(AdminView):
    column_list = ['name', 'address', 'phone', 'user_id', 'status']
    column_searchable_list = ['name', 'address']
    column_filters = ['name', 'address', 'status']

    column_labels = {
        'name': 'Tên Nhà Hàng',
        'address': 'Địa Chỉ',
        'phone': 'Số Điện Thoại',
        'user_id': 'Chủ Nhà Hàng',
        'status': 'Trạng Thái'
    }

    form_columns = ['name', 'address', 'phone', 'image', 'description', 'user_id', 'status']

    # 👉 Thêm dòng này để override field Enum thành SelectField
    form_overrides = {
        'status': SelectField
    }

    # 👉 Thêm dòng này để gán choices cho SelectField
    form_args = {
        'status': {
            'choices': [(status.name, status.value) for status in RestaurantStatus]
        }
    }




class MenuItemView(AdminView):
    column_list = ['name', 'price', 'category_id', 'restaurant_id']
    column_searchable_list = ['name']
    column_filters = ['price', 'category_id', 'restaurant_id']
    column_labels = {
        'name': 'Tên Món',
        'price': 'Giá',
        'category_id': 'Danh Mục',
        'restaurant_id': 'Nhà Hàng'
    }

    form_columns = ['name', 'description', 'price', 'available', 'image', 'category_id', 'restaurant_id']

    def on_model_change(self, form, model, is_created):
        restaurant = Restaurant.query.get(model.restaurant_id)
        if not restaurant or restaurant.status != RestaurantStatus.APPROVED:
            raise ValueError("Nhà hàng này chưa được duyệt. Không thể tạo món ăn.")
        return super().on_model_change(form, model, is_created)

from wtforms import SelectField

class UserView(AdminView):
    column_list = ['username', 'name', 'phone', 'role']
    column_searchable_list = ['username', 'name']
    column_filters = ['username', 'name', 'role']
    column_labels = {
        'username': 'Tên Đăng Nhập',
        'name': 'Họ Tên',
        'phone': 'Số Điện Thoại',
        'role': 'Vai Trò'
    }

    form_overrides = {
        'role': SelectField
    }

    form_args = {
        'role': {
            'choices': [(role.value, role.value) for role in UserRole]
        }
    }


class OrderView(AdminView):
    column_list = ['user_id', 'restaurant_id', 'status', 'created_at']
    column_searchable_list = ['user_id']
    column_filters = ['status', 'created_at']
    column_labels = {
        'user_id': 'Khách Hàng',
        'restaurant_id': 'Nhà Hàng',
        'status': 'Trạng Thái',
        'created_at': 'Ngày Tạo'
    }

class LogoutView(BaseView):
    @expose('/')
    def index(self):
        logout_user()
        return redirect('/admin')

    def is_accessible(self):
        return current_user.is_authenticated

admin.add_view(RestaurantView(Restaurant, db.session, name='Nhà Hàng'))
admin.add_view(MenuItemView(MenuItem, db.session, name='Món Ăn'))
admin.add_view(UserView(User, db.session, name='Người Dùng'))
admin.add_view(OrderView(Order, db.session, name='Đơn Hàng'))
admin.add_view(LogoutView(name='Đăng Xuất'))
