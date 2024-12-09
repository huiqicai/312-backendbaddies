from flask import Flask, render_template, request, redirect, make_response, send_file, jsonify
from flask_socketio import SocketIO, emit
from flask_pymongo import PyMongo
from flask_bcrypt import Bcrypt
from pymongo import MongoClient
from bson import ObjectId
from html import escape
import hashlib
import time
import threading

app = Flask(__name__, template_folder='Frontend', static_folder='Frontend/static')
socketio = SocketIO(app, cors_allowed_origins="*", transports=['websocket'])
bcrypt = Bcrypt(app)

mongo_client = MongoClient('mongo')  
db = mongo_client['user_auth_db']
users_collection = db['users']
quizzes_collection = db['quizzes']
interactions_collection = db['interactions']
active_users = {}
user_lock = threading.Lock()

def hash_password(password):
    return bcrypt.generate_password_hash(password).decode('utf-8')

def check_password(stored_password, provided_password):
    return bcrypt.check_password_hash(stored_password, provided_password)

def verify_auth_token(token):
    if not token:
        return None

    hashed_token = hashlib.sha256(token.encode("utf-8")).hexdigest()
    user = users_collection.find_one({"auth_token": hashed_token})
    return user

def validate_session():
    auth_token = request.cookies.get("auth_token")
    user = verify_auth_token(auth_token)
    if not user:
        return None
    return user["username"]

@app.route("/static/cat.jpg")
def serve_cat_image():
    response = send_file("Frontend/static/cat.jpg", mimetype="image/jpeg")
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response

@app.route("/")
def home():
    return render_template("login.html")

@app.route("/register_page", methods=["GET"])
def register_page():
    return render_template("register_page.html")

@app.route("/dashboard")
def dashboard():
    username = validate_session()
    if not username:
        return redirect("/?message=Please log in.")

    quizzes = list(quizzes_collection.find())  # Fetch all quizzes
    return render_template("dashboard.html", username=username, quizzes=quizzes)

@app.route("/register_user", methods=["POST"])
def register_user():
    username = escape(request.form.get("username"))
    password = request.form.get("password")
    email = escape(request.form.get("email"))

    if users_collection.find_one({"username": username}):
        return jsonify({"success": False, "message": "Username already taken."}), 400
    if users_collection.find_one({"email": email}):
        return jsonify({"success": False, "message": "Email already registered."}), 400

    hashed_pw = hash_password(password)
    users_collection.insert_one({"username": username, "email": email, "password": hashed_pw})
    return redirect("/?message=Registered Successfully")

@app.route("/login", methods=["POST"])
def login():
    email = escape(request.form.get("email"))
    password = request.form.get("password")
    user = users_collection.find_one({"email": email})

    if not user or not check_password(user["password"], password):
        return jsonify({"success": False, "message": "Invalid credentials."}), 401

    raw_token = user["username"] + request.remote_addr
    auth_token = hashlib.sha256(raw_token.encode()).hexdigest()
    users_collection.update_one({"username": user["username"]}, {"$set": {"auth_token": auth_token}})

    response = make_response(redirect("/dashboard"))
    response.set_cookie("username", user["username"], httponly=True, secure=True)
    response.set_cookie("auth_token", raw_token, httponly=True, secure=True, max_age=3600)
    return response

@app.route("/logout", methods=["POST"])
def logout():
    username = request.cookies.get("username")
    auth_token = request.cookies.get("auth_token")
    user = verify_auth_token(auth_token)

    if user:
        users_collection.update_one({"username": username}, {"$unset": {"auth_token": ""}})

    response = make_response(redirect("/"))
    response.delete_cookie("username")
    response.delete_cookie("auth_token")
    return response

@app.route("/upload_quiz", methods=["POST"])
def upload_quiz():
    username = validate_session()
    if not username:
        return redirect("/?message=Please log in.")

    title = escape(request.form.get("title"))
    questions = [escape(q) for q in request.form.getlist("questions[]")]
    answers = [escape(a) for a in request.form.getlist("answers[]")]
    correct_answers = [escape(ca) for ca in request.form.getlist("correct_answers[]")]

    if len(questions) != len(answers) or len(questions) != len(correct_answers):
        return jsonify({"success": False, "message": "All fields must have the same number of entries."}), 400

    quiz = {
        "title": title,
        "questions": {
            questions[i]: {
                "correct_answer": correct_answers[i].strip(),
                "choices": [choice.strip() for choice in answers[i].split(',')]
            }
            for i in range(len(questions))
        },
        "created_by": username,
        "likes": 0,
        "comments": []
    }
    quizzes_collection.insert_one(quiz)
    return redirect("/dashboard")

@app.route("/comment_quiz/<quiz_id>", methods=["POST"])
def comment_quiz(quiz_id):
    username = validate_session()
    if not username:
        return jsonify({"success": False, "message": "User not authenticated."}), 401

    comment_text = escape(request.form.get("comment"))
    quiz_object_id = ObjectId(quiz_id)
    comment = {"username": username, "text": comment_text}
    quizzes_collection.update_one({"_id": quiz_object_id}, {"$push": {"comments": comment}})

    # Emit the comment globally
    socketio.emit("new_comment", {"quiz_id": quiz_id, "username": username, "text": comment_text})
    return jsonify({"success": True, "comment": comment})

