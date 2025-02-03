from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_bcrypt import Bcrypt
import os
import ai  # Import the AI-related code
from werkzeug.utils import secure_filename  # Add this import
import json
import datetime
from flask_pymongo import PyMongo
from dotenv import load_dotenv

load_dotenv()

# Initialize Flask app
app = Flask(__name__,static_folder='../client/dist',static_url_path='/')

CORS(app)  # Enable CORS for frontend-backend communication
bcrypt = Bcrypt(app)

# Remove SQLAlchemy database configuration
# app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///quiz.db'
# app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Remove the initialization of the database
# db = SQLAlchemy(app)

mongo = PyMongo(app, uri="mongodb+srv://mithun27:MITHUN123@cluster1.bidbx.mongodb.net/quizmaker")

# Remove SQLAlchemy database models
# class User(db.Model):
#     id = db.Column(db.Integer, primary_key=True)
#     full_name = db.Column(db.String(100), nullable=False)
#     username = db.Column(db.String(50), unique=True, nullable=False)
#     password = db.Column(db.String(200), nullable=False)
#     phone_number = db.Column(db.String(15), nullable=False)

# Remove the creation of database tables
# with app.app_context():
#     db.create_all()

# Routes
@app.route('/')
def home():
    return "running"
@app.route('/api/signup', methods=['POST'])
def signup():
    try:
        data = request.get_json()

        full_name = data.get('fullName')
        username = data.get('username')
        password = data.get('password')
        phone_number = data.get('phoneNumber')

        # Check if user already exists
        existing_user = mongo.db.users.find_one({"username": username})
        if existing_user:
            return jsonify({"error": "Username already exists"}), 409

        # Hash the password
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

        # Create new user document
        new_user = {
            "full_name": full_name,
            "username": username,
            "password": hashed_password,
            "phone_number": phone_number,
            "role": "User"  # Default role
        }

        # Insert into MongoDB
        mongo.db.users.insert_one(new_user)

        return jsonify({"message": "User registered successfully"}), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Login
@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.json
        username = data.get('username')
        password = data.get('password')

        # Find user in MongoDB
        user = mongo.db.users.find_one({"username": username})
        
        if user and bcrypt.check_password_hash(user['password'], password):
            user_data = {
                "username": user['username'],
                "full_name": user['full_name'],
                "phone_number": user['phone_number']
            }
            return jsonify({
                "message": "Login successful",
                "user": user_data
            }), 200
        else:
            return jsonify({"error": "Invalid username or password"}), 401

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Upload folder configuration (separate from routes)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/api/upload_quiz/uploadfile', methods=['POST'])
def upload_quiz_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    # Secure the file name and save it
    filename = secure_filename(file.filename)
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(file_path)

    # Generate MCQs from the PDF
    mcqs = ai.generate_mcqs_from_pdf(file_path)
    
    if mcqs is None:
        return jsonify({"error": "Failed to generate MCQs from the PDF"}), 500

    # Return the generated MCQs as JSON response
    return jsonify({"questions": mcqs}), 200

# Get all questions
@app.route('/getquestions', methods=['GET'])
def get_questions():
    questions = Quiz.query.all()  # Fetch all questions from the Quiz table
    if not questions:
        return jsonify({"error": "No questions found"}), 404

    # Format the questions for the frontend
    questions_data = [
        {
            "question_no": question.question_no,
            "question": question.question,
            "A": question.option_a,
            "B": question.option_b,
            "C": question.option_c,
            "D": question.option_d,
            "correct_answer": question.correct_answer
        }
        for question in questions
    ]

    return jsonify({"questions": questions_data}), 200

