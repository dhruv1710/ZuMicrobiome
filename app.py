import os
import logging
import random
import uuid
from datetime import datetime, timedelta, time
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
    from models import Admin, AnonymousUser, KitCode, TrackingEntry
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

@app.route('/save-lifestyle', methods=['POST'])
def save_lifestyle():
    if 'kit_id' not in session:
        return jsonify({"success": False, "error": "Not logged in"}), 401

    try:
        entry = TrackingEntry.query.filter_by(
            kit_id=session['kit_id'],
            date=datetime.now().date()
        ).first()

        if not entry:
            entry = TrackingEntry(
                kit_id=session['kit_id'],
                date=datetime.now().date()
            )
            db.session.add(entry)

        # Save lifestyle data
        if entry.lifestyle_log:
            return jsonify({"success": False, "error": "Lifestyle already logged for today"}), 400

        entry.lifestyle_log = request.json
        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        logging.error(f"Error saving lifestyle data: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/dashboard')
def dashboard():
    if 'kit_id' not in session:
        return redirect(url_for('index'))

    today = datetime.now().date()
    current_time = datetime.now().time()
    reset_time = time(3, 0)  # 3 AM reset time

    # If it's before reset time, we should look at yesterday's entry
    if current_time < reset_time:
        today = today - timedelta(days=1)

    # Get today's entry
    entry = TrackingEntry.query.filter_by(
        kit_id=session['kit_id'],
        date=today
    ).first()

    # If current time is after reset time and before noon, 
    # we should allow breakfast tracking regardless of yesterday's entries
    is_new_day = current_time >= reset_time and current_time <= time(12, 0)

    # Check meal logging status
    meals = entry.meals if entry else {}

    # During new day (after reset time and before noon), only reset unlogged meals
    breakfast_logged = 'breakfast' in meals
    lunch_logged = 'lunch' in meals if not is_new_day or breakfast_logged else False
    dinner_logged = 'dinner' in meals if not is_new_day or lunch_logged else False
    stool_logged = True if entry and entry.stool_type and not is_new_day else False
    lifestyle_logged = True if entry and entry.lifestyle_log and not is_new_day else False
    mood_logged = True if entry and entry.mood and not is_new_day else False

    # Get streak information
    streak_info = TrackingEntry.get_user_streaks(session['kit_id'])
    current_streak = streak_info['current_streak']
    best_streak = streak_info['best_streak']
    achievement_unlocked = streak_info['achievement_unlocked']

    # Calculate next milestone
    milestones = [7, 30, 100]
    next_milestone = next((m for m in milestones if m > current_streak), milestones[-1])

    return render_template('dashboard.html',
                         mood_logged=mood_logged,
                         breakfast_logged=breakfast_logged,
                         lunch_logged=lunch_logged,
                         dinner_logged=dinner_logged,
                         stool_logged=stool_logged,
                         lifestyle_logged=lifestyle_logged,
                         current_streak=current_streak,
                         best_streak=best_streak,
                         next_milestone=next_milestone,
                         achievement_unlocked=achievement_unlocked)

@app.route('/')
def index():
    if 'kit_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/track/meal/<meal_type>')
def track_meal(meal_type):
    if 'kit_id' not in session:
        return redirect(url_for('index'))

    if meal_type not in ['breakfast', 'lunch', 'dinner']:
        return redirect(url_for('dashboard'))

    today = datetime.now().date()
    current_time = datetime.now().time()
    reset_time = time(3, 0)  # 3 AM reset time

    # If it's before reset time, we should look at yesterday's entry
    if current_time < reset_time:
        today = today - timedelta(days=1)

    # Get today's entry
    entry = TrackingEntry.query.filter_by(
        kit_id=session['kit_id'],
        date=today
    ).first()

    # If it's after reset time but before noon, treat as new day
    is_new_day = current_time >= reset_time and current_time <= time(12, 0)

    # During new day (after reset time and before noon), allow breakfast
    if is_new_day and meal_type == 'breakfast':
        return render_template('track_meal.html', meal_type=meal_type)

    meals = entry.meals if entry else {}

    # Check meal sequence only if it's not a new day
    if not is_new_day:
        if meal_type == 'lunch' and 'breakfast' not in meals:
            flash('Please log breakfast first', 'error')
            return redirect(url_for('dashboard'))
        elif meal_type == 'dinner' and 'lunch' not in meals:
            flash('Please log lunch first', 'error')
            return redirect(url_for('dashboard'))

        # Check if meal already logged
        if meal_type in meals:
            flash(f'{meal_type.capitalize()} already logged for today', 'error')
            return redirect(url_for('dashboard'))

    return render_template('track_meal.html', meal_type=meal_type)

