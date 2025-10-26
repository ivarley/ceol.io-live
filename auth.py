import secrets
import bcrypt
import json
from datetime import timedelta
from flask_login import UserMixin
from database import get_db_connection
from timezone_utils import now_utc

# Session configuration
SESSION_LIFETIME_WEEKS = 6


class User(UserMixin):
    def __init__(
        self,
        user_id,
        person_id,
        username,
        is_active=True,
        is_system_admin=False,
        first_name="",
        last_name="",
        email="",
        timezone="UTC",
        email_verified=False,
        auto_save_tunes=False,
        auto_save_interval=60,
        active_session=None,
    ):
        self.id = str(user_id)
        self.user_id = user_id
        self.person_id = person_id
        self.username = username
        self._is_active = is_active  # Store internally to avoid conflict with UserMixin
        self.is_system_admin = is_system_admin
        self.first_name = first_name
        self.last_name = last_name
        self.email = email
        self.timezone = timezone
        self.email_verified = email_verified
        self.auto_save_tunes = auto_save_tunes
        self.auto_save_interval = auto_save_interval
        self.active_session = active_session  # Dict with session instance data or None
        self.hashed_password = None  # Will be set when loading from database

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
            cur.execute(
                """
                SELECT ua.user_id, ua.person_id, ua.username, ua.is_active, ua.is_system_admin,
                       ua.timezone, ua.email_verified, p.first_name, p.last_name, p.email, ua.auto_save_tunes, ua.auto_save_interval,
                       p.at_active_session_instance_id, si.session_id, si.date, si.start_time, si.end_time, si.location_override, s.name, s.path
                FROM user_account ua
                JOIN person p ON ua.person_id = p.person_id
                LEFT JOIN session_instance si ON p.at_active_session_instance_id = si.session_instance_id
                LEFT JOIN session s ON si.session_id = s.session_id
                WHERE ua.user_id = %s AND ua.is_active = TRUE
            """,
                (user_id,),
            )
            user_data = cur.fetchone()
            if user_data:
                # Build active session dict if data exists
                active_session = None
                if user_data[12]:  # at_active_session_instance_id
                    active_session = {
                        'session_instance_id': user_data[12],
                        'session_id': user_data[13],
                        'date': user_data[14],
                        'start_time': user_data[15],
                        'end_time': user_data[16],
                        'location_override': user_data[17],
                        'session_name': user_data[18],
                        'session_path': user_data[19]
                    }

                return User(
                    user_id=user_data[0],
                    person_id=user_data[1],
                    username=user_data[2],
                    is_active=user_data[3],
                    is_system_admin=user_data[4],
                    timezone=user_data[5],
                    email_verified=user_data[6],
                    first_name=user_data[7],
                    last_name=user_data[8],
                    email=user_data[9],
                    auto_save_tunes=user_data[10],
                    auto_save_interval=user_data[11],
                    active_session=active_session,
                )
            return None
        finally:
            conn.close()

    @staticmethod
    def get_by_username(username):
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT ua.user_id, ua.person_id, ua.username, ua.hashed_password, ua.is_active,
                       ua.is_system_admin, ua.timezone, ua.email_verified, p.first_name, p.last_name, p.email, ua.auto_save_tunes, ua.auto_save_interval
                FROM user_account ua
                JOIN person p ON ua.person_id = p.person_id
                WHERE ua.username = %s
            """,
                (username,),
            )
            user_data = cur.fetchone()
            if user_data:
                user = User(
                    user_id=user_data[0],
                    person_id=user_data[1],
                    username=user_data[2],
                    is_active=user_data[4],
                    is_system_admin=user_data[5],
                    timezone=user_data[6],
                    email_verified=user_data[7],
                    first_name=user_data[8],
                    last_name=user_data[9],
                    email=user_data[10],
                    auto_save_tunes=user_data[11],
                    auto_save_interval=user_data[12],
                )
                user.hashed_password = user_data[3]
                return user
            return None
        finally:
            conn.close()

    def check_password(self, password):
        if not self.hashed_password:
            return False
        return bcrypt.checkpw(
            password.encode("utf-8"), self.hashed_password.encode("utf-8")
        )

    @staticmethod
    def create_user(username, password, person_id, timezone="UTC", user_email=None, referred_by_person_id=None):
        hashed_password = bcrypt.hashpw(
            password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO user_account (person_id, username, user_email, hashed_password, timezone, referred_by_person_id)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING user_id
            """,
                (person_id, username, user_email, hashed_password, timezone, referred_by_person_id),
            )
            result = cur.fetchone()
            if not result:
                return None
            user_id = result[0]
            conn.commit()
            return user_id
        finally:
            conn.close()


