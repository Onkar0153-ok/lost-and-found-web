import os
from flask import Flask, render_template, request, redirect, session, url_for
import mysql.connector  # Changed from flask_mysqldb
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps

# ------------------ APP SETUP ------------------
app = Flask(__name__, static_url_path='/static')
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.secret_key = os.environ.get('SECRET_KEY', 'default_secret_key')

# ------------------ DATABASE HELPER ------------------
# This function connects to the cloud database using environment variables
def get_db():
    return mysql.connector.connect(
        host=os.environ.get('MYSQL_HOST', 'localhost'),
        user=os.environ.get('MYSQL_USER', 'root'),
        password=os.environ.get('MYSQL_PASSWORD', '@Onkar2311'),
        database=os.environ.get('MYSQL_DB', 'lostfound'),
        port=int(os.environ.get('MYSQL_PORT', 3306))
    )

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
        
        db = get_db()
        cur = db.cursor()
        cur.execute("INSERT INTO users(name,email,password,is_admin) VALUES(%s,%s,%s,0)", (name,email,password))
        db.commit()
        cur.close()
        db.close()
        return redirect('/login')
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        db = get_db()
        cur = db.cursor()
        cur.execute("SELECT id, name, email, password, is_admin FROM users WHERE email=%s", (email,))
        user = cur.fetchone()
        cur.close()
        db.close()
        
        if user and check_password_hash(user[3], password):
            session['user_id'] = user[0]
            session['user_name'] = user[1]
            session['is_admin'] = user[4]
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

        db = get_db()
        cur = db.cursor()
        cur.execute("""
            INSERT INTO items(title, description, category, status, location, image, user_id, date_found, contact_info)
            VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (title, description, category, status, location, filename, session['user_id'], date_found, contact_info))
        db.commit()
        cur.close()
        db.close()
        return redirect('/items')
    return render_template('post_item.html')

@app.route('/items')
def items():
    search = request.args.get('search')
    db = get_db()
    cur = db.cursor()
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
    db.close()
    return render_template('view_items.html', items=data)

@app.route('/my_posts')
def my_posts():
    if 'user_id' not in session:
        return redirect('/login')
    db = get_db()
    cur = db.cursor()
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
    db.close()
    return render_template('view_items.html', items=data)

@app.route('/delete/<int:id>')
def delete_item(id):
    if 'user_id' not in session:
        return redirect('/login')
        
    db = get_db()
    cur = db.cursor()
    
    if session.get('is_admin') == 1:
        cur.execute("DELETE FROM items WHERE id=%s", (id,))
    else:
        cur.execute("DELETE FROM items WHERE id=%s AND user_id=%s", (id, session['user_id']))
    
    db.commit()
    cur.close()
    db.close()
    return redirect('/items')

@app.route('/admin/dashboard')
@admin_required
def admin_panel():
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT items.id, items.title, users.name, items.status FROM items JOIN users ON items.user_id = users.id")
    items = cur.fetchall()
    
    cur.execute("SELECT id, name, email, is_admin FROM users WHERE id != %s", (session['user_id'],))
    users = cur.fetchall()
    cur.close()
    db.close()
    return render_template('admin.html', items=items, users=users)

@app.route('/resolve/<int:id>')
def resolve_item(id):
    if 'user_id' not in session:
        return redirect('/login')
        
    db = get_db()
    cur = db.cursor()
    if session.get('is_admin') == 1:
        cur.execute("UPDATE items SET status='resolved' WHERE id=%s", (id,))
    else:
        cur.execute("UPDATE items SET status='resolved' WHERE id=%s AND user_id=%s", (id, session['user_id']))
    
    db.commit()
    cur.close()
    db.close()
    return redirect('/items')

if __name__ == '__main__':
    # Use the port assigned by the server, or 5000 for local testing
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