@app.route("/interact", methods=["POST"])
def interact():
    username = validate_session()
    if not username:
        return jsonify({"success": False, "message": "User not authenticated."}), 401

    quiz_id = request.form.get("quiz_id")
    interaction_type = request.form.get("type")
    
    try:
        quiz_object_id = ObjectId(quiz_id)
    except Exception:
        return jsonify({"success": False, "message": "Invalid quiz ID."}), 400

    if interaction_type == "like":
        try:
            existing_like = interactions_collection.find_one(
                {"quiz_id": quiz_object_id, "username": username, "type": "like"}
            )
            action = ""
            if existing_like:
                interactions_collection.delete_one(
                    {"quiz_id": quiz_object_id, "username": username, "type": "like"}
                )
                quizzes_collection.update_one(
                    {"_id": quiz_object_id},
                    {"$inc": {"likes": -1}, "$pull": {"likes_users": username}}
                )
                action = "unliked"
            else:
                interactions_collection.insert_one(
                    {"quiz_id": quiz_object_id, "username": username, "type": "like"}
                )
                quizzes_collection.update_one(
                    {"_id": quiz_object_id},
                    {"$inc": {"likes": 1}, "$addToSet": {"likes_users": username}}
                )
                action = "liked"

            updated_quiz = quizzes_collection.find_one(
                {"_id": quiz_object_id}, {"likes": 1, "likes_users": 1}
            )
            if not updated_quiz:
                return jsonify({"success": False, "message": "Quiz not found."}), 404

            likes_count = updated_quiz.get("likes", 0)
            likes_users = updated_quiz.get("likes_users", [])

            socketio.emit("like_quiz", {
                "quiz_id": quiz_id,
                "likes_count": likes_count,
                "likes_users": likes_users,
                "action": action,
            })

            return jsonify({"success": True, "action": action, "likes_count": likes_count, "likes_users": likes_users})

        except Exception as e:
            print(f"Error processing like/unlike: {e}")
            return jsonify({"success": False, "message": "Failed to process like/unlike."}), 500

    return jsonify({"success": False, "message": "Invalid interaction type."}), 400

@app.route("/likes/<quiz_id>", methods=["GET"])
def get_likes(quiz_id):
    quiz_object_id = ObjectId(quiz_id)
    quiz = quizzes_collection.find_one({"_id": quiz_object_id}, {"likes_users": 1})
    if not quiz:
        return jsonify({"success": False, "message": "Quiz not found"}), 404

    likes_users = quiz.get("likes_users", [])
    return jsonify({"success": True, "likes_users": likes_users})
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


@app.route("/active_users", methods=["GET"])
def get_active_users():
    active_users = list(users_collection.find({}, {"_id": 1, "active_time": 1}))
    formatted_users = {str(user["_id"]): user["active_time"] for user in active_users}
    return jsonify({"success": True, "active_users": formatted_users})

@app.route("/track_user_activity", methods=["POST"])
def track_user_activity():
    user_id = request.form.get("user_id")
    if not user_id:
        return jsonify({"success": False, "message": "Missing user_id"}), 400

    with user_lock:
        users_collection.update_one(
            {"_id": user_id},
            {"$inc": {"active_time": 1}},
            upsert=True  
        )

    active_users = list(users_collection.find({}, {"_id": 1, "active_time": 1}))
    formatted_users = {str(user["_id"]): user["active_time"] for user in active_users}

    socketio.emit('update_times', formatted_users)
    return jsonify({"success": True, "active_users": formatted_users})

def update_user_times():
    while True:
        with user_lock:
            users_collection.update_many({}, {"$inc": {"active_time": 1}})

            active_users = list(users_collection.find({}, {"_id": 1, "active_time": 1}))
            formatted_users = {str(user["_id"]): user["active_time"] for user in active_users}

        print(f"Broadcasting active users: {formatted_users}")
        socketio.emit('update_times', formatted_users, broadcast=False)  
        time.sleep(1)


threading.Thread(target=update_user_times, daemon=True).start()

@socketio.on('connect')
def handle_connect():
    user_id = request.args.get('user_id', 'anonymous')
    if not user_id:
        return

    with user_lock:
        users_collection.update_one(
            {"_id": user_id},
            {"$setOnInsert": {"active_time": 0}}, 
            upsert=True
        )
    print(f"User {user_id} connected")

    active_users = list(users_collection.find({}, {"_id": 1, "active_time": 1}))
    formatted_users = {str(user["_id"]): user["active_time"] for user in active_users}
    emit('update_times', formatted_users, broadcast=True)


@socketio.on('disconnect')
def handle_disconnect():
    user_id = request.args.get('user_id', 'anonymous')
    if not user_id:
        return

    print(f"User {user_id} disconnected")

    active_users = list(users_collection.find({}, {"_id": 1, "active_time": 1}))
    formatted_users = {str(user["_id"]): user["active_time"] for user in active_users}
    emit('update_times', formatted_users, broadcast=True)


@socketio.on('reset_time')
def reset_time(data):
    user_id = data.get('user_id')
    if user_id:
        with user_lock:
            active_users[user_id] = 0

if __name__ == "__main__":
    socketio.run(app, debug=True, host="0.0.0.0", port=8080)
