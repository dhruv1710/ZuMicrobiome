from database import db
import uuid
from datetime import datetime, timedelta

class AnonymousUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    kit_id = db.Column(db.String(36), unique=True, nullable=False)
    name = db.Column(db.String(100))  # This will store the generated username
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

class KitCode(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(36), unique=True, nullable=False)
    batch_name = db.Column(db.String(100), nullable=False)
    menu_data = db.Column(db.JSON)
    created_by = db.Column(db.Integer, db.ForeignKey('admin.id'), nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    is_active = db.Column(db.Boolean, default=True)

class TrackingEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    kit_id = db.Column(db.String(36), nullable=False)
    date = db.Column(db.DateTime, server_default=db.func.now())
    meals = db.Column(db.JSON)
    stool_type = db.Column(db.String(10))
    mood = db.Column(db.Integer)
    mood_details = db.Column(db.JSON)  # Added mood_details column
    shared_with_community = db.Column(db.Boolean, default=True)
    # New streak-related columns
    current_streak = db.Column(db.Integer, default=0)
    best_streak = db.Column(db.Integer, default=0)
    last_tracked_date = db.Column(db.DateTime)

    def update_streak(self):
        """Update the streak count based on tracking consistency"""
        today = datetime.now().date()

        # If this is the first entry
        if not self.last_tracked_date:
            self.current_streak = 1
            self.best_streak = 1
            self.last_tracked_date = today
            return

        last_date = self.last_tracked_date.date()
        days_diff = (today - last_date).days

        # If tracked today already, don't update streak
        if days_diff == 0:
            return

        # If tracked yesterday, increment streak
        if days_diff == 1:
            self.current_streak += 1
            if self.current_streak > self.best_streak:
                self.best_streak = self.current_streak
        # If missed a day, reset streak
        else:
            self.current_streak = 1

        self.last_tracked_date = today

    @classmethod
    def get_user_streaks(cls, kit_id):
        """Get streak information for a user"""
        latest_entry = cls.query.filter_by(kit_id=kit_id).order_by(cls.date.desc()).first()
        if not latest_entry:
            return {
                'current_streak': 0,
                'best_streak': 0,
                'achievement_unlocked': False
            }

        # Check if new achievement unlocked (streak milestones)
        achievement_unlocked = False
        if latest_entry.current_streak in [7, 30, 100]:  # Milestone days
            achievement_unlocked = True

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