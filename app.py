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

# Configure Flask to handle trailing slashes consistently
app.url_map.strict_slashes = False

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
            (tune_id, operation, changed_by, name, tune_type, tunebook_count_cached, tunebook_count_cached_date, created_date, last_modified_date)
            SELECT tune_id, %s, %s, name, tune_type, tunebook_count_cached, tunebook_count_cached_date, created_date, last_modified_date
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

def find_matching_tune(cur, session_id, tune_name, allow_multiple_session_aliases=False):
    """
    Find a matching tune by searching session aliases and tune names.
    
    Returns:
        tuple: (tune_id, final_name, error_message) where:
        - tune_id: The matched tune ID or None if no match
        - final_name: The actual tune name from database or original name
        - error_message: Error message if multiple matches found, None otherwise
    """
    # Normalize the search string the same way we normalize input
    normalized_tune_name = normalize_apostrophes(tune_name.strip())
    # First, search session_tune table for alias match (case insensitive)
    cur.execute('''
        SELECT tune_id 
        FROM session_tune 
        WHERE session_id = %s AND LOWER(alias) = LOWER(%s)
    ''', (session_id, normalized_tune_name))
    
    session_tune_matches = cur.fetchall()
    
    if len(session_tune_matches) > 1 and not allow_multiple_session_aliases:
        return None, tune_name, f'Multiple tunes found with alias "{tune_name}" in this session. Please be more specific.'
    elif len(session_tune_matches) == 1:
        return session_tune_matches[0][0], tune_name, None
    elif len(session_tune_matches) == 0:
        # No session_tune alias match, search session_tune_alias table
        cur.execute('''
            SELECT tune_id 
            FROM session_tune_alias 
            WHERE session_id = %s AND LOWER(alias) = LOWER(%s)
        ''', (session_id, normalized_tune_name))
        
        alias_matches = cur.fetchall()
        
        if len(alias_matches) > 1:
            return None, tune_name, f'Multiple tunes found with alias "{tune_name}" in this session. Please be more specific.'
        elif len(alias_matches) == 1:
            return alias_matches[0][0], tune_name, None
        elif len(alias_matches) == 0:
            # No alias match in either table, search tune table by name with flexible "The " matching
            cur.execute('''
                SELECT tune_id, name 
                FROM tune 
                WHERE (LOWER(name) = LOWER(%s) 
                OR LOWER(name) = LOWER('The ' || %s) 
                OR LOWER('The ' || name) = LOWER(%s))
            ''', (normalized_tune_name, normalized_tune_name, normalized_tune_name))
            
            tune_matches = cur.fetchall()
            
            if len(tune_matches) > 1:
                return None, tune_name, f'Multiple tunes found with name "{tune_name}". Please be more specific or use an alias.'
            elif len(tune_matches) == 1:
                return tune_matches[0][0], tune_matches[0][1], None
    
    # No matches found
    return None, tune_name, None

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
        cur.execute('SELECT name, path, city, state, country, termination_date FROM session ORDER BY name;')
        sessions = cur.fetchall()
        cur.close()
        conn.close()
        return render_template('sessions.html', sessions=sessions)
    except Exception as e:
        return f"Database connection failed: {str(e)}"

