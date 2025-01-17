import os
from flask import Flask, render_template, jsonify, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
import logging
from datetime import datetime, timedelta
from sqlalchemy import func
from werkzeug.security import generate_password_hash, check_password_hash
import json

# Configure logging
logging.basicConfig(level=logging.DEBUG)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
app = Flask(__name__)

app.secret_key = os.environ.get("FLASK_SECRET_KEY") or "health_tracking_secret_key"
# Get the DATABASE_URL from environment and fix potential "postgres://" issue
db_url = os.environ.get("DATABASE_URL")
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

db.init_app(app)

# Admin authentication decorator
def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session:
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/track')
def track():
    return render_template('track.html')

@app.route('/get-menu/<kit_id>')
def get_menu(kit_id):
    from models import KitCode
    kit_code = KitCode.query.filter_by(code=kit_id, is_active=True).first()
    if kit_code:
        return jsonify({"menu_data": kit_code.menu_data})
    return jsonify({"menu_data": None})


@app.route('/get-menu-data')
def get_menu_data():
    kit_id = request.args.get('kitId')
    if not kit_id:
        return jsonify({"error": "No kit ID provided"}), 400

    from models import KitCode
    kit_code = KitCode.query.filter_by(code=kit_id, is_active=True).first()
    if kit_code:
        return jsonify({"menu_data": kit_code.menu_data})
    return jsonify({"error": "Invalid kit ID"}), 404

@app.route('/validate-kit/<kit_id>', methods=['POST'])
def validate_kit(kit_id):
    from models import AnonymousUser, Admin, KitCode
    logging.debug(f"Validating kit ID: {kit_id}")

    data = request.get_json()
    user_name = data.get('name')

    if not user_name:
        logging.debug("Name is required but not provided")
        return jsonify({"valid": False, "error": "Name is required"}), 400

    # Check if it's an admin code
    admin = Admin.query.filter_by(username=kit_id).first()
    if admin and admin.is_active:
        session['admin_id'] = admin.id
        logging.debug(f"Admin login successful for: {kit_id}")
        return jsonify({"valid": True, "is_admin": True})

    # Check if it's a valid kit ID
    user = AnonymousUser.query.filter_by(kit_id=kit_id).first()
    kit_code = KitCode.query.filter_by(code=kit_id, is_active=True).first()

    logging.debug(f"User found: {user is not None}, Kit code found and active: {kit_code is not None}")

    # Only validate if both entries exist and the kit code is active
    is_valid = user is not None and kit_code is not None

    if is_valid:
        # Update user name if valid
        user.name = user_name
        db.session.commit()
        logging.debug(f"Updated name for kit ID {kit_id} to {user_name}")

    return jsonify({"valid": is_valid, "is_admin": False})

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        from models import Admin
        username = request.form.get('username')
        password = request.form.get('password')

        admin = Admin.query.filter_by(username=username).first()
        if admin and check_password_hash(admin.password_hash, password):
            session['admin_id'] = admin.id
            return redirect(url_for('admin_dashboard'))

        flash('Invalid credentials', 'error')
    return render_template('admin/login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_id', None)
    return redirect(url_for('index'))

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    from models import KitCode
    kit_codes = KitCode.query.order_by(KitCode.created_at.desc()).all()
    return render_template('admin/dashboard.html', kit_codes=kit_codes)

