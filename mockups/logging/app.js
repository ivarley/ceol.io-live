/* 021 Simplified Session Screen — prototype logic (dummy data, no backend)
 *
 * Core model decided in the design interview:
 *  - Append-at-end by default; cursor can relocate to a SEAM.
 *  - Rows act on a tune (Before / After / Change / Remove).
 *  - Seams are positions (insert here). Yellow line = relocated insertion point.
 *  - Bottom bar: [ field ][ mic ][ End set ]. Stay-hot burst entry.
 *  - "Go to end" pill: grey = just scroll, yellow = scroll + reset insertion.
 */

// ----------------------------- dummy data -----------------------------------

let _id = 1;
const uid = () => "t" + _id++;

// catalog: name, type, here (times played at THIS session), books (popularity)
const CATALOG = [
  { name: "The Silver Spear", type: "Reel", here: 14, books: 980 },
  { name: "The Bag of Spuds", type: "Reel", here: 9, books: 420 },
  { name: "The Maid Behind the Bar", type: "Reel", here: 12, books: 1500 },
  { name: "Cooley's", type: "Reel", here: 11, books: 1320 },
  { name: "The Wise Maid", type: "Reel", here: 6, books: 610 },
  { name: "The Banshee", type: "Reel", here: 7, books: 880 },
  { name: "The Kesh", type: "Jig", here: 18, books: 2100 },
  { name: "Morrison's", type: "Jig", here: 15, books: 1900 },
  { name: "The Cliffs of Moher", type: "Jig", here: 8, books: 740 },
  { name: "The Kesh Mountain", type: "Reel", here: 0, books: 120 },
  { name: "Tom Billy's", type: "Jig", here: 5, books: 510 },
  { name: "The Cuil Aodha", type: "Jig", here: 3, books: 240 },
  { name: "The Donegal Lass", type: "Jig", here: 2, books: 190 },
  { name: "The Hare in the Corn", type: "Jig", here: 4, books: 300 },
  { name: "The Frost is All Over", type: "Jig", here: 6, books: 650 },
  { name: "Gander in the Pratie Hole", type: "Jig", here: 3, books: 280 },
  { name: "Britches Full of Stitches", type: "Polka", here: 10, books: 560 },
  { name: "John Ryan's", type: "Polka", here: 9, books: 520 },
  { name: "Knocknaboul 1", type: "Polka", here: 5, books: 210 },
  { name: "Knocknaboul 2", type: "Polka", here: 5, books: 205 },
  { name: "The Butterfly", type: "Slip Jig", here: 7, books: 1100 },
  { name: "Drowsy Maggie", type: "Reel", here: 13, books: 1700 },
  { name: "The Musical Priest", type: "Reel", here: 8, books: 900 },
  { name: "The Sailor's Bonnet", type: "Reel", here: 6, books: 700 },
  { name: "The Lark in the Morning", type: "Jig", here: 4, books: 820 },
  { name: "Out on the Ocean", type: "Jig", here: 5, books: 760 },
  { name: "The Connaughtman's Rambles", type: "Jig", here: 6, books: 690 },
  { name: "Egan's", type: "Polka", here: 4, books: 180 },
  { name: "The Maid of Mount Cisco", type: "Reel", here: 2, books: 260 },
  { name: "The Old Bush", type: "Reel", here: 3, books: 340 },
];

const INSTRUMENTS = [
  "Fiddle", "Flute", "Tin Whistle", "Concertina", "Button Accordion",
  "Uilleann Pipes", "Banjo", "Bodhrán", "Guitar", "Bouzouki", "Mandolin", "Harp",
];

// the full roster of known players (search this to add to attendance)
const ROSTER = [
  "Sarah", "Méabh", "Liam", "Aoife", "Conor", "Niamh", "Pádraig", "Ian",
  "Brigid", "Cillian", "Saoirse", "Tadhg", "Órla", "Eoin", "Caoimhe", "Fionn",
  "Síle", "Ruairí", "Maeve", "Declan", "Gráinne", "Oisín", "Róisín", "Cormac",
  "Bríd", "Dónal", "Áine", "Seán",
];

// who's actively logging this session right now (presence)
const LOGGERS = [
  { initials: "IV", name: "Ian Varley", tag: "you", color: "#3b82f6" },
  { initials: "SN", name: "Sarah Nolan", tag: "", color: "#a855f7" },
  { initials: "MB", name: "Méabh Breathnach", tag: "", color: "#14b8a6" },
];
const CURRENT_USER = "Ian Varley"; // matches the logger name so attribution maps

function loggerColor(name) {
  const l = state.loggers.find((x) => x.name === name);
  return l ? l.color : "#888";
}

function mkTune(name, type, linked = true, by = CURRENT_USER) {
  return { id: uid(), name, type, linked, by, at: Date.now() };
}
function mkSet(tunes, closed = true) {
  return { id: uid(), tunes, closed, startedBy: null, loggedBy: CURRENT_USER };
}

const state = {
  sets: [
    mkSet([
      mkTune("The Silver Spear", "Reel"),
      mkTune("The Bag of Spuds", "Reel"),
    ]),
    mkSet([
      mkTune("The Kesh", "Jig"),
      mkTune("Morrison's", "Jig"),
      mkTune("The Cliffs of Moher", "Jig"),
    ]),
    mkSet([
      mkTune("Britches Full of Stitches", "Polka"),
      mkTune("John Ryan's", "Polka"),
    ]),
  ],
  // cursor: where the next typed tune lands.
  //   {kind:'end'} | {kind:'in-set', setId, pos} | {kind:'new-set-after', index}
  //   {kind:'change', setId, tuneId}
  cursor: { kind: "end" },
  selectedTuneId: null, // which tune row is "opened" with its action bar
  entryActive: false,
  query: "",
  deepFilter: null, // active type filter in the deep-search modal
  starterPickerSetId: null, // which set's "started by" pop-in is open
  starterEditing: false,    // false = info mode (name already set), true = entry mode
  starterFilter: "",
  attendance: ["Sarah", "Méabh", "Liam", "Aoife", "Conor", "Niamh"], // present now
  headerExpanded: false,
  mode: "edit", // "edit" (logging) | "view" (read-only)
  notes: "Guest fiddler from Clare sat in for the second half.",
  loggers: LOGGERS.map((l) => ({ ...l })), // who's currently logging (mutable)
  reservations: [], // live position-holds: { id, by, name, color, setId, pos }
  mic: { on: false, paused: false, elapsed: 0, count: 0 },
  offline: false,
  serverQueue: [], // remote events deferred while you're offline
  atBottom: true,
  showBadge: true, // toggle: show "here N×" in results (try both)
};

// ----------------------------- helpers --------------------------------------

const $ = (id) => document.getElementById(id);
const listEl = $("list");
const fieldEl = $("field");
const sheetEl = $("entry-sheet");
const resultsEl = $("results");
const hintEl = $("entry-hint");
const pillEl = $("goend-pill");
const endBtn = $("endset");

function getSet(id) { return state.sets.find((s) => s.id === id); }
function lastSet() { return state.sets[state.sets.length - 1]; }

function viewMode() { return state.mode === "view"; }
function cursorIsEnd() { return state.cursor.kind === "end"; }
function cursorRelocated() {
  return state.cursor.kind === "in-set" || state.cursor.kind === "new-set-after";
}
function editing() { return cursorRelocated() || state.cursor.kind === "change"; }

// The concrete seam that should glow yellow. In 'end' mode this resolves to the
// trailing seam of the open set, so you can see where the next tune will land.
let activeSeam = null;
function activeSeamTarget() {
  const c = state.cursor;
  if (c.kind === "in-set" || c.kind === "new-set-after") return c;
  if (c.kind === "end") {
    const open = lastSet();
    if (open && !open.closed && open.tunes.length) {
      return { kind: "in-set", setId: open.id, pos: open.tunes.length };
    }
  }
  return null;
}

// The open set you can currently "End" — the last set in append mode, or the
// mid-list set you're actively inserting into.
function currentOpenSet() {
  const c = state.cursor;
  if (c.kind === "in-set") {
    const s = getSet(c.setId);
    if (s && !s.closed && s.tunes.length) return s;
  }
  if (c.kind === "end") {
    const s = lastSet();
    if (s && !s.closed && s.tunes.length) return s;
  }
  return null;
}

// Keep the set model sane before every render:
//  - only the last set (or the one being edited) may stay "in progress"
//  - empty set containers are dropped, and a dangling cursor returns to the end
function normalizeSets() {
  const c = state.cursor;
  state.sets.forEach((set, i) => {
    const isLast = i === state.sets.length - 1;
    const beingEdited = (c.kind === "in-set" || c.kind === "change") && c.setId === set.id;
    if (!set.closed && !isLast && !beingEdited) set.closed = true;
  });
  state.sets = state.sets.filter((s) => s.tunes.length > 0);
  if ((c.kind === "in-set" || c.kind === "change") && !getSet(c.setId)) {
    state.cursor = { kind: "end" };
  }
}

