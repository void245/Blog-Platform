from flask import Flask, render_template, request , redirect , url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime , timedelta
from functools import wraps
import json

# importing json file for database
with open('templates/config.json', 'r') as c:
    params = json.load(c)["params"]

local_server = True
 
app = Flask(__name__)
app.config['SECRET_KEY'] = params.get('secret_key', 'your-secret-key-change-in-production')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)
app.config.update(
    MAIL_SERVER = 'smtp.gmail.com',
    MAIL_PORT = '465',
    MAIL_USE_SSL = True,
    MAIL_USERNAME = params['gmail_user'],
    MAIL_PASSWORD = params['gmail_password']
)
mail = Mail(app)
if(local_server):
  app.config['SQLALCHEMY_DATABASE_URI'] = params['local_url']
else :
    app.config['SQLALCHEMY_DATABASE_URI'] = params['prod_url']

db = SQLAlchemy(app)

# setup for flask-login
# it automatically redirect unlogged in user to login page
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view= 'login'
login_manager.login_message = "Please log in to access this page."
login_manager.login_message_category = "info"


# creating table in database for contact form
class Contacts(db.Model):
    # here contact is table name and ser , name , phone_num , mes, date , email are column
    ser = db.Column(db.Integer, primary_key=True)
    name =db.Column(db.String(80), nullable=False)
    phone_num = db.Column(db.String(12), nullable=False)
    mes = db.Column(db.String(255), nullable=False)
    date = db.Column(db.DateTime, default=datetime.now, nullable=True)
    email = db.Column(db.String(50),nullable=False)


#creating table in database for post form
class Posts(db.Model):
    __tablename__ = 'posts'
    # here content is table name : sno , title , slug , content , tagline , date , img_file , author_id
    sno = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(80), nullable=False)
    slug = db.Column(db.String(50), nullable=False)
    content = db.Column(db.String(500), nullable=False)
    tagline = db.Column(db.String(120), nullable=True)
    date = db.Column(db.DateTime, default=datetime.now, nullable=True)
    img_file = db.Column(db.String(50), nullable=True)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    author = db.relationship('User', backref='posts')

# =======================USER MODEL WITH ROLE BASED ACCESS CONTROL =======================

