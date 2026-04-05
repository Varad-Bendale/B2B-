from flask import Flask, render_template, request, redirect, url_for, session
import pandas as pd
import os, csv, io, base64
from datetime import date
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

app = Flask(__name__)
app.secret_key = "supersecretkey"

USERS_CSV  = 'users.csv'
CART_CSV   = 'cart.csv'
ORDERS_CSV = 'orders.csv'
CHAT_CSV   = 'chat.csv'


def init_db():
    if not os.path.exists(USERS_CSV):
        pd.DataFrame(columns=['role', 'name', 'email', 'mobile', 'address', 'password'])\
          .to_csv(USERS_CSV, index=False)
    if not os.path.exists(ORDERS_CSV):
        pd.DataFrame(columns=['id', 'name', 'price', 'image', 'qty',
                               'shopkeeper_email', 'shopkeeper_name',
                               'wholesaler_email', 'date', 'status'])\
          .to_csv(ORDERS_CSV, index=False)
    if not os.path.exists(CHAT_CSV):
        # chat_key = shopkeeper_email + "|" + wholesaler_email  (unique per pair)
        pd.DataFrame(columns=['timestamp', 'sender_role', 'sender_name',
                               'shopkeeper_email', 'wholesaler_email', 'message'])\
          .to_csv(CHAT_CSV, index=False)

init_db()


# ── Cart helpers ──────────────────────────────────────────────────────────────

def read_cart():
    if not os.path.exists(CART_CSV):
        return {}
    with open(CART_CSV, newline="") as f:
        reader = csv.DictReader(f)
        result = {}
        for r in reader:
            result[r["id"]] = {
                "id":               r.get("id", ""),
                "name":             r.get("name", ""),
                "price":            int(r.get("price", 0)),
                "image":            r.get("image", ""),
                "qty":              int(r.get("qty", 1)),
                "shopkeeper_email": r.get("shopkeeper_email", ""),
                "shopkeeper_name":  r.get("shopkeeper_name", ""),
                "wholesaler_email": r.get("wholesaler_email", ""),
                "date":             r.get("date", ""),
            }
        return result


def write_cart(cart):
    with open(CART_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[
            "id", "name", "price", "image", "qty",
            "shopkeeper_email", "shopkeeper_name", "wholesaler_email", "date"
        ])
        w.writeheader()
        for item in cart.values():
            item['shopkeeper_email'] = session.get('shopkeeper_email', '')
            item['shopkeeper_name']  = session.get('shopkeeper_name', '')
            item['wholesaler_email'] = session.get('wholesaler_email', '')
            item['date'] = str(date.today())
            w.writerow(item)


def read_orders():
    if not os.path.exists(ORDERS_CSV):
        return pd.DataFrame(columns=[
            'id', 'name', 'price', 'image', 'qty',
            'shopkeeper_email', 'shopkeeper_name',
            'wholesaler_email', 'date', 'status'
        ])
    df = pd.read_csv(ORDERS_CSV)
    for col in ['shopkeeper_email', 'shopkeeper_name', 'wholesaler_email']:
        if col not in df.columns:
            df[col] = ''
    return df


# ── Chat helpers ──────────────────────────────────────────────────────────────

def read_messages(shopkeeper_email, wholesaler_email):
    """Return last 100 messages between this specific shopkeeper-wholesaler pair."""
    if not os.path.exists(CHAT_CSV):
        return []
    df = pd.read_csv(CHAT_CSV)
    if df.empty:
        return []
    mask = (
        (df['shopkeeper_email'].astype(str).str.strip() == shopkeeper_email.strip()) &
        (df['wholesaler_email'].astype(str).str.strip() == wholesaler_email.strip())
    )
    return df[mask].tail(100).to_dict(orient='records')


def write_message(sender_role, sender_name, shopkeeper_email, wholesaler_email, message):
    from datetime import datetime
    row = {
        'timestamp':        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'sender_role':      sender_role,
        'sender_name':      sender_name,
        'shopkeeper_email': shopkeeper_email,
        'wholesaler_email': wholesaler_email,
        'message':          message.strip()
    }
    if os.path.exists(CHAT_CSV):
        df = pd.read_csv(CHAT_CSV)
        for col in ['shopkeeper_email', 'wholesaler_email']:
            if col not in df.columns:
                df[col] = ''
    else:
        df = pd.DataFrame(columns=[
            'timestamp', 'sender_role', 'sender_name',
            'shopkeeper_email', 'wholesaler_email', 'message'
        ])
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    df.to_csv(CHAT_CSV, index=False)


