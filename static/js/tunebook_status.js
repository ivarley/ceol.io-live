// My-tunebook (person_tune) status resolution — the CANONICAL vanilla-JS copy.
// The tune-detail modal (tune_detail_modal.js) and the My Tunes / session pages
// all delegate here; the only other implementation is the live logger's ES
// module twin (frontend/src/mylist.js, unit-tested — keep the two in sync).
//
// The rules:
//   - override row wins; else an auto instrument follows the base learn_status;
//     a manual instrument without a row is untracked (null)
//   - 'all' = the roll-up: furthest-along status across instruments that have
//     one; with 0/1 instruments it is simply the base learn_status
//
// Two layers: pure resolution (instrumentStatus/resolve — data in, status out)
// and a lazy-loaded map of the current user's whole list (load/statusFor) for
// pages that color/filter by tune_id.
(function () {
    'use strict';

    const STATUSES = ['want to learn', 'learning', 'learned'];
    const NOT_ON_LIST = 'not on list';
    const STATUS_RANK = { 'want to learn': 1, 'learning': 2, 'learned': 3 };
    const hasOwn = (o, k) => Object.prototype.hasOwnProperty.call(o || {}, k);

    let byTuneId = new Map(); // tune_id -> {learn_status, instrument_status}
    let instruments = [];     // [{instrument, is_auto}]
    let loaded = false;
    let loading = null;

    async function fetchAll() {
        let insts = [];
        const tunes = [];
        for (let page = 1; ; page++) {
            const res = await fetch(`/api/my-tunes?per_page=2000&page=${page}`, {
                headers: { Accept: 'application/json' },
                credentials: 'same-origin',
            });
            if (!res.ok) throw new Error('my-tunes failed: ' + res.status);
            const j = await res.json();
            if (page === 1) insts = j.instruments || [];
            tunes.push(...(j.tunes || []));
            if (!j.pagination || !j.pagination.has_next) break;
        }
        return { instruments: insts, tunes: tunes };
    }

    // Idempotent; concurrent callers share one in-flight fetch.
    function load() {
        if (loaded) return Promise.resolve();
        if (!loading) {
            loading = fetchAll()
                .then((d) => {
                    byTuneId = new Map();
                    d.tunes.forEach((t) => {
                        if (t.tune_id != null) {
                            byTuneId.set(t.tune_id, {
                                learn_status: t.learn_status,
                                instrument_status: t.instrument_status || {},
                            });
                        }
                    });
                    instruments = d.instruments;
                    loaded = true;
                })
                .finally(() => { loading = null; });
        }
        return loading;
    }

    // --- pure resolution (no loaded state; entry = {learn_status, instrument_status}) ---

    // One instrument's status for an on-list entry: sparse override wins; else an
    // auto instrument follows the base learn_status; a manual one without a row
    // is untracked (null).
    function instrumentStatus(entry, inst) {
        if (hasOwn(entry.instrument_status, inst.instrument)) return entry.instrument_status[inst.instrument];
        return inst.is_auto ? entry.learn_status : null;
    }

    // Status for an entry under `scope` ('all' or an instrument name) against a
    // given instrument list. NOT_ON_LIST when entry is null/undefined (no
    // person_tune row) or the scoped instrument is untracked. A per-instrument
    // scope only means anything at 2+ instruments — below that the roll-up IS
    // the base learn_status (mirrors the modal's control, which hides the
    // per-instrument panel below that).
    function resolve(entry, insts, scope) {
        if (!entry) return NOT_ON_LIST;
        insts = insts || [];
        const scoped = scope && scope !== 'all' && insts.length >= 2 &&
            insts.some((i) => i.instrument === scope);
        if (scoped) {
            const inst = insts.find((i) => i.instrument === scope);
            return instrumentStatus(entry, inst) || NOT_ON_LIST;
        }
        if (insts.length < 2) return entry.learn_status;
        let best = null;
        insts.forEach((inst) => {
            const st = instrumentStatus(entry, inst);
            if (st && (!best || STATUS_RANK[st] > STATUS_RANK[best])) best = st;
        });
        return best || entry.learn_status;
    }

    // --- loaded-map convenience for pages that color/filter by tune_id ---

    function statusFor(tuneId, scope) {
        return resolve(byTuneId.get(tuneId), instruments, scope);
    }

    const classFor = (st) => 'ls-' + st.replace(/ /g, '-');

    window.TunebookStatus = {
        load: load,
        isLoaded: () => loaded,
        statusFor: statusFor,
        classFor: classFor,
        getInstruments: () => instruments,
        instrumentStatus: instrumentStatus,
        resolve: resolve,
        STATUSES: STATUSES,
        NOT_ON_LIST: NOT_ON_LIST,
        STATUS_RANK: STATUS_RANK,
    };
})();
