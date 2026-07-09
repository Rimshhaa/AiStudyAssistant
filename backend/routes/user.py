from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models.attempt import Attempt

user_routes = Blueprint("user", __name__)

@user_routes.route("/performance", methods=["GET"])
@jwt_required()
def performance():
    user_id = get_jwt_identity()

    attempts = Attempt.query.filter_by(user_id=user_id).all()

    return jsonify([
        {"topic": a.topic, "score": a.score}
        for a in attempts
    ])