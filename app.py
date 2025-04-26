import os, io, tempfile, subprocess
from flask import Flask, render_template, request, send_file, jsonify, redirect, url_for, flash
import requests
from dotenv import load_dotenv
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('tts-web')
logger.setLevel(logging.INFO)

# Create handlers
console_handler = logging.StreamHandler()
file_handler = RotatingFileHandler('tts-web.log', maxBytes=10000000, backupCount=5)

# Create formatters and add it to handlers
log_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(log_format)
file_handler.setFormatter(log_format)

# Add handlers to the logger
logger.addHandler(console_handler)
logger.addHandler(file_handler)

load_dotenv()
API_KEY = os.getenv("OPENAI_API_KEY")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "password")

if not API_KEY:
    logger.error("Missing OPENAI_API_KEY in .env")
    raise RuntimeError("Missing OPENAI_API_KEY in .env")

app = Flask(
    __name__,
    static_folder="static",
    template_folder="templates"
)
app.secret_key = os.getenv("FLASK_SECRET_KEY", os.urandom(24))

# Login manager configuration
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Simple User class
class User(UserMixin):
    def __init__(self, username):
        self.id = username

@login_manager.user_loader
def load_user(username):
    if username == ADMIN_USERNAME:
        return User(username)
    return None

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            login_user(User(username))
            logger.info(f"Successful login for user: {username}")
            return redirect(url_for('index'))
        
        logger.warning(f"Failed login attempt for username: {username}")
        return render_template('login.html', error="Invalid credentials")
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    logger.info("User logged out")
    return redirect(url_for('login'))

@app.route("/")
@login_required
def index():
    logger.info("Serving index page")
    return render_template("index.html")

@app.route("/api/tts", methods=["POST"])
@login_required
def tts():
    data = request.get_json() or {}
    text = data.get("text", "").strip()
    if not text:
        logger.warning("TTS request received with no text")
        return jsonify({"error": "No text provided"}), 400

    # build payload
    payload = {
        "model": data.get("model", "gpt-4o-mini-tts"),
        "input": text,
        "voice": data.get("voice", "coral"),
        "instructions": data.get("instructions", ""),
        "speed": data.get("speed", 1.0)
    }
    logger.info(f"Processing TTS request with payload: {payload}")

    # call OpenAI
    try:
        resp = requests.post(
            "https://api.openai.com/v1/audio/speech",
            json=payload,
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json"
            },
            timeout=300
        )
        if not resp.ok:
            logger.error(f"OpenAI API error: {resp.status_code} - {resp.text}")
            return jsonify(resp.json()), resp.status_code
        
        logger.info("Successfully received audio from OpenAI")
        raw_mp3 = resp.content
    except Exception as e:
        logger.error(f"Error calling OpenAI API: {str(e)}")
        return jsonify({"error": "Failed to generate audio"}), 500

    # server-side pause injection?
    pause = float(data.get("pause", 0))
    if pause > 0:
        logger.info(f"Applying pause of {pause} seconds")
        # write input to temp file
        try:
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as in_f:
                in_f.write(raw_mp3)
                in_path = in_f.name

            # calculate ms and run ffmpeg (adelay)
            ms = int(pause * 1000)
            cmd = [
                "ffmpeg", "-y", "-i", in_path,
                "-af", f"adelay={ms}|{ms}",
                "-f", "mp3", "pipe:1"
            ]
            try:
                proc = subprocess.run(
                    cmd,
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL
                )
                final_mp3 = proc.stdout
                logger.info("Successfully applied pause using ffmpeg")
            except Exception as e:
                logger.error(f"FFmpeg processing failed: {str(e)}")
                # if ffmpeg fails, fallback to original
                final_mp3 = raw_mp3
            finally:
                os.unlink(in_path)
        except Exception as e:
            logger.error(f"Error during pause processing: {str(e)}")
            final_mp3 = raw_mp3
    else:
        final_mp3 = raw_mp3

    # send back
    logger.info("Sending audio file to client")
    return send_file(
        io.BytesIO(final_mp3),
        mimetype="audio/mpeg",
        as_attachment=True,
        download_name="tts.mp3"
    )

if __name__ == "__main__":
    port = int(os.getenv("FLASK_RUN_PORT", 3000))
    logger.info(f"Starting server on port {port}")
    app.run(host="0.0.0.0", port=port)