// Which set is currently being edited (gets the "Done" button beneath it)
function editSetId() {
  const c = state.cursor;
  if (c.kind === "in-set" || c.kind === "change") return c.setId;
  // new-set-after is handled in the render loop (Done goes *below* the inter seam)
  return null;
}

function setLabel(set) {
  if (!set.tunes.length) return set.closed ? "Set" : "New set";
  // label by first tune's type; note "Mixed" if not all same
  const types = new Set(set.tunes.map((t) => t.type));
  return types.size > 1 ? "Mixed" : set.tunes[0].type + "s";
}

// time of the most recently logged tune in the set, in the viewer's timezone
function setTime(set) {
  const ts = set.tunes.reduce((m, t) => Math.max(m, t.at || 0), 0);
  return ts ? new Date(ts).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }) : "";
}

// ----------------------------- rendering ------------------------------------

function render() {
  // wipe everything except the sentinel
  listEl.querySelectorAll(".set, .seam.inter, .done-btn, .offline-banner, .empty-state").forEach((n) => n.remove());

  const sentinel = $("bottom-sentinel");
  const frag = document.createDocumentFragment();

  // pinned offline banner (lives in the chrome, above the scrolling list)
  const ob = $("offline-banner");
  if (state.offline && !viewMode()) {
    const q = state.serverQueue.length;
    ob.classList.remove("hidden");
    ob.innerHTML = "📴 <b>Offline</b> — logging locally" +
      (q ? `, ${q} server update${q === 1 ? "" : "s"} waiting` : "") +
      " · <span class='reconnect'>Reconnect</span>";
    ob.onclick = () => toggleOffline();
  } else {
    ob.classList.add("hidden");
  }

  normalizeSets();
  const vm = viewMode();
  const editId = vm ? null : editSetId();
  activeSeam = vm ? null : activeSeamTarget();

  if (!state.sets.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    if (vm) {
      empty.textContent = "No tunes logged yet.";
    } else {
      empty.innerHTML = "No tunes logged yet. <button class='empty-add' type='button'>Add some!</button>";
      empty.querySelector(".empty-add").onclick = () => { state.cursor = { kind: "end" }; openEntry(); };
    }
    frag.appendChild(empty);
  }

  state.sets.forEach((set, si) => {
    frag.appendChild(renderSet(set, si));
    if (!vm && set.id === editId) frag.appendChild(renderDone());
    if (!vm && si < state.sets.length - 1) {
      frag.appendChild(
        seamEl("inter", { kind: "new-set-after", index: si }, "＋")
      );
      // Done belongs below the gap (next to where the new set would land)
      if (state.cursor.kind === "new-set-after" && state.cursor.index === si) {
        frag.appendChild(renderDone());
      }
    }
  });

  listEl.insertBefore(frag, sentinel);
  updateChrome();
  updateBar();
  updatePill();
  updateHeaderStats();
  $("header-expand").classList.toggle("hidden", !state.headerExpanded);
  $("header-chevron").classList.toggle("up", state.headerExpanded);
}

// show/hide the editing chrome vs the read-only footer
function updateChrome() {
  const vm = viewMode();
  $("phone").classList.toggle("view-mode", vm);
  document.querySelector(".bar").classList.toggle("hidden", vm);
  $("viewbar").classList.toggle("hidden", !vm);
  if (vm) {
    sheetEl.classList.add("hidden");
    pillEl.classList.add("hidden");
  }
}

function setMode(m) {
  state.mode = m;
  // leaving edit mode: drop all transient editing state
  closeEntry();
  state.cursor = { kind: "end" };
  state.selectedTuneId = null;
  state.starterPickerSetId = null;
  render();
}

function renderSet(set, si) {
  const isOpen = !set.closed;
  const card = document.createElement("div");
  card.className = "set" + (isOpen ? " open" : "");

  const vm = viewMode();
  const label = document.createElement("div");
  label.className = "set-label";
  label.textContent = setLabel(set) + (!vm && isOpen ? " · in progress…" : "");
  label.onclick = (e) => { e.stopPropagation(); openStarterPicker(set.id); };
  card.appendChild(label);

  // right-aligned "started by" pill (mirrors the type label)
  if (set.startedBy) {
    const sb = document.createElement("div");
    sb.className = "starter-pill";
    sb.textContent = set.startedBy;
    sb.onclick = (e) => { e.stopPropagation(); openStarterPicker(set.id); };
    card.appendChild(sb);
  }

  // "started by" pop-in, above the first tune (read-only in view mode)
  if (state.starterPickerSetId === set.id) card.appendChild(renderStarterPicker(set));

  // reservation holds for this set, by position (edit mode only)
  const resvAt = (pos) =>
    vm ? [] : state.reservations.filter((r) => r.setId === set.id && r.pos === pos);

  resvAt(0).forEach((r) => card.appendChild(renderReservationBar(r)));
  if (!vm) card.appendChild(seamEl("", { kind: "in-set", setId: set.id, pos: 0 }));

  set.tunes.forEach((t, ti) => {
    card.appendChild(renderTune(set, t));
    if (!vm && state.selectedTuneId === t.id) card.appendChild(renderActions(set, t, ti));
    resvAt(ti + 1).forEach((r) => card.appendChild(renderReservationBar(r)));
    if (!vm) card.appendChild(seamEl("", { kind: "in-set", setId: set.id, pos: ti + 1 }));
  });

  if (!set.tunes.length) {
    const empty = document.createElement("div");
    empty.className = "set-empty";
    empty.textContent = "Tap the field below to add the first tune…";
    card.appendChild(empty);
  }
  return card;
}

function renderTune(set, t) {
  const el = document.createElement("div");
  el.className = "tune" + (t.linked ? "" : " unlinked") +
    (state.selectedTuneId === t.id ? " selected" : "") +
    (t._new ? " flash" : "") +
    (t._merge ? " merge" : "") +
    (t._settle ? " settle" : "");

  // persistent attribution: a tune logged by someone else carries their color —
  // but only in edit mode (who's logging matters while logging, not while reading)
  const remote = t.byColor && t.by !== CURRENT_USER && !viewMode();
  if (remote) {
    el.classList.add("remote");
    el.style.setProperty("--by", t.byColor);
    el.style.borderColor = t.byColor;
    const dot = document.createElement("span");
    dot.className = "by-dot";
    dot.style.background = t.byColor;
    dot.title = "Logged by " + (t.byLabel || t.by);
    el.appendChild(dot);
  }

  // confidence: flag genuinely shaky entries (<= 70%) with a pill right by the
  // name (low confidence in *what the tune is* matters), plus a lighter pill
  if (t.confidence != null) {
    const rc = Math.round(t.confidence / 10) * 10;
    if (rc <= 70) {
      el.classList.add("lowconf");
      const cp = document.createElement("span");
      cp.className = "conf-pill";
      cp.textContent = rc + "%";
      cp.title = "Recognition confidence — Edit to confirm";
      el.appendChild(cp);
    }
  }

  const name = document.createElement("span");
  name.textContent = t.name;
  el.appendChild(name);

  if (t._pendingDelete) {
    el.classList.add("pending");
    name.style.textDecoration = "line-through";
    const p = document.createElement("span");
    p.className = "pending-mark";
    p.textContent = "⏳ removing";
    el.appendChild(p);
  } else if (t._pending) {
    el.classList.add("pending");
    const p = document.createElement("span");
    p.className = "pending-mark";
    p.textContent = "⏳ queued";
    el.appendChild(p);
  } else if (!t.linked) {
    const a = document.createElement("span");
    a.className = "attention";
    a.textContent = "⚠ unlinked";
    el.appendChild(a);
  }

  // per-row info icon — tap goes straight to the details drawer
  const info = document.createElement("button");
  info.className = "tune-info" + (t.linked ? "" : " after-warn");
  info.textContent = "ⓘ";
  info.onclick = (e) => { e.stopPropagation(); openTuneInfo(t); };
  el.appendChild(info);

  el.onclick = (e) => {
    e.stopPropagation();
    if (viewMode()) { openTuneInfo(t); return; } // read-only: tap = details
    const wasSelected = state.selectedTuneId === t.id;
    state.selectedTuneId = wasSelected ? null : t.id;
    if (!wasSelected) {
      // tapping a tune takes focus — cancel any armed seam / insert
      state.cursor = { kind: "end" };
      closeEntry();
    }
    render();
  };
  return el;
}

