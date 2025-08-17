from flask import Flask
from flask_login import LoginManager
import os
from dotenv import load_dotenv

# Import our custom modules
from auth import User
from database import get_db_connection
from api_routes import *
from web_routes import *

load_dotenv()

app = Flask(__name__)
# Secret key required for Flask sessions (used by flash messages to store temporary messages in signed cookies)
app.secret_key = os.environ.get('FLASK_SESSION_SECRET_KEY', 'dev-secret-key-change-in-production')

# Configure Flask to handle trailing slashes consistently
app.url_map.strict_slashes = False

# Configure Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'

@login_manager.user_loader
def load_user(user_id):
    return User.get_by_id(int(user_id))

# Register web page routes
app.add_url_rule('/', 'home', home)
app.add_url_rule('/magic', 'magic', magic)
app.add_url_rule('/db-test', 'db_test', db_test)
app.add_url_rule('/sessions', 'sessions', sessions)
app.add_url_rule('/sessions/<path:session_path>/tunes', 'session_tunes', session_tunes)
app.add_url_rule('/sessions/<path:session_path>/tunes/<int:tune_id>', 'session_tune_info', session_tune_info)
app.add_url_rule('/sessions/<path:full_path>', 'session_handler', session_handler)
app.add_url_rule('/add-session', 'add_session', add_session)
app.add_url_rule('/help', 'help_page', help_page)
app.add_url_rule('/register', 'register', register, methods=['GET', 'POST'])
app.add_url_rule('/login', 'login', login, methods=['GET', 'POST'])
app.add_url_rule('/logout', 'logout', logout)
app.add_url_rule('/forgot-password', 'forgot_password', forgot_password, methods=['GET', 'POST'])
app.add_url_rule('/reset-password/<token>', 'reset_password', reset_password, methods=['GET', 'POST'])
app.add_url_rule('/change-password', 'change_password', change_password, methods=['GET', 'POST'])
app.add_url_rule('/verify-email/<token>', 'verify_email', verify_email)
app.add_url_rule('/resend-verification', 'resend_verification', resend_verification, methods=['GET', 'POST'])
app.add_url_rule('/admin', 'admin', admin)
app.add_url_rule('/admin/sessions', 'admin_sessions', admin_sessions)
app.add_url_rule('/admin/login-history', 'admin_login_history', admin_login_history)
app.add_url_rule('/admin/people', 'admin_people', admin_people)
app.add_url_rule('/admin/test-links', 'admin_test_links', admin_test_links)
app.add_url_rule('/admin/people/<int:person_id>', 'person_details', person_details)
app.add_url_rule('/admin/sessions/<path:session_path>', 'session_admin', session_admin)

# Register API routes
app.add_url_rule('/api/sessions/data', 'sessions_data', sessions_data)
app.add_url_rule('/api/sessions/<path:session_path>/tunes/<int:tune_id>/refresh_tunebook_count', 'refresh_tunebook_count_ajax', refresh_tunebook_count_ajax, methods=['POST'])
app.add_url_rule('/api/sessions/<path:session_path>/tunes/<int:tune_id>/aliases', 'get_session_tune_aliases', get_session_tune_aliases, methods=['GET'])
app.add_url_rule('/api/sessions/<path:session_path>/tunes/<int:tune_id>/aliases', 'add_session_tune_alias', add_session_tune_alias, methods=['POST'])
app.add_url_rule('/api/sessions/<path:session_path>/tunes/<int:tune_id>/aliases/<int:alias_id>', 'delete_session_tune_alias', delete_session_tune_alias, methods=['DELETE'])
app.add_url_rule('/api/sessions/<path:session_path>/add_instance', 'add_session_instance_ajax', add_session_instance_ajax, methods=['POST'])
app.add_url_rule('/api/sessions/<path:session_path>/update', 'update_session_ajax', update_session_ajax, methods=['PUT'])
app.add_url_rule('/api/sessions/<path:session_path>/<date>/update', 'update_session_instance_ajax', update_session_instance_ajax, methods=['PUT'])
app.add_url_rule('/api/sessions/<path:session_path>/<date>/tune_count', 'get_session_tune_count_ajax', get_session_tune_count_ajax)
app.add_url_rule('/api/sessions/<path:session_path>/<date>/delete', 'delete_session_instance_ajax', delete_session_instance_ajax, methods=['DELETE'])
app.add_url_rule('/api/sessions/<path:session_path>/<date>/add_tune', 'add_tune_ajax', add_tune_ajax, methods=['POST'])
app.add_url_rule('/api/sessions/<path:session_path>/<date>/delete_tune_by_order/<int:order_number>', 'delete_tune_by_order_ajax', delete_tune_by_order_ajax, methods=['DELETE'])
app.add_url_rule('/api/sessions/<path:session_path>/<date>/link_tune', 'link_tune_ajax', link_tune_ajax, methods=['POST'])
app.add_url_rule('/api/sessions/<path:session_path>/<date>/tunes', 'get_session_tunes_ajax', get_session_tunes_ajax)
app.add_url_rule('/api/sessions/<path:session_path>/<date>/move_set', 'move_set_ajax', move_set_ajax, methods=['POST'])
app.add_url_rule('/api/sessions/<path:session_path>/<date>/move_tune', 'move_tune_ajax', move_tune_ajax, methods=['POST'])
app.add_url_rule('/api/sessions/<path:session_path>/<date>/add_tunes_to_set', 'add_tunes_to_set_ajax', add_tunes_to_set_ajax, methods=['POST'])
app.add_url_rule('/api/sessions/<path:session_path>/<date>/edit_tune', 'edit_tune_ajax', edit_tune_ajax, methods=['POST'])
app.add_url_rule('/api/check-existing-session', 'check_existing_session_ajax', check_existing_session_ajax, methods=['POST'])
app.add_url_rule('/api/search-sessions', 'search_sessions_ajax', search_sessions_ajax, methods=['POST'])
app.add_url_rule('/api/fetch-session-data', 'fetch_session_data_ajax', fetch_session_data_ajax, methods=['POST'])
app.add_url_rule('/api/add-session', 'add_session_ajax', add_session_ajax, methods=['POST'])
app.add_url_rule('/api/admin/sessions/<path:session_path>/players', 'get_session_players_ajax', get_session_players_ajax)
app.add_url_rule('/api/admin/sessions/<path:session_path>/logs', 'get_session_logs_ajax', get_session_logs_ajax)
app.add_url_rule('/api/person/<int:person_id>/attendance', 'get_person_attendance_ajax', get_person_attendance_ajax)
app.add_url_rule('/api/person/<int:person_id>/logins', 'get_person_logins_ajax', get_person_logins_ajax)

if __name__ == '__main__':
    app.run(debug=True)