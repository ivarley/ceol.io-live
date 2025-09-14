"""
Integration tests for database operations.

Tests database interactions, data integrity, history tracking,
and complex queries with real database connections.
"""

import pytest
from datetime import datetime, date, timedelta
from unittest.mock import patch
import uuid
import time
import random

from database import (
    get_db_connection,
    save_to_history,
    find_matching_tune,
    normalize_apostrophes,
)
from auth import User, create_session
from timezone_utils import now_utc


@pytest.mark.integration
class TestDatabaseConnections:
    """Test database connection handling."""

    def test_database_connection_success(self, db_conn):
        """Test successful database connection."""
        assert db_conn is not None

        # Test basic query
        cursor = db_conn.cursor()
        cursor.execute("SELECT 1 as test_value")
        result = cursor.fetchone()
        assert result[0] == 1

    def test_database_transaction_rollback(self, db_conn):
        """Test transaction rollback functionality."""
        cursor = db_conn.cursor()
        unique_id = str(uuid.uuid4())[:8]

        # Use an existing table to test rollback functionality
        # First, ensure we have a clean starting state
        cursor.execute(
            "SELECT COUNT(*) FROM person WHERE first_name = %s",
            (f"TestRollback{unique_id}",),
        )
        initial_count = cursor.fetchone()[0]
        assert initial_count == 0

        # Insert data in transaction
        cursor.execute(
            """
            INSERT INTO person (first_name, last_name, email)
            VALUES (%s, %s, %s)
        """,
            (
                f"TestRollback{unique_id}",
                "User",
                f"testrollback{unique_id}@example.com",
            ),
        )

        # Verify data exists before rollback
        cursor.execute(
            "SELECT first_name FROM person WHERE first_name = %s",
            (f"TestRollback{unique_id}",),
        )
        assert cursor.fetchone() is not None

        # Rollback transaction
        db_conn.rollback()

        # Verify data is gone after rollback
        cursor.execute(
            "SELECT first_name FROM person WHERE first_name = %s",
            (f"TestRollback{unique_id}",),
        )
        assert cursor.fetchone() is None

    def test_database_connection_autoclose(self):
        """Test that database connections can be properly closed."""
        conn = get_db_connection()
        cursor = conn.cursor()

        # Use connection
        cursor.execute("SELECT 1")
        assert cursor.fetchone()[0] == 1

        # Close connection
        cursor.close()
        conn.close()

        # Verify connection is closed (this should not raise exception)
        assert conn.closed > 0


