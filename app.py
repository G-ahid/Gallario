import os
import sqlite3
import uuid
from datetime import datetime
from flask import (
    Flask, render_template, request, redirect, url_for,
    session, send_from_directory, jsonify, flash, abort
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from PIL import Image

 

# -------- CONFIG --------
app = Flask(__name__)
app.secret_key = "03c7456gt529wd3p;98/.,x32xwxw62edfff5"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
AVATAR_FOLDER = os.path.join(BASE_DIR, "static", "avatars")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(AVATAR_FOLDER, exist_ok=True)

DB_PATH = os.path.join(BASE_DIR, "database.db")

# -------- DB HELPERS --------
def get_db():
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    conn.row_factory = sqlite3.Row
    # Enforce foreign key constraints
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
def ensure_likes_value_column(conn):
    """If likes table exists but lacks 'value' column, add it."""
    info = conn.execute("PRAGMA table_info(likes)").fetchall()
    cols = [r["name"] for r in info]
    if "value" not in cols:
        # add column (default like = 1)
        try:
            conn.execute("ALTER TABLE likes ADD COLUMN value INTEGER DEFAULT 1")
            conn.commit()
        except sqlite3.OperationalError:
            # If ALTER fails for some reason, ignore (older sqlite or locked)
            pass

def init_db():
    conn = get_db()
    cur = conn.cursor()
    # create core tables (posts/likes/users). likes has value column for like/dislike
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        avatar TEXT DEFAULT 'avatars/default.png',
        description Text DEFAULT 'No description set.'
    );

    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        maker_id INTEGER NOT NULL,         -- who triggered the notification
        receiver_id INTEGER NOT NULL,      -- who receives it
        type INTEGER NOT NULL,             -- 0=like, 1=dislike, 2=comment, 3=dm...
        reference_id INTEGER,              -- post_id, dm_id, etc.
        comment_id INTEGER,                -- new column for comment notifications
        seen BOOLEAN DEFAULT 0,            -- 0=unread, 1=read
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(maker_id) REFERENCES users(id),
        FOREIGN KEY(receiver_id) REFERENCES users(id),
        FOREIGN KEY(comment_id) REFERENCES comments(id)
    );

    CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        image TEXT,
        caption TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS likes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        post_id INTEGER,
        value INTEGER DEFAULT 1,
        UNIQUE(user_id, post_id),
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(post_id) REFERENCES posts(id)
    );

    CREATE TABLE IF NOT EXISTS dms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        reciever_id INTEGER,
        message_id INTEGER,
        value TEXT,
        UNIQUE(user_id, message_id),
        FOREIGN KEY(user_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        post_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        text TEXT NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(post_id) REFERENCES posts(id),
        FOREIGN KEY(user_id) REFERENCES users(id)
    );
    """)
    conn.commit()
    # ensure likes.value column exists (for older DBs)
    ensure_likes_value_column(conn)
    conn.commit()
    conn.close()

init_db()

# -------- HELPERS --------
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
    db.close()
    return user

def crop_to_square(img):
    """Crop image to a centered square before resizing."""
    width, height = img.size
    min_dim = min(width, height)
    left = (width - min_dim) / 2
    top = (height - min_dim) / 2
    right = (width + min_dim) / 2
    bottom = (height + min_dim) / 2
    return img.crop((left, top, right, bottom))

def save_avatar_file(file_storage):
    if not file_storage or file_storage.filename == "":
        return None
    if not allowed_file(file_storage.filename):
        return None

    # Make sure avatars folder exists
    os.makedirs(AVATAR_FOLDER, exist_ok=True)

    # Create a unique png filename
    unique_name = f"{uuid.uuid4().hex}.png"
    full_path = os.path.join(AVATAR_FOLDER, unique_name)

    # Open image from the FileStorage stream
    img = Image.open(file_storage.stream)
    # Convert to RGB to avoid issues with alpha/transparency if you want opaque avatars.
    img = img.convert("RGB")
    img = crop_to_square(img)
    img = img.resize((256, 256), Image.LANCZOS)
    # Save as PNG (consistent file type)
    img.save(full_path, format="PNG", optimize=True)

    # Return a relative path that matches how you store avatars in DB
    return f"avatars/{unique_name}"


    return f"avatars/{unique}"  # Relative path to use with url_for

def save_upload_file(file_storage):
    if not file_storage or file_storage.filename == "":
        return None
    if not allowed_file(file_storage.filename):
        return None
    filename = secure_filename(file_storage.filename)
    unique = f"{uuid.uuid4().hex}_{filename}"
    full_path = os.path.join(UPLOAD_FOLDER, unique)
    file_storage.save(full_path)
    return unique

def remove_upload_file(stored_filename):
    try:
        path = os.path.join(UPLOAD_FOLDER, stored_filename)
        if os.path.exists(path):
            os.remove(path)
            return True
    except Exception:
        pass
    return False

# -------- ROUTES --------

@app.route("/")
@app.route("/")
def index():
    db = get_db()
    user_id = session.get("user_id")

    page = int(request.args.get("page", 1))
    per_page = 5
    offset = (page - 1) * per_page

    posts = db.execute("""
        SELECT posts.id, posts.image, posts.caption, posts.timestamp, posts.user_id,
               users.username, users.avatar,
               COALESCE((SELECT COUNT(*) FROM likes WHERE likes.post_id = posts.id AND likes.value = 1),0) AS like_count,
               COALESCE((SELECT COUNT(*) FROM likes WHERE likes.post_id = posts.id AND likes.value = -1),0) AS dislike_count,
               COALESCE((SELECT value FROM likes WHERE likes.post_id = posts.id AND likes.user_id = ?), 0) AS user_vote,
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
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        db.close()
        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            return redirect(url_for("index"))
        else:
            flash("Invalid username or password", "error")
    return render_template("login.html", register=False, user=current_user())

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password_raw = request.form.get("password", "")
        avatar_file = request.files.get("avatar")

        if username == "" or password_raw == "":
            flash("Username and password required.", "error")
            return redirect(url_for("register"))

        avatar_path = save_avatar_file(avatar_file) if avatar_file else None
        if not avatar_path:
            avatar_path = 'avatars/default.png'

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
            db.close()
            flash("Username already taken.", "error")
            return redirect(url_for("register"))

    return render_template("login.html", register=True, user=current_user())

