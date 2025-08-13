from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import random
import os
import psycopg2
from dotenv import load_dotenv
import re
import requests

load_dotenv()

app = Flask(__name__)
# Secret key required for Flask sessions (used by flash messages to store temporary messages in signed cookies)
app.secret_key = os.environ.get('FLASK_SESSION_SECRET_KEY', 'dev-secret-key-change-in-production')

def normalize_apostrophes(text):
    """Normalize smart apostrophes and quotes to standard ASCII characters."""
    if not text:
        return text
    # Replace various smart apostrophes and quotes with standard apostrophe
    return text.replace('’', "'").replace('‘', "'").replace('“', '"').replace('”', '"')

def get_db_connection():
    conn = psycopg2.connect(
        host=os.environ.get('PGHOST'),
        database=os.environ.get('PGDATABASE'),
        user=os.environ.get('PGUSER'),
        password=os.environ.get('PGPASSWORD'),
        port=os.environ.get('PGPORT', 5432)
    )
    return conn

def save_to_history(cur, table_name, operation, record_id, changed_by='system'):
    """Save a record to its history table before modification/deletion"""
    history_table = f"{table_name}_history"
    
    if table_name == 'session':
        cur.execute('''
            INSERT INTO session_history 
            (session_id, operation, changed_by, thesession_id, name, path, location_name, 
             location_website, location_phone, city, state, country, comments, 
             unlisted_address, initiation_date, termination_date, recurrence, created_date, last_modified_date)
            SELECT session_id, %s, %s, thesession_id, name, path, location_name, 
                   location_website, location_phone, city, state, country, comments, 
                   unlisted_address, initiation_date, termination_date, recurrence, created_date, last_modified_date
            FROM session WHERE session_id = %s
        ''', (operation, changed_by, record_id))
    
    elif table_name == 'session_instance':
        cur.execute('''
            INSERT INTO session_instance_history 
            (session_instance_id, operation, changed_by, session_id, date, start_time, 
             end_time, location_override, is_cancelled, comments, created_date, last_modified_date)
            SELECT session_instance_id, %s, %s, session_id, date, start_time, 
                   end_time, location_override, is_cancelled, comments, created_date, last_modified_date
            FROM session_instance WHERE session_instance_id = %s
        ''', (operation, changed_by, record_id))
    
    elif table_name == 'tune':
        cur.execute('''
            INSERT INTO tune_history 
            (tune_id, operation, changed_by, name, tune_type, tunebook_count_cached, created_date, last_modified_date)
            SELECT tune_id, %s, %s, name, tune_type, tunebook_count_cached, created_date, last_modified_date
            FROM tune WHERE tune_id = %s
        ''', (operation, changed_by, record_id))
    
    elif table_name == 'session_tune':
        # For session_tune, record_id should be a tuple (session_id, tune_id)
        session_id, tune_id = record_id
        cur.execute('''
            INSERT INTO session_tune_history 
            (session_id, tune_id, operation, changed_by, setting_id, key, alias, created_date, last_modified_date)
            SELECT session_id, tune_id, %s, %s, setting_id, key, alias, created_date, last_modified_date
            FROM session_tune WHERE session_id = %s AND tune_id = %s
        ''', (operation, changed_by, session_id, tune_id))
    
    elif table_name == 'session_instance_tune':
        cur.execute('''
            INSERT INTO session_instance_tune_history 
            (session_instance_tune_id, operation, changed_by, session_instance_id, tune_id, 
             name, order_number, continues_set, played_timestamp, inserted_timestamp, 
             key_override, setting_override, created_date, last_modified_date)
            SELECT session_instance_tune_id, %s, %s, session_instance_id, tune_id, 
                   name, order_number, continues_set, played_timestamp, inserted_timestamp, 
                   key_override, setting_override, created_date, last_modified_date
            FROM session_instance_tune WHERE session_instance_tune_id = %s
        ''', (operation, changed_by, record_id))

@app.route('/')
def hello_world():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get active sessions (null or future termination dates)
        cur.execute('''
            SELECT session_id, name, path, city, state, country
            FROM session 
            WHERE termination_date IS NULL OR termination_date > CURRENT_DATE
            ORDER BY name
        ''')
        active_sessions = cur.fetchall()
        
        # For each active session, get the 3 most recent session instances
        sessions_with_instances = []
        for session in active_sessions:
            session_id, name, path, city, state, country = session
            
            cur.execute('''
                SELECT date
                FROM session_instance
                WHERE session_id = %s
                ORDER BY date DESC
                LIMIT 3
            ''', (session_id,))
            recent_instances = cur.fetchall()
            
            sessions_with_instances.append({
                'session_id': session_id,
                'name': name,
                'path': path,
                'city': city,
                'state': state,
                'country': country,
                'recent_instances': [instance[0] for instance in recent_instances]
            })
        
        cur.close()
        conn.close()
        
        return render_template('home.html', active_sessions=sessions_with_instances)
    
    except Exception as e:
        return f"Database connection failed: {str(e)}"

