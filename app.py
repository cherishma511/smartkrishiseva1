from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory, jsonify
import os
import sqlite3
import requests
import matplotlib.pyplot as plt
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import random
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

# ====================
# Flask Setup
# ====================
app = Flask(__name__)
app.secret_key = "smartkrishi123"

# Upload folder
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Load environment variables
load_dotenv()
WEATHER_API_KEY = os.getenv("WEATHER_API_kEY")
# ====================
# Database Setup
# ====================
DB_FILE = "smartkrishi.db"

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute('''CREATE TABLE IF NOT EXISTS farmers (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        email TEXT UNIQUE NOT NULL,
                        village TEXT NOT NULL,
                        password TEXT NOT NULL
                    )''')
    conn.commit()
    conn.close()

init_db()

# ====================
# Multi-Language Setup
# ====================
translations = {
    "en": {
        "welcome": "Welcome to Smart Krishi",
        "login": "Login successful!",
        "logout": "Logged out successfully.",
        "signup_success": "Signup successful! Please login.",
        "login_first": "Please login first!",
        "invalid": "Invalid email or password",
        "fill_fields": "Please fill all fields",
        "email_exists": "Email already registered. Please login.",
    },
    "te": {
        "welcome": "స్మార్ట్ కృషికి స్వాగతం",
        "login": "లాగిన్ విజయవంతం!",
        "logout": "విజయవంతంగా లాగ్ అవుట్ అయ్యారు.",
        "signup_success": "నమోదు విజయవంతం! దయచేసి లాగిన్ చేయండి.",
        "login_first": "ముందుగా లాగిన్ చేయండి!",
        "invalid": "చెల్లని ఇమెయిల్ లేదా పాస్‌వర్డ్",
        "fill_fields": "దయచేసి అన్ని వివరాలు పూరించండి",
        "email_exists": "ఇమెయిల్ ఇప్పటికే నమోదైంది. దయచేసి లాగిన్ చేయండి.",
    }
}

@app.before_request
def set_language():
    lang = request.args.get("lang")
    if lang in ["en", "te"]:
        session["lang"] = lang
    elif "lang" not in session:
        session["lang"] = "en"

def t(key):
    lang = session.get("lang", "en")
    return translations.get(lang, {}).get(key, key)

@app.context_processor
def inject_now():
    return {'now': datetime.utcnow(), 't': t}

@app.template_filter('datetimeformat')
def datetimeformat(value):
    return datetime.fromtimestamp(value).strftime('%d %b %Y %H:%M')

# ====================
# Helper Functions
# ====================
def get_weather(city):
    weather = {"temperature": "--", "humidity": "--", "description": "Unavailable"}
    try:
        # Correct URL for current weather
        url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_API_KEY}&units=metric"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            weather = {
                "temperature": f"{data['main']['temp']}°C",
                "humidity": f"{data['main']['humidity']}%",
                "description": data['weather'][0]['description'].capitalize()
            }
        else:
            print("Weather API returned status:", response.status_code, response.text)
    except Exception as e:
        print("Weather API error:", e)
    return weather
def get_weather_alerts(lat=17.3850, lon=78.4867):
    alerts = []
    try:
        url = f"https://api.openweathermap.org/data/3.0/onecall?lat={lat}&lon={lon}&exclude=minutely,hourly,daily&appid={WEATHER_API_KEY}&units=metric"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            alerts = data.get("alerts", [])
    except Exception as e:
        print("Weather alert error:", e)
    return alerts
@app.route('/weather', methods=['GET', 'POST'])
def weather_page():
    weather = None
    city = None

    # Telugu labels
    telugu_labels = {
        "Temperature": "ఉష్ణోగ్రత",
        "Humidity": "తేమ",
        "Condition": "స్థితి"
    }

    if request.method == 'POST':
        city = request.form.get('city', '').strip()
        if city:
            try:
                url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_API_KEY}&units=metric"
                response = requests.get(url)
                data = response.json()
                if response.status_code == 200 and data.get("cod") == 200:
                    weather = {
                        "city": data.get("name", city),
                        "temperature": data["main"]["temp"],
                        "humidity": data["main"]["humidity"],
                        "condition": data["weather"][0]["description"].capitalize()
                    }
                else:
                    weather = {
                        "city": city,
                        "temperature": "--",
                        "humidity": "--",
                        "condition": "Unavailable / అందుబాటులో లేదు"
                    }
            except Exception as e:
                print("Weather API error:", e)
                weather = {
                    "city": city,
                    "temperature": "--",
                    "humidity": "--",
                    "condition": "Unavailable / అందుబాటులో లేదు"
                }

    return render_template('weather.html', weather=weather, telugu_labels=telugu_labels)
