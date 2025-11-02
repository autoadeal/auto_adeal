from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import secrets
import os

# ---------------- CONFIG ----------------
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_EXT = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

app = Flask(__name__)
app.secret_key = "auto_adeal_secret_change_this"
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:@localhost/auto_adeal'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

db = SQLAlchemy(app)

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
        "subcategory_id": product.subcategory_id,
        "main_image": product.main_image,
        "images": images,
        "tags": product.tags or "",
        "specs": specs
    }

# ---------------- ROUTES ----------------
@app.route('/')
def home():
    return render_template('index.html')

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
    """Get all products in a subcategory"""
    Subcategory.query.get_or_404(sub_id)  # Verify subcategory exists
    products = Product.query.filter_by(subcategory_id=sub_id).all()
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
    """Get latest products (simulating 'popular')"""
    products = Product.query.order_by(Product.product_id.desc()).limit(32).all()
    return jsonify([format_product(p) for p in products])

@app.route('/api/search')
def api_search():
    """Search products by name, description, tags, and specs - matches individual words"""
    query = request.args.get('q', '').strip().lower()
    if not query:
        return jsonify([])
    
    # Split query into individual words
    search_words = [w for w in query.split() if len(w) > 0]
    
    # Get all products
    all_products = Product.query.all()
    matching_products = []
    
    for product in all_products:
        # Build searchable content
        searchable_parts = [
            product.product_name.lower(),
            (product.description or '').lower(),
            (product.tags or '').lower()
        ]
        
        # Add specs to searchable content
        for spec in product.specs:
            searchable_parts.append(spec.value.lower())
        
        searchable_text = ' '.join(searchable_parts)
        
        # Check if ANY search word appears
        if any(word in searchable_text for word in search_words):
            matching_products.append(product)
    
    return jsonify([format_product(p) for p in matching_products[:50]])  # Limit to 50 results

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
    """Get all products for a specific brand"""
    # First, get the spec_type for 'E pershtatshme per'
    brand_spec_type = SpecType.query.filter_by(name='E pershtatshme per').first()
    
    if not brand_spec_type:
        return jsonify([])
    
    # Find all product_specs with this spec_type where value matches brand
    matching_specs = ProductSpec.query.filter(
        ProductSpec.spectype_id == brand_spec_type.id,
        ProductSpec.value.like(f'%{brand_name}%')
    ).all()
    
    # Get unique products
    product_ids = list(set([spec.product_id for spec in matching_specs]))
    products = Product.query.filter(Product.product_id.in_(product_ids)).all()
    
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
@app.route('/admin')
def admin_panel():
    """Admin dashboard"""
    return render_template('admin.html')

@app.route('/admin/products')
def admin_products():
    """List all products"""
    products = Product.query.order_by(Product.product_id.desc()).all()
    
    # Ensure products have subcategory relationship loaded
    for product in products:
        if not product.main_image:
            product.main_image = '/static/uploads/default.png'
    
    return render_template('admin_products.html', products=products)

@app.route('/admin/add-product')
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
        
        return jsonify({
            'success': True,
            'product_id': product.product_id,
            'message': 'Product created successfully'
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/admin/product/<int:product_id>', methods=['PUT'])
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
def api_admin_subcategory_specs(subcategory_id):
    """Get spec types for subcategory (for admin form)"""
    sub = Subcategory.query.get_or_404(subcategory_id)
    specs = []
    for st in sub.spec_types:
        specs.append({
            'id': st.id,
            'name': st.name,
            'value_type': st.value_type,
            'choices': st.choices.split(',') if st.choices else []
        })
    return jsonify(specs)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)