@app.route('/admin/import-codes', methods=['POST'])
@admin_required
def import_kit_codes():
    from models import KitCode, AnonymousUser
    batch_name = request.form.get('batch_name')
    codes = request.form.get('codes', '').strip().split('\n')
    menu_data = request.form.get('menu_data')

    try:
        menu_json = json.loads(menu_data) if menu_data else {}
    except json.JSONDecodeError:
        flash('Invalid JSON format for menu data', 'error')
        return redirect(url_for('admin_dashboard'))

    for code in codes:
        code = code.strip()
        if code:
            kit_code = KitCode(
                code=code,
                batch_name=batch_name,
                menu_data=menu_json,
                created_by=session['admin_id']
            )
            db.session.add(kit_code)
            
            anon_user = AnonymousUser(kit_id=code)
            db.session.add(anon_user)

    db.session.commit()
    flash(f'Successfully imported {len(codes)} kit codes', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/generate-codes', methods=['POST'])
@admin_required
def generate_kit_codes():
    from models import KitCode, AnonymousUser
    batch_name = request.form.get('batch_name')
    quantity = int(request.form.get('quantity', 10))
    menu_data = request.form.get('menu_data')

    try:
        menu_json = json.loads(menu_data) if menu_data else {}
    except json.JSONDecodeError:
        flash('Invalid JSON format for menu data', 'error')
        return redirect(url_for('admin_dashboard'))

    for _ in range(quantity):
        # Generate a new kit ID
        new_kit_id = AnonymousUser.generate_kit_id()

        # Create KitCode entry
        kit_code = KitCode(
            code=new_kit_id,
            batch_name=batch_name,
            menu_data=menu_json,
            created_by=session['admin_id']
        )
        db.session.add(kit_code)

        # Create corresponding AnonymousUser entry
        anon_user = AnonymousUser(kit_id=new_kit_id)
        db.session.add(anon_user)

    db.session.commit()
    flash(f'Successfully generated {quantity} new kit codes', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/toggle-code/<int:code_id>', methods=['POST'])
@admin_required
def toggle_kit_code(code_id):
    from models import KitCode
    kit_code = KitCode.query.get_or_404(code_id)
    kit_code.is_active = not kit_code.is_active
    db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/generate-kit', methods=['POST'])
def generate_kit():
    from models import AnonymousUser
    new_user = AnonymousUser(kit_id=AnonymousUser.generate_kit_id())
    db.session.add(new_user)
    db.session.commit()
    return jsonify({"kit_id": new_user.kit_id})

@app.route('/insights/<kit_id>')
def get_insights(kit_id):
    from models import TrackingEntry, CommunityStats
    from datetime import datetime, timedelta

    # Get date range (last 7 days)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)

    # Fetch entries for the last 7 days
    entries = TrackingEntry.query.filter(
        TrackingEntry.kit_id == kit_id,
        TrackingEntry.date >= start_date,
        TrackingEntry.date <= end_date
    ).order_by(TrackingEntry.date).all()

    if not entries:
        return render_template('insights.html', has_data=False)

    # Prepare trend data
    trend_data = {
        'dates': [],
        'moods': [],
        'stool_types': []
    }

    for entry in entries:
        trend_data['dates'].append(entry.date.strftime('%Y-%m-%d'))
        trend_data['moods'].append(entry.mood)
        trend_data['stool_types'].append(int(entry.stool_type) if entry.stool_type else 0)

    # Get today's latest entry for detailed insights
    latest_entry = entries[-1] if entries else None

    insights = {
        'mood_summary': None,
        'stool_health': None,
        'meal_patterns': None,
        'community_comparison': None
    }

    if latest_entry:
        # Mood analysis
        mood_level = latest_entry.mood
        mood_insights = {
            1: "You're having a tough day. Remember, it's okay to not be okay.",
            2: "Your mood is low. Consider some self-care activities.",
            3: "You're feeling a bit down. Try to do something you enjoy.",
            4: "You're feeling balanced today.",
            5: "You're having a good day! Keep up the positive energy.",
            6: "You're feeling great! What a wonderful day.",
            7: "You're feeling amazing! Remember this feeling!"
        }
        insights['mood_summary'] = mood_insights.get(mood_level, "No mood data available.")

        # Stool health analysis
        stool_type = latest_entry.stool_type
        stool_insights = {
            '1': "Your stool is very hard and separate, indicating possible dehydration.",
            '2': "Your stool is firm but segmented, suggesting good but could be better hydration.",
            '3': "Your stool is well-formed - this is ideal!",
            '4': "Your stool is soft but still well-formed.",
            '5': "Your stool is soft with clear edges - consider more fiber.",
            '6': "Your stool is mushy - consider adjusting your diet.",
            '7': "Your stool is liquid - stay hydrated and monitor your diet."
        }
        insights['stool_health'] = stool_insights.get(stool_type, "No stool data available.")

        # Meal pattern analysis
        meals = latest_entry.meals
        meal_analysis = []

        if meals:
            for meal_type, foods in meals.items():
                if foods:
                    meal_analysis.append(f"{meal_type.title()}: {', '.join(foods.keys())}")

        insights['meal_patterns'] = meal_analysis if meal_analysis else ["No meal data available."]

        # Get community stats for comparison
        today = datetime.now().date()
        community_stats = CommunityStats.query.filter_by(date=today).first()

        if community_stats and community_stats.total_participants > 10:  # Only show if enough participants
            mood_diff = mood_level - community_stats.avg_mood
            mood_comparison = (
                "above average" if mood_diff > 0.5 else
                "below average" if mood_diff < -0.5 else
                "about average"
            )

            insights['community_comparison'] = {
                'mood_comparison': mood_comparison,
                'community_avg_mood': round(community_stats.avg_mood, 1),
                'total_participants': community_stats.total_participants
            }

    # Check if this is a new submission
    show_trends = request.args.get('new_submission') == 'true'

    return render_template('insights.html', 
                         insights=insights, 
                         has_data=bool(latest_entry),
                         trend_data=trend_data if show_trends else None)

@app.route('/save-tracking', methods=['POST'])
def save_tracking():
    from models import TrackingEntry
    data = request.json

    # Create new tracking entry
    entry = TrackingEntry(
        kit_id=data['kitId'],
        meals=data['meals'],
        stool_type=data.get('stool', {}).get('type'),
        mood=data['mood'],
        shared_with_community=True  # Default to sharing with community
    )
    db.session.add(entry)

    # Update community stats
    from models import CommunityStats
    today = datetime.now().date()
    stats = CommunityStats.get_or_create_daily(today)

    # Calculate new averages
    today_entries = TrackingEntry.query.filter(
        TrackingEntry.date >= today,
        TrackingEntry.shared_with_community == True
    ).all()

    if today_entries:
        # Calculate mood average
        total_mood = sum(entry.mood for entry in today_entries if entry.mood)
        stats.avg_mood = total_mood / len(today_entries)

        # Find most common stool type
        stool_types = [entry.stool_type for entry in today_entries if entry.stool_type]
        if stool_types:
            from collections import Counter
            stats.most_common_stool_type = Counter(stool_types).most_common(1)[0][0]

        stats.total_participants = len(today_entries)

    db.session.commit()
    return jsonify({"success": True})

@app.route('/export-data/<kit_id>', methods=['POST'])
def export_data(kit_id):
    from models import TrackingEntry
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    import base64

    # Generate a secure key for encryption
    password = app.secret_key.encode()
    salt = b'health_tracking_salt'  # In production, this should be randomly generated per user
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=480000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password))
    f = Fernet(key)

    # Fetch all user's data
    entries = TrackingEntry.query.filter_by(kit_id=kit_id).order_by(TrackingEntry.date).all()

    export_data = []
    for entry in entries:
        export_data.append({
            'date': entry.date.isoformat(),
            'meals': entry.meals,
            'stool_type': entry.stool_type,
            'mood': entry.mood
        })

    # Encrypt the data
    json_data = json.dumps(export_data)
    encrypted_data = f.encrypt(json_data.encode())

    return jsonify({
        'encrypted_data': encrypted_data.decode(),
        'key': key.decode(),  # In production, this should be securely transmitted
        'message': 'Data exported successfully'
    })

