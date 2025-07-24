from flask import Flask, render_template
import random
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

def get_db_connection():
    conn = psycopg2.connect(
        host=os.environ.get('PGHOST'),
        database=os.environ.get('PGDATABASE'),
        user=os.environ.get('PGUSER'),
        password=os.environ.get('PGPASSWORD'),
        port=os.environ.get('PGPORT', 5432)
    )
    return conn

@app.route('/')
def hello_world():
    return 'Hello, World!!'

@app.route('/magic')
def magic():
    magic_number = random.randint(1, 8)
    return render_template('magic.html', number=magic_number)

@app.route('/db-test')
def db_test():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('SELECT id, name FROM test_table ORDER BY id;')
        records = cur.fetchall()
        cur.close()
        conn.close()
        return render_template('db_test.html', records=records)
    except Exception as e:
        return f"Database connection failed: {str(e)}"

@app.route('/sessions')
def sessions():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('SELECT name, path, city, state, country FROM session ORDER BY name;')
        sessions = cur.fetchall()
        cur.close()
        conn.close()
        return render_template('sessions.html', sessions=sessions)
    except Exception as e:
        return f"Database connection failed: {str(e)}"

@app.route('/sessions/<path:session_path>')
def session_detail(session_path):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''
            SELECT session_id, thesession_id, name, path, location_name, location_website, 
                   location_phone, city, state, country, comments, unlisted_address, 
                   initiation_date, termination_date, recurrence 
            FROM session 
            WHERE path = %s
        ''', (session_path,))
        session = cur.fetchone()
        cur.close()
        conn.close()
        
        if session:
            # Convert tuple to dictionary with column names
            session_dict = {
                'session_id': session[0],
                'thesession_id': session[1],
                'name': session[2],
                'path': session[3],
                'location_name': session[4],
                'location_website': session[5],
                'location_phone': session[6],
                'city': session[7],
                'state': session[8],
                'country': session[9],
                'comments': session[10],
                'unlisted_address': session[11],
                'initiation_date': session[12],
                'termination_date': session[13],
                'recurrence': session[14]
            }
            return render_template('session_detail.html', session=session_dict)
        else:
            return f"Session not found: {session_path}", 404
    except Exception as e:
        return f"Database connection failed: {str(e)}"