@app.route('/api/upload_quiz/savequiz', methods=['POST'])
def save_quiz_json():
    try:
        json_data = request.get_json()
        if not json_data:
            return jsonify({"error": "No JSON data received"}), 400
            
        print("Received JSON data:", json_data)  # Debug print
        quizzes_collection = mongo.db.quizzes
        
        # Check if questions exist in the JSON data
        if "questions" not in json_data:
            # Try to wrap the data in a questions array if it's not already
            json_data = {"questions": json_data}
            
        # Get quiz_id from the first question
        if json_data["questions"] and len(json_data["questions"]) > 0:
            quiz_id = json_data["questions"][0].get("qid")
            if not quiz_id:
                return jsonify({"error": "Quiz ID (qid) not found in the first question"}), 400
                
            # Ensure all questions have the same qid
            for question in json_data["questions"]:
                question["qid"] = quiz_id
        else:
            return jsonify({"error": "No questions found in quiz data"}), 400
        
        # Add creation timestamp
        json_data["createdAt"] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Insert into MongoDB
        result = quizzes_collection.insert_one(json_data)
        
        return jsonify({
            "success": True,
            "id": str(result.inserted_id),
            "quiz_id": quiz_id
        }), 201
        
    except Exception as e:
        print(f"Error in save_quiz_json: {str(e)}")  # Debug print
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/upload_quiz/questions', methods=['GET'])
def get_all_questions():
    questions = Quiz.query.all()

    questions_data = [
        {
            "id": question.id,
            "question_no": question.question_no,
            "question": question.question,
            "A": question.option_a,
            "B": question.option_b,
            "C": question.option_c,
            "D": question.option_d,
            "correct_answer": question.correct_answer,
        }
        for question in questions
    ]

    return jsonify({"questions": questions_data}), 200

