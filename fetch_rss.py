from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
import feedparser
import json
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///rss_articles.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# Database Model
class Article(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String, unique=True, nullable=False)
    link = db.Column(db.String, nullable=False)
    rating = db.Column(db.Integer, default=None)  # Handmatige beoordeling door gebruiker
    predicted_rating = db.Column(db.Float, default=None)  # Voorspelde relevantiescore

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

# Bereken een voorspelde score voor nieuwe artikelen op basis van eerdere ratings
def predict_interest():
    rated_articles = Article.query.filter(Article.rating.isnot(None)).all()
    unrated_articles = Article.query.filter(Article.rating.is_(None)).all()

    print("predicting interest")

    if not rated_articles or not unrated_articles:
        print("Geen voorspellingen mogelijk: onvoldoende data.")
        return

    if not rated_articles or not unrated_articles:
        print("There are no ratings available to make predictions.")
        return  # Geen voorspellingen mogelijk als er nog geen ratings zijn

    rated_titles = [a.title for a in rated_articles]
    unrated_titles = [a.title for a in unrated_articles]

    vectorizer = TfidfVectorizer()
    tfidf_matrix = vectorizer.fit_transform(rated_titles + unrated_titles)

    rated_vectors = tfidf_matrix[:len(rated_articles)]
    unrated_vectors = tfidf_matrix[len(rated_articles):]

    # Gemiddelde van positieve ratings als referentievector
    rated_scores = [a.rating for a in rated_articles]
    if sum(rated_scores) == 0:
        print("No positive ratings available for reference vector calculation.")
        return

    reference_vector = (rated_vectors.T @ rated_scores) / sum(rated_scores)

    # Vergelijk ongerate artikelen met deze referentievector
    similarities = cosine_similarity(unrated_vectors, reference_vector.reshape(1, -1)).flatten()

    # Opslaan van voorspelde scores in `predicted_rating`
    for article, score in zip(unrated_articles, similarities):
        if score is not None:
            article.predicted_rating = round(score * 10, 2)  # Schalen naar 0-10
            db.session.add(article)  # Expliciet toevoegen aan de sessie
    db.session.commit()

# API: Haal artikelen op met paginering
@app.route("/api/articles")
def get_articles():
    page = request.args.get("page", 1, type=int)
    per_page = 25
    articles = Article.query.paginate(page=page, per_page=per_page)
    
    return jsonify({
        "articles": [{"id": a.id, "title": a.title, "link": a.link, "rating": a.rating, "predicted_rating": a.predicted_rating} for a in articles.items],
        "has_next": articles.has_next
    })

# API: Beoordeel een artikel
@app.route("/api/rate", methods=["POST"])
def rate_article():
    data = request.json
    article = Article.query.get(data["id"])
    if article:
        article.rating = data["rating"]
        db.session.commit()
        return jsonify({"message": "Rating saved"})
    return jsonify({"error": "Article not found"}), 404

# API: Aanbevolen artikelen ophalen (gesorteerd op relevantie)
@app.route("/api/recommended_articles")
def get_recommended_articles():
    predict_interest()  # Update voorspellingen

    page = request.args.get("page", 1, type=int)
    per_page = 25

    # Sorteer correct en zorg dat None-waarden onderaan staan
    articles = Article.query.order_by(
        db.case((Article.predicted_rating.is_(None), 0), else_=Article.predicted_rating).desc()
    ).paginate(page=page, per_page=per_page)

    return jsonify({
        "articles": [
            {"id": a.id, "title": a.title, "link": a.link, "rating": a.rating, "predicted_rating": a.predicted_rating}
            for a in articles.items
        ],
        "has_next": articles.has_next
    })

# HTML pagina
@app.route("/")
def index():
    return render_template("index.html")

if __name__ == "__main__":
    with app.app_context():
        predict_interest()
        fetch_rss()  # RSS-feeds ophalen bij opstarten
    app.run(debug=True)
