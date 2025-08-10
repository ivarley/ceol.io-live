from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import random
import os
import psycopg2
from dotenv import load_dotenv
import re

load_dotenv()

app = Flask(__name__)
# Secret key required for Flask sessions (used by flash messages to store temporary messages in signed cookies)
app.secret_key = os.environ.get('FLASK_SESSION_SECRET_KEY', 'dev-secret-key-change-in-production')

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
                SELECT s.name, si.date, si.comments, si.session_instance_id
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
                    WHERE session_id = %s AND date < CURRENT_DATE
                    ORDER BY date DESC
                ''', (session[0],))
                past_instances = cur.fetchall()
                
                cur.close()
                conn.close()
                
                return render_template('session_detail.html', session=session_dict, past_instances=past_instances)
            else:
                cur.close()
                conn.close()
                return f"Session not found: {session_path}", 404
        except Exception as e:
            return f"Database connection failed: {str(e)}"


@app.route('/api/sessions/<path:session_path>/<date>/add_tune', methods=['POST'])
def add_tune_ajax(session_path, date):
    tune_ids_input = request.json.get('tune_id', '').strip()
    if not tune_ids_input:
        return jsonify({'success': False, 'message': 'Please enter tune ID(s)'})
    
    # Parse comma-separated tune IDs
    tune_ids_str = [t.strip() for t in tune_ids_input.split(',')]
    tune_ids = []
    
    # Validate all tune IDs
    for tune_id_str in tune_ids_str:
        if not tune_id_str.isdigit():
            return jsonify({'success': False, 'message': f'Invalid tune ID: "{tune_id_str}". Please enter numeric IDs only.'})
        tune_ids.append(int(tune_id_str))
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Check if all tunes exist
        for tune_id in tune_ids:
            cur.execute('SELECT tune_id FROM tune WHERE tune_id = %s', (tune_id,))
            if not cur.fetchone():
                cur.close()
                conn.close()
                return jsonify({'success': False, 'message': f'Tune ID {tune_id} not found in database'})
        
        # Get session_id for this session_path
        cur.execute('SELECT session_id FROM session WHERE path = %s', (session_path,))
        session_result = cur.fetchone()
        if not session_result:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'message': 'Session not found'})
        
        session_id = session_result[0]
        
        # Add all tunes in the set
        for i, tune_id in enumerate(tune_ids):
            # First tune starts a new set (True), subsequent tunes continue the set (False)
            starts_set = (i == 0)
            
            cur.execute('SELECT insert_session_instance_tune(%s, %s, %s, %s, %s, %s)', 
                       (session_id, date, tune_id, None, None, starts_set))
        
        conn.commit()
        cur.close()
        conn.close()
        
        message = 'Tune added successfully!' if len(tune_ids) == 1 else f'Set of {len(tune_ids)} tunes added successfully!'
        return jsonify({'success': True, 'message': message})
    
    except Exception as e:
        return jsonify({'success': False, 'message': f'Failed to add tune(s): {str(e)}'})

@app.route('/api/sessions/<path:session_path>/<date>/delete_tune/<int:tune_id>/<int:order_number>', methods=['DELETE'])
def delete_tune_ajax(session_path, date, tune_id, order_number):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get the tune name and check if this tune starts a set
        cur.execute('''
            SELECT 
                COALESCE(sit.name, st.alias, t.name) AS tune_name,
                sit.continues_set,
                sit.session_instance_id
            FROM session_instance_tune sit
            LEFT JOIN tune t ON sit.tune_id = t.tune_id
            LEFT JOIN session_tune st ON sit.tune_id = st.tune_id AND st.session_id = (
                SELECT si.session_id 
                FROM session_instance si 
                WHERE si.session_instance_id = sit.session_instance_id
            )
            JOIN session_instance si ON sit.session_instance_id = si.session_instance_id
            JOIN session s ON si.session_id = s.session_id
            WHERE s.path = %s AND si.date = %s AND sit.tune_id = %s AND sit.order_number = %s
        ''', (session_path, date, tune_id, order_number))
        
        tune_info = cur.fetchone()
        if not tune_info:
            cur.close()
            conn.close()
            return jsonify({'success': False, 'message': 'Tune not found'})
        
        tune_name, continues_set, session_instance_id = tune_info
        
        # If this tune starts a set (continues_set = False) and there's a next tune,
        # update the next tune to start the set
        if not continues_set:
            cur.execute('''
                UPDATE session_instance_tune 
                SET continues_set = FALSE 
                WHERE session_instance_id = %s 
                AND order_number = %s
            ''', (session_instance_id, order_number + 1))
        
        # Delete the tune
        cur.execute('''
            DELETE FROM session_instance_tune 
            WHERE session_instance_id = %s 
            AND tune_id = %s 
            AND order_number = %s
        ''', (session_instance_id, tune_id, order_number))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'message': f'{tune_name} deleted from position {order_number} in the set.'})
    
    except Exception as e:
        return jsonify({'success': False, 'message': f'Failed to delete tune: {str(e)}'})

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
