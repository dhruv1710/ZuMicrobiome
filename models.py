from database import db
import uuid
from datetime import datetime, timedelta, time

class AnonymousUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    kit_id = db.Column(db.String(36), unique=True, nullable=False)
    name = db.Column(db.String(100))  
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    @staticmethod
    def generate_kit_id():
        return str(uuid.uuid4())

class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

class DailyMenu(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    menu_data = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    created_by = db.Column(db.Integer, db.ForeignKey('admin.id'), nullable=False)

    @classmethod
    def get_menu_for_date(cls, date):
        return cls.query.filter_by(date=date).first()

class KitCode(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(36), unique=True, nullable=False)
    batch_name = db.Column(db.String(100), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('admin.id'), nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    is_active = db.Column(db.Boolean, default=True)

class TrackingEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    kit_id = db.Column(db.String(36), nullable=False)
    date = db.Column(db.DateTime, server_default=db.func.now())
    meals = db.Column(db.JSON)
    stool_entries = db.Column(db.JSON)
    mood = db.Column(db.Integer)
    mood_details = db.Column(db.JSON)
    shared_with_community = db.Column(db.Boolean, default=True)
    current_streak = db.Column(db.Integer, default=0)
    best_streak = db.Column(db.Integer, default=0)
    last_tracked_date = db.Column(db.DateTime)
    lifestyle_log = db.Column(db.JSON)  

    def update_streak(self):
        today = datetime.now().date()
        current_time = datetime.now().time()
        reset_time = time(3, 0)  # 3 AM reset time

        # If it's before reset time, consider it as previous day
        if current_time < reset_time:
            today = today - timedelta(days=1)

        if not self.last_tracked_date:
            self.current_streak = 1
            self.best_streak = 1
            self.last_tracked_date = today
            return

        last_date = self.last_tracked_date.date()
        days_diff = (today - last_date).days

        if days_diff == 0:
            # Same day, no streak update needed
            return
        elif days_diff == 1:
            # Consecutive day
            self.current_streak += 1
            if self.current_streak > self.best_streak:
                self.best_streak = self.current_streak
        else:
            # Streak broken
            self.current_streak = 1

        self.last_tracked_date = today

    @classmethod
    def get_user_streaks(cls, kit_id):
        # Get the current time and determine if we're before reset time
        current_time = datetime.now().time()
        reset_time = time(3, 0)

        # If before reset time, use yesterday's date for checking
        check_date = datetime.now().date()
        if current_time < reset_time:
            check_date = check_date - timedelta(days=1)

        latest_entry = cls.query.filter_by(kit_id=kit_id).order_by(cls.date.desc()).first()
        if not latest_entry:
            return {
                'current_streak': 0,
                'best_streak': 0,
                'achievement_unlocked': False
            }

        # Check if latest entry is from check_date
        if latest_entry.date.date() < check_date:
            # User hasn't tracked today yet, but might still be within the streak window
            days_missed = (check_date - latest_entry.date.date()).days
            if days_missed > 1:
                latest_entry.current_streak = 0

        achievement_unlocked = latest_entry.current_streak in [7, 30, 100]

        return {
            'current_streak': latest_entry.current_streak,
            'best_streak': latest_entry.best_streak,
            'achievement_unlocked': achievement_unlocked
        }

class CommunityStats(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    avg_mood = db.Column(db.Float)
    most_common_stool_type = db.Column(db.String(10))
    total_participants = db.Column(db.Integer)
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    @classmethod
    def get_or_create_daily(cls, date):
        stats = cls.query.filter_by(date=date).first()
        if not stats:
            stats = cls(date=date)
            db.session.add(stats)
        return stats