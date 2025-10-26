import argparse               # Argument passing through terminal
import os                     # File system operations
import sqlite3                # Database operations
import uuid                   # Generate unique identifiers
from datetime import datetime # Date/time handling

# Flask framework imports
from flask import (
    Flask, render_template, request, redirect, url_for,
    session, send_from_directory, jsonify, flash, abort, Blueprint
)

# Security and file handling imports
from werkzeug.security import generate_password_hash, check_password_hash  # Password hashing
from werkzeug.utils import secure_filename  # Secure file name handling
from PIL import Image  # Image processing (resize, crop, etc.)

from src.Config import *

# =============================================================================
# DATABASE HELPER FUNCTIONS
# =============================================================================

def get_db():
    """
    Create and return a database connection.
    - Enables foreign key constraints for data integrity
    - Sets row factory to return Row objects (like dictionaries)
    - Enables automatic type detection for dates/times
    """
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    conn.row_factory = sqlite3.Row  # Return rows as dictionary-like objects
    # Enforce foreign key constraints for data integrity
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
def ensure_likes_value_column(conn):
    """
    Database migration helper: Add 'value' column to likes table if missing.
    This supports the like/dislike system where:
    - value = 1 means like
    - value = -1 means dislike
    - value = 0 means no reaction
    """
    # Get all column names from the likes table
    info = conn.execute("PRAGMA table_info(likes)").fetchall()
    cols = [r["name"] for r in info]
    
    # If 'value' column doesn't exist, add it
    if "value" not in cols:
        try:
            # Add the value column with default like = 1
            conn.execute("ALTER TABLE likes ADD COLUMN value INTEGER DEFAULT 1")
            conn.commit()
        except sqlite3.OperationalError:
            # If ALTER fails (older SQLite or locked DB), ignore gracefully
            pass

def init_db():
    """
    Initialize the database with all required tables.
    Creates tables for users, posts, likes, comments, notifications, and DMs.
    Also handles database migrations for existing installations.
    """
    conn = get_db()
    cur = conn.cursor()
    
    # Create all database tables with proper relationships
    cur.executescript("""
    -- Users table: stores user account information
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,           -- Unique username
        password TEXT NOT NULL,                  -- Hashed password
        avatar TEXT DEFAULT 'avatars/default.png',  -- Profile picture path
        description Text DEFAULT 'No description set.'  -- User bio
    );

    -- Notifications table: stores user notifications
    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        maker_id INTEGER NOT NULL,         -- User who triggered the notification
        receiver_id INTEGER NOT NULL,     -- User who receives the notification
        type INTEGER NOT NULL,             -- 0=like, 1=dislike, 2=comment, 3=dm...
        reference_id INTEGER,              -- ID of the referenced post/comment
        comment_id INTEGER,                -- Specific comment ID for comment notifications
        seen BOOLEAN DEFAULT 0,            -- 0=unread, 1=read
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(maker_id) REFERENCES users(id),
        FOREIGN KEY(receiver_id) REFERENCES users(id),
        FOREIGN KEY(comment_id) REFERENCES comments(id)
    );

    -- Posts table: stores user-uploaded images and captions
    CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,                   -- Owner of the post
        image TEXT,                        -- Filename of uploaded image
        caption TEXT,                      -- Post caption/description
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );

    -- Likes table: stores user reactions to posts (like/dislike system)
    CREATE TABLE IF NOT EXISTS likes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,                   -- User who reacted
        post_id INTEGER,                   -- Post being reacted to
        value INTEGER DEFAULT 1,           -- 1=like, -1=dislike, 0=no reaction
        UNIQUE(user_id, post_id),         -- One reaction per user per post
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(post_id) REFERENCES posts(id)
    );

    -- DMs table: stores direct messages (currently unused but ready for future)
    CREATE TABLE IF NOT EXISTS dms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,                   -- Sender
        receiever_id INTEGER,              -- Receiver (note: typo in original)
        message_id INTEGER,                -- Message identifier
        value TEXT,                        -- Message content
        UNIQUE(user_id, message_id),
        FOREIGN KEY(user_id) REFERENCES users(id)
    );

    -- Comments table: stores user comments on posts
    CREATE TABLE IF NOT EXISTS comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        post_id INTEGER NOT NULL,         -- Post being commented on
        user_id INTEGER NOT NULL,         -- User who commented
        text TEXT NOT NULL,               -- Comment content
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(post_id) REFERENCES posts(id),
        FOREIGN KEY(user_id) REFERENCES users(id)
    );
    """)
    conn.commit()
    
    # Ensure likes.value column exists (for database migrations)
    ensure_likes_value_column(conn)
    conn.commit()
    conn.close()

