from flask import Flask, render_template, request, redirect, url_for
import pandas as pd
import os, csv

app = Flask(__name__)
app.secret_key = "supersecretkey"

USERS_CSV = 'users.csv'
CART_CSV  = 'cart.csv'




def init_db():
    if not os.path.exists(USERS_CSV):
        pd.DataFrame(columns=['role','name','email','mobile','address','password'])\
          .to_csv(USERS_CSV, index=False)



def read_cart():
    if not os.path.exists(CART_CSV):
        return {}
    with open(CART_CSV, newline="") as f:
        return {r["id"]: {**r, "price": int(r["price"]), "qty": int(r["qty"])}
                for r in csv.DictReader(f)}

def write_cart(cart):
    with open(CART_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id","name","price","image","qty"])
        w.writeheader()
        w.writerows(cart.values())



@app.route('/')
def index():
    return redirect(url_for('register'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        user_data = {
            "role":     request.form.get('role').strip(),
            "name":     request.form.get('fullname').strip(),
            "email":    request.form.get('email').strip().lower(),
            "mobile":   request.form.get('mobile').strip(),
            "address":  request.form.get('address').strip(),
            "password": request.form.get('password').strip()
        }
        df = pd.read_csv(USERS_CSV)
        if not df.empty and user_data['email'] in df['email'].astype(str).values:
            return "Error: Email already exists!"
        df = pd.concat([df, pd.DataFrame([user_data])], ignore_index=True)
        df.to_csv(USERS_CSV, index=False)
        return redirect(url_for('shopkeeper_login' if user_data['role'] == 'shopkeeper' else 'wholesaler_login'))
    return render_template('register.html')

@app.route('/login-shopkeeper', methods=['GET', 'POST'])
def shopkeeper_login():
    if request.method == 'POST':
        email    = request.form.get('email').strip().lower()
        password = request.form.get('password').strip()
        df = pd.read_csv(USERS_CSV)
        user = df[(df['email'].astype(str) == email) &
                  (df['password'].astype(str) == password) &
                  (df['role'] == 'shopkeeper')]
        if not user.empty:
            return redirect(url_for('shopkeeper_dashboard'))
        return "Invalid Shopkeeper Login!"
    return render_template('shopkeeper-login.html')

@app.route('/login-wholesaler', methods=['GET', 'POST'])
def wholesaler_login():
    if request.method == 'POST':
        email    = request.form.get('email').strip().lower()
        password = request.form.get('password').strip()
        df = pd.read_csv(USERS_CSV)
        user = df[(df['email'].astype(str) == email) &
                  (df['password'].astype(str) == password) &
                  (df['role'] == 'wholesaler')]
        if not user.empty:
            return redirect(url_for('wholesaler_dashboard'))
        return "Invalid Wholesaler Login!"
    return render_template('wholesaler-login.html')

@app.route('/shopkeeper-dashboard')
def shopkeeper_dashboard():
    return render_template('dashboard.html')

@app.route('/wholesaler-dashboard')
def wholesaler_dashboard():
    return render_template('dashboard.html')

@app.route('/category/<name>')
def category(name):
    return render_template(f'{name}.html')



@app.route('/cart')
def view_cart():
    cart_dict = read_cart()
    cart = [{"id": k, **v} for k, v in cart_dict.items()]  
    subtotal = sum(i["price"] * i["qty"] for i in cart)
    tax = round(subtotal * 0.05)
    return render_template('cart.html', cart=cart,
                           subtotal=subtotal, tax=tax, total=subtotal + tax)

@app.route('/cart/add', methods=['POST'])
def add():
    f = request.form
    cart = read_cart()
    item_id = f["item_id"]
    if item_id not in cart:
        cart[item_id] = {"id": item_id, "name": f["name"],
                         "price": int(f["price"]), "image": f["image"], "qty": 1}
    else:
        cart[item_id]["qty"] += 1
    write_cart(cart)
    return redirect(url_for('category', name=f["category"]))

@app.route('/cart/update', methods=['POST'])
def update():
    f = request.form
    cart = read_cart()
    item_id = f["item_id"]
    if item_id in cart:
        cart[item_id]["qty"] += 1 if f["action"] == "increase" else -1
        if cart[item_id]["qty"] <= 0:
            del cart[item_id]
    write_cart(cart)
    if f.get("back") == "view_cart":
        return redirect(url_for('view_cart'))
    return redirect(url_for('category', name=f.get("category", "grocery")))

@app.route('/cart/remove', methods=['POST'])
def remove():
    cart = read_cart()
    cart.pop(request.form["item_id"], None)
    write_cart(cart)
    return redirect(url_for('view_cart'))


if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5001)