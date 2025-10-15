"""
Functional tests for session context menu integration with My Tunes feature.

Tests the ability to add tunes from session instance detail page to personal collection
via context menu, and update tune status from the context menu.

Requirements: 6.1, 6.2, 6.3, 6.4
"""

import pytest
import json
from unittest.mock import patch, MagicMock


@pytest.mark.functional
class TestSessionContextMenuMyTunes:
    """Test suite for session context menu My Tunes integration."""
    
    def test_session_instance_template_includes_my_tunes_javascript(self, client):
        """
        Test that session instance detail template includes My Tunes JavaScript functions.
        
        Requirement: 6.1 - Context menu should include My Tunes functionality
        """
        # Read the template file directly to verify it contains the required code
        with open('templates/session_instance_detail.html', 'r') as f:
            template_content = f.read()
        
        # Check for authentication variable
        assert 'isUserAuthenticated' in template_content
        
        # Check for personal tune management functions
        assert 'checkPersonTune' in template_content
        assert 'addToMyTunes' in template_content
        assert 'updateTuneStatus' in template_content
        assert 'incrementHeardCount' in template_content
        assert 'personTuneCache' in template_content
        
        # Check for context menu integration
        assert 'Add to My Tunes' in template_content
        assert 'My Tunes:' in template_content
    
    def test_context_menu_shows_status_update_options(self, client):
        """
        Test that context menu includes status update options.
        
        Requirement: 6.3 - IF the tune is already in the user's collection THEN 
        the system SHALL display the current learn_status and allow updating it
        """
        # Read the template file directly
        with open('templates/session_instance_detail.html', 'r') as f:
            template_content = f.read()
        
        # Check for status options in context menu
        assert 'want to learn' in template_content
        assert 'learning' in template_content
        assert 'learned' in template_content
        
        # Check for heard count increment option
        assert 'Heard (' in template_content or 'heard_count' in template_content
    
    def test_cannot_add_unlinked_tune_to_collection(
        self, client, authenticated_user
    ):
        """
        Test that unlinked tunes (without tune_id) cannot be added to collection.
        
        Requirement: 6.2 - System should only allow adding linked tunes
        """
        with authenticated_user:
            # Try to add a tune without tune_id (should fail)
            response = client.post(
                '/api/my-tunes',
                data=json.dumps({'learn_status': 'want to learn'}),
                content_type='application/json'
            )
            
            assert response.status_code == 400
            data = json.loads(response.data)
            assert data['success'] is False
            assert 'tune_id' in data['error'].lower()
