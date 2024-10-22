from flask import Flask, render_template

app = Flask(__name__, template_folder='frontend', static_folder='frontend/static')

@app.route("/")
def home():
    return render_template("bb.html")

@app.route("/css")
def css_path():
    return render_template("style.css")

@app.route("/image")
def image_path():
    return render_template("")

@app.route("/js")
def js_path():
    return render_template("")

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=8080)  
