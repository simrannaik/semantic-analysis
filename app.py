from flask import Flask, render_template, request, jsonify
import tweepy
from textblob import TextBlob
import sqlite3
import json
from config import Config
import time
from datetime import datetime, timedelta

app = Flask(__name__)
app.config.from_object(Config)

# Simple rate limiting
last_request_time = None
MIN_TIME_BETWEEN_REQUESTS = 5  # seconds

def init_db():
    conn = sqlite3.connect(app.config['SQLITE_DB_PATH'])
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS searches
        (id INTEGER PRIMARY KEY AUTOINCREMENT,
         query TEXT NOT NULL,
         results TEXT NOT NULL,
         timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)
    ''')
    # Add table for rate limiting
    c.execute('''
        CREATE TABLE IF NOT EXISTS api_requests
        (id INTEGER PRIMARY KEY AUTOINCREMENT,
         timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)
    ''')
    conn.commit()
    conn.close()

def can_make_request():
    """Check if we can make a new request based on our rate limits"""
    conn = sqlite3.connect(app.config['SQLITE_DB_PATH'])
    c = conn.cursor()
    
    # Delete old records (older than 15 minutes)
    c.execute('''
        DELETE FROM api_requests 
        WHERE timestamp < datetime('now', '-15 minutes')
    ''')
    
    # Count recent requests
    c.execute('''
        SELECT COUNT(*) FROM api_requests 
        WHERE timestamp > datetime('now', '-15 minutes')
    ''')
    count = c.fetchone()[0]
    
    # Check last request time
    global last_request_time
    current_time = time.time()
    
    if last_request_time is not None:
        time_since_last_request = current_time - last_request_time
        if time_since_last_request < MIN_TIME_BETWEEN_REQUESTS:
            return False
    
    # Twitter's basic tier allows roughly 180 requests per 15 minutes
    # We'll be more conservative and limit to 150
    if count >= 150:
        return False
        
    # Log this request
    c.execute('INSERT INTO api_requests DEFAULT VALUES')
    conn.commit()
    conn.close()
    
    last_request_time = current_time
    return True

def get_twitter_client():
    client = tweepy.Client(bearer_token=app.config['TWITTER_BEARER_TOKEN'])
    return client

def analyze_sentiment(text):
    analysis = TextBlob(text)
    if analysis.sentiment.polarity > 0:
        return 'positive'
    elif analysis.sentiment.polarity < 0:
        return 'negative'
    return 'neutral'

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    if not can_make_request():
        return jsonify({
            'error': 'Rate limit exceeded. Please wait a few minutes before trying again.'
        }), 429

    query = request.form.get('query')
    if not query:
        return jsonify({'error': 'No query provided'}), 400

    try:
        client = get_twitter_client()
        tweets = client.search_recent_tweets(
            query=query,
            max_results=10,
            tweet_fields=['created_at']
        )
        
        if not tweets.data:
            return jsonify({
                'success': True,
                'results': [],
                'stats': {'positive': 0, 'negative': 0, 'neutral': 0, 'total': 0}
            })

        results = []
        for tweet in tweets.data:
            sentiment = analyze_sentiment(tweet.text)
            results.append({
                'text': tweet.text,
                'sentiment': sentiment,
                'created_at': tweet.created_at.strftime('%Y-%m-%d %H:%M:%S')
            })

        # Save to database
        conn = sqlite3.connect(app.config['SQLITE_DB_PATH'])
        c = conn.cursor()
        c.execute('INSERT INTO searches (query, results) VALUES (?, ?)',
                 (query, json.dumps(results)))
        conn.commit()
        conn.close()

        sentiments = [r['sentiment'] for r in results]
        stats = {
            'positive': sentiments.count('positive'),
            'negative': sentiments.count('negative'),
            'neutral': sentiments.count('neutral'),
            'total': len(results)
        }

        return jsonify({
            'success': True,
            'results': results,
            'stats': stats
        })

    except tweepy.TooManyRequests:
        return jsonify({
            'error': 'Twitter API rate limit exceeded. Please try again later.'
        }), 429
    except tweepy.TwitterServerError:
        return jsonify({
            'error': 'Twitter service is currently unavailable. Please try again later.'
        }), 503
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    init_db()
    app.run(debug=True)