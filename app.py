# =============================================================================
# IMAGE SHARING APPLICATION - FLASK WEB APP
# =============================================================================
# This is a social media-style image sharing application built with Flask.
# Features: User registration/login, image uploads, likes/dislikes, comments,
# notifications, and user profiles with editable descriptions.

# Made by Nezar Bahid @ AUI 
# =============================================================================

# Standard library imports
import os                    # File system operations
import sqlite3              # Database operations
import uuid                 # Generate unique identifiers
from datetime import datetime  # Date/time handling

# Flask framework imports
from flask import (
    Flask, render_template, request, redirect, url_for,
    session, send_from_directory, jsonify, flash, abort
)

# Security and file handling imports
from werkzeug.security import generate_password_hash, check_password_hash  # Password hashing
from werkzeug.utils import secure_filename  # Secure file name handling
from PIL import Image  # Image processing (resize, crop, etc.)
 

# =============================================================================
# APPLICATION CONFIGURATION
# =============================================================================
# Initialize Flask application
sharingOnLocalNetwork = False

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

# =============================================================================
# FLASK ROUTES - WEB PAGES AND API ENDPOINTS
# =============================================================================

@app.route("/")
def index():
    """
    Main page - displays the feed of all posts with pagination.
    Shows posts with like/dislike counts, comment counts, and user vote status.
    """
    db = get_db()
    user_id = session.get("user_id")

    # Pagination setup
    page = int(request.args.get("page", 1))
    per_page = 5  # Posts per page
    offset = (page - 1) * per_page

    # Complex query to get posts with all related data
    posts = db.execute("""
        SELECT posts.id, posts.image, posts.caption, posts.timestamp, posts.user_id,
               users.username, users.avatar,
               -- Count likes (value = 1)
               COALESCE((SELECT COUNT(*) FROM likes WHERE likes.post_id = posts.id AND likes.value = 1),0) AS like_count,
               -- Count dislikes (value = -1)
               COALESCE((SELECT COUNT(*) FROM likes WHERE likes.post_id = posts.id AND likes.value = -1),0) AS dislike_count,
               -- Get current user's vote on this post
               COALESCE((SELECT value FROM likes WHERE likes.post_id = posts.id AND likes.user_id = ?), 0) AS user_vote,
               -- Count comments on this post
               COALESCE((SELECT COUNT(*) FROM comments WHERE comments.post_id = posts.id),0) AS comment_count
        FROM posts
        JOIN users ON posts.user_id = users.id
        ORDER BY posts.timestamp DESC
        LIMIT ? OFFSET ?
    """, (user_id, per_page, offset)).fetchall()

    db.close()
    return render_template("index.html", posts=posts, user=current_user(), page=page)

@app.route("/login", methods=["GET", "POST"])
def login():
    """
    User login page and authentication.
    GET: Show login form
    POST: Process login credentials and authenticate user
    """
    if request.method == "POST":
        # Get form data
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        
        # Check user credentials
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        db.close()
        
        # Verify password hash
        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]  # Start user session
            return redirect(url_for("index"))
        else:
            flash("Invalid username or password", "error")
    
    # Show login form (GET request or failed POST)
    return render_template("login.html", register=False, user=current_user())

@app.route("/logout")
def logout():
    """
    Log out the current user by clearing the session.
    Redirects to login page.
    """
    session.clear()  # Remove all session data
    return redirect(url_for("login"))

@app.route("/register", methods=["GET", "POST"])
def register():
    """
    User registration page and account creation.
    GET: Show registration form
    POST: Create new user account with optional avatar
    """
    if request.method == "POST":
        # Get form data
        username = request.form.get("username", "").strip()
        password_raw = request.form.get("password", "")
        avatar_file = request.files.get("avatar")  # Optional avatar upload

        # Validate required fields
        if username == "" or password_raw == "":
            flash("Username and password required.", "error")
            return redirect(url_for("register"))

        # Process avatar if provided
        avatar_path = save_avatar_file(avatar_file) if avatar_file else None
        if not avatar_path:
            avatar_path = 'avatars/default.png'  # Use default avatar

        # Create user account
        db = get_db()
        try:
            db.execute(
                "INSERT INTO users (username, password, avatar, description) VALUES (?, ?, ?, ?)",
                (username, generate_password_hash(password_raw), avatar_path, None)
            )
            db.commit()
            flash("Account created. Please log in.", "success")
            db.close()
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            # Username already exists
            db.close()
            flash("Username already taken.", "error")
            return redirect(url_for("register"))

    # Show registration form (GET request or failed POST)
    return render_template("login.html", register=True, user=current_user())

