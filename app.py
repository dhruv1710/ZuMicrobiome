import os
import logging
import random
import uuid
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from database import db

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Admin authentication decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session:
            flash('Please login first.', 'error')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

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

# Import models after db initialization to avoid circular imports
with app.app_context():
    from models import Admin, AnonymousUser, KitCode, TrackingEntry, CommunityStats
    db.create_all()

    # Create default admin account if it doesn't exist
    default_admin = Admin.query.filter_by(username='Microbiome').first()
    if not default_admin:
        admin = Admin(
            username='Microbiome',
            password_hash=generate_password_hash('MBDao'),
            is_active=True
        )
        db.session.add(admin)
        db.session.commit()
        logging.info('Default admin account created')

@app.route('/')
def index():
    if 'kit_id' in session:
        # Check if user has tracked today
        today = datetime.now().date()
        entry = TrackingEntry.query.filter_by(
            kit_id=session['kit_id'],
            date=today
        ).first()

        # If tracked today, show insights
        if entry:
            return redirect(url_for('get_insights', kit_id=session['kit_id']))

        # If not tracked today, check if they have previous entries
        last_entry = TrackingEntry.query.filter_by(
            kit_id=session['kit_id']
        ).order_by(TrackingEntry.date.desc()).first()

        if last_entry:
            # Show insights first, then they can track new entry
            return redirect(url_for('get_insights', kit_id=session['kit_id']))
        else:
            # First time user, go directly to tracking
            return redirect(url_for('track'))

    return render_template('index.html')

@app.route('/track')
def track():
    if 'kit_id' not in session:
        return redirect(url_for('index'))
    return render_template('track.html')

@app.route('/get-menu-data')
def get_menu_data():
    kit_id = request.args.get('kitId')
    if not kit_id:
        logging.debug("No kit ID provided in get-menu-data request")
        return jsonify({"error": "No kit ID provided"}), 400

    logging.debug(f"Fetching menu data for kit ID: {kit_id}")
    kit_code = KitCode.query.filter_by(code=kit_id, is_active=True).first()

    if kit_code and kit_code.menu_data:
        logging.debug(f"Found menu data for kit ID {kit_id}: {kit_code.menu_data}")
        return jsonify({"menu_data": kit_code.menu_data})

    logging.debug(f"No menu data found for kit ID: {kit_id}")
    return jsonify({"error": "Invalid kit ID or no menu data available"}), 404

@app.route('/validate-kit/<kit_id>', methods=['GET', 'POST'])
def validate_kit(kit_id):
    logging.debug(f"Validating kit ID: {kit_id}")

    try:
        # Check if it's an admin code
        admin = Admin.query.filter_by(username=kit_id).first()
        if admin and admin.is_active:
            session['admin_id'] = admin.id
            logging.debug(f"Admin login successful for: {kit_id}")
            return jsonify({"valid": True, "is_admin": True})

        # Check if kit code exists and is active
        kit_code = KitCode.query.filter_by(code=kit_id, is_active=True).first()
        logging.debug(f"Kit code found: {kit_code is not None}")

        if not kit_code:
            logging.debug(f"Kit code {kit_id} not found or inactive")
            return jsonify({"valid": False, "error": "Invalid or inactive kit code"})

        # Check if user exists or create new one
        user = AnonymousUser.query.filter_by(kit_id=kit_id).first()
        logging.debug(f"User found: {user is not None}")

        if not user:
            # Create new anonymous user
            user = AnonymousUser(kit_id=kit_id)
            db.session.add(user)
            db.session.commit()
            logging.debug(f"Created new anonymous user for kit ID: {kit_id}")

        # Generate username
        username = f"User_{kit_id[-4:].upper()}"
        if not user.name:
            user.name = username
            db.session.commit()
            logging.debug(f"Updated username for kit ID {kit_id}: {username}")

        # Store in session
        session['kit_id'] = kit_id
        session['username'] = username

        # Check tracking status
        today = datetime.now().date()
        entry = TrackingEntry.query.filter_by(kit_id=kit_id, date=today).first()
        last_entry = None if entry else TrackingEntry.query.filter_by(kit_id=kit_id).order_by(TrackingEntry.date.desc()).first()

        response_data = {
            "valid": True,
            "is_admin": False,
            "username": username,
            "has_tracked": entry is not None,
            "has_previous_entries": last_entry is not None,
            "last_entry_date": last_entry.date.strftime('%Y-%m-%d') if last_entry else None,
            "show_username_warning": True
        }
        logging.debug(f"Validation successful. Response data: {response_data}")
        return jsonify(response_data)

    except Exception as e:
        logging.error(f"Error during kit validation: {str(e)}")
        return jsonify({"valid": False, "error": "Internal server error"}), 500

