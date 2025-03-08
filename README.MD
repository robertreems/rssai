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

## Usage

This has been tested on Debian 12 on a Raspberry 5.

1. Run the Flask application:
    ```sh
    gunicorn -w 1 --threads 2 -b 0.0.0.0:8000 --capture-output --log-level=debug wsgi:app
    ```

2. Open your web browser and go to `http://127.0.0.1:8000` to view the RSS articles.

## Configuration

- The RSS feeds are configured in the `feeds.json` file.
- The database is configured to use SQLite and is stored in `rss_articles.db`.

## NGINX Setup

To set up NGINX as a reverse proxy for your Flask application, use the following configuration:

```nginx
location /rssai/ {
    rewrite ^/rssai(/.*)$ $1 break;
    proxy_pass http://unix:/tmp/rssai.sock;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    client_max_body_size 100M;

    # Substitute API calls to dynamic paths
    sub_filter '/api/' '/rssai/api/';
    sub_filter_once off;
}
```

When using NGINX and Unix socket, start the app with the following command:

```sh
gunicorn -w 1 --threads 2 -b unix:/tmp/rssai.sock --capture-output --log-level=debug wsgi:app
```

## License

This project is licensed under the MIT License.