@app.route("/upload", methods=["POST"])
def upload():
    """
    Handle image uploads for new posts.
    Requires user to be logged in.
    Validates file type and saves to database.
    """
    # Check if user is logged in
    user = current_user()
    if not user:
        return redirect(url_for("login"))

    # Get uploaded file
    file = request.files.get("photo")
    if not file:
        flash("No file uploaded.", "error")
        return redirect(url_for("index"))

    # Validate file type
    if not allowed_file(file.filename):
        flash("Invalid file type.", "error")
        return redirect(url_for("index"))

    # Save the file
    stored_filename = save_upload_file(file)
    if not stored_filename:
        flash("Failed to save file.", "error")
        return redirect(url_for("index"))

    # Get caption and save post to database
    caption = request.form.get("caption", "").strip()
    db = get_db()
    db.execute(
        "INSERT INTO posts (user_id, image, caption) VALUES (?, ?, ?)",
        (user["id"], stored_filename, caption)
    )
    db.commit()
    db.close()
    flash("Uploaded!", "success")
    return redirect(url_for("index"))

@app.route("/like/<int:post_id>", methods=["POST"])
def like(post_id):
    """
    Handle like/unlike functionality for posts.
    Toggle behavior: like if not liked, unlike if already liked.
    Returns JSON with updated counts for AJAX updates.
    """
    # Check authentication
    user = current_user()
    if not user:
        return jsonify(success=False), 401

    db = get_db()

    # Get the post owner (for notifications)
    post = db.execute("SELECT user_id FROM posts WHERE id=?", (post_id,)).fetchone()
    if not post:
        return jsonify(success=False, error="Post not found"), 404

    # Check if user already reacted to this post
    existing = db.execute("SELECT * FROM likes WHERE user_id=? AND post_id=?", 
                          (user["id"], post_id)).fetchone()

    if existing:
        if existing["value"] == 1:
            # User already liked - remove the like (unlike)
            db.execute("DELETE FROM likes WHERE id=?", (existing["id"],))
        else:
            # User disliked - change to like
            db.execute("UPDATE likes SET value=1 WHERE id=?", (existing["id"],))

            # Send notification to post owner (if not self-like)
            if post["user_id"] != user["id"]:
                db.execute("""
                    INSERT INTO notifications (maker_id, receiver_id, type, reference_id)
                    VALUES (?, ?, ?, ?)
                """, (user["id"], post["user_id"], 0, post_id))  # type 0 = like
    else:
        # First time reaction - add like
        db.execute("INSERT INTO likes (user_id, post_id, value) VALUES (?, ?, 1)", 
                   (user["id"], post_id))

        # Send notification to post owner (if not self-like)
        if post["user_id"] != user["id"]:
            db.execute("""
                INSERT INTO notifications (maker_id, receiver_id, type, reference_id)
                VALUES (?, ?, ?, ?)
            """, (user["id"], post["user_id"], 0, post_id))  # type 0 = like

    db.commit()

    # Get updated reaction counts
    like_count = db.execute("SELECT COUNT(*) FROM likes WHERE post_id=? AND value=1", 
                            (post_id,)).fetchone()[0]
    dislike_count = db.execute("SELECT COUNT(*) FROM likes WHERE post_id=? AND value=-1", 
                               (post_id,)).fetchone()[0]
    db.close()

    # Return JSON response for AJAX
    return jsonify(success=True, like_count=like_count, dislike_count=dislike_count)

