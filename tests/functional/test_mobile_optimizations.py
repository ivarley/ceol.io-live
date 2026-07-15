"""
Simplified functional tests for mobile optimizations in personal tune management.
Tests that mobile CSS and JavaScript are properly loaded.
"""

import os

import pytest

# Mobile CSS now lives in an external stylesheet (linked from the page) rather
# than inline <style> blocks, so feature checks read the file directly.
_MOBILE_CSS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "static", "css", "my_tunes_mobile.css",
)


def _mobile_css():
    with open(_MOBILE_CSS_PATH, "r", encoding="utf-8") as fh:
        return fh.read()


class TestMobileAssets:
    """Test that mobile assets are loaded on tune management pages."""

    def test_my_tunes_has_mobile_assets(self, client, authenticated_user):
        """The thin shell loads the mobile stylesheet and the Svelte page bundle
        (spec 035 Step 2: markup renders client-side; my_tunes_mobile.js is
        legacy-only and no longer loaded here)."""
        with authenticated_user:
            response = client.get('/my-tunes')
            assert response.status_code == 200

            assert b'my_tunes_mobile.css' in response.data
            assert b'mytunespage/page.js' in response.data
            assert b'my_tunes_mobile.js' not in response.data

    def test_add_tune_redirects_to_pane(self, client, authenticated_user):
        """The legacy add page is folded away: /my-tunes/add redirects to the
        My Tunes page with the Svelte add pane auto-opened (?add=1)."""
        with authenticated_user:
            response = client.get('/my-tunes/add', follow_redirects=False)
            assert response.status_code == 302
            assert response.location == '/my-tunes?add=1'

    def test_sync_redirects_to_pane(self, client, authenticated_user):
        """The legacy sync page is folded away: /my-tunes/sync redirects to the
        My Tunes page with the add pane auto-opened in its sync view."""
        with authenticated_user:
            response = client.get('/my-tunes/sync', follow_redirects=False)
            assert response.status_code == 302
            assert response.location == '/my-tunes?add=1&sync=1'


class TestMobileCSSFeatures:
    """Test that mobile CSS features are present."""

    def test_touch_target_minimum_defined(self, client, authenticated_user):
        """Touch-target sizing is defined in the mobile stylesheet."""
        assert '44px' in _mobile_css()

    def test_mobile_media_queries_present(self, client, authenticated_user):
        """Mobile media queries live in the external stylesheet."""
        css = _mobile_css()
        assert '@media' in css
        assert 'max-width' in css

    def test_responsive_grid_present(self, client, authenticated_user):
        """The grid renders client-side (Svelte); the shell carries the mount root
        and embedded payload, and the grid CSS lives in the stylesheet."""
        with authenticated_user:
            response = client.get('/my-tunes')
            assert response.status_code == 200
            assert b'my-tunes-root' in response.data
            assert b'__PAGE_DATA__' in response.data
        assert 'grid-template-columns' in _mobile_css()

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
        """The Svelte page bundle (which owns all mobile interactions now) loads."""
        with authenticated_user:
            response = client.get('/my-tunes')
            assert response.status_code == 200

            assert b'mytunespage/page.js' in response.data

    def test_search_debounce_present(self, client, authenticated_user):
        """Test that search debouncing is present."""
        with authenticated_user:
            response = client.get('/my-tunes')
            assert response.status_code == 200
            
            # Check for debounce implementation
            assert b'setTimeout' in response.data

    def test_add_search_query_survives_redirect(self, client, authenticated_user):
        """The old autocomplete page is gone; ?q= rides the redirect so the
        Svelte add pane opens with its deep search prefilled."""
        with authenticated_user:
            response = client.get('/my-tunes/add?q=cooley', follow_redirects=False)
            assert response.status_code == 302
            assert response.location == '/my-tunes?add=1&q=cooley'


class TestMobileLayout:
    """Test mobile layout features."""

    def test_filters_container_present(self, client, authenticated_user):
        """Filter markup renders client-side; its CSS contract stays in the
        stylesheet the shell loads."""
        with authenticated_user:
            response = client.get('/my-tunes')
            assert response.status_code == 200
            assert b'my-tunes-root' in response.data
        css = _mobile_css()
        assert '.filters-container' in css
        assert '.filter-top-row' in css
        assert '.filter-button-group' in css

    def test_modal_present(self, client, authenticated_user):
        """The tune-detail modal renders client-side (spec 035 Step 3): the page
        loads the tunesheet bundle, which mounts #tune-detail-modal itself; its
        CSS contract stays in the shared stylesheet."""
        with authenticated_user:
            response = client.get('/my-tunes')
            assert response.status_code == 200

            # The Svelte sheet bundle (renders .modal-overlay/.modal-dialog at mount)
            assert b'tunesheet/sheet.js' in response.data
            assert b'css/tune_detail_modal.css' in response.data

    def test_button_groups_present(self, client, authenticated_user):
        """Button-group styling stays available to the client-rendered markup."""
        with authenticated_user:
            response = client.get('/my-tunes')
            assert response.status_code == 200
        css = _mobile_css()
        assert '.page-actions' in css or 'button-group' in css

    def test_tune_cards_present(self, client, authenticated_user):
        """Cards render client-side from the embedded payload — the embed carries
        the tune rows the cards are built from."""
        with authenticated_user:
            response = client.get('/my-tunes')
            assert response.status_code == 200
            assert b'__PAGE_DATA__' in response.data
            assert b'tune_name' in response.data  # serialized rows in the embed
        css = _mobile_css()
        assert '.tune-card' in css


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
        """The no-results state renders client-side; its styling stays loaded."""
        with authenticated_user:
            response = client.get('/my-tunes')
            assert response.status_code == 200
        assert '.no-results' in _mobile_css()