@app.route('/track/stool')
def track_stool():
    if 'kit_id' not in session:
        return redirect(url_for('index'))

    today = datetime.now().date()
    current_time = datetime.now().time()
    reset_time = time(3, 0)  # 3 AM reset time

    # If it's before reset time, we should look at yesterday's entry
    if current_time < reset_time:
        today = today - timedelta(days=1)

    # Get today's entry
    entry = TrackingEntry.query.filter_by(
        kit_id=session['kit_id'],
        date=today
    ).first()

    # If it's after reset time but before noon, treat as new day
    is_new_day = current_time >= reset_time and current_time <= time(12, 0)

    # During new day, don't require breakfast
    if not is_new_day and (not entry or 'breakfast' not in entry.meals):
        flash('Please log breakfast first', 'error')
        return redirect(url_for('dashboard'))

    if entry and entry.stool_type and not is_new_day:
        flash('Stool data already logged for today', 'error')
        return redirect(url_for('dashboard'))

    return render_template('track_stool.html')

@app.route('/track/mood')
def track_mood():
    if 'kit_id' not in session:
        return redirect(url_for('index'))
    return render_template('track_mood.html')


@app.route('/get-menu-data')
def get_menu_data():
    kit_id = request.args.get('kitId')
    meal_type = request.args.get('meal_type')

    if not kit_id:
        logging.debug("No kit ID provided in get-menu-data request")
        return jsonify({"error": "No kit ID provided"}), 400

    if not meal_type:
        logging.debug("No meal type provided in get-menu-data request")
        return jsonify({"error": "No meal type provided"}), 400

    logging.debug(f"Fetching menu data for kit ID: {kit_id}")
    kit_code = KitCode.query.filter_by(code=kit_id, is_active=True).first()

    # If no menu data found, return default menu data
    default_menu_data = {
        "breakfast": {
            "Beverages": {
                "Coffee": {},
                "Tea": {},
                "Water": {}
            },
            "Cereals": {
                "Oatmeal": {},
                "Granola": {},
                "Muesli": {}
            },
            "Protein": {
                "Eggs": {},
                "Greek Yogurt": {},
                "Tofu Scramble": {}
            }
        }
    }

    if kit_code and kit_code.menu_data:
        logging.debug(f"Found menu data for kit ID {kit_id}: {kit_code.menu_data}")
        return jsonify({"menu_data": kit_code.menu_data})

    logging.debug(f"No menu data found for kit ID: {kit_id}, returning default menu")
    return jsonify({"menu_data": default_menu_data})

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

@app.route('/save-meal', methods=['POST'])
def save_meal():
    data = request.json
    kit_id = data.get('kitId')
    meal_type = data.get('type')
    foods = data.get('foods', {})

    try:
        today = datetime.now().date()
        current_time = datetime.now().time()
        reset_time = time(3, 0)  # 3 AM reset time

        # If it's before reset time, we should look at yesterday's entry
        if current_time < reset_time:
            today = today - timedelta(days=1)

        # Check if this is breakfast during new day period
        is_new_day = current_time >= reset_time and current_time <= time(12, 0)

        entry = TrackingEntry.query.filter_by(
            kit_id=kit_id,
            date=today
        ).first()

        if not entry:
            entry = TrackingEntry(
                kit_id=kit_id,
                date=today,
                meals={}
            )
            db.session.add(entry)

        # Initialize meals if None
        if not entry.meals:
            entry.meals = {}

        # For breakfast during new day, always allow and save
        if meal_type == 'breakfast' and is_new_day:
            entry.meals[meal_type] = foods
        # For other meals, check sequence
        elif meal_type == 'lunch' and 'breakfast' not in entry.meals:
            return jsonify({"success": False, "error": "Please log breakfast first"}), 400
        elif meal_type == 'dinner' and 'lunch' not in entry.meals:
            return jsonify({"success": False, "error": "Please log lunch first"}), 400
        else:
            entry.meals[meal_type] = foods

        # Update streak
        entry.update_streak()

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