class User(UserMixin, db.Model):
    __tablename__= 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80),unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='user') # two roles : admin or user
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    def set_password(self, password):
        """ Hash and set password"""
        self.password_hash =  generate_password_hash(password, method='pbkdf2:sha256' )

    def check_password(self, password):
        """ Check hashed password."""
        return check_password_hash(self.password_hash, password)

    def is_admin(self):
        """ Check if user is admin."""
        return self.role == 'admin'

    def __repr__(self):
        return f'<User {self.username}>'    

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ==================== ROLE-BASED ACCESS CONTROL DECORATOR ====================
def admin_required(f):
    """Decorator to require admin access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in first.', 'warning')
            return redirect(url_for('login'))
        if not current_user.is_admin():
            flash('You do not have permission to access this page.', 'danger')
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def home():
    posts = Posts.query.filter_by().all()[0:params['no_of_posts']]
    return render_template('index.html', params=params, posts=posts)

@app.route('/about')
def about():
    return render_template('about.html', params=params)

# ==================== AUTHENTICATION ROUTES ====================

# LOGIN ROUTE
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember_me = request.form.get('remember-me')
        
        # Validate input
        if not email or not password:
            flash('Email and password are required!', 'danger')
            return redirect(url_for('login'))
        
        # Find user by email
        user = User.query.filter_by(email=email).first()
        
        if user is None or not user.check_password(password):
            flash('Invalid email or password!', 'danger')
            return redirect(url_for('login'))
        
        if not user.is_active:
            flash('Your account has been disabled.', 'warning')
            return redirect(url_for('login'))
        
        # Log user in
        login_user(user, remember=bool(remember_me))
        flash(f'Welcome back, {user.username}!', 'success')
        
        # Redirect to next page or dashboard
        next_page = request.args.get('next')
        if next_page and next_page.startswith('/'):
            return redirect(next_page)
        return redirect(url_for('dashboard'))
    
    return render_template('login.html', params=params)

# REGISTER ROUTE
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm-password')
        
        # Validate input
        if not username or not email or not password or not confirm_password:
            flash('All fields are required!', 'danger')
            return redirect(url_for('register'))
        
        if password != confirm_password:
            flash('Passwords do not match!', 'danger')
            return redirect(url_for('register'))
        
        if len(password) < 6:
            flash('Password must be at least 6 characters long!', 'danger')
            return redirect(url_for('register'))
        
        # Check if user already exists
        if User.query.filter_by(email=email).first():
            flash('Email already registered!', 'warning')
            return redirect(url_for('register'))
        
        if User.query.filter_by(username=username).first():
            flash('Username already taken!', 'warning')
            return redirect(url_for('register'))
        
        # Create new user
        user = User(username=username, email=email, role='user')
        user.set_password(password)
        
        try:
            db.session.add(user)
            db.session.commit()
            flash('Account created successfully! Please log in.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating account: {str(e)}', 'danger')
            return redirect(url_for('register'))
    
    return render_template('register.html', params=params)

# LOGOUT ROUTE
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('home'))





# for getting data from contact form and saving it in database and sending mail to admin
@app.route('/contact' , methods=['GET', 'POST'])
def contact():
    if (request.method == 'POST'):
        try:
            name = request.form.get('name')
            email = request.form.get('email')
            phone_number = request.form.get('phone_number')
            message = request.form.get('message')

            entry = Contacts(name = name, phone_num=phone_number, mes=message,date = datetime.now(), email=email)
            db.session.add(entry)
            db.session.commit()
            mail.send_message('New message from ' + name,
                               sender=email,
                               recipients=[params['gmail_user']],
                               body = message + "\n" + phone_number
                               
                               )
            return "Message sent successfully!", 200
        except Exception as e:
            db.session.rollback()
            return f"Error: {str(e)}", 500
    
    return render_template('contact.html', params=params)

# for getting post form database and showing it in html page
@app.route('/post/<string:post_slug>', methods=['GET'])
def post(post_slug):
    # Retrieve the post from the database based on the slug
    post = Posts.query.filter_by(slug=post_slug).first() 

    return render_template('post.html', params=params, post=post, post_slug=post_slug)

# for adding new posts (Any logged-in user can post)
@app.route('/add-post', methods=['GET', 'POST'])
@login_required
def add_post():
    """Add new post - Any logged-in user can create posts"""
    if request.method == 'POST':
        try:
            title = request.form.get('title')
            slug = request.form.get('slug')
            tagline = request.form.get('tagline')
            content = request.form.get('content')
            img_file = request.form.get('img_file')
            
            # Validate inputs
            if not title or not slug or not content:
                flash('Title, slug, and content are required!', 'danger')
                return redirect(url_for('add_post'))
            
            # Check if slug already exists
            if Posts.query.filter_by(slug=slug).first():
                flash('A post with this slug already exists!', 'warning')
                return redirect(url_for('add_post'))
            
            entry = Posts(title=title, slug=slug, tagline=tagline, content=content, date=datetime.now(), img_file=img_file, author_id=current_user.id)
            db.session.add(entry)
            db.session.commit()
            flash('Post created successfully!', 'success')
            return redirect(url_for('home'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'danger')
            return redirect(url_for('add_post'))
    
    return render_template('add-post.html', params=params)

# EDIT POST ROUTE (User can only edit their own posts)
@app.route('/edit-post/<int:post_id>', methods=['GET', 'POST'])
@login_required
def edit_post(post_id):
    """Edit post - Users can only edit their own posts"""
    post = Posts.query.get_or_404(post_id)
    
    # Check if user owns this post or is admin
    if post.author_id != current_user.id and not current_user.is_admin():
        flash('You do not have permission to edit this post.', 'danger')
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        try:
            post.title = request.form.get('title')
            post.slug = request.form.get('slug')
            post.tagline = request.form.get('tagline')
            post.content = request.form.get('content')
            post.img_file = request.form.get('img_file')
            
            # Validate inputs
            if not post.title or not post.slug or not post.content:
                flash('Title, slug, and content are required!', 'danger')
                return redirect(url_for('edit_post', post_id=post_id))
            
            # Check if new slug already exists (and is different from current)
            existing_post = Posts.query.filter_by(slug=post.slug).first()
            if existing_post and existing_post.sno != post_id:
                flash('A post with this slug already exists!', 'warning')
                return redirect(url_for('edit_post', post_id=post_id))
            
            db.session.commit()
            flash('Post updated successfully!', 'success')
            return redirect(url_for('post', post_slug=post.slug))
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'danger')
            return redirect(url_for('edit_post', post_id=post_id))
    
    return render_template('edit-post.html', params=params, post=post)

# DELETE POST ROUTE (User can only delete their own posts)
@app.route('/delete-post/<int:post_id>', methods=['POST'])
@login_required
def delete_post(post_id):
    """Delete post - Users can only delete their own posts"""
    post = Posts.query.get_or_404(post_id)
    
    # Check if user owns this post or is admin
    if post.author_id != current_user.id and not current_user.is_admin():
        flash('You do not have permission to delete this post.', 'danger')
        return redirect(url_for('home'))
    
    try:
        db.session.delete(post)
        db.session.commit()
        flash('Post deleted successfully!', 'success')
        return redirect(url_for('dashboard'))
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'danger')
        return redirect(url_for('dashboard'))
# ====================USER DASHBOARD ========================
@app.route('/dashboard', methods =['GET'])
@login_required
def dashboard():
    """ USER DASHBOARD """
    user_posts = Posts.query.filter_by(author_id=current_user.id).all()
    
    # Stats
    total_posts = len(user_posts)
    total_views = 0  # You can add views column to Posts model later
    
    return render_template('dashboard.html', 
                         params=params, 
                         posts=user_posts, 
                         user=current_user,
                         stats={
                             'total_posts': total_posts,
                             'total_views': total_views,
                             'total_followers': 0  # Add followers table later
                         })

# ==================== ADMIN DASHBOARD - CONTROL CENTER ====================
@app.route('/admin/dashboard', methods=['GET'])
@login_required
def admin_dashboard():
    """Admin dashboard - Full platform control"""
    if not current_user.is_admin():
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('home'))
    
    # Analytics
    total_users = User.query.count()
    total_posts = Posts.query.count()
    total_contacts = Contacts.query.count()
    admin_count = User.query.filter_by(role='admin').count()
    active_users = User.query.filter_by(is_active=True).count()
    
    # Recent activity
    recent_posts = Posts.query.order_by(Posts.date.desc()).limit(10).all()
    recent_users = User.query.order_by(User.created_at.desc()).limit(10).all()
    recent_contacts = Contacts.query.order_by(Contacts.date.desc()).limit(10).all()
    
    return render_template('admin-dashboard.html',
                         params=params,
                         stats={
                             'total_users': total_users,
                             'total_posts': total_posts,
                             'total_contacts': total_contacts,
                             'admin_count': admin_count,
                             'active_users': active_users
                         },
                         recent_posts=recent_posts,
                         recent_users=recent_users,
                         recent_contacts=recent_contacts)

# ==================== ADMIN USERS MANAGEMENT ====================
@app.route('/admin/users', methods=['GET'])
@login_required
def admin_users():
    """Manage all users - ban, promote, etc."""
    if not current_user.is_admin():
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('home'))
    
    search_query = request.args.get('search', '')
    if search_query:
        all_users = User.query.filter(User.username.ilike(f'%{search_query}%')).all()
    else:
        all_users = User.query.all()
    
    return render_template('admin-users.html', params=params, users=all_users, search_query=search_query)

@app.route('/admin/user/<int:user_id>/toggle-status', methods=['POST'])
@login_required
def toggle_user_status(user_id):
    """Ban/Unban user"""
    if not current_user.is_admin():
        flash('You do not have permission to perform this action.', 'danger')
        return redirect(url_for('home'))
    
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('Cannot deactivate yourself!', 'danger')
        return redirect(url_for('admin_users'))
    
    user.is_active = not user.is_active
    db.session.commit()
    status = "activated" if user.is_active else "deactivated"
    flash(f'User {user.username} {status}!', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/user/<int:user_id>/promote', methods=['POST'])
@login_required
def promote_user(user_id):
    """Promote user to admin or demote admin to user"""
    if not current_user.is_admin():
        flash('You do not have permission to perform this action.', 'danger')
        return redirect(url_for('home'))
    
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('Cannot change your own role!', 'info')
        return redirect(url_for('admin_users'))
    
    user.role = 'admin' if user.role == 'user' else 'user'
    db.session.commit()
    new_role = "admin" if user.role == 'admin' else "user"
    flash(f'User {user.username} is now {new_role}!', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/user/<int:user_id>/delete', methods=['POST'])
@login_required
def admin_delete_user(user_id):
    """Delete user account"""
    if not current_user.is_admin():
        flash('You do not have permission to perform this action.', 'danger')
        return redirect(url_for('home'))
    
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('Cannot delete your own account!', 'danger')
        return redirect(url_for('admin_users'))
    
    username = user.username
    # Delete user's posts first
    Posts.query.filter_by(author_id=user_id).delete()
    # Delete user
    db.session.delete(user)
    db.session.commit()
    flash(f'User {username} and all their posts deleted!', 'success')
    return redirect(url_for('admin_users'))

# ==================== ADMIN POSTS MODERATION ====================
@app.route('/admin/posts', methods=['GET'])
@login_required
def admin_posts():
    """Moderate all posts"""
    if not current_user.is_admin():
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('home'))
    
    search_query = request.args.get('search', '')
    if search_query:
        all_posts = Posts.query.filter(Posts.title.ilike(f'%{search_query}%')).all()
    else:
        all_posts = Posts.query.order_by(Posts.date.desc()).all()
    
    return render_template('admin-posts.html', params=params, posts=all_posts, search_query=search_query)

@app.route('/admin/post/<int:post_id>/delete', methods=['POST'])
@login_required
def admin_delete_post(post_id):
    """Admin can delete any post"""
    if not current_user.is_admin():
        flash('You do not have permission to perform this action.', 'danger')
        return redirect(url_for('home'))
    
    post = Posts.query.get_or_404(post_id)
    title = post.title
    db.session.delete(post)
    db.session.commit()
    flash(f'Post "{title}" deleted!', 'success')
    return redirect(url_for('admin_posts'))

# ==================== ADMIN CONTACTS MANAGEMENT ====================
@app.route('/admin/contacts', methods=['GET'])
@login_required
def admin_contacts():
    """View all contact form submissions"""
    if not current_user.is_admin():
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('home'))
    
    search_query = request.args.get('search', '')
    if search_query:
        all_contacts = Contacts.query.filter(Contacts.name.ilike(f'%{search_query}%')).all()
    else:
        all_contacts = Contacts.query.order_by(Contacts.date.desc()).all()
    
    return render_template('admin-contacts.html', params=params, contacts=all_contacts, search_query=search_query)

@app.route('/admin/contact/<int:contact_id>/delete', methods=['POST'])
@login_required
def delete_contact(contact_id):
    """Delete contact message"""
    if not current_user.is_admin():
        flash('You do not have permission to perform this action.', 'danger')
        return redirect(url_for('home'))
    
    contact = Contacts.query.get_or_404(contact_id)
    db.session.delete(contact)
    db.session.commit()
    flash('Contact message deleted!', 'success')
    return redirect(url_for('admin_contacts'))

# ==================== ADMIN SETTINGS ====================
@app.route('/admin/settings', methods=['GET', 'POST'])
@login_required
def admin_settings():
    """Admin settings and permissions"""
    if not current_user.is_admin():
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('home'))
    
    all_admins = User.query.filter_by(role='admin').all()
    return render_template('admin-settings.html', params=params, admins=all_admins)

# ==================== ADMIN INITIALIZATION (Run once to create first admin) ====================
@app.route('/create-admin', methods=['GET', 'POST'])
def create_admin():
    """Create first admin user - Remove this route after initial setup"""
    # Check if any admin exists
    admin_exists = User.query.filter_by(role='admin').first()
    if admin_exists:
        flash('Admin user already exists. This route is disabled.', 'warning')
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if not username or not email or not password:
            flash('All fields are required!', 'danger')
            return redirect(url_for('create_admin'))
        
        if len(password) < 6:
            flash('Password must be at least 6 characters!', 'danger')
            return redirect(url_for('create_admin'))
        
        try:
            admin = User(username=username, email=email, role='admin')
            admin.set_password(password)
            db.session.add(admin)
            db.session.commit()
            flash('Admin user created successfully! DELETE /create-admin route from code for security.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'danger')
            return redirect(url_for('create_admin'))
    
    return render_template('create_admin.html', params=params)

if __name__ == '__main__':
    # Create database tables on startup if they don't exist
    with app.app_context():
        db.create_all()
        print("[OK] Database tables initialized!")
    
    app.run(debug=True)