@app.route('/magic')
def magic():
    tune_type = request.args.get('type', 'reel')
    # Convert URL parameter back to database format
    db_tune_type = tune_type.replace('+', ' ')
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''
            SELECT t.tune_id, t.name, t.tune_type, COUNT(sit.session_instance_tune_id) AS instance_count
            FROM tune t
            JOIN session_tune st ON t.tune_id = st.tune_id
            LEFT JOIN session_instance_tune sit ON st.session_id = (
                SELECT si.session_id 
                FROM session_instance si 
                WHERE si.session_instance_id = sit.session_instance_id
            ) AND st.tune_id = sit.tune_id
            WHERE st.session_id = 1 AND lower(t.tune_type) = lower(%s)
            GROUP BY t.tune_id, t.name, t.tune_type
            HAVING COUNT(sit.session_instance_tune_id) > 1
        ''', (db_tune_type,))
        
        all_tunes = cur.fetchall()
        cur.close()
        conn.close()
        
        if len(all_tunes) >= 3:
            # Randomly select 3 tunes
            selected_tunes = random.sample(all_tunes, 3)
            
            # Sort by instance_count to get low, middle, high
            sorted_tunes = sorted(selected_tunes, key=lambda x: x[3])
            
            # Reorder as middle, low, high
            if len(sorted_tunes) == 3:
                ordered_tunes = [sorted_tunes[1], sorted_tunes[0], sorted_tunes[2]]  # middle, low, high
            else:
                ordered_tunes = sorted_tunes
        else:
            ordered_tunes = all_tunes
        
        tune_types = ['reel', 'jig', 'slip+jig', 'slide', 'polka']
        
        return render_template('magic.html', tunes=ordered_tunes, tune_types=tune_types, current_type=tune_type)
    
    except Exception as e:
        return f"Database connection failed: {str(e)}"

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

@app.route('/sessions/<path:session_path>/tunes')
def session_tunes(session_path):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get session info
        cur.execute('''
            SELECT session_id, name FROM session WHERE path = %s
        ''', (session_path,))
        session_info = cur.fetchone()
        
        if not session_info:
            cur.close()
            conn.close()
            return f"Session not found: {session_path}", 404
            
        session_id, session_name = session_info
        
        # Get session tunes with play counts and popularity data
        cur.execute('''
            SELECT 
                st.tune_id,
                COALESCE(st.alias, t.name) AS tune_name,
                t.tune_type,
                COUNT(sit.session_instance_tune_id) AS play_count,
                COALESCE(t.tunebook_count_cached, 0) AS tunebook_count,
                st.setting_id
            FROM session_tune st
            LEFT JOIN tune t ON st.tune_id = t.tune_id
            LEFT JOIN session_instance_tune sit ON st.tune_id = sit.tune_id
            LEFT JOIN session_instance si ON sit.session_instance_id = si.session_instance_id
            WHERE st.session_id = %s AND (si.session_id = %s OR si.session_id IS NULL)
            GROUP BY st.tune_id, st.alias, t.name, t.tune_type, t.tunebook_count_cached, st.setting_id
            ORDER BY play_count DESC, tunebook_count DESC, tune_name ASC
        ''', (session_id, session_id))
        
        tunes = cur.fetchall()
        cur.close()
        conn.close()
        
        return render_template('session_tunes.html', 
                             session_path=session_path,
                             session_name=session_name, 
                             tunes=tunes)
                             
    except Exception as e:
        return f"Database connection failed: {str(e)}"

@app.route('/sessions/<path:session_path>/tunes/<int:tune_id>')
def session_tune_info(session_path, tune_id):
    # Get optional session_instance_date from query parameter
    session_instance_date = request.args.get('from_date')
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get session info
        cur.execute('''
            SELECT session_id, name FROM session WHERE path = %s
        ''', (session_path,))
        session_info = cur.fetchone()
        
        if not session_info:
            cur.close()
            conn.close()
            return f"Session not found: {session_path}", 404
            
        session_id, session_name = session_info
        
        # Get tune basic info
        cur.execute('''
            SELECT name, tune_type, tunebook_count_cached 
            FROM tune 
            WHERE tune_id = %s
        ''', (tune_id,))
        tune_info = cur.fetchone()
        
        if not tune_info:
            cur.close()
            conn.close()
            return f"Tune not found: {tune_id}", 404
            
        tune_name, tune_type, tunebook_count = tune_info
        
        # Get session_tune info (setting, overridden key, alias)
        cur.execute('''
            SELECT setting_id, key, alias 
            FROM session_tune 
            WHERE session_id = %s AND tune_id = %s
        ''', (session_id, tune_id))
        session_tune_info = cur.fetchone()
        
        if not session_tune_info:
            cur.close()
            conn.close()
            return f"Tune not found in this session: {tune_id}", 404
        
        setting_id, overridden_key, alias = session_tune_info
        
        # Get play count for this session
        cur.execute('''
            SELECT COUNT(*) 
            FROM session_instance_tune sit
            JOIN session_instance si ON sit.session_instance_id = si.session_instance_id
            WHERE si.session_id = %s AND sit.tune_id = %s
        ''', (session_id, tune_id))
        play_count = cur.fetchone()[0]
        
        # Get session instances where this tune was played
        cur.execute('''
            SELECT DISTINCT 
                si.date,
                sit.order_number,
                sit.name AS overridden_name,
                sit.key_override,
                sit.setting_override
            FROM session_instance_tune sit
            JOIN session_instance si ON sit.session_instance_id = si.session_instance_id
            WHERE si.session_id = %s AND sit.tune_id = %s
            ORDER BY si.date DESC, sit.order_number ASC
        ''', (session_id, tune_id))
        
        play_instances = cur.fetchall()
        cur.close()
        conn.close()
        
        return render_template('session_tune_info.html',
                             session_path=session_path,
                             session_name=session_name,
                             tune_name=tune_name,
                             tune_type=tune_type,
                             tunebook_count=tunebook_count,
                             setting_id=setting_id,
                             overridden_key=overridden_key,
                             alias=alias,
                             play_count=play_count,
                             play_instances=play_instances,
                             tune_id=tune_id,
                             session_instance_date=session_instance_date)
                             
    except Exception as e:
        return f"Database connection failed: {str(e)}"

@app.route('/api/sessions/<path:session_path>/tunes/<int:tune_id>/refresh_tunebook_count', methods=['POST'])
def refresh_tunebook_count_ajax(session_path, tune_id):
    try:
        # Fetch data from thesession.org API
        api_url = f"https://thesession.org/tunes/{tune_id}?format=json"
        response = requests.get(api_url, timeout=10)
        
        if response.status_code != 200:
            return jsonify({'success': False, 'message': f'Failed to fetch data from thesession.org (status: {response.status_code})'})
        
        data = response.json()
        
        # Check if tunebooks property exists in the response
        if 'tunebooks' not in data:
            return jsonify({'success': False, 'message': 'No tunebooks data found in API response'})
        
        new_tunebook_count = data['tunebooks']
        
        # Update the database
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get current cached count
        cur.execute('SELECT tunebook_count_cached FROM tune WHERE tune_id = %s', (tune_id,))
        result = cur.fetchone()
        
        if not result:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'message': 'Tune not found in database'})
        
        current_count = result[0]
        
        # Update if different
        if current_count != new_tunebook_count:
            cur.execute(
                'UPDATE tune SET tunebook_count_cached = %s WHERE tune_id = %s',
                (new_tunebook_count, tune_id)
            )
            conn.commit()
            message = f'Updated tunebook count from {current_count} to {new_tunebook_count}'
        else:
            message = f'Tunebook count unchanged ({current_count})'
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True, 
            'message': message,
            'old_count': current_count,
            'new_count': new_tunebook_count
        })
        
    except requests.exceptions.RequestException as e:
        return jsonify({'success': False, 'message': f'Error connecting to thesession.org: {str(e)}'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error updating tunebook count: {str(e)}'})

@app.route('/sessions/<path:full_path>')
def session_handler(full_path):
    # Check if the last part of the path looks like a date (yyyy-mm-dd)
    path_parts = full_path.split('/')
    last_part = path_parts[-1]
    date_pattern = r'^\d{4}-\d{2}-\d{2}$'
    
    if re.match(date_pattern, last_part):
        # This is a session instance request
        session_path = '/'.join(path_parts[:-1])
        date = last_part
        
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute('''
                SELECT s.name, si.date, si.comments, si.session_instance_id, si.is_cancelled, 
                       si.location_override, s.location_name
                FROM session_instance si
                JOIN session s ON si.session_id = s.session_id
                WHERE s.path = %s AND si.date = %s
            ''', (session_path, date))
            session_instance = cur.fetchone()
            
            if session_instance:
                session_instance_dict = {
                    'session_name': session_instance[0],
                    'date': session_instance[1],
                    'comments': session_instance[2],
                    'session_instance_id': session_instance[3],
                    'is_cancelled': session_instance[4],
                    'location_override': session_instance[5],
                    'default_location': session_instance[6],
                    'session_path': session_path
                }
                
                # Get tunes played in this session instance
                cur.execute('''
                    SELECT 
                        sit.order_number,
                        sit.continues_set,
                        sit.tune_id,
                        COALESCE(sit.name, st.alias, t.name) AS tune_name,
                        COALESCE(sit.setting_override, st.setting_id) AS setting
                    FROM session_instance_tune sit
                    LEFT JOIN tune t ON sit.tune_id = t.tune_id
                    LEFT JOIN session_tune st ON sit.tune_id = st.tune_id AND st.session_id = (
                        SELECT si2.session_id 
                        FROM session_instance si2 
                        WHERE si2.session_instance_id = %s
                    )
                    WHERE sit.session_instance_id = %s
                    ORDER BY sit.order_number
                ''', (session_instance[3], session_instance[3]))
                
                tunes = cur.fetchall()
                cur.close()
                conn.close()
                
                # Group tunes into sets
                sets = []
                current_set = []
                for tune in tunes:
                    if not tune[1] and current_set:  # continues_set is False and we have a current set
                        sets.append(current_set)
                        current_set = []
                    current_set.append(tune)
                if current_set:
                    sets.append(current_set)
                
                return render_template('session_instance_detail.html', 
                                     session_instance=session_instance_dict, 
                                     tune_sets=sets)
            else:
                cur.close()
                conn.close()
                return f"Session instance not found: {session_path} on {date}", 404
        except Exception as e:
            return f"Database connection failed: {str(e)}"
    
    else:
        # This is a session detail request
        session_path = full_path
        
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
                
                # Fetch past session instances in descending date order
                cur.execute('''
                    SELECT date 
                    FROM session_instance 
                    WHERE session_id = %s
                    ORDER BY date DESC
                ''', (session[0],))
                past_instances = cur.fetchall()
                
                # Group past instances by year
                instances_by_year = {}
                for instance in past_instances:
                    date = instance[0]
                    year = date.year
                    if year not in instances_by_year:
                        instances_by_year[year] = []
                    instances_by_year[year].append(date)
                
                # Sort years in descending order
                sorted_years = sorted(instances_by_year.keys(), reverse=True)
                
                # Get top 20 most popular tunes for this session
                cur.execute('''
                    WITH tune_counts AS (
                        SELECT 
                            COALESCE(sit.name, st.alias, t.name) AS tune_name,
                            sit.tune_id,
                            COUNT(*) AS play_count,
                            COALESCE(t.tunebook_count_cached, 0) AS tunebook_count
                        FROM session_instance_tune sit
                        JOIN session_instance si ON sit.session_instance_id = si.session_instance_id
                        LEFT JOIN tune t ON sit.tune_id = t.tune_id
                        LEFT JOIN session_tune st ON sit.tune_id = st.tune_id AND st.session_id = %s
                        WHERE si.session_id = %s AND COALESCE(sit.name, st.alias, t.name) IS NOT NULL
                        GROUP BY COALESCE(sit.name, st.alias, t.name), sit.tune_id, COALESCE(t.tunebook_count_cached, 0)
                    )
                    SELECT tune_name, tune_id, play_count, tunebook_count
                    FROM tune_counts
                    ORDER BY play_count DESC, tunebook_count DESC, tune_name ASC
                    LIMIT 20
                ''', (session[0], session[0]))
                
                popular_tunes = cur.fetchall()
                
                cur.close()
                conn.close()
                
                return render_template('session_detail.html', session=session_dict, instances_by_year=instances_by_year, sorted_years=sorted_years, popular_tunes=popular_tunes)
            else:
                cur.close()
                conn.close()
                return f"Session not found: {session_path}", 404
        except Exception as e:
            return f"Database connection failed: {str(e)}"

@app.route('/api/sessions/<path:session_path>/add_instance', methods=['POST'])
def add_session_instance_ajax(session_path):
    date = request.json.get('date', '').strip()
    location = request.json.get('location', '').strip() if request.json.get('location') else None
    comments = request.json.get('comments', '').strip() if request.json.get('comments') else None
    cancelled = request.json.get('cancelled', False)
    
    if not date:
        return jsonify({'success': False, 'message': 'Please enter a session date'})
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get session_id and location_name for this session_path
        cur.execute('SELECT session_id, location_name FROM session WHERE path = %s', (session_path,))
        session_result = cur.fetchone()
        if not session_result:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'message': 'Session not found'})
        
        session_id, session_location_name = session_result
        
        # Check if session instance already exists for this date
        cur.execute('''
            SELECT session_instance_id FROM session_instance 
            WHERE session_id = %s AND date = %s
        ''', (session_id, date))
        existing_instance = cur.fetchone()
        
        if existing_instance:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'message': f'Session instance for {date} already exists'})
        
        # Determine location_override: only set if location is provided AND different from session's location_name
        location_override = None
        if location and location != session_location_name:
            location_override = location
        
        # Insert new session instance
        cur.execute('''
            INSERT INTO session_instance (session_id, date, location_override, is_cancelled, comments)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING session_instance_id
        ''', (session_id, date, location_override, cancelled, comments))
        
        session_instance_result = cur.fetchone()
        if not session_instance_result:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'message': 'Failed to create session instance'})
        
        session_instance_id = session_instance_result[0]
        
        # Save the newly created session instance to history
        save_to_history(cur, 'session_instance', 'INSERT', session_instance_id)
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'message': f'Session instance for {date} created successfully!'})
    
    except Exception as e:
        return jsonify({'success': False, 'message': f'Failed to create session instance: {str(e)}'})

@app.route('/api/sessions/<path:session_path>/<date>/update', methods=['PUT'])
def update_session_instance_ajax(session_path, date):
    new_date = request.json.get('date', '').strip()
    location = request.json.get('location', '').strip() if request.json.get('location') else None
    comments = request.json.get('comments', '').strip() if request.json.get('comments') else None
    cancelled = request.json.get('cancelled', False)
    
    if not new_date:
        return jsonify({'success': False, 'message': 'Please enter a session date'})
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get session_id and location_name for this session_path
        cur.execute('SELECT session_id, location_name FROM session WHERE path = %s', (session_path,))
        session_result = cur.fetchone()
        if not session_result:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'message': 'Session not found'})
        
        session_id, session_location_name = session_result
        
        # Get the session instance ID
        cur.execute('''
            SELECT session_instance_id FROM session_instance 
            WHERE session_id = %s AND date = %s
        ''', (session_id, date))
        instance_result = cur.fetchone()
        
        if not instance_result:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'message': 'Session instance not found'})
        
        session_instance_id = instance_result[0]
        
        # If date is changing, check if new date conflicts with existing instance
        if new_date != date:
            cur.execute('''
                SELECT session_instance_id FROM session_instance 
                WHERE session_id = %s AND date = %s
            ''', (session_id, new_date))
            existing_instance = cur.fetchone()
            
            if existing_instance:
                cur.close()
                conn.close()
                return jsonify({'success': False, 'message': f'Session instance for {new_date} already exists'})
        
        # Determine location_override: only set if location is provided AND different from session's location_name
        location_override = None
        if location and location != session_location_name:
            location_override = location
        
        # Save current state to history before update
        save_to_history(cur, 'session_instance', 'UPDATE', session_instance_id)
        
        # Update the session instance
        cur.execute('''
            UPDATE session_instance 
            SET date = %s, location_override = %s, is_cancelled = %s, comments = %s
            WHERE session_instance_id = %s
        ''', (new_date, location_override, cancelled, comments, session_instance_id))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'message': f'Session instance updated successfully!'})
    
    except Exception as e:
        return jsonify({'success': False, 'message': f'Failed to update session instance: {str(e)}'})

@app.route('/api/sessions/<path:session_path>/<date>/tune_count')
def get_session_tune_count_ajax(session_path, date):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get tune count for this session instance
        cur.execute('''
            SELECT COUNT(*)
            FROM session_instance_tune sit
            JOIN session_instance si ON sit.session_instance_id = si.session_instance_id
            JOIN session s ON si.session_id = s.session_id
            WHERE s.path = %s AND si.date = %s
        ''', (session_path, date))
        
        tune_count = cur.fetchone()[0]
        
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'tune_count': tune_count})
    
    except Exception as e:
        return jsonify({'success': False, 'message': f'Failed to get tune count: {str(e)}'})

@app.route('/api/sessions/<path:session_path>/<date>/delete', methods=['DELETE'])
def delete_session_instance_ajax(session_path, date):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get session_id for this session_path
        cur.execute('SELECT session_id FROM session WHERE path = %s', (session_path,))
        session_result = cur.fetchone()
        if not session_result:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'message': 'Session not found'})
        
        session_id = session_result[0]
        
        # Get the session instance ID
        cur.execute('''
            SELECT session_instance_id FROM session_instance 
            WHERE session_id = %s AND date = %s
        ''', (session_id, date))
        instance_result = cur.fetchone()
        
        if not instance_result:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'message': 'Session instance not found'})
        
        session_instance_id = instance_result[0]
        
        # Save to history before deletion
        save_to_history(cur, 'session_instance', 'DELETE', session_instance_id)
        
        # Get all session_instance_tune records to save to history before deletion
        cur.execute('''
            SELECT session_instance_tune_id FROM session_instance_tune 
            WHERE session_instance_id = %s
        ''', (session_instance_id,))
        tune_records = cur.fetchall()
        
        # Save each tune record to history before deletion
        for tune_record in tune_records:
            save_to_history(cur, 'session_instance_tune', 'DELETE', tune_record[0])
        
        # Explicitly delete session_instance_tune records first
        cur.execute('''
            DELETE FROM session_instance_tune WHERE session_instance_id = %s
        ''', (session_instance_id,))
        
        # Then delete the session instance
        cur.execute('''
            DELETE FROM session_instance WHERE session_instance_id = %s
        ''', (session_instance_id,))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'message': f'Session instance for {date} deleted successfully!'})
    
    except Exception as e:
        return jsonify({'success': False, 'message': f'Failed to delete session instance: {str(e)}'})

@app.route('/api/sessions/<path:session_path>/<date>/add_tune', methods=['POST'])
def add_tune_ajax(session_path, date):
    tune_names_input = request.json.get('tune_name', '').strip()
    if not tune_names_input:
        return jsonify({'success': False, 'message': 'Please enter tune name(s)'})
    
    # Parse newline-separated sets, with comma-separated tune names within each set
    lines = [line.strip() for line in tune_names_input.split('\n') if line.strip()]
    
    if not lines:
        return jsonify({'success': False, 'message': 'Please enter tune name(s)'})
    
    # Build sets structure: list of lists, where each inner list is tunes in a set
    tune_sets = []
    for line in lines:
        tune_names_in_set = [normalize_apostrophes(name.strip()) for name in line.split(',') if name.strip()]
        if tune_names_in_set:
            tune_sets.append(tune_names_in_set)
    
    if not tune_sets:
        return jsonify({'success': False, 'message': 'Please enter tune name(s)'})
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get session_id for this session_path
        cur.execute('SELECT session_id FROM session WHERE path = %s', (session_path,))
        session_result = cur.fetchone()
        if not session_result:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'message': 'Session not found'})
        
        session_id = session_result[0]
        
        # Process each set of tunes
        total_tunes_added = 0
        
        for set_index, tune_names_in_set in enumerate(tune_sets):
            # Process each tune name in this set to determine tune_id or use as name-only
            tune_data = []  # List of (tune_id, name) tuples for this set
            
            for tune_name in tune_names_in_set:
                tune_id = None
                final_name = tune_name
                
                # First, search session_tune table for alias match (case insensitive)
                cur.execute('''
                    SELECT tune_id 
                    FROM session_tune 
                    WHERE session_id = %s AND LOWER(alias) = LOWER(%s)
                ''', (session_id, tune_name))
                
                session_tune_matches = cur.fetchall()
                
                if len(session_tune_matches) > 1:
                    cur.close()
                    conn.close()
                    return jsonify({'success': False, 'message': f'Multiple tunes found with alias "{tune_name}" in this session. Please be more specific.'})
                elif len(session_tune_matches) == 1:
                    tune_id = session_tune_matches[0][0]
                else:
                    # No alias match, search tune table by name with flexible "The " matching
                    cur.execute('''
                        SELECT tune_id, name 
                        FROM tune 
                        WHERE (LOWER(name) = LOWER(%s) 
                        OR LOWER(name) = LOWER('The ' || %s) 
                        OR LOWER('The ' || name) = LOWER(%s))
                    ''', (tune_name, tune_name, tune_name))
                    
                    tune_matches = cur.fetchall()
                    
                    if len(tune_matches) > 1:
                        cur.close()
                        conn.close()
                        return jsonify({'success': False, 'message': f'Multiple tunes found with name "{tune_name}". Please be more specific or use an alias.'})
                    elif len(tune_matches) == 1:
                        tune_id = tune_matches[0][0]
                        final_name = tune_matches[0][1]  # Use the actual tune name from database
                    # If no matches found, tune_id stays None and we'll save as name-only
                
                tune_data.append((tune_id, final_name))
            
            # Add all tunes in this set
            for i, (tune_id, name) in enumerate(tune_data):
                # First tune in each set starts a new set (continues_set = False), subsequent tunes continue the set (continues_set = True)
                starts_set = (i == 0)
                
                # Use the existing stored procedure for both tune_id and name-based records
                cur.execute('SELECT insert_session_instance_tune(%s, %s, %s, %s, %s, %s)', 
                           (session_id, date, tune_id, None, name if tune_id is None else None, starts_set))
                total_tunes_added += 1
        
        conn.commit()
        cur.close()
        conn.close()
        
        if len(tune_sets) == 1 and len(tune_sets[0]) == 1:
            message = 'Tune added successfully!'
        elif len(tune_sets) == 1:
            message = f'Set of {len(tune_sets[0])} tunes added successfully!'
        else:
            message = f'{total_tunes_added} tunes in {len(tune_sets)} sets added successfully!'
        
        return jsonify({'success': True, 'message': message})
    
    except Exception as e:
        return jsonify({'success': False, 'message': f'Failed to add tune(s): {str(e)}'})

@app.route('/api/sessions/<path:session_path>/<date>/delete_tune_by_order/<int:order_number>', methods=['DELETE'])
def delete_tune_by_order_ajax(session_path, date, order_number):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get the tune info and session_instance_tune_id for history
        cur.execute('''
            SELECT 
                COALESCE(sit.name, st.alias, t.name) AS tune_name,
                sit.continues_set,
                sit.session_instance_id,
                sit.tune_id,
                sit.session_instance_tune_id
            FROM session_instance_tune sit
            LEFT JOIN tune t ON sit.tune_id = t.tune_id
            LEFT JOIN session_tune st ON sit.tune_id = st.tune_id AND st.session_id = (
                SELECT si.session_id 
                FROM session_instance si 
                WHERE si.session_instance_id = sit.session_instance_id
            )
            JOIN session_instance si ON sit.session_instance_id = si.session_instance_id
            JOIN session s ON si.session_id = s.session_id
            WHERE s.path = %s AND si.date = %s AND sit.order_number = %s
        ''', (session_path, date, order_number))
        
        tune_info = cur.fetchone()
        if not tune_info:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'message': 'Tune not found'})
        
        tune_name, continues_set, session_instance_id, tune_id, session_instance_tune_id = tune_info
        
        # Save to history before making changes
        save_to_history(cur, 'session_instance_tune', 'DELETE', session_instance_tune_id)
        
        # If this tune starts a set (continues_set = False) and there's a next tune,
        # update the next tune to start the set
        if not continues_set:
            # Get the next tune's ID for history
            cur.execute('''
                SELECT session_instance_tune_id 
                FROM session_instance_tune 
                WHERE session_instance_id = %s AND order_number = %s
            ''', (session_instance_id, order_number + 1))
            next_tune_result = cur.fetchone()
            
            if next_tune_result:
                next_tune_id = next_tune_result[0]
                save_to_history(cur, 'session_instance_tune', 'UPDATE', next_tune_id)
                
            cur.execute('''
                UPDATE session_instance_tune 
                SET continues_set = FALSE 
                WHERE session_instance_id = %s 
                AND order_number = %s
            ''', (session_instance_id, order_number + 1))
        
        # Delete the tune by order number (works for both tune_id and name-based records)
        cur.execute('''
            DELETE FROM session_instance_tune 
            WHERE session_instance_id = %s 
            AND order_number = %s
        ''', (session_instance_id, order_number))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'message': f'{tune_name} deleted from position {order_number} in the set.'})
    
    except Exception as e:
        return jsonify({'success': False, 'message': f'Failed to delete tune: {str(e)}'})

@app.route('/api/sessions/<path:session_path>/<date>/link_tune', methods=['POST'])
def link_tune_ajax(session_path, date):
    tune_input = request.json.get('tune_id', '').strip()
    tune_name = request.json.get('tune_name', '').strip()
    order_number = request.json.get('order_number')
    
    if not tune_input or not tune_name or order_number is None:
        return jsonify({'success': False, 'message': 'Missing required parameters'})
    
    # Parse tune ID and setting ID from input
    # Check if it's a URL with setting
    url_pattern = r'.*thesession\.org\/tunes\/(\d+)(?:#setting(\d+))?'
    url_match = re.search(url_pattern, tune_input)
    
    if url_match:
        tune_id = url_match.group(1)
        setting_id = int(url_match.group(2)) if url_match.group(2) else None
    elif re.match(r'^\d+$', tune_input):
        # Just a tune ID number
        tune_id = tune_input
        setting_id = None
    else:
        return jsonify({'success': False, 'message': 'Invalid tune ID or URL format'})
    
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get session_id for this session_path
        cur.execute('SELECT session_id FROM session WHERE path = %s', (session_path,))
        session_result = cur.fetchone()
        if not session_result:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'message': 'Session not found'})
        
        session_id = session_result[0]
        
        # Get session instance ID
        cur.execute('''
            SELECT session_instance_id FROM session_instance 
            WHERE session_id = %s AND date = %s
        ''', (session_id, date))
        session_instance_result = cur.fetchone()
        if not session_instance_result:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'message': 'Session instance not found'})
        
        session_instance_id = session_instance_result[0]
        
        # Check if tune_id is already in session_tune for this session
        cur.execute('''
            SELECT tune_id FROM session_tune 
            WHERE session_id = %s AND tune_id = %s
        ''', (session_id, tune_id))
        session_tune_exists = cur.fetchone()
        
        if session_tune_exists:
            # Get the session_instance_tune_id for history
            cur.execute('''
                SELECT session_instance_tune_id 
                FROM session_instance_tune 
                WHERE session_instance_id = %s AND order_number = %s
            ''', (session_instance_id, order_number))
            sit_result = cur.fetchone()
            
            if sit_result:
                sit_id = sit_result[0]
                save_to_history(cur, 'session_instance_tune', 'UPDATE', sit_id)
            
            # Tune already in session_tune, just update session_instance_tune
            # Use setting_id as setting_override if provided
            cur.execute('''
                UPDATE session_instance_tune 
                SET tune_id = %s, name = %s, setting_override = %s
                WHERE session_instance_id = %s AND order_number = %s
            ''', (tune_id, tune_name, setting_id, session_instance_id, order_number))
            
            setting_msg = f' with setting #{setting_id}' if setting_id else ''
            message = f'Linked "{tune_name}" to existing tune in session{setting_msg}'
        else:
            # Check if tune exists in tune table
            cur.execute('SELECT name FROM tune WHERE tune_id = %s', (tune_id,))
            tune_exists = cur.fetchone()
            
            if tune_exists:
                # Add to session_tune with alias and setting_id
                cur.execute('''
                    INSERT INTO session_tune (session_id, tune_id, alias, setting_id)
                    VALUES (%s, %s, %s, %s)
                ''', (session_id, tune_id, tune_name, setting_id))
                
                # Save the newly inserted record to history
                save_to_history(cur, 'session_tune', 'INSERT', (session_id, tune_id))
                
                # Get the session_instance_tune_id for history before update
                cur.execute('''
                    SELECT session_instance_tune_id 
                    FROM session_instance_tune 
                    WHERE session_instance_id = %s AND order_number = %s
                ''', (session_instance_id, order_number))
                sit_result = cur.fetchone()
                
                if sit_result:
                    sit_id = sit_result[0]
                    save_to_history(cur, 'session_instance_tune', 'UPDATE', sit_id)
                
                # Update session_instance_tune
                cur.execute('''
                    UPDATE session_instance_tune 
                    SET tune_id = %s, name = NULL
                    WHERE session_instance_id = %s AND order_number = %s
                ''', (tune_id, session_instance_id, order_number))
                
                setting_msg = f' with setting #{setting_id}' if setting_id else ''
                message = f'Added "{tune_name}" to session and linked{setting_msg}'
            else:
                # Tune doesn't exist in our database, fetch from thesession.org
                try:
                    # Fetch data from thesession.org API
                    api_url = f"https://thesession.org/tunes/{tune_id}?format=json"
                    response = requests.get(api_url, timeout=10)
                    
                    if response.status_code == 404:
                        cur.close()
                        conn.close()
                        return jsonify({'success': False, 'message': f'Tune #{tune_id} not found on thesession.org'})
                    elif response.status_code != 200:
                        cur.close()
                        conn.close()
                        return jsonify({'success': False, 'message': f'Failed to fetch tune data from thesession.org (status: {response.status_code})'})
                    
                    data = response.json()
                    
                    # Extract required fields
                    if 'name' not in data or 'type' not in data:
                        cur.close()
                        conn.close()
                        return jsonify({'success': False, 'message': 'Invalid tune data received from thesession.org'})
                    
                    tune_name_from_api = data['name']
                    tune_type = data['type'].title()  # Convert to title case
                    tunebook_count = data.get('tunebooks', 0)  # Default to 0 if not present
                    
                    # Insert new tune into tune table
                    cur.execute('''
                        INSERT INTO tune (tune_id, name, tune_type, tunebook_count_cached)
                        VALUES (%s, %s, %s, %s)
                    ''', (tune_id, tune_name_from_api, tune_type, tunebook_count))
                    
                    # Save the newly inserted tune to history
                    save_to_history(cur, 'tune', 'INSERT', tune_id)
                    
                    # Determine if we need to use an alias
                    alias = tune_name if tune_name != tune_name_from_api else None
                    
                    # Add to session_tune with alias and setting_id
                    cur.execute('''
                        INSERT INTO session_tune (session_id, tune_id, alias, setting_id)
                        VALUES (%s, %s, %s, %s)
                    ''', (session_id, tune_id, alias, setting_id))
                    
                    # Save the newly inserted session_tune to history
                    save_to_history(cur, 'session_tune', 'INSERT', (session_id, tune_id))
                    
                    # Update session_instance_tune
                    cur.execute('''
                        UPDATE session_instance_tune 
                        SET tune_id = %s, name = NULL
                        WHERE session_instance_id = %s AND order_number = %s
                    ''', (tune_id, session_instance_id, order_number))
                    
                    setting_msg = f' with setting #{setting_id}' if setting_id else ''
                    message = f'Fetched "{tune_name_from_api}" from thesession.org and added to session{setting_msg}'
                    
                except requests.exceptions.Timeout:
                    cur.close()
                    conn.close()
                    return jsonify({'success': False, 'message': 'Timeout connecting to thesession.org'})
                except requests.exceptions.RequestException as e:
                    cur.close()
                    conn.close()
                    return jsonify({'success': False, 'message': f'Error connecting to thesession.org: {str(e)}'})
                except Exception as e:
                    cur.close()
                    conn.close()
                    return jsonify({'success': False, 'message': f'Error processing tune data: {str(e)}'})
        
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'message': message})
    
    except Exception as e:
        return jsonify({'success': False, 'message': f'Failed to link tune: {str(e)}'})

@app.route('/api/sessions/<path:session_path>/<date>/tunes')
def get_session_tunes_ajax(session_path, date):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get session instance ID
        cur.execute('''
            SELECT si.session_instance_id
            FROM session_instance si
            JOIN session s ON si.session_id = s.session_id
            WHERE s.path = %s AND si.date = %s
        ''', (session_path, date))
        session_instance = cur.fetchone()
        
        if not session_instance:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'message': 'Session instance not found'})
        
        session_instance_id = session_instance[0]
        
        # Get tunes played in this session instance
        cur.execute('''
            SELECT 
                sit.order_number,
                sit.continues_set,
                sit.tune_id,
                COALESCE(sit.name, st.alias, t.name) AS tune_name,
                COALESCE(sit.setting_override, st.setting_id) AS setting
            FROM session_instance_tune sit
            LEFT JOIN tune t ON sit.tune_id = t.tune_id
            LEFT JOIN session_tune st ON sit.tune_id = st.tune_id AND st.session_id = (
                SELECT si2.session_id 
                FROM session_instance si2 
                WHERE si2.session_instance_id = %s
            )
            WHERE sit.session_instance_id = %s
            ORDER BY sit.order_number
        ''', (session_instance_id, session_instance_id))
        
        tunes = cur.fetchall()
        cur.close()
        conn.close()
        
        # Group tunes into sets
        sets = []
        current_set = []
        for tune in tunes:
            if not tune[1] and current_set:  # continues_set is False and we have a current set
                sets.append(current_set)
                current_set = []
            current_set.append(tune)
        if current_set:
            sets.append(current_set)
        
        return jsonify({'success': True, 'tune_sets': sets})
    
    except Exception as e:
        return jsonify({'success': False, 'message': f'Failed to get tunes: {str(e)}'})
