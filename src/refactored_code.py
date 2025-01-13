"""
This module implements an election management system using Flask and MongoDB.
It provides endpoints for managing voters, candidates, elections, and votes.
"""

from datetime import datetime
import os
from functools import wraps
from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from flask_pymongo import PyMongo
from bson.objectid import ObjectId

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'fallback_secret_key')

# Configure MongoDB
app.config["MONGO_URI"] = (
    "mongodb+srv://bsef21m009:DcVFS1Pa0TaS3aFV@cluster0.rwzex.mongodb.net/evote"
)
app.config["MONGO_DBNAME"] = "evote"
mongo = PyMongo(app)

def format_response(success, message, data=None):
    """Formats the JSON response returned by API endpoints."""
    return jsonify({"success": success, "message": message, "data": data})

def login_required(f):
    """Decorator to ensure the user is logged in before accessing the route."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator to ensure the user has admin privileges before accessing the route."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session or session['user']['role'] != 'admin':
            return access_denied()
        return f(*args, **kwargs)
    return decorated_function

# User Login
@app.route('/login', methods=['POST'])
def login():
    """Logs in a voter or admin based on provided credentials."""
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
    """Registers a new voter if they meet age and uniqueness requirements."""
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
    """Adds a new candidate to the system if they meet the age requirement."""
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

    mongo.db.candidates.insert_one({
        "name": name,
        "party": party,
        "cnic": cnic,
        "dob": dob,
        "age": age
    })
    return format_response(True, "Candidate added successfully.")

# Get all candidates
@app.route('/get_candidates', methods=['GET'])
@login_required
def get_candidates():
    """Fetches a list of all registered candidates."""
    candidates = mongo.db.candidates.find()
    candidate_list = [
        {
            "candidate_id": str(candidate["_id"]),
            "name": candidate["name"],
            "party": candidate["party"]
        }
        for candidate in candidates
    ]
    return format_response(True, "Candidates retrieved successfully.", candidate_list)

# Election Scheduling
@app.route('/create_election', methods=['POST'])
@admin_required
def create_election():
    """Creates a new election with specified candidates and schedule."""
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
            candidates.append({
                "_id": str(candidate["_id"]),
                "name": candidate["name"],
                "party": candidate["party"]
            })


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
    """Edits an existing election's details, such as name, schedule, and candidates."""
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
            candidates.append({
                "_id": str(candidate["_id"]),
                "name": candidate["name"],
                "party": candidate["party"]
            })


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
    """Deletes an election by its ID."""
    result = mongo.db.elections.delete_one({"_id": ObjectId(election_id)})
    if result.deleted_count == 0:
        return format_response(False, "Election not found.")
    return format_response(True, "Election deleted successfully.")

# Vote Casting
@app.route('/cast_vote', methods=['POST'])
@login_required
def cast_vote():
    """Allows a voter to cast a vote in an active election."""
    response = {"success": True, "message": "Vote cast successfully."}

    if session['user']['role'] == 'admin':
        response.update({"success": False, "message": "Admins are not allowed to cast votes."})
        return jsonify(response)

    data = request.json
    voter_id = session['user']['id']
    election_id = data.get('election_id')
    candidate_id = data.get('candidate_id')

    # Check voter registration
    if not is_voter_registered(voter_id):
        response.update({"success": False, "message": "Voter not registered."})
    # Check if voter already voted
    elif has_already_voted(election_id, voter_id):
        response.update(
            {"success": False, "message": "Voter has already cast a vote in this election."}
        )
    else:
        election = get_election1(election_id)
        # Check election validity
        if not election:
            response.update({"success": False, "message": "Election not found."})
        else:
            candidate = get_candidate(candidate_id)
            # Check candidate validity
            if not candidate:
                response.update({"success": False, "message": "Candidate not found."})
            # Check if election is active
            elif not is_election_active(election):
                response.update({"success": False, "message": "Election is not active."})
            else:
                # Record vote
                record_vote(election_id, voter_id, candidate_id, election)

    return jsonify(response)


