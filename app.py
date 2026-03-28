from flask import Flask, render_template, send_file, request
from pymongo import MongoClient
from flask_jwt_extended import create_access_token, JWTManager, jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
import os, json, uuid

app = Flask(__name__)
app.config["JWT_SECRET_KEY"] = "mini-secret-key"
jwt = JWTManager(app)



try:
    client = MongoClient("mongodb://localhost:27017/", serverSelectionTimeoutMS=5000)
    client.admin.command('ping')
    db = client["mini_drive"]
    USE_MONGODB = True
except:
    USE_MONGODB = False
    USERS_FILE = "users.json"
    FILES_FILE = "files.json"

    for file in [USERS_FILE, FILES_FILE]:
        if not os.path.exists(file):
            with open(file, 'w') as f:
                json.dump([], f)

os.makedirs("uploads", exist_ok=True)



def get_users():
    if USE_MONGODB:
        return db.users
    with open(USERS_FILE) as f:
        return json.load(f)

def save_users(users):
    if not USE_MONGODB:
        with open(USERS_FILE, 'w') as f:
            json.dump(users, f)

def get_files():
    if USE_MONGODB:
        return db.files
    with open(FILES_FILE) as f:
        return json.load(f)

def save_files(files):
    if not USE_MONGODB:
        with open(FILES_FILE, 'w') as f:
            json.dump(files, f)



@app.route("/")
def index():
    return render_template("index.html")

@app.route("/login")
def login_page():
    return render_template("login.html")

@app.route("/register")
def register_page():
    return render_template("register.html")

@app.route("/dashboard")
def dashboard_page():
    return render_template("dashboard.html")


@app.route("/api/register", methods=["POST"])
def register():
    data = request.json
    if not data or not data.get("email") or not data.get("password"):
        return {"message": "Email and password are required"}, 400

    if USE_MONGODB:
        if db.users.find_one({"email": data["email"]}):
            return {"message": "User already exists"}, 400
        db.users.insert_one(data)
    else:
        users = get_users()
        if any(u["email"] == data["email"] for u in users):
            return {"message": "User already exists"}, 400
        users.append({"id": str(uuid.uuid4()), **data})
        save_users(users)

    return {"message": "User registered successfully"}


@app.route("/api/login", methods=["POST"])
def login():
    data = request.json
    if not data or not data.get("email") or not data.get("password"):
        return {"message": "Email and password are required"}, 400

    if USE_MONGODB:
        user = db.users.find_one({"email": data["email"]})
        if not user or user["password"] != data["password"]:
            return {"message": "Invalid email or password"}, 401
        user_id = str(user["_id"])
    else:
        users = get_users()
        user = next((u for u in users if u["email"] == data["email"] and u["password"] == data["password"]), None)
        if not user:
            return {"message": "Invalid email or password"}, 401
        user_id = user["id"]

    token = create_access_token(identity=user_id)
    return {"token": token}



@app.route("/api/upload", methods=["POST"])
@jwt_required()
def upload():
    user_id = get_jwt_identity()

    file = request.files.get("file")
    if not file or file.filename == "":
        return {"message": "No file selected"}, 400

    filename = secure_filename(file.filename)
    stored_name = f"{uuid.uuid4()}_{filename}"
    path = os.path.join("uploads", stored_name)
    file.save(path)

    record = {
        "user_id": user_id,
        "original_filename": filename,
        "stored_filename": stored_name,
        "filepath": path
    }

    if USE_MONGODB:
        db.files.insert_one(record)
    else:
        files = get_files()
        files.append(record)
        save_files(files)

    return {"message": "File uploaded successfully"}



@app.route("/api/files", methods=["GET"])
@jwt_required()
def list_files():
    user_id = get_jwt_identity()

    if USE_MONGODB:
        files = [
            {
                "original_filename": f["original_filename"],
                "stored_filename": f["stored_filename"],
                "upload_time": str(f["_id"])
            }
            for f in db.files.find({"user_id": user_id})
        ]
    else:
        files = [
            {
                "original_filename": f["original_filename"],
                "stored_filename": f["stored_filename"],
                "upload_time": ""
            }
            for f in get_files() if f["user_id"] == user_id
        ]

    return {"files": files}



@app.route("/api/download/<file_id>", methods=["GET"])
@jwt_required()
def download_file(file_id):
    user_id = get_jwt_identity()

    if USE_MONGODB:
        file = db.files.find_one({"stored_filename": file_id, "user_id": user_id})
    else:
        file = next((f for f in get_files() if f["stored_filename"] == file_id and f["user_id"] == user_id), None)

    if not file:
        return {"message": "File not found"}, 404

    return send_file(file["filepath"], as_attachment=True, download_name=file["original_filename"])



if __name__ == "__main__":
    app.run(debug=True)