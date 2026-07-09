from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from services.summarizer import generate_summary
from services.question_gen import generate_mcqs, generate_descriptive
from services.evaluator import evaluate_answer
from services.topic_model import extract_topics
from services.pdf_reader import extract_text

from models.attempt import Attempt
from models import db

ai_routes = Blueprint("ai", __name__)


@ai_routes.route("/process", methods=["POST"])
@jwt_required()
def process():

    print("PROCESS ROUTE CALLED")

    user_id = get_jwt_identity()

    if 'file' in request.files:
        file = request.files['file']
        text = extract_text(file)

        print("===== PDF TEXT =====")
        print(text[:3000])
        print("====================")

    else:
        text = request.json.get("text", "")

    summary = generate_summary(text)

    mcqs = generate_mcqs(text)

    descriptive = generate_descriptive(text)

    topics = extract_topics(text)

    return jsonify({
        "summary": summary,
        "mcqs": mcqs,
        "descriptive": descriptive,
        "topics": topics
    })
    
@ai_routes.route("/evaluate", methods=["POST"])
@jwt_required()
def evaluate():
    user_id = get_jwt_identity()
    data = request.json

    score = evaluate_answer(
        data["student_answer"],
        data["correct_answer"]
    )

    attempt = Attempt(
        user_id=user_id,
        topic=data.get("topic", "general"),
        score=score
    )

    db.session.add(attempt)
    db.session.commit()

    return {"score": score}