@app.route('/insights/<kit_id>')
def get_insights(kit_id):
    from models import TrackingEntry, CommunityStats

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
            for meal_type, categories in meals.items():
                if categories:
                    meal_foods = []
                    for category, items in categories.items():
                        if items:
                            # Handle both dictionary and list type items
                            if isinstance(items, dict):
                                meal_foods.extend(items.keys())
                            elif isinstance(items, list):
                                meal_foods.extend(items)
                    if meal_foods:
                        meal_analysis.append(f"{meal_type.title()}: {', '.join(meal_foods)}")

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


@app.route('/save-meal', methods=['POST'])
def save_meal():
    data = request.json
    kit_id = data.get('kitId')
    meal_type = data.get('type')
    foods = data.get('foods', {})

    try:
        entry = TrackingEntry.query.filter_by(
            kit_id=kit_id,
            date=datetime.now().date()
        ).first()

        if not entry:
            entry = TrackingEntry(
                kit_id=kit_id,
                date=datetime.now().date(),
                meals={}
            )
            db.session.add(entry)

        # Update only the specific meal
        if not entry.meals:
            entry.meals = {}
        entry.meals[meal_type] = foods

        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        logging.error(f"Error saving meal data: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/save-stool', methods=['POST'])
def save_stool():
    data = request.json
    kit_id = data.get('kitId')

    try:
        entry = TrackingEntry.query.filter_by(
            kit_id=kit_id,
            date=datetime.now().date()
        ).first()

        if not entry:
            entry = TrackingEntry(
                kit_id=kit_id,
                date=datetime.now().date()
            )
            db.session.add(entry)

        entry.stool_type = data.get('type')
        entry.stool_details = {
            'relief': data.get('relief'),
            'smell': data.get('smell')
        }

        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        logging.error(f"Error saving stool data: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/save-mood', methods=['POST'])
def save_mood():
    data = request.json
    kit_id = data.get('kitId')
    mood_data = data.get('mood', {})

    try:
        entry = TrackingEntry.query.filter_by(
            kit_id=kit_id,
            date=datetime.now().date()
        ).first()

        if not entry:
            entry = TrackingEntry(
                kit_id=kit_id,
                date=datetime.now().date()
            )
            db.session.add(entry)

        # Calculate overall mood average
        mood_values = [
            mood_data.get('morning_mood', 0),
            mood_data.get('meal_mood', 0),
            mood_data.get('energy_level', 0),
            mood_data.get('evening_mood', 0),
            mood_data.get('overall_mood', 0)
        ]
        non_zero_values = [v for v in mood_values if v != 0]
        entry.mood = sum(non_zero_values) / len(non_zero_values) if non_zero_values else 0
        entry.mood_details = mood_data

        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        logging.error(f"Error saving mood data: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/save-tracking', methods=['POST'])
def save_tracking():
    #This function is now redundant and can be removed.  The new endpoints handle the individual data points.
    return jsonify({"success": False, "error": "This endpoint is no longer in use."}), 405


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        admin = Admin.query.filter_by(username=username).first()

        if admin and check_password_hash(admin.password_hash, password):
            session['admin_id'] = admin.id
            flash('Login successful!', 'success')
            return redirect(url_for('admin_dashboard'))

        flash('Invalid credentials', 'error')
        return redirect(url_for('admin_login'))

    return render_template('admin/login.html')

@app.route('/admin/logout')
@admin_required
def admin_logout():
    session.pop('admin_id', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('admin_login'))

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    kit_codes = KitCode.query.order_by(KitCode.created_at.desc()).all()
    return render_template('admin/dashboard.html', kit_codes=kit_codes)

@app.route('/admin/import-kit-codes', methods=['POST'])
@admin_required
def import_kit_codes():
    batch_name = request.form.get('batch_name')
    codes = request.form.get('codes').strip().split('\n')
    menu_data = request.form.get('menu_data')

    admin_id = session.get('admin_id')

    for code in codes:
        code = code.strip()
        if code:
            kit_code = KitCode(
                code=code,
                batch_name=batch_name,
                menu_data=menu_data,
                created_by=admin_id
            )
            db.session.add(kit_code)

    db.session.commit()
    flash(f'Successfully imported {len(codes)} kit codes.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/generate-kit-codes', methods=['POST'])
@admin_required
def generate_kit_codes():
    batch_name = request.form.get('batch_name')
    quantity = int(request.form.get('quantity', 10))
    menu_data = request.form.get('menu_data')

    admin_id = session.get('admin_id')

    for _ in range(quantity):
        code = str(uuid.uuid4())
        kit_code = KitCode(
            code=code,
            batch_name=batch_name,
            menu_data=menu_data,
            created_by=admin_id
        )
        db.session.add(kit_code)

    db.session.commit()
    flash(f'Successfully generated {quantity} new kit codes.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/toggle-kit-code/<int:code_id>', methods=['POST'])
@admin_required
def toggle_kit_code(code_id):
    kit_code = KitCode.query.get_or_404(code_id)
    kit_code.is_active = not kit_code.is_active
    db.session.commit()

    status = 'activated' if kit_code.is_active else 'deactivated'
    flash(f'Kit code {kit_code.code} has been {status}.', 'success')
    return redirect(url_for('admin_dashboard'))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)