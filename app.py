from flask import Flask, render_template, request, redirect, url_for
import pandas as pd
import os, csv
from datetime import date

app = Flask(__name__)
app.secret_key = "supersecretkey"

USERS_CSV  = 'users.csv'
CART_CSV   = 'cart.csv'
ORDERS_CSV = 'orders.csv'


def init_db():
    if not os.path.exists(USERS_CSV):
        pd.DataFrame(columns=['role', 'name', 'email', 'mobile', 'address', 'password'])\
          .to_csv(USERS_CSV, index=False)
    if not os.path.exists(ORDERS_CSV):
        pd.DataFrame(columns=['id', 'name', 'price', 'image', 'qty', 'shopkeeper_name', 'date', 'status'])\
          .to_csv(ORDERS_CSV, index=False)

init_db()


def read_cart():
    if not os.path.exists(CART_CSV):
        return {}
    with open(CART_CSV, newline="") as f:
        return {r["id"]: {**r, "price": int(r["price"]), "qty": int(r["qty"])}
                for r in csv.DictReader(f)}


def write_cart(cart):
    with open(CART_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "name", "price", "image", "qty", "shopkeeper_name", "date"])
        w.writeheader()
        for item in cart.values():
            item['shopkeeper_name'] = current_shopkeeper['name']
            item['date'] = date.today()
            w.writerow(item)


def read_orders():
    if not os.path.exists(ORDERS_CSV):
        return pd.DataFrame(columns=['id', 'name', 'price', 'image', 'qty', 'shopkeeper_name', 'date', 'status'])
    return pd.read_csv(ORDERS_CSV)


current_shopkeeper = {}


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
        if not df.empty and user_data['email'] in df['email'].astype(str).str.strip().values:
            return "Error: Email already exists!"
        df = pd.concat([df, pd.DataFrame([user_data])], ignore_index=True)
        df.to_csv(USERS_CSV, index=False)
        if user_data['role'] == 'shopkeeper':
            return redirect(url_for('shopkeeper_login'))
        else:
            return redirect(url_for('wholesaler_login'))
    return render_template('register.html')


@app.route('/login-shopkeeper', methods=['GET', 'POST'])
def shopkeeper_login():
    global current_shopkeeper
    if request.method == 'POST':
        email    = request.form.get('email').strip().lower()
        password = request.form.get('password').strip()
        df       = pd.read_csv(USERS_CSV)
        user     = df[
            (df['email'].astype(str).str.strip() == email) &
            (df['password'].astype(str).str.strip() == password) &
            (df['role'].astype(str).str.strip() == 'shopkeeper')
        ]
        if not user.empty:
            current_shopkeeper = user.iloc[0].to_dict()
            return redirect(url_for('shopkeeper_dashboard'))
        return "Invalid Shopkeeper Login!"
    return render_template('shopkeeper-login.html')


@app.route('/login-wholesaler', methods=['GET', 'POST'])
def wholesaler_login():
    if request.method == 'POST':
        email    = request.form.get('email').strip().lower()
        password = request.form.get('password').strip()
        df       = pd.read_csv(USERS_CSV)
        user     = df[
            (df['email'].astype(str).str.strip() == email) &
            (df['password'].astype(str).str.strip() == password) &
            (df['role'].astype(str).str.strip() == 'wholesaler')
        ]
        if not user.empty:
            return redirect(url_for('wholesaler_dashboard'))
        return "Invalid Wholesaler Login!"
    return render_template('wholesaler-login.html')


@app.route('/shopkeeper-dashboard')
def shopkeeper_dashboard():
    return render_template('dashboard.html')


@app.route('/category/<name>')
def category(name):
    return render_template(f'{name}.html')


@app.route('/cart')
def view_cart():
    cart_dict = read_cart()
    cart      = list(cart_dict.values())
    subtotal  = sum(i["price"] * i["qty"] for i in cart)
    tax       = round(subtotal * 0.05)
    return render_template('cart.html', cart=cart, subtotal=subtotal, tax=tax, total=subtotal + tax)


@app.route('/cart/add', methods=['POST'])
def add():
    f       = request.form
    cart    = read_cart()
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
    f       = request.form
    cart    = read_cart()
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


@app.route('/wholesaler-dashboard')
def wholesaler_dashboard():
    orders = read_orders()
    if os.path.exists(CART_CSV):
        cart = pd.read_csv(CART_CSV)
        if not cart.empty:
            cart['status'] = 'incoming'
            if not orders.empty:
                already_added = orders['id'].astype(str).values
                cart = cart[~cart['id'].astype(str).isin(already_added)]
            if not cart.empty:
                orders = pd.concat([orders, cart], ignore_index=True)
                orders.to_csv(ORDERS_CSV, index=False)

    total_orders      = len(orders)
    total_shopkeepers = orders['shopkeeper_name'].nunique() if not orders.empty else 0
    completed_count   = len(orders[orders['status'] == 'completed']) if not orders.empty else 0

    shopkeepers = []
    if not orders.empty:
        for name, group in orders.groupby('shopkeeper_name'):
            shopkeepers.append({
                'shopkeeper_name': name,
                'order_count':     len(group),
                'last_date':       group['date'].max()
            })

    return render_template('wholesaler.html',
                           total_orders=total_orders,
                           total_shopkeepers=total_shopkeepers,
                           completed_count=completed_count,
                           shopkeepers=shopkeepers)


@app.route('/wholesaler/incoming')
def incoming_orders():
    orders = read_orders()
    if orders.empty or 'status' not in orders.columns:
        incoming = []
    else:
        incoming = orders[orders['status'] == 'incoming'].to_dict(orient='records')
    return render_template('incoming.html', orders=incoming)


@app.route('/wholesaler/completed')
def completed_orders():
    orders = read_orders()
    if orders.empty or 'status' not in orders.columns:
        completed = []
    else:
        completed = orders[orders['status'] == 'completed'].to_dict(orient='records')
    return render_template('completed.html', orders=completed)


@app.route('/wholesaler/complete-order', methods=['POST'])
def complete_order():
    order_id   = request.form.get('order_id')
    new_status = request.form.get('new_status')
    orders     = read_orders()
    orders.loc[orders['id'].astype(str) == str(order_id), 'status'] = new_status
    orders.to_csv(ORDERS_CSV, index=False)
    return redirect(url_for('incoming_orders'))


@app.route('/wholesaler/shopkeeper', methods=['POST'])
def shopkeeper_orders():
    name   = request.form.get('name')
    orders = read_orders()
    if orders.empty:
        result = []
    else:
        result = orders[orders['shopkeeper_name'] == name].to_dict(orient='records')
    return render_template('shopkeeper_orders.html', shopkeeper_name=name, orders=result)


@app.route('/wholesaler/chat')
def chat():
    return render_template('chat.html')


if __name__ == '__main__':
    app.run(debug=True, port=5001)