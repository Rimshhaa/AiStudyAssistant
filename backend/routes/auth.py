from flask import Blueprint, request, jsonify
from models.user import User
from models import db
from flask_jwt_extended import create_access_token

auth_routes = Blueprint("auth", __name__)

@auth_routes.route("/register", methods=["POST"])
def register():
    try:
        data = request.get_json()
        print("📝 Registration attempt:", data)
        
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        
        if not username or not password:
            return jsonify({"msg": "Username and password required"}), 400
        
        # Check if user exists
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            return jsonify({"msg": "Username already exists"}), 400
        
        # Create new user (store password as is for now - we'll add hashing later)
        user = User(username=username, password=password)
        
        db.session.add(user)
        db.session.commit()
        
        print(f"✅ User registered: {username}")
        return jsonify({"msg": "Registration successful! Please login."}), 201
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Registration error: {str(e)}")
        return jsonify({"msg": f"Registration failed: {str(e)}"}), 500

@auth_routes.route("/login", methods=["POST"])
def login():
    try:
        data = request.get_json()
        print("🔐 Login attempt:", data)
        
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        
        if not username or not password:
            return jsonify({"msg": "Username and password required"}), 400
        
        # Find user
        user = User.query.filter_by(username=username).first()
        
        if user and user.password == password:
            access_token = create_access_token(identity=str(user.id))
            print(f"✅ Login successful: {username}")
            return jsonify({
                "token": access_token,
                "username": user.username,
                "user_id": user.id
            }), 200
        
        print(f"❌ Login failed: {username}")
        return jsonify({"msg": "Invalid username or password"}), 401
        
    except Exception as e:
        print(f"❌ Login error: {str(e)}")
        return jsonify({"msg": f"Login failed: {str(e)}"}), 500