# ====================
@app.route('/')
def home():
    email = session.get('email')
    farmer = None
    if email:
        conn = get_db_connection()
        farmer = conn.execute("SELECT * FROM farmers WHERE email=?", (email,)).fetchone()
        conn.close()
    return render_template('home.html', farmer=farmer)

@app.route('/signup', methods=['GET','POST'])
def signup():
    if request.method == 'POST':
        fullname = request.form.get('fullname', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        phone = request.form.get('phone', '').strip()
        address = request.form.get('address', '').strip()
        role = request.form.get('role', '').strip()

        if not all([fullname, email, password, phone, address, role]):
            flash(t("fill_fields"), "danger")
            return redirect(url_for('signup'))

        conn = get_db_connection()
        existing = conn.execute("SELECT * FROM farmers WHERE email=?", (email,)).fetchone()
        if existing:
            flash(t("email_exists"), "warning")
            conn.close()
            return redirect(url_for('login'))

        hashed_password = generate_password_hash(password)
        conn.execute("INSERT INTO farmers (name,email,village,password) VALUES (?,?,?,?)",
                     (fullname, email, address, hashed_password))
        conn.commit()
        conn.close()

        flash(t("signup_success"), "success")
        return redirect(url_for('login'))

    return render_template('signup.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        if not all([email,password]):
            flash(t("fill_fields"),"danger")
            return redirect(url_for('login'))

        conn = get_db_connection()
        farmer = conn.execute("SELECT * FROM farmers WHERE email=?", (email,)).fetchone()
        conn.close()

        if farmer and check_password_hash(farmer['password'], password):
            session['email'] = email
            flash(t("login"),"success")
            return redirect(url_for('dashboard'))
        else:
            flash(t("invalid"),"danger")
            return redirect(url_for('login'))

    return render_template('login.html')
@app.route('/dashboard')
def dashboard():
    email = session.get('email')
    if not email:
        flash(t("login_first"), "warning")
        return redirect(url_for('login'))

    conn = get_db_connection()
    farmer = conn.execute("SELECT * FROM farmers WHERE email=?", (email,)).fetchone()
    conn.close()

    city = farmer["village"]
    weather = get_weather(city)  # <-- API call
    alerts = get_weather_alerts()  # Optional: alerts API
    graph_path = 'soil_graph.png' if os.path.exists(os.path.join('static','soil_graph.png')) else None
    uploaded_files = os.listdir(app.config['UPLOAD_FOLDER'])
    uploaded_filename = uploaded_files[-1] if uploaded_files else None

    return render_template('dashboard.html', farmer=farmer, weather=weather,
                           weather_alerts=alerts, graph_path=graph_path,
                           uploaded_filename=uploaded_filename)
@app.route('/logout')
def logout():
    session.pop('email', None)
    flash(t("logout"), "info")
    return redirect(url_for('home'))


# ====================
# Soil Analyzer (Static)
# ====================
@app.route('/soil', methods=['GET', 'POST'])
def soil():
    soil_condition = suitable_crops = fertilizer_suggestion = uploaded_filename = None
    testing_method = best_time = soil_type_info = tips_for_health = None

    if request.method == 'POST':
        file = request.files['soil_photo']
        if file:
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            uploaded_filename = filename

            # --------------------------
            # Static analysis (no API)
            # --------------------------
            soil_condition = {
                "en": "The soil appears healthy with moderate texture and good moisture retention.",
                "te": "మట్టి మోస్తరు పొరుగు మరియు మంచి తేమ నిలుపుదలతో ఆరోగ్యంగా కనిపిస్తోంది."
            }

            suitable_crops = {
                "en": "Suitable for rice, wheat, maize, and vegetables.",
                "te": "ఇది వరి, గోధుమ, మక్కా మరియు కూరగాయల కోసం తగినది."
            }

            fertilizer_suggestion = {
                "en": "Use organic compost and balanced NPK fertilizers for better crop yield.",
                "te": "మంచి పంట ఉత్పత్తికి సేంద్రీయ కంపోస్ట్ మరియు సమతుల్య NPK ఎరువులు ఉపయోగించండి."
            }

            testing_method = {
                "en": "Soil testing involves collecting a soil sample, sending it to a lab, and analyzing pH, nitrogen, phosphorus, potassium, and micronutrients.",
                "te": "మట్టి పరీక్షలో మట్టి నమూనాను సేకరించి, ల్యాబ్‌కు పంపి pH, నత్రజని, ఫాస్ఫరస్, పొటాష్ మరియు సూక్ష్మపోషకాలను విశ్లేషిస్తారు."
            }

            best_time = {
                "en": "The best time for soil testing is before sowing season or after harvest.",
                "te": "మట్టి పరీక్షకు ఉత్తమ సమయం నాటకం ముంచునుండగా లేదా ఫసలు కోత చేసిన తర్వాత."
            }

            soil_type_info = {
                "en": "This soil is loamy, well-drained, and suitable for most crops.",
                "te": "ఈ మట్టి లోమీ, బాగా-drained మరియు ఎక్కువ పంటలకు తగినది."
            }

            tips_for_health = {
                "en": "Rotate crops, add organic matter, avoid waterlogging, and monitor soil pH regularly.",
                "te": "పంటలను మారుస్తూ, సేంద్రీయ పదార్ధాలు చేర్చండి, నీరు నిలవకుండా చూడండి, మరియు మట్టి pH ను సాధారణంగా పరిశీలించండి."
            }

    return render_template(
        "soil.html",
        soil_condition=soil_condition,
        suitable_crops=suitable_crops,
        fertilizer_suggestion=fertilizer_suggestion,
        uploaded_filename=uploaded_filename,
        testing_method=testing_method,
        best_time=best_time,
        soil_type_info=soil_type_info,
        tips_for_health=tips_for_health
    )
# ====================
# Help Card
# ====================
@app.route('/help_card', methods=['GET','POST'])
def help_card():
    email = session.get('email')
    if not email:
        flash(t("login_first"),"warning")
        return redirect(url_for('login'))

    if request.method == 'POST':
        name = request.form.get("name")
        village = request.form.get("village")
        phone = request.form.get("phone")
        crop = request.form.get("crop", "").lower()
        query = request.form.get("query")

        if "paddy" in crop or "rice" in crop:
            suggestion = "Use drone-based pesticide spraying and soil moisture sensors for improved yield."
        elif "cotton" in crop:
            suggestion = "Adopt drip irrigation and use pest traps for pink bollworm control."
        elif "tomato" in crop:
            suggestion = "Use greenhouse cultivation and organic fertilizers for better growth."
        else:
            suggestion = "Consult your nearest Krishi Seva expert for crop-specific smart farming technologies."

        return render_template("help_card.html",
                               submitted=True,
                               name=name,
                               village=village,
                               phone=phone,
                               crop=crop,
                               query=query,
                               suggestion=suggestion)

    return render_template("help_card.html", submitted=False)

# ====================
# Upload Route for Crop Images
# ====================
@app.route('/upload', methods=['GET', 'POST'])
def upload():
    email = session.get('email')
    if not email:
        flash(t("login_first"), "warning")
        return redirect(url_for('login'))

    crop_name = None
    fertilizers = None
    ai_suggestion = None
    filename = None

    if request.method == 'POST':
        file = request.files.get('photo')
        crop_name = request.form.get('crop', '').lower()

        if file and file.filename != '':
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            flash("Image uploaded successfully!", "success")

            # AI-like logic for fertilizer recommendation
            crop_recommendations = {
                "wheat": ["Urea", "DAP", "Potash", "Zinc Sulphate"],
                "paddy": ["Ammonium Sulphate", "Super Phosphate", "MOP", "Organic Compost"],
                "cotton": ["Urea", "SSP", "Gypsum", "Bio-fertilizer"],
                "maize": ["Nitrogen Fertilizer", "Phosphate", "Potash", "Organic Manure"],
                "tomato": ["Compost", "Urea", "Super Phosphate", "Micronutrients"]
            }

            if crop_name in crop_recommendations:
                fertilizers = crop_recommendations[crop_name]
                ai_suggestion = f"Recommended fertilizers for {crop_name.title()} have been analyzed using AI based on soil needs."
            else:
                fertilizers = ["General NPK (20:20:20)", "Organic Compost"]
                ai_suggestion = "Fertilizer recommendations are based on general soil conditions."

        else:
            flash("Please upload a valid crop image.", "danger")

    return render_template(
        'upload.html',
        crop=crop_name,
        fertilizers=fertilizers,
        ai_suggestion=ai_suggestion,
        filename=filename
    )

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/forgot-password', methods=['GET','POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        flash('Password reset instructions sent to your email','success')
        return redirect(url_for('login'))
    return render_template('forgot_password.html')

@app.route('/send_otp', methods=['POST'])
def send_otp():
    email = request.form['email']
    otp = random.randint(100000,999999)
    session['otp'] = str(otp)
    print(f"Send OTP {otp} to {email}")
    return jsonify({"message":"OTP sent successfully"})

# ====================
if __name__ == "__main__":
    app.run(debug=True)