@app.route("/dislike/<int:post_id>", methods=["POST"])
def dislike(post_id):
    """
    Handle dislike functionality for posts.
    Toggle behavior: dislike if not disliked, remove if already disliked.
    Also handles switching between like/dislike.
    Returns JSON with updated counts for AJAX updates.
    """
    # Check authentication
    user = current_user()
    if not user:
        return jsonify(success=False), 401

    # Get reaction type from form (1=like, -1=dislike)
    value = int(request.form.get("value", 1))
    db = get_db()

    # Get the post owner (for notifications)
    post = db.execute("SELECT user_id FROM posts WHERE id=?", (post_id,)).fetchone()
    if not post:
        return jsonify(success=False, error="Post not found"), 404

    # Check if user already reacted to this post
    existing = db.execute("SELECT * FROM likes WHERE user_id=? AND post_id=?", 
                          (user["id"], post_id)).fetchone()

    if existing:
        if existing["value"] == value:
            # User already has this reaction - remove it
            db.execute("DELETE FROM likes WHERE id=?", (existing["id"],))
        else:
            # User has different reaction - switch to new one
            db.execute("UPDATE likes SET value=? WHERE id=?", (value, existing["id"]))
    else:
        # First time reaction - add new reaction
        db.execute("INSERT INTO likes (user_id, post_id, value) VALUES (?, ?, ?)", 
                   (user["id"], post_id, value))

        # Send notification to post owner (if not self-reaction)
        if value == 1 and post["user_id"] != user["id"]:
            # Like notification
            db.execute("""
                INSERT INTO notifications (maker_id, receiver_id, type, reference_id)
                VALUES (?, ?, ?, ?)
            """, (user["id"], post["user_id"], 0, post_id))  # type 0 = like
        elif value == -1 and post["user_id"] != user["id"]:
            # Dislike notification
            db.execute("""
                INSERT INTO notifications (maker_id, receiver_id, type, reference_id)
                VALUES (?, ?, ?, ?)
            """, (user["id"], post["user_id"], 1, post_id))  # type 1 = dislike

    db.commit()

    # Get updated reaction counts
    like_count = db.execute("SELECT COUNT(*) FROM likes WHERE post_id=? AND value=1", (post_id,)).fetchone()[0]
    dislike_count = db.execute("SELECT COUNT(*) FROM likes WHERE post_id=? AND value=-1", (post_id,)).fetchone()[0]
    db.close()

    # Return JSON response for AJAX
    return jsonify(success=True, like_count=like_count, dislike_count=dislike_count)


@app.route("/post/<int:post_id>")
def view_post(post_id):
    """
    Display a single post with its comments and reaction counts.
    Shows the full post details, all comments, and user's current reaction.
    """
    db = get_db()
    
    # Get the post with author information
    post = db.execute("""
        SELECT posts.*, users.username, users.avatar
        FROM posts JOIN users ON posts.user_id = users.id
        WHERE posts.id = ?
    """, (post_id,)).fetchone()
    
    if not post:
        db.close()
        return "Post not found", 404

    # Get all comments for this post with author info
    comments = db.execute("""
        SELECT comments.*, users.username, users.avatar
        FROM comments JOIN users ON comments.user_id = users.id
        WHERE comments.post_id = ?
        ORDER BY comments.timestamp ASC
    """, (post_id,)).fetchall()

    # Get reaction counts
    like_count = db.execute("SELECT COUNT(*) AS c FROM likes WHERE post_id = ? AND value = 1", (post_id,)).fetchone()["c"]
    dislike_count = db.execute("SELECT COUNT(*) AS c FROM likes WHERE post_id = ? AND value = -1", (post_id,)).fetchone()["c"]

    # Get current user's reaction to this post
    user_vote_row = None
    user_vote = 0
    uid = session.get("user_id")
    if uid:
        user_vote_row = db.execute("SELECT value FROM likes WHERE post_id = ? AND user_id = ?", (post_id, uid)).fetchone()
        if user_vote_row:
            user_vote = user_vote_row["value"] or 0

    db.close()
    return render_template("post.html", post=post, comments=comments, like_count=like_count, dislike_count=dislike_count, user_vote=user_vote, user=current_user())

@app.route("/comment/<int:post_id>", methods=["POST"])
def add_comment(post_id):
    """
    Add a new comment to a post.
    Requires user to be logged in.
    Sends notification to post owner if not self-comment.
    """
    # Check authentication
    user = current_user()
    if not user:
        flash("Login to comment.", "error")
        return redirect(url_for("login"))

    # Get and validate comment text
    text = request.form.get("comment", "").strip()
    if text == "":
        flash("Comment cannot be empty.", "error")
        return redirect(url_for("view_post", post_id=post_id))
        
    # Save comment to database
    db = get_db()
    cur = db.execute(
        "INSERT INTO comments (post_id, user_id, text) VALUES (?, ?, ?)",
        (post_id, user["id"], text)
    )
    comment_id = cur.lastrowid  # Get the ID of the new comment
    
    # Send notification to post owner (if not self-comment)
    post = db.execute("SELECT user_id FROM posts WHERE id = ?", (post_id,)).fetchone()
    if post and post["user_id"] != user["id"]:
        db.execute("""
            INSERT INTO notifications (maker_id, receiver_id, type, reference_id, comment_id)
            VALUES (?, ?, ?, ?, ?)
        """, (user["id"], post["user_id"], 2, post_id, comment_id))  # type 2 = comment
    
    db.commit()
    db.close()
    flash("Comment added!", "success")
    return redirect(url_for("view_post", post_id=post_id))

