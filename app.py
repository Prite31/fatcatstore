from flask import Flask, render_template, request, redirect, session, jsonify, url_for
import requests as req
import time
import os
from authlib.integrations.flask_client import OAuth

app = Flask(__name__)
app.secret_key = "fatcatstore2026"

from werkzeug.middleware.proxy_fix import ProxyFix
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# ===== Google OAuth =====
oauth = OAuth(app)
google = oauth.register(
    name="google",
    client_id=os.environ.get("GOOGLE_CLIENT_ID"),
    client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

users = {
    "admin": {"password": "1234", "credit": 0, "role": "admin", "total_topup": 0}
}

pending_slips = []
purchase_history = []

online_users = {}
ONLINE_TIMEOUT = 300

def update_online(username):
    online_users[username] = time.time()

def get_online_count():
    now = time.time()
    return sum(1 for t in online_users.values() if now - t < ONLINE_TIMEOUT)

def get_display(username):
    """คืนชื่อที่จะแสดงใน navbar — ถ้า Google user ใช้ display_name ถ้าปกติใช้ username"""
    if username in users:
        return users[username].get("display_name", username)
    return username

products = [
    {"id": 1, "name": "Robux 400", "description": "Roblox 400 Robux เข้าเกมทันที", "price": 99, "stock": 10, "icon": "💎", "recommended": True},
    {"id": 2, "name": "Robux 800", "description": "Roblox 800 Robux ราคาคุ้มค่า", "price": 189, "stock": 5, "icon": "💎", "recommended": True},
    {"id": 3, "name": "Robux 1700", "description": "Roblox 1700 Robux แพ็กใหญ่ประหยัด", "price": 379, "stock": 0, "icon": "💎", "recommended": False},
]

def get_user():
    if "user" not in session:
        return None
    if session["user"] not in users:
        session.pop("user", None)
        return None
    update_online(session["user"])
    return users[session["user"]]

def get_product(product_id):
    return next((p for p in products if p["id"] == product_id), None)

@app.route("/")
def home():
    user = get_user()
    username = session.get("user")
    return render_template("index.html",
        user=get_display(username) if username else None,
        credit=user["credit"] if user else 0,
        products=products,
        total_users=len(users),
        online_count=get_online_count(),
        total_topup=user["total_topup"] if user else 0)

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
        if username in users and users[username].get("password") and users[username]["password"] == password:
            session["user"] = username
            update_online(username)
            return redirect("/login-success")
        return render_template("login.html", error="ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")
    return render_template("login.html")

@app.route("/auth/google")
def auth_google():
    redirect_uri = url_for("auth_google_callback", _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route("/auth/google/callback")
def auth_google_callback():
    token = google.authorize_access_token()
    userinfo = token["userinfo"]
    email = userinfo["email"]
    name = userinfo.get("name", email.split("@")[0])
    username = email
    if username not in users:
        users[username] = {
            "password": None,
            "credit": 0,
            "role": "user",
            "total_topup": 0,
            "display_name": name,
            "google": True
        }
    session["user"] = username
    update_online(username)
    return redirect("/login-success")

@app.route("/login-success")
def login_success():
    user = get_user()
    if not user:
        return redirect("/login")
    return render_template("login_success.html",
        username=get_display(session["user"]),
        credit=user["credit"])

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        if username in users:
            return render_template("register.html", error="⚠️ มีบัญชีชื่อนี้อยู่แล้ว กรุณาใช้ชื่ออื่นหรือเข้าสู่ระบบ")
        users[username] = {"password": password, "credit": 0, "role": "user", "total_topup": 0}
        session["user"] = username
        update_online(username)
        return redirect("/login-success")
    return render_template("register.html")

@app.route("/logout")
def logout():
    if "user" in session and session["user"] in online_users:
        del online_users[session["user"]]
    session.pop("user", None)
    return redirect("/")

@app.route("/profile")
def profile():
    user = get_user()
    if not user:
        return redirect("/login")
    return render_template("profile.html",
        username=get_display(session["user"]),
        credit=user["credit"])

@app.route("/topup")
def topup():
    user = get_user()
    if not user:
        return redirect("/login")
    return render_template("topup.html", credit=user["credit"])

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
            return render_template("payment.html", success=True, amount=amount, credit=user["credit"])
    return render_template("payment.html", credit=user["credit"])

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
    user_purchases = [p for p in purchase_history if p["user"] == session["user"]]
    return render_template("history.html",
        username=get_display(session["user"]),
        credit=user["credit"],
        slips=user_slips,
        purchases=user_purchases)

@app.route("/shop")
def shop():
    user = get_user()
    username = session.get("user")
    return render_template("shop.html",
        user=get_display(username) if username else None,
        credit=user["credit"] if user else 0,
        products=products)

@app.route("/buy/<int:product_id>", methods=["GET", "POST"])
def buy(product_id):
    user = get_user()
    if not user:
        return redirect("/login")
    product = get_product(product_id)
    if not product:
        return redirect("/shop")
    if request.method == "POST":
        if product["stock"] <= 0:
            return render_template("buy.html", product=product, credit=user["credit"], error="สินค้าหมดแล้ว")
        if user["credit"] < product["price"]:
            return render_template("buy.html", product=product, credit=user["credit"],
                error=f"เครดิตไม่พอ (ต้องการ ฿{product['price']} มีอยู่ ฿{user['credit']})")
        users[session["user"]]["credit"] -= product["price"]
        product["stock"] -= 1
        purchase_history.append({
            "user": session["user"],
            "product": product["name"],
            "price": product["price"],
            "product_id": product_id
        })
        return render_template("buy.html", product=product, credit=users[session["user"]]["credit"], success=True)
    return render_template("buy.html", product=product, credit=user["credit"])

@app.route("/admin/topup", methods=["POST"])
def admin_topup():
    user = get_user()
    if not user or user.get("role") != "admin":
        return jsonify({"error": "Unauthorized"}), 403
    target = request.json.get("username")
    amount = request.json.get("amount", 0)
    if target not in users:
        return jsonify({"error": "ไม่พบผู้ใช้"}), 404
    users[target]["credit"] += int(amount)
    users[target]["total_topup"] += int(amount)
    return jsonify({"success": True, "credit": users[target]["credit"]})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=False)