@app.route("/upload", methods=["POST"])
def upload():
    user = current_user()
    if not user:
        return redirect(url_for("login"))

    file = request.files.get("photo")
    if not file:
        flash("No file uploaded.", "error")
        return redirect(url_for("index"))

    if not allowed_file(file.filename):
        flash("Invalid file type.", "error")
        return redirect(url_for("index"))

    stored_filename = save_upload_file(file)
    if not stored_filename:
        flash("Failed to save file.", "error")
        return redirect(url_for("index"))

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

# Like (toggle) -> sets value = 1 or removes if already liked
@app.route("/like/<int:post_id>", methods=["POST"])
def like(post_id):
    user = current_user()
    if not user:
        return jsonify(success=False), 401

    db = get_db()

    # Get the post (for notifications)
    post = db.execute("SELECT user_id FROM posts WHERE id=?", (post_id,)).fetchone()
    if not post:
        return jsonify(success=False, error="Post not found"), 404

    existing = db.execute("SELECT * FROM likes WHERE user_id=? AND post_id=?", 
                          (user["id"], post_id)).fetchone()

    if existing:
        if existing["value"] == 1:
            # Unlike (remove like)
            db.execute("DELETE FROM likes WHERE id=?", (existing["id"],))
        else:
            # Switch dislike → like
            db.execute("UPDATE likes SET value=1 WHERE id=?", (existing["id"],))

            # Add notification (if not self-like)
            if post["user_id"] != user["id"]:
                db.execute("""
                    INSERT INTO notifications (maker_id, receiver_id, type, reference_id)
                    VALUES (?, ?, ?, ?)
                """, (user["id"], post["user_id"], 0, post_id))  # type 0 = like
    else:
        # First time like
        db.execute("INSERT INTO likes (user_id, post_id, value) VALUES (?, ?, 1)", 
                   (user["id"], post_id))

        # Add notification
        if post["user_id"] != user["id"]:
            db.execute("""
                INSERT INTO notifications (maker_id, receiver_id, type, reference_id)
                VALUES (?, ?, ?, ?)
            """, (user["id"], post["user_id"], 0, post_id))  # type 0 = like

    db.commit()

    # Updated counts
    like_count = db.execute("SELECT COUNT(*) FROM likes WHERE post_id=? AND value=1", 
                            (post_id,)).fetchone()[0]
    dislike_count = db.execute("SELECT COUNT(*) FROM likes WHERE post_id=? AND value=-1", 
                               (post_id,)).fetchone()[0]
    db.close()

    return jsonify(success=True, like_count=like_count, dislike_count=dislike_count)

