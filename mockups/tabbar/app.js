/* 052 Tab-bar IA — prototype logic.
   Hash router (#/home, #/sessions, #/sessions/<path>, #/tunes, #/me, #/me/<section>)
   so the swipe-back gesture works; deeper routes push in from the right and pop back
   out; screens render from one in-memory state; dummy data mirrors the seeded local
   DB. No network. */

(function () {
  "use strict";

  // ---------------------------------------------------------------- data
  const ME = { first: "Ian", last: "Varley", where: "Austin, TX", instruments: ["Fiddle", "Mandolin"], admin: true, tz: "America/Chicago" };

  const SESSIONS = [
    { path: "austin/mueller", name: "Mueller Session", when: "Tuesdays · 7:30pm", where: "Mueller Lake Park, Austin", member: true, tonight: true, live: true, admin: true },
    { path: "austin/downtown", name: "Downtown Session", when: "Thursdays · 8pm", where: "B.D. Riley's, Austin", member: true },
    { path: "boston/celtic", name: "Celtic Session", when: "Sundays · 5pm", where: "The Burren, Somerville", member: false },
    { path: "chicago/trad", name: "Chicago Trad", when: "Wednesdays · 8pm", where: "Chief O'Neill's, Chicago", member: false },
    { path: "sf/sunset", name: "Sunset Session", when: "Mondays · 7pm", where: "The Plough and Stars, SF", member: false },
    { path: "dublin/cobblestone", name: "The Cobblestone", when: "Nightly · 9pm", where: "Smithfield, Dublin", member: false },
    { path: "galway/crane", name: "Crane Bar Session", when: "Fridays · 9:30pm", where: "Sea Road, Galway", member: false },
    { path: "nyc/paddy-reillys", name: "Paddy Reilly's", when: "Thursdays · 9pm", where: "Murray Hill, New York", member: false },
    { path: "seattle/owl", name: "Owl 'n' Thistle", when: "Tuesdays · 8pm", where: "Pioneer Square, Seattle", member: false },
    { path: "portland/tir-na-nog", name: "Tír na nÓg Session", when: "Sundays · 4pm", where: "Portland, OR", member: false },
    { path: "denver/nallens", name: "Nallen's Session", when: "Wednesdays · 7pm", where: "Denver, CO", member: false },
    { path: "philly/plough", name: "Plough & the Stars", when: "Sundays · 5pm", where: "Old City, Philadelphia", member: false },
  ];

  // Today's sessions per prototype mode. `live` = a log is open right now.
  const TODAY = {
    none: [],
    one: [{ path: "austin/mueller", name: "Mueller Session", time: "7:30pm", where: "Mueller Lake Park", live: true, logged: 18, people: 4 }],
    festival: [
      { path: "austin/mueller", name: "Mueller Session", time: "7:30pm", where: "Mueller Lake Park", live: true, logged: 18, people: 4 },
      { path: "austin/fleadh-morning", name: "Fleadh · Morning Session", time: "11am", where: "Scholz Garten, main room", live: false, done: true, logged: 22, people: 9 },
      { path: "austin/fleadh-late", name: "Fleadh · Late Session", time: "11pm", where: "Scholz Garten, back bar", live: false, logged: 0, people: 0 },
    ],
  };

  // My list + a slice of the catalogue. Last field false = NOT in the Mueller repertoire.
  const CATALOG = [
    ["Cooley's", "Reel", "Edor", "know", "|:D2|EBBA B2 EB|B2 AB dBAG|FDAD BDAD|FDAD dAFD|", 3],
    ["The Butterfly", "Slip Jig", "Emin", "know", "|:B2 E G2 E|F3 F2 A|B2 E G2 E|FED F2 A:|", 5],
    ["The Kesh", "Jig", "Gmaj", "learning", "|:G3 GAB|A3 ABd|edd gdd|edB dBA|", 9],
    ["Banish Misfortune", "Jig", "Dmix", "learning", "|:fed cAG|A2d cAG|F2D DED|FEF GFG|", 0, false],
    ["The Wind That Shakes The Barley", "Reel", "Dmaj", null, "|:d2 dA BAFA|ABdA BAFA|d2 dA BAFA|ABde fdd2:|", 6],
    ["Morrison's", "Jig", "Edor", "want", "|:E3 B3|EBE AFD|E3 B3|dcB AFD|", 4],
    ["The Silver Spear", "Reel", "Dmaj", null, "|:d2 fd edfd|AFDF ABdA|d2 fd edfd|AFAB d2:|", 2],
    ["Drowsy Maggie", "Reel", "Edor", null, "|:E2BE dEBE|E2BE AFDF|E2BE dEBE|BABc dAFD:|", 0, false],
    ["The Maid Behind the Bar", "Reel", "Dmaj", "know", "|:AF|D2 FA d2 fd|edfd e2 de|", 7],
    ["Out on the Ocean", "Jig", "Gmaj", "know", "|:G2 GABG|ABA dBA|G2 GABG|ABA ged|", 5],
    ["The Lilting Banshee", "Jig", "Ador", "know", "|:e2A ABA|BAB GBd|e2A ABA|d2B d2e|", 4],
    ["Sligo Maid", "Reel", "Ador", "learning", "|:A2 AB cAce|d2 dB cAGB|", 3],
    ["The Musical Priest", "Reel", "Bmin", "want", "|:fB BA B2 fe|fB BA F2 FA|", 2],
    ["Rolling Waves", "Jig", "Dmaj", null, "|:d2 A FED|ABA AFA|d2 A FED|FAF E2 D|", 3],
    ["The Blarney Pilgrim", "Jig", "Dmix", "know", "|:D2 F FED|DEF G2 A|B2 A GFG|", 6],
    ["Tobin's Favourite", "Jig", "Dmaj", null, "|:A|dcd fdf|ecA GFE|", 1],
    ["The Mason's Apron", "Reel", "Amaj", null, "|:a2 ae fecA|EAcA EAcA|", 2],
    ["The Star of Munster", "Reel", "Ador", "learning", "|:c2 Ac BAGB|ceAc BGGB|", 4],
    ["Cooley's Hornpipe", "Hornpipe", "Dmaj", null, "|:d>e f>d e>d B>A|", 0, false],
    ["The Rights of Man", "Hornpipe", "Emin", "want", "|:GA|B>cB>A G>AB>c|", 2],
    ["Harvest Home", "Hornpipe", "Dmaj", "know", "|:A>G|F>AD>F A>dF>A|", 3],
    ["Off to California", "Hornpipe", "Gmaj", null, "|:d>e|g>fg>a b>ag>e|", 1],
    ["Dennis Murphy's", "Polka", "Dmaj", "know", "|:A2 AB AF|A2 AB de|", 8],
    ["John Ryan's Polka", "Polka", "Dmaj", "know", "|:dd BA|FA de|", 7],
    ["Britches Full of Stitches", "Polka", "Amaj", null, "|:AB|cB cd|ec BA|", 3],
    ["Merrily Kissed the Quaker", "Slide", "Gmaj", null, "|:G3 GAB|A3 ABd|", 2],
    ["The Road to Lisdoonvarna", "Slide", "Edor", "know", "|:E2B B2A|B2c d2A|", 5],
    ["Cooley's Slide", "Slide", "Dmaj", null, "|:d2A FED|", 0, false],
    ["Toss the Feathers", "Reel", "Edor", "learning", "|:E2 BE dEBE|E2 BE AFDF|", 4],
    ["The Congress", "Reel", "Ador", null, "|:eA (3AAA eA (3AAA|", 2],
    ["The Bucks of Oranmore", "Reel", "Dmaj", null, "|:d2 fd edfd|", 3],
    ["Miss McLeod's", "Reel", "Gmaj", "know", "|:G2 GB dBGB|", 6],
    ["Saint Anne's", "Reel", "Dmaj", "know", "|:A2 FA D2 FA|", 5],
    ["The Ships Are Sailing", "Reel", "Emin", null, "|:e2 ef gfed|", 1],
    ["Father Kelly's", "Reel", "Gmaj", "want", "|:dG (3GGG BGdG|", 2],
    ["The Connaughtman's Rambles", "Jig", "Dmaj", "know", "|:FAA dAA|", 5],
    ["Cliffs of Moher", "Jig", "Ador", null, "|:eAA eAA|", 2],
    ["Jerry's Beaver Hat", "Jig", "Dmaj", null, "|:F2D DED|", 1],
    ["The Tenpenny Bit", "Jig", "Ador", "learning", "|:eAA eAA|", 3],
    ["Whelan's", "Jig", "Dmaj", null, "|:AFA d2e|", 0, false],
    ["Garrett Barry's", "Jig", "Dmix", null, "|:d2A F2A|", 2],
    ["Hardiman the Fiddler", "Slip Jig", "Dmaj", null, "|:F2A A2B|", 1],
    ["The Foxhunter's", "Slip Jig", "Gmaj", null, "|:g2e dBA|", 2],
    ["Sí Bheag Sí Mhór", "Waltz", "Dmaj", "know", "|:d3 e|f2 e|", 2],
    ["Inisheer", "Waltz", "Gmaj", "want", "|:d3|B2 G|", 1],
  ];
  const TUNES = CATALOG.map(([name, type, key, status, incipit, plays, mueller], i) => ({
    id: i + 1, name, type, key, status, incipit, plays, onList: !!status, mueller: mueller !== false,
  }));

  const LOGS = (() => {
    const out = [];
    let d = new Date(2026, 8, 16);
    const loggers = ["Ian", "Sarah", "Siobhán", "Seán"];
    for (let i = 0; i < 36; i++) {
      const tunes = 9 + ((i * 7) % 12);
      out.push({ date: new Date(d), tunes, complete: i !== 3 && i !== 11, by: loggers.slice(0, 1 + (i % 3)).join(", "), name: i === 8 ? "Fleadh night" : null });
      d = new Date(d.getTime() - 7 * 86400000);
    }
    return out;
  })();

  const PEOPLE = [
    ["Ian Varley", "Fiddle, mandolin", "admin"], ["Sarah O'Connor", "Fiddle", "regular"], ["Siobhán Walsh", "Flute", "regular"],
    ["Seán O'Brien", "Banjo", "regular"], ["Maeve Brennan", "Button accordion", "regular"], ["Declan Byrne", "Uilleann pipes", "regular"],
    ["Aoife Kelly", "Concertina", "regular"], ["Tomás Ó Murchú", "Bouzouki", "regular"], ["Niamh Ryan", "Whistle", "regular"],
    ["Cormac Doyle", "Guitar", "regular"], ["Róisín Fitzgerald", "Harp", "visitor"], ["Padraig Nolan", "Bodhrán", "regular"],
    ["Ella Stone", "Fiddle", "visitor"], ["Mark Delaney", "Flute", "visitor"], ["Ciara Hughes", "Fiddle", "regular"],
    ["Liam Quinn", "Banjo", "visitor"], ["Orla Kavanagh", "Piano accordion", "regular"], ["Danny Boyle", "Guitar", "visitor"],
    ["Fionnuala Burke", "Whistle", "regular"], ["Eoin McCarthy", "Fiddle", "regular"],
  ].map(([n, inst, role]) => ({ name: n, inst, role, ini: n.split(" ").map((w) => w[0]).join("").slice(0, 2) }));

  const state = {
    todayMode: "one", // none | one | festival — cycled by the Prototype tag
    tuneFilter: "all",
    tuneQuery: "",
    sessionsFilter: "mine",
    sessionsQuery: "",
    sessionTab: "tunes",
    sessionTuneQuery: "",
    sessionTuneType: "all",
    logsQuery: "",
    logsFilter: "all",
    peopleQuery: "",
    peopleFilter: "all",
    openFilter: null, // which filter panel is expanded ("tunes" | "logs" | "people")
    tuneSort: "name",
  };

  // ---------------------------------------------------------------- helpers
  const $ = (sel, root) => (root || document).querySelector(sel);
  const el = (tag, cls, html) => { const n = document.createElement(tag); if (cls) n.className = cls; if (html != null) n.innerHTML = html; return n; };
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const statusLabel = { know: "Know it", learning: "Learning", want: "Want to learn" };
  const chip = (cls, text) => `<span class="chip ${cls}">${esc(text)}</span>`;
  const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
  const DOWS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  const dateBlock = (d, today) => `<span class="date-block${today ? " today" : ""}"><span class="dow">${DOWS[d.getDay()]}</span><span class="dom">${d.getDate()}</span></span>`;
  const abcKey = (s) => s.replace(/[\s|:',()]/g, "").toLowerCase();
  const looksAbc = (q) => /^[a-g0-9\s|:',()]+$/i.test(q) && abcKey(q).length >= 3;
  function matchTune(t, q) {
    if (!q) return true;
    const ql = q.toLowerCase();
    return t.name.toLowerCase().includes(ql) || (looksAbc(q) && abcKey(t.incipit).includes(abcKey(q)));
  }

  function row({ lead = "", primary, secondary = "", trail = "", onClick, chevron = true }) {
    const b = el("button", "row", `<span class="lead">${lead}</span><span class="body"><span class="primary">${esc(primary)}</span>${secondary ? `<span class="secondary">${secondary}</span>` : ""}</span><span class="trail">${trail}${chevron ? '<span class="chev">›</span>' : ""}</span>`);
    b.type = "button";
    if (onClick) b.addEventListener("click", onClick);
    return b;
  }
  const ICON = {
    cal: `<svg viewBox="0 0 24 24"><rect x="3.5" y="5" width="17" height="15" rx="2.5"/><path d="M3.5 10h17M8 3v4M16 3v4"/></svg>`,
    notes: `<svg viewBox="0 0 24 24"><path d="M9 18.5V6l10-2v12"/><circle cx="6.5" cy="18.5" r="2.5"/><circle cx="16.5" cy="16" r="2.5"/></svg>`,
    pencil: `<svg viewBox="0 0 24 24"><path d="M4 20h4l10.5-10.5a2.1 2.1 0 0 0-3-3L5 17v3z"/><path d="m13.5 6.5 3 3"/></svg>`,
    filter: `<svg viewBox="0 0 24 24"><path d="M4 6h16M7 12h10M10 18h4"/></svg>`,
    search: `<svg viewBox="0 0 24 24"><circle cx="10.5" cy="10.5" r="6.5"/><path d="m20 20-4.8-4.8"/></svg>`,
    sort: `<svg viewBox="0 0 24 24"><path d="M4 7h10M4 12h6M4 17h3"/><path d="M17.5 7.5v9M14.5 13.5l3 3 3-3"/></svg>`,
  };
  function section(title, seeAll, icon) {
    const s = el("section", "section");
    if (title) {
      const h = el("div", "section-head", `<h2>${icon ? `<span class="sec-icon">${ICON[icon]}</span>` : ""}${esc(title)}</h2>`);
      if (seeAll) { const a = el("a", "see-all", "See all"); a.href = seeAll; h.appendChild(a); }
      s.appendChild(h);
    }
    return s;
  }
  function seg(options, value, onSelect) {
    const s = el("div", "seg");
    options.forEach(([v, label]) => {
      const b = el("button", v === value ? "active" : "", esc(label));
      b.type = "button";
      b.addEventListener("click", () => onSelect(v));
      s.appendChild(b);
    });
    return s;
  }
  function tabs(options, value, onSelect) {
    const t = el("div", "tabs");
    options.forEach(([v, label, count]) => {
      const b = el("button", v === value ? "active" : "", `${esc(label)}${count != null ? ` <span class="cnt num">${count}</span>` : ""}`);
      b.type = "button";
      b.addEventListener("click", () => onSelect(v));
      t.appendChild(b);
    });
    return t;
  }
  // A search field + optional filter / add buttons. The filter panel expands
  // DOWNWARD from this line rather than rising from the bottom of the screen: it
  // refines the list directly below it, so it belongs there, attached to its button
  // (a notch points back at it). Opening and closing is a class toggle on the live
  // nodes, not a re-render, so both directions animate.
  function toolbar({ placeholder, bind, filter, sort, onAdd }) {
    const wrap = el("div", "toolbar-wrap");
    const t = el("div", "toolbar");
    const sf = el("div", "search", `<span class="icon">${ICON.search}</span><input placeholder="${esc(placeholder)}" aria-label="${esc(placeholder)}" autocomplete="off">`);
    const input = $("input", sf);
    input.value = state[bind];
    input.addEventListener("input", () => { state[bind] = input.value; renderCurrent({ keepFocus: bind }); });
    t.appendChild(sf);

    let panel = null;
    if (filter) {
      const active = filter.groups.filter(([, , key]) => state[key] !== "all");
      const isOpen = state.openFilter === filter.key;
      const f = el("button", "tool-btn" + (active.length ? " on" : "") + (isOpen ? " open" : ""), ICON.filter + (active.length ? '<span class="badge"></span>' : ""));
      f.type = "button";
      f.setAttribute("aria-label", "Filter");
      f.setAttribute("aria-expanded", String(isOpen));
      f.addEventListener("click", () => {
        const open = state.openFilter !== filter.key;
        state.openFilter = open ? filter.key : null;
        panel.classList.toggle("open", open);
        f.classList.toggle("open", open);
        f.setAttribute("aria-expanded", String(open));
      });
      t.appendChild(f);
    }
    if (sort) {
      const b = el("button", "tool-btn" + (state[sort.key] !== sort.def ? " on" : ""), ICON.sort);
      b.type = "button";
      b.setAttribute("aria-label", "Sort");
      b.addEventListener("click", (e) => {
        e.stopPropagation();
        openMenu(b, sort.options, state[sort.key], (v) => { state[sort.key] = v; renderCurrent(); });
      });
      t.appendChild(b);
    }
    if (onAdd) {
      const a = el("button", "tool-btn add", "+");
      a.type = "button";
      a.setAttribute("aria-label", "Add");
      a.addEventListener("click", onAdd);
      t.appendChild(a);
    }
    wrap.appendChild(t);

    if (filter) {
      panel = el("div", "filter-panel" + (state.openFilter === filter.key ? " open" : ""));
      // the notch sits under the filter button: last control, or second-to-last when
      // an add button follows it
      const after = (sort ? 1 : 0) + (onAdd ? 1 : 0);
      panel.style.setProperty("--notch-right", `${21 + after * 50}px`);
      const inner = el("div", "inner");
      filter.groups.forEach(([label, options, key]) => {
        const g = el("div", "filter-group");
        g.appendChild(el("div", "eyebrow", label));
        g.appendChild(seg(options, state[key], (v) => { state[key] = v; renderCurrent(); }));
        inner.appendChild(g);
      });
      const active = filter.groups.filter(([, , key]) => state[key] !== "all");
      if (active.length) {
        const clear = el("button", "btn quiet clear", "Clear filters");
        clear.type = "button";
        clear.addEventListener("click", () => { filter.groups.forEach(([, , key]) => { state[key] = "all"; }); renderCurrent(); });
        inner.appendChild(clear);
      }
      panel.appendChild(inner);
      wrap.appendChild(panel);
    }
    return wrap;
  }

  // An anchored pull-down from a bar button — the iOS idiom for a bar-button menu,
  // and the same principle as the filter panel: it opens where you pressed.
  let openMenuEl = null;
  function closeMenu() {
    if (openMenuEl) { openMenuEl.remove(); openMenuEl = null; }
  }
  function openMenu(anchor, options, value, onSelect) {
    closeMenu();
    const phone = $("#phone");
    const m = el("div", "menu");
    options.forEach(([v, label]) => {
      const b = el("button", "menu-item" + (v === value ? " on" : ""), `<span>${esc(label)}</span>${v === value ? '<span class="tick">✓</span>' : ""}`);
      b.type = "button";
      b.addEventListener("click", (e) => { e.stopPropagation(); closeMenu(); onSelect(v); });
      m.appendChild(b);
    });
    phone.appendChild(m);
    const a = anchor.getBoundingClientRect();
    const p = phone.getBoundingClientRect();
    m.style.top = `${a.bottom - p.top + 6}px`;
    m.style.right = `${Math.max(8, p.right - a.right)}px`;
    openMenuEl = m;
    requestAnimationFrame(() => m.classList.add("open"));
    setTimeout(() => document.addEventListener("pointerdown", function once(ev) {
      if (m.contains(ev.target)) { document.addEventListener("pointerdown", once, { once: true }); return; }
      closeMenu();
    }, { once: true }), 0);
  }

  function tuneRow(t, opts = {}) {
    const trail = t.status ? chip(t.status, statusLabel[t.status]) : "";
    const secondary = `${esc(t.type)} · ${esc(t.key)}${opts.plays && t.plays ? ` · played ${t.plays}×` : ""}`;
    return row({ primary: t.name, secondary, trail, chevron: false, onClick: () => openTuneSheet(t, opts) });
  }

  // ---------------------------------------------------------------- toast (once)
  let toastTimer;
  function toast(msg) {
    const t = $("#toast");
    t.textContent = msg;
    t.classList.add("on");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => t.classList.remove("on"), 2200);
  }

  // ---------------------------------------------------------------- sheets
  function openSheet({ title, back, done, doneLabel = "Done", body, footer, tall = false, bare = false }) {
    const sheet = $("#sheet");
    sheet.classList.toggle("tall", tall);
    const head = $("#sheet-head");
    head.innerHTML = "";
    head.hidden = bare;
    if (!bare) {
      const cancel = el("button", "bar-btn", back ? `‹ ${esc(back)}` : "Cancel");
      cancel.type = "button";
      cancel.addEventListener("click", closeSheet);
      head.appendChild(cancel);
      head.appendChild(el("div", "title", esc(title)));
      const right = el("div", "right");
      if (done) {
        const d = el("button", "bar-btn strong", esc(doneLabel));
        d.type = "button";
        d.addEventListener("click", () => { done(); closeSheet(); });
        right.appendChild(d);
      }
      head.appendChild(right);
    }
    const b = $("#sheet-body");
    b.innerHTML = "";
    body.forEach((n) => b.appendChild(n));
    const f = $("#sheet-foot");
    f.innerHTML = "";
    f.hidden = !footer;
    if (footer) footer.forEach((n) => f.appendChild(n));
    sheet.classList.add("open");
    $("#scrim").classList.add("open");
    b.scrollTop = 0;
  }
  function closeSheet() {
    $("#sheet").classList.remove("open");
    $("#scrim").classList.remove("open");
  }

  // The tune sheet mirrors today's drawer (spec 037): type pill + title + ×, notation
  // first, then My List / Details / History / Played With.
  function openTuneSheet(t, opts = {}) {
    let pane = "my-list";
    const head = el("div", "td-head", `<span class="chip dim type-pill">${esc(t.type)}</span><div class="td-title"><h2>${esc(t.name)}</h2>${t.id === 3 ? '<div class="td-aka">aka Kincora Jig</div>' : ""}</div>`);
    const x = el("button", "kit-x", "×");
    x.type = "button"; x.setAttribute("aria-label", "Close");
    x.addEventListener("click", closeSheet);
    head.appendChild(x);

    const body = [head];
    if (state.todayMode !== "none") {
      const live = el("button", "log-live", `<span class="dot"></span>Log to Mueller Session`);
      live.type = "button";
      live.addEventListener("click", () => { closeSheet(); toast("Logged to Mueller Session"); });
      body.push(live);
    }
    const notation = el("div", "notation", `<div class="staff mono"><span class="k">K:${esc(t.key)}</span>  ${esc(t.incipit)}</div><div class="notation-foot"><span class="hint">${esc(t.key)} · setting 1 of 3</span><button type="button" class="btn quiet">abc</button></div>`);
    body.push(notation);

    const paneHost = el("div", "td-pane");
    const ids = ["my-list", "details", "history", "played-with"];
    const tabRow = tabs([["my-list", "My List"], ["details", "Details"], ["history", "History"], ["played-with", "Played With"]], pane, (v) => { pane = v; [...tabRow.children].forEach((b, i) => b.classList.toggle("active", ids[i] === v)); renderPane(); });
    tabRow.classList.add("td-tabs");
    body.push(tabRow, paneHost);

    function renderPane() {
      paneHost.innerHTML = "";
      if (pane === "my-list") {
        if (!t.onList) {
          const nl = el("div", "not-on-list", `<span>This tune is not on your list</span>`);
          const add = el("button", "btn primary", "Add");
          add.type = "button";
          add.addEventListener("click", () => { t.status = "want"; t.onList = true; renderPane(); if (opts.fromCatalog) toast("Added to My Tunes"); renderCurrent(); });
          nl.appendChild(add);
          paneHost.appendChild(nl);
          return;
        }
        const status = el("div", "section");
        status.appendChild(el("div", "eyebrow", "This tune is on your list as"));
        const saved = el("div", "saved");
        status.appendChild(seg([["want", "Want to learn"], ["learning", "Learning"], ["know", "Know it"]], t.status, (v) => {
          t.status = t.status === v ? null : v;
          t.onList = !!t.status;
          saved.textContent = t.status ? "✓ Saved" : "Removed from your list";
          saved.classList.add("on");
          setTimeout(() => saved.classList.remove("on"), 1500);
          renderPane();
          renderCurrent();
        }));
        status.appendChild(saved);
        paneHost.appendChild(status);
        paneHost.appendChild(el("div", "field", `<label>Notes</label><textarea rows="2" placeholder="Where you learned it, who plays it, the set it lives in…">${t.id === 3 ? "Goes into Morrison's at Mueller." : ""}</textarea>`));
        paneHost.appendChild(el("div", "field", `<label>Tags</label><div class="tagrow">${t.id === 3 ? chip("dim", "session set") + chip("dim", "learn next") : ""}<button type="button" class="btn quiet">+ tag</button></div>`));
        paneHost.appendChild(el("dl", "kv", `<dt>Times heard</dt><dd class="num">${t.plays}</dd>`));
      } else if (pane === "details") {
        paneHost.appendChild(el("dl", "kv", `<dt>Type · key</dt><dd>${esc(t.type)} · ${esc(t.key)}</dd><dt>Tunebooks on thesession.org</dt><dd class="num">1,350</dd><dt>Sessions that play it</dt><dd class="num">${t.mueller ? 2 : 0}</dd><dt>Played at your sessions</dt><dd class="num">${t.plays}×</dd><dt>thesession.org</dt><dd><a href="#">tune #${t.id}</a></dd>`));
      } else if (pane === "history") {
        const l = el("div", "list");
        if (!t.plays) l.appendChild(el("div", "empty", "Not yet played at your sessions."));
        LOGS.slice(0, t.plays).forEach((lg) => l.appendChild(row({ lead: dateBlock(lg.date), primary: "Mueller Session", secondary: `with ${lg.by}` })));
        paneHost.appendChild(l);
      } else {
        const l = el("div", "list");
        TUNES.filter((x) => x.mueller && x.id !== t.id).slice(0, 5).forEach((x, i) => l.appendChild(row({ primary: x.name, secondary: `${esc(x.type)} · ${i < 2 ? "before" : "after"} it, ${3 - (i % 3)}×`, chevron: false, onClick: () => openTuneSheet(x, opts) })));
        paneHost.appendChild(l);
      }
    }
    renderPane();
    openSheet({ title: "", body, bare: true, tall: true });
  }

  function openAddSessionSheet() {
    const f1 = el("div", "field", `<label for="add-url">thesession.org session link</label><input id="add-url" placeholder="https://thesession.org/sessions/…" inputmode="url">`);
    const or = el("div", "note", "Or search thesession.org by place — the details, recurrence and address come across so you only confirm them.");
    const f2 = el("div", "field", `<label for="add-q">Search</label><input id="add-q" placeholder="Town, pub, or session name">`);
    openSheet({ title: "Add a session", done: () => {}, doneLabel: "Next", body: [f1, or, f2] });
  }

  function openAddTuneSheet(sessionName) {
    const sf = el("div", "search", `<span class="icon">${ICON.search}</span><input placeholder="Name, or notes like EBBA B2" autocomplete="off">`);
    const results = el("div", "list");
    const input = $("input", sf);
    const render = () => {
      results.innerHTML = "";
      const q = input.value.trim();
      if (!q) { results.appendChild(el("div", "empty", "Search the catalogue, or paste a thesession.org link.")); return; }
      const hits = TUNES.filter((t) => matchTune(t, q));
      if (!hits.length) { results.appendChild(el("div", "empty", "Nothing local. Search thesession.org →")); return; }
      hits.slice(0, 12).forEach((t) => results.appendChild(row({ primary: t.name, secondary: `${esc(t.type)} · ${esc(t.key)}`, trail: t.mueller ? chip("dim", "Already in") : "", chevron: false, onClick: () => { t.mueller = true; closeSheet(); renderCurrent(); } })));
    };
    input.addEventListener("input", render);
    render();
    openSheet({ title: `Add to ${sessionName}`, body: [sf, results] });
    setTimeout(() => input.focus(), 250);
  }

  // ---------------------------------------------------------------- screens
  function screenHome() {
    const s = el("div", "screen");
    const today = TODAY[state.todayMode];
    if (today.length) {
      const wrap = el("div", "today");
      const strip = el("div", "today-strip" + (today.length > 1 ? " multi" : ""));
      today.forEach((t) => {
        const status = t.live ? chip("live", "Live now") : t.done ? chip("dim", "Finished") : chip("tonight", `Starts ${t.time}`);
        const sub = t.live ? `${t.time} · ${esc(t.where)} · ${t.people} people here` : `${t.time} · ${esc(t.where)}`;
        const tally = t.logged ? `<div class="tally num">${t.logged} tunes logged${t.live ? " so far" : ""}</div>` : `<div class="tally muted">No tunes logged yet</div>`;
        const card = el("button", "card hero today-card", `<div class="hero-top"><div class="eyebrow">Today</div>${status}</div><div class="card-title">${esc(t.name)}</div><div class="card-sub">${sub}</div>${tally}`);
        card.type = "button";
        const openLog = () => alertNote(`Opens ${t.live ? "the live log" : t.done ? "the finished log" : "a new log"} for ${t.name} — the live screen (spec 021/024), read-only if you're only viewing.`);
        card.addEventListener("click", openLog);
        const acts = el("div", "card-actions");
        const view = el("button", "btn primary", "View");
        view.type = "button";
        view.addEventListener("click", (e) => { e.stopPropagation(); openLog(); });
        acts.appendChild(view);
        card.appendChild(acts);
        strip.appendChild(card);
      });
      wrap.appendChild(strip);
      if (today.length > 1) {
        const dots = el("div", "dots", today.map((_, i) => `<span class="${i === 0 ? "on" : ""}"></span>`).join(""));
        wrap.appendChild(dots);
        strip.addEventListener("scroll", () => {
          const i = Math.round(strip.scrollLeft / (strip.firstChild.offsetWidth + 10));
          [...dots.children].forEach((d, j) => d.classList.toggle("on", j === i));
        }, { passive: true });
      }
      s.appendChild(wrap);
    }

    const week = section("This week", null, "cal");
    const list = el("div", "list");
    today.forEach((t) => list.appendChild(row({ lead: dateBlock(new Date(2026, 8, 22), true), primary: t.name, secondary: `${t.time} · ${t.done ? "you were there" : "you're going"}`, trail: t.live ? chip("live", "Live") : chip("tonight", "Today"), onClick: () => go("#/sessions/" + (SESSIONS.find((x) => x.path === t.path) ? t.path : "austin/mueller")) })));
    list.appendChild(row({ lead: dateBlock(new Date(2026, 8, 24)), primary: "Downtown Session", secondary: "8pm · B.D. Riley's", onClick: () => go("#/sessions/austin/downtown") }));
    week.appendChild(list);
    s.appendChild(week);

    const learn = section("Learning", "#/tunes", "notes");
    const learning = TUNES.filter((t) => t.status === "learning").length;
    const want = TUNES.filter((t) => t.status === "want").length;
    const l3 = el("div", "list");
    l3.appendChild(row({ primary: `${learning} learning · ${want} to learn`, secondary: "Your tune list", onClick: () => go("#/tunes") }));
    const sug = TUNES.find((t) => t.name.startsWith("The Wind"));
    l3.appendChild(row({ primary: `Suggested: ${sug.name}`, secondary: `Reel · played ${sug.plays}× at Mueller, not on your list yet`, trail: sug.onList ? chip(sug.status, statusLabel[sug.status]) : '<span class="btn quiet" style="min-height:0">Add</span>', chevron: false, onClick: () => openTuneSheet(sug, { fromCatalog: true }) }));
    learn.appendChild(l3);
    s.appendChild(learn);

    const cont = section("Pick up where you left off", null, "pencil");
    const l2 = el("div", "list");
    l2.appendChild(row({ primary: "Finish logging Mueller · Sep 16", secondary: "14 tunes · edited 2 hours ago · not marked complete", onClick: () => alertNote("Opens that night's live logger.") }));
    l2.appendChild(row({ primary: "Place tunes on Mueller Night recording", secondary: "4 of 11 tunes placed", onClick: () => alertNote("Opens the segmenter — admin/web-only in the app (SFSafariViewController with the web-session handoff).") }));
    cont.appendChild(l2);
    s.appendChild(cont);
    return s;
  }

  function screenSessions() {
    const s = el("div", "screen");
    s.appendChild(el("h1", "large-title", "Sessions"));
    s.appendChild(seg([["mine", "Mine"], ["all", "All sessions"]], state.sessionsFilter, (v) => { state.sessionsFilter = v; renderCurrent(); }));
    if (state.sessionsFilter === "all") s.appendChild(toolbar({ placeholder: "Search by name, town, or pub", bind: "sessionsQuery" }));
    const list = el("div", "list");
    const q = state.sessionsQuery.trim().toLowerCase();
    const shown = SESSIONS.filter((x) => (state.sessionsFilter === "all" || x.member) && (!q || state.sessionsFilter !== "all" || `${x.name} ${x.where}`.toLowerCase().includes(q)));
    shown.forEach((x) => {
      const trail = x.live ? chip("live", "Live") : x.tonight ? chip("tonight", "Today") : "";
      list.appendChild(row({ primary: x.name, secondary: `${x.when} · ${x.where}`, trail, onClick: () => go("#/sessions/" + x.path) }));
    });
    if (!shown.length) list.appendChild(el("div", "empty", "No sessions match."));
    s.appendChild(list);
    return s;
  }

  function screenSession(path) {
    const x = SESSIONS.find((v) => v.path === path) || SESSIONS[0];
    const s = el("div", "screen");
    const hero = el("div", "session-hero");
    hero.appendChild(el("h1", "large-title", esc(x.name)));
    hero.appendChild(el("div", "when", `${esc(x.when)}${x.tonight ? " · " + chip("tonight", "Today") : ""}`));
    hero.appendChild(el("div", "where", esc(x.where)));
    const acts = el("div", "card-actions");
    if (x.member) {
      const b = el("button", "btn primary", x.live ? "Log tonight" : "Log a night");
      b.type = "button";
      b.addEventListener("click", () => alertNote("Opens the live logger for this session's instance (creates tonight's if needed)."));
      acts.appendChild(b);
      const r = el("button", "btn", x.admin ? "Admin" : "Member");
      r.type = "button";
      r.addEventListener("click", () => openSheet({ title: "Your role", body: [el("div", "note", `You're ${x.admin ? "an <strong>admin</strong>" : "a <strong>member</strong>"} of this session. Leaving keeps your logs; you'll stop seeing it on Home.`)], footer: [Object.assign(el("button", "btn danger block", "Leave session"), { type: "button" })] }));
      acts.appendChild(r);
    } else {
      const j = el("button", "btn primary", "Join this session");
      j.type = "button";
      j.addEventListener("click", () => { x.member = true; renderCurrent(); });
      acts.appendChild(j);
    }
    hero.appendChild(acts);
    s.appendChild(hero);

    const repertoire = TUNES.filter((t) => t.mueller);
    s.appendChild(tabs([["tunes", "Tunes", repertoire.length], ["logs", "Logs", LOGS.length], ["people", "People", PEOPLE.length]], state.sessionTab, (v) => { state.sessionTab = v; renderCurrent(); }));

    if (state.sessionTab === "tunes") {
      s.appendChild(toolbar({
        placeholder: "Filter this session's tunes", bind: "sessionTuneQuery",
        filter: { key: "tunes", groups: [["Tune type", [["all", "All"], ["Reel", "Reels"], ["Jig", "Jigs"], ["Hornpipe", "Hornpipes"], ["Polka", "Polkas"]], "sessionTuneType"]] },
        onAdd: () => openAddTuneSheet(x.name),
      }));
      const list = el("div", "list");
      const shown = repertoire.filter((t) => matchTune(t, state.sessionTuneQuery) && (state.sessionTuneType === "all" || t.type === state.sessionTuneType)).sort((a, b) => b.plays - a.plays || a.name.localeCompare(b.name));
      shown.forEach((t) => list.appendChild(tuneRow(t, { inSession: true, plays: true })));
      if (!shown.length) list.appendChild(el("div", "empty", "No tunes match."));
      s.appendChild(list);
    } else if (state.sessionTab === "logs") {
      s.appendChild(toolbar({
        placeholder: "Search logs by date, tune, or who logged", bind: "logsQuery",
        filter: { key: "logs", groups: [["Show", [["all", "All"], ["incomplete", "Not complete"], ["2026", "2026"], ["2025", "2025"]], "logsFilter"]] },
      }));
      const list = el("div", "list");
      const q = state.logsQuery.trim().toLowerCase();
      const shown = LOGS.filter((lg) => {
        if (state.logsFilter === "incomplete" && lg.complete) return false;
        if (/^\d{4}$/.test(state.logsFilter) && String(lg.date.getFullYear()) !== state.logsFilter) return false;
        if (!q) return true;
        return `${MONTHS[lg.date.getMonth()]} ${lg.date.getDate()} ${lg.date.getFullYear()} ${lg.by} ${lg.name || ""}`.toLowerCase().includes(q);
      });
      let lastYear = null;
      shown.forEach((lg) => {
        const y = lg.date.getFullYear();
        if (y !== lastYear && (lastYear !== null || y !== 2026)) list.appendChild(el("div", "list-divider", `${y}`));
        lastYear = y;
        list.appendChild(row({
          lead: dateBlock(lg.date),
          primary: lg.name || `${MONTHS[lg.date.getMonth()]} ${lg.date.getDate()}`,
          secondary: `${lg.tunes} tunes · ${lg.complete ? "complete" : "not marked complete"} · ${lg.by}`,
          trail: lg.complete ? "" : chip("learning", "Open"),
          onClick: () => alertNote("Opens that night read-only (the live screen in view mode)."),
        }));
      });
      if (!shown.length) list.appendChild(el("div", "empty", "No logs match."));
      s.appendChild(list);
      const add = el("button", "btn block", "＋ Add a past night");
      add.type = "button";
      add.addEventListener("click", () => openSheet({ title: "Add a night", done: () => {}, body: [el("div", "field", `<label for="ni-date">Date</label><input id="ni-date" type="date" value="2026-09-14">`), el("div", "note", "Suggested from the session's recurrence: the Tuesday you haven't logged.")] }));
      s.appendChild(add);
    } else {
      s.appendChild(toolbar({
        placeholder: "Search people or instruments", bind: "peopleQuery",
        filter: { key: "people", groups: [["Show", [["all", "Everyone"], ["regular", "Regulars"], ["visitor", "Visitors"], ["admin", "Admins"]], "peopleFilter"]] },
      }));
      const list = el("div", "list");
      const q = state.peopleQuery.trim().toLowerCase();
      const shown = PEOPLE.filter((p) => (state.peopleFilter === "all" || p.role === state.peopleFilter) && (!q || `${p.name} ${p.inst}`.toLowerCase().includes(q)));
      shown.forEach((p) => list.appendChild(row({ lead: `<span class="avatar sm">${p.ini}</span>`, primary: p.name, secondary: `${p.inst} · ${p.role}`, trail: p.role === "admin" ? chip("dim", "Admin") : "" })));
      if (!shown.length) list.appendChild(el("div", "empty", "Nobody matches."));
      s.appendChild(list);
    }
    return s;
  }

  function screenTunes() {
    const s = el("div", "screen");
    s.appendChild(el("h1", "large-title", "Tunes"));
    s.appendChild(toolbar({
      placeholder: "Find a tune — name, or notes like EBBA B2", bind: "tuneQuery",
      sort: { key: "tuneSort", def: "name", options: [["name", "Name"], ["type", "Tune type"], ["recent", "Recently played"]] },
    }));
    s.appendChild(seg([["all", "All"], ["know", "Know"], ["learning", "Learning"], ["want", "Want"]], state.tuneFilter, (v) => { state.tuneFilter = v; renderCurrent(); }));
    const q = state.tuneQuery.trim();
    const byName = (a, b) => a.name.localeCompare(b.name);
    const SORTS = {
      name: byName,
      type: (a, b) => a.type.localeCompare(b.type) || byName(a, b),
      recent: (a, b) => b.plays - a.plays || byName(a, b),
    };
    const list = el("div", "list");
    const mine = TUNES.filter((t) => t.onList && (state.tuneFilter === "all" || t.status === state.tuneFilter) && matchTune(t, q)).sort(SORTS[state.tuneSort]);
    mine.forEach((t) => list.appendChild(tuneRow(t)));
    if (!mine.length) list.appendChild(el("div", "empty", q ? "None of your tunes match." : "Nothing here yet — search above to find a tune and add it."));
    s.appendChild(list);
    // On "All", a search also reaches the catalogue, below a divider — the list you
    // were looking at stays put; more appears under it.
    if (q && state.tuneFilter === "all") {
      const others = TUNES.filter((t) => !t.onList && matchTune(t, q)).sort(byName);
      if (others.length) {
        s.appendChild(el("div", "divider", `Not on your list${looksAbc(q) ? " · notation match" : ""}`));
        const l2 = el("div", "list");
        others.forEach((t) => l2.appendChild(row({ primary: t.name, secondary: `${esc(t.type)} · ${esc(t.key)}${t.mueller ? " · Mueller" : ""}`, chevron: false, onClick: () => openTuneSheet(t, { fromCatalog: true }) })));
        s.appendChild(l2);
      }
      s.appendChild(el("p", "note", "Nothing else? <a href='#'>Search thesession.org</a>"));
    }
    return s;
  }

  function screenMe() {
    const s = el("div", "screen");
    const p = el("div", "profile", `<div class="avatar">IV</div><div class="who"><div class="n">${esc(ME.first)} ${esc(ME.last)}</div><div class="w">${esc(ME.where)} · ${esc(ME.instruments.join(", "))}</div></div>`);
    s.appendChild(p);
    const stats = el("div", "stats", `<div class="stat"><div class="n num">${TUNES.filter((t) => t.status === "know").length}</div><div class="l">tunes known</div></div><div class="stat"><div class="n num">23</div><div class="l">nights this year</div></div><div class="stat"><div class="n num">312</div><div class="l">tunes logged</div></div>`);
    s.appendChild(stats);

    const sess = section("My sessions", "#/sessions");
    const l1 = el("div", "list");
    SESSIONS.filter((x) => x.member).forEach((x) => l1.appendChild(row({ primary: x.name, secondary: x.when, trail: chip("dim", x.admin ? "Admin" : "Member"), onClick: () => go("#/sessions/" + x.path) })));
    sess.appendChild(l1);
    s.appendChild(sess);

    const att = section("Attended", "#/me/attended");
    const l2 = el("div", "list");
    LOGS.slice(0, 3).forEach((lg) => l2.appendChild(row({ primary: "Mueller Session", secondary: `${MONTHS[lg.date.getMonth()].slice(0, 3)} ${lg.date.getDate()} · ${lg.tunes} tunes` })));
    att.appendChild(l2);
    s.appendChild(att);

    const lg = section("Logged by me", "#/me/logged");
    const l3 = el("div", "list");
    [["The Kesh", "Sep 16"], ["Cooley's", "Sep 16"], ["The Butterfly", "Sep 4"]].forEach(([n, d]) => l3.appendChild(row({ primary: n, secondary: `Mueller Session · ${d}` })));
    lg.appendChild(l3);
    s.appendChild(lg);

    const set = section("Settings");
    const l4 = el("div", "list");
    l4.appendChild(row({ primary: "Profile", secondary: "Name, location, instruments" }));
    l4.appendChild(row({ primary: "Time zone", secondary: "Central (Chicago)" }));
    l4.appendChild(row({ primary: "Password", secondary: "Set" }));
    l4.appendChild(row({ primary: "Update emails", secondary: "On" }));
    l4.appendChild(row({ primary: "Login activity", secondary: "3 devices" }));
    set.appendChild(l4);
    s.appendChild(set);

    const more = section("");
    const l5 = el("div", "list");
    l5.appendChild(row({ primary: "Help", onClick: () => alertNote("Help opens the web (help pages stay Jinja) in an in-app browser.") }));
    if (ME.admin) l5.appendChild(row({ primary: "Admin", secondary: "Opens the web, signed in", onClick: () => alertNote("POST /api/auth/web-session mints a one-time link; SFSafariViewController opens /admin already signed in.") }));
    l5.appendChild(row({ primary: "Share ceol.io", onClick: () => { if (navigator.share) navigator.share({ title: "ceol.io", url: "https://ceol.io" }).catch(() => {}); else alertNote("On a phone this is the system share sheet."); } }));
    more.appendChild(l5);
    s.appendChild(more);

    const out = el("button", "btn danger block", "Log out");
    out.type = "button";
    s.appendChild(out);
    return s;
  }

  function screenMeList(kind) {
    const s = el("div", "screen");
    s.appendChild(el("h1", "large-title", kind === "attended" ? "Attended" : "Logged by me"));
    const list = el("div", "list");
    if (kind === "attended") LOGS.slice(0, 20).forEach((lg) => list.appendChild(row({ lead: dateBlock(lg.date), primary: "Mueller Session", secondary: `${lg.tunes} tunes` })));
    else TUNES.filter((t) => t.mueller).slice(0, 20).forEach((t, i) => list.appendChild(row({ primary: t.name, secondary: `Mueller Session · ${MONTHS[LOGS[i % 6].date.getMonth()].slice(0, 3)} ${LOGS[i % 6].date.getDate()}` })));
    s.appendChild(list);
    return s;
  }

  function alertNote(msg) {
    openSheet({ title: "In the real app", body: [el("div", "note", esc(msg))] });
  }

  // ---------------------------------------------------------------- router
  const TABS = [
    ["home", "Home", `<span class="c-logo" aria-hidden="true"></span>`],
    ["sessions", "Sessions", ICON.cal],
    ["tunes", "Tunes", ICON.notes],
    ["me", "Me", `<svg viewBox="0 0 24 24"><circle cx="12" cy="8.5" r="4"/><path d="M4.5 20a7.5 7.5 0 0 1 15 0"/></svg>`],
  ];
  const BAR = {
    home: {
      title: "",
      left: () => { const i = el("img", "wordmark"); i.src = "logo.png"; i.alt = "ceol"; return i; },
      right: () => {
        // Prototype-only: cycle what "today" looks like.
        const labels = { none: "Today: nothing on", one: "Today: 1 session", festival: "Today: festival (3)" };
        const b = el("button", "proto-tag", labels[state.todayMode]);
        b.type = "button";
        b.title = "Prototype: cycle today's sessions";
        b.addEventListener("click", () => { const order = ["one", "festival", "none"]; state.todayMode = order[(order.indexOf(state.todayMode) + 1) % order.length]; renderCurrent(); });
        return b;
      },
    },
    sessions: { title: "Sessions", right: () => { const b = el("button", "bar-btn plus", "+"); b.type = "button"; b.setAttribute("aria-label", "Add a session"); b.addEventListener("click", openAddSessionSheet); return b; } },
    tunes: { title: "Tunes" },
    me: { title: "Me" },
  };

  function go(hash) { location.hash = hash; }

  function parse() {
    const h = (location.hash || "#/home").replace(/^#\/?/, "");
    const parts = h.split("/");
    return { tab: parts[0] || "home", rest: parts.slice(1).join("/") };
  }

  let prevKey = null; // "tab/rest" of the last rendered route, for push/pop direction
  function renderCurrent(opts = {}) {
    const { tab, rest } = parse();
    const key = `${tab}/${rest}`;
    const mount = $("#mount");
    const old = mount.querySelector(".screen:not(.leaving)");
    const prevScroll = old && prevKey === key ? old.scrollTop : 0;
    const prevDepth = prevKey ? (prevKey.split("/").slice(1).join("/") ? 1 : 0) : 0;
    const depth = rest ? 1 : 0;
    const sameTab = prevKey && prevKey.split("/")[0] === tab;

    let screen, title, back = null, right = null, left = null;
    if (tab === "sessions" && rest) { screen = screenSession(rest); title = (SESSIONS.find((x) => x.path === rest) || {}).name || "Session"; back = "#/sessions"; }
    else if (tab === "me" && rest) { screen = screenMeList(rest); title = rest === "attended" ? "Attended" : "Logged"; back = "#/me"; }
    else {
      const fn = { home: screenHome, sessions: screenSessions, tunes: screenTunes, me: screenMe }[tab] || screenHome;
      screen = fn();
      title = (BAR[tab] || BAR.home).title;
      right = (BAR[tab] || {}).right;
      left = (BAR[tab] || {}).left;
    }

    // Push / pop: deeper on the same tab slides in from the right; shallower slides
    // the old screen out to the right over the new one. Cross-tab is a cut.
    const push = sameTab && depth > prevDepth && prevKey !== key;
    const pop = sameTab && depth < prevDepth;
    if (old && pop) {
      mount.querySelectorAll(".screen.leaving").forEach((n) => n.remove());
      old.classList.add("leaving", "pop");
      old.addEventListener("animationend", () => old.remove(), { once: true });
      mount.insertBefore(screen, old);
    } else {
      mount.querySelectorAll(".screen").forEach((n) => n.remove());
      if (push) screen.classList.add("push");
      mount.appendChild(screen);
    }
    screen.scrollTop = prevScroll;
    prevKey = key;

    // keep the search caret where it was on a re-render caused by typing
    if (opts.keepFocus) {
      const inp = screen.querySelector(".toolbar input");
      if (inp) { inp.focus(); const v = inp.value; inp.setSelectionRange(v.length, v.length); }
    }

    // app bar
    const bar = $("#appbar");
    const leftEl = $("#bar-left"); leftEl.innerHTML = "";
    if (back) { const b = el("button", "bar-btn", "‹ Back"); b.type = "button"; b.addEventListener("click", () => history.length > 1 ? history.back() : go(back)); leftEl.appendChild(b); }
    else if (left) { leftEl.appendChild(left()); }
    $("#bar-title").textContent = title;
    const r = $("#bar-right"); r.innerHTML = "";
    if (right) r.appendChild(right());
    bar.classList.toggle("scrolled", screen.scrollTop > 24);
    screen.addEventListener("scroll", () => bar.classList.toggle("scrolled", screen.scrollTop > 24), { passive: true });

    // tab bar
    document.querySelectorAll("#tabbar button").forEach((b) => b.classList.toggle("active", b.dataset.tab === tab));
  }

  function buildTabbar() {
    const t = $("#tabbar");
    TABS.forEach(([id, label, icon]) => {
      const b = el("button", "", `${icon}<span>${label}</span>`);
      b.type = "button";
      b.dataset.tab = id;
      b.setAttribute("aria-label", label);
      b.addEventListener("click", () => {
        const cur = parse();
        if (cur.tab === id && !cur.rest) { const sc = $("#mount .screen"); if (sc) sc.scrollTo({ top: 0, behavior: "smooth" }); return; }
        go("#/" + id);
      });
      t.appendChild(b);
    });
  }

  function start() {
    buildTabbar();
    $("#scrim").addEventListener("click", closeSheet);
    window.addEventListener("hashchange", () => { closeSheet(); closeMenu(); renderCurrent(); });
    document.addEventListener("keydown", (e) => { if (e.key === "Escape") { closeSheet(); closeMenu(); } });
    if (!location.hash || location.hash === "#/search") history.replaceState(null, "", "#/home");
    renderCurrent();
  }
  start();
})();
