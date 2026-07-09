from models import db
from datetime import datetime

class Syllabus(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    filename = db.Column(db.String(200))
    file_path = db.Column(db.String(500))
    topics = db.Column(db.Text)  # Store topics as JSON string
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __init__(self, user_id, filename, file_path, topics=None):
        self.user_id = user_id
        self.filename = filename
        self.file_path = file_path
        self.topics = topics
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'filename': self.filename,
            'topics': self.topics,
            'uploaded_at': self.uploaded_at.isoformat() if self.uploaded_at else None
        }