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
    title = db.Column(db.String, unique=True, nullable=False)
    link = db.Column(db.String, nullable=False)
    published_date = db.Column(db.DateTime, nullable=True)
    english_title = db.Column(db.String, nullable=True)
    rating = db.Column(db.Integer, default=None)  # Handmatige beoordeling (-1, 0, 1)
    predicted_rating = db.Column(db.Float, default=None)  # AI Voorspelling (0-100)

with app.app_context():
    db.create_all()

# Machine Learning Model
def train_model():
    """Train een eenvoudig ML-model op basis van eerdere ratings."""
    articles = Article.query.filter(Article.rating.isnot(None)).all()
    
    if len(articles) < 5:
        print("📉 Niet genoeg data om een model te trainen.")
        return None, None
    
    titles = [a.english_title for a in articles]
    ratings = [a.rating for a in articles]
    
    # Tekstvectorisatie met TF-IDF
    vectorizer = TfidfVectorizer(stop_words='english', max_features=500)
    X = vectorizer.fit_transform(titles)
    y = np.array(ratings)  # Labels (-1, 0, 1)
    
    # Train een Logistic Regression-model
    model = LogisticRegression()
    model.fit(X, y)
    
    print("✅ Model getraind met", len(articles), "artikelen")
    
    return model, vectorizer

def predict_rating(title, model, vectorizer):
    """Voorspel een ranking score tussen 0 en 100."""
    if model is None or vectorizer is None:
        return 50.0  # Neutrale score als er geen model is

    X_new = vectorizer.transform([title])
    prob = model.predict_proba(X_new)[0]  # Geeft kans op aanwezige klassen

    # Controleer de beschikbare klassen
    classes = model.classes_
    ranking_score = 50.0  # Standaard neutrale score

    if len(classes) == 2:
        if set(classes) == {-1, 1}:
            ranking_score = (prob[1] * 100) + (prob[0] * 0)  # Alleen -1 en 1
        elif set(classes) == {0, 1}:
            ranking_score = (prob[1] * 100) + (prob[0] * 50)  # Alleen 0 en 1
        elif set(classes) == {-1, 0}:
            ranking_score = (prob[1] * 50) + (prob[0] * 0)    # Alleen -1 en 0
    elif len(classes) == 3:
        ranking_score = (prob[2] * 100) + (prob[1] * 50) + (prob[0] * 0)  # Alle 3 klassen

    return round(ranking_score, 2)


def update_predictions():
    """Herberekent de ranking score voor alle artikelen."""
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

# Controleer of een artikel al bestaat
def article_exists(title):
    return Article.query.filter_by(title=title).first() is not None

# Sla een nieuw artikel op en voorzie het van een voorspelde score
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

# RSS Feeds inlezen
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

# API Endpoint: Alle artikelen ophalen, gesorteerd op voorspelde rating
@app.route("/api/articles")
def get_articles():
    articles = Article.query.order_by(Article.predicted_rating.desc().nullslast()).all()
    return jsonify({
        "articles": [
            {
                "id": a.id, 
                "title": a.title, 
                "link": a.link, 
                "published_date": a.published_date.strftime("%a, %d %b %Y %H:%M:%S %z") if a.published_date else None,
                "english_title": a.english_title,
                "rating": a.rating,  # Handmatige beoordeling
                "predicted_rating": a.predicted_rating  # Ranking Score 0-100
            }
            for a in articles
        ]
    })

# API Endpoint: Beoordeel een artikel handmatig
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
    update_predictions()  # Zorg dat nieuwe beoordelingen direct invloed hebben op de AI
    return jsonify({"message": "Beoordeling opgeslagen"}), 200

# Hoofdpagina (HTML-rendering)
@app.route("/")
def index():
    return render_template("index.html")

# Main: RSS Feeds ophalen, voorspellingen updaten en de server starten
if __name__ == "__main__":
    with app.app_context():
        fetch_rss()  # Nieuwe artikelen ophalen
        update_predictions()  # Voorspellingen updaten bij elke start
    app.run(debug=True)
