from flask import render_template, request, redirect, url_for, flash, jsonify, session, current_app
import random
import requests
import bcrypt
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime, timedelta
import re

# Import from local modules
from database import get_db_connection, normalize_apostrophes, save_to_history
from timezone_utils import now_utc, get_timezone_display_name, get_timezone_display_with_offset
from auth import User, create_session, cleanup_expired_sessions, generate_password_reset_token, generate_verification_token, log_login_event
from email_utils import send_password_reset_email, send_verification_email


def home():
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
        
        # For each active session, get the 3 most recent session instances and total count
        sessions_with_instances = []
        for session in active_sessions:
            session_id, name, path, city, state, country = session
            
            # Get total count of instances
            cur.execute('''
                SELECT COUNT(*)
                FROM session_instance
                WHERE session_id = %s
            ''', (session_id,))
            total_instances = cur.fetchone()[0]
            
            # Get the 3 most recent instances
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
                'recent_instances': [instance[0] for instance in recent_instances],
                'total_instances': total_instances
            })
        
        cur.close()
        conn.close()
        
        return render_template('home.html', active_sessions=sessions_with_instances)
    
    except Exception as e:
        return f"Database connection failed: {str(e)}"


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
            from app import render_error_page
            return render_error_page(f"Session not found: {session_path}", 404)
            
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
            from app import render_error_page
            return render_error_page(f"Session not found: {session_path}", 404)
            
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
            from app import render_error_page
            return render_error_page(f"Tune not found: {tune_id}", 404)
            
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
            from app import render_error_page
            return render_error_page(f"Tune not found in this session: {tune_id}", 404)
        
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
        
        # Get all aliases for this tune in this session
        cur.execute('''
            SELECT session_tune_alias_id, alias, created_date
            FROM session_tune_alias 
            WHERE session_id = %s AND tune_id = %s
            ORDER BY created_date ASC
        ''', (session_id, tune_id))
        
        aliases = cur.fetchall()
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
                             session_instance_date=session_instance_date,
                             aliases=aliases)
                             
    except Exception as e:
        return f"Database connection failed: {str(e)}"


def session_handler(full_path):
    # Strip trailing slash to normalize the path
    full_path = full_path.rstrip('/')
    
    # Check for beta suffix first
    is_beta = False
    if full_path.endswith('/beta'):
        is_beta = True
        full_path = full_path[:-5]  # Remove '/beta' from path
    
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
                       si.location_override, s.location_name, si.log_complete_date, s.session_id
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
                    'log_complete_date': session_instance[7],
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
                
                # Check if current user is an admin of this session
                is_session_admin = False
                if current_user.is_authenticated:
                    # session_instance[8] is the session_id from our updated query
                    # Use request.session to access Flask session data
                    from flask import session as flask_session
                    is_session_admin = (flask_session.get('is_system_admin', False) or 
                                      session_instance[8] in flask_session.get('admin_session_ids', []))
                
                if is_beta:
                    return render_template('session_instance_detail_beta.html', 
                                         session_instance=session_instance_dict, 
                                         tune_sets=sets,
                                         is_session_admin=is_session_admin)
                else:
                    return render_template('session_instance_detail.html', 
                                         session_instance=session_instance_dict, 
                                         tune_sets=sets,
                                         is_session_admin=is_session_admin)
            else:
                cur.close()
                conn.close()
                from app import render_error_page
                return render_error_page(f"Session instance not found: {session_path} on {date}", 404)
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
                
                # Check if current user is an admin of this session
                is_session_admin = False
                if current_user.is_authenticated:
                    # session is the database tuple, session[0] is the session_id
                    # Use request.session to access Flask session data
                    from flask import session as flask_session
                    is_session_admin = (flask_session.get('is_system_admin', False) or 
                                      session[0] in flask_session.get('admin_session_ids', []))
                
                cur.close()
                conn.close()
                
                return render_template('session_detail.html', session=session_dict, instances_by_year=instances_by_year, sorted_years=sorted_years, popular_tunes=popular_tunes, is_session_admin=is_session_admin)
            else:
                cur.close()
                conn.close()
                from app import render_error_page
                return render_error_page(f"Session not found: {session_path}", 404)
        except Exception as e:
            return f"Database connection failed: {str(e)}"


def add_session():
    return render_template('add_session.html')


def help_page():
    return render_template('help.html')


def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        email = request.form.get('email', '').strip()
        timezone = request.form.get('time_zone', 'UTC')
        # Migrate legacy timezone values to IANA identifiers
        from timezone_utils import migrate_legacy_timezone
        timezone = migrate_legacy_timezone(timezone)
        
        # Validation
        if not username or not password or not first_name or not last_name or not email:
            flash('Username, password, first name, last name, and email are required.', 'error')
            return render_template('auth/register.html')
        
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('auth/register.html')
        
        if len(password) < 8:
            flash('Password must be at least 8 characters long.', 'error')
            return render_template('auth/register.html')
        
        # Check if username already exists
        existing_user = User.get_by_username(username)
        if existing_user:
            flash('Username already exists. Please choose a different one.', 'error')
            return render_template('auth/register.html')
        
        # Check if email already exists
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute('SELECT person_id FROM person WHERE email = %s', (email,))
            if cur.fetchone():
                flash('Email address already registered. Please use a different email or try logging in.', 'error')
                return render_template('auth/register.html')
        finally:
            conn.close()
        
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            
            # Create person record
            cur.execute('''
                INSERT INTO person (first_name, last_name, email)
                VALUES (%s, %s, %s)
                RETURNING person_id
            ''', (first_name, last_name, email))
            person_id = cur.fetchone()[0]
            
            # Create user record (unverified)
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            verification_token = generate_verification_token()
            verification_expires = now_utc() + timedelta(hours=24)
            
            cur.execute('''
                INSERT INTO user_account (person_id, username, user_email, hashed_password, timezone, 
                                        email_verified, verification_token, verification_token_expires)
                VALUES (%s, %s, %s, %s, %s, FALSE, %s, %s)
                RETURNING user_id
            ''', (person_id, username, email, hashed_password, timezone, verification_token, verification_expires))
            user_id = cur.fetchone()[0]
            
            conn.commit()
            
            # Send verification email
            user = User(user_id, person_id, username, email=email, first_name=first_name, last_name=last_name)
            if send_verification_email(user, verification_token):
                flash('Registration successful! Please check your email to verify your account before logging in.', 'success')
            else:
                flash('Registration successful, but failed to send verification email. Please contact support.', 'warning')
            
            return redirect(url_for('login'))
            
        except Exception as e:
            conn.rollback()
            print(f"Registration error: {str(e)}")
            flash('Registration failed. Please try again.', 'error')
            return render_template('auth/register.html')
        finally:
            conn.close()
    
    return render_template('auth/register.html')