# Initialize the database when the app starts
init_db()

# =============================================================================
# UTILITY HELPER FUNCTIONS
# =============================================================================
def allowed_file(filename):
    """
    Check if a file has an allowed extension for security.
    Only allows image files: png, jpg, jpeg, gif
    """
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def current_user():
    """
    Get the currently logged-in user from the session.
    Returns user data if logged in, None if not.
    """
    uid = session.get("user_id")
    if not uid:
        return None
    
    # Fetch user data from database
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
    db.close()
    return user

def crop_to_square(img):
    """
    Crop an image to a centered square before resizing.
    This ensures avatars are always square regardless of original aspect ratio.
    """
    width, height = img.size
    min_dim = min(width, height)  # Use the smaller dimension as the square size
    
    # Calculate crop coordinates to center the square
    left = (width - min_dim) / 2
    top = (height - min_dim) / 2
    right = (width + min_dim) / 2
    bottom = (height + min_dim) / 2
    
    return img.crop((left, top, right, bottom))

def save_avatar_file(file_storage):
    """
    Process and save an uploaded avatar image.
    - Validates file type
    - Crops to square
    - Resizes to 256x256 pixels
    - Saves as PNG with unique filename
    Returns relative path for database storage.
    """
    # Validate file exists and has allowed extension
    if not file_storage or file_storage.filename == "":
        return None
    if not allowed_file(file_storage.filename):
        return None

    # Ensure avatars folder exists
    os.makedirs(AVATAR_FOLDER, exist_ok=True)

    # Generate unique filename (UUID + .png)
    unique_name = f"{uuid.uuid4().hex}.png"
    full_path = os.path.join(AVATAR_FOLDER, unique_name)

    # Process the image
    img = Image.open(file_storage.stream)
    img = img.convert("RGB")  # Convert to RGB to avoid transparency issues
    img = crop_to_square(img)  # Make it square
    img = img.resize((256, 256), Image.LANCZOS)  # Resize to standard avatar size
    
    # Save as optimized PNG
    img.save(full_path, format="PNG", optimize=True)

    # Return relative path for database storage
    return f"avatars/{unique_name}"

def save_upload_file(file_storage):
    """
    Save an uploaded post image file.
    - Validates file type
    - Creates secure filename
    - Saves to uploads folder
    Returns the stored filename.
    """
    # Validate file
    if not file_storage or file_storage.filename == "":
        return None
    if not allowed_file(file_storage.filename):
        return None
    
    # Create secure filename with UUID prefix
    filename = secure_filename(file_storage.filename)
    unique = f"{uuid.uuid4().hex}_{filename}"
    full_path = os.path.join(UPLOAD_FOLDER, unique)
    
    # Save the file
    file_storage.save(full_path)
    return unique

def remove_upload_file(stored_filename):
    """
    Safely delete an uploaded file from the filesystem.
    Used when posts are deleted to clean up storage.
    """
    try:
        path = os.path.join(UPLOAD_FOLDER, stored_filename)
        if os.path.exists(path):
            os.remove(path)
            return True
    except Exception:
        # Silently handle any file deletion errors
        pass
    return False
