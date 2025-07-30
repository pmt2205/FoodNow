from flask import render_template, request
from foodnow import app
import utils

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