def get_comments_for_post(post_id):
    """
    Helper function to get all comments for a specific post.
    Used for displaying comments in various contexts.
    """
    db = get_db()
    comments = db.execute("""
        SELECT comments.text, comments.timestamp, users.username
        FROM comments
        JOIN users ON comments.user_id = users.id
        WHERE comments.post_id = ?
        ORDER BY comments.timestamp ASC
    """, (post_id,)).fetchall()
    db.close()
    return comments

@app.route("/delete/<int:post_id>", methods=["POST"])
def delete_post(post_id):
    """
    Delete a post (owner only).
    Removes the post, all its comments, likes, and the associated image file.
    Only the post owner can delete their posts.
    """
    # Check authentication
    user = current_user()
    if not user:
        flash("Login to delete posts.", "error")
        return redirect(url_for("login"))

    db = get_db()
    post = db.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
    
    # Validate post exists
    if not post:
        db.close()
        flash("Post not found.", "error")
        return redirect(url_for("index"))
    
    # Check ownership
    if post["user_id"] != user["id"]:
        db.close()
        flash("You can only delete your own posts.", "error")
        return redirect(url_for("index"))

    # Delete the associated image file
    try:
        remove_upload_file(post["image"])
    except Exception:
        # Silently handle file deletion errors
        pass

    # Delete all related data (cascade delete)
    db.execute("DELETE FROM likes WHERE post_id = ?", (post_id,))      # Remove all likes
    db.execute("DELETE FROM comments WHERE post_id = ?", (post_id,))   # Remove all comments
    db.execute("DELETE FROM posts WHERE id = ?", (post_id,))          # Remove the post
    db.commit()
    db.close()

    flash("Post deleted.", "success")
    return redirect(url_for("index"))

@app.route("/profile/<username>")
def profile(username=None):
    """
    Display a user's profile page with their posts.
    Shows user info, avatar, description, and all their posts.
    If no username provided, redirects to current user's profile.
    """
    # Handle case where no username is provided
    if username is None:
        user = current_user()
        if not user:
            return redirect(url_for("login"))
        return redirect(url_for("profile", username=user["username"]))

    db = get_db()
    
    # Get the profile user's information
    profile_user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if not profile_user:
        db.close()
        return "Error user not found.", 404
    
    # Get all posts by this user
    posts = db.execute("SELECT * FROM posts WHERE user_id = ? ORDER BY timestamp DESC", (profile_user["id"],)).fetchall()
    db.close()
    
    return render_template("profile.html", profile=profile_user, posts=posts, user=current_user())

@app.route("/profile/avatar", methods=["POST"])
def change_avatar():
    """
    Handle avatar upload/change for the current user.
    Processes the image, resizes it, and updates the user's avatar in the database.
    """
    # Check authentication
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    
    # Get uploaded avatar file
    avatar_file = request.files.get("avatar")
    if not avatar_file or avatar_file.filename == "":
        flash("No file selected.", "error")
        return redirect(url_for("profile", username=user["username"]))
    
    # Process and save the avatar
    avatar_path = save_avatar_file(avatar_file)
    if not avatar_path:
        flash("Invalid avatar file.", "error")
        return redirect(url_for("profile", username=user["username"]))
    
    # Update user's avatar in database
    db = get_db()
    db.execute("UPDATE users SET avatar = ? WHERE id = ?", (avatar_path, user["id"]))
    db.commit()
    db.close()
    
    flash("Avatar updated!", "success")
    return redirect(url_for("profile", username=user["username"]))

