from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO
from datetime import datetime
import sqlite3
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
socketio = SocketIO(app, cors_allowed_origins="*")

# --- Database setup ---
def init_db():
    with sqlite3.connect('attendance.db') as conn:
        conn.execute('''
        CREATE TABLE IF NOT EXISTS students (
            name TEXT PRIMARY KEY
        )
        ''')
        conn.execute('''
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            date TEXT NOT NULL,
            present INTEGER DEFAULT 0,
            excluded INTEGER DEFAULT 0,
            admitted INTEGER DEFAULT 0
        )
        ''')
        conn.execute('''
        CREATE TABLE IF NOT EXISTS supervisors (
            date TEXT PRIMARY KEY,
            count INTEGER DEFAULT 3
        )
        ''')

def seed_students():
    # Edit this list to your actual students
    STUDENTS = [
        'John Doe', 'Jane Smith', 'Alice Johnson', 'Bob Brown',
        'Emily Clark', 'Michael Lee', 'Sarah Turner', 'David Harris',
        'Jessica Walker', 'Matthew Young', 'Ashley King', 'Daniel Wright',
        'Samantha Scott', 'Andrew Green', 'Olivia Baker', 'Ryan Adams',
        'Megan Nelson', 'Joshua Carter', 'Lauren Mitchell', 'Brandon Perez',
        'Hannah Roberts', 'Tyler Phillips', 'Abigail Campbell', 'Nicholas Evans',
        'Brittany Edwards', 'Zachary Collins', 'Victoria Stewart', 'Jacob Morris',
        'Sydney Rogers', 'Alexander Reed', 'Rachel Cook', 'Ethan Morgan',
        'Madison Bell', 'Benjamin Murphy', 'Chloe Bailey', 'William Rivera',
        'Alyssa Cooper', 'Christopher Richardson', 'Natalie Cox', 'Anthony Howard',
        'Grace Ward', 'Justin Torres', 'Hailey Peterson', 'Samuel Gray'
    ]
    with sqlite3.connect('attendance.db') as conn:
        for name in STUDENTS:
            conn.execute('INSERT OR IGNORE INTO students (name) VALUES (?)', (name,))
        conn.commit()

@app.route('/')
def index():
    selected_date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    return render_template('register.html',
                           selected_date=selected_date,
                           max_attendees=21,
                           supervisors=3)

@app.route('/fetch')
def fetch_data():
    date = request.args.get('date')
    with sqlite3.connect('attendance.db') as conn:
        cursor = conn.cursor()
        # Get master student list
        cursor.execute('SELECT name FROM students')
        student_list = [row[0] for row in cursor.fetchall()]
        # Get attendance data for the date
        cursor.execute('SELECT name, present, excluded, admitted FROM attendance WHERE date = ?', (date,))
        attendance_data = {row[0]: {'present': bool(row[1]),
                                    'excluded': bool(row[2]),
                                    'admitted': bool(row[3])}
                          for row in cursor.fetchall()}
        # Get attendance counts
        cursor.execute('''
        SELECT name, COUNT(*) as count
        FROM attendance
        WHERE present = 1 AND date < ?
        GROUP BY name
        ''', (date,))
        attendance_counts = {row[0]: row[1] for row in cursor.fetchall()}
        # Get exclusion counts
        cursor.execute('''
        SELECT name, COUNT(*) as count
        FROM attendance
        WHERE excluded = 1 AND date < ?
        GROUP BY name
        ''', (date,))
        exclusion_counts = {row[0]: row[1] for row in cursor.fetchall()}
        # Get supervisors count
        cursor.execute('SELECT count FROM supervisors WHERE date = ?', (date,))
        supervisors_row = cursor.fetchone()
        supervisors = supervisors_row[0] if supervisors_row else 3

    # Merge: ensure all students are present in attendance_data
    for name in student_list:
        if name not in attendance_data:
            attendance_data[name] = {'present': False, 'excluded': False, 'admitted': False}
        if name not in attendance_counts:
            attendance_counts[name] = 0
        if name not in exclusion_counts:
            exclusion_counts[name] = 0

    return jsonify({
        'attendance': attendance_data,
        'attendance_counts': attendance_counts,
        'exclusion_counts': exclusion_counts,
        'supervisors': supervisors
    })

@app.route('/update', methods=['POST'])
def update_attendance():
    data = request.get_json()
    name = data['name']
    date = data['date']
    present = data['present']
    excluded = data['excluded']
    admitted = data['admitted']
    with sqlite3.connect('attendance.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''
        INSERT OR REPLACE INTO attendance (id, name, date, present, excluded, admitted)
        VALUES (
            COALESCE((SELECT id FROM attendance WHERE name = ? AND date = ?), NULL),
            ?, ?, ?, ?, ?
        )
        ''', (name, date, name, date, present, excluded, admitted))
        conn.commit()
    socketio.emit('refresh', {'date': date})
    return '', 204

@app.route('/update_supervisors', methods=['POST'])
def update_supervisors():
    data = request.get_json()
    date = data['date']
    supervisors = data['supervisors']
    with sqlite3.connect('attendance.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''
        INSERT OR REPLACE INTO supervisors (date, count)
        VALUES (?, ?)
        ''', (date, supervisors))
        conn.commit()
    socketio.emit('refresh', {'date': date})
    return '', 204

if __name__ == '__main__':
    init_db()
    seed_students()
    socketio.run(app, debug=True, host='0.0.0.0', port=5050)

