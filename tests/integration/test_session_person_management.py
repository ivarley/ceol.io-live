"""
Integration test for automatic session_person record management (Fixed Version)
Tests the automatic creation/deletion of session_person records using existing test users.
"""

import pytest
import json


class TestSessionPersonManagement:
    """Integration tests for automatic session_person record management"""

    def test_adding_attendee_creates_session_person_record(self, client, authenticated_admin_user, sample_session_instance_data):
        """Test that adding someone as attending a session creates a session_person record if it doesn't exist"""
        session_instance_id = sample_session_instance_data['session_instance_id']
        person_id = authenticated_admin_user.person_id
        
        # Get the actual session_id from the database for this session_instance_id
        from database import get_db_connection
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT session_id FROM session_instance WHERE session_instance_id = %s", (session_instance_id,))
        session_id = cur.fetchone()[0]
        
        with authenticated_admin_user:
            # Clean up any existing records to ensure clean test state
            cur.execute("""
                DELETE FROM session_instance_person sip
                USING session_instance si
                WHERE sip.session_instance_id = si.session_instance_id
                AND si.session_id = %s AND sip.person_id = %s
            """, (session_id, person_id))
            
            # Remove existing session_person record
            cur.execute("""
                DELETE FROM session_person 
                WHERE session_id = %s AND person_id = %s
            """, (session_id, person_id))
            
            conn.commit()

            # Check that no session_person record exists initially
            cur.execute("""
                SELECT COUNT(*) FROM session_person 
                WHERE session_id = %s AND person_id = %s
            """, (session_id, person_id))
            
            initial_count = cur.fetchone()[0]
            assert initial_count == 0, "Session person record should not exist after cleanup"

            # Add the person as attending the session instance
            checkin_data = {
                'person_id': person_id,
                'attendance': 'yes'
            }
            
            response = client.post(
                f'/api/session_instance/{session_instance_id}/attendees/checkin',
                data=json.dumps(checkin_data),
                content_type='application/json'
            )
            
            assert response.status_code in [200, 201]
            
            # Check that session_person record was created with is_regular=false
            cur.execute("""
                SELECT is_regular, is_admin FROM session_person 
                WHERE session_id = %s AND person_id = %s
            """, (session_id, person_id))
            
            session_person_record = cur.fetchone()
            assert session_person_record is not None, "Session person record should be created"
            assert session_person_record[0] is False, "is_regular should be False by default"
            assert session_person_record[1] is False, "is_admin should be False by default"
            
            cur.close()
            conn.close()

    def test_adding_attendee_does_not_change_existing_session_person_record(self, client, authenticated_admin_user, sample_session_instance_data):
        """Test that adding someone as attending doesn't change existing session_person record"""
        session_instance_id = sample_session_instance_data['session_instance_id']
        person_id = authenticated_admin_user.person_id
        
        # Get the actual session_id from the database for this session_instance_id
        from database import get_db_connection
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT session_id FROM session_instance WHERE session_instance_id = %s", (session_instance_id,))
        session_id = cur.fetchone()[0]

        with authenticated_admin_user:
            # Clean up any existing records first
            cur.execute("""
                DELETE FROM session_instance_person sip
                USING session_instance si
                WHERE sip.session_instance_id = si.session_instance_id
                AND si.session_id = %s AND sip.person_id = %s
            """, (session_id, person_id))
            
            # Manually create a session_person record with is_regular=true
            cur.execute("""
                INSERT INTO session_person (session_id, person_id, is_regular, is_admin)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (session_id, person_id) 
                DO UPDATE SET is_regular = %s, is_admin = %s
            """, (session_id, person_id, True, False, True, False))
            conn.commit()
            
            # Add the person as attending the session instance
            checkin_data = {
                'person_id': person_id,
                'attendance': 'yes'
            }
            
            response = client.post(
                f'/api/session_instance/{session_instance_id}/attendees/checkin',
                data=json.dumps(checkin_data),
                content_type='application/json'
            )
            
            assert response.status_code in [200, 201]
            
            # Check that existing session_person record was NOT changed
            cur.execute("""
                SELECT is_regular, is_admin FROM session_person 
                WHERE session_id = %s AND person_id = %s
            """, (session_id, person_id))
            
            session_person_record = cur.fetchone()
            assert session_person_record is not None, "Session person record should still exist"
            assert session_person_record[0] is True, "is_regular should remain True"
            assert session_person_record[1] is False, "is_admin should remain False"
            
            cur.close()
            conn.close()

    def test_removing_last_attendee_deletes_session_person_record(self, client, authenticated_admin_user, sample_session_instance_data):
        """Test that removing the last attendance record deletes the session_person record"""
        session_instance_id = sample_session_instance_data['session_instance_id']
        person_id = authenticated_admin_user.person_id
        
        # Get the actual session_id from the database for this session_instance_id
        from database import get_db_connection
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT session_id FROM session_instance WHERE session_instance_id = %s", (session_instance_id,))
        session_id = cur.fetchone()[0]

        with authenticated_admin_user:
            # Clean up any existing records first
            cur.execute("""
                DELETE FROM session_instance_person sip
                USING session_instance si
                WHERE sip.session_instance_id = si.session_instance_id
                AND si.session_id = %s AND sip.person_id = %s
            """, (session_id, person_id))
            
            cur.execute("""
                DELETE FROM session_person 
                WHERE session_id = %s AND person_id = %s
            """, (session_id, person_id))
            
            conn.commit()

            # Add the person as attending (should create session_person record)
            checkin_data = {
                'person_id': person_id,
                'attendance': 'yes'
            }
            
            response = client.post(
                f'/api/session_instance/{session_instance_id}/attendees/checkin',
                data=json.dumps(checkin_data),
                content_type='application/json'
            )
            assert response.status_code in [200, 201]
            
            # Verify session_person record exists
            cur.execute("""
                SELECT COUNT(*) FROM session_person 
                WHERE session_id = %s AND person_id = %s
            """, (session_id, person_id))
            
            count_after_add = cur.fetchone()[0]
            assert count_after_add == 1, "Session person record should exist after adding"
            
            # Remove the attendee
            response = client.delete(
                f'/api/session_instance/{session_instance_id}/attendees/{person_id}'
            )
            assert response.status_code == 200
            
            # Verify session_person record was deleted
            cur.execute("""
                SELECT COUNT(*) FROM session_person 
                WHERE session_id = %s AND person_id = %s
            """, (session_id, person_id))
            
            count_after_remove = cur.fetchone()[0]
            assert count_after_remove == 0, "Session person record should be deleted after removing last attendance"
            
            cur.close()
            conn.close()

    def test_removing_one_of_multiple_attendances_keeps_session_person_record(self, client, authenticated_admin_user, multiple_session_instances):
        """Test that removing attendance from one instance doesn't delete session_person if other instances exist"""
        instances = multiple_session_instances['instances']
        session_instance_1 = instances[0]['session_instance_id']
        session_instance_2 = instances[1]['session_instance_id']
        person_id = authenticated_admin_user.person_id
        
        # Get the actual session_id from the database for this session_instance_id
        from database import get_db_connection
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT session_id FROM session_instance WHERE session_instance_id = %s", (session_instance_1,))
        session_id = cur.fetchone()[0]  # Both instances should have same session_id

        with authenticated_admin_user:
            # Clean up any existing records first
            cur.execute("""
                DELETE FROM session_instance_person sip
                USING session_instance si
                WHERE sip.session_instance_id = si.session_instance_id
                AND si.session_id = %s AND sip.person_id = %s
            """, (session_id, person_id))
            
            cur.execute("""
                DELETE FROM session_person 
                WHERE session_id = %s AND person_id = %s
            """, (session_id, person_id))
            
            conn.commit()

            # Add the person to both session instances
            checkin_data = {'person_id': person_id, 'attendance': 'yes'}
            
            response1 = client.post(
                f'/api/session_instance/{session_instance_1}/attendees/checkin',
                data=json.dumps(checkin_data),
                content_type='application/json'
            )
            assert response1.status_code in [200, 201]
            
            response2 = client.post(
                f'/api/session_instance/{session_instance_2}/attendees/checkin',
                data=json.dumps(checkin_data),
                content_type='application/json'
            )
            assert response2.status_code in [200, 201]
            
            # Verify session_person record exists
            cur.execute("""
                SELECT COUNT(*) FROM session_person 
                WHERE session_id = %s AND person_id = %s
            """, (session_id, person_id))
            
            count_after_adds = cur.fetchone()[0]
            assert count_after_adds == 1, "Session person record should exist after adding to both instances"
            
            # Remove from one instance only
            response = client.delete(
                f'/api/session_instance/{session_instance_1}/attendees/{person_id}'
            )
            assert response.status_code == 200
            
            # Verify session_person record still exists (person still attending other instance)
            cur.execute("""
                SELECT COUNT(*) FROM session_person 
                WHERE session_id = %s AND person_id = %s
            """, (session_id, person_id))
            
            count_after_partial_remove = cur.fetchone()[0]
            assert count_after_partial_remove == 1, "Session person record should still exist when person attends other instances"
            
            # Remove from the last instance
            response = client.delete(
                f'/api/session_instance/{session_instance_2}/attendees/{person_id}'
            )
            assert response.status_code == 200
            
            # Now session_person record should be deleted
            cur.execute("""
                SELECT COUNT(*) FROM session_person 
                WHERE session_id = %s AND person_id = %s
            """, (session_id, person_id))
            
            count_after_full_remove = cur.fetchone()[0]
            assert count_after_full_remove == 0, "Session person record should be deleted after removing from all instances"
            
            cur.close()
            conn.close()

    def test_cross_session_isolation(self, client, authenticated_admin_user, sample_session_instance_data):
        """Test that session_person records are only affected for the specific session"""
        session_instance_id = sample_session_instance_data['session_instance_id']
        person_id = authenticated_admin_user.person_id
        
        # Get the actual session_id from the database for this session_instance_id
        from database import get_db_connection
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT session_id FROM session_instance WHERE session_instance_id = %s", (session_instance_id,))
        session_id = cur.fetchone()[0]

        with authenticated_admin_user:
            # Clean up our test session records
            cur.execute("""
                DELETE FROM session_instance_person sip
                USING session_instance si
                WHERE sip.session_instance_id = si.session_instance_id
                AND si.session_id = %s AND sip.person_id = %s
            """, (session_id, person_id))
            
            cur.execute("""
                DELETE FROM session_person 
                WHERE session_id = %s AND person_id = %s
            """, (session_id, person_id))

            # Create a session_person record for a different session
            different_session_id = 13  # Using a different session ID
            cur.execute("""
                INSERT INTO session_person (session_id, person_id, is_regular, is_admin)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (session_id, person_id)
                DO UPDATE SET is_regular = %s, is_admin = %s
            """, (different_session_id, person_id, True, True, True, True))
            conn.commit()
            
            # Add person to our test session instance
            checkin_data = {'person_id': person_id, 'attendance': 'yes'}
            
            response = client.post(
                f'/api/session_instance/{session_instance_id}/attendees/checkin',
                data=json.dumps(checkin_data),
                content_type='application/json'
            )
            assert response.status_code in [200, 201]
            
            # Verify both session_person records exist
            cur.execute("""
                SELECT session_id, is_regular, is_admin FROM session_person 
                WHERE person_id = %s ORDER BY session_id
            """, (person_id,))
            
            session_person_records = cur.fetchall()
            assert len(session_person_records) >= 2, "Should have session_person records for both sessions"
            
            # Find records by session_id
            our_session_record = next((r for r in session_person_records if r[0] == session_id), None)
            other_session_record = next((r for r in session_person_records if r[0] == different_session_id), None)
            
            assert our_session_record is not None, "Should have record for our session"
            assert our_session_record[1] is False, "Our session record should have is_regular=False"
            assert our_session_record[2] is False, "Our session record should have is_admin=False"
            
            assert other_session_record is not None, "Should have record for other session"
            assert other_session_record[1] is True, "Other session record should remain is_regular=True"
            assert other_session_record[2] is True, "Other session record should remain is_admin=True"
            
            # Remove from our session instance
            response = client.delete(
                f'/api/session_instance/{session_instance_id}/attendees/{person_id}'
            )
            assert response.status_code == 200
            
            # Verify only our session_person record was deleted
            cur.execute("""
                SELECT session_id, is_regular, is_admin FROM session_person 
                WHERE person_id = %s ORDER BY session_id
            """, (person_id,))
            
            remaining_records = cur.fetchall()
            other_session_remaining = [r for r in remaining_records if r[0] == different_session_id]
            our_session_remaining = [r for r in remaining_records if r[0] == session_id]
            
            assert len(other_session_remaining) == 1, "Should still have record for the other session"
            assert len(our_session_remaining) == 0, "Should not have record for our session after deletion"
            assert other_session_remaining[0][1] is True, "Other session record should still be is_regular=True"
            assert other_session_remaining[0][2] is True, "Other session record should still be is_admin=True"
            
            cur.close()
            conn.close()