def create_session(user_id, ip_address=None, user_agent=None):
    session_id = secrets.token_urlsafe(32)
    expires_at = now_utc() + timedelta(weeks=SESSION_LIFETIME_WEEKS)

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO user_session (session_id, user_id, expires_at, ip_address, user_agent)
            VALUES (%s, %s, %s, %s, %s)
        """,
            (session_id, user_id, expires_at, ip_address, user_agent),
        )
        conn.commit()
        return session_id
    finally:
        conn.close()


def cleanup_expired_sessions():
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM user_session WHERE expires_at < %s", (now_utc(),))
        conn.commit()
    finally:
        conn.close()


def update_session_activity(session_id):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE user_session
            SET last_accessed = %s
            WHERE session_id = %s AND expires_at > %s
        """,
            (now_utc(), session_id, now_utc()),
        )
        conn.commit()
    finally:
        conn.close()


def generate_password_reset_token():
    return secrets.token_urlsafe(32)


def generate_verification_token():
    return secrets.token_urlsafe(32)


def log_login_event(
    user_id,
    username,
    event_type,
    ip_address=None,
    user_agent=None,
    session_id=None,
    failure_reason=None,
    additional_data=None,
):
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

        cur.execute(
            """
            INSERT INTO login_history (
                user_id, username, event_type, ip_address, user_agent,
                session_id, failure_reason, additional_data
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
            (
                user_id,
                username,
                event_type,
                ip_address,
                user_agent,
                session_id,
                failure_reason,
                additional_data_json,
            ),
        )
        conn.commit()
    except Exception as e:
        print(f"Failed to log login event: {str(e)}")
    finally:
        conn.close()


# Attendance Permission Helper Functions

def can_view_attendance(user, session_id):
    """
    Check if a user can view attendance for a session.
    
    Args:
        user: User object with is_system_admin property
        session_id: Session ID to check permissions for
        
    Returns:
        bool: True if user can view attendance, False otherwise
    """
    # System admins can view any attendance
    if user.is_system_admin:
        return True
    
    # Check if user is a regular or admin for this session
    return is_session_regular(user.person_id, session_id) or is_session_admin(user.person_id, session_id)


def can_manage_attendance(user, session_id):
    """
    Check if a user can manage (add/edit/remove) attendance for a session.
    
    Args:
        user: User object with is_system_admin property
        session_id: Session ID to check permissions for
        
    Returns:
        bool: True if user can manage attendance, False otherwise
    """
    # System admins can manage any attendance
    if user.is_system_admin:
        return True
    
    # Only session admins can manage attendance (regulars cannot)
    return is_session_admin(user.person_id, session_id)


def is_session_regular(person_id, session_id):
    """
    Check if a person is a regular for a given session.
    
    Args:
        person_id: Person ID to check
        session_id: Session ID to check against
        
    Returns:
        bool: True if person is a regular for the session, False otherwise
    """
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT 1 FROM session_person 
            WHERE person_id = %s AND session_id = %s
        """,
            (person_id, session_id)
        )
        return cur.fetchone() is not None
    finally:
        conn.close()


def is_session_admin(person_id, session_id):
    """
    Check if a person is an admin for a given session.
    
    Args:
        person_id: Person ID to check
        session_id: Session ID to check against
        
    Returns:
        bool: True if person is an admin for the session, False otherwise
    """
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT 1 FROM session_person 
            WHERE person_id = %s AND session_id = %s AND is_admin = true
        """,
            (person_id, session_id)
        )
        return cur.fetchone() is not None
    finally:
        conn.close()
