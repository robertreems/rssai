from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
import feedparser
import json

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///rss_articles.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# Database Model
class Article(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String, unique=True, nullable=False)
    link = db.Column(db.String, nullable=False)
    rating = db.Column(db.Integer, default=None)

# Create the database
with app.app_context():
    db.create_all()

# Check if the article already exists
def article_exists(title):
    return Article.query.filter_by(title=title).first() is not None

# Save articles
def save_article(title, link):
    article = Article(title=title, link=link)
    db.session.add(article)
    db.session.commit()

# Fetch RSS feed and save it in the database
def fetch_rss():
    with open('feeds.json', 'r') as f:
        feeds = json.load(f)['feeds']
    
    for rss_url in feeds:
        feed = feedparser.parse(rss_url)
        for entry in feed.entries:
            if not article_exists(entry.title):
                save_article(entry.title, entry.link)

# API: Retrieve articles with pagination
@app.route("/api/articles")
def get_articles():
    page = request.args.get("page", 1, type=int)
    per_page = 25
    articles = Article.query.paginate(page=page, per_page=per_page)
    
    return jsonify({
        "articles": [{"id": a.id, "title": a.title, "link": a.link, "rating": a.rating} for a in articles.items],
        "has_next": articles.has_next
    })

# API: Rate an article
@app.route("/api/rate", methods=["POST"])
def rate_article():
    data = request.json
    article = Article.query.get(data["id"])
    if article:
        article.rating = data["rating"]
        db.session.commit()
        return jsonify({"message": "Rating saved"})
    return jsonify({"error": "Article not found"}), 404

# HTML page
@app.route("/")
def index():
    return render_template("index.html")

if __name__ == "__main__":
    with app.app_context():
        fetch_rss()  # Execute RSS fetch on startup
    app.run(debug=True)
