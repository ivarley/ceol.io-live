-- Create login_history table for tracking login events and security audit
CREATE TABLE login_history (
    login_history_id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES user_account(user_id) ON DELETE SET NULL,
    username VARCHAR(255), -- Store username even if user is deleted
    event_type VARCHAR(20) NOT NULL CHECK (event_type IN ('LOGIN_SUCCESS', 'LOGIN_FAILURE', 'LOGOUT', 'PASSWORD_RESET', 'ACCOUNT_LOCKED')),
    ip_address INET,
    user_agent TEXT,
    session_id VARCHAR(255), -- Reference to user_session.session_id for successful logins
    failure_reason VARCHAR(255), -- For failed login attempts (e.g., 'INVALID_PASSWORD', 'USER_NOT_FOUND', 'ACCOUNT_LOCKED')
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    additional_data JSONB -- For storing extra context like geolocation, device info, etc.
);

-- Create indexes for efficient querying
CREATE INDEX idx_login_history_user_id ON login_history(user_id);
CREATE INDEX idx_login_history_username ON login_history(username);
CREATE INDEX idx_login_history_event_type ON login_history(event_type);
CREATE INDEX idx_login_history_timestamp ON login_history(timestamp);
CREATE INDEX idx_login_history_ip_address ON login_history(ip_address);
CREATE INDEX idx_login_history_session_id ON login_history(session_id);

-- Composite index for common security queries
CREATE INDEX idx_login_history_user_event_time ON login_history(user_id, event_type, timestamp);
CREATE INDEX idx_login_history_ip_event_time ON login_history(ip_address, event_type, timestamp);