from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta, date
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from flask_mail import Mail, Message
import secrets
import random
import os
import psutil
import json
from threading import Thread

def send_async_email(app, msg):
    """Send email asynchronously"""
    with app.app_context():
        try:
            mail.send(msg)
            print("✅ Email sent successfully")
        except Exception as e:
            print(f"❌ Email failed: {e}")

app = Flask(__name__, static_url_path='/static', static_folder='static', template_folder='templates')
# ---------------- CONFIG ----------------
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_EXT = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

app = Flask(__name__)
app.secret_key = "auto_adeal_secret_change_this"
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=72)
import os

# Get database URL from environment variable
DATABASE_URL = os.environ.get('DATABASE_URL') or os.environ.get('MYSQL_URL')

# Debug: print what we got (remove this later)
print(f"🔍 DATABASE_URL from env: {DATABASE_URL}")

# Convert mysql:// to mysql+pymysql:// if needed
if DATABASE_URL:
    if DATABASE_URL.startswith('mysql://'):
        DATABASE_URL = DATABASE_URL.replace('mysql://', 'mysql+pymysql://', 1)
    print(f"✅ Using Railway database: {DATABASE_URL[:30]}...")
else:
    print("⚠️ No DATABASE_URL found, using localhost")

# Use environment variable or fallback to local
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL or 'mysql+pymysql://root:@localhost/auto_adeal'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Email configuration for Gmail
try:
    from flask_mail import Mail, Message
    
    app.config['MAIL_SERVER'] = 'smtp.gmail.com'
    app.config['MAIL_PORT'] = 587
    app.config['MAIL_USE_TLS'] = True
    app.config['MAIL_USERNAME'] = 'autoadeal@gmail.com'
    app.config['MAIL_PASSWORD'] = os.environ.get('EMAIL_PASSWORD', '')
    app.config['MAIL_DEFAULT_SENDER'] = 'autoadeal@gmail.com'
    
    mail = Mail(app)
    MAIL_ENABLED = True
    print("✅ Flask-Mail initialized successfully")
except Exception as e:
    print(f"⚠️ Flask-Mail initialization failed: {e}")
    mail = None
    MAIL_ENABLED = False

db = SQLAlchemy(app)

# Simple admin password
ADMIN_PASSWORD = "admin"  # Change this to your secure password

def require_admin(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check if admin is logged in via session
        from flask import session, request, redirect, url_for
        
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# ---------------- MODELS ----------------
subcategory_spectype = db.Table(
    'subcategory_spectype',
    db.Column('subcategory_id', db.Integer, db.ForeignKey('subcategory.subcategory_id'), primary_key=True),
    db.Column('spectype_id', db.Integer, db.ForeignKey('spec_type.id'), primary_key=True)
)

class SpecType(db.Model):
    __tablename__ = 'spec_type'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    value_type = db.Column(db.String(20), nullable=False, default='text')
    choices = db.Column(db.Text, nullable=True)
    subcategories = db.relationship('Subcategory', secondary=subcategory_spectype, back_populates='spec_types')

class Subcategory(db.Model):
    __tablename__ = 'subcategory'
    subcategory_id = db.Column(db.Integer, primary_key=True)
    subcategory_name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(100), nullable=True)
    category_id = db.Column(db.Integer, db.ForeignKey('category.category_id'))
    sort_order = db.Column(db.Integer, default=0)
    spec_types = db.relationship('SpecType', secondary=subcategory_spectype, back_populates='subcategories')
    products = db.relationship('Product', backref='subcategory', lazy=True)

class Category(db.Model):
    __tablename__ = 'category'
    category_id = db.Column(db.Integer, primary_key=True)
    category_name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(100), nullable=True)
    subcategories = db.relationship('Subcategory', backref='category', cascade='all, delete-orphan', order_by='Subcategory.sort_order')

class Product(db.Model):
    __tablename__ = 'product'
    product_id = db.Column(db.Integer, primary_key=True)
    product_name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    price = db.Column(db.Float, nullable=False)
    discount_price = db.Column(db.Float, nullable=True)
    is_special = db.Column(db.Boolean, default=False)
    sold_out = db.Column(db.Boolean, default=False)
    subcategory_id = db.Column(db.Integer, db.ForeignKey('subcategory.subcategory_id'))
    main_image = db.Column(db.String(255))
    image_urls = db.Column(db.Text, nullable=True)  # Comma-separated additional images
    tags = db.Column(db.Text, nullable=True)  # Comma-separated tags for search
    specs = db.relationship('ProductSpec', back_populates='product', cascade='all, delete-orphan')

class ProductSpec(db.Model):
    __tablename__ = 'product_spec'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.product_id'), nullable=False)
    spectype_id = db.Column(db.Integer, db.ForeignKey('spec_type.id'), nullable=False)
    value = db.Column(db.Text)
    product = db.relationship('Product', back_populates='specs')
    spec_type = db.relationship('SpecType')

class User(db.Model):
    __tablename__ = 'user'
    user_id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    surname = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)

class PasswordReset(db.Model):
    __tablename__ = 'password_reset'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.user_id'), nullable=False)
    token = db.Column(db.String(255), unique=True, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False)

class ProductView(db.Model):
    __tablename__ = 'product_view'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.product_id'), nullable=False)
    search_query = db.Column(db.String(255), nullable=True)
    viewed_at = db.Column(db.DateTime, default=datetime.utcnow)

class DailyFeatured(db.Model):
    __tablename__ = 'daily_featured'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.product_id'), nullable=False)
    featured_date = db.Column(db.Date, nullable=False)
    display_order = db.Column(db.Integer, nullable=False)
    weight_category = db.Column(db.String(50))

class SiteSettings(db.Model):
    __tablename__ = 'site_settings'
    id = db.Column(db.Integer, primary_key=True)
    setting_key = db.Column(db.String(100), unique=True, nullable=False)
    setting_value = db.Column(db.Text)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Order(db.Model):
    __tablename__ = 'order'
    order_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.user_id'), nullable=True)  # NEW
    customer_name = db.Column(db.String(100), nullable=False)
    customer_phone = db.Column(db.String(20), nullable=False)
    customer_email = db.Column(db.String(100), nullable=True)
    customer_address = db.Column(db.String(255), nullable=False)
    customer_city = db.Column(db.String(100), nullable=False)
    customer_country = db.Column(db.String(50), nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    shipping_cost = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, confirmed, in_warehouse, shipped, out_for_delivery, delivered, failed_to_deliver, cancelled
    order_items = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text, nullable=True)
    # Relationship to status history
    status_history = db.relationship('OrderStatusHistory', backref='order', cascade='all, delete-orphan', order_by='OrderStatusHistory.created_at')

class OrderStatusHistory(db.Model):
    __tablename__ = 'order_status_history'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.order_id'), nullable=False)
    status = db.Column(db.String(20), nullable=False)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class BlogPost(db.Model):
    __tablename__ = 'blog_post'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    image = db.Column(db.String(255), nullable=True)
    slug = db.Column(db.String(200), unique=True, nullable=False)
    published = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# ---------------- HELPER FUNCTIONS ----------------
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXT

def format_product(product):
    """Convert product to JSON-friendly dict"""
    specs = {}
    for spec in product.specs:
        specs[spec.spec_type.name] = spec.value
    
    images = []
    if product.image_urls:
        images = [url.strip() for url in product.image_urls.split(',') if url.strip()]
    
    return {
        "id": product.product_id,
        "name": product.product_name,
        "description": product.description or "",
        "price": product.price,
        "discount_price": product.discount_price,
        "is_special": product.is_special,
        "sold_out": product.sold_out,
        "subcategory_id": product.subcategory_id,
        "main_image": product.main_image,
        "images": images,
        "tags": product.tags or "",
        "specs": specs
    }

