# =============================================================================
# Gallraio - THE IMAGE SHARING APPLICATION - FLASK WEB APP                    =
# =============================================================================
# This is a social media-style image sharing application built with Flask.
# Features: User registration/login, image uploads, likes/dislikes, comments,
# notifications, and user profiles with editable descriptions.

# Made by Nezar Bahid @ AUI 
# =============================================================================
from src.Routing import *

# =============================================================================
# APPLICATION STARTUP                                                         =
# =============================================================================
app.register_blueprint(main_bp)
if __name__ == "__main__":
    """
    Start the Flask development server.
    - host="0.0.0.0" allows external connections (for testing on network) also can be turned off in terminal
    - port=8080 is the server port unless changed on the Terminal
    - debug=True enables auto-reload and detailed error pages
    """
    if arg.notlan:
        # For network access (development/testing):
        app.run(host="0.0.0.0", port=arg.port, debug=True)
    else:
        # For local development only:
        app.run(port=arg.port, debug=True)