def login():
    # Capture referrer URL for redirect after login
    if request.method == 'GET' and request.referrer and 'login' not in request.referrer:
        session['login_redirect_url'] = request.referrer
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember_me = request.form.get('remember_me') == 'on'
        
        # Get client info for logging
        ip_address = request.environ.get('HTTP_X_FORWARDED_FOR', request.environ.get('REMOTE_ADDR'))
        # Handle comma-separated IPs from X-Forwarded-For header (take the first one)
        if ip_address and ',' in ip_address:
            ip_address = ip_address.split(',')[0].strip()
        user_agent = request.headers.get('User-Agent')
        
        if not username or not password:
            log_login_event(None, username, 'LOGIN_FAILURE', ip_address, user_agent, 
                          failure_reason='MISSING_CREDENTIALS')
            flash('Username and password are required.', 'error')
            return render_template('auth/login.html')
        
        user = User.get_by_username(username)
        if user and user.is_active and user.check_password(password):
            if not user.email_verified:
                log_login_event(user.user_id, username, 'LOGIN_FAILURE', ip_address, user_agent,
                              failure_reason='EMAIL_NOT_VERIFIED')
                flash('Please verify your email address before logging in. Check your email for a verification link.', 'warning')
                return render_template('auth/login.html')
            
            login_user(user, remember=remember_me)
            
            # Create session record
            session_id = create_session(user.user_id, ip_address, user_agent)
            
            # Log successful login
            log_login_event(user.user_id, username, 'LOGIN_SUCCESS', ip_address, user_agent,
                          session_id=session_id, additional_data={'remember_me': remember_me})
            
            # Store session_id in Flask session to identify this specific session
            session['db_session_id'] = session_id
            # Cache admin status for menu display
            session['is_system_admin'] = user.is_system_admin
            
            # Cache list of sessions this user is an admin of
            conn_admin = get_db_connection()
            try:
                cur_admin = conn_admin.cursor()
                cur_admin.execute('''
                    SELECT s.session_id 
                    FROM session_person sp
                    JOIN session s ON sp.session_id = s.session_id
                    WHERE sp.person_id = %s AND sp.is_admin = TRUE
                ''', (user.person_id,))
                admin_session_ids = [row[0] for row in cur_admin.fetchall()]
                session['admin_session_ids'] = admin_session_ids
            finally:
                conn_admin.close()
            
            # Clean up expired sessions
            cleanup_expired_sessions()
            
            # Check for stored redirect URL first, then next parameter, then default to home
            redirect_url = session.pop('login_redirect_url', None)
            next_page = request.args.get('next')
            
            if redirect_url:
                return redirect(redirect_url)
            elif next_page:
                return redirect(next_page)
            return redirect(url_for('home'))
        else:
            # Determine failure reason
            if user and not user.is_active:
                failure_reason = 'ACCOUNT_INACTIVE'
            elif user:
                failure_reason = 'INVALID_PASSWORD'
            else:
                failure_reason = 'USER_NOT_FOUND'
            
            log_login_event(user.user_id if user else None, username, 'LOGIN_FAILURE', 
                          ip_address, user_agent, failure_reason=failure_reason)
            flash('Invalid username or password.', 'error')
    
    return render_template('auth/login.html')


@login_required
def logout():
    user_id = None
    username = None
    db_session_id = None
    
    if current_user.is_authenticated:
        user_id = current_user.user_id
        username = current_user.username
        
        # Get client info for logging
        ip_address = request.environ.get('HTTP_X_FORWARDED_FOR', request.environ.get('REMOTE_ADDR'))
        if ip_address and ',' in ip_address:
            ip_address = ip_address.split(',')[0].strip()
        user_agent = request.headers.get('User-Agent')
        
        # Remove only the current session from database
        db_session_id = session.get('db_session_id')
        if db_session_id:
            conn = get_db_connection()
            try:
                cur = conn.cursor()
                cur.execute('DELETE FROM user_session WHERE session_id = %s', (db_session_id,))
                conn.commit()
            finally:
                conn.close()
        
        # Log logout event
        log_login_event(user_id, username, 'LOGOUT', ip_address, user_agent, session_id=db_session_id)
    
    # Clear all session data first
    session.clear()
    
    # Then clear Flask-Login session
    logout_user()
    
    # Set flash message after clearing the session
    flash('You have been logged out.', 'info')
    
    # Create response with cache control headers and explicitly clear cookies
    response = redirect(url_for('home'))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    
    # Clear all possible session-related cookies
    response.set_cookie('session', '', expires=0, path='/')
    response.set_cookie('remember_token', '', expires=0, path='/')
    response.set_cookie('user_id', '', expires=0, path='/')
    
    return response


