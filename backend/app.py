import os
import json
import google.generativeai as genai
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from datetime import timedelta, datetime
import PyPDF2
import re
import random
from difflib import SequenceMatcher
from dotenv import load_dotenv
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

model = genai.GenerativeModel("gemini-2.5-flash")
app = Flask(__name__)

# Database — reads DATABASE_URL from environment (Render injects this automatically)
# Falls back to local MySQL for development
database_url = os.getenv(
    'DATABASE_URL',
    'mysql+pymysql://root:@localhost/AiStudyAssistant'
)
# Render PostgreSQL URLs start with postgres:// — SQLAlchemy needs postgresql://
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-here')
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'jwt-secret-key-here')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(days=1)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# Upload folder
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

CORS(app)
jwt = JWTManager(app)

# In-memory store for questions (keyed by user_id)
user_questions = {}

# ============ MODELS ============

class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    uploads = db.relationship('Upload', backref='user', lazy=True)
    results = db.relationship('AssessmentResult', backref='user', lazy=True)


class Upload(db.Model):
    __tablename__ = "uploads"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    topics = db.Column(db.Text)           # JSON list of topics
    mode = db.Column(db.String(50))       # 'assessment', 'summary', 'notes'
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'filename': self.original_filename,
            'topics': json.loads(self.topics) if self.topics else [],
            'mode': self.mode,
            'uploaded_at': self.uploaded_at.strftime('%d %b %Y, %I:%M %p') if self.uploaded_at else None
        }


class AssessmentResult(db.Model):
    __tablename__ = "assessment_results"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    upload_id = db.Column(db.Integer, db.ForeignKey('uploads.id'), nullable=True)
    mcq_answers = db.Column(db.Text)         # JSON: [{question, selected, correct, topic}]
    descriptive_answers = db.Column(db.Text) # JSON: [{question, answer}]
    topics_data = db.Column(db.Text)         # JSON: [{topic, correct, total}]
    total_mcqs = db.Column(db.Integer, default=0)
    correct_mcqs = db.Column(db.Integer, default=0)
    score_percent = db.Column(db.Float, default=0.0)
    weak_areas = db.Column(db.Text)          # JSON list of weak topic strings
    strong_areas = db.Column(db.Text)        # JSON list of strong topic strings
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'mcq_answers': json.loads(self.mcq_answers) if self.mcq_answers else [],
            'descriptive_answers': json.loads(self.descriptive_answers) if self.descriptive_answers else [],
            'topics_data': json.loads(self.topics_data) if self.topics_data else [],
            'total_mcqs': self.total_mcqs,
            'correct_mcqs': self.correct_mcqs,
            'score_percent': self.score_percent,
            'weak_areas': json.loads(self.weak_areas) if self.weak_areas else [],
            'strong_areas': json.loads(self.strong_areas) if self.strong_areas else [],
            'submitted_at': self.submitted_at.strftime('%d %b %Y, %I:%M %p') if self.submitted_at else None
        }


# ============ PAGE ROUTES ============

@app.route("/")
def index():
    return render_template("login.html")

@app.route("/login")
def login_page():
    return render_template("login.html")

@app.route("/dashboard")
def dashboard_page():
    return render_template("dashboard.html")

@app.route("/upload")
def upload_page():
    return render_template("upload.html")

@app.route("/notes")
def notes_page():
    return render_template("notes.html")

@app.route("/summary")
def summary_page():
    return render_template("summary.html")

@app.route("/questions")
def questions_page():
    return render_template("questions.html")

@app.route("/analytics")
def analytics_page():
    return render_template("analytics.html")


# ============ AUTH API ROUTES ============

@app.route("/api/auth/register", methods=["POST"])
def register():
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()

        if not username or not password:
            return jsonify({"msg": "Username and password required"}), 400

        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            return jsonify({"msg": "Username already exists"}), 400

        hashed_password = generate_password_hash(password)
        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        return jsonify({"msg": "Registration successful! Please login."}), 201
    except Exception as e:
        return jsonify({"msg": str(e)}), 500


@app.route("/api/auth/login", methods=["POST"])
def login():
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()

        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            token = create_access_token(identity=str(user.id))
            return jsonify({
                "token": token,
                "username": user.username,
                "user_id": user.id
            }), 200
        return jsonify({"msg": "Invalid username or password"}), 401
    except Exception as e:
        return jsonify({"msg": str(e)}), 500


# ============ PDF HELPERS ============