@app.route('/api/getquizzes', methods=['GET'])
def get_quizzes():
    try:
        quizzes_collection = mongo.db.quizzes
        quizzes = []
        processed_qids = set()  # To track unique qids
        
        for quiz in quizzes_collection.find():
            if quiz.get("questions") and len(quiz["questions"]) > 0:
                first_question = quiz["questions"][0]
                qid = first_question.get("qid")
                
                # Skip if we've already processed this qid or if qid is missing
                if not qid or qid in processed_qids:
                    continue
                    
                processed_qids.add(qid)
                formatted_quiz = {
                    'id': qid,  # Use qid instead of MongoDB _id
                    'topic': first_question.get("topic", "General"),
                    'totalQuestions': len(quiz["questions"])
                }
                quizzes.append(formatted_quiz)
        
        return jsonify({
            'success': True,
            'quizzes': quizzes
        })
    except Exception as e:
        print(f"Error getting quizzes: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/getquizzes', methods=['POST'])
def get_quiz():
    try:
        data = request.get_json()
        if not data or 'id' not in data:
            return jsonify({"error": "Quiz ID not provided in the request body."}), 400

        qid = data['id']
        quizzes_collection = mongo.db.quizzes
        
        # Find quiz where any question in the questions array has matching qid
        quiz = quizzes_collection.find_one({"questions.qid": qid})
        if not quiz:
            return jsonify({"error": "Quiz not found"}), 404
            
        # Remove MongoDB _id from response
        quiz.pop('_id', None)
        
        return jsonify(quiz), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/quizzes/<quiz_id>/submit', methods=['POST'])
def evaluate_quiz(quiz_id):
    answers = request.json.get('answers')
    evaluation_result = ai.evaluate(answers)
    print(evaluation_result)
    return jsonify(evaluation_result)

@app.route('/api/manage/quizzes', methods=['GET'])
def get_all_quizzes():
    try:
        quizzes_collection = mongo.db.quizzes
        quizzes = []
        processed_qids = set()
        
        for quiz in quizzes_collection.find():
            if quiz.get("questions") and len(quiz["questions"]) > 0:
                first_question = quiz["questions"][0]
                qid = first_question.get("qid")
                
                # Skip if we've already processed this qid or if qid is missing
                if not qid or qid in processed_qids:
                    continue
                    
                processed_qids.add(qid)
                quizzes.append({
                    "id": qid,  # Use qid instead of MongoDB's _id
                    "title": first_question.get("topic", "Untitled Quiz"),
                    "totalQuestions": len(quiz["questions"]),
                    "createdAt": quiz.get("createdAt", datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                })
        
        quizzes.sort(key=lambda x: x["createdAt"], reverse=True)
        return jsonify({"success": True, "quizzes": quizzes, "total": len(quizzes)}), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/manage/quiz/<quiz_id>', methods=['GET'])
def get_quiz_by_id(quiz_id):
    try:
        quizzes_collection = mongo.db.quizzes
        # Find quiz where any question in the questions array has matching qid
        quiz = quizzes_collection.find_one({"questions.qid": quiz_id})
        
        if not quiz:
            return jsonify({"success": False, "error": "Quiz not found"}), 404

        quiz.pop('_id')  # Remove MongoDB _id
        first_question = quiz["questions"][0]
            
        return jsonify({
            "success": True,
            "quiz": {
                "id": quiz_id,
                "title": first_question.get("topic", "Untitled Quiz"),
                "totalQuestions": len(quiz["questions"]),
                "questions": quiz["questions"]
            }
        }), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/manage/quiz/<quiz_id>', methods=['DELETE'])
def delete_quiz(quiz_id):
    try:
        quizzes_collection = mongo.db.quizzes
        # Delete quiz by qid in questions array
        result = quizzes_collection.delete_one({"questions.qid": quiz_id})
        
        if result.deleted_count == 0:
            return jsonify({"success": False, "error": "Quiz not found"}), 404

        return jsonify({
            "success": True,
            "message": "Quiz deleted successfully"
        }), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/manage/quiz/<quiz_id>', methods=['PUT'])
def update_quiz(quiz_id):
    try:
        quiz_data = request.get_json()
        quizzes_collection = mongo.db.quizzes
        
        # Ensure all questions have the correct qid
        if "questions" in quiz_data:
            for question in quiz_data["questions"]:
                question["qid"] = quiz_id
        
        # Update quiz by qid in questions array
        result = quizzes_collection.update_one(
            {"questions.qid": quiz_id},
            {"$set": quiz_data}
        )
        
        if result.matched_count == 0:
            return jsonify({"success": False, "error": "Quiz not found"}), 404

        return jsonify({
            "success": True,
            "message": "Quiz updated successfully"
        }), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/manage/quiz/<quiz_id>/question/<int:question_index>', methods=['PUT'])
def update_question(quiz_id, question_index):
    try:
        updated_question = request.get_json()
        quizzes_collection = mongo.db.quizzes
        
        # Ensure the updated question has the correct qid
        updated_question["qid"] = quiz_id
        
        # First get the quiz to verify question index
        quiz = quizzes_collection.find_one({"questions.qid": quiz_id})
        if not quiz or question_index >= len(quiz["questions"]):
            return jsonify({"success": False, "error": "Quiz or question not found"}), 404

        # Update specific question in the array
        result = quizzes_collection.update_one(
            {"questions.qid": quiz_id},
            {"$set": {f"questions.{question_index}": updated_question}}
        )

        return jsonify({"success": True, "message": "Question updated successfully"}), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/manage/quiz/<quiz_id>/question/<int:question_index>', methods=['DELETE'])
def delete_question(quiz_id, question_index):
    try:
        quizzes_collection = mongo.db.quizzes
        
        # First get the quiz to verify question index
        quiz = quizzes_collection.find_one({"questions.qid": quiz_id})
        if not quiz or question_index >= len(quiz["questions"]):
            return jsonify({"success": False, "error": "Quiz or question not found"}), 404

        # Remove the question at the specified index
        result = quizzes_collection.update_one(
            {"questions.qid": quiz_id},
            {"$pull": {"questions": {"$position": question_index}}}
        )

        return jsonify({"success": True, "message": "Question deleted successfully"}), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/profile', methods=['GET'])
def get_profile():
    try:
        # Get username from request headers
        username = request.headers.get('username')
        if not username:
            return jsonify({"error": "No username provided"}), 401

        # Find user in MongoDB
        user = mongo.db.users.find_one({"username": username})
        if not user:
            return jsonify({"error": "User not found"}), 404

        # Remove sensitive information
        user_data = {
            "full_name": user.get('full_name'),
            "username": user.get('username'),
            "phone_number": user.get('phone_number'),
            "role": user.get('role', 'User')
        }

        return jsonify({
            "success": True,
            "user": user_data
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