@pytest.mark.integration
class TestHistoryTracking:
    """Test audit history functionality."""

    def test_session_history_tracking(self, db_conn, db_cursor):
        """Test that session changes are tracked in history."""
        # Create test session with unique path
        unique_id = str(uuid.uuid4())[:8]
        session_name = f"History Test Session {unique_id}"
        session_path = f"history-test-{unique_id}"
        db_cursor.execute(
            """
            INSERT INTO session (name, path, city, state, country)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING session_id
        """,
            (session_name, session_path, "Austin", "TX", "USA"),
        )
        session_id = db_cursor.fetchone()[0]
        db_conn.commit()

        # Save to history before update
        save_to_history(db_cursor, "session", "UPDATE", session_id, "test_user")

        # Update session
        db_cursor.execute(
            """
            UPDATE session
            SET name = %s, last_modified_date = NOW()
            WHERE session_id = %s
        """,
            ("Updated History Session", session_id),
        )
        db_conn.commit()

        # Verify history record was created
        db_cursor.execute(
            """
            SELECT operation, changed_by, name
            FROM session_history
            WHERE session_id = %s
            ORDER BY changed_at DESC
            LIMIT 1
        """,
            (session_id,),
        )

        history_record = db_cursor.fetchone()
        assert history_record is not None
        assert history_record[0] == "UPDATE"
        assert history_record[1] == "test_user"
        assert history_record[2] == session_name  # Original name before update

    def test_user_account_history_tracking(self, db_conn, db_cursor):
        """Test that user account changes are tracked in history."""
        # Create test user with unique email
        unique_id = str(uuid.uuid4())[:8]
        email = f"history{unique_id}@example.com"
        db_cursor.execute(
            """
            INSERT INTO person (first_name, last_name, email)
            VALUES (%s, %s, %s)
            RETURNING person_id
        """,
            ("History", "User", email),
        )
        person_id = db_cursor.fetchone()[0]

        db_cursor.execute(
            """
            INSERT INTO user_account (person_id, username, user_email, hashed_password, timezone)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING user_id
        """,
            (person_id, f"historyuser{unique_id}", email, "hashedpass", "UTC"),
        )
        user_id = db_cursor.fetchone()[0]
        db_conn.commit()

        # Save to history before update
        save_to_history(db_cursor, "user_account", "UPDATE", user_id, "admin_user")

        # Update user
        db_cursor.execute(
            """
            UPDATE user_account
            SET timezone = %s, last_modified_date = NOW()
            WHERE user_id = %s
        """,
            ("America/New_York", user_id),
        )
        db_conn.commit()

        # Verify history record
        db_cursor.execute(
            """
            SELECT operation, changed_by, timezone
            FROM user_account_history
            WHERE user_id = %s
            ORDER BY changed_at DESC
            LIMIT 1
        """,
            (user_id,),
        )

        history_record = db_cursor.fetchone()
        assert history_record is not None
        assert history_record[0] == "UPDATE"
        assert history_record[1] == "admin_user"
        assert history_record[2] == "UTC"  # Original timezone before update

    def test_tune_history_tracking(self, db_conn, db_cursor):
        """Test that tune changes are tracked in history."""
        # Create test tune with unique ID that's less likely to collide
        # Use timestamp + random to ensure uniqueness across test runs
        
        # Generate a unique ID based on current time and randomness
        # Keep it within reasonable integer bounds while still being unique
        base_id = int(time.time()) % 100000  # Last 5 digits of timestamp in seconds
        random_part = random.randint(100, 999)  
        tune_id = 800000 + (base_id % 10000) * 100 + random_part  # Range: 800000-899999
        
        # If by very small chance this ID exists, try a few more times
        max_attempts = 5
        for attempt in range(max_attempts):
            try:
                db_cursor.execute(
                    """
                    INSERT INTO tune (tune_id, name, tune_type, tunebook_count_cached)
                    VALUES (%s, %s, %s, %s)
                """,
                    (tune_id, "History Tune", "Reel", 25),
                )
                db_conn.commit()
                break  # Success, exit retry loop
            except Exception as e:
                # If it's a uniqueness violation, try with a different ID
                if "unique constraint" in str(e).lower() and attempt < max_attempts - 1:
                    # Generate new ID for retry
                    base_id = int(time.time()) % 100000
                    random_part = random.randint(100, 999)
                    tune_id = 800000 + (base_id % 10000) * 100 + random_part + attempt  # Add attempt to ensure different ID
                    continue
                else:
                    # If it's not a uniqueness violation or we've exhausted attempts, re-raise
                    raise

        # Save to history before update
        save_to_history(db_cursor, "tune", "UPDATE", tune_id, "tune_admin")

        # Update tune
        db_cursor.execute(
            """
            UPDATE tune
            SET tunebook_count_cached = %s, tunebook_count_cached_date = NOW()
            WHERE tune_id = %s
        """,
            (30, tune_id),
        )
        db_conn.commit()

        # Verify history record
        db_cursor.execute(
            """
            SELECT operation, changed_by, tunebook_count_cached
            FROM tune_history
            WHERE tune_id = %s
            ORDER BY changed_at DESC
            LIMIT 1
        """,
            (tune_id,),
        )

        history_record = db_cursor.fetchone()
        assert history_record is not None
        assert history_record[0] == "UPDATE"
        assert history_record[1] == "tune_admin"
        assert history_record[2] == 25  # Original count before update


