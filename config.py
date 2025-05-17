import os

class Config:
    """Configuration for the WhatsApp News Bot"""
    # Twilio configuration
    TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
    TWILIO_WHATSAPP_NUMBER = os.environ.get("TWILIO_WHATSAPP_NUMBER", "")  # Format: "whatsapp:+14155238886"
    
    # NewsData.io configuration
    NEWSDATA_API_KEY = os.environ.get("NEWSDATA_API_KEY", "")
    
    # Default news configuration
    DEFAULT_TOPIC = "world news"
    DEFAULT_COUNTRY = "us"
    DEFAULT_LANGUAGE = "en"
    DEFAULT_INTERVAL = 60  # Minutes
    DEFAULT_NUM_ARTICLES = 3
    
    # Flask configuration
    SECRET_KEY = os.environ.get("SESSION_SECRET", "whatsapp-news-bot-secret")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///newsbot.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
