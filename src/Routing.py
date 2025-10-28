import sqlite3                # Database operations
from datetime import datetime # Date/time handling

# Flask framework imports
from flask import (
    render_template, request, redirect, url_for,
    session, send_from_directory, jsonify, flash, Blueprint
)

# Security and file handling imports
from werkzeug.security import generate_password_hash, check_password_hash  # Password hashing
from werkzeug.utils import secure_filename  # Secure file name handling
from PIL import Image  # Image processing (resize, crop, etc.)
 
from src.Config import *
from src.Helpers import *


# =============================================================================
# FLASK ROUTES - WEB PAGES AND API ENDPOINTS
# =============================================================================

main_bp = Blueprint("main", __name__, url_prefix="")

@main_bp.route("/")
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

@main_bp.route("/login", methods=["GET", "POST"])
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
            return redirect(url_for("main.index"))
        else:
            flash("Invalid username or password", "error")
    
    # Show login form (GET request or failed POST)
    return render_template("login.html", register=False, user=current_user())

@main_bp.route("/logout")
def logout():
    """
    Log out the current user by clearing the session.
    Redirects to login page.
    """
    session.clear()  # Remove all session data
    return redirect(url_for("main.login"))

@main_bp.route("/register", methods=["GET", "POST"])
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
            avatar_path = './avatars/default.png'  # Use default avatar

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
            return redirect(url_for("main.login"))
        except sqlite3.IntegrityError:
            # Username already exists
            db.close()
            flash("Username already taken.", "error")
            return redirect(url_for("register"))

    # Show registration form (GET request or failed POST)
    return render_template("login.html", register=True, user=current_user())

@main_bp.route("/upload", methods=["POST"])
def upload():
    """
    Handle image uploads for new posts.
    Requires user to be logged in.
    Validates file type and saves to database.
    """
    # Check if user is logged in
    user = current_user()
    if not user:
        return redirect(url_for("main.login"))

    # Get uploaded file
    file = request.files.get("photo")
    if not file:
        flash("No file uploaded.", "error")
        return redirect(url_for("main.index"))

    # Validate file type
    if not allowed_file(file.filename):
        flash("Invalid file type.", "error")
        return redirect(url_for("main.index"))

    # Save the file
    stored_filename = save_upload_file(file)
    if not stored_filename:
        flash("Failed to save file.", "error")
        return redirect(url_for("main.index"))

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
    return redirect(url_for("main.index"))

@main_bp.route("/like/<int:post_id>", methods=["POST"])
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

@main_bp.route("/dislike/<int:post_id>", methods=["POST"])
def dislike(post_id):
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
        if existing["value"] == -1:
            # User already disliked - remove the dislike (undislike)
            db.execute("DELETE FROM likes WHERE id=?", (existing["id"],))
        else:
            # User liked - change to dislike
            db.execute("UPDATE likes SET value=-1 WHERE id=?", (existing["id"],))

            # Send notification to post owner (if not self-like)
            if post["user_id"] != user["id"]:
                db.execute("""
                    INSERT INTO notifications (maker_id, receiver_id, type, reference_id)
                    VALUES (?, ?, ?, ?)
                """, (user["id"], post["user_id"], 1, post_id))  # type 1 = dislike
    else:
        # First time reaction - add like
        db.execute("INSERT INTO likes (user_id, post_id, value) VALUES (?, ?, -1)", 
                   (user["id"], post_id))

        # Send notification to post owner (if not self-like)
        if post["user_id"] != user["id"]:
            db.execute("""
                INSERT INTO notifications (maker_id, receiver_id, type, reference_id)
                VALUES (?, ?, ?, ?)
            """, (user["id"], post["user_id"], 1, post_id))  # type 1 = dislike

    db.commit()

    # Get updated reaction counts
    like_count = db.execute("SELECT COUNT(*) FROM likes WHERE post_id=? AND value=1", 
                            (post_id,)).fetchone()[0]
    dislike_count = db.execute("SELECT COUNT(*) FROM likes WHERE post_id=? AND value=-1", 
                               (post_id,)).fetchone()[0]
    db.close()

    # Return JSON response for AJAX
    return jsonify(success=True, like_count=like_count, dislike_count=dislike_count)



@main_bp.route("/post/<int:post_id>")
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

@main_bp.route("/comment/<int:post_id>", methods=["POST"])
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
        return redirect(url_for("main.login"))

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

@main_bp.route("/delete/<int:post_id>", methods=["POST"])
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
        return redirect(url_for("main.login"))

    db = get_db()
    post = db.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
    
    # Validate post exists
    if not post:
        db.close()
        flash("Post not found.", "error")
        return redirect(url_for("main.index"))
    
    # Check ownership
    if post["user_id"] != user["id"]:
        db.close()
        flash("You can only delete your own posts.", "error")
        return redirect(url_for("main.index"))

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
    return redirect(url_for("main.index"))

@main_bp.route("/profile/<username>")
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
            return redirect(url_for("main.login"))
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

@main_bp.route("/profile/avatar", methods=["POST"])
def change_avatar():
    """
    Handle avatar upload/change for the current user.
    Processes the image, resizes it, and updates the user's avatar in the database.
    """
    # Check authentication
    user = current_user()
    if not user:
        return redirect(url_for("main.login"))
    
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

@main_bp.route("/uploads/<filename>")
def uploaded_file(filename):
    """
    Serve uploaded image files to the browser.
    This route allows the frontend to display uploaded images.
    """
    return send_from_directory(UPLOAD_FOLDER, filename)

@main_bp.route("/description", methods=["POST"])
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

@main_bp.route("/notifications", methods=["GET"])
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


@main_bp.route("/notifications/<int:notif_id>/seen", methods=["POST"])
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