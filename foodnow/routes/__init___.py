def register_routes(app):
    from .auth import auth_bp
    from .main import main_bp
    from .cart import cart_bp
    from .payment import payment_bp
    from .restaurant import restaurant_bp
    from .review import review_bp
    from .order import order_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(cart_bp)
    app.register_blueprint(payment_bp)
    app.register_blueprint(restaurant_bp)
    app.register_blueprint(review_bp)
    app.register_blueprint(order_bp)