# Dislike (toggle) -> sets value = -1 or removes if already disliked
@app.route("/dislike/<int:post_id>", methods=["POST"])
def dislike(post_id):
    user = current_user()
    if not user:
        return jsonify(success=False), 401

    value = int(request.form.get("value", 1))  # 1=like, -1=dislike
    db = get_db()

    post = db.execute("SELECT user_id FROM posts WHERE id=?", (post_id,)).fetchone()
    if not post:
        return jsonify(success=False, error="Post not found"), 404

    existing = db.execute("SELECT * FROM likes WHERE user_id=? AND post_id=?", 
                          (user["id"], post_id)).fetchone()

    if existing:
        if existing["value"] == value:
            # Undo reaction
            db.execute("DELETE FROM likes WHERE id=?", (existing["id"],))
        else:
            # Switch reaction
            db.execute("UPDATE likes SET value=? WHERE id=?", (value, existing["id"]))
    else:
        # New reaction
        db.execute("INSERT INTO likes (user_id, post_id, value) VALUES (?, ?, ?)", 
                   (user["id"], post_id, value))

        # Add notification if it's a like
        if value == 1 and post["user_id"] != user["id"]:
            db.execute("""
                INSERT INTO notifications (maker_id, receiver_id, type, reference_id)
                VALUES (?, ?, ?, ?)
            """, (user["id"], post["user_id"], 0, post_id))  # type 0 = like
        elif value == -1 and post["user_id"] != user["id"]:
            db.execute("""
                INSERT INTO notifications (maker_id, receiver_id, type, reference_id)
                VALUES (?, ?, ?, ?)
            """, (user["id"], post["user_id"], 1, post_id))  # type 1 = dislike

    db.commit()

    like_count = db.execute("SELECT COUNT(*) FROM likes WHERE post_id=? AND value=1", (post_id,)).fetchone()[0]
    dislike_count = db.execute("SELECT COUNT(*) FROM likes WHERE post_id=? AND value=-1", (post_id,)).fetchone()[0]
    db.close()

    return jsonify(success=True, like_count=like_count, dislike_count=dislike_count)


# View single post + comments
@app.route("/post/<int:post_id>")
def view_post(post_id):
    db = get_db()
    post = db.execute("""
        SELECT posts.*, users.username, users.avatar
        FROM posts JOIN users ON posts.user_id = users.id
        WHERE posts.id = ?
    """, (post_id,)).fetchone()
    if not post:
        db.close()
        return "Post not found", 404

    comments = db.execute("""
        SELECT comments.*, users.username, users.avatar
        FROM comments JOIN users ON comments.user_id = users.id
        WHERE comments.post_id = ?
        ORDER BY comments.timestamp ASC
    """, (post_id,)).fetchall()


    like_count = db.execute("SELECT COUNT(*) AS c FROM likes WHERE post_id = ? AND value = 1", (post_id,)).fetchone()["c"]
    dislike_count = db.execute("SELECT COUNT(*) AS c FROM likes WHERE post_id = ? AND value = -1", (post_id,)).fetchone()["c"]

    user_vote_row = None
    user_vote = 0
    uid = session.get("user_id")
    if uid:
        user_vote_row = db.execute("SELECT value FROM likes WHERE post_id = ? AND user_id = ?", (post_id, uid)).fetchone()
        if user_vote_row:
            user_vote = user_vote_row["value"] or 0

    db.close()
    return render_template("post.html", post=post, comments=comments, like_count=like_count, dislike_count=dislike_count, user_vote=user_vote, user=current_user())

# Add comment
@app.route("/comment/<int:post_id>", methods=["POST"])
def add_comment(post_id):
    user = current_user()
    if not user:
        flash("Login to comment.", "error")
        return redirect(url_for("login"))

    text = request.form.get("comment", "").strip()
    if text == "":
        flash("Comment cannot be empty.", "error")
        return redirect(url_for("view_post", post_id=post_id))
        
    db = get_db()
    cur = db.execute(
        "INSERT INTO comments (post_id, user_id, text) VALUES (?, ?, ?)",
        (post_id, user["id"], text)
    )
    comment_id = cur.lastrowid
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

