from app import db
import uuid
from datetime import datetime

class AnonymousUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    kit_id = db.Column(db.String(36), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    @staticmethod
    def generate_kit_id():
        return str(uuid.uuid4())

class TrackingEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    kit_id = db.Column(db.String(36), nullable=False)
    date = db.Column(db.DateTime, server_default=db.func.now())
    meals = db.Column(db.JSON)
    stool_type = db.Column(db.String(10))
    mood = db.Column(db.Integer)
    shared_with_community = db.Column(db.Boolean, default=True)

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