def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        
        if not email:
            flash('Email address is required.', 'error')
            return render_template('auth/forgot_password.html')
        
        # Find user by email
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute('''
                SELECT ua.user_id, ua.username, p.email, p.first_name
                FROM user_account ua
                JOIN person p ON ua.person_id = p.person_id
                WHERE p.email = %s AND ua.is_active = TRUE
            ''', (email,))
            user_data = cur.fetchone()
            
            if user_data:
                # Generate reset token
                token = generate_password_reset_token()
                expires = now_utc() + timedelta(hours=1)
                
                # Save token to database
                save_to_history(cur, 'user_account', 'UPDATE', user_data[0], f'password_reset_request')
                cur.execute('''
                    UPDATE user_account 
                    SET password_reset_token = %s, password_reset_expires = %s
                    WHERE user_id = %s
                ''', (token, expires, user_data[0]))
                conn.commit()
                
                # Create user object for email sending
                user = User(user_data[0], None, user_data[1], email=user_data[2], first_name=user_data[3])
                
                # Send reset email
                if send_password_reset_email(user, token):
                    flash('Password reset instructions have been sent to your email.', 'info')
                else:
                    flash('Failed to send reset email. Please try again later.', 'error')
            else:
                # Don't reveal whether email exists
                flash('If an account with that email exists, password reset instructions have been sent.', 'info')
                
        finally:
            conn.close()
        
        return redirect(url_for('login'))
    
    return render_template('auth/forgot_password.html')


def reset_password(token):
    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        if not password or not confirm_password:
            flash('Both password fields are required.', 'error')
            return render_template('auth/reset_password.html', token=token)
        
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('auth/reset_password.html', token=token)
        
        if len(password) < 8:
            flash('Password must be at least 8 characters long.', 'error')
            return render_template('auth/reset_password.html', token=token)
        
        # Verify token and update password
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute('''
                SELECT user_id FROM user_account 
                WHERE password_reset_token = %s 
                AND password_reset_expires > %s
                AND is_active = TRUE
            ''', (token, now_utc()))
            user_data = cur.fetchone()
            
            if user_data:
                # Get username for logging
                cur.execute('SELECT username FROM user_account WHERE user_id = %s', (user_data[0],))
                username_row = cur.fetchone()
                username = username_row[0] if username_row else 'unknown'
                
                # Update password and clear reset token
                save_to_history(cur, 'user_account', 'UPDATE', user_data[0], f'password_reset_completion')
                hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                cur.execute('''
                    UPDATE user_account 
                    SET hashed_password = %s, password_reset_token = NULL, password_reset_expires = NULL
                    WHERE user_id = %s
                ''', (hashed_password, user_data[0]))
                conn.commit()
                
                # Log password reset event
                ip_address = request.environ.get('HTTP_X_FORWARDED_FOR', request.environ.get('REMOTE_ADDR'))
                if ip_address and ',' in ip_address:
                    ip_address = ip_address.split(',')[0].strip()
                user_agent = request.headers.get('User-Agent')
                log_login_event(user_data[0], username, 'PASSWORD_RESET', ip_address, user_agent)
                
                flash('Password has been reset successfully. Please log in.', 'success')
                return redirect(url_for('login'))
            else:
                flash('Invalid or expired reset token.', 'error')
                return redirect(url_for('forgot_password'))
                
        finally:
            conn.close()
    
    # Verify token is valid for GET request
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute('''
            SELECT user_id FROM user_account 
            WHERE password_reset_token = %s 
            AND password_reset_expires > %s
            AND is_active = TRUE
        ''', (token, now_utc()))
        if not cur.fetchone():
            flash('Invalid or expired reset token.', 'error')
            return redirect(url_for('forgot_password'))
    finally:
        conn.close()
    
    return render_template('auth/reset_password.html', token=token)


@login_required
def change_password():
    if request.method == 'POST':
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        if not current_password or not new_password or not confirm_password:
            flash('All password fields are required.', 'error')
            return render_template('auth/change_password.html')
        
        if new_password != confirm_password:
            flash('New passwords do not match.', 'error')
            return render_template('auth/change_password.html')
        
        if len(new_password) < 8:
            flash('Password must be at least 8 characters long.', 'error')
            return render_template('auth/change_password.html')
        
        # Get current user with hashed password
        user = User.get_by_username(current_user.username)
        if not user.check_password(current_password):
            flash('Current password is incorrect.', 'error')
            return render_template('auth/change_password.html')
        
        # Update password
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            save_to_history(cur, 'user_account', 'UPDATE', current_user.user_id, f'password_change:{current_user.username}')
            hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            cur.execute('''
                UPDATE user_account 
                SET hashed_password = %s, last_modified_date = %s
                WHERE user_id = %s
            ''', (hashed_password, now_utc(), current_user.user_id))
            conn.commit()
            
            flash('Password changed successfully.', 'success')
            return redirect(url_for('home'))
            
        finally:
            conn.close()
    
    return render_template('auth/change_password.html')


def verify_email(token):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        
        # Find user with valid verification token
        cur.execute('''
            SELECT user_id, username FROM user_account 
            WHERE verification_token = %s 
            AND verification_token_expires > %s
            AND email_verified = FALSE
        ''', (token, now_utc()))
        user_data = cur.fetchone()
        
        if user_data:
            # Mark email as verified and clear token
            save_to_history(cur, 'user_account', 'UPDATE', user_data[0], f'email_verification')
            cur.execute('''
                UPDATE user_account 
                SET email_verified = TRUE, 
                    verification_token = NULL, 
                    verification_token_expires = NULL,
                    last_modified_date = %s
                WHERE user_id = %s
            ''', (now_utc(), user_data[0]))
            conn.commit()
            
            flash('Email verified successfully! You can now log in.', 'success')
            return redirect(url_for('login'))
        else:
            flash('Invalid or expired verification link. Please request a new verification email.', 'error')
            return redirect(url_for('resend_verification'))
            
    finally:
        conn.close()


