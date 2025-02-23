from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
import feedparser
import json
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.decomposition import LatentDirichletAllocation
import numpy as np

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///rss_articles.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# Database Model
class Article(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String, unique=True, nullable=False)
    link = db.Column(db.String, nullable=False)

with app.app_context():
    db.create_all()

def article_exists(title):
    return Article.query.filter_by(title=title).first() is not None

# def categorize_article(title):
#     keywords = {
#         "sport": ["voetbal", "tennis", "hockey", "wedstrijd", "score"],
#         "politiek": ["minister", "regering", "verkiezingen", "partij", "beleid"],
#         "technologie": ["AI", "software", "hardware", "computer", "smartphone"],
#         "entertainment": ["film", "muziek", "festival", "acteur", "zanger"],
#         "wetenschap": ["onderzoek", "universiteit", "experimenteel", "fysica", "chemie"]
#     }
#     for category, words in keywords.items():
#         if any(word.lower() in title.lower() for word in words):
#             return category
#     return "Overig"

def save_article(title, link):
    article = Article(title=title, link=link)
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
                save_article(entry.title, entry.link)

# def predict_interest():
#     rated_articles = Article.query.filter(Article.rating.isnot(None)).order_by(Article.id).all()
#     unrated_articles = Article.query.filter(Article.rating.is_(None)).order_by(Article.id).all()

#     print(f"Aantal beoordeelde artikelen: {len(rated_articles)}")
#     print(f"Aantal onbeoordeelde artikelen: {len(unrated_articles)}")

#     if len(rated_articles) < 5 or len(unrated_articles) == 0:
#         print("Geen voorspellingen mogelijk: onvoldoende data.")
#         return

#     all_articles = rated_articles + unrated_articles
#     all_titles = [a.title for a in all_articles]
#     rated_titles = [a.title for a in rated_articles]
#     unrated_titles = [a.title for a in unrated_articles]
    
#     stopwoorden_nl = ["de", "het", "een", "in", "op", "van", "met", "dat", "is", "bij", "voor", "door", "als", "ook", "niet", "aan", "om", "te", "uit", "naar", "wordt", "kan", "zijn", "was"]
#     vectorizer = CountVectorizer(stop_words=stopwoorden_nl, max_features=1000)
#     title_matrix = vectorizer.fit_transform(all_titles)

#     num_topics = min(len(rated_articles), 5)
#     lda = LatentDirichletAllocation(n_components=num_topics, random_state=42)
#     lda.fit(title_matrix)

#     topic_distributions = lda.transform(title_matrix[len(rated_articles):])
#     rated_scores = np.array([a.rating for a in rated_articles])
#     topic_weights = (lda.transform(title_matrix[:len(rated_articles)]).T @ rated_scores) / np.sum(rated_scores)
#     predicted_scores = topic_distributions @ topic_weights

#     for article, score in zip(unrated_articles, predicted_scores):
#         article.predicted_rating = round(float(score) * 10, 2)
#         db.session.add(article)
    
#     db.session.commit()

@app.route("/api/articles")
def get_articles():
    articles = Article.query.all()
    return jsonify({
        "articles": [
            {
                "id": a.id, 
                "title": a.title, 
                "link": a.link, 
            }
            for a in articles
        ]
    })

# @app.route("/api/recommended_articles")
# def get_recommended_articles():
#     recommended_articles = Article.query.filter(Article.predicted_rating.isnot(None)).order_by(Article.predicted_rating.desc()).limit(25).all()
#     return jsonify({
#         "recommended_articles": [
#             {
#                 "id": a.id, 
#                 "title": a.title, 
#                 "link": a.link, 
#                 "predicted_rating": a.predicted_rating,
#                 "category": a.category or "Onbekend"
#             }
#             for a in recommended_articles
#         ]
#     })

# @app.route("/api/rate", methods=["POST"])
# def rate_article():
#     data = request.json
#     article = Article.query.get(data["id"])
#     if article:
#         article.rating = data["rating"]
#         db.session.commit()
#         predict_interest()
#         return jsonify({"message": "Rating saved"})
#     return jsonify({"message": "Article not found"}), 404

@app.route("/")
def index():
    return render_template("index.html")

if __name__ == "__main__":
    with app.app_context():
        fetch_rss()
    app.run(debug=True)