@pytest.mark.integration
class TestTuneMatching:
    """Test tune matching and search functionality."""

    def test_find_matching_tune_exact_alias(self, db_conn, db_cursor):
        """Test finding tune by exact session alias match."""
        # Create test session and tune with unique identifier
        unique_id = str(uuid.uuid4())[:8]
        session_path = f"tune-match-{unique_id}"
        db_cursor.execute(
            """
            INSERT INTO session (name, path, city, state, country)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING session_id
        """,
            (f"Tune Match Session {unique_id}", session_path, "Austin", "TX", "USA"),
        )
        session_id = db_cursor.fetchone()[0]

        tune_id = int(unique_id[:6], 16) % 100000 + 11000  # Generate unique tune ID
        db_cursor.execute(
            """
            INSERT INTO tune (tune_id, name, tune_type)
            VALUES (%s, %s, %s)
        """,
            (tune_id, f"The Original Tune Name {unique_id}", "Reel"),
        )

        # Create session_tune with alias
        db_cursor.execute(
            """
            INSERT INTO session_tune (session_id, tune_id, alias)
            VALUES (%s, %s, %s)
        """,
            (session_id, tune_id, f"Session Alias Name {unique_id}"),
        )
        db_conn.commit()

        # Test matching by alias
        matched_id, final_name, error = find_matching_tune(
            db_cursor, session_id, f"Session Alias Name {unique_id}"
        )

        assert matched_id == tune_id
        assert final_name == f"Session Alias Name {unique_id}"
        assert error is None

    def test_find_matching_tune_by_name_with_the_prefix(self, db_conn, db_cursor):
        """Test finding tune by name with 'The' prefix handling."""
        # Create test session with unique identifier
        unique_id = str(uuid.uuid4())[:8]
        session_path = f"the-prefix-{unique_id}"
        db_cursor.execute(
            """
            INSERT INTO session (name, path, city, state, country)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING session_id
        """,
            (f"The Prefix Session {unique_id}", session_path, "Austin", "TX", "USA"),
        )
        session_id = db_cursor.fetchone()[0]

        # Create tune with "The" prefix and unique ID
        tune_id = int(unique_id[:6], 16) % 100000 + 12000  # Generate unique tune ID
        db_cursor.execute(
            """
            INSERT INTO tune (tune_id, name, tune_type)
            VALUES (%s, %s, %s)
        """,
            (tune_id, f"The Test Reel {unique_id}", "Reel"),
        )
        db_conn.commit()

        # Test matching without "The" prefix
        search_name_without = f"Test Reel {unique_id}"
        matched_id, final_name, error = find_matching_tune(
            db_cursor, session_id, search_name_without
        )

        assert matched_id == tune_id
        assert final_name == f"The Test Reel {unique_id}"
        assert error is None

        # Test matching with "The" prefix
        search_name_with = f"The Test Reel {unique_id}"
        matched_id, final_name, error = find_matching_tune(
            db_cursor, session_id, search_name_with
        )

        assert matched_id == tune_id
        assert final_name == f"The Test Reel {unique_id}"
        assert error is None

    def test_find_matching_tune_session_tune_alias_table(self, db_conn, db_cursor):
        """Test finding tune in session_tune_alias table."""
        # Create test session and tune with unique identifier
        unique_id = str(uuid.uuid4())[:8]
        session_path = f"alias-table-{unique_id}"
        db_cursor.execute(
            """
            INSERT INTO session (name, path, city, state, country)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING session_id
        """,
            (f"Alias Table Session {unique_id}", session_path, "Austin", "TX", "USA"),
        )
        session_id = db_cursor.fetchone()[0]

        tune_id = int(unique_id[:6], 16) % 100000 + 10000  # Generate unique tune ID
        db_cursor.execute(
            """
            INSERT INTO tune (tune_id, name, tune_type)
            VALUES (%s, %s, %s)
        """,
            (tune_id, f"Original Tune Name {unique_id}", "Jig"),
        )

        # Create entry in session_tune_alias table
        db_cursor.execute(
            """
            INSERT INTO session_tune_alias (session_id, tune_id, alias, created_date)
            VALUES (%s, %s, %s, %s)
        """,
            (session_id, tune_id, f"Alias Table Name {unique_id}", now_utc()),
        )
        db_conn.commit()

        # Test matching from alias table
        matched_id, final_name, error = find_matching_tune(
            db_cursor, session_id, f"Alias Table Name {unique_id}"
        )

        assert matched_id == tune_id
        assert final_name == f"Alias Table Name {unique_id}"
        assert error is None

    def test_find_matching_tune_multiple_matches_error(self, db_conn, db_cursor):
        """Test error handling for multiple matches."""
        # Create test session with unique identifier
        unique_id = str(uuid.uuid4())[:8]
        session_path = f"multiple-match-{unique_id}"
        db_cursor.execute(
            """
            INSERT INTO session (name, path, city, state, country)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING session_id
        """,
            (
                f"Multiple Match Session {unique_id}",
                session_path,
                "Austin",
                "TX",
                "USA",
            ),
        )
        session_id = db_cursor.fetchone()[0]

        # Create multiple tunes with same alias but unique IDs
        tune_id_base = int(unique_id[:6], 16) % 100000 + 13000  # Generate unique base
        tune_ids = [tune_id_base, tune_id_base + 1]
        alias_name = f"Duplicate Alias {unique_id}"
        for i, tune_id in enumerate(tune_ids):
            db_cursor.execute(
                """
                INSERT INTO tune (tune_id, name, tune_type)
                VALUES (%s, %s, %s)
            """,
                (tune_id, f"Multiple Tune {unique_id} {i+1}", "Reel"),
            )

            db_cursor.execute(
                """
                INSERT INTO session_tune (session_id, tune_id, alias)
                VALUES (%s, %s, %s)
            """,
                (session_id, tune_id, alias_name),
            )
        db_conn.commit()

        # Test multiple matches
        matched_id, final_name, error = find_matching_tune(
            db_cursor, session_id, alias_name
        )

        assert matched_id is None
        assert final_name == alias_name
        assert "Multiple tunes found" in error

    def test_find_matching_tune_no_match(self, db_conn, db_cursor):
        """Test when no tune matches are found."""
        # Create test session with unique identifier
        unique_id = str(uuid.uuid4())[:8]
        session_path = f"no-match-{unique_id}"
        db_cursor.execute(
            """
            INSERT INTO session (name, path, city, state, country)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING session_id
        """,
            (f"No Match Session {unique_id}", session_path, "Austin", "TX", "USA"),
        )
        session_id = db_cursor.fetchone()[0]
        db_conn.commit()

        # Test with non-existent tune
        matched_id, final_name, error = find_matching_tune(
            db_cursor, session_id, "Nonexistent Tune"
        )

        assert matched_id is None
        assert final_name == "Nonexistent Tune"
        assert error is None

    def test_normalize_apostrophes_in_tune_search(self, db_conn, db_cursor):
        """Test that apostrophes are normalized in tune searches."""
        # Create test session and tune with unique identifiers
        unique_id = str(uuid.uuid4())[:8]
        session_path = f"apostrophe-{unique_id}"
        db_cursor.execute(
            """
            INSERT INTO session (name, path, city, state, country)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING session_id
        """,
            (f"Apostrophe Session {unique_id}", session_path, "Austin", "TX", "USA"),
        )
        session_id = db_cursor.fetchone()[0]

        tune_id = int(unique_id[:6], 16) % 100000 + 14000  # Generate unique tune ID
        tune_name = f"O'Brien's Reel {unique_id}"
        db_cursor.execute(
            """
            INSERT INTO tune (tune_id, name, tune_type)
            VALUES (%s, %s, %s)
        """,
            (tune_id, tune_name, "Reel"),
        )
        db_conn.commit()

        # Test with smart apostrophe (should be normalized and found)
        search_name = f"O'Brien's Reel {unique_id}"
        matched_id, final_name, error = find_matching_tune(
            db_cursor, session_id, search_name
        )

        assert matched_id == tune_id
        assert final_name == search_name
        assert error is None


