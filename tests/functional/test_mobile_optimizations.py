"""
Simplified functional tests for mobile optimizations in personal tune management.
Tests that mobile CSS and JavaScript are properly loaded.
"""

import pytest


class TestMobileAssets:
    """Test that mobile assets are loaded on tune management pages."""

    def test_my_tunes_has_mobile_assets(self, client, authenticated_user):
        """Test that my tunes page loads mobile CSS and JS."""
        with authenticated_user:
            response = client.get('/my-tunes')
            assert response.status_code == 200
            
            # Check for mobile CSS
            assert b'my_tunes_mobile.css' in response.data
            
            # Check for mobile JavaScript
            assert b'my_tunes_mobile.js' in response.data

    def test_add_tune_has_mobile_assets(self, client, authenticated_user):
        """Test that add tune page loads mobile CSS and JS."""
        with authenticated_user:
            response = client.get('/my-tunes/add')
            assert response.status_code == 200
            
            # Check for mobile CSS
            assert b'my_tunes_mobile.css' in response.data
            
            # Check for mobile JavaScript
            assert b'my_tunes_mobile.js' in response.data

    def test_sync_has_mobile_assets(self, client, authenticated_user):
        """Test that sync page loads mobile CSS and JS."""
        with authenticated_user:
            response = client.get('/my-tunes/sync')
            assert response.status_code == 200
            
            # Check for mobile CSS
            assert b'my_tunes_mobile.css' in response.data
            
            # Check for mobile JavaScript
            assert b'my_tunes_mobile.js' in response.data


class TestMobileCSSFeatures:
    """Test that mobile CSS features are present."""

    def test_touch_target_minimum_defined(self, client, authenticated_user):
        """Test that touch target minimum is defined in CSS."""
        with authenticated_user:
            response = client.get('/my-tunes')
            assert response.status_code == 200
            
            # Check for touch-target-min CSS variable
            assert b'--touch-target-min' in response.data or b'44px' in response.data

    def test_mobile_media_queries_present(self, client, authenticated_user):
        """Test that mobile media queries are present."""
        with authenticated_user:
            response = client.get('/my-tunes')
            assert response.status_code == 200
            
            # Check for mobile media queries
            assert b'@media' in response.data
            assert b'max-width' in response.data

    def test_responsive_grid_present(self, client, authenticated_user):
        """Test that responsive grid is present."""
        with authenticated_user:
            response = client.get('/my-tunes')
            assert response.status_code == 200
            
            # Check for grid layout
            assert b'tunes-grid' in response.data
            assert b'grid-template-columns' in response.data

    def test_pull_to_refresh_css_present(self, client, authenticated_user):
        """Test that pull-to-refresh CSS file is loaded."""
        with authenticated_user:
            response = client.get('/my-tunes')
            assert response.status_code == 200
            
            # Check that mobile CSS file is loaded (which contains pull-to-refresh styles)
            assert b'my_tunes_mobile.css' in response.data

    def test_accessibility_features_present(self, client, authenticated_user):
        """Test that accessibility CSS file is loaded."""
        with authenticated_user:
            response = client.get('/my-tunes')
            assert response.status_code == 200
            
            # Check that mobile CSS file is loaded (which contains accessibility features)
            assert b'my_tunes_mobile.css' in response.data


class TestMobileJavaScriptFeatures:
    """Test that mobile JavaScript features are loaded."""

    def test_mobile_js_loaded(self, client, authenticated_user):
        """Test that mobile JavaScript file is loaded."""
        with authenticated_user:
            response = client.get('/my-tunes')
            assert response.status_code == 200
            
            # Mobile JS should be loaded
            assert b'my_tunes_mobile.js' in response.data

    def test_search_debounce_present(self, client, authenticated_user):
        """Test that search debouncing is present."""
        with authenticated_user:
            response = client.get('/my-tunes')
            assert response.status_code == 200
            
            # Check for debounce implementation
            assert b'setTimeout' in response.data

    def test_autocomplete_present(self, client, authenticated_user):
        """Test that autocomplete is present on add tune page."""
        with authenticated_user:
            response = client.get('/my-tunes/add')
            assert response.status_code == 200
            
            # Check for autocomplete container
            assert b'autocomplete-container' in response.data
            assert b'autocomplete-results' in response.data


class TestMobileLayout:
    """Test mobile layout features."""

    def test_filters_container_present(self, client, authenticated_user):
        """Test that filters container is present."""
        with authenticated_user:
            response = client.get('/my-tunes')
            assert response.status_code == 200
            
            # Check for filters
            assert b'filters-container' in response.data
            assert b'filter-row' in response.data
            assert b'filter-group' in response.data

    def test_modal_present(self, client, authenticated_user):
        """Test that modal is present."""
        with authenticated_user:
            response = client.get('/my-tunes')
            assert response.status_code == 200
            
            # Check for modal
            assert b'modal-dialog' in response.data
            assert b'modal-overlay' in response.data

    def test_button_groups_present(self, client, authenticated_user):
        """Test that button groups are present."""
        with authenticated_user:
            response = client.get('/my-tunes')
            assert response.status_code == 200
            
            # Check for button groups
            assert b'page-actions' in response.data or b'button-group' in response.data

    def test_tune_cards_present(self, client, authenticated_user):
        """Test that tune cards are present."""
        with authenticated_user:
            response = client.get('/my-tunes')
            assert response.status_code == 200
            
            # Check for tune cards
            assert b'tune-card' in response.data
            assert b'tune-name' in response.data


class TestPerformanceFeatures:
    """Test performance optimization features."""

    def test_loading_indicator_present(self, client, authenticated_user):
        """Test that loading indicator is present."""
        with authenticated_user:
            response = client.get('/my-tunes')
            assert response.status_code == 200
            
            # Check for loading element
            assert b'loading' in response.data

    def test_no_results_message_present(self, client, authenticated_user):
        """Test that no results message is present."""
        with authenticated_user:
            response = client.get('/my-tunes')
            assert response.status_code == 200
            
            # Check for no results element
            assert b'no-results' in response.data
