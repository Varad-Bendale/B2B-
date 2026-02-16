from flask import Flask, render_template, request, redirect, url_for, flash
import pandas as pd
import os

app = Flask(__name__)
app.secret_key = "supersecretkey" 

CSV_FILE = 'users.csv'

def init_db():
    if not os.path.exists(CSV_FILE):
        df = pd.DataFrame(columns=['role', 'name', 'email', 'mobile', 'address', 'password'])
        df.to_csv(CSV_FILE, index=False)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        user_data = {
            "role": request.form.get('role').strip(),
            "name": request.form.get('fullname').strip(),
            "email": request.form.get('email').strip().lower(), 
            "mobile": request.form.get('mobile').strip(),
            "address": request.form.get('address').strip(),
            "password": request.form.get('password').strip()
        }
        
        df = pd.read_csv(CSV_FILE)
        
        if not df.empty and user_data['email'] in df['email'].astype(str).values:
            return "Error: Email already exists! Go back and try a different one."

        new_user_df = pd.DataFrame([user_data])
        df = pd.concat([df, new_user_df], ignore_index=True)
        df.to_csv(CSV_FILE, index=False)

        if user_data['role'] == 'shopkeeper':
            return redirect(url_for('shopkeeper_login'))
        else:
            return redirect(url_for('wholeseller_login'))

    return render_template('register.html')

@app.route('/login-shopkeeper', methods=['GET', 'POST'])
def shopkeeper_login():
    if request.method == 'POST':
        email = request.form.get('email').strip().lower()
        password = request.form.get('password').strip()

        df = pd.read_csv(CSV_FILE)
        
        user = df[
            (df['email'].astype(str) == email) & 
            (df['password'].astype(str) == password) & 
            (df['role'] == 'shopkeeper')
        ]
        
        if not user.empty:
            return redirect(url_for('shopkeeper_dashboard'))
        else:
            return "Invalid Shopkeeper Login! Check your email/password."

    return render_template('shopkeeper-login.html')

@app.route('/login-wholeseller', methods=['GET', 'POST'])
def wholeseller_login():
    if request.method == 'POST':
        email = request.form.get('email').strip().lower()
        password = request.form.get('password').strip()

        df = pd.read_csv(CSV_FILE)
        
        user = df[
            (df['email'].astype(str) == email) & 
            (df['password'].astype(str) == password) & 
            (df['role'] == 'wholesaler')
        ]
        
        if not user.empty:
            return redirect(url_for('wholeseller_dashboard'))
        else:
            return "Invalid Wholesaler Login!"

    return render_template('wholesaler-login.html')

@app.route('/shopkeeper-dashboard')
def shopkeeper_dashboard():
    return render_template('dashboard.html')

@app.route('/category/<name>')
def view_category(name):
    return render_template(f'{name}.html')



@app.route('/')
def index():
    return redirect(url_for('register'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5001)