from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
import feedparser
import json
# import numpy as np
from datetime import datetime
import argostranslate.package
import argostranslate.translate

from_code = "nl"
to_code = "en"

# Download and install Argos Translate package
argostranslate.package.update_package_index()
available_packages = argostranslate.package.get_available_packages()
package_to_install = next(
    filter(
        lambda x: x.from_code == from_code and x.to_code == to_code, available_packages
    )
)
argostranslate.package.install_from_path(package_to_install.download())

def translate_text(text, from_code, to_code):
    """Voer een vertaling uit met Argos Translate."""
    try:
        return argostranslate.translate.translate(text, from_code, to_code)
    except Exception as e:
        print(f"❌ Vertaalfout: {e}")
        return text

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///rss_articles.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# Database Model
class Article(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String, unique=True, nullable=False)
    link = db.Column(db.String, nullable=False)
    published_date = db.Column(db.DateTime, nullable=True)
    english_title = db.Column(db.String, nullable=True)
    rating = db.Column(db.Integer, default=0)  # -1 for negative, 0 for neutral, 1 for positive

with app.app_context():
    db.create_all()

def article_exists(title):
    return Article.query.filter_by(title=title).first() is not None

def save_article(title, link, published_date, english_title):
    if published_date:
        published_date = published_date.replace('GMT', '+0000')
        published_date = datetime.strptime(published_date, "%a, %d %b %Y %H:%M:%S %z")
    article = Article(title=title, link=link, published_date=published_date, english_title=english_title)
    print(f"Saving article: {title}")

    db.session.add(article)
    db.session.commit()

def fetch_rss():
    with open('feeds.json', 'r') as f:
        feeds = json.load(f)['feeds']
    
    for rss_url in feeds:
        feed = feedparser.parse(rss_url)
        for entry in feed.entries:
            if not article_exists(entry.title):
                published_date = entry.published if 'published' in entry else None
                english_title = translate_text(entry.title, from_code, to_code)
                save_article(entry.title, entry.link, published_date, english_title)

@app.route("/api/articles")
def get_articles():
    articles = Article.query.order_by(Article.published_date.desc()).all()
    return jsonify({
        "articles": [
            {
                "id": a.id, 
                "title": a.title, 
                "link": a.link, 
                "published_date": a.published_date.strftime("%a, %d %b %Y %H:%M:%S %z") if a.published_date else None,
                "english_title": a.english_title,
                "rating": a.rating
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
        return jsonify({"error": "Article not found"}), 404

    if rating in [-1, 0, 1]:
        article.rating = rating
    else:
        return jsonify({"error": "Invalid rating"}), 400

    db.session.commit()
    return jsonify({"message": "Rating updated"}), 200

@app.route("/")
def index():
    return render_template("index.html")

if __name__ == "__main__":
    with app.app_context():
        fetch_rss()
    app.run(debug=True)