function renderActions(set, t, ti) {
  const mk = (label, fn, cls) => {
    const b = document.createElement("button");
    b.textContent = label;
    if (cls) b.className = cls;
    b.onclick = (e) => { e.stopPropagation(); fn(); };
    return b;
  };
  const wrap = document.createElement("div");
  wrap.className = "actions-wrap";
  const lowconf = t.confidence != null && Math.round(t.confidence / 10) * 10 <= 70;

  // unconfirmed (low-confidence) tunes get a dedicated Confirm / Edit row on top
  if (lowconf) {
    const top = document.createElement("div");
    top.className = "actions";
    top.appendChild(mk("✓ Confirm", () => confirmTune(set, t), "confirm"));
    top.appendChild(mk("✎ Edit", () => startChange(set, t)));
    wrap.appendChild(top);
  }

  const row = document.createElement("div");
  row.className = "actions";
  row.appendChild(mk("ⓘ Info", () => openTuneInfo(t), "info"));
  row.appendChild(mk("↑ Before", () => armInsert({ kind: "in-set", setId: set.id, pos: ti })));
  row.appendChild(mk("↓ After", () => armInsert({ kind: "in-set", setId: set.id, pos: ti + 1 })));
  if (!lowconf) row.appendChild(mk("✎ Edit", () => startChange(set, t))); // Edit lives in the top row when low-conf
  if (t._pendingDelete) {
    // already queued for removal (offline) → offer to undo that
    row.appendChild(mk("↩ Restore", () => { t._pendingDelete = false; render(); }, "confirm"));
  } else {
    row.appendChild(mk("🗑 Remove", () => removeTune(set, t), "danger"));
  }
  wrap.appendChild(row);
  return wrap;
}

// confirm a low-confidence tune as-is — a human vouched for the identity
function confirmTune(set, t) {
  const prevConf = t.confidence;
  t.confidence = null;
  state.selectedTuneId = null;
  render();
  showToast("Confirmed “" + t.name + "”", () => { t.confidence = prevConf; render(); }, 4000);
}

// ---- "started by" pop-in ----
function openStarterPicker(setId) {
  const opening = state.starterPickerSetId !== setId;
  state.starterPickerSetId = opening ? setId : null;
  state.starterFilter = "";
  if (opening) {
    const set = getSet(setId);
    state.starterEditing = !(set && set.startedBy); // info mode if already set
  }
  render();
}
function chooseStarter(set, name) {
  set.startedBy = name;
  state.starterPickerSetId = null;
  state.starterEditing = false;
  state.starterFilter = "";
  render();
}
function renderStarterPicker(set) {
  const box = document.createElement("div");
  box.className = "starter-popin";
  box.onclick = (e) => e.stopPropagation();

  // who logged this set + when the latest tune landed (informational, small)
  if (set.loggedBy) {
    const lb = document.createElement("div");
    lb.className = "starter-loggedby";
    const time = setTime(set);
    lb.textContent = "Logged by " + set.loggedBy + (time ? " · " + time : "");
    box.appendChild(lb);
  }

  // read-only in view mode: just show who started it, no editing
  if (viewMode()) {
    const line = document.createElement("div");
    line.className = "starter-viewline";
    line.textContent = set.startedBy ? "Started by " + set.startedBy : "Started by — not recorded";
    box.appendChild(line);
    return box;
  }

  // info mode: a name is already set — show it with a "Change" button
  if (set.startedBy && !state.starterEditing) {
    const info = document.createElement("div");
    info.className = "starter-info";
    const text = document.createElement("span");
    text.className = "starter-info-text";
    text.innerHTML = "Started by <b>" + set.startedBy + "</b>";
    const change = document.createElement("button");
    change.className = "starter-change";
    change.type = "button";
    change.textContent = "Change";
    change.onclick = (e) => {
      e.stopPropagation();
      set.startedBy = null;        // clear and drop into entry mode
      state.starterEditing = true;
      render();
    };
    info.appendChild(text);
    info.appendChild(change);
    box.appendChild(info);
    return box;
  }

  const head = document.createElement("div");
  head.className = "starter-head";
  head.textContent = "Who started this set?";
  box.appendChild(head);

  const filter = document.createElement("input");
  filter.className = "starter-filter";
  filter.placeholder = "Filter players…";
  filter.value = state.starterFilter;
  filter.oninput = () => { state.starterFilter = filter.value; buildStarterList(list, set); };
  box.appendChild(filter);

  const list = document.createElement("div");
  list.className = "starter-list";
  box.appendChild(list);
  buildStarterList(list, set);

  setTimeout(() => filter.focus(), 0);
  return box;
}
function buildStarterList(listEl, set) {
  listEl.innerHTML = "";
  const f = state.starterFilter.trim().toLowerCase();
  const item = (text, fn, cls) => {
    const b = document.createElement("button");
    b.className = "starter-item" + (cls ? " " + cls : "");
    b.type = "button";
    b.textContent = text;
    b.onclick = (e) => { e.stopPropagation(); fn(); };
    return b;
  };
  if (set.startedBy) listEl.appendChild(item("— No one / clear —", () => chooseStarter(set, null), "clear"));
  state.attendance.filter((n) => !f || n.toLowerCase().includes(f)).forEach((n) => {
    listEl.appendChild(item(n, () => chooseStarter(set, n), set.startedBy === n ? "selected" : ""));
  });
  // jump straight to the attendance editor to add someone not yet checked in
  listEl.appendChild(item("＋ Add people…", openAttendance, "add-people"));
}

function seamEl(extra, target, plusLabel) {
  const s = document.createElement("div");
  s.className = "seam " + extra + (sameTarget(target, activeSeam) ? " active" : "");
  const plus = document.createElement("span");
  plus.className = "plus";
  plus.textContent = plusLabel || "＋";
  s.appendChild(plus);
  s.onclick = (e) => { e.stopPropagation(); armInsert(target); };

  // when this seam is the armed (yellow) one, offer split/join on its right edge
  if (sameTarget(target, activeSeam)) {
    if (target.kind === "in-set") {
      const set = getSet(target.setId);
      if (set && target.pos > 0 && target.pos < set.tunes.length) {
        s.appendChild(seamActionBtn("Split", () => splitSet(set, target.pos)));
      }
    } else if (target.kind === "new-set-after") {
      s.appendChild(seamActionBtn("Join", () => joinSets(target.index)));
    }
  }
  return s;
}

function seamActionBtn(label, fn) {
  const b = document.createElement("button");
  b.className = "seam-action";
  b.type = "button";
  b.textContent = label;
  b.onclick = (e) => { e.stopPropagation(); fn(); };
  return b;
}

// split a set into two at `pos` (the front becomes a finished set, the tail
// keeps the original's open/closed state); leaves edit mode
function splitSet(set, pos) {
  const idx = state.sets.indexOf(set);
  const origTunes = set.tunes.slice();
  const origClosed = set.closed;
  const tail = set.tunes.splice(pos);
  const ns = mkSet(tail, set.closed);
  set.closed = true;
  state.reservations.forEach((r) => {
    if (r.setId === set.id && r.pos >= pos) { r.setId = ns.id; r.pos -= pos; }
  });
  state.sets.splice(idx + 1, 0, ns);
  state.cursor = { kind: "end" };
  closeEntry();
  render();
  showToast("Split into two sets", () => {
    state.sets = state.sets.filter((s) => s.id !== ns.id);
    set.tunes = origTunes;
    set.closed = origClosed;
    state.reservations.forEach((r) => { if (r.setId === ns.id) { r.setId = set.id; r.pos += pos; } });
    render();
  }, 4000);
}

// join the set at `index` with the one after it; leaves edit mode
function joinSets(index) {
  const a = state.sets[index], b = state.sets[index + 1];
  if (!a || !b) return;
  const aLen = a.tunes.length;
  const aClosed = a.closed;
  a.tunes = a.tunes.concat(b.tunes);
  a.closed = b.closed;
  state.reservations.forEach((r) => {
    if (r.setId === b.id) { r.setId = a.id; r.pos += aLen; }
  });
  state.sets.splice(index + 1, 1);
  state.cursor = { kind: "end" };
  closeEntry();
  render();
  showToast("Joined into one set", () => {
    a.tunes = a.tunes.slice(0, aLen);
    a.closed = aClosed;
    state.sets.splice(index + 1, 0, b);
    state.reservations.forEach((r) => { if (r.setId === a.id && r.pos >= aLen) { r.setId = b.id; r.pos -= aLen; } });
    render();
  }, 4000);
}

function sameTarget(a, b) {
  if (!a || !b || a.kind !== b.kind) return false;
  if (a.kind === "in-set") return a.setId === b.setId && a.pos === b.pos;
  if (a.kind === "new-set-after") return a.index === b.index;
  return false;
}

// ---- reservations: live "someone is typing here" position-holds ----
const resvTimers = {};

// insert a tune AND slide any reservation that sat at/after that spot down one,
// so a held slot re-anchors instead of being overwritten
function insertTuneAt(set, pos, tune) {
  set.tunes.splice(pos, 0, tune);
  state.reservations.forEach((r) => { if (r.setId === set.id && r.pos >= pos) r.pos++; });
}
function removeReservation(id) {
  state.reservations = state.reservations.filter((r) => r.id !== id);
  clearTimeout(resvTimers[id]);
  delete resvTimers[id];
  render();
}
function removeReservationByName(name) {
  const r = state.reservations.find((x) => x.by === name);
  if (r) removeReservation(r.id);
}
function renderReservationBar(r) {
  const el = document.createElement("div");
  el.className = "typing other resv";
  el.style.setProperty("--by", r.color);
  el.innerHTML =
    `<span class="typing-dot" style="background:${r.color}">${r.name[0]}</span>` +
    `<span>${r.name} is adding a tune</span>` +
    `<span class='dots'><span>•</span><span>•</span><span>•</span></span>`;
  return el;
}

