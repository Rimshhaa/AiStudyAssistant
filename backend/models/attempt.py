from models import db

class Attempt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    topic = db.Column(db.String(200))
    score = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())