def get_name_from_email(email):
    """Look up display name from users.csv by email."""
    df = pd.read_csv(USERS_CSV)
    user = df[df['email'].astype(str).str.strip() == email.strip()]
    return user.iloc[0]['name'] if not user.empty else email


def get_wholesalers_for_shopkeeper(shopkeeper_email):
    """Return list of wholesalers this shopkeeper has placed orders with."""
    orders = read_orders()
    if orders.empty:
        return []
    filtered = orders[orders['shopkeeper_email'].astype(str).str.strip() == shopkeeper_email.strip()]
    result = {}
    for _, row in filtered.iterrows():
        we = str(row.get('wholesaler_email', '')).strip()
        if we:
            result[we] = get_name_from_email(we)
    return [{'email': e, 'name': n} for e, n in sorted(result.items(), key=lambda x: x[1])]


def get_shopkeepers_for_wholesaler(wholesaler_email):
    """Return list of shopkeepers who have ordered from this wholesaler."""
    orders = read_orders()
    if orders.empty:
        return []
    filtered = orders[orders['wholesaler_email'].astype(str).str.strip() == wholesaler_email.strip()]
    result = {}
    for _, row in filtered.iterrows():
        se = str(row.get('shopkeeper_email', '')).strip()
        sn = str(row.get('shopkeeper_name', '')).strip()
        if se:
            result[se] = sn if sn else get_name_from_email(se)
    return [{'email': e, 'name': n} for e, n in sorted(result.items(), key=lambda x: x[1])]


# ── Auth decorators ───────────────────────────────────────────────────────────

def shopkeeper_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('shopkeeper_logged_in'):
            return redirect(url_for('shopkeeper_login'))
        return f(*args, **kwargs)
    return decorated


def wholesaler_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('wholesaler_logged_in'):
            return redirect(url_for('wholesaler_login'))
        return f(*args, **kwargs)
    return decorated


