from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
import feedparser
import json
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.decomposition import LatentDirichletAllocation
import numpy as np
from datetime import datetime
from transformers import MarianMTModel, MarianTokenizer

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

with app.app_context():
    db.create_all()

# Gebruik een kleiner vertaalmodel: Nederlands → Engels
model_name = "Helsinki-NLP/opus-mt-nl-en"
tokenizer = MarianTokenizer.from_pretrained(model_name)
model = MarianMTModel.from_pretrained(model_name)

def translate_title(title):
    try:
        encoded_text = tokenizer(title, return_tensors="pt", padding=True, truncation=True)
        translated_tokens = model.generate(**encoded_text)
        translated_title = tokenizer.batch_decode(translated_tokens, skip_special_tokens=True)[0]
        return translated_title
    except Exception as e:
        print(f"Vertaalfout: {e}")
        return title  # Terugvallen op originele titel

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
                english_title = translate_title(entry.title)
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
                "english_title": a.english_title
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
