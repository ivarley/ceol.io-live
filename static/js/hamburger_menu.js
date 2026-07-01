// Shared app hamburger-menu behavior (spec 024). Loaded by base.html and the
// live-logging shell so both use the SAME menu logic. Functions are global (called
// from inline onclick in templates/hamburger_menu.html).

function toggleHamburgerMenu() {
    const dropdown = document.getElementById('hamburgerDropdown');
    if (dropdown) dropdown.classList.toggle('show');
}

// Close dropdown when clicking outside it
document.addEventListener('click', function (event) {
    const hamburgerMenu = document.querySelector('.hamburger-menu');
    const dropdown = document.getElementById('hamburgerDropdown');
    if (hamburgerMenu && dropdown && !hamburgerMenu.contains(event.target)) {
        dropdown.classList.remove('show');
    }
});

// Prevent clicks on disabled items
document.addEventListener('click', function (event) {
    if (event.target.classList && event.target.classList.contains('disabled')) {
        event.preventDefault();
    }
});

// --- Dark mode (app-wide data-theme system; a no-op where the page is always dark) ---
function toggleDarkMode() {
    const currentTheme = document.documentElement.getAttribute('data-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    updateDarkModeText(newTheme);
    updateLogo(newTheme);
}

function updateLogo(theme) {
    // Kept for parity / future per-theme logos (currently one logo).
    void theme;
}

function updateDarkModeText(theme) {
    const darkModeText = document.getElementById('dark-mode-text');
    if (!darkModeText) return; // hidden in always-dark contexts (e.g. the live editor)
    darkModeText.textContent = theme === 'dark' ? '☀️ Light Mode' : '🌙 Dark Mode';
}

function shareCurrentPage() {
    window.location.href = '/share?url=' + encodeURIComponent(window.location.href);
}

document.addEventListener('DOMContentLoaded', function () {
    const savedTheme = localStorage.getItem('theme') || 'dark';
    updateDarkModeText(savedTheme);
    updateLogo(savedTheme);
});

// --- 'Find a tune' (context-aware) ---------------------------------------
// In the live editor, App.svelte sets window.__liveFindTune to insert into the current
// set. Everywhere else, open a small search overlay that opens the shared tune-detail
// modal on a result.
function findTune() {
    toggleHamburgerMenu(); // close the menu
    if (typeof window.__liveFindTune === 'function') {
        window.__liveFindTune();
    } else {
        openFindTuneOverlay();
    }
}

function openFindTuneOverlay() {
    if (document.getElementById('find-tune-overlay')) return;
    const ov = document.createElement('div');
    ov.id = 'find-tune-overlay';
    ov.innerHTML =
        '<div class="ft-scrim"></div>' +
        '<div class="ft-panel" role="dialog" aria-modal="true">' +
        '  <div class="ft-head"><span>Find a tune</span><button class="ft-close" aria-label="Close">✕</button></div>' +
        '  <input class="ft-input" type="text" placeholder="Search tunes…" autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false">' +
        '  <ul class="ft-results"></ul>' +
        '</div>';
    document.body.appendChild(ov);
    const input = ov.querySelector('.ft-input');
    const results = ov.querySelector('.ft-results');
    const close = () => ov.remove();
    ov.querySelector('.ft-scrim').addEventListener('click', close);
    ov.querySelector('.ft-close').addEventListener('click', close);
    document.addEventListener('keydown', function esc(e) { if (e.key === 'Escape') { close(); document.removeEventListener('keydown', esc); } });

    let timer = null, seq = 0;
    input.addEventListener('input', function () {
        const q = input.value.trim();
        if (timer) clearTimeout(timer);
        if (q.length < 2) { results.innerHTML = ''; return; }
        timer = setTimeout(async () => {
            const mine = ++seq;
            const render = (tunes) => {
                if (mine !== seq) return;
                results.innerHTML = (tunes && tunes.length)
                    ? tunes.map(t => `<li class="ft-item" data-tune-id="${t.tune_id}">${escapeHtmlFT(t.name)}<span class="ft-type">${t.tune_type || ''}</span></li>`).join('')
                    : '<li class="ft-empty">No tunes match</li>';
            };
            const offline = async () => {
                // Offline fallback: search the locally-cached bundle (your tunes + popular).
                if (window.CeolOffline) { try { return await window.CeolOffline.searchTunes(q, 10); } catch (e) {} }
                return null;
            };
            try {
                const res = await fetch('/api/tunes/search?q=' + encodeURIComponent(q) + '&limit=10', { credentials: 'same-origin' });
                const json = await res.json();
                if (mine !== seq) return;
                if (json && json.success && (json.tunes || []).length) { render(json.tunes); return; }
                const off = await offline();
                render(off !== null ? off : (json.tunes || []));
            } catch (e) {
                const off = await offline();
                if (off !== null) render(off);
            }
        }, 200);
    });
    results.addEventListener('click', function (e) {
        const li = e.target.closest('.ft-item');
        if (!li) return;
        const tuneId = parseInt(li.dataset.tuneId, 10);
        const tuneName = li.firstChild ? li.firstChild.textContent : '';
        close();
        // 'session_instance' context renders the session_tune shape our session-agnostic
        // /api/tunes/<id>/detail returns (no sessionPath/dateOrId — a global read view).
        ensureTuneModal().then(function () {
            window.TuneDetailModal.show({
                context: 'session_instance',
                tuneId: tuneId,
                apiEndpoint: '/api/tunes/' + tuneId + '/detail',
                additionalData: { isUserLoggedIn: true, tuneName: tuneName, global: true },
            });
        }).catch(function () { /* modal unavailable (should not happen: base.html loads it app-wide) */ });
    });
    setTimeout(() => input.focus(), 50);
}

function escapeHtmlFT(s) {
    const d = document.createElement('div'); d.textContent = s || ''; return d.innerHTML;
}

// Ensure the shared tune-detail modal is available, lazy-loading it (container + css + js)
// on pages that don't already include it (e.g. the home page). The modal self-inits even
// when its script loads after DOMContentLoaded.
let _tuneModalLoading = null;
function ensureTuneModal() {
    if (window.TuneDetailModal && typeof window.TuneDetailModal.show === 'function') return Promise.resolve();
    if (_tuneModalLoading) return _tuneModalLoading;
    _tuneModalLoading = new Promise(function (resolve, reject) {
        if (!document.getElementById('tune-detail-modal')) {
            document.body.insertAdjacentHTML('beforeend',
                '<div id="tune-detail-modal" class="modal-overlay"><div class="modal-dialog"><div id="tune-detail-content"></div></div></div>');
        }
        if (!document.querySelector('link[href*="tune_detail_modal.css"]')) {
            const l = document.createElement('link');
            l.rel = 'stylesheet'; l.href = '/static/css/tune_detail_modal.css';
            document.head.appendChild(l);
        }
        const s = document.createElement('script');
        s.src = '/static/js/tune_detail_modal.js';
        s.onload = function () { window.TuneDetailModal ? resolve() : reject(); };
        s.onerror = reject;
        document.body.appendChild(s);
    });
    return _tuneModalLoading;
}
