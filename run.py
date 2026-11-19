import os
from app import create_app

# Create application using FLASK_CONFIG, FLASK_ENV, or default to development
env = os.getenv("FLASK_CONFIG") or os.getenv("FLASK_ENV") or "development"
app = create_app(env)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "1") == "1"
    print(f" * ProductGuard Server Starting in {env.upper()} mode on port {port}...")
    app.run(host="127.0.0.1", port=port, debug=debug)