def extract_text_from_pdf(file):
    try:
        pdf_reader = PyPDF2.PdfReader(file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text()
        return text
    except Exception as e:
        print(f"PDF extraction error: {e}")
        return ""


def generate_questions_from_text(text, filename):
    prompt = f"""
You are an expert university examiner.

Analyze the PDF content and generate:

1. 10 Concept-based MCQs
2. 5 Descriptive Questions
3. Topic List
4. Short Summary

STRICT RULES:

- No grammar questions.
- No fill in the blanks.
- No vocabulary questions.
- Questions must test understanding.
- Focus on concepts, definitions, workflows,
architecture, advantages and applications.
- Each MCQ must have a "topic" field indicating which topic this question belongs to.

Return JSON ONLY.

Format:

{{
"summary":"",
"topics":[""],
"mcqs":[
{{
    "question":"",
    "options":["","","",""],
    "answer":"",
    "topic":""
}}
],
"descriptive":[]
}}

CONTENT:

{text[:10000]}
    """
    response = model.generate_content(prompt)
    content = response.text.strip()
    print("===== GEMINI RESPONSE =====")
    print(content)
    print("==========================")

    content = re.sub(r"```json\s*", "", content)
    content = re.sub(r"```", "", content)
    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end == -1:
        raise Exception("No valid JSON found in Gemini response")
    content = content[start:end+1]
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        print("BAD JSON:")
        print(content)
    raise Exception(f"Gemini returned invalid JSON: {e}")

def generate_summary_from_text(text):
    prompt = f"""You are an expert academic summarizer.

Analyze the following content and produce a comprehensive study summary.

Return JSON ONLY in this exact format:
{{
  "title": "Short descriptive title for the document",
  "overview": "2-3 sentence high-level overview of what the document covers",
  "key_topics": [
    {{
      "topic": "Topic name",
      "summary": "3-5 sentence summary of this topic covering the most important concepts",
      "key_points": ["point 1", "point 2", "point 3"]
    }}
  ],
  "important_terms": [
    {{"term": "term name", "definition": "brief definition"}}
  ],
  "conclusion": "2-3 sentence conclusion/takeaway from the document"
}}

Include 4-6 key topics. Include 5-8 important terms.

CONTENT:
{text[:12000]}
"""
    response = model.generate_content(prompt)
    content = response.text
    content = content.replace("```json", "").replace("```", "").strip()
    start = content.find("{")
    end = content.rfind("}") + 1
    if start != -1 and end != -1:
        content = content[start:end]
    return json.loads(content)


def generate_notes_from_text(text):
    prompt = f"""You are an expert study notes creator.

Analyze the following content and create comprehensive Q&A study notes.

Return JSON ONLY in this exact format:
{{
  "title": "Short descriptive title for the document",
  "topics": ["topic1", "topic2"],
  "qa_notes": [
    {{
      "category": "Category/topic name this Q&A belongs to",
      "question": "A clear, specific question",
      "answer": "A thorough answer (3-5 sentences) that fully explains the concept"
    }}
  ]
}}

Rules:
- Generate 15-20 Q&A pairs covering the most important concepts
- Questions should test understanding, not just memory
- Answers must be detailed and educational
- Group questions by category/topic
- No grammar or vocabulary questions

CONTENT:
{text[:12000]}
"""
    response = model.generate_content(prompt)
    content = response.text
    content = content.replace("```json", "").replace("```", "").strip()
    start = content.find("{")
    end = content.rfind("}") + 1
    if start != -1 and end != -1:
        content = content[start:end]
    return json.loads(content)


# ============ AI GENERATE ROUTE ============

@app.route("/api/ai/generate", methods=["POST"])
@jwt_required()
def generate():
    try:
        user_id = get_jwt_identity()

        if 'file' not in request.files:
            return jsonify({"error": "No file uploaded"}), 400

        file = request.files['file']
        file.seek(0, 2)
        file_size = file.tell()
        file.seek(0)
        mode = request.form.get('mode', 'assessment')

        if file_size > 16 * 1024 * 1024:
            return jsonify({"error": "File too large. Maximum allowed size is 16 MB."}), 400

        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400

        if not file.filename.lower().endswith('.pdf'):
            return jsonify({"error": "Please upload a PDF file"}), 400

        # Save file to disk
        safe_name = f"{user_id}_{int(datetime.utcnow().timestamp())}_{file.filename}"
        file_path = os.path.join(UPLOAD_FOLDER, safe_name)
        file.seek(0)
        file.save(file_path)
        file.seek(0)

        text = extract_text_from_pdf(file)

        if not text or len(text) < 50:
            return jsonify({
                "error": "Could not extract enough text from PDF. Please ensure the PDF contains readable text."
            }), 400

        if mode == 'summary':
            result = generate_summary_from_text(text)
            # Save upload record
            topics = [t['topic'] for t in result.get('key_topics', [])]
            upload = Upload(
                user_id=int(user_id),
                filename=safe_name,
                original_filename=file.filename,
                topics=json.dumps(topics),
                mode='summary'
            )
            db.session.add(upload)
            db.session.commit()
            return jsonify({"success": True, "mode": "summary", "upload_id": upload.id, **result})

        elif mode == 'notes':
            result = generate_notes_from_text(text)
            topics = result.get('topics', [])
            upload = Upload(
                user_id=int(user_id),
                filename=safe_name,
                original_filename=file.filename,
                topics=json.dumps(topics),
                mode='notes'
            )
            db.session.add(upload)
            db.session.commit()
            return jsonify({"success": True, "mode": "notes", "upload_id": upload.id, **result})

        else:
            questions = generate_questions_from_text(text, file.filename)
            topics = questions.get("topics", [])
            upload = Upload(
                user_id=int(user_id),
                filename=safe_name,
                original_filename=file.filename,
                topics=json.dumps(topics),
                mode='assessment'
            )
            db.session.add(upload)
            db.session.commit()

            # Store questions in memory for this user
            user_questions[user_id] = {
                **questions,
                "upload_id": upload.id
            }

            return jsonify({
                "success": True,
                "mode": "assessment",
                "upload_id": upload.id,
                "summary": questions.get("summary", ""),
                "topics": topics,
                "mcqs": questions.get("mcqs", []),
                "descriptive": questions.get("descriptive", [])
            })

    except Exception as e:
        print("GENERATE ERROR:", str(e))
        return jsonify({"error": str(e)}), 500


# ============ GET RECENT UPLOADS ============

@app.route("/api/user/uploads", methods=["GET"])
@jwt_required()
def get_uploads():
    try:
        user_id = int(get_jwt_identity())
        uploads = Upload.query.filter_by(user_id=user_id)\
            .order_by(Upload.uploaded_at.desc()).limit(10).all()
        return jsonify([u.to_dict() for u in uploads])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============ GET USER QUESTIONS ============

@app.route("/api/user/questions", methods=["GET"])
@jwt_required()
def get_user_questions():
    try:
        user_id = get_jwt_identity()
        if user_id in user_questions:
            return jsonify(user_questions[user_id])
        return jsonify({"summary": None, "topics": [], "mcqs": [], "descriptive": []})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============ SUBMIT ASSESSMENT ============

@app.route("/api/ai/submit-assessment", methods=["POST"])
@jwt_required()
def submit_assessment():
    try:
        user_id = int(get_jwt_identity())
        data = request.get_json()

        mcq_answers = data.get('mcq_answers', [])   # [{question, selected, correct, topic}]
        desc_answers = data.get('descriptive_answers', [])  # [{question, answer}]
        upload_id = data.get('upload_id')

        # Calculate per-topic scores
        topic_map = {}
        for item in mcq_answers:
            topic = item.get('topic', 'General')
            if topic not in topic_map:
                topic_map[topic] = {'correct': 0, 'total': 0}
            topic_map[topic]['total'] += 1
            if item.get('selected') == item.get('correct'):
                topic_map[topic]['correct'] += 1

        total_mcqs = len(mcq_answers)
        correct_mcqs = sum(1 for i in mcq_answers if i.get('selected') == i.get('correct'))
        score_percent = round((correct_mcqs / total_mcqs * 100), 1) if total_mcqs > 0 else 0

        topics_data = [
            {
                'topic': t,
                'correct': v['correct'],
                'total': v['total'],
                'percent': round(v['correct'] / v['total'] * 100, 1) if v['total'] > 0 else 0
            }
            for t, v in topic_map.items()
        ]

        # Classify weak (<50%) and strong (>=70%) areas
        weak_areas = [t['topic'] for t in topics_data if t['percent'] < 50]
        strong_areas = [t['topic'] for t in topics_data if t['percent'] >= 70]

        result = AssessmentResult(
            user_id=user_id,
            upload_id=upload_id,
            mcq_answers=json.dumps(mcq_answers),
            descriptive_answers=json.dumps(desc_answers),
            topics_data=json.dumps(topics_data),
            total_mcqs=total_mcqs,
            correct_mcqs=correct_mcqs,
            score_percent=score_percent,
            weak_areas=json.dumps(weak_areas),
            strong_areas=json.dumps(strong_areas)
        )
        db.session.add(result)
        db.session.commit()

        return jsonify({
            "success": True,
            "result_id": result.id,
            "score_percent": score_percent,
            "correct_mcqs": correct_mcqs,
            "total_mcqs": total_mcqs,
            "weak_areas": weak_areas,
            "strong_areas": strong_areas,
            "topics_data": topics_data
        })

    except Exception as e:
        print("SUBMIT ERROR:", str(e))
        return jsonify({"error": str(e)}), 500


# ============ GET LATEST RESULT ============

@app.route("/api/user/latest-result", methods=["GET"])
@jwt_required()
def latest_result():
    try:
        user_id = int(get_jwt_identity())
        result = AssessmentResult.query.filter_by(user_id=user_id)\
            .order_by(AssessmentResult.submitted_at.desc()).first()
        if result:
            return jsonify(result.to_dict())
        return jsonify(None)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============ GET ALL RESULTS (for analytics) ============

@app.route("/api/user/results", methods=["GET"])
@jwt_required()
def all_results():
    try:
        user_id = int(get_jwt_identity())
        results = AssessmentResult.query.filter_by(user_id=user_id)\
            .order_by(AssessmentResult.submitted_at.asc()).all()
        return jsonify([r.to_dict() for r in results])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


with app.app_context():
    db.create_all()

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 AI STUDY ASSISANT STARTING...")
    print("=" * 60)
    app.run(debug=True, host="127.0.0.1", port=5000)
