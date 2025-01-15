import os
from flask import Flask, render_template, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
import logging
from datetime import datetime, timedelta
from sqlalchemy import func
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
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

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/track')
def track():
    return render_template('track.html')

@app.route('/validate-kit/<kit_id>')
def validate_kit(kit_id):
    from models import AnonymousUser
    user = AnonymousUser.query.filter_by(kit_id=kit_id).first()
    return jsonify({"valid": user is not None})

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

with app.app_context():
    import models
    db.create_all()

    # Create a test kit ID if it doesn't exist
    from models import AnonymousUser
    test_kit = AnonymousUser.query.filter_by(kit_id='TEST123456').first()
    if not test_kit:
        test_kit = AnonymousUser(kit_id='TEST123456')
        db.session.add(test_kit)
        db.session.commit()
        logging.info("Created test kit ID: TEST123456")