# Helper Functions
def is_voter_registered(voter_id):
    """Checks if the voter is registered."""
    return mongo.db.voters.find_one({"cnic": voter_id}) is not None


def has_already_voted(election_id, voter_id):
    """Checks if the voter has already voted in the specified election."""
    return mongo.db.elections.find_one({
        "_id": ObjectId(election_id),
        f"votes.{voter_id}": {"$exists": True}
    }) is not None


def get_election1(election_id):
    """Retrieves the election by its ID."""
    return mongo.db.elections.find_one({"_id": ObjectId(election_id)})


def get_candidate(candidate_id):
    """Retrieves the candidate by their ID."""
    return mongo.db.candidates.find_one({"_id": ObjectId(candidate_id)})


def is_election_active(election):
    """Checks if the election is currently active."""
    current_time = datetime.now()
    return election['start_date'] <= current_time <= election['end_date']


def record_vote(election_id, voter_id, candidate_id, election):
    """Records a vote for the specified candidate in the election."""
    votes = election.get('votes', {})
    votes[candidate_id] = votes.get(candidate_id, 0) + 1
    votes[voter_id] = True  # Mark voter as having voted
    mongo.db.elections.update_one({"_id": ObjectId(election_id)}, {"$set": {"votes": votes}})



# Results and Analytics
@app.route('/get_results/<election_id>', methods=['GET'])
@login_required
def get_results(election_id):
    """Retrieves election results, including vote counts and winner details."""
    election = mongo.db.elections.find_one({"_id": ObjectId(election_id)})
    if not election:
        return format_response(False, "Election not found.")

    votes = election.get('votes', {})
    if not votes:
        return format_response(
            True,
            "No votes have been cast yet.",
            {"results": [], "winner": None}
        )

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
    """Lists elections that are currently active based on the date."""
    current_time = datetime.now()
    elections = mongo.db.elections.find({
        "start_date": {"$lte": current_time},
        "end_date": {"$gte": current_time}
    })
    election_list = [
        {
            "election_id": str(election["_id"]),
            "name": election["name"]
        }
        for election in elections
    ]
    return format_response(True, "Available elections retrieved successfully.", election_list)

@app.route('/all_elections', methods=['GET'])
@login_required
def all_elections():
    """Lists all elections in the system, regardless of their status."""
    elections = mongo.db.elections.find()
    election_list = [
        {
            "election_id": str(election["_id"]),
            "name": election["name"]
        }
        for election in elections
    ]
    return format_response(True, "All elections retrieved successfully.", election_list)

# Get election details
@app.route('/get_election/<election_id>', methods=['GET'])
@admin_required
def get_election(election_id):
    """Retrieves details of a specific election by its ID."""
    election = mongo.db.elections.find_one({"_id": ObjectId(election_id)})
    if not election:
        return format_response(False, "Election not found.")

    election_data = {
        "name": election["name"],
        "start_date": election["start_date"].isoformat(),
        "end_date": election["end_date"].isoformat(),
        "candidates": [
            {
                "_id": str(candidate["_id"]),
                "name": candidate["name"],
                "party": candidate["party"]
            }
            for candidate in election["candidates"]
        ]

    }
    return format_response(True, "Election details retrieved successfully.", election_data)

def access_denied():
    """Renders the access denied page."""
    return render_template('access_denied.html'), 403

# Admin Dashboard
@app.route('/admin_dashboard')
@admin_required
def admin_dashboard():
    """Renders the admin dashboard page."""
    return render_template('admin_dashboard.html')

# Voter Dashboard
@app.route('/voter_dashboard')
@login_required
def voter_dashboard():
    """Renders the voter dashboard page."""
    if session['user']['role'] != 'voter':
        return access_denied()
    return render_template('voter_dashboard.html')

@app.route('/')
@login_required
def home():
    """Redirects the user to their respective dashboard based on their role."""
    if session['user']['role'] == 'admin':
        return redirect(url_for('admin_dashboard'))
    return redirect(url_for('voter_dashboard'))

@app.route('/login_page')
def login_page():
    """Renders the login page."""
    return render_template('login.html')

if __name__ == '__main__':
    app.run()
