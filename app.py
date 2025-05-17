import os
import logging
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix
import threading
import time
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()


# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Database setup
class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

# Flask app setup
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "whatsapp-news-bot-secret")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Database configuration
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///newsbot.db")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Initialize the app with the database extension
db.init_app(app)

# Import models and create tables
with app.app_context():
    from models import NewsConfig, NewsLog
    db.create_all()

# Import news bot functionality
from news_bot import fetch_news, send_whatsapp_message, format_news_message

# Global variable to track if the bot is running
bot_thread = None
bot_running = False

def news_bot_thread():
    """Thread function to run the news bot periodically"""
    global bot_running
    
    with app.app_context():
        while bot_running:
            try:
                # Get the active configuration
                config = NewsConfig.query.filter_by(active=True).first()
                
                if config:
                    logger.info(f"Running news bot with config: {config.topic}")
                    # Fetch news with improved error handling
                    articles, error_message = fetch_news(
                        api_key=os.environ.get("NEWSDATA_API_KEY", ""),
                        topic=config.topic,
                        country=config.country,
                        language=config.language
                    )
                    
                    # Format the message with articles or error information
                    message = format_news_message(articles, error_message, config.num_articles)
                    
                    # Log message status based on whether we found articles
                    status = "success" if articles else "warning"
                    
                    # If we have an API key error, mark it as an error
                    if error_message and "API key" in error_message:
                        status = "error"
                        logger.error(f"API key error: {error_message}")
                    elif not articles:
                        logger.warning(f"No news found: {error_message}")
                    else:
                        logger.info(f"Found {len(articles)} news articles")
                    
                    # Send the message
                    send_success = send_whatsapp_message(
                        message=message,
                        to_number=config.whatsapp_number,
                        twilio_sid=os.environ.get("TWILIO_ACCOUNT_SID", ""),
                        twilio_token=os.environ.get("TWILIO_AUTH_TOKEN", ""),
                        from_number=os.environ.get("TWILIO_WHATSAPP_NUMBER", "")
                    )
                    
                    # Update status if message sending failed
                    if not send_success:
                        status = "error"
                        logger.error("Failed to send WhatsApp message")
                    
                    # Log the message result
                    log_entry = NewsLog(
                        config_id=config.id,
                        timestamp=datetime.now(),
                        message=message[:500],  # Save first 500 chars
                        status=status
                    )
                    db.session.add(log_entry)
                    db.session.commit()
                    
                    # Log final status
                    if status == "success":
                        logger.info("News message sent successfully")
                    elif status == "warning":
                        logger.warning("News message sent with warnings")
                    else:
                        logger.error("Failed to process or send news")
                
                # Sleep for the interval period (convert minutes to seconds)
                interval_seconds = config.interval * 60 if config else 3600
                logger.info(f"Sleeping for {interval_seconds} seconds")
                
                # Sleep in smaller chunks to allow for graceful shutdown
                for _ in range(interval_seconds // 10):
                    if not bot_running:
                        break
                    time.sleep(10)
                
                if interval_seconds % 10 > 0 and bot_running:
                    time.sleep(interval_seconds % 10)
                
            except Exception as e:
                logger.error(f"Error in news bot thread: {str(e)}")
                # Log the error
                try:
                    config = NewsConfig.query.filter_by(active=True).first()
                    if config:
                        log_entry = NewsLog(
                            config_id=config.id,
                            timestamp=datetime.now(),
                            message=f"Error: {str(e)}",
                            status="error"
                        )
                        db.session.add(log_entry)
                        db.session.commit()
                except Exception as log_error:
                    logger.error(f"Error logging error: {str(log_error)}")
                
                # Sleep before retrying
                time.sleep(60)

@app.route('/')
def index():
    """Homepage route showing the status of the bot and latest logs"""
    global bot_running
    
    config = NewsConfig.query.filter_by(active=True).first()
    logs = NewsLog.query.order_by(NewsLog.timestamp.desc()).limit(10).all()
    
    return render_template('index.html', 
                          config=config, 
                          logs=logs, 
                          bot_running=bot_running)

@app.route('/configure', methods=['GET', 'POST'])
def configure():
    """Configure the news bot settings"""
    if request.method == 'POST':
        try:
            # Get form data
            topic = request.form.get('topic', 'world news')
            whatsapp_number = request.form.get('whatsapp_number', '')
            country = request.form.get('country', 'us')
            language = request.form.get('language', 'en')
            interval = int(request.form.get('interval', '60'))
            num_articles = int(request.form.get('num_articles', '3'))
            
            # Basic validation
            if not whatsapp_number or not whatsapp_number.startswith('whatsapp:+'):
                flash('WhatsApp number must start with "whatsapp:+". Example: whatsapp:+1234567890', 'danger')
                return redirect(url_for('configure'))
            
            if interval < 15:
                flash('Interval must be at least 15 minutes', 'warning')
                interval = 15
            
            # Check if there's an active config
            existing_config = NewsConfig.query.filter_by(active=True).first()
            
            if existing_config:
                # Update existing config
                existing_config.topic = topic
                existing_config.whatsapp_number = whatsapp_number
                existing_config.country = country
                existing_config.language = language
                existing_config.interval = interval
                existing_config.num_articles = num_articles
                db.session.commit()
                flash('Configuration updated successfully', 'success')
            else:
                # Create new config
                new_config = NewsConfig(
                    topic=topic,
                    whatsapp_number=whatsapp_number,
                    country=country,
                    language=language,
                    interval=interval,
                    num_articles=num_articles,
                    active=True
                )
                db.session.add(new_config)
                db.session.commit()
                flash('Configuration created successfully', 'success')
            
            return redirect(url_for('index'))
        
        except Exception as e:
            logger.error(f"Error saving configuration: {str(e)}")
            flash(f'Error saving configuration: {str(e)}', 'danger')
    
    # GET request or form validation failed
    config = NewsConfig.query.filter_by(active=True).first()
    return render_template('configure.html', config=config)

@app.route('/start_bot')
def start_bot():
    """Start the news bot thread"""
    global bot_thread, bot_running
    
    if not bot_running:
        # Check if there's an active configuration
        config = NewsConfig.query.filter_by(active=True).first()
        if not config:
            flash('Please configure the bot first', 'warning')
            return redirect(url_for('configure'))
        
        # Check for required environment variables
        if not os.environ.get("NEWSDATA_API_KEY"):
            flash('NEWSDATA_API_KEY environment variable not set', 'danger')
            return redirect(url_for('index'))
        
        if not os.environ.get("TWILIO_ACCOUNT_SID") or \
           not os.environ.get("TWILIO_AUTH_TOKEN") or \
           not os.environ.get("TWILIO_WHATSAPP_NUMBER"):
            flash('Twilio environment variables not set', 'danger')
            return redirect(url_for('index'))
        
        # Start the bot thread
        bot_running = True
        bot_thread = threading.Thread(target=news_bot_thread)
        bot_thread.daemon = True
        bot_thread.start()
        
        flash('News bot started', 'success')
    else:
        flash('News bot is already running', 'info')
    
    return redirect(url_for('index'))

@app.route('/stop_bot')
def stop_bot():
    """Stop the news bot thread"""
    global bot_running
    
    if bot_running:
        bot_running = False
        flash('News bot stopping. It may take a few seconds to complete.', 'success')
    else:
        flash('News bot is not running', 'info')
    
    return redirect(url_for('index'))

@app.route('/test_message')
def test_message():
    """Send a test message to verify the configuration"""
    try:
        config = NewsConfig.query.filter_by(active=True).first()
        
        if not config:
            flash('Please configure the bot first', 'warning')
            return redirect(url_for('configure'))
        
        # Fetch a single news article for testing
        articles, error_message = fetch_news(
            api_key=os.environ.get("NEWSDATA_API_KEY", ""),
            topic=config.topic,
            country=config.country,
            language=config.language
        )
        
        # Format message with test header
        message = format_news_message(articles, error_message, 1)
        message = "🧪 TEST MESSAGE 🧪\n\n" + message
        
        # Send the message
        send_success = send_whatsapp_message(
            message=message,
            to_number=config.whatsapp_number,
            twilio_sid=os.environ.get("TWILIO_ACCOUNT_SID", ""),
            twilio_token=os.environ.get("TWILIO_AUTH_TOKEN", ""),
            from_number=os.environ.get("TWILIO_WHATSAPP_NUMBER", "")
        )
        
        # Log the message
        log_entry = NewsLog(
            config_id=config.id,
            timestamp=datetime.now(),
            message=message[:500],  # Save first 500 chars
            status="test"
        )
        db.session.add(log_entry)
        db.session.commit()
        
        if send_success:
            flash('Test message sent successfully', 'success')
        else:
            flash('Error sending test message via Twilio', 'warning')
    
    except Exception as e:
        logger.error(f"Error sending test message: {str(e)}")
        flash(f'Error sending test message: {str(e)}', 'danger')
    
    return redirect(url_for('index'))

@app.route('/clear_logs')
def clear_logs():
    """Clear all logs from the database"""
    try:
        NewsLog.query.delete()
        db.session.commit()
        flash('Logs cleared successfully', 'success')
    except Exception as e:
        logger.error(f"Error clearing logs: {str(e)}")
        flash(f'Error clearing logs: {str(e)}', 'danger')
    
    return redirect(url_for('index'))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