// ----------------------------- bar / pill -----------------------------------

function updateBar() {
  if (viewMode()) return;
  if (state.cursor.kind === "change") {
    fieldEl.placeholder = "Change tune…";
    fieldEl.classList.add("relocating");
  } else if (cursorRelocated()) {
    fieldEl.placeholder = "Insert tune here…";
    fieldEl.classList.add("relocating");
  } else {
    fieldEl.placeholder = state.sets.length ? "Type next tune…" : "Type first tune…";
    fieldEl.classList.remove("relocating");
  }
  // End set only makes sense when there's an open set in play (last OR the
  // mid-list set you're inserting into)
  const canEnd = !!currentOpenSet();
  endBtn.classList.toggle("hidden", !canEnd); // only present when a set is in progress
  endBtn.classList.toggle("hot", canEnd);     // and glows yellow when it is
  // when no set is in progress, that slot offers a subtle "Done" → read-only view.
  // hide it while seam-editing (the yellow "✓ Done" means something else there,
  // and the two are easy to confuse)
  $("view-toggle").classList.toggle("hidden", canEnd || editing());
}

function updatePill() {
  // While editing at a seam, the exit is the "Done" button beside the set — not
  // a global pill. The grey scroll-pill only returns once you're back at 'end'.
  // Also suppress it while a tune is selected (the action row pushes the end
  // off-screen, but you're interacting, not lost).
  if (editing() || state.selectedTuneId) {
    pillEl.classList.add("hidden");
  } else if (!state.atBottom) {
    pillEl.classList.remove("hidden");
    pillEl.classList.remove("yellow");
    pillEl.textContent = "↓ Go to end";
  } else {
    pillEl.classList.add("hidden");
  }
}

// ----------------------------- actions --------------------------------------

function armInsert(target) {
  state.cursor = target;
  state.selectedTuneId = null;
  openEntry();
  render();
  scrollCursorIntoView();
}

function renderDone() {
  const b = document.createElement("button");
  b.className = "done-btn";
  b.textContent = "✓ Done";
  b.onclick = (e) => { e.stopPropagation(); doneEditing(); };
  return b;
}

function doneEditing() {
  state.cursor = { kind: "end" };
  state.selectedTuneId = null;
  closeEntry();
  render(); // grey "Go to end" pill now appears if we're scrolled up
}

function startChange(set, t) {
  state.cursor = { kind: "change", setId: set.id, tuneId: t.id };
  state.selectedTuneId = null;
  openEntry();
  fieldEl.value = t.name;
  state.query = t.name;
  renderResults();
  render();
}

function removeTune(set, t) {
  // offline: don't drop it yet — show it as pending removal so the change is
  // visible and syncs on reconnect
  if (state.offline) {
    t._pendingDelete = true;
    state.selectedTuneId = null;
    render();
    showToast("“" + t.name + "” — will be removed on sync", () => {
      t._pendingDelete = false; render();
    }, 4000);
    return;
  }
  const idx = set.tunes.findIndex((x) => x.id === t.id);
  const removed = set.tunes.splice(idx, 1)[0];
  state.selectedTuneId = null;
  // normalizeSets() (in render) drops the container if this emptied the set
  render();
  showToast("Removed “" + removed.name + "”", () => {
    const s = getSet(set.id) || (state.sets.push(mkSetWithId(set.id)), getSet(set.id));
    s.tunes.splice(Math.min(idx, s.tunes.length), 0, removed);
    render();
  });
}
function mkSetWithId(id) { return { id, tunes: [], closed: true }; }

function commitTune(tune) {
  const c = state.cursor;
  if (c.kind === "change") {
    const set = getSet(c.setId);
    const t = set.tunes.find((x) => x.id === c.tuneId);
    if (t) {
      t.name = tune.name; t.type = tune.type; t.linked = tune.linked;
      t.confidence = null; // a human picked it → confirmed, drop the % flag
      if (state.offline) t._pending = true; // edit queued until reconnect
    }
    state.cursor = { kind: "end" };
    closeEntry();
    render();
    return;
  }
  // corroboration: if this tune was just logged by someone else in the set
  // you're adding to, merge into that entry instead of duplicating it
  if (c.kind === "end" || c.kind === "in-set") {
    const target = c.kind === "end"
      ? (lastSet() && !lastSet().closed ? lastSet() : null)
      : getSet(c.setId);
    const dup = target && tune.linked && target.tunes.find(
      (x) => x.linked && x.by !== CURRENT_USER &&
        x.name.toLowerCase() === tune.name.toLowerCase());
    if (dup) {
      mergeIntoExisting(dup);
      fieldEl.value = "";
      state.query = "";
      renderResults();
      render();
      scrollCursorIntoView();
      return;
    }
  }

  if (c.kind === "end") {
    let set = lastSet();
    if (!set || set.closed) { set = mkSet([], false); state.sets.push(set); }
    insertTuneAt(set, set.tunes.length, tune);
  } else if (c.kind === "in-set") {
    insertTuneAt(getSet(c.setId), c.pos, tune);
    state.cursor = { kind: "in-set", setId: c.setId, pos: c.pos + 1 }; // stay-hot, advance
  } else if (c.kind === "new-set-after") {
    const set = mkSet([tune], false);
    state.sets.splice(c.index + 1, 0, set);
    state.cursor = { kind: "in-set", setId: set.id, pos: 1 };
  }
  // settle animation: the new tune flares brighter, then eases to its resting look
  tune._settle = true;
  setTimeout(() => { tune._settle = false; render(); }, 1600);
  if (state.offline) tune._pending = true; // logged locally, awaiting sync

  // stay hot: clear query, keep sheet open & field focused
  fieldEl.value = "";
  state.query = "";
  renderResults();
  render();
  scrollCursorIntoView();
}

// you logged a tune someone else already logged here → collapse to one entry,
// earliest keeps credit, you're recorded as corroborating (confidence up)
function mergeIntoExisting(dup) {
  dup._merge = true;
  dup.corroborated = dup.corroborated || [];
  if (!dup.corroborated.includes(CURRENT_USER)) dup.corroborated.push(CURRENT_USER);
  showToast(`“${dup.name}” already logged by ${dup.byLabel || dup.by} — merged`, null, 2600);
  setTimeout(() => { dup._merge = false; render(); }, 1400);
}

function endSet() {
  const set = currentOpenSet();
  if (set) set.closed = true;
  state.cursor = { kind: "end" };
  closeEntry();
  render();
}

function goToEnd() {
  state.cursor = { kind: "end" };
  closeEntry();
  render();
  listEl.scrollTo({ top: listEl.scrollHeight, behavior: "smooth" });
}

// ----------------------------- entry sheet ----------------------------------

function openEntry() {
  state.entryActive = true;
  sheetEl.classList.remove("hidden");
  renderResults();
  fieldEl.focus();
}
function closeEntry() {
  state.entryActive = false;
  sheetEl.classList.add("hidden");
  fieldEl.value = "";
  state.query = "";
  fieldEl.blur();
  if (state.cursor.kind === "change") state.cursor = { kind: "end" };
}

// the set your typed tune would land in right now (for the already-logged nudge)
function currentTargetSet() {
  const c = state.cursor;
  if (c.kind === "end") { const s = lastSet(); return s && !s.closed ? s : null; }
  if (c.kind === "in-set" || c.kind === "change") return getSet(c.setId);
  return null;
}

function rankResults(q) {
  const query = q.trim().toLowerCase();
  let pool = CATALOG.slice();
  if (query) pool = pool.filter((c) => c.name.toLowerCase().includes(query));
  // played-here first, then popularity
  pool.sort((a, b) => b.here - a.here || b.books - a.books);
  return pool.slice(0, 6);
}

