from flask import Flask, render_template, request, redirect, make_response, send_file, jsonify, url_for, send_from_directory
from flask_socketio import SocketIO, emit
from flask_pymongo import PyMongo
from flask_bcrypt import Bcrypt
from pymongo import MongoClient
from bson import ObjectId
from werkzeug.utils import secure_filename
import hashlib
import os
import uuid
from html import escape
import time

app = Flask(__name__, template_folder='Frontend', static_folder='Frontend/static')
app.config['UPLOAD_FOLDER'] = 'Frontend/uploads'
socketio = SocketIO(app, cors_allowed_origins="*", transports=['websocket'])

bcrypt = Bcrypt(app)

mongo_client = MongoClient('mongo')  
db = mongo_client['user_auth_db']
users_collection = db['users']
quizzes_collection = db['quizzes']
interactions_collection = db['interactions']

ip_request_count = {}
blocked_ip = {}

def check_blocked_ip(ip):
    if ip in blocked_ip:
        if time.time() - blocked_ip[ip] >= 30:
            del blocked_ip[ip]
            return False
        return True
    return False

def check_rate_limit(ip):
    current_time = time.time()
    if ip not in ip_request_count:
        ip_request_count[ip] = []
    
    checked_requests = []
    for timestamp in ip_request_count[ip]:
        if (current_time - timestamp) < 10:
            checked_requests.append(timestamp)
    ip_request_count[ip] = checked_requests
    ip_request_count[ip].append(current_time)

    if len(ip_request_count[ip]) > 50:
        blocked_ip[ip] = current_time
        return False
    return True

@app.before_request
def check_dos_protection():
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if check_blocked_ip(ip):
        return "Too Many Requests", 429
    if not check_rate_limit(ip):
        return "Too Many Requests", 429

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

@app.route("/profile")
def profile():
    username = request.cookies.get("username")
    if not username:
        return redirect(url_for("home"))
    user = users_collection.find_one({"username": username})
    if not user:
        return redirect(url_for("home"))
    pfp = user.get("profile_picture", "/static/default-pfp.jpg")
    response = make_response(render_template("profile.html", user_pfp=pfp))
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


def allowed_file(filename):
    ALLOWED_EXTENSIONS = {"jpg"}
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/profile/upload", methods=["POST"])
def upload_pfp():
    if "file" not in request.files:
        return jsonify({'status': 'error', 'message': 'No file selected'}), 400

    file = request.files["file"]

    # Check if the user selected a file
    if file.filename == "":
        return jsonify({'status': 'error', 'message': 'No file selected'}), 400

    if file and allowed_file(file.filename):
        file_extension = file.filename.rsplit('.', 1)[1].lower()
        random_filename = f"{uuid.uuid4().hex}.{file_extension}"  # Generate a random filename
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], random_filename)
        file.save(filepath)

        # Update the user's profile picture in the database
        username = request.cookies.get("username")
        if username:
            users_collection.update_one(
                {"username": username},
                {"$set": {"profile_picture": f"/uploads/{random_filename}"}}
            )
            return jsonify({'status': 'ok', 'message': 'Profile picture updated successfully!', 'profile_picture': f"/{filepath}"}), 200

        return jsonify({'status': 'error', 'message': 'User not authenticated'}), 401

    return jsonify({'status': 'error', 'message': 'Invalid file format'}), 400

@app.route('/uploads/<filename>')
def serve_uploaded_file(filename):
    try:
        file_path = os.path.join(os.getcwd(), "Frontend/uploads", filename)
        print("Resolved file path:", file_path)  # Debugging output
        response = send_file(file_path, mimetype="image/jpg")
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response
    except FileNotFoundError:
        return jsonify({'status': 'error', 'message': 'File not found'}), 404


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


if __name__ == "__main__":
    socketio.run(app, debug=True, host="0.0.0.0", port=8080)