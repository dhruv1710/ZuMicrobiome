from app import db
import uuid

class AnonymousUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    kit_id = db.Column(db.String(36), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    @staticmethod
    def generate_kit_id():
        return str(uuid.uuid4())
