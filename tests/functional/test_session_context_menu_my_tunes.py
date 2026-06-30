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
    
    # NOTE: tests that asserted the My Tunes context-menu JavaScript was inlined
    # into templates/session_instance_detail.html were removed — that
    # context-menu integration no longer exists in the (now-deprecated)
    # word-processor logger template. The remaining test covers the still-current
    # API contract for adding tunes to a collection.

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
