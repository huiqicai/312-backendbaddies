from flask import Flask, render_template, request, redirect, make_response
from flask_pymongo import PyMongo
from flask_bcrypt import Bcrypt
from pymongo import MongoClient
import hashlib
import os
from datetime import datetime, timedelta

app = Flask(__name__, template_folder='Frontend', static_folder='Frontend/static')

@app.route("/register_page", methods=["GET"])
def register():       
    return render_template("register_page.html")

bcrypt = Bcrypt(app)
mongo_client = MongoClient('mongo')
db = mongo_client['user_auth_db']
users_collection = db['users']
tokens_collection = db['tokens']

def hash_password(password):
    return bcrypt.generate_password_hash(password).decode('utf-8')

def check_password(stored_password, provided_password):
    return bcrypt.check_password_hash(stored_password, provided_password)

def generate_auth_token(username):
    token = os.urandom(24).hex()
    hashed_token = hashlib.sha256(token.encode()).hexdigest()
    tokens_collection.insert_one({
        "username": username,
        "token": hashed_token,
    })
    return token

@app.route("/")
def home():
    username = request.cookies.get("username")
    return render_template("login.html", username=username)

@app.route("/register_user", methods=["POST"], endpoint = "register_user")
def register():
    username = request.form.get("username")
    password = request.form.get("password")
    email = request.form.get("email")

    if not users_collection.find_one({"username": username}):
        if not users_collection.find_one({"email": email}):
            hashed_pw = hash_password(password)
            user = {"email": email,"username": username, "password": hashed_pw}
            users_collection.insert_one(user)
            response = make_response(redirect("/"))
            response.headers["X-Content-Type-Options"] = "nosniff"
            return response
    else:
        response = make_response("Username already taken", 400)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Type"] = "application/json"
        return response
    
@app.route("/login", methods=["POST"])
def login():
    username = request.form.get("username")
    password = request.form.get("password")
    email = request.form.get("email")
    user = users_collection.find_one({"email": email})

    if not user or not check_password(user["password"], password):
        return "Invalid credentials", 401

    auth_token = generate_auth_token(username)
    response = make_response(redirect("/"))
    #response.set_cookie("username", username, httponly=True, max_age=3600)
    response.set_cookie("auth_token", auth_token, httponly=True, max_age=3600)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Content-Type"] = "text/html; charset=utf-8"
    return response

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=8080)