def ping_google_sitemap():
    """Notify Google of sitemap update"""
    try:
        import requests
        requests.get('http://www.google.com/ping?sitemap=https://autoadeal.com/sitemap.xml', timeout=5)
        print("✅ Pinged Google about sitemap update")
    except:
        pass  # Don't fail if ping fails
    
def create_admin_notification_email(order, cart_items):
    """Create admin notification email message"""
    # ... (move all the HTML building code here)
    return Message(
        subject=f'🔔 New Order #{order.order_id} - Auto Adeal',
        recipients=['autoadeal@gmail.com'],
        html=html_content
    )

def create_customer_confirmation_email(order, cart_items, customer_email):
    """Create customer confirmation email message"""
    # ... (move all the HTML building code here)
    return Message(
        subject=f'✅ Konfirmim Porosie #{order.order_id} - Auto Adeal',
        recipients=[customer_email],
        html=html_content
    )

# ---------------- ROUTES ----------------
@app.route('/subcategory/<int:subcategory_id>')
@app.route('/subcategory/<int:subcategory_id>/<path:name>')
def subcategory_page(subcategory_id, name=None):
    """Show subcategory products page"""
    subcategory = Subcategory.query.get_or_404(subcategory_id)
    
    # Get all products in this subcategory (in stock first, then sold out)
    in_stock = Product.query.filter_by(subcategory_id=subcategory_id, sold_out=False).filter(
        Product.main_image.isnot(None), 
        Product.main_image != ''
    ).all()
    sold_out = Product.query.filter_by(subcategory_id=subcategory_id, sold_out=True).filter(
        Product.main_image.isnot(None), 
        Product.main_image != ''
    ).all()
    products = in_stock + sold_out
    
    # Get all categories for sidebar
    categories = Category.query.all()
    
    return render_template('subcategory.html', 
                         subcategory=subcategory, 
                         products=products,
                         categories=categories)

@app.route('/product/<int:product_id>')
def product_page(product_id):
    """Show product detail page"""
    product = Product.query.get_or_404(product_id)
    
    # Get related products (same subcategory, exclude current)
    related = Product.query.filter(
        Product.subcategory_id == product.subcategory_id,
        Product.product_id != product.product_id,
        Product.main_image.isnot(None),
        Product.main_image != ''
    ).limit(6).all()
    
    # Format product specs
    specs = {}
    for spec in product.specs:
        specs[spec.spec_type.name] = spec.value
    
    # Format additional images
    images = []
    if product.image_urls:
        images = [url.strip() for url in product.image_urls.split(',') if url.strip()]
    
    return render_template('product.html', 
                         product=product,
                         specs=specs,
                         images=images,
                         related=related)

@app.route('/brand/<path:brand_name>')
def redirect_to_brand(brand_name):
    """Redirect /brand/BMW to /#brand/BMW"""
    from urllib.parse import quote
    return redirect(f'/#brand/{quote(brand_name)}')

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/health')
def health():
    """Monitor app health"""
    process = psutil.Process(os.getpid())
    mem_info = process.memory_info()
    
    return {
        'status': 'healthy',
        'memory_mb': round(mem_info.rss / 1024 / 1024, 2),
        'cpu_percent': process.cpu_percent()
    }

#BLOG PAGE ROUTES
@app.route('/api/blog/posts')
def get_blog_posts():
    """Get all published blog posts"""
    posts = BlogPost.query.filter_by(published=True).order_by(BlogPost.created_at.desc()).all()
    return jsonify([{
        'id': post.id,
        'title': post.title,
        'content': post.content,
        'image': post.image,
        'slug': post.slug,
        'created_at': post.created_at.strftime('%Y-%m-%d')
    } for post in posts])

@app.route('/api/blog/post/<int:post_id>')
def get_blog_post(post_id):
    """Get single blog post"""
    post = BlogPost.query.get_or_404(post_id)
    return jsonify({
        'id': post.id,
        'title': post.title,
        'content': post.content,
        'image': post.image,
        'slug': post.slug,
        'created_at': post.created_at.strftime('%Y-%m-%d')
    })

@app.route('/api/admin/blog/posts', methods=['GET'])
@require_admin
def admin_get_blog_posts():
    """Get all blog posts for admin"""
    posts = BlogPost.query.order_by(BlogPost.created_at.desc()).all()
    return jsonify([{
        'id': post.id,
        'title': post.title,
        'content': post.content[:100] + '...' if len(post.content) > 100 else post.content,
        'image': post.image,
        'published': post.published,
        'created_at': post.created_at.strftime('%Y-%m-%d')
    } for post in posts])