def resend_verification():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        
        if not email:
            flash('Email address is required.', 'error')
            return render_template('auth/resend_verification.html')
        
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            
            # Find unverified user by email
            cur.execute('''
                SELECT ua.user_id, ua.username, p.first_name, p.last_name, p.email
                FROM user_account ua
                JOIN person p ON ua.person_id = p.person_id
                WHERE p.email = %s AND ua.email_verified = FALSE AND ua.is_active = TRUE
            ''', (email,))
            user_data = cur.fetchone()
            
            if user_data:
                # Generate new verification token
                verification_token = generate_verification_token()
                verification_expires = now_utc() + timedelta(hours=24)
                
                # Update token in database
                save_to_history(cur, 'user_account', 'UPDATE', user_data[0], f'verification_token_regeneration')
                cur.execute('''
                    UPDATE user_account 
                    SET verification_token = %s, verification_token_expires = %s
                    WHERE user_id = %s
                ''', (verification_token, verification_expires, user_data[0]))
                conn.commit()
                
                # Send verification email
                user = User(user_data[0], None, user_data[1], email=user_data[4], 
                          first_name=user_data[2], last_name=user_data[3])
                if send_verification_email(user, verification_token):
                    flash('Verification email sent! Please check your email.', 'success')
                else:
                    flash('Failed to send verification email. Please try again later.', 'error')
            else:
                # Don't reveal whether email exists or is already verified
                flash('If an unverified account with that email exists, a verification email has been sent.', 'info')
                
        finally:
            conn.close()
        
        return redirect(url_for('login'))
    
    return render_template('auth/resend_verification.html')


@login_required
def admin():
    # Check if user is system admin
    if not session.get('is_system_admin'):
        flash('You must be authorized to view this page.', 'error')
        return redirect(url_for('home'))
    
    # Redirect to admin_people as the default tab
    return redirect(url_for('admin_people'))


