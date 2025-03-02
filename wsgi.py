from app import app, start_background_tasks

# Start achtergrondtaken hier
start_background_tasks()

if __name__ == "__main__":
    app.run()