@app.route('/api/admin/blog/post', methods=['POST'])
@require_admin
def admin_create_blog_post():
    """Create new blog post"""
    try:
        data = request.json
        
        # Generate slug from title
        slug = data['title'].lower().replace(' ', '-').replace('ë', 'e').replace('ç', 'c')
        
        post = BlogPost(
            title=data['title'],
            content=data['content'],
            image=data.get('image'),
            slug=slug,
            published=data.get('published', True)
        )
        
        db.session.add(post)
        db.session.commit()
        
        return jsonify({'success': True, 'post_id': post.id}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/admin/blog/post/<int:post_id>', methods=['PUT'])
@require_admin
def admin_update_blog_post(post_id):
    """Update blog post"""
    try:
        post = BlogPost.query.get_or_404(post_id)
        data = request.json
        
        post.title = data.get('title', post.title)
        post.content = data.get('content', post.content)
        post.image = data.get('image', post.image)
        post.published = data.get('published', post.published)
        
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/admin/blog/post/<int:post_id>', methods=['DELETE'])
@require_admin
def admin_delete_blog_post(post_id):
    """Delete blog post"""
    try:
        post = BlogPost.query.get_or_404(post_id)
        db.session.delete(post)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400
    
@app.route('/admin/blog')
@require_admin
def admin_blog():
    """Admin blog management page"""
    return render_template('admin_blog.html')

@app.route('/admin/test-email')
@require_admin
def test_email():
    """Test email configuration"""
    if not MAIL_ENABLED:
        return jsonify({'success': False, 'error': 'Email system is disabled'})
    
    try:
        msg = Message(
            subject='🧪 Test Email - Auto Adeal',
            recipients=['autoadeal@gmail.com'],
            body='This is a test email.'
        )
        mail.send(msg)
        return jsonify({'success': True, 'message': 'Test email sent'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    
@app.route('/blog')
def blog_page():
    """Blog listing page"""
    return render_template('blog.html')

@app.route('/blog/<int:post_id>')
def blog_post_page(post_id):
    """Individual blog post page"""
    return render_template('blog_post.html')
    
# ---------------- API ENDPOINTS ----------------

@app.route('/api/categories')
def api_categories():
    """Get all categories with subcategories (sorted by sort_order)"""
    categories = Category.query.all()
    output = []
    for cat in categories:
        output.append({
            "id": cat.category_id,
            "name": cat.category_name,
            "slug": cat.slug,
            "subcategories": [
                {
                    "id": sub.subcategory_id, 
                    "name": sub.subcategory_name,
                    "slug": sub.slug
                }
                for sub in cat.subcategories  # Already sorted by sort_order
            ]
        })
    return jsonify(output)

@app.route('/api/subcategory/<int:sub_id>/specs')
def api_subcategory_specs(sub_id):
    """Get spec types for a subcategory (for dynamic filters)"""
    sub = Subcategory.query.get_or_404(sub_id)
    out = []
    for st in sub.spec_types:
        out.append({
            'id': st.id,
            'name': st.name,
            'value_type': st.value_type,
            'choices': (st.choices.split(',') if st.choices else [])
        })
    return jsonify(out)

@app.route('/api/subcategory/<int:sub_id>/products')
def api_subcategory_products(sub_id):
    """Get all products in a subcategory, sold out items at end"""
    Subcategory.query.get_or_404(sub_id)  # Verify subcategory exists
    
    # Get in stock and sold out separately, filter out products without images
    in_stock = Product.query.filter_by(subcategory_id=sub_id, sold_out=False).filter(Product.main_image.isnot(None), Product.main_image != '').all()
    sold_out = Product.query.filter_by(subcategory_id=sub_id, sold_out=True).filter(Product.main_image.isnot(None), Product.main_image != '').all()
    
    # Combine: in stock first, sold out at end
    products = in_stock + sold_out
    
    return jsonify([format_product(p) for p in products])

@app.route('/api/product/<int:product_id>')
def api_product_detail(product_id):
    """Get detailed product info with related products"""
    product = Product.query.get_or_404(product_id)
    
    # Get related products (same subcategory, exclude current)
    related = Product.query.filter(
        Product.subcategory_id == product.subcategory_id,
        Product.product_id != product.product_id
    ).limit(6).all()
    
    result = format_product(product)
    result['related'] = [
        {
            "id": r.product_id,
            "name": r.product_name,
            "price": r.price,
            "discount_price": r.discount_price,
            "main_image": r.main_image
        } for r in related
    ]
    
    return jsonify(result)

@app.route('/api/products/specials')
def api_special_products():
    """Get products with discounts or marked as special"""
    products = Product.query.filter(
        (Product.discount_price.isnot(None)) | (Product.is_special == True)
    ).all()
    return jsonify([format_product(p) for p in products])

@app.route('/api/products/popular')
def api_popular_products():
    """Get daily rotated featured products with weighted randomization"""
    import random
    from datetime import date
    
    today = date.today()
    print(f"📅 Today's date: {today}")  # Debug
    
    # Check if we have cached products for today
    cached = DailyFeatured.query.filter_by(featured_date=today).order_by(DailyFeatured.display_order).all()
    print(f"💾 Cached products found: {len(cached)}")  # Debug
    
    if cached and len(cached) > 0:
        # Return cached products
        product_ids = [c.product_id for c in cached]
        products = Product.query.filter(Product.product_id.in_(product_ids)).all()
        
        # Sort by cached order
        products_dict = {p.product_id: p for p in products}
        ordered_products = [products_dict[pid] for pid in product_ids if pid in products_dict]
        
        print(f"✓ Returning {len(ordered_products)} cached products")  # Debug
        return jsonify([format_product(p) for p in ordered_products])
    
    # Generate new daily rotation
    print("🔄 Generating new daily rotation...")  # Debug
    all_products = Product.query.all()
    
    if not all_products:
        return jsonify([])
    
    # Categorize products
    popular_products = []
    recent_products = []
    older_products = []
    
    # Get the highest product ID to determine what's recent
    max_id = max([p.product_id for p in all_products])
    recent_threshold = max_id - 30
    
    print(f"📈 Total products: {len(all_products)}, Max ID: {max_id}, Recent threshold: {recent_threshold}")  # Debug
    
    # Filter out sold out products and products without images for home page
    all_products = [p for p in all_products if not p.sold_out and p.main_image]

    for product in all_products:
        # Check if popular (has discount or is special)
        is_popular = product.is_special or (product.discount_price and product.discount_price < product.price)
        
        # Check if recent
        is_recent = product.product_id > recent_threshold
        
        if is_popular:
            popular_products.append(product)
        elif is_recent:
            recent_products.append(product)
        else:
            older_products.append(product)
    
    print(f"📊 Popular: {len(popular_products)}, Recent: {len(recent_products)}, Older: {len(older_products)}")  # Debug
    
    # Weighted selection
    selected = []
    
    # 50% popular (32 out of 64)
    random.shuffle(popular_products)
    selected.extend(popular_products[:32])
    print(f"➕ Added {len(selected)} popular products")  # Debug
    
    # 30% recent (19 out of 64)
    random.shuffle(recent_products)
    selected.extend(recent_products[:19])
    print(f"➕ Added recent products, total: {len(selected)}")  # Debug
    
    # 20% older (13 out of 64)
    random.shuffle(older_products)
    selected.extend(older_products[:13])
    print(f"➕ Added older products, total: {len(selected)}")  # Debug
    
    # If we don't have enough, fill with any remaining
    if len(selected) < 64:
        remaining = [p for p in all_products if p not in selected]
        random.shuffle(remaining)
        needed = 64 - len(selected)
        selected.extend(remaining[:needed])
        print(f"➕ Filled remaining {needed} products, total: {len(selected)}")  # Debug
    
    # Final shuffle and limit to 64
    random.shuffle(selected)
    selected = selected[:64]
    
    print(f"🎲 Final selection: {len(selected)} products")  # Debug
    
    # Cache for today
    for idx, product in enumerate(selected):
        if product in popular_products:
            category = 'popular'
        elif product in recent_products:
            category = 'recent'
        else:
            category = 'older'
        
        daily_featured = DailyFeatured(
            product_id=product.product_id,
            featured_date=today,
            display_order=idx,
            weight_category=category
        )
        db.session.add(daily_featured)
    
    try:
        db.session.commit()
        print("✓ Cached products saved to database")  # Debug
    except Exception as e:
        db.session.rollback()
        print(f"❌ Failed to cache products: {e}")  # Debug
    
    return jsonify([format_product(p) for p in selected])

@app.route('/api/search')
def api_search():
    """Smart search with relevance scoring and synonym support"""
    query = request.args.get('q', '').strip().lower()
    if not query:
        return jsonify([])
    
    # Albanian stop words
    stop_words = {"per", "dhe", "ose", "te", "me", "nga", "ne", "si", "qe", "eshte", "nje", "i", "e", "a", "u"}
    
    # Synonym map (Albanian automotive terms)
    synonyms = {
        'makine': ['makin', 'auto', 'veture', 'car'],
        'butona': ['buton', 'buttons', 'switch', 'celes', 'celsa'],
        'xhami': ['xhamash', 'xhamat', 'xhama', 'window'],
        'veshje': ['mbulese', 'cover', 'mbrojtese', 'cover'],
        'timoni': ['timon', 'timona', 'timonash', 'steering wheel'],
        'leva': ['leve', 'shkop', 'kembe', 'gear', 'knob'],
        'marshi': ['marsha', 'kamjo', 'manual', 'marshat', 'marshash', 'shift', 'shifter'],
        'doreza': ['doreze', 'lecke', 'plastike', 'mbajtese', 'dore', 'handle'],
        'dyersh': ['dere', 'dyert', 'dera', 'dyerve', 'door'],
        'njesi': ['unit', 'komponent'],
        'ac': ['air conditioner', 'air', 'ajer', 'ftohes', 'ftohesi', 'ftohsi'],
        'vent': ['ventilator', 'kapak', 'plastike', 'plastik'],
        'celsa': ['celsash', 'cels', 'celes', 'buton', 'butona', 'celsash'],
        'celsash': ['celsa', 'cels', 'celes', 'buton', 'butona', 'celsash', 'key', 'keys'],
        'varese': ['varse', 'keychain', 'holder'],
        'aksesore': ['aksesor', 'parts', 'accessories', 'pjese'],
        'pasqyre': ['pasqyrash', 'pasqyrat', 'pasqyr', 'mirror', 'mirrors'],
        'dritash': ['drita', 'dritave', 'drite', 'drit', 'llampe', 'light', 'lights'],
        'pedale': ['mbulese', 'mbulesa', 'mbrojtese', 'pedalesh', 'pedalet', 'pedals'],
        'mbulesa': ['cover', 'mbulese', 'boot', 'roller', 'console'],
        'sedilje': ['sendilje', 'ulse', 'ulese', 'karrige', 'karrike', 'seat', 'seats'],
        'tapeta': ['shtresa', 'tapet', 'tepetash', 'mats', 'floor'],
        'maskarino': ['maskarin', 'grill', 'gril', 'veshke', 'mushkri'],
        'grila': ['maskarino', 'grill', 'maskarin', 'mjegulle', 'mjegull', 'cover'],
        'sinjale': ['signals', 'indicator', 'indicators', 'sinjal', 'sinjalesh'],
        'dinamike': ['dynamic', 'dinamik'],
        'llampe': ['llampa', 'lampe', 'sinjal', 'llambe', 'llamba', 'stopash', 'drita', 'dritash', 'drite'],
        'fenere': ['fener', 'drita', 'llampa', 'llampe', 'headlight', 'headlights'],
        'stopa': ['tail lights', 'drita', 'mbrapme', 'mbrapa', 'stopat'],
        'fshirese': ['pastruese', 'pastrues', 'pastrim', 'fshese', 'fshesa', 'cleaner'],
        'leter': ['vinyl', 'wrap', 'tint', 'erresim', 'errsim'],
        'tint': ['erresim', 'leter', 'vinyl', 'wrap', 'mbulese'],
        'rezervuar': ['tank', 'depozite', 'depozita', 'depozit', 'mbajtese', 'reservoir'],
        'coolant': ['antifriz', 'antifreeze', 'anti', 'freeze', 'ftohes', 'ftohje', 'coolanti', 'kullant'],
        'xhamash': ['xhama', 'xhamat', 'xhamave', 'xhami', 'window', 'windshield'],
        'veshje': ['mbulese', 'shtrese', 'shtres', 'mbrojtes', 'mbrojtese', 'coat', 'coating', 'cover'],
        'qeramike': ['qeramik', 'graphene', 'qeramika', 'ceramic'],
        'lecke': ['doreze', 'dorashk', 'mitt', 'glove', 'towel'],
        'aditive': ['additive', 'aditiv', 'shtues', 'riparues', 'fuqizues', 'pastrues', 'shtese'],
        'alkol': ['leng', 'uje'],
        'vaj': ['lubrifikues', 'lubrifikant', 'oil', 'vaji', 'fluid', 'leng'],
        'kapak': ['vent', 'ac', 'cover'],
        'karikues': ['karikus', 'fuqizus', 'fuqizues', 'riparues', 'riparim', 'charger'],
        'siguresa': ['fuse', 'sigures', 'sigurese'],
        'universale': ['universal', 'gjitha', 'all'],
        'halogjen': ['halogen', 'drita'],
        'p21w': ['p21/5w', 'stopa'],
        'ba15s': ['ba15d', 'bay15d', 'bau15s', 'baz15d'],
        'kruajtes': ['scraper', 'kruajts', 'kruarje', 'krruajtes', 'krruajts', 'krruarje'],
        'vinyl': ['leter', 'wrap', 'vinil', 'vinyli'],
        'vinyli': ['leter', 'wrap', 'vinil', 'vinyl'],
        'coolanti': ['antifriz', 'antifreeze', 'anti', 'freeze', 'ftohes', 'ftohje', 'coolant', 'kullant'],
        'qafe': ['neck', 'tub', 'trup', 'kok', 'koke'],
        'kapsula': ['pako', 'leng', 'xhami'],
        'shkumeberes': ['shkume', 'shkum', 'shkumues', 'shkumator', 'beres', 'foam', 'cannon', 'shishe'],
    }
    
    # Tokenize and clean query - remove stop words
    tokens = [w.strip() for w in query.split() if w.strip() and w.strip() not in stop_words]
    
    if not tokens:
        return jsonify([])
    
    print(f"🔍 Search tokens after cleaning: {tokens}")  # Debug
    
    # Get all products
    all_products = Product.query.all()
    scored_products = []
    
    for product in all_products:
        # Build searchable fields
        title_text = product.product_name.lower()
        desc_text = (product.description or '').lower()
        tags_text = (product.tags or '').lower()
        specs_text = ' '.join([spec.value.lower() for spec in product.specs])
        
        # Combine all text for checking
        all_text = f"{title_text} {desc_text} {tags_text} {specs_text}"
        
        # Check if ALL tokens match (AND logic)
        all_tokens_found = True
        score = 0
        
        for token in tokens:
            token_found = False
            
            # Get synonyms for this token
            search_terms = [token]
            if token in synonyms:
                search_terms = synonyms[token]
            
            # Check if any synonym matches
            for term in search_terms:
                if term in all_text:
                    token_found = True
                    
                    # Add weighted scores based on where it's found
                    if term in title_text:
                        score += 10
                    if term in tags_text:
                        score += 8
                    if term in specs_text:
                        score += 5
                    if term in desc_text:
                        score += 2
                    
                    break  # Stop checking synonyms once one matches
            
            # If this token (or its synonyms) wasn't found, exclude this product
            if not token_found:
                all_tokens_found = False
                break
        
        # Only include if ALL tokens were found
        if all_tokens_found and product.main_image:
            # Bonus for exact phrase match
            if query in title_text:
                score += 50
            
            # Bonus for newer products
            score += product.product_id * 0.01
            
            # Bonus for special offers
            if product.is_special or product.discount_price:
                score += 5
            
            scored_products.append((score, product))
            print(f"✓ Match: {product.product_name} (score: {score})")  # Debug
    
    print(f"📊 Total matches: {len(scored_products)}")  # Debug
    
    # Sort by score (highest first)
    scored_products.sort(key=lambda x: x[0], reverse=True)
    
    # Filter out products without images and return top 50
    products_with_images = [(score, p) for score, p in scored_products if p.main_image]
    
    return jsonify([format_product(p[1]) for p in products_with_images[:50]])

# ---------------- IMAGE UPLOAD (Optional - for admin) ----------------
@app.route('/api/upload-image', methods=['POST'])
def upload_image():
    """Upload product image"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        # Add timestamp to avoid conflicts
        filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Return relative URL
        return jsonify({'url': f'/static/uploads/{filename}'}), 200
    
    return jsonify({'error': 'Invalid file type'}), 400

@app.route('/api/brands/<brand_name>/products')
def api_brand_products(brand_name):
    """Get all products for a specific brand - supports comma-separated brands"""
    # First, get the spec_type for 'E pershtatshme per'
    brand_spec_type = SpecType.query.filter_by(name='E pershtatshme per').first()
    
    if not brand_spec_type:
        return jsonify([])
    
    # Get all product specs with this type
    all_brand_specs = ProductSpec.query.filter_by(spectype_id=brand_spec_type.id).all()
    
    # Filter products where brand appears in comma-separated list
    product_ids = []
    for spec in all_brand_specs:
        if spec.value:
            # Split by comma and check each brand
            brands = [b.strip() for b in spec.value.split(',')]
            if brand_name in brands or any(brand_name.lower() == b.lower() for b in brands):
                product_ids.append(spec.product_id)
    
    # Remove duplicates
    product_ids = list(set(product_ids))
    
    # Get products that have images
    products = Product.query.filter(
        Product.product_id.in_(product_ids),
        Product.main_image.isnot(None),
        Product.main_image != ''
    ).all()
    
    return jsonify([format_product(p) for p in products])

@app.route('/api/auth/signup', methods=['POST'])
def api_signup():
    """User registration"""
    data = request.json
    
    if not data or not data.get('email') or not data.get('password') or not data.get('name') or not data.get('surname'):
        return jsonify({'error': 'Missing required fields'}), 400
    
    # Check if user exists
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'Email already registered'}), 400
    
    # Create user
    user = User(
        email=data['email'],
        password_hash=generate_password_hash(data['password']),
        name=data['name'],
        surname=data['surname']
    )
    
    db.session.add(user)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'user': {
            'id': user.user_id,
            'email': user.email,
            'name': user.name,
            'surname': user.surname
        }
    }), 201

@app.route('/api/auth/login', methods=['POST'])
def api_login():
    """User login"""
    data = request.json
    
    if not data or not data.get('email') or not data.get('password'):
        return jsonify({'error': 'Missing email or password'}), 400
    
    user = User.query.filter_by(email=data['email']).first()
    
    if not user or not check_password_hash(user.password_hash, data['password']):
        return jsonify({'error': 'Invalid email or password'}), 401
    
    # Update last login
    user.last_login = datetime.utcnow()
    db.session.commit()
    
    return jsonify({
        'success': True,
        'user': {
            'id': user.user_id,
            'email': user.email,
            'name': user.name,
            'surname': user.surname
        }
    }), 200

@app.route('/api/auth/forgot-password', methods=['POST'])
def api_forgot_password():
    """Initiate password reset"""
    data = request.json
    
    if not data or not data.get('email'):
        return jsonify({'error': 'Email required'}), 400
    
    user = User.query.filter_by(email=data['email']).first()
    
    if not user:
        # Don't reveal if email exists
        return jsonify({'success': True, 'message': 'If email exists, reset link sent'}), 200
    
    # Generate reset token
    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(hours=24)
    
    reset = PasswordReset(
        user_id=user.user_id,
        token=token,
        expires_at=expires_at
    )
    
    db.session.add(reset)
    db.session.commit()
    
    # TODO: Send email with reset link
    # For now, just return the token (in production, send via email)
    return jsonify({
        'success': True,
        'message': 'Reset link sent to email',
        'token': token  # Remove this in production
    }), 200

@app.route('/api/auth/reset-password', methods=['POST'])
def api_reset_password():
    """Reset password with token"""
    data = request.json
    
    if not data or not data.get('token') or not data.get('new_password'):
        return jsonify({'error': 'Missing required fields'}), 400
    
    reset = PasswordReset.query.filter_by(token=data['token'], used=False).first()
    
    if not reset or reset.expires_at < datetime.utcnow():
        return jsonify({'error': 'Invalid or expired token'}), 400
    
    user = User.query.get(reset.user_id)
    user.password_hash = generate_password_hash(data['new_password'])
    reset.used = True
    
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Password reset successful'}), 200

# ---------------- ADMIN PANEL ----------------

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    from flask import session, request, redirect, url_for
    
    if request.method == 'POST':
        password = request.form.get('password')
        if password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            return redirect(url_for('admin_panel'))
        else:
            flash('Invalid password', 'error')
    
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Admin Login</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <script src="https://cdn.tailwindcss.com"></script>
        <style>
            @media (max-width: 767px) {
                input[type="password"] {
                    font-size: 16px !important;
                }
            }
        </style>
    </head>
    <body class="bg-gray-100 flex items-center justify-center min-h-screen p-4">
        <div class="bg-white p-6 md:p-8 rounded-lg shadow-lg w-full max-w-md">
            <h1 class="text-xl md:text-2xl font-bold text-black mb-6 text-center">Admin Login</h1>
            <form method="POST" class="space-y-4">
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-2">Password</label>
                    <input type="password" name="password" required 
                           class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-600 focus:border-transparent text-base">
                </div>
                <button type="submit" 
                        class="w-full bg-red-600 text-white py-3 rounded-lg hover:bg-red-700 transition-colors font-medium">
                    Login
                </button>
            </form>
        </div>
    </body>
    </html>
    '''

@app.route('/admin/logout')
def admin_logout():
    from flask import session, redirect, url_for
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))

@app.route('/admin')
@require_admin
def admin_panel():
    """Admin dashboard"""
    return render_template('admin.html')

@app.route('/admin/products')
@require_admin
def admin_products():
    """List all products"""
    products = Product.query.order_by(Product.product_id.desc()).all()
    
    # Ensure products have subcategory relationship loaded
    for product in products:
        if not product.main_image:
            product.main_image = '/static/uploads/default.png'
    
    return render_template('admin_products.html', products=products)

@app.route('/admin/add-product')
@require_admin
def admin_add_product():
    """Add new product page"""
    categories = Category.query.all()
    
    # Convert categories to JSON-serializable format
    categories_data = []
    for cat in categories:
        categories_data.append({
            'category_id': cat.category_id,
            'category_name': cat.category_name,
            'subcategories': [
                {
                    'subcategory_id': sub.subcategory_id,
                    'subcategory_name': sub.subcategory_name
                }
                for sub in cat.subcategories
            ]
        })
    
    return render_template('admin_add_product.html', categories=categories_data)

@app.route('/admin/edit-product/<int:product_id>')
@require_admin
def admin_edit_product(product_id):
    """Edit existing product page"""
    product = Product.query.get_or_404(product_id)
    categories = Category.query.all()
    
    # Convert categories to JSON-serializable format
    categories_data = []
    for cat in categories:
        categories_data.append({
            'category_id': cat.category_id,
            'category_name': cat.category_name,
            'subcategories': [
                {
                    'subcategory_id': sub.subcategory_id,
                    'subcategory_name': sub.subcategory_name
                }
                for sub in cat.subcategories
            ]
        })
    
    # Convert product to dict
    product_data = {
        'product_id': product.product_id,
        'product_name': product.product_name,
        'description': product.description or '',
        'price': product.price,
        'discount_price': product.discount_price or '',
        'is_special': product.is_special,
        'subcategory_id': product.subcategory_id,
        'category_id': product.subcategory.category_id,
        'main_image': product.main_image or '',
        'image_urls': product.image_urls or '',
        'tags': product.tags or '',
        'specs': [
            {
                'spectype_id': spec.spectype_id,
                'spectype_name': spec.spec_type.name,
                'value': spec.value
            }
            for spec in product.specs
        ]
    }
    
    return render_template('admin_add_product.html', 
                         categories=categories_data, 
                         product=product_data,
                         is_edit=True)

@app.route('/api/admin/product', methods=['POST'])
@require_admin
def api_admin_create_product():
    """Create a new product"""
    try:
        data = request.json
        
        # Create product
        product = Product(
            product_name=data['name'],
            description=data.get('description'),
            price=float(data['price']),
            discount_price=float(data['discount_price']) if data.get('discount_price') else None,
            is_special=data.get('is_special', False),
            sold_out=data.get('sold_out', False),
            subcategory_id=int(data['subcategory_id']),
            main_image=data.get('main_image'),
            image_urls=data.get('image_urls'),
            tags=data.get('tags')
        )
        
        db.session.add(product)
        db.session.flush()  # Get the product_id
        
        # Add specs
        if data.get('specs'):
            for spec_data in data['specs']:
                if spec_data.get('value'):  # Only add if value exists
                    spec = ProductSpec(
                        product_id=product.product_id,
                        spectype_id=int(spec_data['spectype_id']),
                        value=spec_data['value']
                    )
                    db.session.add(spec)
        
        db.session.commit()

        ping_google_sitemap()  # Notify Google
        
        return jsonify({
            'success': True,
            'product_id': product.product_id,
            'message': 'Product created successfully'
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/admin/product/<int:product_id>', methods=['PUT'])
@require_admin
def api_admin_update_product(product_id):
    """Update existing product"""
    try:
        product = Product.query.get_or_404(product_id)
        data = request.json
        
        # Update basic fields
        product.product_name = data['name']
        product.description = data.get('description')
        product.price = float(data['price'])
        product.discount_price = float(data['discount_price']) if data.get('discount_price') else None
        product.is_special = data.get('is_special', False)
        product.sold_out = data.get('sold_out', False)
        product.subcategory_id = int(data['subcategory_id'])
        product.main_image = data.get('main_image')
        product.image_urls = data.get('image_urls')
        product.tags = data.get('tags')
        
        # Update specs - delete old ones and add new
        ProductSpec.query.filter_by(product_id=product_id).delete()
        
        if data.get('specs'):
            for spec_data in data['specs']:
                if spec_data.get('value'):
                    spec = ProductSpec(
                        product_id=product_id,
                        spectype_id=int(spec_data['spectype_id']),
                        value=spec_data['value']
                    )
                    db.session.add(spec)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Product updated successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/admin/product/<int:product_id>', methods=['DELETE'])
@require_admin
def api_admin_delete_product(product_id):
    """Delete a product"""
    try:
        product = Product.query.get_or_404(product_id)
        db.session.delete(product)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Product deleted successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/admin/subcategory/<int:subcategory_id>/specs')
@require_admin
def api_admin_subcategory_specs(subcategory_id):
    """Get spec types for subcategory (for admin form)"""
    sub = Subcategory.query.get_or_404(subcategory_id)
    specs = []
    for st in sub.spec_types:
        # Use predefined choices if spec name matches known types
        choices = []
        if st.choices:
            choices = st.choices.split(',')
        
        # Override with predefined choices for known types
        if st.name == 'E pershtatshme per':
            choices = ['Volkswagen', 'BMW', 'Audi', 'Mercedes-Benz', 'Toyota', 'Ford', 
                      'Skoda', 'Porsche', 'SEAT', 'Opel', 'Fiat', 'Range Rover', 
                      'Tesla', 'Hyundai', 'Citroën', 'MINI', 'Honda', 'Peugeot', 
                      'Renault', 'Nissan', 'Volvo', 'Mazda']
        
        specs.append({
            'id': st.id,
            'name': st.name,
            'value_type': st.value_type,
            'choices': choices
        })
    return jsonify(specs)

def send_order_notification_email(order, cart_items):
    """Send email notification when new order is placed"""
    if not MAIL_ENABLED or mail is None:
        print("⚠️ Email system disabled - skipping notification")
        return
    try:
        # Build order items HTML
        items_html = ""
        for item in cart_items:
            items_html += f"""
            <tr>
                <td style="padding: 10px; border-bottom: 1px solid #ddd;">{item['name']}</td>
                <td style="padding: 10px; border-bottom: 1px solid #ddd; text-align: center;">{item['quantity']}</td>
                <td style="padding: 10px; border-bottom: 1px solid #ddd; text-align: right;">{int(item['price'])} ALL</td>
                <td style="padding: 10px; border-bottom: 1px solid #ddd; text-align: right;">{int(item['price'] * item['quantity'])} ALL</td>
            </tr>
            """
        
        # Create email
        msg = Message(
            subject=f'🔔 New Order #{order.order_id} - Auto Adeal',
            recipients=['autoadeal@gmail.com'],
            html=f"""
            <html>
                <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                    <div style="max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f9f9f9;">
                        <div style="background-color: #dc2626; color: white; padding: 20px; text-align: center; border-radius: 10px 10px 0 0;">
                            <h1 style="margin: 0;">New Order Received!</h1>
                            <p style="margin: 10px 0 0 0; font-size: 18px;">Order #{order.order_id}</p>
                        </div>
                        
                        <div style="background-color: white; padding: 20px; border-radius: 0 0 10px 10px;">
                            <h2 style="color: #dc2626; border-bottom: 2px solid #dc2626; padding-bottom: 10px;">Customer Information</h2>
                            <table style="width: 100%; margin-bottom: 20px;">
                                <tr>
                                    <td style="padding: 8px 0;"><strong>Name:</strong></td>
                                    <td style="padding: 8px 0;">{order.customer_name}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 8px 0;"><strong>Phone:</strong></td>
                                    <td style="padding: 8px 0;">{order.customer_phone}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 8px 0;"><strong>Address:</strong></td>
                                    <td style="padding: 8px 0;">{order.customer_address if hasattr(order, 'customer_address') else ''}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 8px 0;"><strong>City:</strong></td>
                                    <td style="padding: 8px 0;">{order.customer_city}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 8px 0;"><strong>Country:</strong></td>
                                    <td style="padding: 8px 0;">{order.customer_country}</td>
                                </tr>
                            </table>
                            
                            <h2 style="color: #dc2626; border-bottom: 2px solid #dc2626; padding-bottom: 10px;">Order Details</h2>
                            <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
                                <thead>
                                    <tr style="background-color: #f3f4f6;">
                                        <th style="padding: 10px; text-align: left; border-bottom: 2px solid #ddd;">Product</th>
                                        <th style="padding: 10px; text-align: center; border-bottom: 2px solid #ddd;">Qty</th>
                                        <th style="padding: 10px; text-align: right; border-bottom: 2px solid #ddd;">Price</th>
                                        <th style="padding: 10px; text-align: right; border-bottom: 2px solid #ddd;">Total</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {items_html}
                                </tbody>
                            </table>
                            
                            <div style="text-align: right; font-size: 16px;">
                                <p style="margin: 10px 0;"><strong>Shipping:</strong> {int(order.shipping_cost)} ALL</p>
                                <p style="margin: 10px 0; font-size: 20px; color: #dc2626;"><strong>TOTAL:</strong> {int(order.total_amount)} ALL</p>
                            </div>
                            
                            <div style="margin-top: 30px; padding: 15px; background-color: #fef3c7; border-left: 4px solid #f59e0b; border-radius: 4px;">
                                <p style="margin: 0; font-size: 14px;">
                                    <strong>⚡ Action Required:</strong> Contact the customer to confirm the order and arrange delivery.
                                </p>
                            </div>
                            
                            <div style="margin-top: 20px; text-align: center;">
                                <a href="https://autoadeal.com/admin/orders" style="display: inline-block; background-color: #dc2626; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; font-weight: bold;">
                                    View in Admin Panel
                                </a>
                            </div>
                        </div>
                        
                        <div style="text-align: center; margin-top: 20px; color: #666; font-size: 12px;">
                            <p>Auto Adeal - Aksesore dhe Pjese per Makina</p>
                            <p>Order placed on {order.created_at.strftime('%d/%m/%Y at %H:%M')}</p>
                        </div>
                    </div>
                </body>
            </html>
            """
        )
        
        mail.send(msg)
        print(f"✅ Order notification email sent for order #{order.order_id}")
        
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
        raise


def send_customer_confirmation_email(order, cart_items, customer_email):
    """Send confirmation email to customer"""
    if not MAIL_ENABLED or mail is None:
        print("⚠️ Email system disabled - skipping notification")
        return
    
    try:
        # Build order items HTML
        items_html = ""
        for item in cart_items:
            items_html += f"""
            <tr>
                <td style="padding: 10px; border-bottom: 1px solid #ddd;">{item['name']}</td>
                <td style="padding: 10px; border-bottom: 1px solid #ddd; text-align: center;">{item['quantity']}</td>
                <td style="padding: 10px; border-bottom: 1px solid #ddd; text-align: right;">{int(item['price'] * item['quantity'])} ALL</td>
            </tr>
            """
        
        msg = Message(
            subject=f'✅ Konfirmim Porosie #{order.order_id} - Auto Adeal',
            recipients=[customer_email],
            html=f"""
            <html>
                <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                    <div style="max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f9f9f9;">
                        <div style="background-color: #dc2626; color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
                            <h1 style="margin: 0; font-size: 28px;">Faleminderit për Porosinë!</h1>
                            <p style="margin: 15px 0 0 0; font-size: 18px;">Porosia Juaj #${order.order_id}</p>
                        </div>
                        
                        <div style="background-color: white; padding: 30px; border-radius: 0 0 10px 10px;">
                            <div style="background-color: #dcfce7; border-left: 4px solid #16a34a; padding: 15px; margin-bottom: 25px; border-radius: 4px;">
                                <p style="margin: 0; color: #166534; font-weight: bold;">✅ Porosia juaj u pranua me sukses!</p>
                                <p style="margin: 5px 0 0 0; color: #166534; font-size: 14px;">Do t'ju kontaktojmë së shpejti për konfirmim.</p>
                            </div>
                            
                            <h2 style="color: #dc2626; border-bottom: 2px solid #dc2626; padding-bottom: 10px; margin-bottom: 20px;">Detajet e Dërgesës</h2>
                            <table style="width: 100%; margin-bottom: 25px;">
                                <tr>
                                    <td style="padding: 8px 0; color: #666;">Emri:</td>
                                    <td style="padding: 8px 0; font-weight: bold;">{order.customer_name}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 8px 0; color: #666;">Telefoni:</td>
                                    <td style="padding: 8px 0; font-weight: bold;">{order.customer_phone}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 8px 0; color: #666;">Adresa:</td>
                                    <td style="padding: 8px 0; font-weight: bold;">{order.customer_address if hasattr(order, 'customer_address') else ''}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 8px 0; color: #666;">Qyteti:</td>
                                    <td style="padding: 8px 0; font-weight: bold;">{order.customer_city}, {order.customer_country}</td>
                                </tr>
                            </table>
                            
                            <h2 style="color: #dc2626; border-bottom: 2px solid #dc2626; padding-bottom: 10px; margin-bottom: 20px;">Produktet e Porositura</h2>
                            <table style="width: 100%; border-collapse: collapse; margin-bottom: 25px;">
                                <thead>
                                    <tr style="background-color: #f3f4f6;">
                                        <th style="padding: 12px; text-align: left; border-bottom: 2px solid #ddd;">Produkti</th>
                                        <th style="padding: 12px; text-align: center; border-bottom: 2px solid #ddd;">Sasia</th>
                                        <th style="padding: 12px; text-align: right; border-bottom: 2px solid #ddd;">Çmimi</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {items_html}
                                </tbody>
                            </table>
                            
                            <div style="background-color: #f9fafb; padding: 20px; border-radius: 8px; margin-bottom: 25px;">
                                <div style="display: flex; justify-content: space-between; margin-bottom: 10px; font-size: 16px;">
                                    <span>Nëntotali:</span>
                                    <span>{int(order.total_amount - order.shipping_cost)} ALL</span>
                                </div>
                                <div style="display: flex; justify-content: space-between; margin-bottom: 15px; font-size: 16px;">
                                    <span>Dërgesa:</span>
                                    <span>{int(order.shipping_cost)} ALL</span>
                                </div>
                                <div style="display: flex; justify-content: space-between; font-size: 22px; font-weight: bold; color: #dc2626; padding-top: 15px; border-top: 2px solid #ddd;">
                                    <span>TOTALI:</span>
                                    <span>{int(order.total_amount)} ALL</span>
                                </div>
                            </div>
                            
                            <div style="background-color: #fef3c7; border-left: 4px solid #f59e0b; padding: 15px; margin-bottom: 25px; border-radius: 4px;">
                                <p style="margin: 0; font-size: 14px; color: #92400e;">
                                    <strong>💳 Pagesa në Dorëzim</strong><br>
                                    Do të paguani kur të merrni produktet. Asnjë pagesë paraprak nuk kërkohet.
                                </p>
                            </div>
                            
                            <h3 style="color: #1f2937; margin-bottom: 15px;">Çfarë Ndodh Tani?</h3>
                            <ol style="color: #4b5563; line-height: 1.8; padding-left: 20px;">
                                <li>Do t'ju kontaktojmë brenda 24 orëve për të konfirmuar porosinë.</li>
                                <li>Do të përgatisim produktet tuaja për dërgim.</li>
                                <li>Do t'ju njoftojmë kur porosia të jetë në rrugë.</li>
                                <li>Produktet do t'ju dorëzohen në adresën tuaj.</li>
                            </ol>
                            
                            <div style="text-align: center; margin-top: 30px;">
                                <p style="color: #666; margin-bottom: 15px;">Keni pyetje? Na kontaktoni:</p>
                                <p style="margin: 5px 0;">📞 <a href="tel:+355685526714" style="color: #dc2626; text-decoration: none;">+355 68 552 6714</a></p>
                                <p style="margin: 5px 0;">📧 <a href="mailto:autoadeal@gmail.com" style="color: #dc2626; text-decoration: none;">autoadeal@gmail.com</a></p>
                                <p style="margin: 5px 0;">📱 <a href="https://www.instagram.com/autoadeal" style="color: #dc2626; text-decoration: none;">@autoadeal</a></p>
                            </div>
                        </div>
                        
                        <div style="text-align: center; margin-top: 20px; color: #666; font-size: 12px;">
                            <p style="margin: 5px 0;">Auto Adeal - Aksesore dhe Pjesë për Makina</p>
                            <p style="margin: 5px 0;">Sarandë, Shqipëri</p>
                            <p style="margin: 5px 0;">Porosia u krye më {order.created_at.strftime('%d/%m/%Y në %H:%M')}</p>
                        </div>
                    </div>
                </body>
            </html>
            """
        )
        
        mail.send(msg)
        print(f"✅ Customer confirmation email sent for order #{order.order_id}")
        
    except Exception as e:
        print(f"❌ Failed to send customer email: {e}")

@app.route('/api/order', methods=['POST'])
def create_order():
    """Save customer order"""
    try:
        data = request.json
        
        if not data or not data.get('customer_name') or not data.get('customer_phone'):
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400
        
        # Calculate totals
        cart_items = data.get('cart_items', [])
        subtotal = sum(item['price'] * item['quantity'] for item in cart_items)
        shipping_cost = data.get('shipping_cost', 0)
        total = subtotal + shipping_cost
        
        # Get user_id if email provided
        user_id = None
        customer_email = data.get('customer_email')
        if customer_email:
            user = User.query.filter_by(email=customer_email).first()
            if user:
                user_id = user.user_id

        # Create order
        order = Order(
            user_id=user_id,
            customer_name=data['customer_name'],
            customer_phone=data['customer_phone'],
            customer_email=customer_email,
            customer_address=data.get('customer_address', ''),
            customer_city=data.get('customer_city', ''),
            customer_country=data.get('customer_country', ''),
            total_amount=total,
            shipping_cost=shipping_cost,
            order_items=json.dumps(cart_items),
            status='pending'
        )
        
        db.session.add(order)
        db.session.commit()
        
        print(f"✅ Order #{order.order_id} created successfully")
        
        # Send emails asynchronously (non-blocking)
        if MAIL_ENABLED and mail:
            try:
                # Create email messages
                admin_msg = create_admin_notification_email(order, cart_items)
                
                # Send in background thread
                Thread(target=send_async_email, args=(app, admin_msg)).start()
                
                if customer_email:
                    customer_msg = create_customer_confirmation_email(order, cart_items, customer_email)
                    Thread(target=send_async_email, args=(app, customer_msg)).start()
                
                print("📧 Emails queued for sending")
            except Exception as e:
                print(f"⚠️ Email queueing failed: {e}")
        
        return jsonify({
            'success': True,
            'order_id': order.order_id,
            'message': 'Order placed successfully'
        }), 201
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Order creation error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400
    
@app.route('/api/user/orders', methods=['POST'])
def get_user_orders():
    """Get orders for a specific user by email"""
    try:
        data = request.json
        email = data.get('email')
        
        if not email:
            return jsonify({'success': False, 'error': 'Email required'}), 400
        
        # Get user
        user = User.query.filter_by(email=email).first()
        
        if not user:
            return jsonify({'success': False, 'orders': []}), 200
        
        # Get all orders for this user
        orders = Order.query.filter_by(user_id=user.user_id).order_by(Order.created_at.desc()).all()
        
        orders_list = []
        for order in orders:
            # Get status history
            history = OrderStatusHistory.query.filter_by(order_id=order.order_id).order_by(OrderStatusHistory.created_at.asc()).all()
            
            orders_list.append({
                'order_id': order.order_id,
                'customer_name': order.customer_name,
                'customer_phone': order.customer_phone,
                'customer_address': order.customer_address,
                'customer_city': order.customer_city,
                'customer_country': order.customer_country,
                'total_amount': order.total_amount,
                'shipping_cost': order.shipping_cost,
                'status': order.status,
                'order_items': json.loads(order.order_items),
                'created_at': order.created_at.strftime('%Y-%m-%d %H:%M'),
                'notes': order.notes,
                'status_history': [
                    {
                        'status': h.status,
                        'notes': h.notes,
                        'created_at': h.created_at.strftime('%Y-%m-%d %H:%M')
                    } for h in history
                ]
            })
        
        return jsonify({'success': True, 'orders': orders_list}), 200
        
    except Exception as e:
        print(f"❌ Get user orders error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/admin/orders', methods=['GET'])
@require_admin
def get_orders():
    """Get all orders for admin"""
    try:
        status = request.args.get('status', None)
        
        if status:
            orders = Order.query.filter_by(status=status).order_by(Order.created_at.desc()).all()
        else:
            orders = Order.query.order_by(Order.created_at.desc()).all()
        
        orders_list = []
        for order in orders:
            orders_list.append({
                'order_id': order.order_id,
                'customer_name': order.customer_name,
                'customer_phone': order.customer_phone,
                'customer_address': order.customer_address,
                'customer_city': order.customer_city,
                'customer_country': order.customer_country,
                'total_amount': order.total_amount,
                'shipping_cost': order.shipping_cost,
                'status': order.status,
                'order_items': json.loads(order.order_items),
                'created_at': order.created_at.strftime('%Y-%m-%d %H:%M'),
                'notes': order.notes
            })
        
        return jsonify(orders_list), 200
        
    except Exception as e:
        print(f"❌ Get orders error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/admin/order/<int:order_id>/status', methods=['PUT'])
@require_admin
def update_order_status(order_id):
    """Update order status"""
    try:
        order = Order.query.get_or_404(order_id)
        data = request.json
        
        # Create status history entry
        if 'status' in data:
            history = OrderStatusHistory(
                order_id=order_id,
                status=data['status'],
                notes=data.get('notes')
            )
            db.session.add(history)
            order.status = data['status']
        
        if 'notes' in data:
            order.notes = data['notes']
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Order updated'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/admin/order/<int:order_id>', methods=['DELETE'])
@require_admin
def delete_order(order_id):
    """Delete an order"""
    try:
        order = Order.query.get_or_404(order_id)
        db.session.delete(order)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Order deleted'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/track-view', methods=['POST'])
def track_product_view():
    """Track product views for relevance learning"""
    data = request.json
    if not data or not data.get('product_id'):
        return jsonify({'success': False}), 400
    
    view = ProductView(
        product_id=data['product_id'],
        search_query=data.get('search_query')
    )
    
    db.session.add(view)
    db.session.commit()
    
    return jsonify({'success': True}), 200

#Cleanup task to remove old cached entries
@app.route('/api/admin/cleanup-cache', methods=['POST'])
def cleanup_old_cache():
    """Remove cached products older than 7 days"""
    from datetime import date, timedelta
    
    seven_days_ago = date.today() - timedelta(days=7)
    DailyFeatured.query.filter(DailyFeatured.featured_date < seven_days_ago).delete()
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Old cache cleaned up'})

# Cleanup old cache on startup
def cleanup_on_startup():
    from datetime import date, timedelta
    with app.app_context():
        seven_days_ago = date.today() - timedelta(days=7)
        try:
            DailyFeatured.query.filter(DailyFeatured.featured_date < seven_days_ago).delete()
            db.session.commit()
            print("✓ Cleaned up old daily featured cache")
        except:
            db.session.rollback()

# Run cleanup
cleanup_on_startup()

@app.route('/api/admin/product/<int:product_id>/toggle-stock', methods=['POST'])
@require_admin
def toggle_product_stock(product_id):
    """Toggle product sold out status"""
    try:
        product = Product.query.get_or_404(product_id)
        product.sold_out = not product.sold_out
        db.session.commit()
        
        status = "sold out" if product.sold_out else "in stock"
        return jsonify({
            'success': True,
            'sold_out': product.sold_out,
            'message': f'Product marked as {status}'
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/admin/products/clear-sold-out', methods=['POST'])
@require_admin
def clear_sold_out_products():
    """Delete all sold out products"""
    try:
        deleted_count = Product.query.filter_by(sold_out=True).delete()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'deleted_count': deleted_count,
            'message': f'Deleted {deleted_count} sold out products'
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400
    
@app.route('/api/settings')
def get_settings():
    """Get site settings"""
    settings = SiteSettings.query.all()
    return jsonify({s.setting_key: s.setting_value for s in settings})

@app.route('/api/admin/settings', methods=['POST'])
@require_admin
def update_settings():
    """Update site settings"""
    try:
        data = request.json
        
        for key, value in data.items():
            setting = SiteSettings.query.filter_by(setting_key=key).first()
            if setting:
                setting.setting_value = value
            else:
                setting = SiteSettings(setting_key=key, setting_value=value)
                db.session.add(setting)
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Settings updated'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400
    
@app.route('/admin/settings')
def admin_settings():
    """Site settings page"""
    return render_template('admin_settings.html')

@app.route('/sitemap.xml')
def sitemap():
    """Generate dynamic sitemap for SEO"""
    from flask import make_response
    
    pages = []
    
    # Homepage
    pages.append({
        'loc': 'https://autoadeal.com/',
        'lastmod': datetime.now().strftime('%Y-%m-%d'),
        'changefreq': 'daily',
        'priority': '1.0'
    })
    
    # Static pages
    static_pages = [
        ('/#special-offers', '0.9', 'daily'),
        ('/#brands', '0.8', 'weekly'),
        ('/#contact', '0.7', 'monthly'),
    ]
    
    for url, priority, freq in static_pages:
        pages.append({
            'loc': f'https://autoadeal.com{url}',
            'lastmod': datetime.now().strftime('%Y-%m-%d'),
            'changefreq': freq,
            'priority': priority
        })
    
    # All subcategories
    from sqlalchemy import distinct
    subcategories = Subcategory.query.all()
    for sub in subcategories:
        pages.append({
            'loc': f'https://autoadeal.com/subcategory/{sub.subcategory_id}/{sub.subcategory_name.replace(" ", "-")}',
            'lastmod': datetime.now().strftime('%Y-%m-%d'),
            'changefreq': 'weekly',
            'priority': '0.8'
        })

    # All products
    products = Product.query.filter(Product.main_image.isnot(None)).all()
    for product in products:
        pages.append({
            'loc': f'https://autoadeal.com/product/{product.product_id}',
            'lastmod': datetime.now().strftime('%Y-%m-%d'),
            'changefreq': 'weekly',
            'priority': '0.8'
        })
    
    # Generate XML
    sitemap_xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    sitemap_xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    
    for page in pages:
        sitemap_xml += '  <url>\n'
        sitemap_xml += f'    <loc>{page["loc"]}</loc>\n'
        sitemap_xml += f'    <lastmod>{page["lastmod"]}</lastmod>\n'
        sitemap_xml += f'    <changefreq>{page["changefreq"]}</changefreq>\n'
        sitemap_xml += f'    <priority>{page["priority"]}</priority>\n'
        sitemap_xml += '  </url>\n'
    
    sitemap_xml += '</urlset>'
    
    response = make_response(sitemap_xml)
    response.headers["Content-Type"] = "application/xml"
    return response

@app.route('/admin/orders')
@require_admin
def admin_orders():
    """Admin orders page"""
    return render_template('admin_orders.html')

@app.route('/robots.txt')
def robots():
    """Tell search engines what to crawl"""
    from flask import make_response
    
    robots_txt = """User-agent: *
Allow: /
Disallow: /admin/
Disallow: /api/auth/

Sitemap: https://autoadeal.com/sitemap.xml
"""
    
    response = make_response(robots_txt)
    response.headers["Content-Type"] = "text/plain"
    return response

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=port, debug=False)