@app.route('/api/sessions/data')
def sessions_data():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('SELECT name, path, city, state, country, termination_date FROM session ORDER BY name;')
        sessions = cur.fetchall()
        cur.close()
        conn.close()
        
        # Convert to list format for JSON serialization, handling dates
        sessions_list = []
        for session in sessions:
            session_data = list(session)
            # Convert date to string if it exists
            if session_data[5]:  # termination_date
                session_data[5] = session_data[5].isoformat()
            sessions_list.append(session_data)
        
        return jsonify({'sessions': sessions_list})
    except Exception as e:
        return jsonify({'error': f"Database connection failed: {str(e)}"}), 500

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
            SELECT name, tune_type, tunebook_count_cached, tunebook_count_cached_date 
            FROM tune 
            WHERE tune_id = %s
        ''', (tune_id,))
        tune_info = cur.fetchone()
        
        if not tune_info:
            cur.close()
            conn.close()
            return f"Tune not found: {tune_id}", 404
            
        tune_name, tune_type, tunebook_count, tunebook_count_cached_date = tune_info
        
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
                             tunebook_count_cached_date=tunebook_count_cached_date,
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
        
        # Always update the cached date, and update count if different
        if current_count != new_tunebook_count:
            cur.execute(
                'UPDATE tune SET tunebook_count_cached = %s, tunebook_count_cached_date = CURRENT_DATE WHERE tune_id = %s',
                (new_tunebook_count, tune_id)
            )
            message = f'Updated tunebook count from {current_count} to {new_tunebook_count}'
        else:
            cur.execute(
                'UPDATE tune SET tunebook_count_cached_date = CURRENT_DATE WHERE tune_id = %s',
                (tune_id,)
            )
            message = f'Tunebook count unchanged ({current_count})'
        
        conn.commit()
        
        # Get the current cached date (whether updated or not)
        cur.execute('SELECT tunebook_count_cached_date FROM tune WHERE tune_id = %s', (tune_id,))
        cached_date_result = cur.fetchone()
        cached_date = cached_date_result[0] if cached_date_result else None
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True, 
            'message': message,
            'old_count': current_count,
            'new_count': new_tunebook_count,
            'cached_date': cached_date.isoformat() if cached_date else None
        })
        
    except requests.exceptions.RequestException as e:
        return jsonify({'success': False, 'message': f'Error connecting to thesession.org: {str(e)}'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error updating tunebook count: {str(e)}'})

@app.route('/sessions/<path:full_path>')
def session_handler(full_path):
    # Strip trailing slash to normalize the path
    full_path = full_path.rstrip('/')
    
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
                        COALESCE(sit.setting_override, st.setting_id) AS setting,
                        t.tune_type
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
                       location_phone, location_street, city, state, country, comments, unlisted_address, 
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
                    'location_street': session[7],
                    'city': session[8],
                    'state': session[9],
                    'country': session[10],
                    'comments': session[11],
                    'unlisted_address': session[12],
                    'initiation_date': session[13],
                    'termination_date': session[14],
                    'recurrence': session[15]
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

@app.route('/api/sessions/<path:session_path>/update', methods=['PUT'])
def update_session_ajax(session_path):
    name = request.json.get('name', '').strip()
    path = request.json.get('path', '').strip()
    location_name = request.json.get('location_name', '').strip() if request.json.get('location_name') else None
    location_website = request.json.get('location_website', '').strip() if request.json.get('location_website') else None
    location_phone = request.json.get('location_phone', '').strip() if request.json.get('location_phone') else None
    location_street = request.json.get('location_street', '').strip() if request.json.get('location_street') else None
    city = request.json.get('city', '').strip()
    state = request.json.get('state', '').strip()
    country = request.json.get('country', '').strip()
    comments = request.json.get('comments', '').strip() if request.json.get('comments') else None
    unlisted_address = request.json.get('unlisted_address', False)
    initiation_date = request.json.get('initiation_date', '').strip() if request.json.get('initiation_date') else None
    termination_date = request.json.get('termination_date', '').strip() if request.json.get('termination_date') else None
    recurrence = request.json.get('recurrence', '').strip() if request.json.get('recurrence') else None
    
    # Validation
    if not name:
        return jsonify({'success': False, 'message': 'Session name is required'})
    if not path:
        return jsonify({'success': False, 'message': 'Path is required'})
    if not city or not state or not country:
        return jsonify({'success': False, 'message': 'City, state, and country are required'})
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get the session_id for the current path
        cur.execute('SELECT session_id FROM session WHERE path = %s', (session_path,))
        session_result = cur.fetchone()
        if not session_result:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'message': 'Session not found'})
        
        session_id = session_result[0]
        
        # Check if the new path is already taken by another session
        if path != session_path:
            cur.execute('SELECT session_id FROM session WHERE path = %s AND session_id != %s', (path, session_id))
            existing_path = cur.fetchone()
            if existing_path:
                cur.close()
                conn.close()
                return jsonify({'success': False, 'message': f'Path "{path}" is already taken by another session'})
        
        # Save current record to history before updating
        save_to_history(cur, 'session', 'update', session_id)
        
        # Update the session
        cur.execute('''
            UPDATE session SET 
                name = %s, 
                path = %s, 
                location_name = %s, 
                location_website = %s, 
                location_phone = %s, 
                location_street = %s,
                city = %s, 
                state = %s, 
                country = %s, 
                comments = %s, 
                unlisted_address = %s, 
                initiation_date = %s, 
                termination_date = %s, 
                recurrence = %s,
                last_modified_date = CURRENT_TIMESTAMP
            WHERE session_id = %s
        ''', (name, path, location_name, location_website, location_phone, location_street,
              city, state, country, comments, unlisted_address, initiation_date, 
              termination_date, recurrence, session_id))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Session updated successfully!'})
    
    except Exception as e:
        return jsonify({'success': False, 'message': f'Failed to update session: {str(e)}'})

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
        
        # Check if the very first line starts with a delimiter
        first_line_starts_with_delimiter = lines[0].startswith((',', ';', '/'))
        
        # If first line starts with delimiter, we need to append to the existing last set
        if first_line_starts_with_delimiter:
            # Get the highest order number (last tune) to find the last set
            cur.execute('''
                SELECT order_number
                FROM session_instance_tune sit
                JOIN session_instance si ON sit.session_instance_id = si.session_instance_id
                WHERE si.session_id = %s AND si.date = %s
                ORDER BY sit.order_number DESC
                LIMIT 1
            ''', (session_id, date))
            
            last_tune_result = cur.fetchone()
            if last_tune_result:
                # There are existing tunes, so we can append to the last set
                last_order_number = last_tune_result[0]
                
                # Parse all the tune names from all lines and add them to the existing last set
                all_tune_names = []
                for line in lines:
                    tune_names_in_line = [normalize_apostrophes(name.strip()) for name in re.split('[,;/]', line) if name.strip()]
                    all_tune_names.extend(tune_names_in_line)
                
                if all_tune_names:
                    # Use the add_tunes_to_set logic
                    total_tunes_added = 0
                    for tune_name in all_tune_names:
                        # Use the refactored tune matching function
                        tune_id, final_name, error_message = find_matching_tune(cur, session_id, tune_name)
                        
                        if error_message:
                            cur.close()
                            conn.close()
                            return jsonify({'success': False, 'message': error_message})
                        
                        # Add tune to continue the existing set
                        cur.execute('SELECT insert_session_instance_tune(%s, %s, %s, %s, %s, %s)', 
                                   (session_id, date, tune_id, None, final_name if tune_id is None else None, False))  # starts_set = False (continues existing set)
                        total_tunes_added += 1
                    
                    conn.commit()
                    cur.close()
                    conn.close()
                    
                    if total_tunes_added == 1:
                        message = 'Tune added to existing set successfully!'
                    else:
                        message = f'{total_tunes_added} tunes added to existing set successfully!'
                    
                    return jsonify({'success': True, 'message': message})
            # If no existing tunes, fall through to normal processing (treat as if no delimiter)
        
        # Build sets structure: list of lists, where each inner list is tunes in a set
        tune_sets = []
        for line in lines:
            # Check if line starts with a delimiter (comma, semicolon, or slash)
            starts_with_delimiter = line.startswith((',', ';', '/'))
            
            # Split by comma, semicolon, or forward slash
            tune_names_in_set = [normalize_apostrophes(name.strip()) for name in re.split('[,;/]', line) if name.strip()]
            
            if tune_names_in_set:
                if starts_with_delimiter and tune_sets:
                    # Add to the previous set if line starts with delimiter and there's a previous set
                    tune_sets[-1].extend(tune_names_in_set)
                else:
                    # Create a new set
                    tune_sets.append(tune_names_in_set)
        
        if not tune_sets:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'message': 'Please enter tune name(s)'})
        
        # Process each set of tunes
        total_tunes_added = 0
        
        for set_index, tune_names_in_set in enumerate(tune_sets):
            # Process each tune name in this set to determine tune_id or use as name-only
            tune_data = []  # List of (tune_id, name) tuples for this set
            
            for tune_name in tune_names_in_set:
                # Use the refactored tune matching function
                tune_id, final_name, error_message = find_matching_tune(cur, session_id, tune_name)
                
                if error_message:
                    cur.close()
                    conn.close()
                    return jsonify({'success': False, 'message': error_message})
                
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
                        INSERT INTO tune (tune_id, name, tune_type, tunebook_count_cached, tunebook_count_cached_date)
                        VALUES (%s, %s, %s, %s, CURRENT_DATE)
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
                COALESCE(sit.setting_override, st.setting_id) AS setting,
                t.tune_type
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
# Move Set endpoint
@app.route('/api/sessions/<path:session_path>/<date>/move_set', methods=['POST'])
def move_set_ajax(session_path, date):
    data = request.get_json()
    order_number = data.get('order_number')
    direction = data.get('direction')  # 'up' or 'down'
    
    if not order_number or not direction or direction not in ['up', 'down']:
        return jsonify({'success': False, 'message': 'Invalid parameters'})
    
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
        
        # Get all tunes ordered by order_number
        cur.execute('''
            SELECT order_number, continues_set, session_instance_tune_id
            FROM session_instance_tune 
            WHERE session_instance_id = %s 
            ORDER BY order_number
        ''', (session_instance_id,))
        
        all_tunes = cur.fetchall()
        if not all_tunes:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'message': 'No tunes found'})
        
        # Find the tune and its set
        target_tune_index = next((i for i, tune in enumerate(all_tunes) if tune[0] == order_number), -1)
        if target_tune_index == -1:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'message': 'Tune not found'})
        
        # Group tunes into sets to identify set boundaries
        sets = []
        current_set = []
        for tune in all_tunes:
            if not tune[1] and current_set:  # continues_set is False and we have a current set
                sets.append(current_set)
                current_set = []
            current_set.append(tune)
        if current_set:
            sets.append(current_set)
        
        # Find which set the target tune belongs to
        target_set_index = -1
        for set_index, tune_set in enumerate(sets):
            if any(tune[0] == order_number for tune in tune_set):
                target_set_index = set_index
                break
        
        if target_set_index == -1:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'message': 'Tune set not found'})
        
        # Check if move is possible
        if direction == 'up' and target_set_index == 0:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'message': 'Cannot move first set up'})
        
        if direction == 'down' and target_set_index == len(sets) - 1:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'message': 'Cannot move last set down'})
        
        # Save to history before making changes
        for tune_set in sets:
            for tune in tune_set:
                save_to_history(cur, 'session_instance_tune', 'UPDATE', tune[2], 'move_set')
        
        # Perform the move
        target_set = sets[target_set_index]
        
        if direction == 'up':
            # Move set up - swap with previous set
            prev_set = sets[target_set_index - 1]
            
            # Get the order numbers where each set should go
            prev_set_start_order = prev_set[0][0]
            target_set_start_order = target_set[0][0]
            
            # Update order numbers - target set goes where prev set was
            for i, tune in enumerate(target_set):
                new_order = prev_set_start_order + i
                cur.execute('''
                    UPDATE session_instance_tune 
                    SET order_number = %s 
                    WHERE session_instance_tune_id = %s
                ''', (new_order, tune[2]))
            
            # Previous set goes after target set
            for i, tune in enumerate(prev_set):
                new_order = prev_set_start_order + len(target_set) + i
                cur.execute('''
                    UPDATE session_instance_tune 
                    SET order_number = %s 
                    WHERE session_instance_tune_id = %s
                ''', (new_order, tune[2]))
                
        else:  # direction == 'down'
            # Move set down - swap with next set
            next_set = sets[target_set_index + 1]
            
            # Get the order numbers where each set should go
            target_set_start_order = target_set[0][0]
            next_set_start_order = next_set[0][0]
            
            # Next set goes where target set was
            for i, tune in enumerate(next_set):
                new_order = target_set_start_order + i
                cur.execute('''
                    UPDATE session_instance_tune 
                    SET order_number = %s 
                    WHERE session_instance_tune_id = %s
                ''', (new_order, tune[2]))
            
            # Target set goes after next set
            for i, tune in enumerate(target_set):
                new_order = target_set_start_order + len(next_set) + i
                cur.execute('''
                    UPDATE session_instance_tune 
                    SET order_number = %s 
                    WHERE session_instance_tune_id = %s
                ''', (new_order, tune[2]))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'message': f'Set moved {direction} successfully'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Failed to move set: {str(e)}'})


# Move Tune endpoint  
@app.route('/api/sessions/<path:session_path>/<date>/move_tune', methods=['POST'])
def move_tune_ajax(session_path, date):
    data = request.get_json()
    order_number = data.get('order_number')
    direction = data.get('direction')  # 'left' or 'right'
    
    if not order_number or not direction or direction not in ['left', 'right']:
        return jsonify({'success': False, 'message': 'Invalid parameters'})
    
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
        
        # Get all tunes ordered by order_number
        cur.execute('''
            SELECT order_number, continues_set, session_instance_tune_id
            FROM session_instance_tune 
            WHERE session_instance_id = %s 
            ORDER BY order_number
        ''', (session_instance_id,))
        
        all_tunes = cur.fetchall()
        if not all_tunes:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'message': 'No tunes found'})
        
        # Group tunes into sets
        sets = []
        current_set = []
        for tune in all_tunes:
            if not tune[1] and current_set:  # continues_set is False and we have a current set
                sets.append(current_set)
                current_set = []
            current_set.append(tune)
        if current_set:
            sets.append(current_set)
        
        # Find which set and position the target tune is in
        target_set_index = -1
        target_tune_index_in_set = -1
        for set_index, tune_set in enumerate(sets):
            for tune_index, tune in enumerate(tune_set):
                if tune[0] == order_number:
                    target_set_index = set_index
                    target_tune_index_in_set = tune_index
                    break
            if target_set_index != -1:
                break
        
        if target_set_index == -1:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'message': 'Tune not found'})
        
        target_set = sets[target_set_index]
        
        # Check if move is possible
        if direction == 'left' and target_tune_index_in_set == 0:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'message': 'Cannot move leftmost tune in set left'})
        
        if direction == 'right' and target_tune_index_in_set == len(target_set) - 1:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'message': 'Cannot move rightmost tune in set right'})
        
        # Save to history before making changes
        for tune in target_set:
            save_to_history(cur, 'session_instance_tune', 'UPDATE', tune[2], 'move_tune')
        
        # Perform the move - swap order numbers and potentially continues_set values
        if direction == 'left':
            # Swap with previous tune in set
            prev_tune = target_set[target_tune_index_in_set - 1]
            target_tune = target_set[target_tune_index_in_set]
            
            # Swap order numbers
            cur.execute('''
                UPDATE session_instance_tune 
                SET order_number = %s 
                WHERE session_instance_tune_id = %s
            ''', (target_tune[0], prev_tune[2]))
            
            cur.execute('''
                UPDATE session_instance_tune 
                SET order_number = %s 
                WHERE session_instance_tune_id = %s
            ''', (prev_tune[0], target_tune[2]))
            
            # Update continues_set if moving to first position
            if target_tune_index_in_set - 1 == 0:
                # Target tune becomes the first in set (continues_set = False)
                cur.execute('''
                    UPDATE session_instance_tune 
                    SET continues_set = FALSE 
                    WHERE session_instance_tune_id = %s
                ''', (target_tune[2],))
                
                # Previous tune is no longer first (continues_set = True)
                cur.execute('''
                    UPDATE session_instance_tune 
                    SET continues_set = TRUE 
                    WHERE session_instance_tune_id = %s
                ''', (prev_tune[2],))
                
        else:  # direction == 'right'
            # Swap with next tune in set
            target_tune = target_set[target_tune_index_in_set]
            next_tune = target_set[target_tune_index_in_set + 1]
            
            # Swap order numbers
            cur.execute('''
                UPDATE session_instance_tune 
                SET order_number = %s 
                WHERE session_instance_tune_id = %s
            ''', (next_tune[0], target_tune[2]))
            
            cur.execute('''
                UPDATE session_instance_tune 
                SET order_number = %s 
                WHERE session_instance_tune_id = %s
            ''', (target_tune[0], next_tune[2]))
            
            # Update continues_set if moving from first position
            if target_tune_index_in_set == 0:
                # Next tune becomes the first in set (continues_set = False)
                cur.execute('''
                    UPDATE session_instance_tune 
                    SET continues_set = FALSE 
                    WHERE session_instance_tune_id = %s
                ''', (next_tune[2],))
                
                # Target tune is no longer first (continues_set = True)
                cur.execute('''
                    UPDATE session_instance_tune 
                    SET continues_set = TRUE 
                    WHERE session_instance_tune_id = %s
                ''', (target_tune[2],))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'message': f'Tune moved {direction} successfully'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Failed to move tune: {str(e)}'})

# Add Tunes to Set endpoint
@app.route('/api/sessions/<path:session_path>/<date>/add_tunes_to_set', methods=['POST'])
def add_tunes_to_set_ajax(session_path, date):
    data = request.get_json()
    tune_names_input = data.get('tune_names', '').strip()
    reference_order_number = data.get('reference_order_number')
    
    if not tune_names_input or reference_order_number is None:
        return jsonify({'success': False, 'message': 'Missing required parameters'})
    
    # Parse comma, semicolon, or forward slash separated tune names - same logic as existing add_tune function
    tune_names_in_set = [normalize_apostrophes(name.strip()) for name in re.split('[,;/]', tune_names_input) if name.strip()]
    
    if not tune_names_in_set:
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
        
        # Get all tunes ordered by order_number to determine set structure
        cur.execute('''
            SELECT order_number, continues_set, session_instance_tune_id
            FROM session_instance_tune 
            WHERE session_instance_id = %s 
            ORDER BY order_number
        ''', (session_instance_id,))
        
        all_tunes = cur.fetchall()
        if not all_tunes:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'message': 'No tunes found'})
        
        # Find the reference tune and determine its set
        reference_tune_index = next((i for i, tune in enumerate(all_tunes) if tune[0] == reference_order_number), -1)
        if reference_tune_index == -1:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'message': 'Reference tune not found'})
        
        # Group tunes into sets to find where to insert
        sets = []
        current_set = []
        for tune in all_tunes:
            if not tune[1] and current_set:  # continues_set is False and we have a current set
                sets.append(current_set)
                current_set = []
            current_set.append(tune)
        if current_set:
            sets.append(current_set)
        
        # Find which set the reference tune belongs to
        target_set_index = -1
        for set_index, tune_set in enumerate(sets):
            if any(tune[0] == reference_order_number for tune in tune_set):
                target_set_index = set_index
                break
        
        if target_set_index == -1:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'message': 'Reference tune set not found'})
        
        # Determine the insertion point (end of the target set)
        target_set = sets[target_set_index]
        last_order_in_set = target_set[-1][0]  # Order number of last tune in set
        
        # Calculate how many order numbers we need to shift
        num_tunes_to_add = len(tune_names_in_set)
        
        # Save all affected tunes to history before making changes
        # This includes all tunes after the insertion point
        for tune_set in sets[target_set_index + 1:]:  # All sets after target set
            for tune in tune_set:
                save_to_history(cur, 'session_instance_tune', 'UPDATE', tune[2], 'add_tunes_to_set')
        
        # Update order numbers for all tunes after the insertion point
        cur.execute('''
            UPDATE session_instance_tune 
            SET order_number = order_number + %s
            WHERE session_instance_id = %s AND order_number > %s
        ''', (num_tunes_to_add, session_instance_id, last_order_in_set))
        
        # Process each tune name to determine tune_id or use as name-only
        tune_data = []  # List of (tune_id, name) tuples for the new tunes
        
        for tune_name in tune_names_in_set:
            # Use the refactored tune matching function
            tune_id, final_name, error_message = find_matching_tune(cur, session_id, tune_name)
            
            if error_message:
                cur.close()
                conn.close()
                return jsonify({'success': False, 'message': error_message})
            
            tune_data.append((tune_id, final_name))
        
        # Insert new tunes at the end of the target set
        for i, (tune_id, name) in enumerate(tune_data):
            new_order_number = last_order_in_set + 1 + i
            continues_set = True  # All added tunes continue the existing set
            
            # Insert the new tune
            cur.execute('''
                INSERT INTO session_instance_tune 
                (session_instance_id, tune_id, name, order_number, continues_set, played_timestamp, inserted_timestamp)
                VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                RETURNING session_instance_tune_id
            ''', (session_instance_id, tune_id, name if tune_id is None else None, new_order_number, continues_set))
            
            new_tune_result = cur.fetchone()
            if new_tune_result:
                new_tune_id = new_tune_result[0]
                save_to_history(cur, 'session_instance_tune', 'INSERT', new_tune_id, 'add_tunes_to_set')
        
        conn.commit()
        cur.close()
        conn.close()
        
        if len(tune_names_in_set) == 1:
            message = f'Added "{tune_names_in_set[0]}" to the set successfully!'
        else:
            message = f'Added {len(tune_names_in_set)} tunes to the set successfully!'
        
        return jsonify({'success': True, 'message': message})
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Failed to add tunes to set: {str(e)}'})

@app.route('/api/sessions/<path:session_path>/<date>/edit_tune', methods=['POST'])
def edit_tune_ajax(session_path, date):
    order_number = request.json.get('order_number')
    new_name = normalize_apostrophes(request.json.get('new_name', '').strip())
    original_name = request.json.get('original_name', '').strip()
    tune_id = request.json.get('tune_id')
    setting_id = request.json.get('setting_id')
    
    if order_number is None or not new_name:
        return jsonify({'success': False, 'message': 'Missing required parameters'})
    
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
        
        # Get the session_instance_tune_id for history
        cur.execute('''
            SELECT session_instance_tune_id 
            FROM session_instance_tune 
            WHERE session_instance_id = %s AND order_number = %s
        ''', (session_instance_id, order_number))
        sit_result = cur.fetchone()
        
        if not sit_result:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'message': 'Tune not found'})
        
        sit_id = sit_result[0]
        
        # Save to history before making changes
        save_to_history(cur, 'session_instance_tune', 'UPDATE', sit_id)
        
        # Determine what changes need to be made based on the requirements
        if tune_id:  # This is a linked tune
            # Get the tune name from the tune table
            cur.execute('SELECT name FROM tune WHERE tune_id = %s', (tune_id,))
            tune_result = cur.fetchone()
            if not tune_result:
                cur.close()
                conn.close()
                return jsonify({'success': False, 'message': 'Tune not found in database'})
            
            actual_tune_name = tune_result[0]
            
            # Get the current session_tune alias
            cur.execute('''
                SELECT alias FROM session_tune 
                WHERE session_id = %s AND tune_id = %s
            ''', (session_id, tune_id))
            session_tune_result = cur.fetchone()
            
            if not session_tune_result:
                cur.close()
                conn.close()
                return jsonify({'success': False, 'message': 'Session tune not found'})
            
            current_alias = session_tune_result[0]
            
            if new_name != actual_tune_name:
                # The new name is different from the tune.name
                if not current_alias:
                    # No alias exists, so set the new name as the alias
                    # First save session_tune to history
                    save_to_history(cur, 'session_tune', 'UPDATE', (session_id, tune_id))
                    
                    cur.execute('''
                        UPDATE session_tune 
                        SET alias = %s
                        WHERE session_id = %s AND tune_id = %s
                    ''', (new_name, session_id, tune_id))
                    
                    # Clear any name override in session_instance_tune
                    cur.execute('''
                        UPDATE session_instance_tune 
                        SET name = NULL
                        WHERE session_instance_tune_id = %s
                    ''', (sit_id,))
                    
                    message = f'Set alias to "{new_name}" for this session'
                    
                elif current_alias == new_name:
                    # The alias matches the entered name, clear the session_instance_tune name
                    cur.execute('''
                        UPDATE session_instance_tune 
                        SET name = NULL
                        WHERE session_instance_tune_id = %s
                    ''', (sit_id,))
                    
                    message = f'Using session alias "{new_name}"'
                    
                else:
                    # The alias exists but doesn't match, update session_instance_tune.name
                    cur.execute('''
                        UPDATE session_instance_tune 
                        SET name = %s
                        WHERE session_instance_tune_id = %s
                    ''', (new_name, sit_id))
                    
                    message = f'Set instance name to "{new_name}"'
            else:
                # New name matches the tune.name from the tune table
                if current_alias == new_name:
                    # Clear the alias since it's the same as the tune name
                    # First save session_tune to history
                    save_to_history(cur, 'session_tune', 'UPDATE', (session_id, tune_id))
                    
                    cur.execute('''
                        UPDATE session_tune 
                        SET alias = NULL
                        WHERE session_id = %s AND tune_id = %s
                    ''', (session_id, tune_id))
                    
                    # Clear any name override in session_instance_tune
                    cur.execute('''
                        UPDATE session_instance_tune 
                        SET name = NULL
                        WHERE session_instance_tune_id = %s
                    ''', (sit_id,))
                    
                    message = f'Using original tune name "{new_name}"'
                else:
                    # Just clear any session_instance_tune name override since we want the tune name
                    cur.execute('''
                        UPDATE session_instance_tune 
                        SET name = NULL
                        WHERE session_instance_tune_id = %s
                    ''', (sit_id,))
                    
                    message = f'Using original tune name "{new_name}"'
        else:
            # This is a name-only tune, try to match it with existing tunes before updating
            # Use the refactored tune matching function (allow multiple session aliases since we're in edit mode)
            matched_tune_id, final_name, error_message = find_matching_tune(cur, session_id, new_name, allow_multiple_session_aliases=True)
            
            if matched_tune_id:
                # We found a match! Need to link this tune
                # First check if this tune is already in session_tune for this session
                cur.execute('''
                    SELECT tune_id FROM session_tune 
                    WHERE session_id = %s AND tune_id = %s
                ''', (session_id, matched_tune_id))
                existing_session_tune = cur.fetchone()
                
                if not existing_session_tune:
                    # Add to session_tune (no alias needed since we're using the exact match)
                    cur.execute('''
                        INSERT INTO session_tune (session_id, tune_id)
                        VALUES (%s, %s)
                    ''', (session_id, matched_tune_id))
                    
                    # Save the newly inserted record to history
                    save_to_history(cur, 'session_tune', 'INSERT', (session_id, matched_tune_id))
                
                # Update session_instance_tune to link to the tune and clear the name field
                cur.execute('''
                    UPDATE session_instance_tune 
                    SET tune_id = %s, name = NULL
                    WHERE session_instance_tune_id = %s
                ''', (matched_tune_id, sit_id))
                
                message = f'Linked "{final_name}" to existing tune (ID: {matched_tune_id})'
            else:
                # No match found, just update the name as before
                cur.execute('''
                    UPDATE session_instance_tune 
                    SET name = %s
                    WHERE session_instance_tune_id = %s
                ''', (new_name, sit_id))
                
                message = f'Updated name to "{new_name}"'
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'message': message})
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Failed to edit tune: {str(e)}'})

@app.route('/add-session')
def add_session():
    return render_template('add_session.html')

@app.route('/api/check-existing-session', methods=['POST'])
def check_existing_session_ajax():
    session_id = request.json.get('session_id')
    if not session_id:
        return jsonify({'success': False, 'message': 'Session ID is required'})
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Check if session ID already exists in our database
        cur.execute('SELECT path FROM session WHERE thesession_id = %s', (session_id,))
        existing_session = cur.fetchone()
        
        cur.close()
        conn.close()
        
        if existing_session:
            return jsonify({'exists': True, 'session_path': f'/sessions/{existing_session[0]}'})
        else:
            return jsonify({'exists': False})
            
    except Exception as e:
        return jsonify({'success': False, 'message': f'Database error: {str(e)}'})

@app.route('/api/search-sessions', methods=['POST'])
def search_sessions_ajax():
    search_query = request.json.get('query')
    if not search_query:
        return jsonify({'success': False, 'message': 'Search query is required'})
    
    try:
        # Search sessions on thesession.org API
        api_url = f"https://thesession.org/sessions/search?q={search_query}&format=json"
        response = requests.get(api_url, timeout=10)
        
        if response.status_code != 200:
            return jsonify({'success': False, 'message': f'Failed to search sessions (status: {response.status_code})'})
        
        data = response.json()
        sessions = data.get('sessions', [])
        
        # Get database connection to check existing sessions
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Return first 5 results with formatted data and existence check
        results = []
        for session in sessions[:5]:
            session_id = session.get('id')
            venue_name = session.get('venue', {}).get('name', '') if session.get('venue') else ''
            city = session.get('town', {}).get('name', '') if session.get('town') else ''
            state = session.get('area', {}).get('name', '') if session.get('area') else ''
            country = session.get('country', {}).get('name', '') if session.get('country') else ''
            
            # Check if this session already exists in our database
            cur.execute('SELECT path FROM session WHERE thesession_id = %s', (session_id,))
            existing_session = cur.fetchone()
            
            result = {
                'id': session_id,
                'name': venue_name,
                'city': city,
                'state': state,
                'country': country,
                'display_text': f"{venue_name}, {city}, {state}, {country}".replace(', , ', ', ').strip(', '),
                'exists_in_db': existing_session is not None,
                'session_path': f'/sessions/{existing_session[0]}' if existing_session else None
            }
            results.append(result)
        
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'results': results})
        
    except requests.exceptions.RequestException as e:
        return jsonify({'success': False, 'message': f'Error connecting to TheSession.org: {str(e)}'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error processing search results: {str(e)}'})

@app.route('/api/fetch-session-data', methods=['POST'])
def fetch_session_data_ajax():
    session_id = request.json.get('session_id')
    if not session_id:
        return jsonify({'success': False, 'message': 'Session ID is required'})
    
    try:
        # Fetch data from thesession.org API
        api_url = f"https://thesession.org/sessions/{session_id}?format=json"
        response = requests.get(api_url, timeout=10)
        
        if response.status_code == 404:
            return jsonify({'success': False, 'message': 'Session not found on TheSession.org'})
        elif response.status_code != 200:
            return jsonify({'success': False, 'message': f'Failed to fetch session data (status: {response.status_code})'})
        
        data = response.json()
        
        # Map TheSession.org data to our format
        venue_name = data.get('venue', {}).get('name', '') if data.get('venue') else ''
        
        # Extract just the date part from the datetime string (format: "2017-04-21 16:33:23")
        date_str = data.get('date', '')
        inception_date = date_str.split(' ')[0] if date_str else ''
        
        session_data = {
            'id': data.get('id'),
            'name': venue_name,  # Default session name to location name
            'inception_date': inception_date,
            'location_name': venue_name,
            'location_phone': data.get('venue', {}).get('phone', '') if data.get('venue') else '',
            'location_website': data.get('venue', {}).get('web', '') if data.get('venue') else '',
            'city': data.get('town', {}).get('name', '') if data.get('town') else '',
            'state': data.get('area', {}).get('name', '') if data.get('area') else '',
            'country': data.get('country', {}).get('name', '') if data.get('country') else '',
            'recurrence': data.get('schedule', '')
        }
        
        return jsonify({'success': True, 'session_data': session_data})
        
    except requests.exceptions.RequestException as e:
        return jsonify({'success': False, 'message': f'Error connecting to TheSession.org: {str(e)}'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error processing session data: {str(e)}'})

@app.route('/api/add-session', methods=['POST'])
def add_session_ajax():
    data = request.json
    
    # Validate required fields
    required_fields = ['name', 'path', 'city', 'state', 'country']
    for field in required_fields:
        if not data.get(field, '').strip():
            return jsonify({'success': False, 'message': f'{field.title()} is required'})
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Check if path is already taken
        cur.execute('SELECT session_id FROM session WHERE path = %s', (data['path'],))
        existing_session = cur.fetchone()
        if existing_session:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'message': f'Path "{data["path"]}" is already taken'})
        
        # Check if TheSession.org ID is already used
        if data.get('thesession_id'):
            cur.execute('SELECT session_id FROM session WHERE thesession_id = %s', (data['thesession_id'],))
            existing_thesession = cur.fetchone()
            if existing_thesession:
                cur.close()
                conn.close()
                return jsonify({'success': False, 'message': f'TheSession.org session {data["thesession_id"]} is already in the database'})
        
        # Insert new session
        cur.execute('''
            INSERT INTO session (
                thesession_id, name, path, location_name, location_phone, location_website,
                city, state, country, initiation_date, recurrence, created_date, last_modified_date
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            ) RETURNING session_id
        ''', (
            data.get('thesession_id') or None,
            data['name'],
            data['path'],
            data.get('location_name') or None,
            data.get('location_phone') or None,
            data.get('location_website') or None,
            data['city'],
            data['state'],
            data['country'],
            data.get('inception_date') or None,
            data.get('recurrence') or None
        ))
        
        session_result = cur.fetchone()
        if not session_result:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'message': 'Failed to create session'})
        
        session_id = session_result[0]
        
        # Save the newly created session to history
        save_to_history(cur, 'session', 'INSERT', session_id)
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'message': f'Session "{data["name"]}" created successfully!'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Failed to create session: {str(e)}'})

@app.route('/help')
def help_page():
    return render_template('help.html')