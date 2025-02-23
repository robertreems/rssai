from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
import feedparser
import json
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.decomposition import LatentDirichletAllocation
import numpy as np
from datetime import datetime

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

with app.app_context():
    db.create_all()

def article_exists(title):
    return Article.query.filter_by(title=title).first() is not None

def save_article(title, link, published_date):
    if published_date:
        published_date = published_date.replace('GMT', '+0000')
        published_date = datetime.strptime(published_date, "%a, %d %b %Y %H:%M:%S %z")
    article = Article(title=title, link=link, published_date=published_date)
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
                save_article(entry.title, entry.link, published_date)

@app.route("/api/articles")
def get_articles():
    articles = Article.query.order_by(Article.published_date.desc()).all()
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

@app.route("/")
def index():
    return render_template("index.html")

if __name__ == "__main__":
    with app.app_context():
        fetch_rss()
    app.run(debug=True)
