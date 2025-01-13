from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from flask_pymongo import PyMongo
from datetime import datetime
from functools import wraps
from bson.objectid import ObjectId
from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Configure MongoDB
app.config["MONGO_URI"] = os.getenv("MONGO_URI")
app.config["MONGO_DBNAME"] = "evote"
mongo = PyMongo(app)

# Initialize admin user
# @app.before_first_request
# def create_admin():
#     if not mongo.db.admins.find_one({"cnic": "admin_cnic"}):
#         mongo.db.admins.insert_one({
#             "admin_id": "admin",
#             "name": "Admin",
#             "cnic": "admin_cnic",
#             "dob": "1970-01-01"
#         })
        
def format_response(success, message, data=None):
    return jsonify({"success": success, "message": message, "data": data})

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session or session['user']['role'] != 'admin':
            return access_denied()
        return f(*args, **kwargs)
    return decorated_function

# User Login
@app.route('/login', methods=['POST'])
def login():
    data = request.json
    cnic = data.get('cnic')
    dob = data.get('dob')

    user = mongo.db.voters.find_one({"cnic": cnic, "dob": dob})
    if user:
        session['user'] = {"id": user['cnic'], "role": "voter"}
        return format_response(True, "Login successful", {"role": "voter"})

    admin = mongo.db.admins.find_one({"cnic": cnic, "dob": dob})

    if admin:
        session['user'] = {"id": admin['admin_id'], "role": "admin"}
        return format_response(True, "Login successful", {"role": "admin"})
    
    return format_response(False, "Invalid credentials")

# Voter Registration
@app.route('/register_voter', methods=['POST'])
@admin_required
def register_voter():
    data = request.json
    name = data.get('name')
    cnic = data.get('cnic')
    dob = data.get('dob')

    dob_date = datetime.strptime(dob, "%Y-%m-%d")
    age = (datetime.now() - dob_date).days // 365

    if mongo.db.voters.find_one({"cnic": cnic}):
        return format_response(False, "Voter already registered.")
    if age < 18:
        return format_response(False, "Voter must be at least 18 years old.")

    mongo.db.voters.insert_one({"name": name, "cnic": cnic, "dob": dob, "age": age, "voted": False})
    return format_response(True, "Voter registered successfully.")

# Candidate Management
@app.route('/add_candidate', methods=['POST'])
@admin_required
def add_candidate():
    data = request.json
    name = data.get('name')
    party = data.get('party')
    cnic = data.get('cnic')
    dob = data.get('dob')

    try:
        dob_date = datetime.strptime(dob, "%Y-%m-%d")
        age = (datetime.now() - dob_date).days // 365
    except ValueError:
        return format_response(False, "Invalid date format. Use YYYY-MM-DD.")

    if age < 25:
        return format_response(False, "Candidate must be at least 25 years old.")

    if mongo.db.candidates.find_one({"cnic": cnic, "dob": dob}):
        return format_response(False, "Candidate already exists.")

    mongo.db.candidates.insert_one({"name": name, "party": party, "cnic": cnic, "dob": dob, "age": age})
    return format_response(True, "Candidate added successfully.")

# Get all candidates
@app.route('/get_candidates', methods=['GET'])
@login_required
def get_candidates():
    candidates = mongo.db.candidates.find()
    candidate_list = [{"candidate_id": str(candidate["_id"]), "name": candidate["name"], "party": candidate["party"]} for candidate in candidates]
    return format_response(True, "Candidates retrieved successfully.", candidate_list)

# Election Scheduling
@app.route('/create_election', methods=['POST'])
@admin_required
def create_election():
    data = request.json
    name = data.get('name')
    start_date = datetime.fromisoformat(data.get('start_date'))
    end_date = datetime.fromisoformat(data.get('end_date'))
    candidate_ids = data.get('candidate_ids')

    if start_date >= end_date:
        return format_response(False, "Invalid election schedule.")

    # Check for scheduling conflicts
    conflict = mongo.db.elections.find_one({
        "$or": [
            {"start_date": {"$lte": end_date, "$gte": start_date}},
            {"end_date": {"$lte": end_date, "$gte": start_date}},
            {"start_date": {"$lte": start_date}, "end_date": {"$gte": end_date}}
        ]
    })
    if conflict:
        return format_response(False, "Election schedule conflicts with an existing election.")

    candidates = []
    for candidate_id in candidate_ids:
        candidate = mongo.db.candidates.find_one({"_id": ObjectId(candidate_id)})
        if candidate:
            candidates.append({"_id": str(candidate["_id"]), "name": candidate["name"], "party": candidate["party"]})

    mongo.db.elections.insert_one({
        "name": name,
        "start_date": start_date,
        "end_date": end_date,
        "candidates": candidates,
        "votes": {}
    })
    return format_response(True, "Election created successfully.", {"candidates": candidates})

@app.route('/edit_election/<election_id>', methods=['PUT'])
@admin_required
def edit_election(election_id):
    data = request.json
    name = data.get('name')
    start_date = datetime.fromisoformat(data.get('start_date'))
    end_date = datetime.fromisoformat(data.get('end_date'))
    candidate_ids = data.get('candidate_ids')

    if start_date >= end_date:
        return format_response(False, "Invalid election schedule.")

    # Check for scheduling conflicts
    conflict = mongo.db.elections.find_one({
        "_id": {"$ne": ObjectId(election_id)},
        "$or": [
            {"start_date": {"$lte": end_date, "$gte": start_date}},
            {"end_date": {"$lte": end_date, "$gte": start_date}},
            {"start_date": {"$lte": start_date}, "end_date": {"$gte": end_date}}
        ]
    })
    if conflict:
        return format_response(False, "Election schedule conflicts with an existing election.")

    candidates = []
    for candidate_id in candidate_ids:
        candidate = mongo.db.candidates.find_one({"_id": ObjectId(candidate_id)})
        if candidate:
            candidates.append({"_id": str(candidate["_id"]), "name": candidate["name"], "party": candidate["party"]})

    result = mongo.db.elections.update_one(
        {"_id": ObjectId(election_id)},
        {"$set": {
            "name": name,
            "start_date": start_date,
            "end_date": end_date,
            "candidates": candidates
        }}
    )
    if result.matched_count == 0:
        return format_response(False, "Election not found.")
    return format_response(True, "Election updated successfully.", {"candidates": candidates})