@app.route("/uploads/<filename>")
def uploaded_file(filename):
    """
    Serve uploaded image files to the browser.
    This route allows the frontend to display uploaded images.
    """
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route("/description", methods=["POST"])
def change_description():
    """
    Update user's profile description via AJAX.
    Validates length and updates the database.
    Returns JSON response for frontend updates.
    """
    # Check authentication
    user = current_user()
    if not user:
        return jsonify(success=False, error="Unauthorized"), 401

    # Get description from JSON request
    data = request.get_json() or {}
    description = (data.get("description") or "").strip()

    # Validate description length
    if len(description) > 1000:
        return jsonify(success=False, error="Description too long (max 1000 chars)."), 400

    # Update description in database
    db = get_db()
    db.execute("UPDATE users SET description = ? WHERE id = ?", (description, user["id"]))
    db.commit()
    db.close()
    
    return jsonify({"success": True, "description": description})

@app.route("/notifications", methods=["GET"])
def get_notifications():
    """
    Get all notifications for the current user.
    Returns JSON with notification data including post/comment details.
    Used by the notification sidebar to display recent activity.
    """
    # Check authentication
    user = current_user()
    if not user:
        return jsonify(success=False, error="Unauthorized"), 401

    db = get_db()
    
    # Complex query to get notifications with all related data
    notifications = db.execute("""
        SELECT n.id,
               n.type,                    -- 0=like, 1=dislike, 2=comment, 3=dm
               n.reference_id,           -- Post ID being referenced
               n.seen,                   -- Whether notification was read
               n.created_at,             -- When notification was created
               n.comment_id AS notif_comment_id,  -- Comment ID for comment notifications
               u.username AS maker_username,     -- Who triggered the notification
               u.avatar   AS maker_avatar,       -- Avatar of the notification maker
               p.id AS post_id,                 -- Post being referenced
               p.image AS post_image,            -- Post image
               c.id AS comment_row_id,          -- Comment details
               c.text AS comment_content         -- Comment text
        FROM notifications n
        JOIN users u ON n.maker_id = u.id        -- Get notification maker info
        LEFT JOIN posts p ON n.reference_id = p.id  -- Get post info
        LEFT JOIN comments c ON n.comment_id = c.id  -- Get comment info
        WHERE n.receiver_id = ?                   -- Only notifications for current user
        ORDER BY n.created_at DESC                -- Most recent first
    """, (user["id"],)).fetchall()
    db.close()

    # Format notifications for JSON response
    data = []
    for n in notifications:
        item = {
            "id": n["id"],
            "type": n["type"],
            "reference_id": n["reference_id"],
            "seen": bool(n["seen"]),
            "created_at": n["created_at"],
            "maker": {
                "username": n["maker_username"],
                "avatar": n["maker_avatar"]
            },
            "post": {
                "id": n["post_id"],
                "image": n["post_image"]
            }
        }

        # Add comment details for comment notifications
        if n["type"] == 2:  # comment notification
            item["comment"] = {
                "id": n["notif_comment_id"],
                "content": n["comment_content"]
            }

        data.append(item)

    return jsonify(success=True, notifications=data)


@app.route("/notifications/<int:notif_id>/seen", methods=["POST"])
def mark_notification_seen(notif_id):
    """
    Mark a specific notification as seen/read.
    Used when user clicks on a notification to mark it as read.
    Returns JSON response for frontend updates.
    """
    # Check authentication
    user = current_user()
    if not user:
        return jsonify(success=False, error="Unauthorized"), 401

    db = get_db()
    
    # Mark notification as seen (only for current user's notifications)
    cur = db.execute(
        "UPDATE notifications SET seen = 1 WHERE id = ? AND receiver_id = ?",
        (notif_id, user["id"])
    )
    db.commit()
    
    # Verify the update was successful
    # (rowcount may not be reliable, so we check the actual state)
    changed = db.execute("SELECT COUNT(1) AS cnt FROM notifications WHERE id = ? AND seen = 1", (notif_id,)).fetchone()["cnt"]
    db.close()

    if not changed:
        return jsonify(success=False, error="Not found or not allowed"), 404
    return jsonify(success=True)
# =============================================================================
# APPLICATION STARTUP
# =============================================================================

if __name__ == "__main__":
    """
    Start the Flask development server.
    - host="0.0.0.0" allows external connections (for testing on network)
    - port=8080 is the server port
    - debug=True enables auto-reload and detailed error pages
    """
    if sharingOnLocalNetwork:
        # For network access (development/testing):
        app.run(host="0.0.0.0", port=8080, debug=True)
    else:
        # For local development only:
        app.run(port=8080, debug=True)
