from flask_admin import BaseView, expose
from sqlalchemy import extract, func
from foodnow.models import Order, Restaurant
from foodnow import db
from foodnow.models import User
from datetime import datetime

class RevenueByRestaurantYearView(BaseView):
    @expose('/')
    def index(self):
        # Truy vấn doanh thu theo nhà hàng và theo năm
        stats = db.session.query(
            extract('year', Order.created_at).label('year'),
            Restaurant.name.label('restaurant_name'),
            func.sum(Order.total).label('revenue')
        ).join(Restaurant, Restaurant.id == Order.restaurant_id)\
         .group_by(extract('year', Order.created_at), Restaurant.name)\
         .order_by(extract('year', Order.created_at), Restaurant.name).all()

        # Tạo cấu trúc dữ liệu cho Chart.js
        data = {}
        years = sorted({int(row.year) for row in stats})
        restaurants = sorted({row.restaurant_name for row in stats})

        for restaurant in restaurants:
            data[restaurant] = [0] * len(years)

        for row in stats:
            year_index = years.index(int(row.year))
            data[row.restaurant_name][year_index] = float(row.revenue or 0)

        return self.render('admin/revenuerestaurant.html',
                           data=data, years=years, restaurants=restaurants)

class UserStatsByMonthView(BaseView):
    @expose('/')
    def index(self):
        year = datetime.now().year

        stats = db.session.query(
            extract('month', User.created_at).label('month'),
            func.count(User.id).label('user_count')
        ).filter(extract('year', User.created_at) == year)\
         .group_by(extract('month', User.created_at))\
         .order_by(extract('month', User.created_at))\
         .all()

        # Dữ liệu cho Chart.js
        months = [f"Tháng {int(row.month)}" for row in stats]
        values = [row.user_count for row in stats]

        return self.render('admin/userstatsbymonth.html',
                           months=months, values=values, year=year)