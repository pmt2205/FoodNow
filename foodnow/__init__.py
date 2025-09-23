from flask import Flask
from urllib.parse import quote
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
import cloudinary
import cloudinary.uploader



app = Flask(__name__)
app.secret_key = "KJGHJG^&*%&*^T&*(IGFG%ERFTGHCFHGF^&**&TYIU"
app.config["SQLALCHEMY_DATABASE_URI"] = "mysql+pymysql://admin:123456789a@database.c4tmq86mca9u.us-east-1.rds.amazonaws.com/foodnow?charset=utf8mb4"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = True
db = SQLAlchemy(app)
login = LoginManager(app)


cloudinary.config(
    cloud_name="dtnfkk7ih",
    api_key="243235146525595",
    api_secret="53EJRPqJEP8jEsfEK_t3jalUzrg"
)
