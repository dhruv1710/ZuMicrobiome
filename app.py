import os
from flask import Flask, render_template, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
import logging

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