import os

# Use environment variable PORT if available; otherwise, default to 8080.
PORT = int(os.environ.get("PORT", 8080))