# This remains for backward compatibility, but should be deprecated eventually
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

@app.route('/save-tracking', methods=['POST'])
def save_tracking():
    #This function is now redundant and can be removed.  The new endpoints handle the individual data points.
    return jsonify({"success": False, "error": "This endpoint is no longer in use."}), 405

@app.route('/insights')
def insights():
    if 'kit_id' not in session:
        return redirect(url_for('index'))

    # Get date range (last 7 days)
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=7)

    # Fetch entries for the last 7 days
    entries = TrackingEntry.query.filter(
        TrackingEntry.kit_id == session['kit_id'],
        TrackingEntry.date >= start_date,
        TrackingEntry.date <= end_date
    ).order_by(TrackingEntry.date).all()

    if not entries:
        return render_template('insights.html', has_data=False)

    # Prepare trend data
    trend_data = {
        'dates': [],
        'moods': [],
        'stool_types': [],
        'breakfast_counts': [],
        'lunch_counts': [],
        'dinner_counts': []
    }

    for entry in entries:
        date_str = entry.date.strftime('%Y-%m-%d')
        trend_data['dates'].append(date_str)
        trend_data['moods'].append(entry.mood if entry.mood else 0)
        trend_data['stool_types'].append(int(entry.stool_type) if entry.stool_type else 0)

        # Count items in each meal
        meals = entry.meals or {}
        breakfast_items = sum(len(items) for category in meals.get('breakfast', {}).values() for items in (category if isinstance(category, list) else [category.keys()]))
        lunch_items = sum(len(items) for category in meals.get('lunch', {}).values() for items in (category if isinstance(category, list) else [category.keys()]))
        dinner_items = sum(len(items) for category in meals.get('dinner', {}).values() for items in (category if isinstance(category, list) else [category.keys()]))

        trend_data['breakfast_counts'].append(breakfast_items)
        trend_data['lunch_counts'].append(lunch_items)
        trend_data['dinner_counts'].append(dinner_items)

    return render_template('insights.html', 
                         has_data=True,
                         trend_data=trend_data)

@app.route('/test-reset')
def test_reset():
    if 'kit_id' not in session:
        return redirect(url_for('index'))

    current_time = datetime.now().time()
    reset_time = time(3, 0)
    current_date = datetime.now().date()

    # If before reset time, use previous day
    if current_time < reset_time:
        current_date = current_date - timedelta(days=1)

    # Check if it's a new day (after reset, before noon)
    is_new_day = current_time >= reset_time and current_time <= time(12, 0)

    # Get today's entry
    entry = TrackingEntry.query.filter_by(
        kit_id=session['kit_id'],
        date=current_date
    ).first()

    # Get tracking status
    meals = entry.meals if entry else {}
    tracking_status = {
        'current_time': current_time.strftime('%H:%M:%S'),
        'reset_time': reset_time.strftime('%H:%M:%S'),
        'current_date': current_date.strftime('%Y-%m-%d'),
        'is_new_day': is_new_day,
        'breakfast_logged': 'breakfast' in meals if not is_new_day else False,
        'lunch_logged': 'lunch' in meals if not is_new_day else False,
        'dinner_logged': 'dinner' in meals if not is_new_day else False,
        'stool_logged': bool(entry and entry.stool_type and not is_new_day),
        'mood_logged': bool(entry and entry.mood and not is_new_day),
        'lifestyle_logged': bool(entry and entry.lifestyle_log and not is_new_day)
    }

    return jsonify(tracking_status)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)