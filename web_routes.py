from flask import render_template, request, redirect, url_for, flash, jsonify
import random
import requests
import bcrypt
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime, timedelta
import re

# Import from local modules
from database import get_db_connection, normalize_apostrophes
from auth import User, create_session, cleanup_expired_sessions, generate_password_reset_token, generate_verification_token
from email_utils import send_password_reset_email, send_verification_email


@login_required
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
        time_zone = request.form.get('time_zone', 'UTC')
        
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
            verification_expires = datetime.utcnow() + timedelta(hours=24)
            
            cur.execute('''
                INSERT INTO user_account (person_id, username, hashed_password, time_zone, 
                                        email_verified, verification_token, verification_token_expires)
                VALUES (%s, %s, %s, %s, FALSE, %s, %s)
                RETURNING user_id
            ''', (person_id, username, hashed_password, time_zone, verification_token, verification_expires))
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
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember_me = request.form.get('remember_me') == 'on'
        
        if not username or not password:
            flash('Username and password are required.', 'error')
            return render_template('auth/login.html')
        
        user = User.get_by_username(username)
        if user and user.is_active and user.check_password(password):
            if not user.email_verified:
                flash('Please verify your email address before logging in. Check your email for a verification link.', 'warning')
                return render_template('auth/login.html')
            
            login_user(user, remember=remember_me)
            
            # Create session record
            ip_address = request.environ.get('HTTP_X_FORWARDED_FOR', request.environ.get('REMOTE_ADDR'))
            # Handle comma-separated IPs from X-Forwarded-For header (take the first one)
            if ip_address and ',' in ip_address:
                ip_address = ip_address.split(',')[0].strip()
            user_agent = request.headers.get('User-Agent')
            session_id = create_session(user.user_id, ip_address, user_agent)
            
            # Clean up expired sessions
            cleanup_expired_sessions()
            
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return redirect(url_for('hello_world'))
        else:
            flash('Invalid username or password.', 'error')
    
    return render_template('auth/login.html')


@login_required
def logout():
    if current_user.is_authenticated:
        # Remove user sessions from database
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute('DELETE FROM user_session WHERE user_id = %s', (current_user.user_id,))
            conn.commit()
        finally:
            conn.close()
    
    logout_user()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('login'))


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
                expires = datetime.utcnow() + timedelta(hours=1)
                
                # Save token to database
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
            ''', (token, datetime.utcnow()))
            user_data = cur.fetchone()
            
            if user_data:
                # Update password and clear reset token
                hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                cur.execute('''
                    UPDATE user_account 
                    SET hashed_password = %s, password_reset_token = NULL, password_reset_expires = NULL
                    WHERE user_id = %s
                ''', (hashed_password, user_data[0]))
                conn.commit()
                
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
        ''', (token, datetime.utcnow()))
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
            hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            cur.execute('''
                UPDATE user_account 
                SET hashed_password = %s, last_modified_date = %s
                WHERE user_id = %s
            ''', (hashed_password, datetime.utcnow(), current_user.user_id))
            conn.commit()
            
            flash('Password changed successfully.', 'success')
            return redirect(url_for('hello_world'))
            
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
        ''', (token, datetime.utcnow()))
        user_data = cur.fetchone()
        
        if user_data:
            # Mark email as verified and clear token
            cur.execute('''
                UPDATE user_account 
                SET email_verified = TRUE, 
                    verification_token = NULL, 
                    verification_token_expires = NULL,
                    last_modified_date = %s
                WHERE user_id = %s
            ''', (datetime.utcnow(), user_data[0]))
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
                verification_expires = datetime.utcnow() + timedelta(hours=24)
                
                # Update token in database
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