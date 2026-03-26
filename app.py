from flask import Flask, render_template, request, redirect, session, url_for, abort
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
import os
from werkzeug.utils import secure_filename
from functools import wraps

# ------------------ APP SETUP ------------------
app = Flask(__name__, static_url_path='/static')
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.secret_key = 'secretkey'

# ------------------ MYSQL CONFIG ------------------
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = '@Onkar2311' 
app.config['MYSQL_DB'] = 'lostfound'
mysql = MySQL(app)

# ------------------ ADMIN WRAPPER ------------------
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('is_admin') != 1:
            return "Access Denied: Administrative Privileges Required", 403
        return f(*args, **kwargs)
    return decorated_function

# ------------------ ROUTES ------------------

@app.route('/')
def home():
    return redirect('/login')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])
        cur = mysql.connection.cursor()
        # Default is_admin is 0
        cur.execute("INSERT INTO users(name,email,password,is_admin) VALUES(%s,%s,%s,0)", (name,email,password))
        mysql.connection.commit()
        cur.close()
        return redirect('/login')
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        cur = mysql.connection.cursor()
        cur.execute("SELECT id, name, email, password, is_admin FROM users WHERE email=%s", (email,))
        user = cur.fetchone()
        cur.close()
        
        if user and check_password_hash(user[3], password):
            session['user_id'] = user[0]
            session['user_name'] = user[1]
            session['is_admin'] = user[4] # Store admin status
            return redirect('/dashboard')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect('/login')
    return render_template('dashboard.html', name=session.get('user_name'))

@app.route('/post', methods=['GET','POST'])
def post_item():
    if 'user_id' not in session:
        return redirect('/login')

    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        category = request.form['category']
        status = request.form['status']
        location = request.form['location']
        date_found = request.form['date_found']
        contact_info = request.form['contact_info']
        
        file = request.files['image']
        filename = None
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        cur = mysql.connection.cursor()
        cur.execute("""
            INSERT INTO items(title, description, category, status, location, image, user_id, date_found, contact_info)
            VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (title, description, category, status, location, filename, session['user_id'], date_found, contact_info))
        mysql.connection.commit()
        cur.close()
        return redirect('/items')
    return render_template('post_item.html')

@app.route('/items')
def items():
    search = request.args.get('search')
    cur = mysql.connection.cursor()
    query = """
        SELECT items.id, items.title, items.description, items.category, 
               items.status, items.location, items.image, items.user_id, 
               users.email, items.date_found, items.contact_info 
        FROM items 
        JOIN users ON items.user_id = users.id
    """
    if search:
        cur.execute(query + " WHERE items.title LIKE %s", ('%' + search + '%',))
    else:
        cur.execute(query)
    data = cur.fetchall()
    cur.close()
    return render_template('view_items.html', items=data)

@app.route('/my_posts')
def my_posts():
    if 'user_id' not in session:
        return redirect('/login')
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT items.id, items.title, items.description, items.category, 
               items.status, items.location, items.image, items.user_id, 
               users.email, items.date_found, items.contact_info 
        FROM items 
        JOIN users ON items.user_id = users.id 
        WHERE items.user_id=%s
    """, (session['user_id'],))
    data = cur.fetchall()
    cur.close()
    return render_template('view_items.html', items=data)

@app.route('/delete/<int:id>')
def delete_item(id):
    if 'user_id' not in session:
        return redirect('/login')
        
    cur = mysql.connection.cursor()
    
    # Check if user owns the post OR is an admin
    if session.get('is_admin') == 1:
        cur.execute("DELETE FROM items WHERE id=%s", (id,))
    else:
        cur.execute("DELETE FROM items WHERE id=%s AND user_id=%s", (id, session['user_id']))
    
    mysql.connection.commit()
    cur.close()
    return redirect('/items')

# ------------------ ADMIN ONLY ROUTES ------------------

@app.route('/admin/dashboard')
@admin_required
def admin_panel():
    cur = mysql.connection.cursor()
    # Get all items
    cur.execute("SELECT items.id, items.title, users.name, items.status FROM items JOIN users ON items.user_id = users.id")
    items = cur.fetchall()
    
    # Get all users (except self)
    cur.execute("SELECT id, name, email, is_admin FROM users WHERE id != %s", (session['user_id'],))
    users = cur.fetchall()
    cur.close()
    return render_template('admin.html', items=items, users=users)

@app.route('/admin/delete_user/<int:id>')
@admin_required
def delete_user(id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM users WHERE id=%s", (id,))
    mysql.connection.commit()
    cur.close()
    return redirect('/admin/dashboard')
@app.route('/resolve/<int:id>')
def resolve_item(id):
    if 'user_id' not in session:
        return redirect('/login')
        
    cur = mysql.connection.cursor()
    # Check if user owns the post OR is an admin
    if session.get('is_admin') == 1:
        cur.execute("UPDATE items SET status='resolved' WHERE id=%s", (id,))
    else:
        cur.execute("UPDATE items SET status='resolved' WHERE id=%s AND user_id=%s", (id, session['user_id']))
    
    mysql.connection.commit()
    cur.close()
    return redirect('/items')

if __name__ == '__main__':
    app.run(debug=True)