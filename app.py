import os
from flask import Flask, render_template, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
import logging
from datetime import datetime, timedelta

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
    # Simple validation - check if kit ID exists
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
    from models import TrackingEntry

    # Get today's date range
    today = datetime.now().date()
    tomorrow = today + timedelta(days=1)

    # Fetch today's entries
    entries = TrackingEntry.query.filter(
        TrackingEntry.kit_id == kit_id,
        TrackingEntry.date >= today,
        TrackingEntry.date < tomorrow
    ).all()

    if not entries:
        return render_template('insights.html', has_data=False)

    # Analyze the entries
    insights = {
        'mood_summary': None,
        'stool_health': None,
        'meal_patterns': None
    }

    # Get the latest entry
    latest_entry = entries[-1]

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

    return render_template('insights.html', insights=insights, has_data=True)

@app.route('/save-tracking', methods=['POST'])
def save_tracking():
    from models import TrackingEntry
    data = request.json
    entry = TrackingEntry(
        kit_id=data['kitId'],
        meals=data['meals'],
        stool_type=data.get('stool', {}).get('type'),
        mood=data['mood']
    )
    db.session.add(entry)
    db.session.commit()
    return jsonify({"success": True})

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