# ── Auth routes ───────────────────────────────────────────────────────────────

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
            row = user.iloc[0].to_dict()
            session['shopkeeper_logged_in'] = True
            session['shopkeeper_name']      = row['name']
            session['shopkeeper_email']     = row['email']
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
            row = user.iloc[0].to_dict()
            session['wholesaler_logged_in'] = True
            session['wholesaler_name']      = row['name']
            session['wholesaler_email']     = row['email']
            return redirect(url_for('wholesaler_dashboard'))
        return "Invalid Wholesaler Login!"
    return render_template('wholesaler-login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


# ── Shopkeeper routes ─────────────────────────────────────────────────────────

@app.route('/shopkeeper-dashboard')
@shopkeeper_required
def shopkeeper_dashboard():
    return render_template('dashboard.html')


@app.route('/category/<name>')
@shopkeeper_required
def category(name):
    return render_template(f'{name}.html')


@app.route('/cart')
@shopkeeper_required
def view_cart():
    cart_dict = read_cart()
    cart      = list(cart_dict.values())
    subtotal  = sum(i["price"] * i["qty"] for i in cart)
    tax       = round(subtotal * 0.05)
    return render_template('cart.html', cart=cart, subtotal=subtotal, tax=tax, total=subtotal + tax)


@app.route('/cart/add', methods=['POST'])
@shopkeeper_required
def add():
    f       = request.form
    cart    = read_cart()
    item_id = f["item_id"]
    if item_id not in cart:
        cart[item_id] = {
            "id":               item_id,
            "name":             f["name"],
            "price":            int(f["price"]),
            "image":            f["image"],
            "qty":              1,
            "shopkeeper_email": session.get('shopkeeper_email', ''),
            "shopkeeper_name":  session.get('shopkeeper_name', ''),
            "wholesaler_email": session.get('wholesaler_email', ''),
            "date":             str(date.today())
        }
    else:
        cart[item_id]["qty"] += 1
    write_cart(cart)
    return redirect(url_for('category', name=f["category"]))


@app.route('/cart/update', methods=['POST'])
@shopkeeper_required
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
@shopkeeper_required
def remove():
    cart = read_cart()
    cart.pop(request.form["item_id"], None)
    write_cart(cart)
    return redirect(url_for('view_cart'))


@app.route('/cart/checkout', methods=['POST'])
@shopkeeper_required
def checkout():
    cart = read_cart()
    if not cart:
        return redirect(url_for('view_cart'))

    orders       = read_orders()
    existing_ids = set(orders['id'].astype(str).values) if not orders.empty else set()

    new_rows = []
    for item in cart.values():
        if str(item['id']) not in existing_ids:
            new_rows.append({
                'id':               item['id'],
                'name':             item['name'],
                'price':            item['price'],
                'image':            item['image'],
                'qty':              item['qty'],
                'shopkeeper_email': session.get('shopkeeper_email', ''),
                'shopkeeper_name':  session.get('shopkeeper_name', ''),
                'wholesaler_email': session.get('wholesaler_email', ''),
                'date':             str(date.today()),
                'status':           'incoming',
            })

    if new_rows:
        orders = pd.concat([orders, pd.DataFrame(new_rows)], ignore_index=True)
        orders.to_csv(ORDERS_CSV, index=False)

    if os.path.exists(CART_CSV):
        os.remove(CART_CSV)

    return redirect(url_for('shopkeeper_dashboard'))


# ── Wholesaler routes ─────────────────────────────────────────────────────────

@app.route('/wholesaler-dashboard')
@wholesaler_required
def wholesaler_dashboard():
    wholesaler_email = session.get('wholesaler_email', '')
    orders = read_orders()
    orders = orders[orders['wholesaler_email'].astype(str).str.strip() == wholesaler_email] \
             if not orders.empty else orders

    total_orders      = len(orders)
    total_shopkeepers = orders['shopkeeper_email'].nunique() if not orders.empty else 0
    completed_count   = len(orders[orders['status'] == 'completed']) if not orders.empty else 0

    shopkeepers = []
    if not orders.empty:
        for email, group in orders.groupby('shopkeeper_email'):
            shopkeepers.append({
                'shopkeeper_name':  group['shopkeeper_name'].iloc[0],
                'shopkeeper_email': email,
                'order_count':      len(group),
                'last_date':        group['date'].max()
            })

    return render_template('wholesaler.html',
                           total_orders=total_orders,
                           total_shopkeepers=total_shopkeepers,
                           completed_count=completed_count,
                           shopkeepers=shopkeepers)


@app.route('/wholesaler/incoming')
@wholesaler_required
def incoming_orders():
    wholesaler_email = session.get('wholesaler_email', '')
    orders = read_orders()
    if orders.empty or 'status' not in orders.columns:
        incoming = []
    else:
        incoming = orders[
            (orders['status'] == 'incoming') &
            (orders['wholesaler_email'].astype(str).str.strip() == wholesaler_email)
        ].to_dict(orient='records')
    return render_template('incoming.html', orders=incoming)


@app.route('/wholesaler/completed')
@wholesaler_required
def completed_orders():
    wholesaler_email = session.get('wholesaler_email', '')
    orders = read_orders()
    chart  = None
    if orders.empty or 'status' not in orders.columns:
        completed = []
    else:
        completed_df = orders[
            (orders['status'] == 'completed') &
            (orders['wholesaler_email'].astype(str).str.strip() == wholesaler_email)
        ]
        completed = completed_df.to_dict(orient='records')

        if not completed_df.empty and 'name' in completed_df.columns:
            completed_df['qty'] = pd.to_numeric(completed_df['qty'], errors='coerce').fillna(1)
            counts = completed_df.groupby('name')['qty'].sum().sort_values(ascending=False)
            fig, ax = plt.subplots(figsize=(8, 8))
            ax.pie(counts.values, labels=counts.index, autopct='%1.1f%%',
                   startangle=140, pctdistance=0.82)
            ax.set_title('Completed Orders — Units Dispatched per Product', fontsize=13, pad=20)
            buf = io.BytesIO()
            plt.savefig(buf, format='png', bbox_inches='tight')
            buf.seek(0)
            chart = base64.b64encode(buf.read()).decode('utf-8')
            plt.close(fig)

    return render_template('completed.html', orders=completed, chart=chart)


@app.route('/wholesaler/complete-order', methods=['POST'])
@wholesaler_required
def complete_order():
    order_id   = request.form.get('order_id')
    new_status = request.form.get('new_status')
    orders     = read_orders()
    orders.loc[orders['id'].astype(str) == str(order_id), 'status'] = new_status
    orders.to_csv(ORDERS_CSV, index=False)
    return redirect(url_for('incoming_orders'))


@app.route('/wholesaler/shopkeeper', methods=['POST'])
@wholesaler_required
def shopkeeper_orders():
    email  = request.form.get('email', '')
    name   = request.form.get('name', email)
    orders = read_orders()
    if orders.empty:
        result = []
    else:
        result = orders[orders['shopkeeper_email'].astype(str) == email].to_dict(orient='records')
    return render_template('shopkeeper_orders.html', shopkeeper_name=name, orders=result)


# ── Wholesaler chat ───────────────────────────────────────────────────────────

@app.route('/wholesaler/chat')
@wholesaler_required
def wholesaler_chat():
    wholesaler_email = session.get('wholesaler_email', '')
    shopkeepers = get_shopkeepers_for_wholesaler(wholesaler_email)
    return render_template('wholesaler_chat_list.html', shopkeepers=shopkeepers)


@app.route('/wholesaler/chat/<path:shopkeeper_email>')
@wholesaler_required
def wholesaler_chat_room(shopkeeper_email):
    wholesaler_email = session.get('wholesaler_email', '')
    sk_name          = get_name_from_email(shopkeeper_email)
    messages         = read_messages(shopkeeper_email, wholesaler_email)
    return render_template('chat.html',
                           role='wholesaler',
                           sender_name=session.get('wholesaler_name', 'Wholesaler'),
                           shopkeeper_email=shopkeeper_email,
                           wholesaler_email=wholesaler_email,
                           shopkeeper_name=sk_name,
                           room_title=f'Chat with {sk_name}',
                           messages=messages,
                           send_url=url_for('wholesaler_chat_send', shopkeeper_email=shopkeeper_email),
                           back_url=url_for('wholesaler_chat'))


@app.route('/wholesaler/chat/<path:shopkeeper_email>/send', methods=['POST'])
@wholesaler_required
def wholesaler_chat_send(shopkeeper_email):
    wholesaler_email = session.get('wholesaler_email', '')
    wholesaler_name  = session.get('wholesaler_name', 'Wholesaler')
    msg = request.form.get('message', '').strip()
    if msg:
        write_message('wholesaler', wholesaler_name, shopkeeper_email, wholesaler_email, msg)
    return redirect(url_for('wholesaler_chat_room', shopkeeper_email=shopkeeper_email))


# ── Shopkeeper chat ───────────────────────────────────────────────────────────

@app.route('/shopkeeper/chat')
@shopkeeper_required
def shopkeeper_chat():
    sk_email    = session.get('shopkeeper_email', '')
    wholesalers = get_wholesalers_for_shopkeeper(sk_email)
    return render_template('shopkeeper_chat_list.html', wholesalers=wholesalers)


@app.route('/shopkeeper/chat/<path:wholesaler_email>')
@shopkeeper_required
def shopkeeper_chat_room(wholesaler_email):
    sk_email = session.get('shopkeeper_email', '')
    sk_name  = session.get('shopkeeper_name', 'Shopkeeper')
    w_name   = get_name_from_email(wholesaler_email)
    messages = read_messages(sk_email, wholesaler_email)
    return render_template('chat.html',
                           role='shopkeeper',
                           sender_name=sk_name,
                           shopkeeper_email=sk_email,
                           wholesaler_email=wholesaler_email,
                           shopkeeper_name=sk_name,
                           room_title=f'Chat with {w_name}',
                           messages=messages,
                           send_url=url_for('shopkeeper_chat_send', wholesaler_email=wholesaler_email),
                           back_url=url_for('shopkeeper_chat'))


@app.route('/shopkeeper/chat/<path:wholesaler_email>/send', methods=['POST'])
@shopkeeper_required
def shopkeeper_chat_send(wholesaler_email):
    sk_email = session.get('shopkeeper_email', '')
    sk_name  = session.get('shopkeeper_name', 'Shopkeeper')
    msg      = request.form.get('message', '').strip()
    if msg:
        write_message('shopkeeper', sk_name, sk_email, wholesaler_email, msg)
    return redirect(url_for('shopkeeper_chat_room', wholesaler_email=wholesaler_email))


if __name__ == '__main__':
    app.run(debug=True, port=5001)