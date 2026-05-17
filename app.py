from flask import Flask, render_template, request, redirect, session, jsonify
import os
import requests as req

app = Flask(__name__)
app.secret_key = "fatcatstore2026"

users = {
    "admin": {"password": "1234", "credit": 0, "role": "admin"}
}

pending_slips = []

def get_user():
    """คืนค่า user dict ถ้า session valid, ไม่งั้น return None"""
    if "user" not in session:
        return None
    if session["user"] not in users:
        session.pop("user", None)
        return None
    return users[session["user"]]

@app.route("/")
def home():
    user = get_user()
    return render_template("index.html",
        user=session.get("user"),
        credit=user["credit"] if user else 0)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        recaptcha = request.form.get("g-recaptcha-response", "")

        verify = req.post("https://www.google.com/recaptcha/api/siteverify", data={
            "secret": "6Le5B-4sAAAAKMO6d5Lhi0U3QQf7Z0cL4g7JgoD",
            "response": recaptcha
        }).json()

        # if not verify.get("success"):
        #     return render_template("login.html", error="กรุณายืนยันว่าไม่ใช่บอทก่อน")

        if username in users and users[username]["password"] == password:
            session["user"] = username
            return redirect("/login-success")
        return render_template("login.html", error="ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")
    return render_template("login.html")

@app.route("/login-success")
def login_success():
    user = get_user()
    if not user:
        return redirect("/login")
    return render_template("login_success.html",
        username=session["user"],
        credit=user["credit"])

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        if username in users:
            return render_template("register.html", error="ชื่อผู้ใช้นี้มีอยู่แล้ว")
        users[username] = {"password": password, "credit": 0, "role": "user"}
        session["user"] = username
        return redirect("/login-success")
    return render_template("register.html")

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect("/")

@app.route("/profile")
def profile():
    user = get_user()
    if not user:
        return redirect("/login")
    return render_template("profile.html",
        username=session["user"],
        credit=user["credit"])

@app.route("/topup")
def topup():
    user = get_user()
    if not user:
        return redirect("/login")
    return render_template("topup.html",
        credit=user["credit"])

@app.route("/payment", methods=["GET", "POST"])
def payment():
    user = get_user()
    if not user:
        return redirect("/login")
    if request.method == "POST":
        amount = request.form.get("amount", 0)
        slip = request.files.get("slip")
        if slip and amount:
            pending_slips.append({
                "user": session["user"],
                "amount": int(amount),
                "filename": slip.filename
            })
            return render_template("payment.html",
                success=True, amount=amount,
                credit=user["credit"])
    return render_template("payment.html",
        credit=user["credit"])

@app.route("/credit")
def credit():
    user = get_user()
    if not user:
        return jsonify({"credit": 0})
    return jsonify({"credit": user["credit"]})

@app.route("/history")
def history():
    user = get_user()
    if not user:
        return redirect("/login")
    user_slips = [s for s in pending_slips if s["user"] == session["user"]]
    return render_template("history.html",
        username=session["user"],
        credit=user["credit"],
        slips=user_slips)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=False)
