from flask import Flask, render_template, request

app = Flask(__name__, template_folder='Frontend', static_folder='Frontend/static')

@app.route("/")
def home():
    return render_template("login.html")  

@app.route("/register", methods=["GET", "POST"])
def register():
        #mango logic goes here 
       
    return render_template("register.html")  

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=8080)
