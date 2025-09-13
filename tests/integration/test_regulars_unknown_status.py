"""
Integration test for T047 - Always show regulars with unknown status
Tests that session regulars are always shown in attendance list, even without attendance records.
"""

import pytest
import json
from database import get_db_connection


class TestRegularsUnknownStatus:
    """Integration tests for showing regulars with unknown status"""

    def test_regulars_show_with_unknown_status_when_no_attendance_record(self, client, authenticated_admin_user):
        """Test that regulars appear with 'unknown' status when they have no attendance record"""
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            # Create test session
            cur.execute("""
                INSERT INTO session (session_id, name, path, location_name)
                VALUES (999, 'Test Session', 'test-session', 'Test Location')
                ON CONFLICT (session_id) DO NOTHING
            """)
            
            # Create test person
            cur.execute("""
                INSERT INTO person (person_id, first_name, last_name, email)
                VALUES (999, 'Test', 'Regular', 'test.regular@example.com')
                ON CONFLICT (person_id) DO NOTHING
            """)
            
            # Make person a regular of the session (but no attendance record)
            cur.execute("""
                INSERT INTO session_person (session_id, person_id, is_regular, is_admin)
                VALUES (999, 999, true, false)
                ON CONFLICT (session_id, person_id) DO NOTHING
            """)
            
            # Create session instance
            cur.execute("""
                INSERT INTO session_instance (session_instance_id, session_id, date)
                VALUES (999, 999, '2023-01-01')
                ON CONFLICT (session_instance_id) DO NOTHING
            """)
            
            conn.commit()
            
            # Test the API - should show the regular with 'unknown' status
            with authenticated_admin_user:
                response = client.get('/api/session_instance/999/attendees')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] is True
            
            # Should have one regular with 'unknown' status
            regulars = data['data']['regulars']
            assert len(regulars) == 1
            
            regular = regulars[0]
            assert regular['person_id'] == 999
            assert regular['display_name'] == 'Test R'
            assert regular['attendance'] == 'unknown'  # This should be the new 'unknown' status
            assert regular['is_regular'] is True
            
        finally:
            # Cleanup - order matters for foreign key constraints
            cur.execute("DELETE FROM session_instance_person WHERE session_instance_id = 999")
            cur.execute("DELETE FROM session_instance_tune WHERE session_instance_id = 999")
            cur.execute("DELETE FROM session_instance WHERE session_instance_id = 999") 
            cur.execute("DELETE FROM session_person WHERE session_id = 999")
            cur.execute("DELETE FROM person WHERE person_id = 999")
            cur.execute("DELETE FROM session WHERE session_id = 999")
            conn.commit()
            cur.close()
            conn.close()

    def test_regulars_with_attendance_still_show_correct_status(self, client, authenticated_admin_user):
        """Test that regulars with attendance records still show their actual status, not unknown"""
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Use unique IDs to avoid conflicts
        test_session_id = 99998
        test_person_id = 99998
        test_instance_id = 99998
        
        try:
            # Clean up any existing test data first
            cur.execute("DELETE FROM session_instance_person WHERE session_instance_id = %s", (test_instance_id,))
            cur.execute("DELETE FROM session_instance_tune WHERE session_instance_id = %s", (test_instance_id,))
            cur.execute("DELETE FROM session_instance WHERE session_instance_id = %s", (test_instance_id,))
            cur.execute("DELETE FROM session_person WHERE session_id = %s AND person_id = %s", (test_session_id, test_person_id))
            cur.execute("DELETE FROM person WHERE person_id = %s", (test_person_id,))
            cur.execute("DELETE FROM session WHERE session_id = %s", (test_session_id,))
            conn.commit()
            
            # Create test session
            cur.execute("""
                INSERT INTO session (session_id, name, path, location_name)
                VALUES (%s, 'Test Session 2', 'test-session-99998', 'Test Location')
            """, (test_session_id,))
            
            # Create test person
            cur.execute("""
                INSERT INTO person (person_id, first_name, last_name, email)
                VALUES (%s, 'Test', 'Regular2', 'test.regular99998@example.com')
            """, (test_person_id,))
            
            # Make person a regular of the session
            cur.execute("""
                INSERT INTO session_person (session_id, person_id, is_regular, is_admin)
                VALUES (%s, %s, true, false)
            """, (test_session_id, test_person_id))
            
            # Create session instance
            cur.execute("""
                INSERT INTO session_instance (session_instance_id, session_id, date)
                VALUES (%s, %s, '2023-01-02')
            """, (test_instance_id, test_session_id))
            
            # Add attendance record for the regular
            cur.execute("""
                INSERT INTO session_instance_person (session_instance_id, person_id, attendance, comment)
                VALUES (%s, %s, 'yes', 'Will be there')
            """, (test_instance_id, test_person_id))
            
            conn.commit()
            
            # Test the API - should show the regular with 'yes' status, not 'unknown'
            with authenticated_admin_user:
                response = client.get(f'/api/session_instance/{test_instance_id}/attendees')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] is True
            
            # Should have one regular with 'yes' status
            regulars = data['data']['regulars']
            assert len(regulars) == 1
            
            regular = regulars[0]
            assert regular['person_id'] == test_person_id
            assert regular['display_name'] == 'Test R'
            assert regular['attendance'] == 'yes'  # Should be actual status, not 'unknown'
            assert regular['is_regular'] is True
            assert regular['comment'] == 'Will be there'
            
        finally:
            # Cleanup - order matters for foreign key constraints
            cur.execute("DELETE FROM session_instance_person WHERE session_instance_id = %s", (test_instance_id,))
            cur.execute("DELETE FROM session_instance_tune WHERE session_instance_id = %s", (test_instance_id,))
            cur.execute("DELETE FROM session_instance WHERE session_instance_id = %s", (test_instance_id,))
            cur.execute("DELETE FROM session_person WHERE session_id = %s", (test_session_id,))
            cur.execute("DELETE FROM person WHERE person_id = %s", (test_person_id,))
            cur.execute("DELETE FROM session WHERE session_id = %s", (test_session_id,))
            conn.commit()
            cur.close()
            conn.close()

    def test_mixed_scenario_some_regulars_with_some_without_attendance(self, client, authenticated_admin_user):
        """Test scenario with mix of regulars - some with attendance, some without"""
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            # Create test session
            cur.execute("""
                INSERT INTO session (session_id, name, path, location_name)
                VALUES (997, 'Test Session 3', 'test-session-3', 'Test Location')
                ON CONFLICT (session_id) DO NOTHING
            """)
            
            # Create two test people
            cur.execute("""
                INSERT INTO person (person_id, first_name, last_name, email)
                VALUES 
                    (997, 'Regular', 'WithAttendance', 'reg.attendance@example.com'),
                    (996, 'Regular', 'NoAttendance', 'reg.noattendance@example.com')
                ON CONFLICT (person_id) DO NOTHING
            """)
            
            # Make both regulars of the session
            cur.execute("""
                INSERT INTO session_person (session_id, person_id, is_regular, is_admin)
                VALUES 
                    (997, 997, true, false),
                    (997, 996, true, false)
                ON CONFLICT (session_id, person_id) DO NOTHING
            """)
            
            # Create session instance
            cur.execute("""
                INSERT INTO session_instance (session_instance_id, session_id, date)
                VALUES (997, 997, '2023-01-03')
                ON CONFLICT (session_instance_id) DO NOTHING
            """)
            
            # Add attendance record for only one regular
            cur.execute("""
                INSERT INTO session_instance_person (session_instance_id, person_id, attendance, comment)
                VALUES (997, 997, 'maybe', 'Might attend')
                ON CONFLICT (session_instance_id, person_id) DO NOTHING
            """)
            
            conn.commit()
            
            # Test the API - should show both regulars
            with authenticated_admin_user:
                response = client.get('/api/session_instance/997/attendees')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] is True
            
            # Should have two regulars
            regulars = data['data']['regulars']
            assert len(regulars) == 2
            
            # Sort by person_id to ensure consistent testing
            regulars.sort(key=lambda x: x['person_id'])
            
            # First regular (996) should have 'unknown' status
            regular_no_attendance = regulars[0]
            assert regular_no_attendance['person_id'] == 996
            assert regular_no_attendance['attendance'] == 'unknown'
            assert regular_no_attendance['is_regular'] is True
            
            # Second regular (997) should have 'maybe' status
            regular_with_attendance = regulars[1]
            assert regular_with_attendance['person_id'] == 997
            assert regular_with_attendance['attendance'] == 'maybe'
            assert regular_with_attendance['comment'] == 'Might attend'
            assert regular_with_attendance['is_regular'] is True
            
        finally:
            # Cleanup - order matters for foreign key constraints
            cur.execute("DELETE FROM session_instance_person WHERE session_instance_id = 997")
            cur.execute("DELETE FROM session_instance_tune WHERE session_instance_id = 997")
            cur.execute("DELETE FROM session_instance WHERE session_instance_id = 997") 
            cur.execute("DELETE FROM session_person WHERE session_id = 997")
            cur.execute("DELETE FROM person WHERE person_id IN (996, 997)")
            cur.execute("DELETE FROM session WHERE session_id = 997")
            conn.commit()
            cur.close()
            conn.close()