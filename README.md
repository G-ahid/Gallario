# 📸 ImageServer - Social Media Image Sharing Platform

[![Python](https://img.shields.io/badge/Python-3.7+-blue.svg)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-2.0+-green.svg)](https://flask.palletsprojects.com)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A modern, feature-rich social media platform built with Flask that allows users to share images, interact with posts, and connect with others through a clean, responsive interface.

## ✨ Features

### 🔐 User Management
- **Secure Registration & Login** - Password hashing with Werkzeug
- **Profile Customization** - Upload avatars and edit descriptions
- **Session Management** - Secure user authentication

### 📱 Core Functionality
- **Image Upload** - Support for PNG, JPG, JPEG, GIF formats
- **Post Feed** - Paginated timeline with latest posts first
- **Interactive Posts** - Like/dislike system with real-time updates
- **Comments System** - Engage with posts through threaded comments

### 🔔 Notifications
- **Real-time Notifications** - Get notified for likes, dislikes, and comments
- **Interactive Sidebar** - Slide-out notification panel
- **Mark as Read** - Click to mark notifications as seen

### 🎨 User Experience
- **Responsive Design** - Works on desktop and mobile devices
- **Dark Theme** - Modern, eye-friendly interface
- **Image Processing** - Automatic avatar cropping and resizing
- **File Management** - Secure file uploads with validation

## 🚀 Quick Start

### Prerequisites
- Python 3.7 or higher
- pip (Python package installer)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/ImageServer.git
   cd ImageServer
   ```

2. **Create a virtual environment** (recommended)
   ```bash
   python -m venv venv
   
   # On Windows
   venv\Scripts\activate
   
   # On macOS/Linux
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application**
   ```bash
   python app.py
   ```

5. **Open your browser**
   Navigate to `http://localhost:8080`

## Or if you have Linux(very cool)
just run this in whatever folder you want :
```
sudo apt update
sudo apt install python3
sudo apt install python3-flask
sudo apt install python3-pillow
sudo apt install python3-werkzeug
git clone https://github.com/yourusername/ImageServer.git
cd ImageServer
python3 app.py
```
Then you can see the ip adress on the terminal, type the same thing into any other device that is also connected to the same network.
## Requirement
Have Python and download all the libraries from `requirements.txt` file.

##  Project Structure

```
ImageServer/
├── app.py               # Main Flask application
├── database.db          # SQLite database (auto-created)
├── requirements.txt     # Python dependencies
├── README.md            # This file
├── static/              # Static assets
│   ├── styles.css       # Main stylesheet
│   ├── code.js          # JavaScript functionality
│   ├── logo.png         # Application logo
│   ├── Biome.ttf        # Custom font
│   ├── avatars/         # User profile pictures
│   └── uploads/         # User uploaded images
└── templates/           # HTML templates
    ├── index.html       # Main feed page
    ├── login.html       # Login/register page
    ├── post.html        # Individual post view
    ├── profile.html     # User profile page
    ├── layout.html      # Base template (Bootstrap)
    └── side.html        # Notification sidebar
```

## Database Schema

The application uses SQLite with the following tables:

- **users** - User accounts and profiles
- **posts** - Image posts with captions
- **likes** - User reactions (like/dislike system)
- **comments** - Post comments
- **notifications** - User notifications(not implemented yet)
- **dms** - Direct messages (future feature)

## 🔧 Configuration

### Ternimal Running
Edit `app.py` to control network access:

```bash
python3 app.py --port 5000 --notlan
```
```
options:
  -h, --help   show this help message and exit
  --port PORT  Port number to run on the web app.
  --notlan     Set it to True if you want to test it on other devices that
               are also connected to the local network.
```


### Security
- Change the `app.secret_key` in production
- Use environment variables for sensitive data
- Consider using HTTPS in production

### For Users
1. **Register** - Create a new account with username and password
2. **Login** - Access your account
3. **Upload** - Share images with captions
4. **Interact** - Like, dislike, and comment on posts
5. **Customize** - Update your profile and avatar
6. **Stay Updated** - Check notifications for activity

### For Developers
- **Modular Design** - Easy to extend with new features
- **Clean Code** - Well-commented and documented
- **Database Migrations** - Automatic schema updates
- **Error Handling** - Graceful error management

## Development

### Adding New Features
1. Create new routes in `app.py`
2. Add corresponding templates in `templates/`
3. Update database schema if needed
4. Add JavaScript functionality in `static/code.js`

### Database Modifications
The app automatically handles database migrations. For new tables:
1. Add table creation in `init_db()` function
2. The app will create tables on startup

## Troubleshooting

### Common Issues

**Port already in use**
Kill the Python... in Terminal.

**Database errors**
```bash
# Delete database.db to reset
rm database.db
```

**File upload issues**
- Check file permissions on `static/uploads/` and `static/avatars/`
- Ensure allowed file extensions match your uploads

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Author(me)

**Nezar Bahid**
- Email: n.bahid@aui.ma
- Institution: Al Akhawayn University (AUI)

## Acknowledgments

- Flask community for the excellent framework
- Contributors and testers(Chatgpt and Cursor and maybe Gemini)
- Open source libraries used in this project

---

⭐ **Star this repository if you found it helpful!**

📧 **Contact me for questions or collaboration opportunities.**