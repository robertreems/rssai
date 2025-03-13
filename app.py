from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
import feedparser
import json
from datetime import datetime
import argostranslate.package
import argostranslate.translate
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
import numpy as np
import threading
import time
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Instellingen voor vertaling (Argos Translate)
from_code = "nl"
to_code = "en"

# Download en installeer Argos Translate package
argostranslate.package.update_package_index()
available_packages = argostranslate.package.get_available_packages()
package_to_install = next(
    filter(lambda x: x.from_code == from_code and x.to_code == to_code, available_packages)
)
argostranslate.package.install_from_path(package_to_install.download())

def translate_text(text, from_code, to_code):
    """Voer een vertaling uit met Argos Translate."""
    try:
        return argostranslate.translate.translate(text, from_code, to_code)
    except Exception as e:
        print(f"❌ Vertaalfout: {e}")
        return text

# Flask-app configureren
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///rss_articles.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# Database Model
class Article(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    view_count = db.Column(db.Integer, default=0)  # Ensure this line is present
    link = db.Column(db.String, nullable=False)
    published_date = db.Column(db.DateTime, nullable=True)
    english_title = db.Column(db.String, nullable=True)
    rating = db.Column(db.Integer, default=None)  # Handmatige beoordeling (-1, 0, 1)
    predicted_rating = db.Column(db.Float, default=None)  # AI Voorspelling (0-100)

# Database Model for RSS Feeds
class RSSFeed(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String, unique=True, nullable=False)

# Database Model for Configuration Settings
class Config(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    view_count = db.Column(db.Integer, default=5)

with app.app_context():
    db.create_all()
    # Ensure default configuration exists
    if Config.query.first() is None:
        default_config = Config(view_count=5)
        db.session.add(default_config)
        db.session.commit()

# Machine Learning Model
def train_model():
    articles = Article.query.filter(Article.rating.isnot(None)).all()
    
    if len(articles) < 5:
        print("📉 Niet genoeg data om een model te trainen.")
        return None, None
    
    titles = [a.english_title for a in articles]
    ratings = [a.rating for a in articles]
    
    vectorizer = TfidfVectorizer(stop_words='english', max_features=500)
    X = vectorizer.fit_transform(titles)
    y = np.array(ratings)
    
    model = LogisticRegression()
    model.fit(X, y)
    
    print("✅ Model getraind met", len(articles), "artikelen")
    
    return model, vectorizer

def predict_rating(title, model, vectorizer):
    if model is None or vectorizer is None:
        return 50.0

    X_new = vectorizer.transform([title])
    prob = model.predict_proba(X_new)[0]

    classes = model.classes_
    ranking_score = 50.0

    if len(classes) == 2:
        if set(classes) == {-1, 1}:
            ranking_score = (prob[1] * 100) + (prob[0] * 0)
        elif set(classes) == {0, 1}:
            ranking_score = (prob[1] * 100) + (prob[0] * 50)
        elif set(classes) == {-1, 0}:
            ranking_score = (prob[1] * 50) + (prob[0] * 0)
    elif len(classes) == 3:
        ranking_score = (prob[2] * 100) + (prob[1] * 50) + (prob[0] * 0)

    return round(ranking_score, 2)

def update_predictions():
    model, vectorizer = train_model()

    if model is None or vectorizer is None:
        print("⚠️ Niet genoeg data om voorspellingen te maken.")
        return

    articles = Article.query.all()

    for article in articles:
        new_predicted_rating = predict_rating(article.english_title, model, vectorizer)
        article.predicted_rating = new_predicted_rating

    db.session.commit()
    print("✅ Alle artikelen hebben een nieuwe ranking score.")

def article_exists(title):
    return Article.query.filter_by(title=title).first() is not None

def save_article(title, link, published_date, english_title):
    if published_date:
        published_date = published_date.replace('GMT', '+0000')
        published_date = datetime.strptime(published_date, "%a, %d %b %Y %H:%M:%S %z")

    article = Article(
        title=title,
        link=link,
        published_date=published_date,
        english_title=english_title
    )
    db.session.add(article)
    db.session.commit()

def fetch_rss():
    feeds = RSSFeed.query.all()
    for feed in feeds:
        rss_url = feed.url
        logger.info("Fetching RSS feed: %s", feed.url)
        feed_data = feedparser.parse(rss_url)
        for entry in feed_data.entries:
            if not article_exists(entry.title):
                published_date = entry.published if 'published' in entry else None
                english_title = translate_text(entry.title, from_code, to_code)
                save_article(entry.title, entry.link, published_date, english_title)

    print("✅ RSS-feeds opgehaald en artikelen opgeslagen.")
    update_predictions()

def background_fetch_rss():
    while True:
        logger.info("🚀 Achtergrondtaak gestart: RSS-feeds ophalen...")
        with app.app_context():
            fetch_rss()
        time.sleep(600)

def start_background_tasks():
    print("📢 start_background_tasks() wordt aangeroepen!", flush=True)
    threading.Thread(target=background_fetch_rss, daemon=False).start()

# API Endpoint: Alleen ongelezen artikelen ophalen (inclusief 0 en -1 beoordeelde)
@app.route("/api/articles")
def get_articles():
    config = Config.query.first()
    view_count_limit = config.view_count
    articles = Article.query.filter(
        ((Article.rating.is_(None)) | (Article.rating == 0) | (Article.rating == -1)) & 
        (Article.view_count < view_count_limit)
    ).order_by(Article.predicted_rating.desc().nullslast()).all()
    
    return jsonify({
        "articles": [
            {
                "id": a.id,
                "title": a.title,
                "link": a.link,
                "published_date": a.published_date.strftime("%a, %d %b %Y %H:%M:%S %z") if a.published_date else None,
                "english_title": a.english_title,
                "rating": a.rating,
                "predicted_rating": a.predicted_rating
            }
            for a in articles
        ]
    })

@app.route("/api/all_articles")
def get_all_articles():
    articles = Article.query.order_by(Article.published_date.desc()).all()
    return jsonify({
        "articles": [
            {
                "id": a.id,
                "title": a.title,
                "link": a.link,
                "published_date": a.published_date.strftime("%a, %d %b %Y %H:%M:%S %z") if a.published_date else None,
            }
            for a in articles
        ]
    })

@app.route("/api/rate_article", methods=["POST"])
def rate_article():
    data = request.json
    article_id = data.get("article_id")
    rating = data.get("rating")

    article = Article.query.get(article_id)
    if not article:
        return jsonify({"error": "Artikel niet gevonden"}), 404

    if rating in [-1, 0, 1]:
        article.rating = rating
    else:
        return jsonify({"error": "Ongeldige beoordeling"}), 400

    db.session.commit()
    update_predictions()
    return jsonify({"message": "Beoordeling opgeslagen"}), 200

# API Endpoint: Only read articles (rating = 0 or 1)
@app.route("/api/read_articles")
def get_read_articles():
    articles = Article.query.filter(Article.rating.in_([0, 1])).order_by(Article.published_date.desc()).all()
    return jsonify({
        "articles": [
            {
                "id": a.id,
                "title": a.title,
                "link": a.link,
                "published_date": a.published_date.strftime("%a, %d %b %Y %H:%M:%S %z") if a.published_date else None
            }
            for a in articles
        ]
    })

@app.route("/api/rss_feeds", methods=["GET", "POST", "DELETE"])
def manage_rss_feeds():
    if request.method == "GET":
        feeds = RSSFeed.query.all()
        return jsonify({"feeds": [{"id": f.id, "url": f.url} for f in feeds]})

    if request.method == "POST":
        data = request.json
        url = data.get("url")
        if not url:
            return jsonify({"error": "URL is required"}), 400

        if RSSFeed.query.filter_by(url=url).first():
            return jsonify({"error": "Feed already exists"}), 400

        new_feed = RSSFeed(url=url)
        db.session.add(new_feed)
        db.session.commit()
        return jsonify({"message": "Feed added"}), 201

    if request.method == "DELETE":
        data = request.json
        feed_id = data.get("id")
        feed = RSSFeed.query.get(feed_id)
        if not feed:
            return jsonify({"error": "Feed not found"}), 404

        db.session.delete(feed)
        db.session.commit()
        return jsonify({"message": "Feed deleted"}), 200

@app.route("/api/fetch_articles", methods=["POST"])
def fetch_articles():
    with app.app_context():
        fetch_rss()
    return jsonify({"message": "Artikelen succesvol opgehaald!"}), 200

@app.route("/api/increment_view_count", methods=["POST"])
def increment_view_count():
    data = request.json
    article_id = data.get("article_id")

    article = Article.query.get(article_id)
    if not article:
        return jsonify({"error": "Artikel niet gevonden"}), 404

    article.view_count += 1
    db.session.commit()
    return jsonify({"message": "View count incremented"}), 200

@app.route("/api/config", methods=["GET", "POST"])
def manage_config():
    if request.method == "GET":
        config = Config.query.first()
        return jsonify({"view_count": config.view_count})

    if request.method == "POST":
        data = request.json
        view_count = data.get("view_count")
        if view_count is None:
            return jsonify({"error": "view_count is required"}), 400

        config = Config.query.first()
        config.view_count = view_count
        db.session.commit()
        return jsonify({"message": "Configuration updated"}), 200

@app.route("/")
def index():
    return render_template("index.html")

if __name__ == "__main__":
    with app.app_context():
        update_predictions()
    start_background_tasks()
    app.run(debug=True, use_reloader=False)