# Delete post (owner only)
@app.route("/delete/<int:post_id>", methods=["POST"])
def delete_post(post_id):
    user = current_user()
    if not user:
        flash("Login to delete posts.", "error")
        return redirect(url_for("login"))

    db = get_db()
    post = db.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
    if not post:
        db.close()
        flash("Post not found.", "error")
        return redirect(url_for("index"))
    if post["user_id"] != user["id"]:
        db.close()
        flash("You can only delete your own posts.", "error")
        return redirect(url_for("index"))

    # delete file
    try:
        remove_upload_file(post["image"])
    except Exception:
        pass

    db.execute("DELETE FROM likes WHERE post_id = ?", (post_id,))
    db.execute("DELETE FROM comments WHERE post_id = ?", (post_id,))
    db.execute("DELETE FROM posts WHERE id = ?", (post_id,))
    db.commit()
    db.close()

    flash("Post deleted.", "success")
    return redirect(url_for("index"))

@app.route("/profile/")
@app.route("/profile/<username>")
def profile(username=None):
    if username is None:
        user = current_user()
        if not user:
            return redirect(url_for("login"))
        return redirect(url_for("profile", username=user["username"]))

    db = get_db()
    profile_user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if not profile_user:
        db.close()
        return "Error user not found.", 404
    posts = db.execute("SELECT * FROM posts WHERE user_id = ? ORDER BY timestamp DESC", (profile_user["id"],)).fetchall()
    db.close()
    return render_template("profile.html", profile=profile_user, posts=posts, user=current_user())

@app.route("/profile/avatar", methods=["POST"])
def change_avatar():
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    avatar_file = request.files.get("avatar")
    if not avatar_file or avatar_file.filename == "":
        flash("No file selected.", "error")
        return redirect(url_for("profile", username=user["username"]))
    avatar_path = save_avatar_file(avatar_file)
    if not avatar_path:
        flash("Invalid avatar file.", "error")
        return redirect(url_for("profile", username=user["username"]))
    db = get_db()
    db.execute("UPDATE users SET avatar = ? WHERE id = ?", (avatar_path, user["id"]))
    db.commit()
    db.close()
    flash("Avatar updated!", "success")
    return redirect(url_for("profile", username=user["username"]))

# Serve uploads (images posted)
@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route("/description", methods=["POST"])
def change_description():
    user = current_user()
    if not user:
        return jsonify(success=False, error="Unauthorized"), 401

    data = request.get_json() or {}
    description = (data.get("description") or "").strip()

    # Basic validation
    if len(description) > 1000:
        return jsonify(success=False, error="Description too long (max 1000 chars)."), 400

    db = get_db()
    db.execute("UPDATE users SET description = ? WHERE id = ?", (description, user["id"]))
    db.commit()
    db.close()
    return jsonify({"success": True, "description": description})

@app.route("/notifications", methods=["GET"])
def get_notifications():
    user = current_user()
    if not user:
        return jsonify(success=False, error="Unauthorized"), 401

    db = get_db()
    notifications = db.execute("""
        SELECT n.id,
               n.type,
               n.reference_id,
               n.seen,
               n.created_at,
               n.comment_id AS notif_comment_id,
               u.username AS maker_username,
               u.avatar   AS maker_avatar,
               p.id AS post_id,
               p.image AS post_image,
               c.id AS comment_row_id,
               c.text AS comment_content
        FROM notifications n
        JOIN users u ON n.maker_id = u.id
        LEFT JOIN posts p ON n.reference_id = p.id
        LEFT JOIN comments c ON n.comment_id = c.id
        WHERE n.receiver_id = ?
        ORDER BY n.created_at DESC
    """, (user["id"],)).fetchall()
    db.close()

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

        if n["type"] == 2:  # comment
            item["comment"] = {
                "id": n["notif_comment_id"],   # the ID stored on notification row
                "content": n["comment_content"]
            }

        data.append(item)

    return jsonify(success=True, notifications=data)

@app.route("/notifications/<int:notif_id>/seen", methods=["POST"])
def mark_notification_seen(notif_id):
    user = current_user()
    if not user:
        return jsonify(success=False, error="Unauthorized"), 401

    db = get_db()
    cur = db.execute(
        "UPDATE notifications SET seen = 1 WHERE id = ? AND receiver_id = ?",
        (notif_id, user["id"])
    )
    db.commit()
    # cur.rowcount may or may not be reliable depending on DB driver; check if row existed:
    changed = db.execute("SELECT COUNT(1) AS cnt FROM notifications WHERE id = ? AND seen = 1", (notif_id,)).fetchone()["cnt"]
    db.close()

    if not changed:
        return jsonify(success=False, error="Not found or not allowed"), 404
    return jsonify(success=True)
# Start server
if __name__ == "__main__":
    #app.run(port=8080, debug=True)
    app.run(host="0.0.0.0", port=8080, debug=True)