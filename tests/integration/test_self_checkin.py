"""
Integration test for regular attendee self check-in
Tests the complete self-checkin flow for regular attendees.
"""

import pytest
import json
import uuid
from datetime import date


class TestSelfCheckin:
    """Integration tests for self check-in scenarios"""

    def test_regular_attendee_one_click_checkin(self, client, authenticated_regular_user, sample_session_instance_data):
        """Test that regular attendees can check themselves in with one click"""
        session_instance_id = sample_session_instance_data['session_instance_id']
        
        with authenticated_regular_user:
            user_person_id = authenticated_regular_user.person_id
            
            # One-click check-in
            checkin_data = {
                'person_id': user_person_id,
                'attendance': 'yes'
            }
            
            response = client.post(
                f'/api/session_instance/{session_instance_id}/attendees/checkin',
                data=json.dumps(checkin_data),
                content_type='application/json'
            )
        
        assert response.status_code in [200, 201]
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['attendance'] == 'yes'
        # Seeded roster people are members (spec 034).
        assert data['data']['relationship'] == 'member'

    def test_member_appears_in_attendance_list(self, client, authenticated_regular_user, sample_session_instance_data):
        """A member who checks in appears in the attendee list, carrying their relationship.

        The attendance list no longer pre-populates anyone; people appear only after they
        are actually added/checked in (the endpoint returns an empty `regulars` section by
        design). Spec 034: checking in must NOT downgrade an existing member to a visitor.
        """
        session_instance_id = sample_session_instance_data['session_instance_id']
        user_person_id = authenticated_regular_user.person_id

        with authenticated_regular_user:
            client.post(
                f'/api/session_instance/{session_instance_id}/attendees/checkin',
                data=json.dumps({'person_id': user_person_id, 'attendance': 'yes'}),
                content_type='application/json'
            )

            response = client.get(f'/api/session_instance/{session_instance_id}/attendees')
            assert response.status_code == 200
            data = json.loads(response.data)

            attendees = data['data']['attendees']
            match = next((a for a in attendees if a['person_id'] == user_person_id), None)
            assert match is not None
            assert match['relationship'] == 'member'

    def test_regular_can_change_attendance_status(self, client, authenticated_regular_user, sample_session_instance_data):
        """Test that regulars can change their attendance status multiple times"""
        session_instance_id = sample_session_instance_data['session_instance_id']
        user_person_id = authenticated_regular_user.person_id
        
        with authenticated_regular_user:
            # First: Check in as 'yes'
            response1 = client.post(
                f'/api/session_instance/{session_instance_id}/attendees/checkin',
                data=json.dumps({'person_id': user_person_id, 'attendance': 'yes'}),
                content_type='application/json'
            )
            assert response1.status_code in [200, 201]
            
            # Then: Change to 'maybe'
            response2 = client.post(
                f'/api/session_instance/{session_instance_id}/attendees/checkin',
                data=json.dumps({'person_id': user_person_id, 'attendance': 'maybe'}),
                content_type='application/json'
            )
            assert response2.status_code == 200
            
            data = json.loads(response2.data)
            assert data['data']['attendance'] == 'maybe'
            
            # Finally: Change to 'no'
            response3 = client.post(
                f'/api/session_instance/{session_instance_id}/attendees/checkin',
                data=json.dumps({'person_id': user_person_id, 'attendance': 'no'}),
                content_type='application/json'
            )
            assert response3.status_code == 200
            
            data = json.loads(response3.data)
            assert data['data']['attendance'] == 'no'

    def test_regular_checkin_with_comment(self, client, authenticated_regular_user, sample_session_instance_data):
        """Test that regulars can add comments when checking in"""
        session_instance_id = sample_session_instance_data['session_instance_id']
        user_person_id = authenticated_regular_user.person_id
        
        checkin_data = {
            'person_id': user_person_id,
            'attendance': 'yes',
            'comment': 'Bringing my new fiddle!'
        }
        
        with authenticated_regular_user:
            response = client.post(
                f'/api/session_instance/{session_instance_id}/attendees/checkin',
                data=json.dumps(checkin_data),
                content_type='application/json'
            )
        
        assert response.status_code in [200, 201]
        data = json.loads(response.data)
        assert data['success'] is True

    def test_outsider_self_checkin_creates_a_visitor(self, client, authenticated_user, non_regular_session_instance_id):
        """An outsider can check themselves into any session -- and lands as a VISITOR.

        Spec 034: self-check-in creates session_person(relationship='visitor', confirmed=FALSE).
        It must not make the session "one of yours", and it must not grant you the roster.
        """
        # A session the test user has no prior relationship with.
        session_instance_id = non_regular_session_instance_id
        
        with authenticated_user:
            user_person_id = authenticated_user.person_id
            
            checkin_data = {
                'person_id': user_person_id,
                'attendance': 'yes'
            }
            
            response = client.post(
                f'/api/session_instance/{session_instance_id}/attendees/checkin',
                data=json.dumps(checkin_data),
                content_type='application/json'
            )
        
        assert response.status_code in [200, 201]
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['relationship'] == 'visitor'  # turning up != membership

    def test_self_checkin_updates_attendance_list(self, client, authenticated_user, sample_session_instance_data):
        """Test that self check-in immediately updates the attendance list"""
        session_instance_id = sample_session_instance_data['session_instance_id']
        user_person_id = authenticated_user.person_id
        
        with authenticated_user:
            # Check initial state
            response1 = client.get(f'/api/session_instance/{session_instance_id}/attendees')
            initial_data = json.loads(response1.data)
            
            # Self check-in
            checkin_response = client.post(
                f'/api/session_instance/{session_instance_id}/attendees/checkin',
                data=json.dumps({'person_id': user_person_id, 'attendance': 'yes'}),
                content_type='application/json'
            )
            assert checkin_response.status_code in [200, 201]
            
            # Check updated state
            response2 = client.get(f'/api/session_instance/{session_instance_id}/attendees')
            updated_data = json.loads(response2.data)
            
            # Should now appear in attendees list
            all_attendees = updated_data['data']['regulars'] + updated_data['data']['attendees']
            attendee_ids = [a['person_id'] for a in all_attendees]
            
            assert user_person_id in attendee_ids

    def test_relationship_is_exposed_in_attendance_list(self, client, authenticated_regular_user, sample_session_instance_data):
        """Each attendee carries their `relationship` ('member' | 'visitor'), spec 034.

        There is no separately pre-populated "regulars" section, and no is_regular flag.
        Ordering by "regular-ness" is computed from actual attendance, not carried here.
        """
        session_instance_id = sample_session_instance_data['session_instance_id']

        with authenticated_regular_user:
            user_person_id = authenticated_regular_user.person_id
            client.post(
                f'/api/session_instance/{session_instance_id}/attendees/checkin',
                data=json.dumps({'person_id': user_person_id, 'attendance': 'yes'}),
                content_type='application/json'
            )

            response = client.get(f'/api/session_instance/{session_instance_id}/attendees')
            data = json.loads(response.data)

            all_attendees = data['data']['regulars'] + data['data']['attendees']
            match = next((a for a in all_attendees if a['person_id'] == user_person_id), None)
            assert match is not None
            assert match['relationship'] == 'member'

    def test_self_checkin_persistence_across_requests(self, client, authenticated_user, sample_session_instance_data):
        """Test that self check-in persists across multiple requests"""
        session_instance_id = sample_session_instance_data['session_instance_id']
        user_person_id = authenticated_user.person_id
        
        with authenticated_user:
            # Self check-in
            client.post(
                f'/api/session_instance/{session_instance_id}/attendees/checkin',
                data=json.dumps({'person_id': user_person_id, 'attendance': 'yes'}),
                content_type='application/json'
            )
            
            # Multiple subsequent requests should show consistent state
            for _ in range(3):
                response = client.get(f'/api/session_instance/{session_instance_id}/attendees')
                data = json.loads(response.data)
                
                all_attendees = data['data']['regulars'] + data['data']['attendees']
                user_attendee = next((a for a in all_attendees if a['person_id'] == user_person_id), None)
                
                assert user_attendee is not None
                assert user_attendee['attendance'] == 'yes'

    def test_self_checkin_cross_session_independence(self, client, authenticated_user, db_conn, db_cursor):
        """Check-in to one instance does not leak into another instance.

        Uses two freshly-created real instances so the assertion is deterministic
        (the old fixture referenced a session_instance_id that did not exist).
        """
        unique = str(uuid.uuid4())[:8]
        db_cursor.execute(
            """
            INSERT INTO session (name, path, city, state, country)
            VALUES (%s, %s, %s, %s, %s) RETURNING session_id
        """,
            (f"Indep Session {unique}", f"indep-{unique}", "Austin", "TX", "USA"),
        )
        session_id = db_cursor.fetchone()[0]
        db_cursor.execute(
            "INSERT INTO session_instance (session_id, date) VALUES (%s, %s) RETURNING session_instance_id",
            (session_id, date(2023, 8, 15)),
        )
        instance_a = db_cursor.fetchone()[0]
        db_cursor.execute(
            "INSERT INTO session_instance (session_id, date) VALUES (%s, %s) RETURNING session_instance_id",
            (session_id, date(2023, 8, 22)),
        )
        instance_b = db_cursor.fetchone()[0]
        db_conn.commit()

        user_person_id = authenticated_user.person_id

        with authenticated_user:
            # Check into instance A only
            checkin_response = client.post(
                f'/api/session_instance/{instance_a}/attendees/checkin',
                data=json.dumps({'person_id': user_person_id, 'attendance': 'yes'}),
                content_type='application/json'
            )
            assert checkin_response.status_code in [200, 201]

        # Verify in the DB: the user is an unconfirmed visitor of this brand-new
        # session, so they cannot read its people list (spec 034).
        # Instance A shows attendance
        db_cursor.execute(
            "SELECT attendance FROM session_instance_person WHERE session_instance_id = %s AND person_id = %s",
            (instance_a, user_person_id),
        )
        row_a = db_cursor.fetchone()
        assert row_a is not None
        assert row_a[0] == 'yes'

        # Instance B does not
        db_cursor.execute(
            "SELECT attendance FROM session_instance_person WHERE session_instance_id = %s AND person_id = %s",
            (instance_b, user_person_id),
        )
        assert db_cursor.fetchone() is None