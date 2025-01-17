import os
from flask import Flask, render_template, jsonify, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
import logging
from datetime import datetime, timedelta
import random

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# List of capital cities for username generation
CAPITAL_CITIES = [
    "Tokyo", "Paris", "London", "Berlin", "Rome", "Madrid", "Moscow", "Cairo",
    "Bangkok", "Seoul", "Beijing", "Delhi", "Sydney", "Toronto", "Lima",
    "Vienna", "Prague", "Athens", "Oslo", "Dublin", "Amsterdam", "Brussels",
    "Copenhagen", "Helsinki", "Stockholm", "Warsaw", "Budapest", "Lisbon"
]

def generate_microbial_username():
    """Generate a unique username using a capital city name"""
    return random.choice(CAPITAL_CITIES)

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

@app.route('/')
def index():
    if 'kit_id' in session:
        # Check if user has tracked today
        from models import TrackingEntry
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

    from models import KitCode
    logging.debug(f"Fetching menu data for kit ID: {kit_id}")
    kit_code = KitCode.query.filter_by(code=kit_id, is_active=True).first()

    if kit_code and kit_code.menu_data:
        logging.debug(f"Found menu data for kit ID {kit_id}: {kit_code.menu_data}")
        return jsonify({"menu_data": kit_code.menu_data})

    logging.debug(f"No menu data found for kit ID: {kit_id}")
    return jsonify({"error": "Invalid kit ID or no menu data available"}), 404

@app.route('/validate-kit/<kit_id>', methods=['POST'])
def validate_kit(kit_id):
    from models import AnonymousUser, Admin, KitCode, TrackingEntry
    logging.debug(f"Validating kit ID: {kit_id}")

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
        # Generate or get existing username
        username = user.name or generate_microbial_username()
        if not user.name:
            user.name = username
            db.session.commit()

        # Store in session
        session['kit_id'] = kit_id
        session['username'] = username
        logging.debug(f"Generated username for kit ID {kit_id}: {username}")

        # Check if user has tracked today
        today = datetime.now().date()
        entry = TrackingEntry.query.filter_by(kit_id=kit_id, date=today).first()

        # If no entry for today, check if there's any previous entry
        last_entry = None
        if not entry:
            last_entry = TrackingEntry.query.filter_by(kit_id=kit_id).order_by(TrackingEntry.date.desc()).first()

        return jsonify({
            "valid": is_valid,
            "is_admin": False,
            "username": username,
            "has_tracked": entry is not None,
            "has_previous_entries": last_entry is not None,
            "last_entry_date": last_entry.date.strftime('%Y-%m-%d') if last_entry else None
        })

    return jsonify({"valid": is_valid, "is_admin": False})

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
    from models import TrackingEntry, CommunityStats
    data = request.json

    # Create new tracking entry
    entry = TrackingEntry(
        kit_id=data['kitId'],
        meals=data['meals'],
        stool_type=data.get('stool', {}).get('type'),
        mood=data['mood'],
        date=datetime.now().date()
    )
    db.session.add(entry)

    # Update community stats
    today = datetime.now().date()
    stats = CommunityStats.query.filter_by(date=today).first()

    if not stats:
        stats = CommunityStats(date=today)
        db.session.add(stats)

    # Calculate new averages
    today_entries = TrackingEntry.query.filter(
        TrackingEntry.date == today
    ).all()

    if today_entries:
        # Calculate mood average
        total_mood = sum(entry.mood for entry in today_entries if entry.mood)
        stats.avg_mood = total_mood / len(today_entries)
        stats.total_participants = len(today_entries)

    db.session.commit()
    return jsonify({"success": True})

# Initialize the database
with app.app_context():
    db.create_all()