# Initialize the database with test data
with app.app_context():
    import models
    db.create_all()

    # Create a default admin account if it doesn't exist
    from models import Admin
    admin = Admin.query.filter_by(username='admin').first()
    if not admin:
        admin = Admin(
            username='admin',
            password_hash=generate_password_hash('admin123')
        )
        db.session.add(admin)
        db.session.commit()
        logging.info("Created default admin account: username='admin', password='admin123'")

    # Create a test kit ID if it doesn't exist
    from models import AnonymousUser, KitCode
    test_kit_id = 'TEST123456'
    test_kit = AnonymousUser.query.filter_by(kit_id=test_kit_id).first()
    test_kit_code = KitCode.query.filter_by(code=test_kit_id).first()

    if not test_kit and not test_kit_code:
        # Create test anonymous user
        test_kit = AnonymousUser(kit_id=test_kit_id)
        db.session.add(test_kit)

        # Create test kit code with menu data
        test_menu_data = {
            "breakfast": {
                "fruits": ["apple", "banana", "orange"],
                "grains": ["oatmeal", "bread", "cereal"],
                "proteins": ["eggs", "yogurt"]
            },
            "lunch": {
                "proteins": ["chicken", "fish", "tofu"],
                "vegetables": ["salad", "carrots", "broccoli"],
                "grains": ["rice", "pasta"]
            },
            "dinner": {
                "proteins": ["beef", "salmon", "beans"],
                "vegetables": ["spinach", "asparagus", "peas"],
                "grains": ["quinoa", "bread"]
            }
        }

        test_kit_code = KitCode(
            code=test_kit_id,
            batch_name='Test Batch',
            menu_data=test_menu_data,
            created_by=1,  # admin id
            is_active=True
        )
        db.session.add(test_kit_code)
        db.session.commit()
        logging.info(f"Created test kit ID: {test_kit_id} with menu data")