@login_required
def admin_sessions():
    # Check if user is system admin
    if not session.get('is_system_admin'):
        flash('You must be authorized to view this page.', 'error')
        return redirect(url_for('home'))
    
    # Get list of currently logged in users from user_session table
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute('''
            SELECT 
                us.user_id,
                p.first_name,
                p.last_name,
                us.created_date,
                us.last_accessed,
                us.ip_address
            FROM user_session us
            JOIN user_account ua ON us.user_id = ua.user_id
            JOIN person p ON ua.person_id = p.person_id
            WHERE us.expires_at > %s
            ORDER BY us.last_accessed DESC
        ''', (now_utc(),))
        
        active_sessions = []
        for row in cur.fetchall():
            user_id, first_name, last_name, created_date, last_accessed, ip_address = row
            
            # Calculate how long they've been logged in
            login_duration = now_utc() - created_date
            days = login_duration.days
            hours, remainder = divmod(login_duration.seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            
            if days > 0:
                duration_str = f"{days}d {hours}h {minutes}m"
            elif hours > 0:
                duration_str = f"{hours}h {minutes}m"
            else:
                duration_str = f"{minutes}m"
            
            active_sessions.append({
                'user_id': user_id,
                'name': f"{first_name} {last_name}",
                'login_date': created_date.strftime('%Y-%m-%d %H:%M:%S'),
                'duration': duration_str,
                'ip_address': ip_address or 'Unknown'
            })
        
        return render_template('user_sessions.html', active_sessions=active_sessions, active_tab='sessions')
        
    finally:
        conn.close()


@login_required
def admin_login_history():
    # Check if user is system admin
    if not session.get('is_system_admin'):
        flash('You must be authorized to view this page.', 'error')
        return redirect(url_for('home'))
    
    
    # Get pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = 50
    offset = (page - 1) * per_page
    
    # Get filter parameters
    event_type = request.args.get('event_type', '')
    username_filter = request.args.get('username', '')
    hours_filter = request.args.get('hours', 24, type=int)  # Default to last 24 hours
    
    
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        
        # Build WHERE conditions
        where_conditions = ['lh.timestamp > %s']
        params = [now_utc() - timedelta(hours=hours_filter)]
        
        if event_type:
            where_conditions.append('lh.event_type = %s')
            params.append(event_type)
        
        if username_filter:
            where_conditions.append('lh.username ILIKE %s')
            params.append(f'%{username_filter}%')
        
        where_clause = ' AND '.join(where_conditions)
        
        # Get total count for pagination
        count_query = f'''
            SELECT COUNT(*) FROM login_history lh
            WHERE {where_clause}
        '''
        cur.execute(count_query, params)
        total_count = cur.fetchone()[0]
        
        # Get login history with user details
        query = f'''
            SELECT 
                lh.login_history_id,
                lh.user_id,
                lh.username,
                lh.event_type,
                lh.ip_address,
                lh.user_agent,
                lh.session_id,
                lh.failure_reason,
                lh.timestamp,
                lh.additional_data,
                p.first_name,
                p.last_name
            FROM login_history lh
            LEFT JOIN user_account ua ON lh.user_id = ua.user_id
            LEFT JOIN person p ON ua.person_id = p.person_id
            WHERE {where_clause}
            ORDER BY lh.timestamp DESC
            LIMIT %s OFFSET %s
        '''
        params.extend([per_page, offset])
        cur.execute(query, params)
        
        login_history = []
        for row in cur.fetchall():
            (history_id, user_id, username, row_event_type, ip_address, user_agent, 
             session_id, failure_reason, timestamp, additional_data, 
             first_name, last_name) = row
            
            # Format the timestamp
            formatted_time = timestamp.strftime('%Y-%m-%d %H:%M:%S')
            
            # Get full name if available
            full_name = f"{first_name} {last_name}" if first_name and last_name else "Unknown"
            
            # Truncate user agent for display
            display_user_agent = user_agent[:50] + "..." if user_agent and len(user_agent) > 50 else user_agent
            
            login_history.append({
                'history_id': history_id,
                'user_id': user_id,
                'username': username,
                'full_name': full_name,
                'event_type': row_event_type,
                'ip_address': ip_address or 'Unknown',
                'user_agent': display_user_agent or 'Unknown',
                'session_id': session_id,
                'failure_reason': failure_reason,
                'timestamp': formatted_time,
                'additional_data': additional_data
            })
        
        # Calculate pagination info
        total_pages = (total_count + per_page - 1) // per_page
        has_prev = page > 1
        has_next = page < total_pages
        
        return render_template('admin_login_history.html', 
                             login_history=login_history,
                             active_tab='login_history',
                             page=page,
                             total_pages=total_pages,
                             has_prev=has_prev,
                             has_next=has_next,
                             total_count=total_count,
                             event_type=event_type,
                             username_filter=username_filter,
                             hours_filter=hours_filter)
        
    finally:
        conn.close()


@login_required
def admin_people():
    # Check if user is system admin
    if not session.get('is_system_admin'):
        flash('You must be authorized to view this page.', 'error')
        return redirect(url_for('home'))
    
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        
        # Get all people with outer join to user_account and their most recent login
        # Also get session counts and latest session instance info
        cur.execute('''
            SELECT 
                p.person_id,
                p.first_name,
                p.last_name,
                p.email,
                p.city,
                p.state,
                p.country,
                p.thesession_user_id,
                ua.username,
                ua.is_system_admin,
                us.last_login,
                COALESCE(sp.session_count, 0) as session_count,
                COALESCE(sip.session_instance_count, 0) as session_instance_count,
                latest_si.latest_date,
                latest_si.session_name
            FROM person p
            LEFT JOIN user_account ua ON p.person_id = ua.person_id
            LEFT JOIN (
                SELECT 
                    user_id,
                    MAX(last_accessed) as last_login
                FROM user_session
                GROUP BY user_id
            ) us ON ua.user_id = us.user_id
            LEFT JOIN (
                SELECT 
                    person_id,
                    COUNT(*) as session_count
                FROM session_person
                GROUP BY person_id
            ) sp ON p.person_id = sp.person_id
            LEFT JOIN (
                SELECT 
                    person_id,
                    COUNT(*) as session_instance_count
                FROM session_instance_person
                GROUP BY person_id
            ) sip ON p.person_id = sip.person_id
            LEFT JOIN (
                SELECT DISTINCT ON (sip.person_id)
                    sip.person_id,
                    si.date as latest_date,
                    s.name as session_name
                FROM session_instance_person sip
                JOIN session_instance si ON sip.session_instance_id = si.session_instance_id
                JOIN session s ON si.session_id = s.session_id
                ORDER BY sip.person_id, si.date DESC
            ) latest_si ON p.person_id = latest_si.person_id
            ORDER BY p.last_name, p.first_name
        ''')
        
        people = []
        for row in cur.fetchall():
            person_id, first_name, last_name, email, city, state, country, thesession_user_id, username, is_system_admin, last_login, session_count, session_instance_count, latest_date, session_name = row
            
            # Format full location for tooltip
            location_parts = []
            if city:
                location_parts.append(city)
            if state:
                location_parts.append(state)
            if country:
                location_parts.append(country)
            full_location = ', '.join(location_parts) if location_parts else 'Unknown'
            
            # Format last login
            if last_login:
                formatted_last_login = last_login.strftime('%Y-%m-%d %H:%M')
            else:
                formatted_last_login = 'Never' if username else 'N/A'
            
            # Format latest session date
            if latest_date:
                formatted_latest_date = latest_date.strftime('%Y-%m-%d')
                latest_session_info = f"{formatted_latest_date} - {session_name}"
            else:
                latest_session_info = 'None'
            
            people.append({
                'person_id': person_id,
                'name': f"{first_name} {last_name}",
                'email': email or 'Not provided',
                'city': city or 'Unknown',
                'full_location': full_location,
                'thesession_user_id': thesession_user_id,
                'username': username or 'No account',
                'is_system_admin': is_system_admin,
                'last_login': formatted_last_login,
                'session_count': session_count,
                'session_instance_count': session_instance_count,
                'latest_session_info': latest_session_info
            })
        
        return render_template('admin_people.html', 
                             people=people,
                             active_tab='people')
        
    finally:
        conn.close()


@login_required 
def admin_test_links():
    """Admin test links page with sample URLs for testing"""
    # Check if user is system admin
    if not session.get('is_system_admin'):
        flash('You must be authorized to view this page.', 'error')
        return redirect(url_for('home'))
    
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        
        # Get a sample session (try to find session_id=1 first, fallback to any session)
        cur.execute('''
            SELECT session_id, path, name 
            FROM session 
            WHERE session_id = 1
            LIMIT 1
        ''')
        sample_session = cur.fetchone()
        
        if not sample_session:
            # Fallback to any session
            cur.execute('''
                SELECT session_id, path, name 
                FROM session 
                ORDER BY session_id
                LIMIT 1
            ''')
            sample_session = cur.fetchone()
        
        # Get a random tune from that session
        sample_tune_id = None
        if sample_session:
            cur.execute('''
                SELECT tune_id 
                FROM session_tune 
                WHERE session_id = %s 
                ORDER BY RANDOM()
                LIMIT 1
            ''', (sample_session[0],))
            tune_result = cur.fetchone()
            if tune_result:
                sample_tune_id = tune_result[0]
        
        # Get latest session instance for that session
        latest_instance_date = None
        if sample_session:
            cur.execute('''
                SELECT date 
                FROM session_instance 
                WHERE session_id = %s 
                ORDER BY date DESC
                LIMIT 1
            ''', (sample_session[0],))
            instance_result = cur.fetchone()
            if instance_result:
                latest_instance_date = instance_result[0]
        
        # Get a random person
        cur.execute('''
            SELECT person_id 
            FROM person 
            ORDER BY RANDOM()
            LIMIT 1
        ''')
        person_result = cur.fetchone()
        sample_person_id = person_result[0] if person_result else None
        
        return render_template('admin_test_links.html',
                             active_tab='test_links',
                             sample_session=sample_session,
                             sample_tune_id=sample_tune_id,
                             latest_instance_date=latest_instance_date,
                             sample_person_id=sample_person_id)
        
    finally:
        conn.close()


@login_required
def person_details(person_id=None):
    """Person details page showing person info, user account, and activity data"""
    # Determine if this is a user profile view or admin view
    is_user_profile = person_id is None
    
    if is_user_profile:
        # User profile view - use current user's person_id
        person_id = current_user.person_id
    else:
        # Admin view - check if user is system admin
        if not session.get('is_system_admin'):
            flash('You must be authorized to view this page.', 'error')
            return redirect(url_for('home'))
    
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        
        # Get person details
        cur.execute('''
            SELECT person_id, first_name, last_name, email, sms_number, city, state, country, thesession_user_id
            FROM person
            WHERE person_id = %s
        ''', (person_id,))
        
        person_row = cur.fetchone()
        if not person_row:
            from app import render_error_page
            return render_error_page("Person not found.", 404)
        
        person_id, first_name, last_name, email, sms_number, city, state, country, thesession_user_id = person_row
        
        # Format location
        location_parts = []
        if city:
            location_parts.append(city)
        if state:
            location_parts.append(state)
        if country:
            location_parts.append(country)
        location = ', '.join(location_parts) if location_parts else None
        
        person = {
            'id': person_id,
            'name': f"{first_name} {last_name}",
            'first_name': first_name,
            'last_name': last_name,
            'email': email,
            'sms_number': sms_number,
            'city': city,
            'state': state,
            'country': country,
            'location': location,
            'thesession_user_id': thesession_user_id
        }
        
        # Get user account details if exists
        cur.execute('''
            SELECT user_id, username, user_email, email_verified, is_system_admin, is_active, created_date, timezone
            FROM user_account
            WHERE person_id = %s
        ''', (person_id,))
        
        user_row = cur.fetchone()
        user = None
        if user_row:
            user_id, username, user_email, email_verified, is_system_admin, is_active, created_date, timezone = user_row
            
            # Get last login from user_session table
            cur.execute('''
                SELECT MAX(last_accessed) as last_login
                FROM user_session
                WHERE user_id = %s
            ''', (user_id,))
            last_login_row = cur.fetchone()
            last_login = last_login_row[0] if last_login_row and last_login_row[0] else None
            
            user = {
                'user_id': user_id,
                'username': username,
                'user_email': user_email,
                'email_verified': email_verified,
                'is_system_admin': is_system_admin,
                'is_active': is_active,
                'created_at': created_date,  # Keep as created_at in template for consistency
                'last_login': last_login,
                'timezone': timezone,
                'timezone_display': get_timezone_display_name(timezone or 'UTC')
            }
        
        # Get sessions this person is associated with
        cur.execute('''
            SELECT s.name as session_name, s.city, s.state, s.country, sp.is_regular, sp.is_admin
            FROM session_person sp
            JOIN session s ON sp.session_id = s.session_id
            WHERE sp.person_id = %s
            ORDER BY s.name
        ''', (person_id,))
        
        sessions = []
        for row in cur.fetchall():
            session_name, session_city, session_state, session_country, is_regular, is_admin = row
            
            # Derive role from boolean flags
            if is_admin:
                role = 'Admin'
            elif is_regular:
                role = 'Regular'
            else:
                role = 'Attendee'
            
            # Format session location
            session_location_parts = []
            if session_city:
                session_location_parts.append(session_city)
            if session_state:
                session_location_parts.append(session_state)
            if session_country:
                session_location_parts.append(session_country)
            session_location = ', '.join(session_location_parts) if session_location_parts else 'Unknown'
            
            sessions.append({
                'session_name': session_name,
                'location': session_location,
                'regular_schedule': None,  # Would need to be added to query if available
                'role': role
            })
        
        # Get timezone options with UTC offsets for dropdown
        timezone_options = [
            ('UTC', get_timezone_display_with_offset('UTC')),
            # Americas
            ('America/New_York', get_timezone_display_with_offset('America/New_York')),
            ('America/Chicago', get_timezone_display_with_offset('America/Chicago')),
            ('America/Denver', get_timezone_display_with_offset('America/Denver')),
            ('America/Los_Angeles', get_timezone_display_with_offset('America/Los_Angeles')),
            ('America/Anchorage', get_timezone_display_with_offset('America/Anchorage')),
            ('Pacific/Honolulu', get_timezone_display_with_offset('Pacific/Honolulu')),
            ('America/Toronto', get_timezone_display_with_offset('America/Toronto')),
            ('America/Vancouver', get_timezone_display_with_offset('America/Vancouver')),
            ('America/Mexico_City', get_timezone_display_with_offset('America/Mexico_City')),
            ('America/Buenos_Aires', get_timezone_display_with_offset('America/Buenos_Aires')),
            ('America/Sao_Paulo', get_timezone_display_with_offset('America/Sao_Paulo')),
            # Europe
            ('Europe/London', get_timezone_display_with_offset('Europe/London')),
            ('Europe/Dublin', get_timezone_display_with_offset('Europe/Dublin')),
            ('Europe/Paris', get_timezone_display_with_offset('Europe/Paris')),
            ('Europe/Berlin', get_timezone_display_with_offset('Europe/Berlin')),
            ('Europe/Rome', get_timezone_display_with_offset('Europe/Rome')),
            ('Europe/Madrid', get_timezone_display_with_offset('Europe/Madrid')),
            ('Europe/Amsterdam', get_timezone_display_with_offset('Europe/Amsterdam')),
            ('Europe/Brussels', get_timezone_display_with_offset('Europe/Brussels')),
            ('Europe/Zurich', get_timezone_display_with_offset('Europe/Zurich')),
            ('Europe/Stockholm', get_timezone_display_with_offset('Europe/Stockholm')),
            ('Europe/Oslo', get_timezone_display_with_offset('Europe/Oslo')),
            ('Europe/Copenhagen', get_timezone_display_with_offset('Europe/Copenhagen')),
            ('Europe/Helsinki', get_timezone_display_with_offset('Europe/Helsinki')),
            ('Europe/Athens', get_timezone_display_with_offset('Europe/Athens')),
            ('Europe/Moscow', get_timezone_display_with_offset('Europe/Moscow')),
            # Africa & Middle East
            ('Africa/Cairo', get_timezone_display_with_offset('Africa/Cairo')),
            ('Africa/Johannesburg', get_timezone_display_with_offset('Africa/Johannesburg')),
            ('Africa/Lagos', get_timezone_display_with_offset('Africa/Lagos')),
            ('Asia/Dubai', get_timezone_display_with_offset('Asia/Dubai')),
            ('Asia/Jerusalem', get_timezone_display_with_offset('Asia/Jerusalem')),
            # Asia
            ('Asia/Kolkata', get_timezone_display_with_offset('Asia/Kolkata')),
            ('Asia/Bangkok', get_timezone_display_with_offset('Asia/Bangkok')),
            ('Asia/Singapore', get_timezone_display_with_offset('Asia/Singapore')),
            ('Asia/Hong_Kong', get_timezone_display_with_offset('Asia/Hong_Kong')),
            ('Asia/Shanghai', get_timezone_display_with_offset('Asia/Shanghai')),
            ('Asia/Tokyo', get_timezone_display_with_offset('Asia/Tokyo')),
            ('Asia/Seoul', get_timezone_display_with_offset('Asia/Seoul')),
            # Australia & Pacific
            ('Australia/Perth', get_timezone_display_with_offset('Australia/Perth')),
            ('Australia/Sydney', get_timezone_display_with_offset('Australia/Sydney')),
            ('Australia/Melbourne', get_timezone_display_with_offset('Australia/Melbourne')),
            ('Pacific/Auckland', get_timezone_display_with_offset('Pacific/Auckland')),
        ]
        
        return render_template('person_details.html', 
                             person=person,
                             user=user,
                             sessions=sessions,
                             is_user_profile=is_user_profile,
                             timezone_options=timezone_options)
        
    finally:
        conn.close()



def _get_session_data(session_path):
    """Helper function to get session data by path"""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        
        # Get session details
        cur.execute('''
            SELECT session_id, name, path, location_name, location_website, location_phone,
                   location_street, city, state, country, comments, unlisted_address,
                   initiation_date, termination_date, recurrence, timezone
            FROM session 
            WHERE path = %s
        ''', (session_path,))
        
        session_row = cur.fetchone()
        if not session_row:
            return None
            
        session_data = {
            'session_id': session_row[0],
            'name': session_row[1],
            'path': session_row[2],
            'location_name': session_row[3],
            'location_website': session_row[4],
            'location_phone': session_row[5],
            'location_street': session_row[6],
            'city': session_row[7],
            'state': session_row[8],
            'country': session_row[9],
            'comments': session_row[10],
            'unlisted_address': session_row[11],
            'initiation_date': session_row[12],
            'termination_date': session_row[13],
            'recurrence': session_row[14],
            'timezone': session_row[15],
            'timezone_display': get_timezone_display_name(session_row[15] or 'UTC')
        }
        
        return session_data
        
    finally:
        conn.close()


@login_required
def session_admin(session_path):
    """Session admin details page"""
    # Check if user is system admin
    if not session.get('is_system_admin'):
        flash('You must be authorized to view this page.', 'error')
        return redirect(url_for('home'))
    
    session_data = _get_session_data(session_path)
    if not session_data:
        from app import render_error_page
        return render_error_page("Session not found", 404)
    
    # Get timezone options with UTC offsets for dropdown
    timezone_options = [
        ('UTC', get_timezone_display_with_offset('UTC')),
        # Americas
        ('America/New_York', get_timezone_display_with_offset('America/New_York')),
        ('America/Chicago', get_timezone_display_with_offset('America/Chicago')),
        ('America/Denver', get_timezone_display_with_offset('America/Denver')),
        ('America/Los_Angeles', get_timezone_display_with_offset('America/Los_Angeles')),
        ('America/Anchorage', get_timezone_display_with_offset('America/Anchorage')),
        ('Pacific/Honolulu', get_timezone_display_with_offset('Pacific/Honolulu')),
        ('America/Toronto', get_timezone_display_with_offset('America/Toronto')),
        ('America/Vancouver', get_timezone_display_with_offset('America/Vancouver')),
        ('America/Mexico_City', get_timezone_display_with_offset('America/Mexico_City')),
        ('America/Buenos_Aires', get_timezone_display_with_offset('America/Buenos_Aires')),
        ('America/Sao_Paulo', get_timezone_display_with_offset('America/Sao_Paulo')),
        # Europe
        ('Europe/London', get_timezone_display_with_offset('Europe/London')),
        ('Europe/Dublin', get_timezone_display_with_offset('Europe/Dublin')),
        ('Europe/Paris', get_timezone_display_with_offset('Europe/Paris')),
        ('Europe/Berlin', get_timezone_display_with_offset('Europe/Berlin')),
        ('Europe/Rome', get_timezone_display_with_offset('Europe/Rome')),
        ('Europe/Madrid', get_timezone_display_with_offset('Europe/Madrid')),
        ('Europe/Amsterdam', get_timezone_display_with_offset('Europe/Amsterdam')),
        ('Europe/Brussels', get_timezone_display_with_offset('Europe/Brussels')),
        ('Europe/Zurich', get_timezone_display_with_offset('Europe/Zurich')),
        ('Europe/Stockholm', get_timezone_display_with_offset('Europe/Stockholm')),
        ('Europe/Oslo', get_timezone_display_with_offset('Europe/Oslo')),
        ('Europe/Copenhagen', get_timezone_display_with_offset('Europe/Copenhagen')),
        ('Europe/Helsinki', get_timezone_display_with_offset('Europe/Helsinki')),
        ('Europe/Athens', get_timezone_display_with_offset('Europe/Athens')),
        ('Europe/Moscow', get_timezone_display_with_offset('Europe/Moscow')),
        # Africa & Middle East
        ('Africa/Cairo', get_timezone_display_with_offset('Africa/Cairo')),
        ('Africa/Johannesburg', get_timezone_display_with_offset('Africa/Johannesburg')),
        ('Africa/Lagos', get_timezone_display_with_offset('Africa/Lagos')),
        ('Asia/Dubai', get_timezone_display_with_offset('Asia/Dubai')),
        ('Asia/Jerusalem', get_timezone_display_with_offset('Asia/Jerusalem')),
        # Asia
        ('Asia/Kolkata', get_timezone_display_with_offset('Asia/Kolkata')),
        ('Asia/Bangkok', get_timezone_display_with_offset('Asia/Bangkok')),
        ('Asia/Singapore', get_timezone_display_with_offset('Asia/Singapore')),
        ('Asia/Hong_Kong', get_timezone_display_with_offset('Asia/Hong_Kong')),
        ('Asia/Shanghai', get_timezone_display_with_offset('Asia/Shanghai')),
        ('Asia/Tokyo', get_timezone_display_with_offset('Asia/Tokyo')),
        ('Asia/Seoul', get_timezone_display_with_offset('Asia/Seoul')),
        # Australia & Pacific
        ('Australia/Perth', get_timezone_display_with_offset('Australia/Perth')),
        ('Australia/Sydney', get_timezone_display_with_offset('Australia/Sydney')),
        ('Australia/Melbourne', get_timezone_display_with_offset('Australia/Melbourne')),
        ('Pacific/Auckland', get_timezone_display_with_offset('Pacific/Auckland')),
    ]
        
    return render_template('session_admin.html', 
                         session=session_data,
                         session_path=session_path,
                         active_tab='details',
                         timezone_options=timezone_options)


@login_required
def session_admin_players(session_path):
    """Session admin players page"""
    # Check if user is system admin
    if not session.get('is_system_admin'):
        flash('You must be authorized to view this page.', 'error')
        return redirect(url_for('home'))
    
    session_data = _get_session_data(session_path)
    if not session_data:
        from app import render_error_page
        return render_error_page("Session not found", 404)
        
    return render_template('session_admin.html', 
                         session=session_data,
                         session_path=session_path,
                         active_tab='players')


@login_required
def session_admin_logs(session_path):
    """Session admin logs page"""
    # Check if user is system admin
    if not session.get('is_system_admin'):
        flash('You must be authorized to view this page.', 'error')
        return redirect(url_for('home'))
    
    session_data = _get_session_data(session_path)
    if not session_data:
        from app import render_error_page
        return render_error_page("Session not found", 404)
        
    return render_template('session_admin.html', 
                         session=session_data,
                         session_path=session_path,
                         active_tab='logs')


@login_required
def session_admin_person(session_path, person_id):
    """Session admin person details page"""
    # Check if user is system admin
    if not session.get('is_system_admin'):
        flash('You must be authorized to view this page.', 'error')
        return redirect(url_for('home'))
    
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        
        # Get session details
        session_data = _get_session_data(session_path)
        if not session_data:
            from app import render_error_page
            return render_error_page("Session not found", 404)
        
        session_id = session_data['session_id']
        
        # Get person details and their relationship to this session
        cur.execute('''
            SELECT 
                p.person_id,
                p.first_name,
                p.last_name,
                p.email,
                p.sms_number,
                p.city,
                p.state,
                p.country,
                p.thesession_user_id,
                sp.is_regular,
                sp.is_admin,
                sp.gets_email_reminder,
                sp.gets_email_followup,
                u.username,
                u.is_system_admin
            FROM person p
            JOIN session_person sp ON p.person_id = sp.person_id
            LEFT JOIN user_account u ON p.person_id = u.person_id
            WHERE p.person_id = %s AND sp.session_id = %s
        ''', (person_id, session_id))
        
        person_row = cur.fetchone()
        if not person_row:
            from app import render_error_page
            return render_error_page("Person not found in this session", 404)
        
        person_data = {
            'person_id': person_row[0],
            'first_name': person_row[1],
            'last_name': person_row[2],
            'email': person_row[3],
            'sms_number': person_row[4],
            'city': person_row[5],
            'state': person_row[6],
            'country': person_row[7],
            'thesession_user_id': person_row[8],
            'is_regular': person_row[9],
            'is_admin': person_row[10],
            'gets_email_reminder': person_row[11],
            'gets_email_followup': person_row[12],
            'username': person_row[13],
            'is_system_admin': person_row[14]
        }
        
        # Get attendance history for this person at this session
        cur.execute('''
            SELECT 
                si.date,
                si.start_time,
                si.end_time,
                si.is_cancelled,
                si.comments
            FROM session_instance si
            JOIN session_instance_person sip ON si.session_instance_id = sip.session_instance_id
            WHERE si.session_id = %s AND sip.person_id = %s
            ORDER BY si.date DESC
        ''', (session_id, person_id))
        
        attendance_history = []
        for row in cur.fetchall():
            attendance_history.append({
                'date': row[0],
                'start_time': row[1],
                'end_time': row[2],
                'is_cancelled': row[3],
                'comments': row[4]
            })
        
        return render_template('session_admin_person.html',
                             session=session_data,
                             session_path=session_path,
                             person=person_data,
                             attendance_history=attendance_history)
        
    finally:
        conn.close()