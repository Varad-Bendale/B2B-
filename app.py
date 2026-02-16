from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        user_data = {
            "role": request.form.get('role'),
            "name": request.form.get('fullname'),
            "email": request.form.get('email'),
            "mobile": request.form.get('mobile'),
            "address": request.form.get('address'),
            "password": request.form.get('password')
        }
        print("--- NEW REGISTRATION RECEIVED ---")
        print(user_data)
        user_role = request.form.get('role')
        if user_role == 'shopkeeper':
            return redirect(url_for('shopkeeper_login'))
            
        elif user_role == 'wholesaler':
            return redirect(url_for('wholeseller_login'))

    return render_template('register.html')

@app.route('/login-shopkeeper')
def shopkeeper_login():
    return render_template('shopkeeper-login.html')

@app.route('/login-wholeseller')
def wholeseller_login():
    return render_template('wholesaler-login.html')

if __name__ == '__main__':
    app.run(debug=True, port=5001)