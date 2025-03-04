from app import app
# , start_background_tasks

# Deze moet BUITEN `if __name__ == "__main__"` staan
start_background_tasks()  # Zorgt dat de achtergrondthread start, ook met Gunicorn!

# Alleen `app.run()` binnen `if __name__ == "__main__"`
if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)
