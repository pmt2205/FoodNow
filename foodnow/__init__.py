from flask import Flask
from urllib.parse import quote
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
import cloudinary


app = Flask(__name__)
app.secret_key = "KJGHJG^&*%&*^T&*(IGFG%ERFTGHCFHGF^&**&TYIU"
app.config['SQLALCHEMY_DATABASE_URI'] = (
    "mysql+pymysql://lehongduc3491:123456789a@db-test.cb7hspzehogr.us-east-1.rds.amazonaws.com:3306/fooddb?charset=utf8mb4"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = True
db = SQLAlchemy(app)
login = LoginManager(app)




cloudinary.config(
    cloud_name="dtnfkk7ih",
    api_key="794598113389753",
    api_secret="LnU0d-WZtV3VzlOkPQMK_YFVoxk",
    secure=True
)