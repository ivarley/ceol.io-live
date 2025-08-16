import os
import secrets
import bcrypt
import json
from datetime import datetime, timedelta
from flask_login import UserMixin
from database import get_db_connection

# Session configuration
SESSION_LIFETIME_WEEKS = 6


class User(UserMixin):
    def __init__(self, user_id, person_id, username, is_active=True, is_system_admin=False, 
                 first_name='', last_name='', email='', time_zone='UTC', email_verified=False):
        self.id = str(user_id)
        self.user_id = user_id
        self.person_id = person_id
        self.username = username
        self._is_active = is_active  # Store internally to avoid conflict with UserMixin
        self.is_system_admin = is_system_admin
        self.first_name = first_name
        self.last_name = last_name
        self.email = email
        self.time_zone = time_zone
        self.email_verified = email_verified

    @property
    def is_active(self):
        """Override UserMixin's is_active property"""
        return self._is_active

    def get_id(self):
        return str(self.user_id)

    @staticmethod
    def get_by_id(user_id):
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute('''
                SELECT ua.user_id, ua.person_id, ua.username, ua.is_active, ua.is_system_admin,
                       ua.time_zone, ua.email_verified, p.first_name, p.last_name, p.email
                FROM user_account ua
                JOIN person p ON ua.person_id = p.person_id
                WHERE ua.user_id = %s AND ua.is_active = TRUE
            ''', (user_id,))
            user_data = cur.fetchone()
            if user_data:
                return User(
                    user_id=user_data[0],
                    person_id=user_data[1],
                    username=user_data[2],
                    is_active=user_data[3],
                    is_system_admin=user_data[4],
                    time_zone=user_data[5],
                    email_verified=user_data[6],
                    first_name=user_data[7],
                    last_name=user_data[8],
                    email=user_data[9]
                )
            return None
        finally:
            conn.close()

    @staticmethod
    def get_by_username(username):
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute('''
                SELECT ua.user_id, ua.person_id, ua.username, ua.hashed_password, ua.is_active, 
                       ua.is_system_admin, ua.time_zone, ua.email_verified, p.first_name, p.last_name, p.email
                FROM user_account ua
                JOIN person p ON ua.person_id = p.person_id
                WHERE ua.username = %s
            ''', (username,))
            user_data = cur.fetchone()
            if user_data:
                user = User(
                    user_id=user_data[0],
                    person_id=user_data[1],
                    username=user_data[2],
                    is_active=user_data[4],
                    is_system_admin=user_data[5],
                    time_zone=user_data[6],
                    email_verified=user_data[7],
                    first_name=user_data[8],
                    last_name=user_data[9],
                    email=user_data[10]
                )
                user.hashed_password = user_data[3]
                return user
            return None
        finally:
            conn.close()

    def check_password(self, password):
        return bcrypt.checkpw(password.encode('utf-8'), self.hashed_password.encode('utf-8'))

    @staticmethod
    def create_user(username, password, person_id, time_zone='UTC'):
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute('''
                INSERT INTO user_account (person_id, username, hashed_password, time_zone)
                VALUES (%s, %s, %s, %s)
                RETURNING user_id
            ''', (person_id, username, hashed_password, time_zone))
            user_id = cur.fetchone()[0]
            conn.commit()
            return user_id
        finally:
            conn.close()


def create_session(user_id, ip_address=None, user_agent=None):
    session_id = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(weeks=SESSION_LIFETIME_WEEKS)
    
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO user_session (session_id, user_id, expires_at, ip_address, user_agent)
            VALUES (%s, %s, %s, %s, %s)
        ''', (session_id, user_id, expires_at, ip_address, user_agent))
        conn.commit()
        return session_id
    finally:
        conn.close()


def cleanup_expired_sessions():
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute('DELETE FROM user_session WHERE expires_at < %s', (datetime.utcnow(),))
        conn.commit()
    finally:
        conn.close()


def update_session_activity(session_id):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute('''
            UPDATE user_session 
            SET last_accessed = %s 
            WHERE session_id = %s AND expires_at > %s
        ''', (datetime.utcnow(), session_id, datetime.utcnow()))
        conn.commit()
    finally:
        conn.close()


def generate_password_reset_token():
    return secrets.token_urlsafe(32)


def generate_verification_token():
    return secrets.token_urlsafe(32)


def log_login_event(user_id, username, event_type, ip_address=None, user_agent=None, 
                   session_id=None, failure_reason=None, additional_data=None):
    """
    Log login/logout events to the login_history table.
    
    Args:
        user_id: User ID (can be None for failed logins)
        username: Username attempted
        event_type: 'LOGIN_SUCCESS', 'LOGIN_FAILURE', 'LOGOUT', 'PASSWORD_RESET', 'ACCOUNT_LOCKED'
        ip_address: Client IP address
        user_agent: Client user agent string
        session_id: Session ID for successful logins
        failure_reason: Reason for failed login ('INVALID_PASSWORD', 'USER_NOT_FOUND', 'ACCOUNT_LOCKED', etc.)
        additional_data: Dict of additional context data
    """
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        
        # Convert additional_data to JSON if provided
        additional_data_json = json.dumps(additional_data) if additional_data else None
        
        cur.execute('''
            INSERT INTO login_history (
                user_id, username, event_type, ip_address, user_agent,
                session_id, failure_reason, additional_data
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ''', (
            user_id, username, event_type, ip_address, user_agent,
            session_id, failure_reason, additional_data_json
        ))
        conn.commit()
    except Exception as e:
        print(f"Failed to log login event: {str(e)}")
    finally:
        conn.close()