@pytest.mark.integration
class TestComplexQueries:
    """Test complex database queries and data integrity."""

    def test_session_with_instances_and_tunes(self, db_conn, db_cursor):
        """Test complex query involving sessions, instances, and tunes."""
        # Create test session with unique identifier
        unique_id = str(uuid.uuid4())[:8]
        session_path = f"complex-query-{unique_id}"
        db_cursor.execute(
            """
            INSERT INTO session (name, path, city, state, country, timezone)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING session_id
        """,
            (
                f"Complex Query Session {unique_id}",
                session_path,
                "Austin",
                "TX",
                "USA",
                "America/Chicago",
            ),
        )
        session_id = db_cursor.fetchone()[0]

        # Create session instances
        test_dates = [date(2023, 8, 10), date(2023, 8, 17), date(2023, 8, 24)]
        instance_ids = []

        for test_date in test_dates:
            db_cursor.execute(
                """
                INSERT INTO session_instance (session_id, date, comments)
                VALUES (%s, %s, %s)
                RETURNING session_instance_id
            """,
                (session_id, test_date, f"Session on {test_date}"),
            )
            instance_ids.append(db_cursor.fetchone()[0])

        # Create tunes with unique IDs
        tune_id_base = int(unique_id[:6], 16) % 100000 + 15000
        tune_data = [
            (tune_id_base, f"Complex Query Reel 1 {unique_id}", "Reel"),
            (tune_id_base + 1, f"Complex Query Jig 1 {unique_id}", "Jig"),
            (tune_id_base + 2, f"Complex Query Reel 2 {unique_id}", "Reel"),
        ]

        for tune_id, name, tune_type in tune_data:
            db_cursor.execute(
                """
                INSERT INTO tune (tune_id, name, tune_type, tunebook_count_cached)
                VALUES (%s, %s, %s, %s)
            """,
                (tune_id, name, tune_type, 25 + tune_id % 10),
            )

        # Add tunes to instances
        for i, instance_id in enumerate(instance_ids):
            for j, (tune_id, name, _) in enumerate(
                tune_data[:2]
            ):  # First 2 tunes per instance
                db_cursor.execute(
                    """
                    INSERT INTO session_instance_tune (session_instance_id, tune_id, name, order_number, continues_set)
                    VALUES (%s, %s, %s, %s, %s)
                """,
                    (instance_id, tune_id, name, j + 1, j > 0),
                )

        db_conn.commit()

        # Complex query: Get session with instance count and most played tunes
        db_cursor.execute(
            """
            WITH tune_play_counts AS (
                SELECT
                    sit.tune_id,
                    t.name,
                    COUNT(*) as play_count
                FROM session_instance_tune sit
                JOIN session_instance si ON sit.session_instance_id = si.session_instance_id
                LEFT JOIN tune t ON sit.tune_id = t.tune_id
                WHERE si.session_id = %s
                GROUP BY sit.tune_id, t.name
            ),
            session_stats AS (
                SELECT
                    COUNT(DISTINCT si.session_instance_id) as instance_count,
                    COUNT(sit.session_instance_tune_id) as total_tunes
                FROM session_instance si
                LEFT JOIN session_instance_tune sit ON si.session_instance_id = sit.session_instance_id
                WHERE si.session_id = %s
            )
            SELECT
                s.name,
                s.city,
                s.timezone,
                ss.instance_count,
                ss.total_tunes,
                tpc.name as most_played_tune,
                tpc.play_count
            FROM session s
            CROSS JOIN session_stats ss
            LEFT JOIN tune_play_counts tpc ON tpc.play_count = (
                SELECT MAX(play_count) FROM tune_play_counts
            )
            WHERE s.session_id = %s
        """,
            (session_id, session_id, session_id),
        )

        result = db_cursor.fetchone()

        assert result is not None
        assert f"Complex Query Session {unique_id}" in result[0]  # session name
        assert result[1] == "Austin"  # city
        assert result[2] == "America/Chicago"  # timezone
        assert result[3] == 3  # instance_count
        assert result[4] == 6  # total_tunes (2 tunes × 3 instances)
        assert any(
            name in result[5]
            for name in [
                f"Complex Query Reel 1 {unique_id}",
                f"Complex Query Jig 1 {unique_id}",
            ]
        )  # most played tune
        assert result[6] == 3  # play_count (played in all 3 instances)

    def test_user_session_management_with_cleanup(self, db_conn, db_cursor):
        """Test user session management and automatic cleanup."""
        # Create test user with unique identifier
        unique_id = str(uuid.uuid4())[:8]
        email = f"sessionmgr{unique_id}@example.com"
        username = f"sessionmgr{unique_id}"

        db_cursor.execute(
            """
            INSERT INTO person (first_name, last_name, email)
            VALUES (%s, %s, %s)
            RETURNING person_id
        """,
            ("Session", "Manager", email),
        )
        person_id = db_cursor.fetchone()[0]

        db_cursor.execute(
            """
            INSERT INTO user_account (person_id, username, user_email, hashed_password)
            VALUES (%s, %s, %s, %s)
            RETURNING user_id
        """,
            (person_id, username, email, "hashedpass"),
        )
        user_id = db_cursor.fetchone()[0]
        db_conn.commit()

        # Create multiple sessions with different expiry times
        session_data = [
            ("active-session-1", now_utc() + timedelta(hours=1)),
            ("active-session-2", now_utc() + timedelta(days=1)),
            ("expired-session-1", now_utc() - timedelta(hours=1)),
            ("expired-session-2", now_utc() - timedelta(days=1)),
        ]

        for session_name, expires_at in session_data:
            session_id = f"{session_name}-{unique_id}"  # Make session IDs unique
            db_cursor.execute(
                """
                INSERT INTO user_session (session_id, user_id, expires_at, ip_address)
                VALUES (%s, %s, %s, %s)
            """,
                (session_id, user_id, expires_at, "127.0.0.1"),
            )
        db_conn.commit()

        # Test cleanup query (simulate cleanup_expired_sessions)
        db_cursor.execute(
            "DELETE FROM user_session WHERE expires_at < %s", (now_utc(),)
        )
        db_conn.commit()

        # Verify only active sessions remain
        db_cursor.execute(
            """
            SELECT session_id
            FROM user_session
            WHERE user_id = %s
            ORDER BY session_id
        """,
            (user_id,),
        )

        remaining_sessions = [row[0] for row in db_cursor.fetchall()]
        # Sessions now have UUID suffixes, so check for the pattern
        active_session_1 = f"active-session-1-{unique_id}"
        active_session_2 = f"active-session-2-{unique_id}"
        expired_session_1 = f"expired-session-1-{unique_id}"
        expired_session_2 = f"expired-session-2-{unique_id}"
        assert active_session_1 in remaining_sessions
        assert active_session_2 in remaining_sessions
        assert expired_session_1 not in remaining_sessions
        assert expired_session_2 not in remaining_sessions

    def test_data_integrity_constraints(self, db_conn, db_cursor):
        """Test database constraints and data integrity rules."""
        # Test unique constraints with unique identifier
        unique_id = str(uuid.uuid4())[:8]
        session_path = f"integrity-test-{unique_id}"

        db_cursor.execute(
            """
            INSERT INTO session (name, path, city, state, country)
            VALUES (%s, %s, %s, %s, %s)
        """,
            (f"Integrity Test {unique_id}", session_path, "Austin", "TX", "USA"),
        )
        db_conn.commit()

        # Try to insert duplicate path (should fail)
        with pytest.raises(Exception):  # Should raise integrity error
            db_cursor.execute(
                """
                INSERT INTO session (name, path, city, state, country)
                VALUES (%s, %s, %s, %s, %s)
            """,
                (f"Another Session {unique_id}", session_path, "Dallas", "TX", "USA"),
            )
            db_conn.commit()

        db_conn.rollback()  # Reset transaction state

        # Test foreign key constraints
        with pytest.raises(Exception):  # Should raise foreign key error
            db_cursor.execute(
                """
                INSERT INTO session_instance (session_id, date)
                VALUES (%s, %s)
            """,
                (99999, date(2023, 8, 15)),
            )  # Non-existent session_id
            db_conn.commit()

        db_conn.rollback()  # Reset transaction state
