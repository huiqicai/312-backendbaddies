from flask import Flask, render_template, request, redirect, make_response, send_file, jsonify
from flask_pymongo import PyMongo
from flask_bcrypt import Bcrypt
from pymongo import MongoClient
from bson import ObjectId
import hashlib
import os

app = Flask(__name__, template_folder='Frontend', static_folder='Frontend/static')

bcrypt = Bcrypt(app)

mongo_client = MongoClient('mongo')  # init mongo

db = mongo_client['user_auth_db']

users_collection = db['users']

tokens_collection = db['tokens']

quizzes_collection = db['quizzes']

interactions_collection = db['interactions']

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

def escapeHTML(line):
    return line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

@app.route("/register_page", methods=["GET"])
def register():
    response = make_response(render_template("register_page.html"))
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response

@app.route("/")
def home():
    response = make_response(render_template("login.html"))
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response

@app.route("/about")
def about():
    response = make_response(render_template("about.html"))
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response

@app.route("/static/cat.jpg")
def serve_cat_image():
    response = send_file("Frontend/static/cat.jpg", mimetype="image/jpeg")
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response

@app.route("/register_user", methods=["POST"])
def register_user():
    username = escapeHTML(request.form.get("username"))
    password = request.form.get("password")
    email = escapeHTML(request.form.get("email"))

    if users_collection.find_one({"username": username}): 
        return jsonify({"success": False, "message": "Username already taken, please use another."}), 400
    if users_collection.find_one({"email": email}):
        return jsonify({"success": False, "message": "Email already registered with an account!"}), 400

    hashed_pw = hash_password(password)
    user = {"email": email, "username": username, "password": hashed_pw}
    users_collection.insert_one(user)

    response = make_response(redirect("/?message=Registered Successfully"))
    
    response.set_cookie("username", username)  
    
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response

@app.route("/login", methods=["POST"])
def login():
    email = escapeHTML(request.form.get("email"))
    password = request.form.get("password")
    user = users_collection.find_one({"email": email})

    if not user or not check_password(user["password"], password):
        return jsonify({"success": False, "message": "Invalid credentials, try again."}), 401

    auth_token = generate_auth_token(user["username"])

    response = make_response(redirect("/dashboard"))
    
    response.set_cookie("auth_token", auth_token, httponly=True, max_age=3600)
    
    response.set_cookie("username", user["username"])  # Set the username cookie. 
    
    response.headers["X-Content-Type-Options"] = "nosniff"
    
    return response

@app.route("/dashboard")
def dashboard():
    username = request.cookies.get("username")
    quizzes = list(quizzes_collection.find())  # find every quiz that is created in our Db
    message = request.args.get("message")

    response = make_response(render_template("dashboard.html", username=username, quizzes=quizzes, message=message))
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response

@app.route("/upload_quiz", methods=["POST"]) 
def upload_quiz(): 
    title = escapeHTML(request.form.get("title"))
    questions = [escapeHTML(q) for q in request.form.getlist("questions[]")]
    answers = [escapeHTML(a) for a in request.form.getlist("answers[]")]
    answers = [ele.split(',') for ele in answers]
    correct_answers = [escapeHTML(a) for a in request.form.getlist("correct_answers[]")]
    
    username = request.cookies.get("username")

    if username:
        quiz = {
            "title": title,
            "questions": {
                questions[i]: (correct_answers[i].strip(), [ans.strip() for ans in answers[i] if ans != correct_answers[i]])
                for i in range(len(questions))
            },
            "created_by": username, 
            "likes": 0,  
            "comments": [] 
        }
        print(quiz)
        quizzes_collection.insert_one(quiz)
        return redirect("/dashboard")

    return jsonify({"success": False, "message": "User not authenticated"}), 401

@app.route("/interact", methods=["POST"])
def interact():  
    username = request.cookies.get("username")
    quiz_id = request.form.get("quiz_id")
    interaction_type = request.form.get("type")

    if username:
        quiz_object_id = ObjectId(quiz_id)

        if interaction_type == "like":
            existing_like = interactions_collection.find_one({
                "quiz_id": quiz_object_id,
                "username": username,
                "type": "like"
            })

            if existing_like:
                interactions_collection.delete_one({
                    "quiz_id": quiz_object_id,
                    "username": username,
                    "type": "like"
                })
                quizzes_collection.update_one({"_id": quiz_object_id}, {"$inc": {"likes": -1}})
                action = "unliked"
            else:
                interactions_collection.insert_one({
                    "quiz_id": quiz_object_id,
                    "username": username,
                    "type": "like"
                })
                quizzes_collection.update_one({"_id": quiz_object_id}, {"$inc": {"likes": 1}})
                action = "liked"

            # get updated list of different users who liked the quiz
            likes_users = [
                interaction["username"] for interaction in interactions_collection.find({
                    "quiz_id": quiz_object_id,
                    "type": "like"
                })
            ]

            return jsonify({"success": True, "action": action, "likes_users": likes_users})

    return jsonify({"success": False, "message": "User not authenticated"}), 401

@app.route('/static/dashboard.js')
def serve_dashboard_js():
    return send_file('Frontend/static/dashboard.js', mimetype='application/javascript')

@app.route("/quiz/<quiz_id>")
def quiz_details(quiz_id):
    #testing
    try:
        quiz = quizzes_collection.find_one({"_id": ObjectId(quiz_id)})
        if not quiz:
            return "Invalid credentials", 401
        return render_template('quizPage.html', quiz=quiz)
    except Exception as e:
        # Handle any exceptions (e.g., invalid ObjectId format)
        return str(e), 400

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=8080)