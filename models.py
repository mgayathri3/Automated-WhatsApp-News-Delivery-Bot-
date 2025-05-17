from app import db
from datetime import datetime

class NewsConfig(db.Model):
    """Configuration for the WhatsApp News Bot"""
    id = db.Column(db.Integer, primary_key=True)
    topic = db.Column(db.String(100), nullable=False, default='world news')
    whatsapp_number = db.Column(db.String(50), nullable=False)  # Format: "whatsapp:+1234567890"
    country = db.Column(db.String(10), nullable=False, default='us')  # Country code (e.g., 'us', 'in')
    language = db.Column(db.String(10), nullable=False, default='en')  # Language code (e.g., 'en')
    interval = db.Column(db.Integer, nullable=False, default=60)  # Minutes between updates
    num_articles = db.Column(db.Integer, nullable=False, default=3)  # Number of articles to send
    active = db.Column(db.Boolean, nullable=False, default=True)  # Whether this config is active
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)
    
    # Relationship with logs
    logs = db.relationship('NewsLog', backref='config', lazy=True)

    def __repr__(self):
        return f'<NewsConfig {self.topic} {self.whatsapp_number}>'

class NewsLog(db.Model):
    """Log of news messages sent"""
    id = db.Column(db.Integer, primary_key=True)
    config_id = db.Column(db.Integer, db.ForeignKey('news_config.id'), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.now)
    message = db.Column(db.Text, nullable=False)  # Store the first part of the message
    status = db.Column(db.String(20), nullable=False)  # success, error, warning, test
    
    def __repr__(self):
        return f'<NewsLog {self.timestamp} {self.status}>'