function renderResults() {
  const q = state.query;
  resultsEl.innerHTML = "";

  // Empty field is quiet — popularity isn't a useful guess out of thousands of
  // tunes. Wait for the user to type before showing anything. (No hint row —
  // the field placeholder already says "Type next tune…".)
  if (!q.trim()) {
    hintEl.classList.add("hidden");
    hintEl.textContent = "";
    return;
  }
  hintEl.classList.remove("hidden");
  hintEl.textContent = "Tap a tune to log it";

  const target = currentTargetSet();
  rankResults(q).forEach((c) => {
    const r = document.createElement("div");
    r.className = "result";
    const n = document.createElement("span");
    n.className = "rname";
    n.textContent = c.name;
    const m = document.createElement("span");
    m.className = "rmeta";
    r.appendChild(n);

    // is this tune already in the set you're adding to?
    const dup = target && target.tunes.find(
      (t) => t.linked && t.name.toLowerCase() === c.name.toLowerCase());
    const isLast = dup && target.tunes[target.tunes.length - 1] === dup;
    const remote = dup && dup.by !== CURRENT_USER;

    if (dup && isLast && remote) {
      // just logged by someone else → nudge to beg off, with a one-tap Discard
      r.classList.add("just-logged");
      const who = (dup.byLabel || dup.by).split(" ")[0];
      m.innerHTML = "✓ just logged by <b>" + who + "</b>";
      r.appendChild(m);
      const dz = document.createElement("button");
      dz.className = "result-discard";
      dz.type = "button";
      dz.textContent = "Discard";
      dz.onclick = (e) => { e.stopPropagation(); fieldEl.value = ""; state.query = ""; renderResults(); };
      r.appendChild(dz);
    } else if (dup) {
      r.classList.add("already-here");
      m.textContent = "already in this set";
      r.appendChild(m);
    } else {
      m.innerHTML = state.showBadge && c.here
        ? c.type + " · <span class='here'>here " + c.here + "×</span>"
        : c.type + " · " + c.books + " books";
      r.appendChild(m);
    }

    r.onclick = () => commitTune(mkTune(c.name, c.type, true)); // merges if dup
    resultsEl.appendChild(r);
  });

  const sep = document.createElement("div");
  sep.className = "result-sep";
  resultsEl.appendChild(sep);

  // the only inline escape now: search deeper (which is where "log as-is" lives)
  const deep = document.createElement("div");
  deep.className = "result escape";
  deep.innerHTML = "<span class='ricon'>🔍</span><span class='rname'>Search deeper…</span>";
  deep.onclick = openDeepModal;
  resultsEl.appendChild(deep);
}

// ----------------------------- header expand + attendance -------------------

function updateHeaderStats() {
  const tunes = state.sets.reduce((n, s) => n + s.tunes.length, 0);
  const sets = state.sets.length;
  const n = state.attendance.length;
  const tunesTxt = `${tunes} ${tunes === 1 ? "tune" : "tunes"} in ${sets} ${sets === 1 ? "set" : "sets"}`;

  // notes line (shown in both modes when there's a note)
  const notesEl = $("header-notes");
  notesEl.classList.toggle("hidden", !state.notes.trim());
  notesEl.innerHTML = state.notes.trim() ? `<span>“${state.notes.trim()}”</span>` : "";

  // verbose "currently logging" list (both modes)
  renderLoggers();

  // collapsed view-mode header carries the summary inline under the date
  const summaryEl = $("session-summary");
  if (viewMode()) {
    summaryEl.classList.remove("hidden");
    summaryEl.textContent = tunesTxt + (state.notes.trim() ? " — " + state.notes.trim() : "");
  } else {
    summaryEl.classList.add("hidden");
    summaryEl.textContent = "";
  }

  if (viewMode()) {
    // informational only — no edit affordances
    $("header-tunes").innerHTML = `<span>${tunesTxt}</span>`;
    $("header-attend").innerHTML =
      `<span>In attendance (${n}): ${state.attendance.join(", ")}</span>`;
    return;
  }

  $("header-tunes").innerHTML =
    `<span>${tunesTxt}</span><button class="hchip" id="notes-link" type="button">Notes</button>`;
  $("header-attend").innerHTML =
    `<span>In attendance: ${n} ${n === 1 ? "person" : "people"}</span>` +
    `<button class="hchip" id="attend-link" type="button">Edit</button>`;
  $("notes-link").onclick = (e) => { e.stopPropagation(); openNotes(); };
  $("attend-link").onclick = (e) => { e.stopPropagation(); openAttendance(); };
}

function renderLoggers() {
  const box = $("header-loggers");
  box.innerHTML = "<div class='loggers-label'>Currently logging</div>";
  const list = state.offline ? state.loggers.filter((l) => l.tag === "you") : state.loggers;
  list.forEach((p) => {
    const row = document.createElement("div");
    row.className = "logger-row";
    const dot = document.createElement("span");
    dot.className = "logger-dot";
    dot.style.background = p.color;
    dot.textContent = p.initials;
    const name = document.createElement("span");
    name.textContent = p.name;
    row.appendChild(dot);
    row.appendChild(name);
    if (p.tag) {
      const tag = document.createElement("span");
      tag.className = "logger-tag";
      tag.textContent = p.tag;
      row.appendChild(tag);
    }
    box.appendChild(row);
  });
  if (state.offline) {
    const note = document.createElement("div");
    note.className = "loggers-offline-note";
    note.textContent = "Can't see others while you're offline";
    box.appendChild(note);
  }
}

function toggleHeader() {
  state.headerExpanded = !state.headerExpanded;
  render();
}

function openNotes() {
  $("notes-area").value = state.notes;
  $("notes-modal").classList.remove("hidden");
  $("notes-area").focus();
}
function openAttendance() {
  $("attend-add").value = "";
  $("attend-panel").classList.remove("hidden");
  renderAttendResults();
  renderAttendList();
  setTimeout(() => $("attend-add").focus(), 0);
}
function closeAttendance() {
  $("attend-panel").classList.add("hidden");
  render(); // refresh the starter picker (if open) with updated attendance
}

function addAttendee(name) {
  if (!state.attendance.includes(name)) state.attendance.push(name);
  $("attend-add").value = "";
  renderAttendResults();
  renderAttendList();
  updateHeaderStats();
  $("attend-add").focus();
}
function removeAttendee(name) {
  state.attendance = state.attendance.filter((n) => n !== name);
  renderAttendResults();
  renderAttendList();
  updateHeaderStats();
}

function renderAttendResults() {
  const box = $("attend-results");
  box.innerHTML = "";
  const q = $("attend-add").value.trim().toLowerCase();
  if (!q) return;
  const matches = ROSTER.filter((n) => n.toLowerCase().includes(q));
  const available = matches.filter((n) => !state.attendance.includes(n));
  const already = matches.filter((n) => state.attendance.includes(n));

  available.slice(0, 8).forEach((n) => {
    const r = document.createElement("button");
    r.className = "attend-result"; r.type = "button"; r.textContent = n;
    r.onclick = () => addAttendee(n);
    box.appendChild(r);
  });
  // already-attending matches sink to the bottom, disabled + italic
  already.forEach((n) => {
    const r = document.createElement("div");
    r.className = "attend-result disabled";
    r.textContent = n + " — already here";
    box.appendChild(r);
  });
  // escape hatch: add someone who isn't on the roster at all
  const raw = $("attend-add").value.trim();
  const add = document.createElement("button");
  add.className = "attend-result attend-newperson";
  add.type = "button";
  add.innerHTML = "＋ Add a new person “" + raw + "”";
  add.onclick = () => openNewPerson(raw);
  box.appendChild(add);
}

function openNewPerson(name) {
  const parts = name.trim().split(/\s+/);
  $("np-first").value = parts[0] || "";
  $("np-last").value = parts.slice(1).join(" ");
  $("np-email").value = "";
  $("np-other").value = "";
  const ibox = $("np-instruments");
  ibox.innerHTML = "";
  INSTRUMENTS.forEach((name) => {
    const l = document.createElement("label");
    l.className = "np-chk";
    const c = document.createElement("input");
    c.type = "checkbox"; c.value = name;
    l.appendChild(c);
    l.appendChild(document.createTextNode(name));
    ibox.appendChild(l);
  });
  $("newperson-modal").classList.remove("hidden");
  $("np-first").focus();
}

function addNewPerson() {
  const first = $("np-first").value.trim();
  const last = $("np-last").value.trim();
  if (!first) { $("np-first").focus(); return; }
  const full = (first + " " + last).trim();
  if (!ROSTER.includes(full)) ROSTER.push(full);
  if (!state.attendance.includes(full)) state.attendance.push(full);
  $("newperson-modal").classList.add("hidden");
  $("attend-add").value = "";
  renderAttendResults();
  renderAttendList();
  updateHeaderStats();
  showToast("Added " + full + " to attendance", null, 1800);
}

function renderAttendList() {
  const list = $("attend-list");
  $("attend-listlabel").textContent = `Currently here (${state.attendance.length})`;
  list.innerHTML = "";
  state.attendance.forEach((n) => {
    const row = document.createElement("div");
    row.className = "attend-person";
    const name = document.createElement("span");
    name.textContent = n;
    const rm = document.createElement("button");
    rm.className = "attend-remove"; rm.type = "button"; rm.textContent = "✕";
    rm.setAttribute("aria-label", "Remove " + n);
    rm.onclick = () => removeAttendee(n);
    row.appendChild(name); row.appendChild(rm);
    list.appendChild(row);
  });
}

// ----------------------------- tune details drawer --------------------------

function fauxHistory(n) {
  const months = ["Jun 2026", "May 2026", "Apr 2026", "Feb 2026", "Jan 2026",
                  "Nov 2025", "Sep 2025", "Jun 2025"];
  return months.slice(0, Math.max(0, Math.min(n, 6)));
}

