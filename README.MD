## Requirements

- Python 3.8+ (Only compatible with Python 3.12.*, not with Python 3.13.*)
- Flask
- Flask-SQLAlchemy
- feedparser
- Argos Translate

## Installation

1. Clone the repository:
    ```sh
    git clone https://github.com/yourusername/rssai.git
    cd rssai
    ```

2. Create a virtual environment:
    ```sh
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```

3. Install the dependencies:
    ```sh
    pip install -r requirements.txt
    ```

4. Set up the database:
    ```sh
    python fetch_rss.py
    ```

## Usage

1. Run the Flask application:
    ```sh
    python fetch_rss.py
    ```

2. Open your web browser and go to `http://127.0.0.1:5000` to view the RSS articles.

## Configuration

- The RSS feeds are configured in the [feeds.json](http://_vscodecontentref_/6) file.
- The database is configured to use SQLite and is stored in [rss_articles.db](http://_vscodecontentref_/7).

## License

This project is licensed under the MIT License.