@app.route('/delete_election/<election_id>', methods=['DELETE'])
@admin_required
def delete_election(election_id):
    result = mongo.db.elections.delete_one({"_id": ObjectId(election_id)})
    if result.deleted_count == 0:
        return format_response(False, "Election not found.")
    return format_response(True, "Election deleted successfully.")

# Vote Casting
@app.route('/cast_vote', methods=['POST'])
@login_required
def cast_vote():
    if session['user']['role'] == 'admin':
        return format_response(False, "Admins are not allowed to cast votes.")
    
    data = request.json
    voter_id = session['user']['id']
    election_id = data.get('election_id')
    candidate_id = data.get('candidate_id')

    voter = mongo.db.voters.find_one({"cnic": voter_id})
    if not voter:
        return format_response(False, "Voter not registered.")
    
    # Check if the voter has already voted in this election
    if mongo.db.elections.find_one({"_id": ObjectId(election_id), f"votes.{voter_id}": {"$exists": True}}):
        return format_response(False, "Voter has already cast a vote in this election.")

    election = mongo.db.elections.find_one({"_id": ObjectId(election_id)})
    if not election:
        return format_response(False, "Election not found.")

    candidate = mongo.db.candidates.find_one({"_id": ObjectId(candidate_id)})
    if not candidate:
        return format_response(False, "Candidate not found.")

    current_time = datetime.now()
    if current_time < election['start_date'] or current_time > election['end_date']:
        return format_response(False, "Election is not active.")

    votes = election.get('votes', {})
    votes[candidate_id] = votes.get(candidate_id, 0) + 1
    votes[voter_id] = True  # Mark that the voter has voted in this election
    mongo.db.elections.update_one({"_id": ObjectId(election_id)}, {"$set": {"votes": votes}})

    return format_response(True, "Vote cast successfully.")

# Results and Analytics
@app.route('/get_results/<election_id>', methods=['GET'])
@login_required
def get_results(election_id):
    election = mongo.db.elections.find_one({"_id": ObjectId(election_id)})
    if not election:
        return format_response(False, "Election not found.")

    votes = election.get('votes', {})
    if not votes:
        return format_response(True, "No votes have been cast yet.", {"results": [], "winner": None})

    candidates = election.get('candidates', [])
    results = []
    for candidate in candidates:
        candidate_id = str(candidate['_id'])
        candidate_votes = votes.get(candidate_id, 0)
        results.append({
            "name": candidate['name'],
            "party": candidate['party'],
            "votes": candidate_votes
        })


    max_votes = max(results, key=lambda x: x['votes'])['votes']
    winners = [candidate for candidate in results if candidate['votes'] == max_votes]

    if len(winners) > 1:
        winner = {"name": "Draw", "party": "N/A", "votes": max_votes}
    else:
        winner = winners[0]

    return format_response(True, "Results retrieved successfully.", {
        "results": results,
        "winner": winner
    })

@app.route('/available_elections', methods=['GET'])
@login_required
def available_elections():
    current_time = datetime.now()
    elections = mongo.db.elections.find({"start_date": {"$lte": current_time}, "end_date": {"$gte": current_time}})
    election_list = [{"election_id": str(election["_id"]), "name": election["name"]} for election in elections]
    return format_response(True, "Available elections retrieved successfully.", election_list)

@app.route('/all_elections', methods=['GET'])
@login_required
def all_elections():
    elections = mongo.db.elections.find()
    election_list = [{"election_id": str(election["_id"]), "name": election["name"]} for election in elections]
    return format_response(True, "All elections retrieved successfully.", election_list)

# Get election details
@app.route('/get_election/<election_id>', methods=['GET'])
@admin_required
def get_election(election_id):
    election = mongo.db.elections.find_one({"_id": ObjectId(election_id)})
    if not election:
        return format_response(False, "Election not found.")

    election_data = {
        "name": election["name"],
        "start_date": election["start_date"].isoformat(),
        "end_date": election["end_date"].isoformat(),
        "candidates": [{"_id": str(candidate["_id"]), "name": candidate["name"], "party": candidate["party"]} for candidate in election["candidates"]]
    }
    return format_response(True, "Election details retrieved successfully.", election_data)

def access_denied():
    return render_template('access_denied.html'), 403

# Admin Dashboard
@app.route('/admin_dashboard')
@admin_required
def admin_dashboard():
    return render_template('admin_dashboard.html')

# Voter Dashboard
@app.route('/voter_dashboard')
@login_required
def voter_dashboard():
    if session['user']['role'] != 'voter':
        return access_denied()
    return render_template('voter_dashboard.html')

@app.route('/')
@login_required
def home():
    if session['user']['role'] == 'admin':
        return redirect(url_for('admin_dashboard'))
    return redirect(url_for('voter_dashboard'))

@app.route('/login_page')
def login_page():
    return render_template('login.html')

if __name__ == '__main__':
    app.run(debug=True)