function openTuneInfo(t) {
  const cat = CATALOG.find((c) => c.name === t.name);
  $("d-name").textContent = t.name;
  $("d-type").textContent = t.linked ? (cat ? cat.type : t.type) : "Not linked yet";

  const body = $("drawer-body");
  if (!t.linked) {
    body.innerHTML =
      "<div class='d-note'>This tune was logged as plain text and isn't linked to a " +
      "catalog tune yet, so there's no detail to show. Linking it pulls in the dots, " +
      "thesession.org page, stats and history.</div>" +
      "<button class='d-linkbtn' id='d-link-now'>🔍 Find &amp; link this tune</button>";
    body.querySelector("#d-link-now").onclick = () => {
      closeDrawer();
      const set = state.sets.find((s) => s.tunes.includes(t));
      if (set) startChange(set, t);
    };
    showDrawer();
    return;
  }

  const dates = fauxHistory(cat ? cat.here : 0);
  const here = cat ? cat.here : 0;
  const pop = cat ? cat.books : 0;
  const globalPlays = here * 3 + 8;
  const abc = `X:1
T:${t.name}
R:${cat ? cat.type : t.type}
M:4/4  L:1/8  K:Dmaj
|:~A3B AFED|FAdf edBd|cAce dBdf|1 ecAF DEFD:|`;

  body.innerHTML = `
    <div class="d-notation">
      <div class="d-staff" id="d-staff">${dotsSVG(t.name)}</div>
      <pre class="d-abc hidden" id="d-abc">${abc}</pre>
      <div class="d-notation-bar">
        <div class="d-toggle">
          <button class="seg active" data-v="notes">notes</button>
          <button class="seg" data-v="abc">abc</button>
        </div>
        <div class="d-extlinks">
          <a class="d-ext">thesession ↗</a>
          <a class="d-ext">abc-tools ↗</a>
        </div>
      </div>
    </div>

    <div class="d-listbanner">
      <span>On your list as</span>
      <select class="d-status">
        <option>Not in your list</option>
        <option selected>Learned</option>
        <option>Learning</option>
        <option>Want to learn</option>
      </select>
    </div>

    <div class="d-section">
      <div class="d-label">Stats</div>
      <div class="d-statlist">
        <div class="d-statrow"><span>TheSession.org popularity</span><b>${pop}</b></div>
        <div class="d-statrow"><span>Played at this session</span><b>${here}×</b></div>
        <div class="d-statrow"><span>Played globally</span><b>${globalPlays}</b></div>
        <div class="d-statrow muted"><span>Popularity updated</span><b>2025-08-18</b></div>
      </div>
    </div>

    <div class="d-section">
      <div class="d-label">History at this session</div>
      <ul class="d-history">${dates.map((d) => "<li>" + d + "</li>").join("") || "<li>—</li>"}</ul>
    </div>`;

  // notes / abc toggle
  body.querySelectorAll(".seg").forEach((seg) => {
    seg.onclick = () => {
      body.querySelectorAll(".seg").forEach((s) => s.classList.remove("active"));
      seg.classList.add("active");
      const abcMode = seg.dataset.v === "abc";
      $("d-staff").classList.toggle("hidden", abcMode);
      $("d-abc").classList.toggle("hidden", !abcMode);
    };
  });
  showDrawer();
}

function hashStr(s) {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) & 0xffff;
  return h;
}

// a tidy placeholder "dots" image — a staff with a few notes, on white.
// `seed` varies the melodic contour so different tunes don't render identically.
function dotsSVG(seed) {
  const h = hashStr(seed || "x");
  const lines = [18, 28, 38, 48, 58]
    .map((y) => `<line x1="34" y1="${y}" x2="306" y2="${y}" stroke="#333" stroke-width="1"/>`)
    .join("");
  const note = (x, y) =>
    `<ellipse cx="${x}" cy="${y}" rx="6" ry="4.4" fill="#111" transform="rotate(-20 ${x} ${y})"/>` +
    `<line x1="${x + 5.4}" y1="${y}" x2="${x + 5.4}" y2="${y - 27}" stroke="#111" stroke-width="1.6"/>`;
  const heights = [20, 25, 30, 35, 40, 45, 50, 55];
  const xs = [58, 86, 114, 150, 178, 206, 244, 272];
  let idx = h % heights.length;
  const notes = xs.map((x, i) => {
    idx = (idx + (((h >> i) & 3) - 1) + heights.length) % heights.length;
    return note(x, heights[idx]);
  }).join("");
  const bars = [132, 226]
    .map((x) => `<line x1="${x}" y1="18" x2="${x}" y2="58" stroke="#999" stroke-width="1"/>`)
    .join("");
  return `<svg viewBox="0 0 320 78" width="100%" height="78" xmlns="http://www.w3.org/2000/svg">` +
    `<rect width="320" height="78" fill="#fbfbf6"/>` +
    `<text x="12" y="54" font-size="46" fill="#111" font-family="Georgia, serif">𝄞</text>` +
    lines + bars + notes + `</svg>`;
}

function showDrawer() {
  const w = $("tune-drawer");
  w.classList.remove("hidden");
  requestAnimationFrame(() => w.classList.add("open"));
}
function closeDrawer() {
  const w = $("tune-drawer");
  w.classList.remove("open");
  setTimeout(() => w.classList.add("hidden"), 220);
}

// ----------------------------- mic (stub) -----------------------------------

// The mic is a persistent recorder: first tap starts it (stays on, auto-logging
// every ~9s); tapping again toggles a control panel with elapsed/count/pause/stop.
let micTicker = null;

function toggleMic() {
  if (!state.mic.on) {
    startMic();
  } else {
    const p = $("mic-panel");
    p.classList.toggle("hidden");
    if (!p.classList.contains("hidden")) {
      updateMicPanel();
      // the panel shortens the list; if we were at the end, scroll to keep it
      // in view rather than stranding behind a "Go to end" pill
      if (endIsFollowing()) requestAnimationFrame(scrollEnd);
    }
  }
}
function startMic() {
  state.mic = { on: true, paused: false, elapsed: 0, count: 0 };
  $("mic").classList.add("listening");
  showToast("🎤 Listening — tap the mic again for controls", null, 2600);
  clearInterval(micTicker);
  micTicker = setInterval(micTick, 1000);
}
function micTick() {
  if (!state.mic.on || state.mic.paused) return;
  state.mic.elapsed++;
  if (state.mic.elapsed % 9 === 0) micAutoAction();
  updateMicPanel();
}
function micAutoAction() {
  // sometimes the mic hears a pause and ends the current set instead of logging
  const open = lastSet();
  if (open && !open.closed && open.tunes.length >= 2 && Math.random() < 0.3) {
    open.closed = true;
    render();
    showToast("🎤 heard a pause — ended the set", null, 2200);
    return;
  }
  micAutoLog();
}
function micAutoLog() {
  const follow = endIsFollowing();
  const cat = CATALOG[Math.floor(Math.random() * CATALOG.length)];
  let set = lastSet();
  if (!set || set.closed) { set = mkSet([], false); set.loggedBy = CURRENT_USER; state.sets.push(set); }
  const t = mkTune(cat.name, cat.type, true, CURRENT_USER);
  t.confidence = 60 + Math.floor(Math.random() * 4) * 10; // 60-90%
  t.byLabel = "Your 🎤";
  t._settle = true;
  insertTuneAt(set, set.tunes.length, t);
  state.mic.count++;
  setTimeout(() => { t._settle = false; render(); }, 1600);
  render();
  if (follow) scrollEnd();
}
function toggleMicPause() {
  state.mic.paused = !state.mic.paused;
  $("mic").classList.toggle("listening", !state.mic.paused);
  updateMicPanel();
}
function stopMic() {
  clearInterval(micTicker);
  micTicker = null;
  state.mic.on = false;
  state.mic.paused = false;
  $("mic").classList.remove("listening");
  $("mic-panel").classList.add("hidden");
}
function fmtTime(s) {
  return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0");
}
function updateMicPanel() {
  if ($("mic-panel").classList.contains("hidden")) return;
  $("mic-time").textContent = fmtTime(state.mic.elapsed);
  $("mic-count").textContent = state.mic.count + (state.mic.count === 1 ? " tune" : " tunes") + " logged";
  $("mic-rec").classList.toggle("paused", state.mic.paused);
  $("mic-pause").textContent = state.mic.paused ? "Resume" : "Pause";
}

// ----------------------------- deep modal -----------------------------------

// the tune type of the set you're currently pointed at (for a pre-set filter)
function contextType() {
  const c = state.cursor;
  let set = null;
  if (c.kind === "in-set" || c.kind === "change") set = getSet(c.setId);
  else if (c.kind === "end") {
    // only the OPEN in-progress set counts — not the previous closed set when
    // you've just ended a set and are starting a fresh one
    const s = lastSet();
    if (s && !s.closed && s.tunes.length) set = s;
  }
  if (set && set.tunes.length) {
    const types = new Set(set.tunes.map((t) => t.type).filter((t) => t && t !== "?"));
    if (types.size === 1) return [...types][0];
  }
  return null;
}

function openDeepModal() {
  const m = $("deep-modal");
  m.classList.remove("hidden");
  // pre-set a type filter from the set you came in from
  state.deepFilter = contextType();
  $("deep-field").value = state.query;
  renderDeepFilter();
  renderDeepResults(state.query);
  $("deep-field").focus();
}

