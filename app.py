from flask import Flask, render_template, request, redirect, make_response, send_file, jsonify, url_for, send_from_directory
from flask_socketio import SocketIO, emit
from flask_pymongo import PyMongo
from flask_bcrypt import Bcrypt
from pymongo import MongoClient
from bson import ObjectId
import hashlib
import os
import uuid
from html import escape
import time
from random import choice
from datetime import datetime, timedelta
import threading
import pytz

app = Flask(__name__, template_folder='Frontend', static_folder='Frontend/static')
app.config['UPLOAD_FOLDER'] = 'Frontend/uploads'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading", transports=['websocket'])

bcrypt = Bcrypt(app)

mongo_client = MongoClient('mongo')

db = mongo_client['user_auth_db']
users_collection = db['users']
quizzes_collection = db['quizzes']
interactions_collection = db['interactions']
polls_collection = db['polls']


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
    if ',' in ip:
        ip = ip.split(',')[0].strip()
    print(f"Request from IP: {ip}")
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
    response = make_response(render_template("profile.html", user_pfp=pfp, is_not_logged_in=True if validate_session() else False))
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
    return render_template("login.html", is_not_logged_in=True if validate_session() else False)

@app.route("/register_page", methods=["GET"])
def register_page():
    return render_template("register_page.html", is_not_logged_in=True if validate_session() else False)

@app.template_filter('chr')
def chr_filter(value):
    try:
        return chr(value)
    except (ValueError, TypeError):
        return ''

def broadcast_timer():
    ny_tz = pytz.timezone('America/New_York')

    while True:
        now = datetime.now(ny_tz)
        today = now.date()
        reset_time = ny_tz.localize(datetime.combine(today + timedelta(days=1), datetime.min.time()))
        time_left = int((reset_time - now).total_seconds())
        socketio.emit("update_timer", {"time_left": time_left}, to=None)
        
        socketio.sleep(1)

@app.route("/dashboard")
def dashboard():
    username = validate_session()
    if not username:
        return redirect("/?message=Please log in.")

    quizzes = list(quizzes_collection.find())

    today = datetime.utcnow().date()
    today_datetime = datetime.combine(today, datetime.min.time())
    daily_poll = polls_collection.find_one({"date": today_datetime})

    correct_answer = None

    if not quizzes:
        default_quiz = {
    "title": "Cat Trivia",
    "questions": {
        "What is the most popular cat breed in the world?": {
            "correct_answer": "Siamese",
            "choices": ["Persian", "Siamese", "Maine Coon", "Bengal"]
        },
        "What is the average lifespan of an indoor cat?": {
            "correct_answer": "15 years",
            "choices": ["10 years", "12 years", "15 years", "20 years"]
        },
        "What unique feature do cats have that helps them balance?": {
            "correct_answer": "Tail",
            "choices": ["Whiskers", "Tail", "Claws", "Paws"]
        },
        "What is the scientific name for the domestic cat?": {
            "correct_answer": "Felis catus",
            "choices": ["Canis lupus", "Felis catus", "Panthera leo", "Equus ferus"]
        },
        "Which sense is most developed in cats?": {
            "correct_answer": "Hearing",
            "choices": ["Vision", "Hearing", "Smell", "Touch"]
        },
        "How many toes do most cats have on each front paw?": {
            "correct_answer": "5",
            "choices": ["4", "5", "6", "3"]
        },
        "What is a group of cats called?": {
            "correct_answer": "Clowder",
            "choices": ["Pack", "Clowder", "Herd", "Flock"]
        },
        "What does a cat use its whiskers for?": {
            "correct_answer": "To sense their surroundings",
            "choices": ["For decoration", "To sense their surroundings", "To clean their face", "To attract mates"]
        },
        "How many hours a day do cats typically sleep?": {
            "correct_answer": "12-16 hours",
            "choices": ["6-8 hours", "12-16 hours", "18-20 hours", "24 hours"]
        },
        "What is a cat’s top speed?": {
            "correct_answer": "30 mph",
            "choices": ["15 mph", "20 mph", "30 mph", "40 mph"]
        }
    },
    "created_by": "System",
    "likes": 0,
    "comments": []
}
        quizzes_collection.insert_one(default_quiz)
        quizzes = [default_quiz] 

    if not daily_poll:
        random_quiz = choice(quizzes)
        question_text = choice(list(random_quiz["questions"].keys()))
        choices = random_quiz["questions"][question_text]["choices"]

        daily_poll = {
            "question": question_text,
            "choices": choices,
            "quiz_id": random_quiz["_id"],
            "results": {choices[i].strip(): 0 for i in range(len(choices)) if choices[i].strip()},
            "date": today_datetime
        }
        polls_collection.insert_one(daily_poll)

    if daily_poll:
        quiz = quizzes_collection.find_one({"_id": daily_poll["quiz_id"]})
        if quiz and daily_poll["question"] in quiz["questions"]:
            correct_answer = quiz["questions"][daily_poll["question"]]["correct_answer"]

    user_vote = None
    if daily_poll:
        user_vote = interactions_collection.find_one({
            "poll_id": daily_poll["_id"],
            "username": username,
            "type": "vote"
        })

    return render_template(
        "dashboard.html",
        username=username,
        quizzes=quizzes,
        daily_poll=daily_poll,
        poll_results=daily_poll["results"] if user_vote else None,
        correct_answer=correct_answer,
        user_vote=user_vote,
        is_not_logged_in=True if validate_session() else False
    )



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
        return render_template('quizPage.html', quiz=quiz, is_not_logged_in=True if validate_session() else False)
    except Exception as e:
        # Handle any exceptions (e.g., invalid ObjectId format)
        return str(e), 400

@app.route("/submit_poll", methods=["POST"])
def submit_poll():
    username = validate_session()
    if not username:
        return jsonify({"success": False, "message": "User not authenticated."}), 401

    data = request.get_json()
    poll_id = data.get("poll_id")
    selected_answer = data.get("selected_answer")  # Match the JSON key sent by the client


    if not poll_id or not selected_answer:
        return jsonify({"success": False, "message": "Invalid request."}), 400

    try:
        poll_object_id = ObjectId(poll_id)
    except Exception:
        return jsonify({"success": False, "message": "Invalid poll ID."}), 400

    poll = polls_collection.find_one({"_id": poll_object_id})
    if not poll:
        return jsonify({"success": False, "message": "Poll not found."}), 404

    existing_vote = interactions_collection.find_one({
        "poll_id": poll_object_id,
        "username": username,
        "type": "vote"
    })

    if existing_vote:
        return jsonify({"success": False, "message": "User already voted in this poll."}), 403

    interactions_collection.insert_one({
        "poll_id": poll_object_id,
        "username": username,
        "type": "vote",
        "answer": selected_answer
    })

    update_key = f"results.{selected_answer}"
    polls_collection.update_one({"_id": poll_object_id}, {"$inc": {update_key: 1}})

    updated_poll = polls_collection.find_one({"_id": poll_object_id})
    if not updated_poll:
        return jsonify({"success": False, "message": "Poll update failed."}), 500

    return jsonify({"success": True})

if __name__ == "__main__":
    threading.Thread(target=broadcast_timer, daemon=True).start()
    socketio.run(app, debug=True, host="0.0.0.0", port=8080, allow_unsafe_werkzeug=True)