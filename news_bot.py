import os
import logging
import requests
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def fetch_news(api_key, topic="world news", country="us", language="en", max_retries=2):
    """
    Fetch news articles from NewsData.io API
    
    Args:
        api_key (str): NewsData.io API key
        topic (str): Topic to search for
        country (str): Country code (e.g., 'us', 'in')
        language (str): Language code (e.g., 'en')
        max_retries (int): Maximum number of retries for API call
        
    Returns:
        tuple: (articles list, error message) - articles will be None if there's an error
    """
    # Validate inputs
    if not api_key:
        return None, "Missing API key"
    
    # URL-encode the topic for proper API request
    import urllib.parse
    encoded_topic = urllib.parse.quote(topic)
    
    # Track retry attempts
    retry_count = 0
    last_error = None
    
    while retry_count <= max_retries:
        try:
            # Construct the URL
            url = (
                f"https://newsdata.io/api/1/news?apikey={api_key}"
                f"&q={encoded_topic}&country={country}&language={language}"
            )
            
            logger.debug(f"Fetching news from URL (attempt {retry_count+1})")
            
            # Make the request with timeout
            response = requests.get(url, timeout=10)
            
            # Debug the raw response
            logger.debug(f"Response status code: {response.status_code}")
            
            # Check for HTTP errors
            if response.status_code != 200:
                error_msg = f"HTTP error: {response.status_code}"
                if response.status_code == 401:
                    error_msg = "API key unauthorized. Please check your NewsData.io API key."
                elif response.status_code == 429:
                    error_msg = "Rate limit exceeded. Please try again later."
                
                logger.error(error_msg)
                return None, error_msg
            
            # Parse the JSON response
            data = response.json()
            
            # Log the response structure for debugging
            logger.debug(f"Response data structure: {list(data.keys())}")
            
            # Check if we got successful results
            if data.get("status") == "success" and data.get("results") and len(data["results"]) > 0:
                logger.info(f"Fetched {len(data['results'])} news articles")
                return data["results"], None
            else:
                # Check for specific error messages from the API
                if data.get("status") == "error":
                    error_message = "API error"
                    if isinstance(data.get("results"), dict):
                        error_message = data.get("results", {}).get("message", "Unknown API error")
                    logger.warning(f"API error: {error_message}")
                    return None, f"NewsData.io API error: {error_message}"
                elif not data.get("results") or len(data["results"]) == 0:
                    logger.warning("No news articles found for the given criteria")
                    return None, "No news articles found for the given search criteria. Try a different topic or country."
                else:
                    logger.warning(f"Unexpected API response: {data}")
                    return None, "Unexpected API response format"
                
        except requests.exceptions.RequestException as e:
            last_error = f"Request error: {str(e)}"
            logger.error(last_error)
        except ValueError as e:
            last_error = f"Invalid JSON response: {str(e)}"
            logger.error(last_error)
        except Exception as e:
            last_error = f"Unexpected error: {str(e)}"
            logger.error(last_error)
        
        # Increment retry counter
        retry_count += 1
        if retry_count <= max_retries:
            logger.info(f"Retrying API call ({retry_count}/{max_retries})...")
            import time
            time.sleep(2)  # Wait 2 seconds before retrying
    
    # If we got here, all retries failed
    return None, last_error

def format_news_message(articles, error_message=None, num_articles=3):
    """
    Format news articles into a WhatsApp message
    
    Args:
        articles (list): List of news articles
        error_message (str): Error message if news fetching failed
        num_articles (int): Number of articles to include
        
    Returns:
        str: Formatted message for WhatsApp
    """
    messages = []
    # Add a header
    messages.append("📰 *LATEST NEWS UPDATES* 📰")
    
    if not articles:
        # Handle error case with proper user feedback
        if error_message:
            messages.append(f"⚠️ *Issue fetching news*: {error_message}")
            messages.append("\n💡 *Suggestions*:")
            
            if "API key" in error_message:
                messages.append("• Please check your NewsData.io API key")
                messages.append("• Verify the API key is active and has sufficient quota")
            elif "search criteria" in error_message:
                messages.append("• Try a broader search topic (e.g., 'world' instead of specific terms)")
                messages.append("• Try different country or language settings")
                messages.append("• Check if the topic is too specific or has limited coverage")
            else:
                messages.append("• The news service might be temporarily unavailable")
                messages.append("• Try again later or check your internet connection")
        else:
            messages.append("⚠️ No news found. Please try again with different search criteria.")
            
        return "\n\n".join(messages)
    
    # Process articles if available
    # Add each article (limited to num_articles)
    for article in articles[:num_articles]:
        title = article.get("title", "No title")
        source = article.get("source_id", "Unknown")
        pub_date = article.get("pubDate", "Unknown date")
        link = article.get("link", "#")
        
        # Create a rich text message with emoji
        article_text = f"🗞️ *{title}*\n📍{source} | 🕒 {pub_date}\n🔗 {link}"
        
        # Add a description if available (limited to 100 chars)
        description = article.get("description", "")
        if description and len(description) > 0:
            # Truncate long descriptions
            if len(description) > 100:
                description = description[:97] + "..."
            article_text += f"\n\n{description}"
        
        messages.append(article_text)
    
    # Add footer with timestamp
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    messages.append(f"⏱️ Updated: {timestamp}")
    
    # Return the joined message
    return "\n\n".join(messages)

def send_whatsapp_message(message, to_number, twilio_sid, twilio_token, from_number):
    """
    Send a WhatsApp message using Twilio
    
    Args:
        message (str): Message to send
        to_number (str): Recipient WhatsApp number (format: whatsapp:+1234567890)
        twilio_sid (str): Twilio Account SID
        twilio_token (str): Twilio Auth Token
        from_number (str): Sender WhatsApp number (format: whatsapp:+1234567890)
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Initialize Twilio client
        client = Client(twilio_sid, twilio_token)
        
        # Send the message
        message_obj = client.messages.create(
            from_=from_number,
            body=message,
            to=to_number
        )
        
        logger.info(f"Message sent successfully with SID: {message_obj.sid}")
        return True
        
    except TwilioRestException as e:
        logger.error(f"Twilio error: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error sending WhatsApp message: {str(e)}")
        return False