function renderDeepFilter() {
  const box = $("deep-filters");
  const tab = $("deep-filter-tab");
  box.innerHTML = "";
  if (state.deepFilter) {
    box.classList.remove("hidden");
    tab.classList.add("active");
    const pill = document.createElement("button");
    pill.className = "filter-pill";
    pill.type = "button";
    pill.innerHTML = state.deepFilter + "s <span class='x'>✕</span>";
    pill.onclick = () => {
      state.deepFilter = null;
      renderDeepFilter();
      renderDeepResults($("deep-field").value);
    };
    box.appendChild(pill);
  } else {
    box.classList.add("hidden");
    tab.classList.remove("active");
  }
}
function renderDeepResults(q) {
  const box = $("deep-results");
  box.innerHTML = "";

  // "log as-is" lives here now — reflect the current query text
  const asis = $("deep-asis");
  const qt = (q || "").trim();
  if (qt) {
    asis.classList.remove("hidden");
    asis.textContent = "＋ Log “" + qt + "” as-is (unlinked)";
  } else {
    asis.classList.add("hidden");
  }

  const query = (q || "").trim().toLowerCase();
  let pool = CATALOG.slice();
  if (query) pool = pool.filter((c) => c.name.toLowerCase().includes(query));
  if (state.deepFilter) pool = pool.filter((c) => c.type === state.deepFilter);
  pool.sort((a, b) => b.here - a.here || b.books - a.books);

  if (!pool.length) {
    const f = state.deepFilter ? " " + state.deepFilter.toLowerCase() + "s" : "";
    box.innerHTML = "<div class='deep-empty'>No" + f + " tunes match “" + (q || "").trim() + "”.</div>";
    return;
  }

  pool.forEach((c) => {
    const card = document.createElement("div");
    card.className = "deep-card";
    card.innerHTML =
      "<div class='deep-card-head'><span class='deep-name'>" + c.name +
      "</span><span class='deep-type'>" + c.type + "</span></div>" +
      "<div class='deep-staff'>" + dotsSVG(c.name) + "</div>";
    card.onclick = () => {
      $("deep-modal").classList.add("hidden");
      commitTune(mkTune(c.name, c.type, true));
    };
    box.appendChild(card);
  });
}

// ----------------------------- toast ----------------------------------------

let toastTimer = null;
function showToast(msg, undoFn, ms = 4000) {
  const t = $("toast"), action = $("toast-action");
  $("toast-msg").textContent = msg;
  if (undoFn) {
    action.classList.remove("hidden");
    action.onclick = () => { undoFn(); hideToast(); };
  } else {
    action.classList.add("hidden");
  }
  t.classList.remove("hidden");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(hideToast, ms);
}
function hideToast() { $("toast").classList.add("hidden"); }

// ----------------------------- scroll tracking ------------------------------

function scrollCursorIntoView() {
  const active = listEl.querySelector(".seam.active") ||
    listEl.querySelector(".set.open");
  if (active) active.scrollIntoView({ block: "center", behavior: "smooth" });
}

const io = new IntersectionObserver((entries) => {
  state.atBottom = entries[0].isIntersecting;
  updatePill();
}, { root: listEl, threshold: 0.1 });
io.observe($("bottom-sentinel"));

// ----------------------------- presence (faux) ------------------------------

function renderPresence() {
  const box = $("presence");
  box.innerHTML = "";
  // offline: you can't see who else is here, so show only yourself
  const list = state.offline ? state.loggers.filter((l) => l.tag === "you") : state.loggers;
  list.forEach((p) => {
    const d = document.createElement("div");
    d.className = "dot-user" + (p.offline ? " offline" : "");
    d.style.background = p.color;
    d.textContent = p.initials;
    box.appendChild(d);
  });
}

// occasionally show "someone else is typing" to preview multi-user feel
function fauxTyping() {
  if (Math.random() < 0.5 && !state.entryActive) {
    const open = lastSet();
    if (open && !open.closed) {
      const card = listEl.querySelector(".set.open");
      if (card && !card.querySelector(".typing.other")) {
        const t = document.createElement("div");
        t.className = "typing other";
        t.innerHTML = "Sarah is adding a tune <span class='dots'><span>.</span><span>.</span><span>.</span></span>";
        card.appendChild(t);
        setTimeout(() => t.remove(), 2600);
      }
    }
  }
  setTimeout(fauxTyping, 7000);
}

// ----------------------------- simulator (prototype only) -------------------
// Triggers for testing multi-user / audio conditions. Each fires a baseline
// effect (the change actually lands + a brief flash + a toast); we'll layer the
// real presence/attribution visuals on top of these next.

const SIM_COLORS = ["#e0a13a", "#2dd4bf", "#f472b6", "#a3e635", "#60a5fa"];

function flashTune(t) {
  t._new = true;
  render();
  setTimeout(() => { t._new = false; render(); }, 1500);
}

// "following" = you're parked at the live end, so new arrivals should pull you
// along automatically instead of stranding you behind a "Go to end" pill
function endIsFollowing() { return state.atBottom && cursorIsEnd(); }
function scrollEnd() { listEl.scrollTo({ top: listEl.scrollHeight, behavior: "smooth" }); }

// byName = the person (drives color + credit); displayName = attribution label
// (e.g. "Sarah's 🎤" when it came via her audio auto-logger — still her color)
function remoteAddTune(byName, displayName, verb = "logged", conf = null) {
  displayName = displayName || byName;
  const follow = endIsFollowing();
  const cat = CATALOG[Math.floor(Math.random() * CATALOG.length)];
  let set = lastSet();
  if (!set || set.closed) { set = mkSet([], false); set.loggedBy = displayName; state.sets.push(set); }
  const t = mkTune(cat.name, cat.type, true, byName);
  t.byColor = loggerColor(byName);
  t.byLabel = displayName;
  if (conf != null) t.confidence = conf;
  removeReservationByName(byName); // their typing hold resolves into the tune
  insertTuneAt(set, set.tunes.length, t);
  showToast(`${displayName} ${verb} “${cat.name}”`, null, 2200);
  flashTune(t);
  if (follow) scrollEnd();
}

function simEndSet() {
  const set = lastSet();
  if (!set || set.closed) { showToast("No open set to end", null, 1800); return; }
  set.closed = true;
  showToast("Sarah ended the set", null, 2000);
  render();
}

function simMerge() {
  const follow = endIsFollowing();
  const cat = CATALOG[Math.floor(Math.random() * CATALOG.length)];
  let set = lastSet();
  if (!set || set.closed) { set = mkSet([], false); set.loggedBy = "Sarah Nolan"; state.sets.push(set); }
  // you both logged the same tune in the same place → collapses to one entry;
  // the earliest logger (here, Sarah) keeps the credit
  const t = mkTune(cat.name, cat.type, true, "Sarah Nolan");
  t.byColor = loggerColor("Sarah Nolan");
  t.byLabel = "Sarah Nolan";
  t._merge = true;
  insertTuneAt(set, set.tunes.length, t);
  showToast(`You and Sarah logged “${cat.name}” at once — merged, Sarah credited`, null, 3200);
  render();
  if (follow) scrollEnd();
  setTimeout(() => { t._merge = false; render(); }, 1400);
}

function simNewSetRemote() {
  const follow = endIsFollowing();
  const last = lastSet();
  if (last && !last.closed) last.closed = true;
  const cat = CATALOG[Math.floor(Math.random() * CATALOG.length)];
  const set = mkSet([], false);
  set.loggedBy = "Sarah Nolan";
  const t = mkTune(cat.name, cat.type, true, "Sarah Nolan");
  t.byColor = loggerColor("Sarah Nolan");
  t.byLabel = "Sarah Nolan";
  set.tunes.push(t);
  state.sets.push(set);
  showToast("Sarah started a new set with “" + cat.name + "”", null, 2200);
  flashTune(t);
  if (follow) scrollEnd();
}

function simulate(action) {
  if (action === "offline") { toggleOffline(); return; }
  if (action === "clear") {
    state.sets = [];
    state.reservations = [];
    state.cursor = { kind: "end" };
    closeEntry();
    render();
    return;
  }

  // remote events that change the shared log; while YOU are offline these are
  // happening on the server but you don't see them — they queue until reconnect
  const remote = {
    logTune: () => remoteAddTune("Sarah Nolan"),
    newSet: () => simNewSetRemote(),
    endSetRemote: () => simEndSet(),
    audio: () => remoteAddTune("Sarah Nolan", "Sarah's 🎤", "logged", 60 + Math.floor(Math.random() * 4) * 10),
    merge: () => simMerge(),
  };
  if (remote[action]) {
    if (state.offline) {
      state.serverQueue.push(remote[action]);
      showToast("📡 Queued on the server — you're offline", null, 1800);
      render();
      return;
    }
    remote[action]();
    return;
  }

  if (action === "typing") {
    if (!state.offline) simTyping("Sarah");
  } else if (action === "typingMeabh") {
    if (!state.offline) simTyping("Méabh");
  } else if (action === "typingBoth") {
    if (!state.offline) { simTyping("Sarah"); simTyping("Méabh"); }
  } else if (action === "join") {
    const candidate = state.attendance.find(
      (n) => !state.loggers.some((l) => l.name.split(" ")[0] === n));
    if (!candidate) { showToast("Everyone present is already logging", null, 1800); return; }
    state.loggers.push({
      initials: candidate.slice(0, 2).toUpperCase(),
      name: candidate,
      tag: "",
      color: SIM_COLORS[state.loggers.length % SIM_COLORS.length],
    });
    renderPresence();
    showToast(candidate + " started logging", null, 1800);
    render();
  } else if (action === "leave") {
    const idx = state.loggers.map((l) => l.tag).lastIndexOf("");
    if (idx <= 0) { showToast("No one else to remove", null, 1800); return; }
    const gone = state.loggers.splice(idx, 1)[0];
    renderPresence();
    showToast(gone.name + " stopped logging", null, 1800);
    render();
  }
}

