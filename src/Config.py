import os                     # File system operations
import argparse               # Argument passing through terminal
# Flask framework imports
from flask import (
    Flask, render_template, request, redirect, url_for,
    session, send_from_directory, jsonify, flash, abort
)


# =============================================================================
# APPLICATION CONFIGURATION
# =============================================================================
# Initialize Flask application
parser = argparse.ArgumentParser(description="Gallario - ImageServer - Social Media Image Sharing Platform")
parser.add_argument("--port", type=int, default=8080, help="Port number to run on the web app.")
parser.add_argument("--notlan", action="store_false", default=True, help="Set it to True if you want to test it on other devices that are also connected to the local network.")
arg = parser.parse_args()

app = Flask(__name__)
# Secret key for session management and security
app.secret_key = "F18029BD1E955FB23095506A7223710A90B5F43E1F57442EB3ECC8D704B8554D"

# Get the directory where this script is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Define folder paths for file storage
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")  # User uploaded images
AVATAR_FOLDER = os.path.join(BASE_DIR, "static", "avatars")  # User profile pictures

# Allowed file extensions for security
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

# Create necessary directories if they don't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(AVATAR_FOLDER, exist_ok=True)

# Database file path
DB_PATH = os.path.join(BASE_DIR, "database.db")
