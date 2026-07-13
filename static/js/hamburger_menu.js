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

function shareCurrentPage() {
    window.location.href = '/share?url=' + encodeURIComponent(window.location.href);
}

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

// The overlay itself is a Svelte component in the app-wide tunesheet bundle
// (frontend/src/tunesheet/FindTune.svelte, spec 035 Step 3c) — a kit Sheet whose
// body keeps the .ft-* DOM, styled by hamburger_menu.css. ensureTuneModal loads
// the bundle lazily on any page that somehow lacks it.
function openFindTuneOverlay() {
    ensureTuneModal().then(function () {
        if (window.FindTuneOverlay) window.FindTuneOverlay.open();
    }).catch(function () { /* bundle unavailable (should not happen: base.html loads it app-wide) */ });
}

// Ensure the shared tune-detail modal is available, lazy-loading the Svelte bundle
// (which renders its own #tune-detail-modal container) + css on pages that don't
// already include it. Module scripts don't reliably signal readiness via onload,
// so poll for window.TuneDetailModal with a timeout.
let _tuneModalLoading = null;
function ensureTuneModal() {
    if (window.TuneDetailModal && typeof window.TuneDetailModal.show === 'function') return Promise.resolve();
    if (_tuneModalLoading) return _tuneModalLoading;
    _tuneModalLoading = new Promise(function (resolve, reject) {
        if (!document.querySelector('link[href*="tune_detail_modal.css"]')) {
            const l = document.createElement('link');
            l.rel = 'stylesheet'; l.href = '/static/css/tune_detail_modal.css';
            document.head.appendChild(l);
        }
        if (!document.querySelector('script[src*="tunesheet/sheet.js"]')) {
            const s = document.createElement('script');
            s.type = 'module';
            s.src = '/static/tunesheet/sheet.js';
            s.onerror = reject;
            document.body.appendChild(s);
        }
        const start = Date.now();
        (function poll() {
            if (window.TuneDetailModal && typeof window.TuneDetailModal.show === 'function') return resolve();
            if (Date.now() - start > 10000) return reject(new Error('tune-detail modal failed to load'));
            setTimeout(poll, 50);
        })();
    });
    return _tuneModalLoading;
}