// ---- offline / reconnect ----
function countTunes() { return state.sets.reduce((n, s) => n + s.tunes.length, 0); }

function toggleOffline() {
  if (!state.offline) goOffline(); else reconnect();
}
function goOffline() {
  state.offline = true;
  // you can no longer observe anyone else — drop others' presence and any holds
  Object.keys(resvTimers).forEach((k) => clearTimeout(resvTimers[k]));
  state.reservations = [];
  const you = state.loggers.find((l) => l.tag === "you");
  if (you) you.offline = true;
  renderPresence();
  render();
  showToast("📴 You're offline — still logging, will sync on reconnect", null, 2600);
}
function reconnect() {
  const queued = state.serverQueue.slice();
  state.serverQueue = [];
  state.offline = false;
  const you = state.loggers.find((l) => l.tag === "you");
  if (you) you.offline = false;

  // your locally-queued changes are now confirmed synced: deletes apply,
  // inserts/edits clear their pending flag (with a settle flash)
  let mine = 0;
  state.sets.forEach((s) => {
    s.tunes = s.tunes.filter((t) => {
      if (t._pendingDelete) { mine++; return false; }
      return true;
    });
    s.tunes.forEach((t) => {
      if (t._pending) { t._pending = false; t._settle = true; mine++; setTimeout(() => { t._settle = false; render(); }, 1600); }
    });
  });

  // replay what others did on the server while you were away (set is the merge
  // unit; for the prototype these append in arrival order)
  const before = countTunes();
  queued.forEach((fn) => fn());
  const theirs = countTunes() - before;

  renderPresence();
  render();
  showToast(`🌐 Reconnected — ${mine} of your tunes synced` +
    (theirs ? `, ${theirs} added while you were away` : ""), null, 4200);
}

function simTyping(name) {
  const set = lastSet();
  if (!set) return;
  const logger = state.loggers.find((l) => l.name.split(" ")[0] === name);
  const color = logger ? logger.color : "#a855f7";
  const fullName = logger ? logger.name : name;

  let r = state.reservations.find((x) => x.by === fullName);
  if (!r) { r = { id: "resv-" + fullName, by: fullName, name }; state.reservations.push(r); }
  r.color = color;
  r.setId = set.id;
  r.pos = set.tunes.length; // anchored at the live end of the latest set
  render();
  if (endIsFollowing()) scrollEnd();

  // clears only after 10s of no further typing activity
  clearTimeout(resvTimers[r.id]);
  resvTimers[r.id] = setTimeout(() => removeReservation(r.id), 10000);
}

// ----------------------------- wiring ---------------------------------------

fieldEl.addEventListener("focus", () => { if (!state.entryActive) openEntry(); });
fieldEl.addEventListener("input", () => { state.query = fieldEl.value; renderResults(); });
fieldEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    const top = rankResults(state.query)[0];
    if (state.query.trim() && top && top.name.toLowerCase().includes(state.query.trim().toLowerCase())) {
      commitTune(mkTune(top.name, top.type, true));
    } else if (state.query.trim()) {
      commitTune(mkTune(state.query.trim(), "?", false));
    }
  }
});

endBtn.addEventListener("click", endSet);
$("mic").addEventListener("click", toggleMic);
$("mic-pause").addEventListener("click", toggleMicPause);
$("mic-stop").addEventListener("click", stopMic);
pillEl.addEventListener("click", goToEnd);
$("deep-close").addEventListener("click", () => $("deep-modal").classList.add("hidden"));
$("drawer-close").addEventListener("click", closeDrawer);
$("drawer-scrim").addEventListener("click", closeDrawer);
$("deep-field").addEventListener("input", (e) => renderDeepResults(e.target.value));
$("deep-filter-tab").addEventListener("click", () => {
  // toggle the type filter: clear if on, else apply the context set's type
  state.deepFilter = state.deepFilter ? null : contextType();
  renderDeepFilter();
  renderDeepResults($("deep-field").value);
});
$("deep-asis").addEventListener("click", () => {
  const qt = $("deep-field").value.trim();
  if (!qt) return;
  $("deep-modal").classList.add("hidden");
  commitTune(mkTune(qt, "?", false));
});

// tap empty list area to dismiss selection / picker
listEl.addEventListener("click", () => {
  let changed = false;
  if (state.selectedTuneId) { state.selectedTuneId = null; changed = true; }
  if (state.starterPickerSetId) { state.starterPickerSetId = null; changed = true; }
  if (changed) render();
});

// edit <-> read-only view
$("view-toggle").addEventListener("click", () => setMode("view"));
$("edit-toggle").addEventListener("click", () => setMode("edit"));

// expandable session header
$("header-toggle").addEventListener("click", toggleHeader);
$("attend-close").addEventListener("click", closeAttendance);
$("attend-add").addEventListener("input", renderAttendResults);
$("np-add").addEventListener("click", addNewPerson);
$("np-cancel").addEventListener("click", () => $("newperson-modal").classList.add("hidden"));
$("notes-area").addEventListener("input", (e) => { state.notes = e.target.value; });
$("notes-close").addEventListener("click", () => { $("notes-modal").classList.add("hidden"); render(); });

// ----------------------------- boot -----------------------------------------

// hamburger menu toggle
$("hamburger-btn").addEventListener("click", (e) => {
  e.stopPropagation();
  $("sim-dropdown").classList.remove("show");
  $("hamburger-dropdown").classList.toggle("show");
});
$("hamburger-dropdown").addEventListener("click", (e) => e.stopPropagation());

// simulate menu toggle + item handling
$("sim-btn").addEventListener("click", (e) => {
  e.stopPropagation();
  $("hamburger-dropdown").classList.remove("show");
  $("sim-dropdown").classList.toggle("show");
});
$("sim-dropdown").addEventListener("click", (e) => {
  const item = e.target.closest("[data-sim]");
  if (!item) { e.stopPropagation(); return; }
  $("sim-dropdown").classList.remove("show");
  simulate(item.dataset.sim);
});

document.addEventListener("click", () => {
  $("hamburger-dropdown").classList.remove("show");
  $("sim-dropdown").classList.remove("show");
});

state.sets[0].startedBy = "Méabh"; // demo: one set already has a starter
state.sets[1].loggedBy = "Sarah";  // demo: a set logged by someone else
state.sets[1].tunes[1].confidence = 70; // demo: an audio-recognized tune
// stagger demo timestamps so the "logged by · time" reads realistically
(() => {
  let t = Date.now() - 45 * 60 * 1000;
  state.sets.forEach((s) => {
    s.tunes.forEach((tune) => { t += 4 * 60 * 1000; tune.at = t; });
    t += 3 * 60 * 1000;
  });
})();
// Keyboard handling. The trace shows iOS reports the keyboard as a SINGLE
// discrete jump (one visualViewport event ~100ms after focus with the final
// offset), while it *renders* the keyboard slide over ~250ms. So we don't try
// to follow frame-by-frame — instead we CSS-transition transform/height so the
// app glides in sync with the keyboard, and preemptively kick that glide off on
// focus/blur (using the last measured keyboard size) to erase the event lag.
let kbLastOffset = 0, kbLastVh = 0;
function applyKb(off, vh) {
  const phone = $("phone");
  if (!window.visualViewport || window.innerWidth >= 480) {
    phone.style.height = ""; phone.style.transform = ""; return;
  }
  phone.style.height = vh + "px";
  phone.style.transform = "translateY(" + off + "px)";
}
function fitToViewport() {
  const vv = window.visualViewport;
  if (!vv) return;
  if (vv.offsetTop > 0) { kbLastOffset = vv.offsetTop; kbLastVh = vv.height; } // remember keyboard size
  applyKb(vv.offsetTop, vv.height);
}
function onViewportChange() {
  fitToViewport();
  // keep the insertion point in view as the list resizes (avoids a stray pill)
  if (state.entryActive) {
    requestAnimationFrame(() => {
      if (cursorIsEnd()) listEl.scrollTop = listEl.scrollHeight;
      else scrollCursorIntoView();
    });
  }
}
if (window.visualViewport) {
  window.visualViewport.addEventListener("resize", onViewportChange);
  window.visualViewport.addEventListener("scroll", onViewportChange);
}
fitToViewport();

renderPresence();
render();
