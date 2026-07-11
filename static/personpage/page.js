var Yl = Object.defineProperty;
var Ta = (e) => {
  throw TypeError(e);
};
var Gl = (e, t, n) => t in e ? Yl(e, t, { enumerable: !0, configurable: !0, writable: !0, value: n }) : e[t] = n;
var nt = (e, t, n) => Gl(e, typeof t != "symbol" ? t + "" : t, n), ds = (e, t, n) => t.has(e) || Ta("Cannot " + n);
var c = (e, t, n) => (ds(e, t, "read from private field"), n ? n.call(e) : t.get(e)), z = (e, t, n) => t.has(e) ? Ta("Cannot add the same private member more than once") : t instanceof WeakSet ? t.add(e) : t.set(e, n), j = (e, t, n, r) => (ds(e, t, "write to private field"), r ? r.call(e, n) : t.set(e, n), n), ee = (e, t, n) => (ds(e, t, "access private method"), n);
var Rs = Array.isArray, Wl = Array.prototype.indexOf, Ur = Array.prototype.includes, Wr = Array.from, Jl = Object.defineProperty, vr = Object.getOwnPropertyDescriptor, Kl = Object.getOwnPropertyDescriptors, Zl = Object.prototype, Xl = Array.prototype, Ha = Object.getPrototypeOf, Aa = Object.isExtensible;
const Ql = () => {
};
function $l(e) {
  for (var t = 0; t < e.length; t++)
    e[t]();
}
function Ya() {
  var e, t, n = new Promise((r, s) => {
    e = r, t = s;
  });
  return { promise: n, resolve: e, reject: t };
}
const Ne = 2, Xn = 4, Jr = 8, Ga = 1 << 24, Ft = 16, Vt = 32, bn = 64, bs = 128, gt = 512, ye = 1024, De = 2048, Xt = 4096, Ve = 8192, yt = 16384, nr = 32768, gs = 1 << 25, Qn = 65536, Fr = 1 << 17, eo = 1 << 18, rr = 1 << 19, to = 1 << 20, Jt = 1 << 25, Dn = 65536, jr = 1 << 21, qn = 1 << 22, hn = 1 << 23, Bn = Symbol("$state"), no = Symbol(""), Dr = Symbol("attributes"), ys = Symbol("class"), ws = Symbol("style"), or = Symbol("text"), Nr = Symbol("form reset"), Kr = new class extends Error {
  constructor() {
    super(...arguments);
    nt(this, "name", "StaleReactionError");
    nt(this, "message", "The reaction that called `getAbortSignal()` was re-run or destroyed");
  }
}();
function ro() {
  throw new Error("https://svelte.dev/e/async_derived_orphan");
}
function so(e, t, n) {
  throw new Error("https://svelte.dev/e/each_key_duplicate");
}
function ao(e) {
  throw new Error("https://svelte.dev/e/effect_in_teardown");
}
function io() {
  throw new Error("https://svelte.dev/e/effect_in_unowned_derived");
}
function lo(e) {
  throw new Error("https://svelte.dev/e/effect_orphan");
}
function oo() {
  throw new Error("https://svelte.dev/e/effect_update_depth_exceeded");
}
function uo() {
  throw new Error("https://svelte.dev/e/state_descriptors_fixed");
}
function co() {
  throw new Error("https://svelte.dev/e/state_prototype_fixed");
}
function fo() {
  throw new Error("https://svelte.dev/e/state_unsafe_mutation");
}
function vo() {
  throw new Error("https://svelte.dev/e/svelte_boundary_reset_onerror");
}
const _o = 1, ho = 2, Wa = 4, mo = 8, po = 16, bo = 1, go = 2, ge = Symbol("uninitialized"), yo = "http://www.w3.org/1999/xhtml";
function wo() {
  console.warn("https://svelte.dev/e/derived_inert");
}
function ko() {
  console.warn("https://svelte.dev/e/select_multiple_invalid_value");
}
function xo() {
  console.warn("https://svelte.dev/e/svelte_boundary_reset_noop");
}
function Ja(e) {
  return e === this.v;
}
function Eo(e, t) {
  return e != e ? t == t : e !== t || e !== null && typeof e == "object" || typeof e == "function";
}
function Ka(e) {
  return !Eo(e, this.v);
}
let ze = null;
function $n(e) {
  ze = e;
}
function Mn(e, t = !1, n) {
  ze = {
    p: ze,
    i: !1,
    c: null,
    e: null,
    s: e,
    x: null,
    r: (
      /** @type {Effect} */
      K
    ),
    l: null
  };
}
function On(e) {
  var t = (
    /** @type {ComponentContext} */
    ze
  ), n = t.e;
  if (n !== null) {
    t.e = null;
    for (var r of n)
      pi(r);
  }
  return t.i = !0, ze = t.p, /** @type {T} */
  {};
}
function Za() {
  return !0;
}
let yn = [];
function Xa() {
  var e = yn;
  yn = [], $l(e);
}
function Kt(e) {
  if (yn.length === 0 && !hr) {
    var t = yn;
    queueMicrotask(() => {
      t === yn && Xa();
    });
  }
  yn.push(e);
}
function So() {
  for (; yn.length > 0; )
    Xa();
}
function Qa(e) {
  var t = K;
  if (t === null)
    return G.f |= hn, e;
  if (!(t.f & nr) && !(t.f & Xn))
    throw e;
  _n(e, t);
}
function _n(e, t) {
  if (!(t !== null && t.f & yt)) {
    for (; t !== null; ) {
      if (t.f & bs) {
        if (!(t.f & nr))
          throw e;
        try {
          t.b.error(e);
          return;
        } catch (n) {
          e = n;
        }
      }
      t = t.parent;
    }
    throw e;
  }
}
const To = -7169;
function pe(e, t) {
  e.f = e.f & To | t;
}
function Us(e) {
  e.f & gt || e.deps === null ? pe(e, ye) : pe(e, Xt);
}
function $a(e) {
  if (e !== null)
    for (const t of e)
      !(t.f & Ne) || !(t.f & Dn) || (t.f ^= Dn, $a(
        /** @type {Derived} */
        t.deps
      ));
}
function ei(e, t, n) {
  e.f & De ? t.add(e) : e.f & Xt && n.add(e), $a(e.deps), pe(e, ye);
}
function Ao(e) {
  let t = 0, n = Ln(0), r;
  return () => {
    zs() && (a(n), Sr(() => (t === 0 && (r = Ar(() => e(() => mr(n)))), t += 1, () => {
      Kt(() => {
        t -= 1, t === 0 && (r == null || r(), r = void 0, mr(n));
      });
    })));
  };
}
var Po = Qn | rr;
function Co(e, t, n, r) {
  new Io(e, t, n, r);
}
var ht, Os, mt, xn, Je, pt, Fe, st, nn, En, fn, Hn, gr, yr, rn, Hr, ve, Do, No, Lo, ks, Lr, Mr, xs, Es;
class Io {
  /**
   * @param {TemplateNode} node
   * @param {BoundaryProps} props
   * @param {((anchor: Node) => void)} children
   * @param {((error: unknown) => unknown) | undefined} [transform_error]
   */
  constructor(t, n, r, s) {
    z(this, ve);
    /** @type {Boundary | null} */
    nt(this, "parent");
    nt(this, "is_pending", !1);
    /**
     * API-level transformError transform function. Transforms errors before they reach the `failed` snippet.
     * Inherited from parent boundary, or defaults to identity.
     * @type {(error: unknown) => unknown}
     */
    nt(this, "transform_error");
    /** @type {TemplateNode} */
    z(this, ht);
    /** @type {TemplateNode | null} */
    z(this, Os, null);
    /** @type {BoundaryProps} */
    z(this, mt);
    /** @type {((anchor: Node) => void)} */
    z(this, xn);
    /** @type {Effect} */
    z(this, Je);
    /** @type {Effect | null} */
    z(this, pt, null);
    /** @type {Effect | null} */
    z(this, Fe, null);
    /** @type {Effect | null} */
    z(this, st, null);
    /** @type {DocumentFragment | null} */
    z(this, nn, null);
    z(this, En, 0);
    z(this, fn, 0);
    z(this, Hn, !1);
    /** @type {Set<Effect>} */
    z(this, gr, /* @__PURE__ */ new Set());
    /** @type {Set<Effect>} */
    z(this, yr, /* @__PURE__ */ new Set());
    /**
     * A source containing the number of pending async deriveds/expressions.
     * Only created if `$effect.pending()` is used inside the boundary,
     * otherwise updating the source results in needless `Batch.ensure()`
     * calls followed by no-op flushes
     * @type {Source<number> | null}
     */
    z(this, rn, null);
    z(this, Hr, Ao(() => (j(this, rn, Ln(c(this, En))), () => {
      j(this, rn, null);
    })));
    var i;
    j(this, ht, t), j(this, mt, n), j(this, xn, (o) => {
      var u = (
        /** @type {Effect} */
        K
      );
      u.b = this, u.f |= bs, r(o);
    }), this.parent = /** @type {Effect} */
    K.b, this.transform_error = s ?? ((i = this.parent) == null ? void 0 : i.transform_error) ?? ((o) => o), j(this, Je, qs(() => {
      ee(this, ve, ks).call(this);
    }, Po));
  }
  /**
   * Defer an effect inside a pending boundary until the boundary resolves
   * @param {Effect} effect
   */
  defer_effect(t) {
    ei(t, c(this, gr), c(this, yr));
  }
  /**
   * Returns `false` if the effect exists inside a boundary whose pending snippet is shown
   * @returns {boolean}
   */
  is_rendered() {
    return !this.is_pending && (!this.parent || this.parent.is_rendered());
  }
  has_pending_snippet() {
    return !!c(this, mt).pending;
  }
  /**
   * Update the source that powers `$effect.pending()` inside this boundary,
   * and controls when the current `pending` snippet (if any) is removed.
   * Do not call from inside the class
   * @param {1 | -1} d
   * @param {Batch} batch
   */
  update_pending_count(t, n) {
    ee(this, ve, xs).call(this, t, n), j(this, En, c(this, En) + t), !(!c(this, rn) || c(this, Hn)) && (j(this, Hn, !0), Kt(() => {
      j(this, Hn, !1), c(this, rn) && er(c(this, rn), c(this, En));
    }));
  }
  get_effect_pending() {
    return c(this, Hr).call(this), a(
      /** @type {Source<number>} */
      c(this, rn)
    );
  }
  /** @param {unknown} error */
  error(t) {
    if (!c(this, mt).onerror && !c(this, mt).failed)
      throw t;
    L != null && L.is_fork ? (c(this, pt) && L.skip_effect(c(this, pt)), c(this, Fe) && L.skip_effect(c(this, Fe)), c(this, st) && L.skip_effect(c(this, st)), L.oncommit(() => {
      ee(this, ve, Es).call(this, t);
    })) : ee(this, ve, Es).call(this, t);
  }
}
ht = new WeakMap(), Os = new WeakMap(), mt = new WeakMap(), xn = new WeakMap(), Je = new WeakMap(), pt = new WeakMap(), Fe = new WeakMap(), st = new WeakMap(), nn = new WeakMap(), En = new WeakMap(), fn = new WeakMap(), Hn = new WeakMap(), gr = new WeakMap(), yr = new WeakMap(), rn = new WeakMap(), Hr = new WeakMap(), ve = new WeakSet(), Do = function() {
  try {
    j(this, pt, bt(() => c(this, xn).call(this, c(this, ht))));
  } catch (t) {
    this.error(t);
  }
}, /**
 * @param {unknown} error The deserialized error from the server's hydration comment
 */
No = function(t) {
  const n = c(this, mt).failed;
  n && j(this, st, bt(() => {
    n(
      c(this, ht),
      () => t,
      () => () => {
      }
    );
  }));
}, Lo = function() {
  const t = c(this, mt).pending;
  t && (this.is_pending = !0, j(this, Fe, bt(() => t(c(this, ht)))), Kt(() => {
    var n = j(this, nn, document.createDocumentFragment()), r = mn();
    n.append(r), j(this, pt, ee(this, ve, Mr).call(this, () => bt(() => c(this, xn).call(this, r)))), c(this, fn) === 0 && (c(this, ht).before(n), j(this, nn, null), Cn(
      /** @type {Effect} */
      c(this, Fe),
      () => {
        j(this, Fe, null);
      }
    ), ee(this, ve, Lr).call(
      this,
      /** @type {Batch} */
      L
    ));
  }));
}, ks = function() {
  try {
    if (this.is_pending = this.has_pending_snippet(), j(this, fn, 0), j(this, En, 0), j(this, pt, bt(() => {
      c(this, xn).call(this, c(this, ht));
    })), c(this, fn) > 0) {
      var t = j(this, nn, document.createDocumentFragment());
      Hs(c(this, pt), t);
      const n = (
        /** @type {(anchor: Node) => void} */
        c(this, mt).pending
      );
      j(this, Fe, bt(() => n(c(this, ht))));
    } else
      ee(this, ve, Lr).call(
        this,
        /** @type {Batch} */
        L
      );
  } catch (n) {
    this.error(n);
  }
}, /**
 * @param {Batch} batch
 */
Lr = function(t) {
  this.is_pending = !1, t.transfer_effects(c(this, gr), c(this, yr));
}, /**
 * @template T
 * @param {() => T} fn
 */
Mr = function(t) {
  var n = K, r = G, s = ze;
  Qt(c(this, Je)), wt(c(this, Je)), $n(c(this, Je).ctx);
  try {
    return Nn.ensure(), t();
  } catch (i) {
    return Qa(i), null;
  } finally {
    Qt(n), wt(r), $n(s);
  }
}, /**
 * Updates the pending count associated with the currently visible pending snippet,
 * if any, such that we can replace the snippet with content once work is done
 * @param {1 | -1} d
 * @param {Batch} batch
 */
xs = function(t, n) {
  var r;
  if (!this.has_pending_snippet()) {
    this.parent && ee(r = this.parent, ve, xs).call(r, t, n);
    return;
  }
  j(this, fn, c(this, fn) + t), c(this, fn) === 0 && (ee(this, ve, Lr).call(this, n), c(this, Fe) && Cn(c(this, Fe), () => {
    j(this, Fe, null);
  }), c(this, nn) && (c(this, ht).before(c(this, nn)), j(this, nn, null)));
}, /**
 * @param {unknown} error
 */
Es = function(t) {
  c(this, pt) && (Xe(c(this, pt)), j(this, pt, null)), c(this, Fe) && (Xe(c(this, Fe)), j(this, Fe, null)), c(this, st) && (Xe(c(this, st)), j(this, st, null));
  var n = c(this, mt).onerror;
  let r = c(this, mt).failed;
  var s = !1, i = !1;
  const o = () => {
    if (s) {
      xo();
      return;
    }
    s = !0, i && vo(), c(this, st) !== null && Cn(c(this, st), () => {
      j(this, st, null);
    }), ee(this, ve, Mr).call(this, () => {
      ee(this, ve, ks).call(this);
    });
  }, u = (d) => {
    try {
      i = !0, n == null || n(d, o), i = !1;
    } catch (v) {
      _n(v, c(this, Je) && c(this, Je).parent);
    }
    r && j(this, st, ee(this, ve, Mr).call(this, () => {
      try {
        return bt(() => {
          var v = (
            /** @type {Effect} */
            K
          );
          v.b = this, v.f |= bs, r(
            c(this, ht),
            () => d,
            () => o
          );
        });
      } catch (v) {
        return _n(
          v,
          /** @type {Effect} */
          c(this, Je).parent
        ), null;
      }
    }));
  };
  Kt(() => {
    var d;
    try {
      d = this.transform_error(t);
    } catch (v) {
      _n(v, c(this, Je) && c(this, Je).parent);
      return;
    }
    d !== null && typeof d == "object" && typeof /** @type {any} */
    d.then == "function" ? d.then(
      u,
      /** @param {unknown} e */
      (v) => _n(v, c(this, Je) && c(this, Je).parent)
    ) : u(d);
  });
};
function Mo(e, t, n, r) {
  const s = Zr;
  var i = e.filter((g) => !g.settled), o = t.map(s);
  if (n.length === 0 && i.length === 0) {
    r(o);
    return;
  }
  var u = (
    /** @type {Effect} */
    K
  ), d = Oo(), v = i.length === 1 ? i[0].promise : i.length > 1 ? Promise.all(i.map((g) => g.promise)) : null;
  function p(g) {
    if (!(u.f & yt)) {
      d();
      try {
        r([...o, ...g]);
      } catch (k) {
        _n(k, u);
      }
      Vr();
    }
  }
  var y = ti();
  if (n.length === 0) {
    v.then(() => p([])).finally(y);
    return;
  }
  function h() {
    Promise.all(n.map((g) => /* @__PURE__ */ Ro(g))).then(p).catch((g) => _n(g, u)).finally(y);
  }
  v ? v.then(() => {
    d(), h(), Vr();
  }) : h();
}
function Oo() {
  var e = (
    /** @type {Effect} */
    K
  ), t = G, n = ze, r = (
    /** @type {Batch} */
    L
  );
  return function(i = !0) {
    Qt(e), wt(t), $n(n), i && !(e.f & yt) && (r == null || r.activate(), r == null || r.apply());
  };
}
function Vr(e = !0) {
  Qt(null), wt(null), $n(null), e && (L == null || L.deactivate());
}
function ti() {
  var e = (
    /** @type {Effect} */
    K
  ), t = e.b, n = (
    /** @type {Batch} */
    L
  ), r = !!(t != null && t.is_rendered());
  return t == null || t.update_pending_count(1, n), n.increment(r, e), () => {
    t == null || t.update_pending_count(-1, n), n.decrement(r, e);
  };
}
// @__NO_SIDE_EFFECTS__
function Zr(e) {
  var t = Ne | De;
  return K !== null && (K.f |= rr), {
    ctx: ze,
    deps: null,
    effects: null,
    equals: Ja,
    f: t,
    fn: e,
    reactions: null,
    rv: 0,
    v: (
      /** @type {V} */
      ge
    ),
    wv: 0,
    parent: K,
    ac: null
  };
}
const dr = Symbol("obsolete");
// @__NO_SIDE_EFFECTS__
function Ro(e, t, n) {
  let r = (
    /** @type {Effect | null} */
    K
  );
  r === null && ro();
  var s = (
    /** @type {Promise<V>} */
    /** @type {unknown} */
    void 0
  ), i = Ln(
    /** @type {V} */
    ge
  ), o = !G, u = /* @__PURE__ */ new Set();
  return $o(() => {
    var g, k;
    var d = (
      /** @type {Effect} */
      K
    ), v = Ya();
    s = v.promise;
    try {
      Promise.resolve(e()).then(v.resolve, (w) => {
        w !== Kr && v.reject(w);
      }).finally(Vr);
    } catch (w) {
      v.reject(w), Vr();
    }
    var p = (
      /** @type {Batch} */
      L
    );
    if (o) {
      if (d.f & nr)
        var y = ti();
      if (
        // boundary can be null if the async derived is inside an $effect.root not connected to the component render tree
        (g = r.b) != null && g.is_rendered()
      )
        (k = p.async_deriveds.get(d)) == null || k.reject(dr);
      else
        for (const w of u.values())
          w.reject(dr);
      u.add(v), p.async_deriveds.set(d, v);
    }
    const h = (w, m = void 0) => {
      y == null || y(), u.delete(v), m !== dr && (p.activate(), m ? (i.f |= hn, er(i, m)) : (i.f & hn && (i.f ^= hn), er(i, w)), p.deactivate());
    };
    v.promise.then(h, (w) => h(null, w || "unknown"));
  }), $r(() => {
    for (const d of u)
      d.reject(dr);
  }), new Promise((d) => {
    function v(p) {
      function y() {
        p === s ? d(i) : v(s);
      }
      p.then(y, y);
    }
    v(s);
  });
}
// @__NO_SIDE_EFFECTS__
function Ut(e) {
  const t = /* @__PURE__ */ Zr(e);
  return xi(t), t;
}
// @__NO_SIDE_EFFECTS__
function Uo(e) {
  const t = /* @__PURE__ */ Zr(e);
  return t.equals = Ka, t;
}
function Fo(e) {
  var t = e.effects;
  if (t !== null) {
    e.effects = null;
    for (var n = 0; n < t.length; n += 1)
      Xe(
        /** @type {Effect} */
        t[n]
      );
  }
}
function Fs(e) {
  var t, n = K, r = e.parent;
  if (!gn && r !== null && e.v !== ge && // if it was never evaluated before, it's guaranteed to fail downstream, so we try to execute instead
  r.f & (yt | Ve))
    return wo(), e.v;
  Qt(r);
  try {
    e.f &= ~Dn, Fo(e), t = Ai(e);
  } finally {
    Qt(n);
  }
  return t;
}
function ni(e) {
  var t = Fs(e);
  if (!e.equals(t) && (e.wv = Si(), (!(L != null && L.is_fork) || e.deps === null) && (L !== null ? (L.capture(e, t, !0), _r == null || _r.capture(e, t, !0)) : e.v = t, e.deps === null))) {
    pe(e, ye);
    return;
  }
  gn || (Ie !== null ? (zs() || L != null && L.is_fork) && Ie.set(e, t) : Us(e));
}
function jo(e) {
  var t, n;
  if (e.effects !== null)
    for (const r of e.effects)
      (r.teardown || r.ac) && ((t = r.teardown) == null || t.call(r), (n = r.ac) == null || n.abort(Kr), r.fn !== null && (r.teardown = Ql), r.ac = null, br(r, 0), Bs(r));
}
function ri(e) {
  if (e.effects !== null)
    for (const t of e.effects)
      t.teardown && t.fn !== null && tr(t);
}
let us = null, Fn = null, L = null, _r = null, Ie = null, Ss = null, hr = !1, cs = !1, zn = null, Or = null;
var Pa = 0;
let Vo = 1;
var Yn, vn, Sn, Gn, Wn, Jn, sn, Kn, Ke, wr, an, Ot, Gt, Zn, Tn, re, Ts, ur, As, si, ai, jn, zo, cr;
const Yr = class Yr {
  constructor() {
    z(this, re);
    nt(this, "id", Vo++);
    /** True as soon as `#process` was called */
    z(this, Yn, !1);
    nt(this, "linked", !0);
    /** @type {Batch | null} */
    z(this, vn, null);
    /** @type {Batch | null} */
    z(this, Sn, null);
    /** @type {Map<Effect, ReturnType<typeof deferred<any>>>} */
    nt(this, "async_deriveds", /* @__PURE__ */ new Map());
    /**
     * The current values of any signals that are updated in this batch.
     * Tuple format: [value, is_derived] (note: is_derived is false for deriveds, too, if they were overridden via assignment)
     * They keys of this map are identical to `this.#previous`
     * @type {Map<Value, [any, boolean]>}
     */
    nt(this, "current", /* @__PURE__ */ new Map());
    /**
     * The values of any signals (sources and deriveds) that are updated in this batch _before_ those updates took place.
     * They keys of this map are identical to `this.#current`
     * @type {Map<Value, any>}
     */
    nt(this, "previous", /* @__PURE__ */ new Map());
    /**
     * When the batch is committed (and the DOM is updated), we need to remove old branches
     * and append new ones by calling the functions added inside (if/each/key/etc) blocks
     * @type {Set<(batch: Batch) => void>}
     */
    z(this, Gn, /* @__PURE__ */ new Set());
    /**
     * If a fork is discarded, we need to destroy any effects that are no longer needed
     * @type {Set<(batch: Batch) => void>}
     */
    z(this, Wn, /* @__PURE__ */ new Set());
    /**
     * The number of async effects that are currently in flight
     */
    z(this, Jn, 0);
    /**
     * Async effects that are currently in flight, _not_ inside a pending boundary
     * @type {Map<Effect, number>}
     */
    z(this, sn, /* @__PURE__ */ new Map());
    /**
     * A deferred that resolves when the batch is committed, used with `settled()`
     * TODO replace with Promise.withResolvers once supported widely enough
     * @type {{ promise: Promise<void>, resolve: (value?: any) => void, reject: (reason: unknown) => void } | null}
     */
    z(this, Kn, null);
    /**
     * The root effects that need to be flushed
     * @type {Effect[]}
     */
    z(this, Ke, []);
    /**
     * Effects created while this batch was active.
     * @type {Effect[]}
     */
    z(this, wr, []);
    /**
     * Deferred effects (which run after async work has completed) that are DIRTY
     * @type {Set<Effect>}
     */
    z(this, an, /* @__PURE__ */ new Set());
    /**
     * Deferred effects that are MAYBE_DIRTY
     * @type {Set<Effect>}
     */
    z(this, Ot, /* @__PURE__ */ new Set());
    /**
     * A map of branches that still exist, but will be destroyed when this batch
     * is committed — we skip over these during `process`.
     * The value contains child effects that were dirty/maybe_dirty before being reset,
     * so they can be rescheduled if the branch survives.
     * @type {Map<Effect, { d: Effect[], m: Effect[] }>}
     */
    z(this, Gt, /* @__PURE__ */ new Map());
    /**
     * Inverse of #skipped_branches which we need to tell prior batches to unskip them when committing
     * @type {Set<Effect>}
     */
    z(this, Zn, /* @__PURE__ */ new Set());
    nt(this, "is_fork", !1);
    z(this, Tn, !1);
    Fn === null ? us = Fn = this : (j(Fn, Sn, this), j(this, vn, Fn)), Fn = this;
  }
  /**
   * Add an effect to the #skipped_branches map and reset its children
   * @param {Effect} effect
   */
  skip_effect(t) {
    c(this, Gt).has(t) || c(this, Gt).set(t, { d: [], m: [] }), c(this, Zn).delete(t);
  }
  /**
   * Remove an effect from the #skipped_branches map and reschedule
   * any tracked dirty/maybe_dirty child effects
   * @param {Effect} effect
   * @param {(e: Effect) => void} callback
   */
  unskip_effect(t, n = (r) => this.schedule(r)) {
    var r = c(this, Gt).get(t);
    if (r) {
      c(this, Gt).delete(t);
      for (var s of r.d)
        pe(s, De), n(s);
      for (s of r.m)
        pe(s, Xt), n(s);
    }
    c(this, Zn).add(t);
  }
  /**
   * Associate a change to a given source with the current
   * batch, noting its previous and current values
   * @param {Value} source
   * @param {any} value
   * @param {boolean} [is_derived]
   */
  capture(t, n, r = !1) {
    t.v !== ge && !this.previous.has(t) && this.previous.set(t, t.v), t.f & hn || (this.current.set(t, [n, r]), Ie == null || Ie.set(t, n)), this.is_fork || (t.v = n);
  }
  activate() {
    L = this;
  }
  deactivate() {
    L = null, Ie = null;
  }
  flush() {
    try {
      cs = !0, L = this, ee(this, re, ur).call(this);
    } finally {
      Pa = 0, Ss = null, zn = null, Or = null, cs = !1, L = null, Ie = null, Pn.clear();
    }
  }
  discard() {
    var t;
    for (const n of c(this, Wn)) n(this);
    c(this, Wn).clear();
    for (const n of this.async_deriveds.values())
      n.reject(dr);
    ee(this, re, cr).call(this), (t = c(this, Kn)) == null || t.resolve();
  }
  /**
   * @param {Effect} effect
   */
  register_created_effect(t) {
    c(this, wr).push(t);
  }
  /**
   * @param {boolean} blocking
   * @param {Effect} effect
   */
  increment(t, n) {
    if (j(this, Jn, c(this, Jn) + 1), t) {
      let r = c(this, sn).get(n) ?? 0;
      c(this, sn).set(n, r + 1);
    }
  }
  /**
   * @param {boolean} blocking
   * @param {Effect} effect
   */
  decrement(t, n) {
    if (j(this, Jn, c(this, Jn) - 1), t) {
      let r = c(this, sn).get(n) ?? 0;
      r === 1 ? c(this, sn).delete(n) : c(this, sn).set(n, r - 1);
    }
    c(this, Tn) || (j(this, Tn, !0), Kt(() => {
      j(this, Tn, !1), this.linked && this.flush();
    }));
  }
  /**
   * @param {Set<Effect>} dirty_effects
   * @param {Set<Effect>} maybe_dirty_effects
   */
  transfer_effects(t, n) {
    for (const r of t)
      c(this, an).add(r);
    for (const r of n)
      c(this, Ot).add(r);
    t.clear(), n.clear();
  }
  /** @param {(batch: Batch) => void} fn */
  oncommit(t) {
    c(this, Gn).add(t);
  }
  /** @param {(batch: Batch) => void} fn */
  ondiscard(t) {
    c(this, Wn).add(t);
  }
  settled() {
    return (c(this, Kn) ?? j(this, Kn, Ya())).promise;
  }
  static ensure() {
    if (L === null) {
      const t = L = new Yr();
      !cs && !hr && Kt(() => {
        c(t, Yn) || t.flush();
      });
    }
    return L;
  }
  apply() {
    {
      Ie = null;
      return;
    }
  }
  /**
   *
   * @param {Effect} effect
   */
  schedule(t) {
    var s;
    if (Ss = t, (s = t.b) != null && s.is_pending && t.f & (Xn | Jr | Ga) && !(t.f & nr)) {
      t.b.defer_effect(t);
      return;
    }
    for (var n = t; n.parent !== null; ) {
      n = n.parent;
      var r = n.f;
      if (zn !== null && n === K && (G === null || !(G.f & Ne)))
        return;
      if (r & (bn | Vt)) {
        if (!(r & ye))
          return;
        n.f ^= ye;
      }
    }
    c(this, Ke).push(n);
  }
};
Yn = new WeakMap(), vn = new WeakMap(), Sn = new WeakMap(), Gn = new WeakMap(), Wn = new WeakMap(), Jn = new WeakMap(), sn = new WeakMap(), Kn = new WeakMap(), Ke = new WeakMap(), wr = new WeakMap(), an = new WeakMap(), Ot = new WeakMap(), Gt = new WeakMap(), Zn = new WeakMap(), Tn = new WeakMap(), re = new WeakSet(), Ts = function() {
  if (this.is_fork) return !0;
  for (const r of c(this, sn).keys()) {
    for (var t = r, n = !1; t.parent !== null; ) {
      if (c(this, Gt).has(t)) {
        n = !0;
        break;
      }
      t = t.parent;
    }
    if (!n)
      return !0;
  }
  return !1;
}, ur = function() {
  var d, v, p, y;
  j(this, Yn, !0), Pa++ > 1e3 && (ee(this, re, cr).call(this), Bo());
  for (const h of c(this, an))
    c(this, Ot).delete(h), pe(h, De), this.schedule(h);
  for (const h of c(this, Ot))
    pe(h, Xt), this.schedule(h);
  const t = c(this, Ke);
  j(this, Ke, []), this.apply();
  var n = zn = [], r = [], s = Or = [];
  for (const h of t)
    try {
      ee(this, re, As).call(this, h, n, r);
    } catch (g) {
      throw oi(h), ee(this, re, Ts).call(this) || this.discard(), g;
    }
  if (L = null, s.length > 0) {
    var i = Yr.ensure();
    for (const h of s)
      i.schedule(h);
  }
  if (zn = null, Or = null, ee(this, re, Ts).call(this)) {
    ee(this, re, jn).call(this, r), ee(this, re, jn).call(this, n);
    for (const [h, g] of c(this, Gt))
      li(h, g);
    s.length > 0 && /** @type {unknown} */
    ee(d = L, re, ur).call(d);
    return;
  }
  const o = ee(this, re, si).call(this);
  if (o) {
    ee(this, re, jn).call(this, r), ee(this, re, jn).call(this, n), ee(v = o, re, ai).call(v, this);
    return;
  }
  c(this, an).clear(), c(this, Ot).clear();
  for (const h of c(this, Gn)) h(this);
  c(this, Gn).clear(), _r = this, Ca(r), Ca(n), _r = null, (p = c(this, Kn)) == null || p.resolve();
  var u = (
    /** @type {Batch | null} */
    /** @type {unknown} */
    L
  );
  if (c(this, Jn) === 0 && (c(this, Ke).length === 0 || u !== null) && ee(this, re, cr).call(this), c(this, Ke).length > 0)
    if (u !== null) {
      const h = u;
      c(h, Ke).push(...c(this, Ke).filter((g) => !c(h, Ke).includes(g)));
    } else
      u = this;
  u !== null && ee(y = u, re, ur).call(y);
}, /**
 * Traverse the effect tree, executing effects or stashing
 * them for later execution as appropriate
 * @param {Effect} root
 * @param {Effect[]} effects
 * @param {Effect[]} render_effects
 */
As = function(t, n, r) {
  t.f ^= ye;
  for (var s = t.first; s !== null; ) {
    var i = s.f, o = (i & (Vt | bn)) !== 0, u = o && (i & ye) !== 0, d = u || (i & Ve) !== 0 || c(this, Gt).has(s);
    if (!d && s.fn !== null) {
      o ? s.f ^= ye : i & Xn ? n.push(s) : Tr(s) && (i & Ft && c(this, Ot).add(s), tr(s));
      var v = s.first;
      if (v !== null) {
        s = v;
        continue;
      }
    }
    for (; s !== null; ) {
      var p = s.next;
      if (p !== null) {
        s = p;
        break;
      }
      s = s.parent;
    }
  }
}, si = function() {
  for (var t = c(this, vn); t !== null; ) {
    if (!t.is_fork) {
      for (const [n, [, r]] of this.current)
        if (t.current.has(n) && !r)
          return t;
    }
    t = c(t, vn);
  }
  return null;
}, /**
 * @param {Batch} batch
 */
ai = function(t) {
  var r;
  for (const [s, i] of t.current)
    !this.previous.has(s) && t.previous.has(s) && this.previous.set(s, t.previous.get(s)), this.current.set(s, i);
  for (const [s, i] of t.async_deriveds) {
    const o = this.async_deriveds.get(s);
    o && i.promise.then(o.resolve).catch(o.reject);
  }
  t.async_deriveds.clear(), this.transfer_effects(c(t, an), c(t, Ot));
  const n = (s) => {
    var i = s.reactions;
    if (i !== null)
      for (const d of i) {
        var o = d.f;
        if (o & Ne)
          n(
            /** @type {Derived} */
            d
          );
        else {
          var u = (
            /** @type {Effect} */
            d
          );
          o & (qn | Ft) && !this.async_deriveds.has(u) && (c(this, Ot).delete(u), pe(u, De), this.schedule(u));
        }
      }
  };
  for (const s of this.current.keys())
    n(s);
  this.oncommit(() => t.discard()), ee(r = t, re, cr).call(r), L = this, ee(this, re, ur).call(this);
}, /**
 * @param {Effect[]} effects
 */
jn = function(t) {
  for (var n = 0; n < t.length; n += 1)
    ei(t[n], c(this, an), c(this, Ot));
}, zo = function() {
  var y;
  for (let h = us; h !== null; h = c(h, Sn)) {
    var t = h.id < this.id, n = [];
    for (const [g, [k, w]] of this.current) {
      if (h.current.has(g)) {
        var r = (
          /** @type {[any, boolean]} */
          h.current.get(g)[0]
        );
        if (t && k !== r)
          h.current.set(g, [k, w]);
        else
          continue;
      }
      n.push(g);
    }
    if (t)
      for (const [g, k] of this.async_deriveds) {
        const w = h.async_deriveds.get(g);
        w && k.promise.then(w.resolve).catch(w.reject);
      }
    var s = [...h.current.keys()].filter(
      (g) => !/** @type {[any, boolean]} */
      h.current.get(g)[1]
    );
    if (!(!c(h, Yn) || s.length === 0)) {
      var i = s.filter((g) => !this.current.has(g));
      if (i.length === 0)
        t && h.discard();
      else if (n.length > 0) {
        if (t)
          for (const g of c(this, Zn))
            h.unskip_effect(g, (k) => {
              var w;
              k.f & (Ft | qn) ? h.schedule(k) : ee(w = h, re, jn).call(w, [k]);
            });
        h.activate();
        var o = /* @__PURE__ */ new Set(), u = /* @__PURE__ */ new Map();
        for (var d of n)
          ii(d, i, o, u);
        u = /* @__PURE__ */ new Map();
        var v = [...h.current].filter(([g, k]) => {
          const w = this.current.get(g);
          return w ? w[0] !== k[0] || w[1] !== k[1] : !0;
        }).map(([g]) => g);
        if (v.length > 0)
          for (const g of c(this, wr))
            !(g.f & (yt | Ve | Fr)) && js(g, v, u) && (g.f & (qn | Ft) ? (pe(g, De), h.schedule(g)) : c(h, an).add(g));
        if (c(h, Ke).length > 0 && !c(h, Tn)) {
          h.apply();
          for (var p of c(h, Ke))
            ee(y = h, re, As).call(y, p, [], []);
          j(h, Ke, []);
        }
        h.deactivate();
      }
    }
  }
}, cr = function() {
  if (this.linked) {
    var t = c(this, vn), n = c(this, Sn);
    t === null ? us = n : j(t, Sn, n), n === null ? Fn = t : j(n, vn, t), this.linked = !1;
  }
};
let Nn = Yr;
function qo(e) {
  var t = hr;
  hr = !0;
  try {
    for (var n; ; ) {
      if (So(), L === null)
        return (
          /** @type {T} */
          n
        );
      L.flush();
    }
  } finally {
    hr = t;
  }
}
function Bo() {
  try {
    oo();
  } catch (e) {
    _n(e, Ss);
  }
}
let Mt = null;
function Ca(e) {
  var t = e.length;
  if (t !== 0) {
    for (var n = 0; n < t; ) {
      var r = e[n++];
      if (!(r.f & (yt | Ve)) && Tr(r) && (Mt = /* @__PURE__ */ new Set(), tr(r), r.deps === null && r.first === null && r.nodes === null && r.teardown === null && r.ac === null && yi(r), (Mt == null ? void 0 : Mt.size) > 0)) {
        Pn.clear();
        for (const s of Mt) {
          if (s.f & (yt | Ve)) continue;
          const i = [s];
          let o = s.parent;
          for (; o !== null; )
            Mt.has(o) && (Mt.delete(o), i.push(o)), o = o.parent;
          for (let u = i.length - 1; u >= 0; u--) {
            const d = i[u];
            d.f & (yt | Ve) || tr(d);
          }
        }
        Mt.clear();
      }
    }
    Mt = null;
  }
}
function ii(e, t, n, r) {
  if (!n.has(e) && (n.add(e), e.reactions !== null))
    for (const s of e.reactions) {
      const i = s.f;
      i & Ne ? ii(
        /** @type {Derived} */
        s,
        t,
        n,
        r
      ) : i & (qn | Ft) && !(i & De) && js(s, t, r) && (pe(s, De), Vs(
        /** @type {Effect} */
        s
      ));
    }
}
function js(e, t, n) {
  const r = n.get(e);
  if (r !== void 0) return r;
  if (e.deps !== null)
    for (const s of e.deps) {
      if (Ur.call(t, s))
        return !0;
      if (s.f & Ne && js(
        /** @type {Derived} */
        s,
        t,
        n
      ))
        return n.set(
          /** @type {Derived} */
          s,
          !0
        ), !0;
    }
  return n.set(e, !1), !1;
}
function Vs(e) {
  L.schedule(e);
}
function li(e, t) {
  if (!(e.f & Vt && e.f & ye)) {
    e.f & De ? t.d.push(e) : e.f & Xt && t.m.push(e), pe(e, ye);
    for (var n = e.first; n !== null; )
      li(n, t), n = n.next;
  }
}
function oi(e) {
  pe(e, ye);
  for (var t = e.first; t !== null; )
    oi(t), t = t.next;
}
let zr = /* @__PURE__ */ new Set();
const Pn = /* @__PURE__ */ new Map();
let di = !1;
function Ln(e, t) {
  var n = {
    f: 0,
    // TODO ideally we could skip this altogether, but it causes type errors
    v: e,
    reactions: null,
    equals: Ja,
    rv: 0,
    wv: 0
  };
  return n;
}
// @__NO_SIDE_EFFECTS__
function P(e, t) {
  const n = Ln(e);
  return xi(n), n;
}
// @__NO_SIDE_EFFECTS__
function Ho(e, t = !1, n = !0) {
  const r = Ln(e);
  return t || (r.equals = Ka), r;
}
function b(e, t, n = !1) {
  G !== null && // since we are untracking the function inside `$inspect.with` we need to add this check
  // to ensure we error if state is set inside an inspect effect
  (!jt || G.f & Fr) && Za() && G.f & (Ne | Ft | qn | Fr) && (Zt === null || !Zt.has(e)) && fo();
  let r = n ? me(t) : t;
  return er(e, r, Or);
}
function er(e, t, n = null) {
  if (!e.equals(t)) {
    Pn.set(e, gn ? t : e.v);
    var r = Nn.ensure();
    if (r.capture(e, t), e.f & Ne) {
      const s = (
        /** @type {Derived} */
        e
      );
      e.f & De && Fs(s), Ie === null && Us(s);
    }
    e.wv = Si(), ui(e, De, n), K !== null && K.f & ye && !(K.f & (Vt | bn)) && (_t === null ? nd([e]) : _t.push(e)), !r.is_fork && zr.size > 0 && !di && Yo();
  }
  return t;
}
function Yo() {
  di = !1;
  for (const e of zr) {
    e.f & ye && pe(e, Xt);
    let t;
    try {
      t = Tr(e);
    } catch {
      t = !0;
    }
    t && tr(e);
  }
  zr.clear();
}
function mr(e) {
  b(e, e.v + 1);
}
function ui(e, t, n) {
  var r = e.reactions;
  if (r !== null)
    for (var s = r.length, i = 0; i < s; i++) {
      var o = r[i], u = o.f, d = (u & De) === 0;
      if (d && pe(o, t), u & Fr)
        zr.add(
          /** @type {Effect} */
          o
        );
      else if (u & Ne) {
        var v = (
          /** @type {Derived} */
          o
        );
        Ie == null || Ie.delete(v), u & Dn || (u & gt && (K === null || !(K.f & jr)) && (o.f |= Dn), ui(v, Xt, n));
      } else if (d) {
        var p = (
          /** @type {Effect} */
          o
        );
        u & Ft && Mt !== null && Mt.add(p), n !== null ? n.push(p) : Vs(p);
      }
    }
}
function me(e) {
  if (typeof e != "object" || e === null || Bn in e)
    return e;
  const t = Ha(e);
  if (t !== Zl && t !== Xl)
    return e;
  var n = /* @__PURE__ */ new Map(), r = Rs(e), s = /* @__PURE__ */ P(0), i = In, o = (u) => {
    if (In === i)
      return u();
    var d = G, v = In;
    wt(null), La(i);
    var p = u();
    return wt(d), La(v), p;
  };
  return r && n.set("length", /* @__PURE__ */ P(
    /** @type {any[]} */
    e.length
  )), new Proxy(
    /** @type {any} */
    e,
    {
      defineProperty(u, d, v) {
        (!("value" in v) || v.configurable === !1 || v.enumerable === !1 || v.writable === !1) && uo();
        var p = n.get(d);
        return p === void 0 ? o(() => {
          var y = /* @__PURE__ */ P(v.value);
          return n.set(d, y), y;
        }) : b(p, v.value, !0), !0;
      },
      deleteProperty(u, d) {
        var v = n.get(d);
        if (v === void 0) {
          if (d in u) {
            const p = o(() => /* @__PURE__ */ P(ge));
            n.set(d, p), mr(s);
          }
        } else
          b(v, ge), mr(s);
        return !0;
      },
      get(u, d, v) {
        var g;
        if (d === Bn)
          return e;
        var p = n.get(d), y = d in u;
        if (p === void 0 && (!y || (g = vr(u, d)) != null && g.writable) && (p = o(() => {
          var k = me(y ? u[d] : ge), w = /* @__PURE__ */ P(k);
          return w;
        }), n.set(d, p)), p !== void 0) {
          var h = a(p);
          return h === ge ? void 0 : h;
        }
        return Reflect.get(u, d, v);
      },
      getOwnPropertyDescriptor(u, d) {
        var v = Reflect.getOwnPropertyDescriptor(u, d);
        if (v && "value" in v) {
          var p = n.get(d);
          p && (v.value = a(p));
        } else if (v === void 0) {
          var y = n.get(d), h = y == null ? void 0 : y.v;
          if (y !== void 0 && h !== ge)
            return {
              enumerable: !0,
              configurable: !0,
              value: h,
              writable: !0
            };
        }
        return v;
      },
      has(u, d) {
        var h;
        if (d === Bn)
          return !0;
        var v = n.get(d), p = v !== void 0 && v.v !== ge || Reflect.has(u, d);
        if (v !== void 0 || K !== null && (!p || (h = vr(u, d)) != null && h.writable)) {
          v === void 0 && (v = o(() => {
            var g = p ? me(u[d]) : ge, k = /* @__PURE__ */ P(g);
            return k;
          }), n.set(d, v));
          var y = a(v);
          if (y === ge)
            return !1;
        }
        return p;
      },
      set(u, d, v, p) {
        var V;
        var y = n.get(d), h = d in u;
        if (r && d === "length")
          for (var g = v; g < /** @type {Source<number>} */
          y.v; g += 1) {
            var k = n.get(g + "");
            k !== void 0 ? b(k, ge) : g in u && (k = o(() => /* @__PURE__ */ P(ge)), n.set(g + "", k));
          }
        if (y === void 0)
          (!h || (V = vr(u, d)) != null && V.writable) && (y = o(() => /* @__PURE__ */ P(void 0)), b(y, me(v)), n.set(d, y));
        else {
          h = y.v !== ge;
          var w = o(() => me(v));
          b(y, w);
        }
        var m = Reflect.getOwnPropertyDescriptor(u, d);
        if (m != null && m.set && m.set.call(p, v), !h) {
          if (r && typeof d == "string") {
            var A = (
              /** @type {Source<number>} */
              n.get("length")
            ), H = Number(d);
            Number.isInteger(H) && H >= A.v && b(A, H + 1);
          }
          mr(s);
        }
        return !0;
      },
      ownKeys(u) {
        a(s);
        var d = Reflect.ownKeys(u).filter((y) => {
          var h = n.get(y);
          return h === void 0 || h.v !== ge;
        });
        for (var [v, p] of n)
          p.v !== ge && !(v in u) && d.push(v);
        return d;
      },
      setPrototypeOf() {
        co();
      }
    }
  );
}
function Ia(e) {
  try {
    if (e !== null && typeof e == "object" && Bn in e)
      return e[Bn];
  } catch {
  }
  return e;
}
function ci(e, t) {
  return Object.is(Ia(e), Ia(t));
}
var Ps, fi, vi, _i, hi;
function Go() {
  if (Ps === void 0) {
    Ps = window, fi = document, vi = /Firefox/.test(navigator.userAgent);
    var e = Element.prototype, t = Node.prototype, n = Text.prototype;
    _i = vr(t, "firstChild").get, hi = vr(t, "nextSibling").get, Aa(e) && (e[ys] = void 0, e[Dr] = null, e[ws] = void 0, e.__e = void 0), Aa(n) && (n[or] = void 0);
  }
}
function mn(e = "") {
  return document.createTextNode(e);
}
// @__NO_SIDE_EFFECTS__
function qr(e) {
  return (
    /** @type {TemplateNode | null} */
    _i.call(e)
  );
}
// @__NO_SIDE_EFFECTS__
function Er(e) {
  return (
    /** @type {TemplateNode | null} */
    hi.call(e)
  );
}
function l(e, t) {
  return /* @__PURE__ */ qr(e);
}
function Oe(e, t = !1) {
  {
    var n = /* @__PURE__ */ qr(e);
    return n instanceof Comment && n.data === "" ? /* @__PURE__ */ Er(n) : n;
  }
}
function f(e, t = 1, n = !1) {
  let r = e;
  for (; t--; )
    r = /** @type {TemplateNode} */
    /* @__PURE__ */ Er(r);
  return r;
}
function Wo(e) {
  e.textContent = "";
}
function mi() {
  return !1;
}
function Jo(e, t, n) {
  return (
    /** @type {T extends keyof HTMLElementTagNameMap ? HTMLElementTagNameMap[T] : Element} */
    n ? document.createElement(e, { is: n }) : document.createElement(e)
  );
}
let Da = !1;
function Ko() {
  Da || (Da = !0, document.addEventListener(
    "reset",
    (e) => {
      Promise.resolve().then(() => {
        var t;
        if (!e.defaultPrevented)
          for (
            const n of
            /**@type {HTMLFormElement} */
            e.target.elements
          )
            (t = n[Nr]) == null || t.call(n);
      });
    },
    // In the capture phase to guarantee we get noticed of it (no possibility of stopPropagation)
    { capture: !0 }
  ));
}
function Xr(e) {
  var t = G, n = K;
  wt(null), Qt(null);
  try {
    return e();
  } finally {
    wt(t), Qt(n);
  }
}
function Qr(e, t, n, r = n) {
  e.addEventListener(t, () => Xr(n));
  const s = (
    /** @type {any} */
    e[Nr]
  );
  s ? e[Nr] = () => {
    s(), r(!0);
  } : e[Nr] = () => r(!0), Ko();
}
function Zo(e) {
  K === null && (G === null && lo(), io()), gn && ao();
}
function Xo(e, t) {
  var n = t.last;
  n === null ? t.last = t.first = e : (n.next = e, e.prev = n, t.last = e);
}
function ln(e, t) {
  var n = K;
  n !== null && n.f & Ve && (e |= Ve);
  var r = {
    ctx: ze,
    deps: null,
    nodes: null,
    f: e | De | gt,
    first: null,
    fn: t,
    last: null,
    next: null,
    parent: n,
    b: n && n.b,
    prev: null,
    teardown: null,
    wv: 0,
    ac: null
  };
  L == null || L.register_created_effect(r);
  var s = r;
  if (e & Xn)
    zn !== null ? zn.push(r) : Nn.ensure().schedule(r);
  else if (t !== null) {
    try {
      tr(r);
    } catch (o) {
      throw Xe(r), o;
    }
    s.deps === null && s.teardown === null && s.nodes === null && s.first === s.last && // either `null`, or a singular child
    !(s.f & rr) && (s = s.first, e & Ft && e & Qn && s !== null && (s.f |= Qn));
  }
  if (s !== null && (s.parent = n, n !== null && Xo(s, n), G !== null && G.f & Ne && !(e & bn))) {
    var i = (
      /** @type {Derived} */
      G
    );
    (i.effects ?? (i.effects = [])).push(s);
  }
  return r;
}
function zs() {
  return G !== null && !jt;
}
function $r(e) {
  const t = ln(Jr, null);
  return pe(t, ye), t.teardown = e, t;
}
function es(e) {
  Zo();
  var t = (
    /** @type {Effect} */
    K.f
  ), n = !G && (t & Vt) !== 0 && ze !== null && !ze.i;
  if (n) {
    var r = (
      /** @type {ComponentContext} */
      ze
    );
    (r.e ?? (r.e = [])).push(e);
  } else
    return pi(e);
}
function pi(e) {
  return ln(Xn | to, e);
}
function Qo(e) {
  Nn.ensure();
  const t = ln(bn | rr, e);
  return (n = {}) => new Promise((r) => {
    n.outro ? Cn(t, () => {
      Xe(t), r(void 0);
    }) : (Xe(t), r(void 0));
  });
}
function bi(e) {
  return ln(Xn, e);
}
function $o(e) {
  return ln(qn | rr, e);
}
function Sr(e, t = 0) {
  return ln(Jr | t, e);
}
function B(e, t = [], n = [], r = []) {
  Mo(r, t, n, (s) => {
    ln(Jr, () => {
      e(...s.map(a));
    });
  });
}
function qs(e, t = 0) {
  var n = ln(Ft | t, e);
  return n;
}
function bt(e) {
  return ln(Vt | rr, e);
}
function gi(e) {
  var t = e.teardown;
  if (t !== null) {
    const n = gn, r = G;
    Na(!0), wt(null);
    try {
      t.call(null);
    } finally {
      Na(n), wt(r);
    }
  }
}
function Bs(e, t = !1) {
  var n = e.first;
  for (e.first = e.last = null; n !== null; ) {
    const s = n.ac;
    s !== null && Xr(() => {
      s.abort(Kr);
    });
    var r = n.next;
    n.f & bn ? n.parent = null : Xe(n, t), n = r;
  }
}
function ed(e) {
  for (var t = e.first; t !== null; ) {
    var n = t.next;
    t.f & Vt || Xe(t), t = n;
  }
}
function Xe(e, t = !0) {
  var n = !1;
  (t || e.f & eo) && e.nodes !== null && e.nodes.end !== null && (td(
    e.nodes.start,
    /** @type {TemplateNode} */
    e.nodes.end
  ), n = !0), e.f |= gs, Bs(e, t && !n), br(e, 0);
  var r = e.nodes && e.nodes.t;
  if (r !== null)
    for (const i of r)
      i.stop();
  gi(e), e.f ^= gs, e.f |= yt;
  var s = e.parent;
  s !== null && s.first !== null && yi(e), e.next = e.prev = e.teardown = e.ctx = e.deps = e.fn = e.nodes = e.ac = e.b = null;
}
function td(e, t) {
  for (; e !== null; ) {
    var n = e === t ? null : /* @__PURE__ */ Er(e);
    e.remove(), e = n;
  }
}
function yi(e) {
  var t = e.parent, n = e.prev, r = e.next;
  n !== null && (n.next = r), r !== null && (r.prev = n), t !== null && (t.first === e && (t.first = r), t.last === e && (t.last = n));
}
function Cn(e, t, n = !0) {
  var r = [];
  wi(e, r, !0);
  var s = () => {
    n && Xe(e), t && t();
  }, i = r.length;
  if (i > 0) {
    var o = () => --i || s();
    for (var u of r)
      u.out(o);
  } else
    s();
}
function wi(e, t, n) {
  if (!(e.f & Ve)) {
    e.f ^= Ve;
    var r = e.nodes && e.nodes.t;
    if (r !== null)
      for (const u of r)
        (u.is_global || n) && t.push(u);
    for (var s = e.first; s !== null; ) {
      var i = s.next;
      if (!(s.f & bn)) {
        var o = (s.f & Qn) !== 0 || // If this is a branch effect without a block effect parent,
        // it means the parent block effect was pruned. In that case,
        // transparency information was transferred to the branch effect.
        (s.f & Vt) !== 0 && (e.f & Ft) !== 0;
        wi(s, t, o ? n : !1);
      }
      s = i;
    }
  }
}
function Br(e) {
  ki(e, !0);
}
function ki(e, t) {
  if (e.f & Ve) {
    e.f ^= Ve, e.f & ye || (pe(e, De), Nn.ensure().schedule(e));
    for (var n = e.first; n !== null; ) {
      var r = n.next, s = (n.f & Qn) !== 0 || (n.f & Vt) !== 0;
      ki(n, s ? t : !1), n = r;
    }
    var i = e.nodes && e.nodes.t;
    if (i !== null)
      for (const o of i)
        (o.is_global || t) && o.in();
  }
}
function Hs(e, t) {
  if (e.nodes)
    for (var n = e.nodes.start, r = e.nodes.end; n !== null; ) {
      var s = n === r ? null : /* @__PURE__ */ Er(n);
      t.append(n), n = s;
    }
}
let Rr = !1, gn = !1;
function Na(e) {
  gn = e;
}
let G = null, jt = !1;
function wt(e) {
  G = e;
}
let K = null;
function Qt(e) {
  K = e;
}
let Zt = null;
function xi(e) {
  G !== null && (Zt ?? (Zt = /* @__PURE__ */ new Set())).add(e);
}
let Ze = null, rt = 0, _t = null;
function nd(e) {
  _t = e;
}
let Ei = 1, wn = 0, In = wn;
function La(e) {
  In = e;
}
function Si() {
  return ++Ei;
}
function Tr(e) {
  var t = e.f;
  if (t & De)
    return !0;
  if (t & Ne && (e.f &= ~Dn), t & Xt) {
    for (var n = (
      /** @type {Value[]} */
      e.deps
    ), r = n.length, s = 0; s < r; s++) {
      var i = n[s];
      if (Tr(
        /** @type {Derived} */
        i
      ) && ni(
        /** @type {Derived} */
        i
      ), i.wv > e.wv)
        return !0;
    }
    t & gt && // During time traveling we don't want to reset the status so that
    // traversal of the graph in the other batches still happens
    Ie === null && pe(e, ye);
  }
  return !1;
}
function Ti(e, t, n = !0) {
  var r = e.reactions;
  if (r !== null && !(Zt !== null && Zt.has(e)))
    for (var s = 0; s < r.length; s++) {
      var i = r[s];
      i.f & Ne ? Ti(
        /** @type {Derived} */
        i,
        t,
        !1
      ) : t === i && (n ? pe(i, De) : i.f & ye && pe(i, Xt), Vs(
        /** @type {Effect} */
        i
      ));
    }
}
function Ai(e) {
  var w;
  var t = Ze, n = rt, r = _t, s = G, i = Zt, o = ze, u = jt, d = In, v = e.f;
  Ze = /** @type {null | Value[]} */
  null, rt = 0, _t = null, G = v & (Vt | bn) ? null : e, Zt = null, $n(e.ctx), jt = !1, In = ++wn, e.ac !== null && (Xr(() => {
    e.ac.abort(Kr);
  }), e.ac = null);
  try {
    e.f |= jr;
    var p = (
      /** @type {Function} */
      e.fn
    ), y = p();
    e.f |= nr;
    var h = e.deps, g = L == null ? void 0 : L.is_fork;
    if (Ze !== null) {
      var k;
      if (g || br(e, rt), h !== null && rt > 0)
        for (h.length = rt + Ze.length, k = 0; k < Ze.length; k++)
          h[rt + k] = Ze[k];
      else
        e.deps = h = Ze;
      if (zs() && e.f & gt)
        for (k = rt; k < h.length; k++)
          ((w = h[k]).reactions ?? (w.reactions = [])).push(e);
    } else !g && h !== null && rt < h.length && (br(e, rt), h.length = rt);
    if (Za() && _t !== null && !jt && h !== null && !(e.f & (Ne | Xt | De)))
      for (k = 0; k < /** @type {Source[]} */
      _t.length; k++)
        Ti(
          _t[k],
          /** @type {Effect} */
          e
        );
    if (s !== null && s !== e) {
      if (wn++, s.deps !== null)
        for (let m = 0; m < n; m += 1)
          s.deps[m].rv = wn;
      if (t !== null)
        for (const m of t)
          m.rv = wn;
      _t !== null && (r === null ? r = _t : r.push(.../** @type {Source[]} */
      _t));
    }
    return e.f & hn && (e.f ^= hn), y;
  } catch (m) {
    return Qa(m);
  } finally {
    e.f ^= jr, Ze = t, rt = n, _t = r, G = s, Zt = i, $n(o), jt = u, In = d;
  }
}
function rd(e, t) {
  let n = t.reactions;
  if (n !== null) {
    var r = Wl.call(n, e);
    if (r !== -1) {
      var s = n.length - 1;
      s === 0 ? n = t.reactions = null : (n[r] = n[s], n.pop());
    }
  }
  if (n === null && t.f & Ne && // Destroying a child effect while updating a parent effect can cause a dependency to appear
  // to be unused, when in fact it is used by the currently-updating parent. Checking `new_deps`
  // allows us to skip the expensive work of disconnecting and immediately reconnecting it
  (Ze === null || !Ur.call(Ze, t))) {
    var i = (
      /** @type {Derived} */
      t
    );
    i.f & gt && (i.f ^= gt, i.f &= ~Dn), i.v !== ge && Us(i), jo(i), br(i, 0);
  }
}
function br(e, t) {
  var n = e.deps;
  if (n !== null)
    for (var r = t; r < n.length; r++)
      rd(e, n[r]);
}
function tr(e) {
  var t = e.f;
  if (!(t & yt)) {
    pe(e, ye);
    var n = K, r = Rr;
    K = e, Rr = !0;
    try {
      t & (Ft | Ga) ? ed(e) : Bs(e), gi(e);
      var s = Ai(e);
      e.teardown = typeof s == "function" ? s : null, e.wv = Ei;
      var i;
    } finally {
      Rr = r, K = n;
    }
  }
}
async function sd() {
  await Promise.resolve(), qo();
}
function a(e) {
  var t = e.f, n = (t & Ne) !== 0;
  if (G !== null && !jt) {
    var r = K !== null && (K.f & yt) !== 0;
    if (!r && (Zt === null || !Zt.has(e))) {
      var s = G.deps;
      if (G.f & jr)
        e.rv < wn && (e.rv = wn, Ze === null && s !== null && s[rt] === e ? rt++ : Ze === null ? Ze = [e] : Ze.push(e));
      else {
        G.deps ?? (G.deps = []), Ur.call(G.deps, e) || G.deps.push(e);
        var i = e.reactions;
        i === null ? e.reactions = [G] : Ur.call(i, G) || i.push(G);
      }
    }
  }
  if (gn && Pn.has(e))
    return Pn.get(e);
  if (n) {
    var o = (
      /** @type {Derived} */
      e
    );
    if (gn) {
      var u = o.v;
      return (!(o.f & ye) && o.reactions !== null || Ci(o)) && (u = Fs(o)), Pn.set(o, u), u;
    }
    var d = (o.f & gt) === 0 && !jt && G !== null && (Rr || (G.f & gt) !== 0), v = (o.f & nr) === 0;
    Tr(o) && (d && (o.f |= gt), ni(o)), d && !v && (ri(o), Pi(o));
  }
  if (Ie != null && Ie.has(e))
    return Ie.get(e);
  if (e.f & hn)
    throw e.v;
  return e.v;
}
function Pi(e) {
  if (e.f |= gt, e.deps !== null)
    for (const t of e.deps)
      (t.reactions ?? (t.reactions = [])).push(e), t.f & Ne && !(t.f & gt) && (ri(
        /** @type {Derived} */
        t
      ), Pi(
        /** @type {Derived} */
        t
      ));
}
function Ci(e) {
  if (e.v === ge) return !0;
  if (e.deps === null) return !1;
  for (const t of e.deps)
    if (Pn.has(t) || t.f & Ne && Ci(
      /** @type {Derived} */
      t
    ))
      return !0;
  return !1;
}
function Ar(e) {
  var t = jt;
  try {
    return jt = !0, e();
  } finally {
    jt = t;
  }
}
const ad = ["touchstart", "touchmove"];
function id(e) {
  return ad.includes(e);
}
const kn = Symbol("events"), Ii = /* @__PURE__ */ new Set(), Cs = /* @__PURE__ */ new Set();
function ld(e, t, n, r = {}) {
  function s(i) {
    if (r.capture || Is.call(t, i), !i.cancelBubble)
      return Xr(() => n == null ? void 0 : n.call(this, i));
  }
  return e.startsWith("pointer") || e.startsWith("touch") || e === "wheel" ? Kt(() => {
    t.addEventListener(e, s, r);
  }) : t.addEventListener(e, s, r), s;
}
function Vn(e, t, n, r, s) {
  var i = { capture: r, passive: s }, o = ld(e, t, n, i);
  (t === document.body || // @ts-ignore
  t === window || // @ts-ignore
  t === document || // Firefox has quirky behavior, it can happen that we still get "canplay" events when the element is already removed
  t instanceof HTMLMediaElement) && $r(() => {
    t.removeEventListener(e, o, i);
  });
}
function M(e, t, n) {
  (t[kn] ?? (t[kn] = {}))[e] = n;
}
function ts(e) {
  for (var t = 0; t < e.length; t++)
    Ii.add(e[t]);
  for (var n of Cs)
    n(e);
}
let Ma = null;
function Is(e) {
  var w, m;
  var t = this, n = (
    /** @type {Node} */
    t.ownerDocument
  ), r = e.type, s = ((w = e.composedPath) == null ? void 0 : w.call(e)) || [], i = (
    /** @type {null | Element} */
    s[0] || e.target
  );
  Ma = e;
  var o = 0, u = Ma === e && e[kn];
  if (u) {
    var d = s.indexOf(u);
    if (d !== -1 && (t === document || t === /** @type {any} */
    window)) {
      e[kn] = t;
      return;
    }
    var v = s.indexOf(t);
    if (v === -1)
      return;
    d <= v && (o = d);
  }
  if (i = /** @type {Element} */
  s[o] || e.target, i !== t) {
    Jl(e, "currentTarget", {
      configurable: !0,
      get() {
        return i || n;
      }
    });
    var p = G, y = K;
    wt(null), Qt(null);
    try {
      for (var h, g = []; i !== null && i !== t; ) {
        try {
          var k = (m = i[kn]) == null ? void 0 : m[r];
          k != null && (!/** @type {any} */
          i.disabled || // DOM could've been updated already by the time this is reached, so we check this as well
          // -> the target could not have been disabled because it emits the event in the first place
          e.target === i) && k.call(i, e);
        } catch (A) {
          h ? g.push(A) : h = A;
        }
        if (e.cancelBubble) break;
        o++, i = o < s.length ? (
          /** @type {Element} */
          s[o]
        ) : null;
      }
      if (h) {
        for (let A of g)
          queueMicrotask(() => {
            throw A;
          });
        throw h;
      }
    } finally {
      e[kn] = t, delete e.currentTarget, wt(p), Qt(y);
    }
  }
}
var qa;
const fs = (
  // We gotta write it like this because after downleveling the pure comment may end up in the wrong location
  ((qa = globalThis == null ? void 0 : globalThis.window) == null ? void 0 : qa.trustedTypes) && /* @__PURE__ */ globalThis.window.trustedTypes.createPolicy("svelte-trusted-html", {
    /** @param {string} html */
    createHTML: (e) => e
  })
);
function od(e) {
  return (
    /** @type {string} */
    (fs == null ? void 0 : fs.createHTML(e)) ?? e
  );
}
function dd(e) {
  var t = Jo("template");
  return t.innerHTML = od(e.replaceAll("<!>", "<!---->")), t.content;
}
function Ds(e, t) {
  var n = (
    /** @type {Effect} */
    K
  );
  n.nodes === null && (n.nodes = { start: e, end: t, a: null, t: null });
}
// @__NO_SIDE_EFFECTS__
function T(e, t) {
  var n = (t & bo) !== 0, r = (t & go) !== 0, s, i = !e.startsWith("<!>");
  return () => {
    s === void 0 && (s = dd(i ? e : "<!>" + e), n || (s = /** @type {TemplateNode} */
    /* @__PURE__ */ qr(s)));
    var o = (
      /** @type {TemplateNode} */
      r || vi ? document.importNode(s, !0) : s.cloneNode(!0)
    );
    if (n) {
      var u = (
        /** @type {TemplateNode} */
        /* @__PURE__ */ qr(o)
      ), d = (
        /** @type {TemplateNode} */
        o.lastChild
      );
      Ds(u, d);
    } else
      Ds(o, o);
    return o;
  };
}
function Di() {
  var e = document.createDocumentFragment(), t = document.createComment(""), n = mn();
  return e.append(t, n), Ds(t, n), e;
}
function E(e, t) {
  e !== null && e.before(
    /** @type {Node} */
    t
  );
}
function I(e, t) {
  var n = t == null ? "" : typeof t == "object" ? `${t}` : t;
  n !== /** @type {any} */
  (e[or] ?? (e[or] = e.nodeValue)) && (e[or] = n, e.nodeValue = `${n}`);
}
function ud(e, t) {
  return cd(e, t);
}
const Ir = /* @__PURE__ */ new Map();
function cd(e, { target: t, anchor: n, props: r = {}, events: s, context: i, intro: o = !0, transformError: u }) {
  Go();
  var d = void 0, v = Qo(() => {
    var p = n ?? t.appendChild(mn());
    Co(
      /** @type {TemplateNode} */
      p,
      {
        pending: () => {
        }
      },
      (g) => {
        Mn({});
        var k = (
          /** @type {ComponentContext} */
          ze
        );
        i && (k.c = i), s && (r.$$events = s), d = e(g, r) || {}, On();
      },
      u
    );
    var y = /* @__PURE__ */ new Set(), h = (g) => {
      for (var k = 0; k < g.length; k++) {
        var w = g[k];
        if (!y.has(w)) {
          y.add(w);
          var m = id(w);
          for (const V of [t, document]) {
            var A = Ir.get(V);
            A === void 0 && (A = /* @__PURE__ */ new Map(), Ir.set(V, A));
            var H = A.get(w);
            H === void 0 ? (V.addEventListener(w, Is, { passive: m }), A.set(w, 1)) : A.set(w, H + 1);
          }
        }
      }
    };
    return h(Wr(Ii)), Cs.add(h), () => {
      var m;
      for (var g of y)
        for (const A of [t, document]) {
          var k = (
            /** @type {Map<string, number>} */
            Ir.get(A)
          ), w = (
            /** @type {number} */
            k.get(g)
          );
          --w == 0 ? (A.removeEventListener(g, Is), k.delete(g), k.size === 0 && Ir.delete(A)) : k.set(g, w);
        }
      Cs.delete(h), p !== n && ((m = p.parentNode) == null || m.removeChild(p));
    };
  });
  return fd.set(d, v), d;
}
let fd = /* @__PURE__ */ new WeakMap();
var Rt, Wt, at, An, kr, xr, Gr;
class vd {
  /**
   * @param {TemplateNode} anchor
   * @param {boolean} transition
   */
  constructor(t, n = !0) {
    /** @type {TemplateNode} */
    nt(this, "anchor");
    /** @type {Map<Batch, Key>} */
    z(this, Rt, /* @__PURE__ */ new Map());
    /**
     * Map of keys to effects that are currently rendered in the DOM.
     * These effects are visible and actively part of the document tree.
     * Example:
     * ```
     * {#if condition}
     * 	foo
     * {:else}
     * 	bar
     * {/if}
     * ```
     * Can result in the entries `true->Effect` and `false->Effect`
     * @type {Map<Key, Effect>}
     */
    z(this, Wt, /* @__PURE__ */ new Map());
    /**
     * Similar to #onscreen with respect to the keys, but contains branches that are not yet
     * in the DOM, because their insertion is deferred.
     * @type {Map<Key, Branch>}
     */
    z(this, at, /* @__PURE__ */ new Map());
    /**
     * Keys of effects that are currently outroing
     * @type {Set<Key>}
     */
    z(this, An, /* @__PURE__ */ new Set());
    /**
     * Whether to pause (i.e. outro) on change, or destroy immediately.
     * This is necessary for `<svelte:element>`
     */
    z(this, kr, !0);
    /**
     * @param {Batch} batch
     */
    z(this, xr, (t) => {
      if (c(this, Rt).has(t)) {
        var n = (
          /** @type {Key} */
          c(this, Rt).get(t)
        ), r = c(this, Wt).get(n);
        if (r)
          Br(r), c(this, An).delete(n);
        else {
          var s = c(this, at).get(n);
          s && (Br(s.effect), c(this, Wt).set(n, s.effect), c(this, at).delete(n), s.fragment.lastChild.remove(), this.anchor.before(s.fragment), r = s.effect);
        }
        for (const [i, o] of c(this, Rt)) {
          if (c(this, Rt).delete(i), i === t)
            break;
          const u = c(this, at).get(o);
          u && (Xe(u.effect), c(this, at).delete(o));
        }
        for (const [i, o] of c(this, Wt)) {
          if (i === n || c(this, An).has(i)) continue;
          const u = () => {
            if (Array.from(c(this, Rt).values()).includes(i)) {
              var v = document.createDocumentFragment();
              Hs(o, v), v.append(mn()), c(this, at).set(i, { effect: o, fragment: v });
            } else
              Xe(o);
            c(this, An).delete(i), c(this, Wt).delete(i);
          };
          c(this, kr) || !r ? (c(this, An).add(i), Cn(o, u, !1)) : u();
        }
      }
    });
    /**
     * @param {Batch} batch
     */
    z(this, Gr, (t) => {
      c(this, Rt).delete(t);
      const n = Array.from(c(this, Rt).values());
      for (const [r, s] of c(this, at))
        n.includes(r) || (Xe(s.effect), c(this, at).delete(r));
    });
    this.anchor = t, j(this, kr, n);
  }
  /**
   *
   * @param {any} key
   * @param {null | ((target: TemplateNode) => void)} fn
   */
  ensure(t, n) {
    var r = (
      /** @type {Batch} */
      L
    ), s = mi();
    if (n && !c(this, Wt).has(t) && !c(this, at).has(t))
      if (s) {
        var i = document.createDocumentFragment(), o = mn();
        i.append(o), c(this, at).set(t, {
          effect: bt(() => n(o)),
          fragment: i
        });
      } else
        c(this, Wt).set(
          t,
          bt(() => n(this.anchor))
        );
    if (c(this, Rt).set(r, t), s) {
      for (const [u, d] of c(this, Wt))
        u === t ? r.unskip_effect(d) : r.skip_effect(d);
      for (const [u, d] of c(this, at))
        u === t ? r.unskip_effect(d.effect) : r.skip_effect(d.effect);
      r.oncommit(c(this, xr)), r.ondiscard(c(this, Gr));
    } else
      c(this, xr).call(this, r);
  }
}
Rt = new WeakMap(), Wt = new WeakMap(), at = new WeakMap(), An = new WeakMap(), kr = new WeakMap(), xr = new WeakMap(), Gr = new WeakMap();
function Y(e, t, n = !1) {
  var r = new vd(e), s = n ? Qn : 0;
  function i(o, u) {
    r.ensure(o, u);
  }
  qs(() => {
    var o = !1;
    t((u, d = 0) => {
      o = !0, i(d, u);
    }), o || i(-1, null);
  }, s);
}
function Ni(e, t) {
  return t;
}
function _d(e, t, n) {
  for (var r = [], s = t.length, i, o = t.length, u = 0; u < s; u++) {
    let y = t[u];
    Cn(
      y,
      () => {
        if (i) {
          if (i.pending.delete(y), i.done.add(y), i.pending.size === 0) {
            var h = (
              /** @type {Set<EachOutroGroup>} */
              e.outrogroups
            );
            Ns(e, Wr(i.done)), h.delete(i), h.size === 0 && (e.outrogroups = null);
          }
        } else
          o -= 1;
      },
      !1
    );
  }
  if (o === 0) {
    var d = r.length === 0 && n !== null;
    if (d) {
      var v = (
        /** @type {Element} */
        n
      ), p = (
        /** @type {Element} */
        v.parentNode
      );
      Wo(p), p.append(v), e.items.clear();
    }
    Ns(e, t, !d);
  } else
    i = {
      pending: new Set(t),
      done: /* @__PURE__ */ new Set()
    }, (e.outrogroups ?? (e.outrogroups = /* @__PURE__ */ new Set())).add(i);
}
function Ns(e, t, n = !0) {
  var r;
  if (e.pending.size > 0) {
    r = /* @__PURE__ */ new Set();
    for (const o of e.pending.values())
      for (const u of o)
        r.add(
          /** @type {EachItem} */
          e.items.get(u).e
        );
  }
  for (var s = 0; s < t.length; s++) {
    var i = t[s];
    if (r != null && r.has(i)) {
      i.f |= Jt;
      const o = document.createDocumentFragment();
      Hs(i, o);
    } else
      Xe(t[s], n);
  }
}
var Oa;
function pn(e, t, n, r, s, i = null) {
  var o = e, u = /* @__PURE__ */ new Map(), d = (t & Wa) !== 0;
  if (d) {
    var v = (
      /** @type {Element} */
      e
    );
    o = v.appendChild(mn());
  }
  var p = null, y = /* @__PURE__ */ Uo(() => {
    var V = n();
    return (
      /** @type {V[]} */
      Rs(V) ? V : V == null ? [] : Wr(V)
    );
  }), h, g = /* @__PURE__ */ new Map(), k = !0;
  function w(V) {
    H.effect.f & yt || (H.pending.delete(V), H.fallback = p, hd(H, h, o, t, r), p !== null && (h.length === 0 ? p.f & Jt ? (p.f ^= Jt, fr(p, null, o)) : Br(p) : Cn(p, () => {
      p = null;
    })));
  }
  function m(V) {
    H.pending.delete(V);
  }
  var A = qs(() => {
    h = /** @type {V[]} */
    a(y);
    for (var V = h.length, F = /* @__PURE__ */ new Set(), Q = (
      /** @type {Batch} */
      L
    ), ae = mi(), te = 0; te < V; te += 1) {
      var _e = h[te], ue = r(_e, te), $ = k ? null : u.get(ue);
      $ ? ($.v && er($.v, _e), $.i && er($.i, te), ae && Q.unskip_effect($.e)) : ($ = md(
        u,
        k ? o : Oa ?? (Oa = mn()),
        _e,
        ue,
        te,
        s,
        t,
        n
      ), k || ($.e.f |= Jt), u.set(ue, $)), F.add(ue);
    }
    if (V === 0 && i && !p && (k ? p = bt(() => i(o)) : (p = bt(() => i(Oa ?? (Oa = mn()))), p.f |= Jt)), V > F.size && so(), !k)
      if (g.set(Q, F), ae) {
        for (const [oe, he] of u)
          F.has(oe) || Q.skip_effect(he.e);
        Q.oncommit(w), Q.ondiscard(m);
      } else
        w(Q);
    a(y);
  }), H = { effect: A, items: u, pending: g, outrogroups: null, fallback: p };
  k = !1;
}
function lr(e) {
  for (; e !== null && !(e.f & Vt); )
    e = e.next;
  return e;
}
function hd(e, t, n, r, s) {
  var $, oe, he, Te, W, J, Z, Ae, Re;
  var i = (r & mo) !== 0, o = t.length, u = e.items, d = lr(e.effect.first), v, p = null, y, h = [], g = [], k, w, m, A;
  if (i)
    for (A = 0; A < o; A += 1)
      k = t[A], w = s(k, A), m = /** @type {EachItem} */
      u.get(w).e, m.f & Jt || ((oe = ($ = m.nodes) == null ? void 0 : $.a) == null || oe.measure(), (y ?? (y = /* @__PURE__ */ new Set())).add(m));
  for (A = 0; A < o; A += 1) {
    if (k = t[A], w = s(k, A), m = /** @type {EachItem} */
    u.get(w).e, e.outrogroups !== null)
      for (const ie of e.outrogroups)
        ie.pending.delete(m), ie.done.delete(m);
    if (m.f & Ve && (Br(m), i && ((Te = (he = m.nodes) == null ? void 0 : he.a) == null || Te.unfix(), (y ?? (y = /* @__PURE__ */ new Set())).delete(m))), m.f & Jt)
      if (m.f ^= Jt, m === d)
        fr(m, null, n);
      else {
        var H = p ? p.next : d;
        m === e.effect.last && (e.effect.last = m.prev), m.prev && (m.prev.next = m.next), m.next && (m.next.prev = m.prev), cn(e, p, m), cn(e, m, H), fr(m, H, n), p = m, h = [], g = [], d = lr(p.next);
        continue;
      }
    if (m !== d) {
      if (v !== void 0 && v.has(m)) {
        if (h.length < g.length) {
          var V = g[0], F;
          p = V.prev;
          var Q = h[0], ae = h[h.length - 1];
          for (F = 0; F < h.length; F += 1)
            fr(h[F], V, n);
          for (F = 0; F < g.length; F += 1)
            v.delete(g[F]);
          cn(e, Q.prev, ae.next), cn(e, p, Q), cn(e, ae, V), d = V, p = ae, A -= 1, h = [], g = [];
        } else
          v.delete(m), fr(m, d, n), cn(e, m.prev, m.next), cn(e, m, p === null ? e.effect.first : p.next), cn(e, p, m), p = m;
        continue;
      }
      for (h = [], g = []; d !== null && d !== m; )
        (v ?? (v = /* @__PURE__ */ new Set())).add(d), g.push(d), d = lr(d.next);
      if (d === null)
        continue;
    }
    m.f & Jt || h.push(m), p = m, d = lr(m.next);
  }
  if (e.outrogroups !== null) {
    for (const ie of e.outrogroups)
      ie.pending.size === 0 && (Ns(e, Wr(ie.done)), (W = e.outrogroups) == null || W.delete(ie));
    e.outrogroups.size === 0 && (e.outrogroups = null);
  }
  if (d !== null || v !== void 0) {
    var te = [];
    if (v !== void 0)
      for (m of v)
        m.f & Ve || te.push(m);
    for (; d !== null; )
      !(d.f & Ve) && d !== e.fallback && te.push(d), d = lr(d.next);
    var _e = te.length;
    if (_e > 0) {
      var ue = r & Wa && o === 0 ? n : null;
      if (i) {
        for (A = 0; A < _e; A += 1)
          (Z = (J = te[A].nodes) == null ? void 0 : J.a) == null || Z.measure();
        for (A = 0; A < _e; A += 1)
          (Re = (Ae = te[A].nodes) == null ? void 0 : Ae.a) == null || Re.fix();
      }
      _d(e, te, ue);
    }
  }
  i && Kt(() => {
    var ie, Pe;
    if (y !== void 0)
      for (m of y)
        (Pe = (ie = m.nodes) == null ? void 0 : ie.a) == null || Pe.apply();
  });
}
function md(e, t, n, r, s, i, o, u) {
  var d = o & _o ? o & po ? Ln(n) : /* @__PURE__ */ Ho(n, !1, !1) : null, v = o & ho ? Ln(s) : null;
  return {
    v: d,
    i: v,
    e: bt(() => (i(t, d ?? n, v ?? s, u), () => {
      e.delete(r);
    }))
  };
}
function fr(e, t, n) {
  if (e.nodes)
    for (var r = e.nodes.start, s = e.nodes.end, i = t && !(t.f & Jt) ? (
      /** @type {EffectNodes} */
      t.nodes.start
    ) : n; r !== null; ) {
      var o = (
        /** @type {TemplateNode} */
        /* @__PURE__ */ Er(r)
      );
      if (i.before(r), r === s)
        return;
      r = o;
    }
}
function cn(e, t, n) {
  t === null ? e.effect.first = n : t.next = n, n === null ? e.effect.last = t : n.prev = t;
}
function Li(e) {
  var t, n, r = "";
  if (typeof e == "string" || typeof e == "number") r += e;
  else if (typeof e == "object") if (Array.isArray(e)) {
    var s = e.length;
    for (t = 0; t < s; t++) e[t] && (n = Li(e[t])) && (r && (r += " "), r += n);
  } else for (n in e) e[n] && (r && (r += " "), r += n);
  return r;
}
function pd() {
  for (var e, t, n = 0, r = "", s = arguments.length; n < s; n++) (e = arguments[n]) && (t = Li(e)) && (r && (r += " "), r += t);
  return r;
}
function Mi(e) {
  return typeof e == "object" ? pd(e) : e ?? "";
}
const Ra = [...` 	
\r\f \v\uFEFF`];
function bd(e, t, n) {
  var r = e == null ? "" : "" + e;
  if (t && (r = r ? r + " " + t : t), n) {
    for (var s of Object.keys(n))
      if (n[s])
        r = r ? r + " " + s : s;
      else if (r.length)
        for (var i = s.length, o = 0; (o = r.indexOf(s, o)) >= 0; ) {
          var u = o + i;
          (o === 0 || Ra.includes(r[o - 1])) && (u === r.length || Ra.includes(r[u])) ? r = (o === 0 ? "" : r.substring(0, o)) + r.substring(u + 1) : o = u;
        }
  }
  return r === "" ? null : r;
}
function Ua(e, t = !1) {
  var n = t ? " !important;" : ";", r = "";
  for (var s of Object.keys(e)) {
    var i = e[s];
    i != null && i !== "" && (r += " " + s + ": " + i + n);
  }
  return r;
}
function gd(e, t) {
  if (t) {
    var n = "", r, s;
    return Array.isArray(t) ? (r = t[0], s = t[1]) : r = t, r && (n += Ua(r)), s && (n += Ua(s, !0)), n = n.trim(), n === "" ? null : n;
  }
  return String(e);
}
function je(e, t, n, r, s, i) {
  var o = (
    /** @type {any} */
    e[ys]
  );
  if (o !== n || o === void 0) {
    var u = bd(n, r, i);
    u == null ? e.removeAttribute("class") : e.className = u, e[ys] = n;
  } else if (i && s !== i)
    for (var d in i) {
      var v = !!i[d];
      (s == null || v !== !!s[d]) && e.classList.toggle(d, v);
    }
  return i;
}
function vs(e, t = {}, n, r) {
  for (var s in n) {
    var i = n[s];
    t[s] !== i && (n[s] == null ? e.style.removeProperty(s) : e.style.setProperty(s, i, r));
  }
}
function Se(e, t, n, r) {
  var s = (
    /** @type {any} */
    e[ws]
  );
  if (s !== t) {
    var i = gd(t, r);
    i == null ? e.removeAttribute("style") : e.style.cssText = i, e[ws] = t;
  } else r && (Array.isArray(r) ? (vs(e, n == null ? void 0 : n[0], r[0]), vs(e, n == null ? void 0 : n[1], r[1], "important")) : vs(e, n, r));
  return r;
}
function Ys(e, t, n = !1) {
  if (e.multiple) {
    if (t == null)
      return;
    if (!Rs(t))
      return ko();
    for (var r of e.options)
      r.selected = t.includes(pr(r));
    return;
  }
  for (r of e.options) {
    var s = pr(r);
    if (ci(s, t)) {
      r.selected = !0;
      return;
    }
  }
  (!n || t !== void 0) && (e.selectedIndex = -1);
}
function Oi(e) {
  var t = new MutationObserver(() => {
    Ys(e, e.__value);
  });
  t.observe(e, {
    // Listen to option element changes
    childList: !0,
    subtree: !0,
    // because of <optgroup>
    // Listen to option element value attribute changes
    // (doesn't get notified of select value changes,
    // because that property is not reflected as an attribute)
    attributes: !0,
    attributeFilter: ["value"]
  }), $r(() => {
    t.disconnect();
  });
}
function Gs(e, t, n = t) {
  var r = /* @__PURE__ */ new WeakSet(), s = !0;
  Qr(e, "change", (i) => {
    var o = i ? "[selected]" : ":checked", u;
    if (e.multiple)
      u = [].map.call(e.querySelectorAll(o), pr);
    else {
      var d = e.querySelector(o) ?? // will fall back to first non-disabled option if no option is selected
      e.querySelector("option:not([disabled])");
      u = d && pr(d);
    }
    n(u), e.__value = u, L !== null && r.add(L);
  }), bi(() => {
    var i = t();
    if (e === document.activeElement) {
      var o = (
        /** @type {Batch} */
        L
      );
      if (r.has(o))
        return;
    }
    if (Ys(e, i, s), s && i === void 0) {
      var u = e.querySelector(":checked");
      u !== null && (i = pr(u), n(i));
    }
    e.__value = i, s = !1;
  }), Oi(e);
}
function pr(e) {
  return "__value" in e ? e.__value : e.value;
}
const yd = Symbol("is custom element"), wd = Symbol("is html");
function Ls(e, t) {
  var n = Ri(e);
  n.checked !== (n.checked = // treat null and undefined the same for the initial value
  t ?? void 0) && (e.checked = t);
}
function Ee(e, t, n, r) {
  var s = Ri(e);
  s[t] !== (s[t] = n) && (t === "loading" && (e[no] = n), n == null ? e.removeAttribute(t) : typeof n != "string" && kd(e).includes(t) ? e[t] = n : e.setAttribute(t, n));
}
function Ri(e) {
  return (
    /** @type {Record<string | symbol, unknown>} **/
    /** @type {any} */
    e[Dr] ?? (e[Dr] = {
      [yd]: e.nodeName.includes("-"),
      [wd]: e.namespaceURI === yo
    })
  );
}
var Fa = /* @__PURE__ */ new Map();
function kd(e) {
  var t = e.getAttribute("is") || e.nodeName, n = Fa.get(t);
  if (n) return n;
  Fa.set(t, n = []);
  for (var r, s = e, i = Element.prototype; i !== s; ) {
    r = Kl(s);
    for (var o in r)
      r[o].set && // better safe than sorry, we don't want spread attributes to mess with HTML content
      o !== "innerHTML" && o !== "textContent" && o !== "innerText" && n.push(o);
    s = Ha(s);
  }
  return n;
}
function We(e, t, n = t) {
  var r = /* @__PURE__ */ new WeakSet();
  Qr(e, "input", async (s) => {
    var i = s ? e.defaultValue : e.value;
    if (i = hs(e) ? ms(i) : i, n(i), L !== null && r.add(L), await sd(), i !== (i = t())) {
      var o = e.selectionStart, u = e.selectionEnd, d = e.value.length;
      if (e.value = i ?? "", u !== null) {
        var v = e.value.length;
        o === u && u === d && v > d ? (e.selectionStart = v, e.selectionEnd = v) : (e.selectionStart = o, e.selectionEnd = Math.min(u, v));
      }
    }
  }), // If we are hydrating and the value has since changed,
  // then use the updated value from the input instead.
  // If defaultValue is set, then value == defaultValue
  // TODO Svelte 6: remove input.value check and set to empty string?
  Ar(t) == null && e.value && (n(hs(e) ? ms(e.value) : e.value), L !== null && r.add(L)), Sr(() => {
    var s = t();
    if (e === document.activeElement) {
      var i = (
        /** @type {Batch} */
        L
      );
      if (r.has(i))
        return;
    }
    hs(e) && s === ms(e.value) || e.type === "date" && !s && !e.value || s !== e.value && (e.value = s ?? "");
  });
}
const _s = /* @__PURE__ */ new Set();
function ja(e, t, n, r, s = r) {
  var i = n.getAttribute("type") === "checkbox", o = e;
  if (t !== null)
    for (var u of t)
      o = o[u] ?? (o[u] = []);
  o.push(n), Qr(
    n,
    "change",
    () => {
      var d = n.__value;
      i && (d = xd(o, d, n.checked)), s(d);
    },
    // TODO better default value handling
    () => s(i ? [] : null)
  ), Sr(() => {
    var d = r();
    i ? (d = d || [], n.checked = d.includes(n.__value)) : n.checked = ci(n.__value, d);
  }), $r(() => {
    var d = o.indexOf(n);
    d !== -1 && o.splice(d, 1);
  }), _s.has(o) || (_s.add(o), Kt(() => {
    o.sort((d, v) => d.compareDocumentPosition(v) === 4 ? -1 : 1), _s.delete(o);
  })), Kt(() => {
  });
}
function Va(e, t, n = t) {
  Qr(e, "change", (r) => {
    var s = r ? e.defaultChecked : e.checked;
    n(s);
  }), // If we are hydrating and the value has since changed,
  // then use the update value from the input instead.
  // If defaultChecked is set, then checked == defaultChecked
  Ar(t) == null && n(e.checked), Sr(() => {
    var r = t();
    e.checked = !!r;
  });
}
function xd(e, t, n) {
  for (var r = /* @__PURE__ */ new Set(), s = 0; s < e.length; s += 1)
    e[s].checked && r.add(e[s].__value);
  return n || r.delete(t), Array.from(r);
}
function hs(e) {
  var t = e.type;
  return t === "number" || t === "range";
}
function ms(e) {
  return e === "" ? null : +e;
}
function ps(e, t) {
  return e === t || (e == null ? void 0 : e[Bn]) === t;
}
function Ed(e = {}, t, n, r) {
  var s = (
    /** @type {ComponentContext} */
    ze.r
  ), i = (
    /** @type {Effect} */
    K
  );
  return bi(() => {
    var o, u;
    return Sr(() => {
      o = u, u = [], Ar(() => {
        ps(n(...u), e) || (t(e, ...u), o && ps(n(...o), e) && t(null, ...o));
      });
    }), () => {
      let d = i;
      for (; d !== s && d.parent !== null && d.parent.f & gs; )
        d = d.parent;
      const v = () => {
        u && ps(n(...u), e) && t(null, ...u);
      }, p = d.teardown;
      d.teardown = () => {
        v(), p == null || p();
      };
    };
  }), e;
}
function Ms(e, t, n, r) {
  var s = (
    /** @type {Derived<V> | undefined} */
    void 0
  ), i = () => (s ?? (s = /* @__PURE__ */ Zr(
    /** @type {() => V} */
    r
  )), a(s)), o;
  o = /** @type {V} */
  e[t], o === void 0 && r !== void 0 && (o = i());
  var u;
  return u = () => {
    var d = (
      /** @type {V} */
      e[t]
    );
    return d === void 0 ? i() : d;
  }, u;
}
const Sd = "5";
var Ba;
typeof window < "u" && ((Ba = window.__svelte ?? (window.__svelte = {})).v ?? (Ba.v = /* @__PURE__ */ new Set())).add(Sd);
var Td = /* @__PURE__ */ T('<a target="_blank" rel="noopener noreferrer"> </a>'), Ad = /* @__PURE__ */ T('<span class="text-muted">Not a member</span>'), Pd = /* @__PURE__ */ T('<span id="instruments-display"> </span>'), Cd = /* @__PURE__ */ T('<span id="instruments-display" class="text-muted">No instruments listed</span>'), Id = /* @__PURE__ */ T('<button type="button" class="typeahead-option"> </button>'), Dd = /* @__PURE__ */ T('<div class="text-muted small">No instruments yet — add one above.</div>'), Nd = /* @__PURE__ */ T('<div class="instrument-row" role="button" tabindex="0"><span> </span> <span> </span></div>'), Ld = /* @__PURE__ */ T('<span class="admin-indicator">(admin)</span>'), Md = /* @__PURE__ */ T('<span class="text-success">✓ Verified</span>'), Od = /* @__PURE__ */ T('<button id="verify-email-btn" class="btn btn-sm btn-success ms-2"> </button>'), Rd = /* @__PURE__ */ T('<span class="text-warning">✗ Not verified</span> <!>', 1), Ud = /* @__PURE__ */ T('<span class="text-success">✓ On</span>'), Fd = /* @__PURE__ */ T('<span class="text-muted">Off</span>'), jd = /* @__PURE__ */ T('<button id="beta-logging-btn" class="btn btn-sm btn-outline-primary ms-2"> </button>'), Vd = /* @__PURE__ */ T('<span class="text-success">✓ Active</span>'), zd = /* @__PURE__ */ T('<span class="text-danger">✗ Inactive</span>'), qd = /* @__PURE__ */ T('<span class="text-success">✓ Subscribed</span>'), Bd = /* @__PURE__ */ T('<span class="text-muted">Not subscribed</span>'), Hd = /* @__PURE__ */ T('<div class="mt-3"><a href="/change-password" class="btn btn-outline-primary"> </a></div>'), Yd = /* @__PURE__ */ T("<option> </option>"), Gd = /* @__PURE__ */ T('<div class="mb-3"><div class="form-check"><input class="form-check-input" type="checkbox" id="is_active" name="is_active"/> <label class="form-check-label" for="is_active">User Account Active</label></div></div>'), Wd = /* @__PURE__ */ T('<div class="mb-3"><div class="form-check"><input class="form-check-input" type="checkbox" id="receive_update_emails" name="receive_update_emails"/> <label class="form-check-label" for="receive_update_emails">Get regular updates about this app via email</label></div></div>'), Jd = /* @__PURE__ */ T('<div id="user-display" class="row"><div class="col-md-6"><dl class="row mb-0"><dt class="col-sm-4">Username:</dt> <dd class="col-sm-8"><strong> </strong> <!></dd> <dt class="col-sm-4">User Email:</dt> <dd class="col-sm-8"> </dd> <dt class="col-sm-4">Email Verified:</dt> <dd class="col-sm-8"><!></dd> <dt class="col-sm-4">Live editor (beta):</dt> <dd class="col-sm-8"><span id="beta-logging-status"><!></span> <!></dd></dl></div> <div class="col-md-6"><dl class="row mb-0"><dt class="col-sm-4">Active:</dt> <dd class="col-sm-8"><!></dd> <dt class="col-sm-4">Created:</dt> <dd class="col-sm-8"> </dd> <dt class="col-sm-4">Last Login:</dt> <dd class="col-sm-8"> </dd> <dt class="col-sm-4">Timezone:</dt> <dd class="col-sm-8"> </dd> <dt class="col-sm-4">Update Emails:</dt> <dd class="col-sm-8"><!></dd></dl></div></div> <!> <div id="user-edit" class="row"><form id="user-form"><div class="row"><div class="col-md-6"><div class="mb-3"><label for="username" class="form-label">Username</label> <input type="text" class="form-control" id="username" name="username" required=""/> <div id="username-warning" class="text-warning"> </div></div> <div class="mb-3"><label for="user_email" class="form-label">Email</label> <input type="email" class="form-control" id="user_email" name="user_email"/></div> <div class="mb-3"><label for="timezone" class="form-label">Timezone</label> <select class="form-select" id="timezone" name="timezone"></select></div></div> <div class="col-md-6"><!> <!></div></div></form></div>', 1), Kd = /* @__PURE__ */ T('<div class="alert alert-info mb-0" role="alert"><p class="mb-0">This person is not connected with a user account.</p></div>'), Zd = /* @__PURE__ */ T('<h6 class="text-danger">Deactivate Person</h6> <p class="text-muted"> </p> <button type="button" class="btn btn-outline-danger" id="deactivate-person-btn"> </button>', 1), Xd = /* @__PURE__ */ T('<div class="alert alert-warning mb-3"><strong>This person is deactivated.</strong> They cannot be added to sessions, session instances, or tune sets.</div> <h6 class="text-success">Reactivate Person</h6> <p class="text-muted"> </p> <button type="button" class="btn btn-success" id="reactivate-person-btn"> </button>', 1), Qd = /* @__PURE__ */ T("<div> </div>"), $d = /* @__PURE__ */ T('<div class="card mt-4 border-danger" id="danger-zone"><div class="card-header bg-danger text-white"><h5 class="mb-0">Danger Zone</h5></div> <div class="card-body"><!> <div id="toggle-active-status" class="mt-3"><!></div></div></div>'), eu = /* @__PURE__ */ T(`<div id="instrument-config-modal" class="pd-modal-overlay" style="display:flex;" role="presentation"><div class="pd-modal"><div class="pd-modal-header"><span id="instrument-config-title"> </span> <button type="button" class="pd-modal-close">&times;</button></div> <div class="pd-modal-body"><div class="form-check"><input class="form-check-input" type="radio" name="instrument-auto" id="inst-auto-radio" value="auto"/> <label class="form-check-label" for="inst-auto-radio"><strong>Auto</strong> — follows the tune's main status. When you mark a tune learned, it's learned on this instrument.</label></div> <div class="form-check"><input class="form-check-input" type="radio" name="instrument-auto" id="inst-manual-radio" value="manual"/> <label class="form-check-label" for="inst-manual-radio"><strong>Manual</strong> — a curated list you set per tune. Starts empty; you add tunes to it one at a time.</label></div></div> <div class="pd-modal-footer"><a class="pd-modal-remove" href="#remove">Remove from profile</a></div></div></div>`), tu = /* @__PURE__ */ T('<div id="instrument-remove-confirm-modal" class="pd-modal-overlay" style="display:flex;" role="presentation"><div class="pd-modal"><div class="pd-modal-header"><span>Remove instrument?</span> <button type="button" class="pd-modal-close">&times;</button></div> <div class="pd-modal-body"><p id="instrument-remove-warn" class="pd-modal-warn">Removing <strong> </strong> </p></div> <div class="pd-modal-footer confirm"><button type="button" class="pd-btn">Cancel</button> <button type="button" class="pd-btn pd-btn-danger">Remove anyway</button></div></div></div>'), nu = /* @__PURE__ */ T('<div class="mt-3"><div class="edit-controls mb-3"><button id="edit-btn" class="btn btn-primary">Edit</button> <div id="edit-buttons"><button id="save-btn" class="btn btn-success">Save</button> <button id="cancel-btn" class="btn btn-secondary">Cancel</button></div></div> <div class="card mb-3"><div class="card-header"><h5 class="mb-0">Personal Information</h5></div> <div class="card-body"><div id="person-display" class="row"><div class="col-md-6"><dl class="row mb-0"><dt class="col-sm-4">Name:</dt> <dd class="col-sm-8"> </dd> <dt class="col-sm-4">Email:</dt> <dd class="col-sm-8"> </dd> <dt class="col-sm-4">SMS Number:</dt> <dd class="col-sm-8"> </dd></dl></div> <div class="col-md-6"><dl class="row mb-0"><dt class="col-sm-4">City:</dt> <dd class="col-sm-8"> </dd> <dt class="col-sm-4">State:</dt> <dd class="col-sm-8"> </dd> <dt class="col-sm-4">Country:</dt> <dd class="col-sm-8"> </dd> <dt class="col-sm-4">TheSession.org:</dt> <dd class="col-sm-8"><!></dd></dl></div> <div class="col-12 mt-2"><dl class="row mb-0"><dt class="col-sm-2">Instruments:</dt> <dd class="col-sm-10"><!></dd></dl></div></div> <div id="person-edit" class="row"><form id="person-form"><div class="row"><div class="col-md-6"><div class="mb-3"><label for="first_name" class="form-label">First Name</label> <input type="text" class="form-control" id="first_name" name="first_name" required=""/></div> <div class="mb-3"><label for="last_name" class="form-label">Last Name</label> <input type="text" class="form-control" id="last_name" name="last_name" required=""/></div> <div class="mb-3"><label for="email" class="form-label">Email</label> <input type="email" class="form-control" id="email" name="email"/></div></div> <div class="col-md-6"><div class="mb-3"><label for="sms_number" class="form-label">SMS Number</label> <input type="text" class="form-control" id="sms_number" name="sms_number"/></div> <div class="mb-3"><label for="city" class="form-label">City</label> <input type="text" class="form-control" id="city" name="city"/></div> <div class="mb-3"><label for="state" class="form-label">State</label> <input type="text" class="form-control" id="state" name="state"/></div> <div class="mb-3"><label for="country" class="form-label">Country</label> <input type="text" class="form-control" id="country" name="country"/></div> <div class="mb-3"><label for="thesession_user_id" class="form-label">TheSession User ID</label> <input type="number" class="form-control" id="thesession_user_id" name="thesession_user_id"/></div></div></div> <div class="row"><div class="col-12"><div class="mb-3"><label class="form-label" for="instrument-typeahead">Instruments</label> <div class="text-muted small mb-2">Changes save immediately. Click an instrument to set it auto/manual or remove it.</div> <div class="instrument-typeahead-wrap"><input type="text" id="instrument-typeahead" class="form-control" placeholder="Add an instrument…" autocomplete="off"/> <div id="instrument-typeahead-menu" class="typeahead-menu"></div></div> <div id="instrument-rows" class="mt-2"><!></div></div></div></div></form></div></div></div> <div class="card"><div class="card-header"><h5 class="mb-0">Account Information</h5></div> <div class="card-body"><!></div></div> <div id="bottom-edit-buttons" class="mt-3"><button id="bottom-save-btn" class="btn btn-success">Save</button> <button id="bottom-cancel-btn" class="btn btn-secondary">Cancel</button></div> <!></div> <!> <!>', 1);
function ru(e, t) {
  Mn(t, !0);
  let n = Ms(t, "timezoneOptions", 19, () => []), r = Ms(t, "canonicalInstruments", 19, () => []);
  const s = (_, S) => window.showMessage && window.showMessage(_, S);
  let i = /* @__PURE__ */ P(!1), o = /* @__PURE__ */ P(me(t.person.first_name || "")), u = /* @__PURE__ */ P(me(t.person.last_name || "")), d = /* @__PURE__ */ P(me(t.person.email || "")), v = /* @__PURE__ */ P(me(t.person.sms_number || "")), p = /* @__PURE__ */ P(me(t.person.city || "")), y = /* @__PURE__ */ P(me(t.person.state || "")), h = /* @__PURE__ */ P(me(t.person.country || "")), g = /* @__PURE__ */ P(me(t.person.thesession_user_id != null ? String(t.person.thesession_user_id) : "")), k = /* @__PURE__ */ P(me(t.user && t.user.username || "")), w = /* @__PURE__ */ P(me(t.user && t.user.user_email || "")), m = /* @__PURE__ */ P(me(t.user ? t.user.timezone : null)), A = /* @__PURE__ */ P(me(t.user ? !!t.user.is_active : !1)), H = /* @__PURE__ */ P(me(t.user ? !!t.user.receive_update_emails : !1));
  const V = t.user && t.user.username || "";
  let F = /* @__PURE__ */ P("");
  const Q = (_) => _ ? _.slice(0, 16).replace("T", " ") : null;
  function ae(_) {
    b(i, _, !0), _ ? lt() : b(F, "");
  }
  function te(_) {
    fetch("/api/check-username-availability", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: _,
        current_user_id: t.user ? t.user.user_id : null
      })
    }).then((S) => S.json()).then((S) => {
      b(F, S.available ? "" : S.message, !0);
    }).catch((S) => {
      console.error("Error checking username:", S);
    });
  }
  function _e() {
    const _ = a(k);
    _ !== V && _.trim() !== "" ? te(_.trim()) : b(F, "");
  }
  function ue() {
    const _ = t.user ? a(k).trim() : V;
    if (a(F) && _ !== V) {
      alert("Please fix the username issue before saving.");
      return;
    }
    const S = { person_id: t.personId, person: {}, user: {} };
    S.person = {
      first_name: a(o).trim() || null,
      last_name: a(u).trim() || null,
      email: a(d).trim() || null,
      sms_number: a(v).trim() || null,
      city: a(p).trim() || null,
      state: a(y).trim() || null,
      country: a(h).trim() || null,
      thesession_user_id: String(a(g)).trim() || null
    }, t.user && (S.user = {
      username: a(k).trim() || null,
      user_email: a(w).trim() || null,
      timezone: a(m) || null,
      user_id: t.user.user_id
    }, t.isUserProfile ? S.user.receive_update_emails = a(H) : S.user.is_active = a(A)), fetch(`/api/person/${t.personId}/update`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(S)
    }).then((U) => U.json()).then((U) => {
      if (!U.success)
        throw new Error(U.message || "Failed to update person data");
      sessionStorage.setItem("personSavedMessage", "Profile updated successfully"), window.location.reload();
    }).catch((U) => {
      console.error("Error saving changes:", U), s("Error saving changes. Please try again.", "error");
    });
  }
  let $ = /* @__PURE__ */ P(!1), oe = /* @__PURE__ */ P("Verify Email");
  function he() {
    confirm("Are you sure you want to manually verify this email address?") && (b($, !0), b(oe, "Verifying..."), fetch(`/api/admin/user/${t.user.user_id}/verify-email`, {
      method: "POST",
      headers: { "Content-Type": "application/json" }
    }).then((_) => _.json()).then((_) => {
      _.success ? (s(_.message, "success"), setTimeout(
        () => {
          window.location.reload();
        },
        1e3
      )) : (s("Error: " + _.message, "error"), b($, !1), b(oe, "Verify Email"));
    }).catch((_) => {
      s("Error verifying email: " + _.message, "error"), b($, !1), b(oe, "Verify Email");
    }));
  }
  let Te = /* @__PURE__ */ P(!1);
  function W() {
    const _ = !t.user.beta_live_logging;
    b(Te, !0), fetch(`/api/admin/users/${t.user.user_id}/beta-logging`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled: _ })
    }).then((S) => S.json()).then((S) => {
      S.success ? (s("Live editor (beta) " + (_ ? "enabled" : "disabled") + " for this user.", "success"), setTimeout(() => window.location.reload(), 800)) : (s("Error: " + (S.error || "failed"), "error"), b(Te, !1));
    }).catch((S) => {
      s("Error: " + S.message, "error"), b(Te, !1);
    });
  }
  let J = /* @__PURE__ */ P(me(
    []
    // [{instrument, is_auto, removal_loss_count}]
  )), Z = /* @__PURE__ */ P(
    null
    // instrument name open in the config modal
  ), Ae = /* @__PURE__ */ P(
    null
    // instrument awaiting the data-loss confirmation
  ), Re = /* @__PURE__ */ P(
    null
    // {name, tunesText}
  ), ie = /* @__PURE__ */ P(""), Pe = /* @__PURE__ */ P(!1), it = /* @__PURE__ */ P(null);
  function lt() {
    fetch(`/api/person/${t.personId}/instruments`).then((_) => _.json()).then((_) => {
      b(J, _ && _.instruments ? _.instruments : [], !0);
    }).catch(() => {
      b(J, [], !0);
    });
  }
  function ot() {
    return fetch(`/api/person/${t.personId}/instruments`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        instruments: a(J).map((_) => _.instrument)
      })
    }).then((_) => _.json());
  }
  function zt(_) {
    if (_ = (_ || "").trim(), !!_) {
      if (a(J).some((S) => S.instrument.toLowerCase() === _.toLowerCase())) {
        b(Pe, !1);
        return;
      }
      b(
        J,
        [
          ...a(J),
          { instrument: _, is_auto: !0 }
        ].sort((S, U) => S.instrument.localeCompare(U.instrument)),
        !0
      ), b(ie, ""), b(Pe, !1), ot().then(lt);
    }
  }
  const qe = /* @__PURE__ */ Ut(() => {
    const _ = a(ie).trim().toLowerCase(), S = new Set(a(J).map((se) => se.instrument.toLowerCase())), fe = r().filter((se) => se.toLowerCase().includes(_) && !S.has(se.toLowerCase())).map((se) => ({ value: se, label: se }));
    return _ && !r().some((se) => se.toLowerCase() === _) && !S.has(_) && fe.push({
      value: a(ie).trim(),
      label: `Add "${a(ie).trim()}"`
    }), fe;
  });
  function kt() {
    b(Pe, a(qe).length > 0);
  }
  function $t(_) {
    _.key === "Enter" ? (_.preventDefault(), a(ie).trim() && zt(a(ie).trim())) : _.key === "Escape" && b(Pe, !1);
  }
  function xt(_) {
    a(it) && !a(it).contains(_.target) && b(Pe, !1);
  }
  function dt(_) {
    b(Z, _, !0);
  }
  function ut() {
    b(Z, null);
  }
  const Et = /* @__PURE__ */ Ut(() => a(J).find((_) => _.instrument === a(Z)) || null);
  function St(_) {
    if (!a(Z)) return;
    const S = a(J).find((U) => U.instrument === a(Z));
    S && (S.is_auto = _), b(J, [...a(J)], !0), fetch(`/api/person/${t.personId}/instrument-auto`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ instrument: a(Z), is_auto: _ })
      // Reload either way: on failure to revert, on success to refresh each
      // instrument's removal_loss_count (auto vs manual changes what a removal loses).
    }).then((U) => U.json()).then(() => lt());
  }
  function qt() {
    if (!a(Z)) return;
    const _ = a(J).find((U) => U.instrument === a(Z)), S = _ && _.removal_loss_count || 0;
    if (S > 0) {
      b(Ae, a(Z), !0), b(
        Re,
        {
          name: a(Z),
          tunesText: S === 1 ? "1 tune" : S + " tunes"
        },
        !0
      ), ut();
      return;
    }
    Tt(a(Z)), ut();
  }
  function Tt(_) {
    b(J, a(J).filter((S) => S.instrument !== _), !0), ot().then(lt);
  }
  function on() {
    a(Ae) && Tt(a(Ae)), At();
  }
  function At() {
    b(Ae, null), b(Re, null);
  }
  let Ue = /* @__PURE__ */ P(
    null
    // null hidden; else {kind, text}
  );
  function Bt(_) {
    confirm(`Are you sure you want to ${_ ? "reactivate" : "deactivate"} ${t.person.name}?`) && (b(Ue, { kind: "info", text: "Processing..." }, !0), fetch(`/api/admin/person/${t.personId}/active`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ active: _ })
    }).then((U) => U.json()).then((U) => {
      U.success ? (s(U.message, "success"), setTimeout(
        () => {
          window.location.reload();
        },
        1e3
      )) : b(Ue, { kind: "danger", text: U.message }, !0);
    }).catch((U) => {
      console.error("Error toggling person active status:", U), b(Ue, { kind: "danger", text: "Error: " + U.message }, !0);
    }));
  }
  var en = nu();
  Vn("click", fi, xt);
  var dn = Oe(en), Pt = l(dn), Ct = l(Pt);
  let x;
  var R = f(Ct, 2);
  let X;
  var we = l(R), de = f(we, 2), Ce = f(Pt, 2), le = f(l(Ce), 2), be = l(le);
  let Le;
  var N = l(be), O = l(N), D = f(l(O), 2), ne = l(D), ce = f(D, 4), Me = l(ce), Be = f(ce, 4), It = l(Be), Qe = f(N, 2), tn = l(Qe), un = f(l(tn), 2), Rn = l(un), Un = f(un, 4), ns = l(Un), Pr = f(Un, 4), rs = l(Pr), ss = f(Pr, 4), He = l(ss);
  {
    var Ye = (_) => {
      var S = Td(), U = l(S);
      B(() => {
        Ee(S, "href", `https://thesession.org/members/${t.person.thesession_user_id ?? ""}`), I(U, t.person.thesession_user_id);
      }), E(_, S);
    }, ct = (_) => {
      var S = Ad();
      E(_, S);
    };
    Y(He, (_) => {
      t.person.thesession_user_id ? _(Ye) : _(ct, -1);
    });
  }
  var sr = f(Qe, 2), as = l(sr), Ui = f(l(as), 2), Fi = l(Ui);
  {
    var ji = (_) => {
      var S = Pd(), U = l(S);
      B((fe) => I(U, fe), [() => t.person.instruments.join(", ")]), E(_, S);
    }, Vi = (_) => {
      var S = Cd();
      E(_, S);
    };
    Y(Fi, (_) => {
      t.person.instruments && t.person.instruments.length ? _(ji) : _(Vi, -1);
    });
  }
  var Ws = f(be, 2);
  let Js;
  var Ks = l(Ws), Zs = l(Ks), Xs = l(Zs), Qs = l(Xs), zi = f(l(Qs), 2), $s = f(Qs, 2), qi = f(l($s), 2), Bi = f($s, 2), Hi = f(l(Bi), 2), Yi = f(Xs, 2), ea = l(Yi), Gi = f(l(ea), 2), ta = f(ea, 2), Wi = f(l(ta), 2), na = f(ta, 2), Ji = f(l(na), 2), ra = f(na, 2), Ki = f(l(ra), 2), Zi = f(ra, 2), Xi = f(l(Zi), 2), Qi = f(Zs, 2), $i = l(Qi), el = l($i), is = f(l(el), 4), ar = l(is), sa = f(ar, 2);
  let aa;
  pn(sa, 21, () => a(qe), (_) => _.value, (_, S) => {
    var U = Id(), fe = l(U);
    B(() => I(fe, a(S).label)), M("mousedown", U, (se) => se.preventDefault()), M("click", U, () => zt(a(S).value)), E(_, U);
  }), Ed(is, (_) => b(it, _), () => a(it));
  var tl = f(is, 2), nl = l(tl);
  {
    var rl = (_) => {
      var S = Dd();
      E(_, S);
    }, sl = (_) => {
      var S = Di(), U = Oe(S);
      pn(U, 17, () => a(J), (fe) => fe.instrument, (fe, se) => {
        var $e = Nd(), ft = l($e), et = l(ft), Dt = f(ft, 2), Ht = l(Dt);
        B(() => {
          I(et, a(se).instrument), je(Dt, 1, `instrument-row-badge${a(se).is_auto ? " auto" : ""}`), I(Ht, a(se).is_auto ? "Auto" : "Manual");
        }), M("click", $e, () => dt(a(se).instrument)), M("keydown", $e, (ke) => {
          ke.key === "Enter" && dt(a(se).instrument);
        }), E(fe, $e);
      }), E(_, S);
    };
    Y(nl, (_) => {
      a(J).length ? _(sl, -1) : _(rl);
    });
  }
  var ia = f(Ce, 2), al = f(l(ia), 2), il = l(al);
  {
    var ll = (_) => {
      var S = Jd(), U = Oe(S);
      let fe;
      var se = l(U), $e = l(se), ft = f(l($e), 2), et = l(ft), Dt = l(et), Ht = f(et, 2);
      {
        var ke = (C) => {
          var q = Ld();
          E(C, q);
        };
        Y(Ht, (C) => {
          t.user.is_system_admin && C(ke);
        });
      }
      var xe = f(ft, 4), tt = l(xe), Nt = f(xe, 4), vt = l(Nt);
      {
        var ir = (C) => {
          var q = Md();
          E(C, q);
        }, hl = (C) => {
          var q = Rd(), Ge = f(Oe(q), 2);
          {
            var Lt = (Yt) => {
              var Cr = Od(), Bl = l(Cr);
              B(() => {
                Cr.disabled = a($), I(Bl, a(oe));
              }), M("click", Cr, (Hl) => {
                Hl.preventDefault(), he();
              }), E(Yt, Cr);
            };
            Y(Ge, (Yt) => {
              t.isUserProfile || Yt(Lt);
            });
          }
          E(C, q);
        };
        Y(vt, (C) => {
          t.user.email_verified ? C(ir) : C(hl, -1);
        });
      }
      var ml = f(Nt, 4), ua = l(ml), pl = l(ua);
      {
        var bl = (C) => {
          var q = Ud();
          E(C, q);
        }, gl = (C) => {
          var q = Fd();
          E(C, q);
        };
        Y(pl, (C) => {
          t.user.beta_live_logging ? C(bl) : C(gl, -1);
        });
      }
      var yl = f(ua, 2);
      {
        var wl = (C) => {
          var q = jd(), Ge = l(q);
          B(() => {
            q.disabled = a(Te), I(Ge, t.user.beta_live_logging ? "Turn off" : "Turn on");
          }), M("click", q, (Lt) => {
            Lt.preventDefault(), W();
          }), E(C, q);
        };
        Y(yl, (C) => {
          t.isUserProfile || C(wl);
        });
      }
      var kl = f(se, 2), xl = l(kl), ca = f(l(xl), 2), El = l(ca);
      {
        var Sl = (C) => {
          var q = Vd();
          E(C, q);
        }, Tl = (C) => {
          var q = zd();
          E(C, q);
        };
        Y(El, (C) => {
          t.user.is_active ? C(Sl) : C(Tl, -1);
        });
      }
      var fa = f(ca, 4), Al = l(fa), va = f(fa, 4), Pl = l(va), _a = f(va, 4), Cl = l(_a), Il = f(_a, 4), Dl = l(Il);
      {
        var Nl = (C) => {
          var q = qd();
          E(C, q);
        }, Ll = (C) => {
          var q = Bd();
          E(C, q);
        };
        Y(Dl, (C) => {
          t.user.receive_update_emails ? C(Nl) : C(Ll, -1);
        });
      }
      var ha = f(U, 2);
      {
        var Ml = (C) => {
          var q = Hd(), Ge = l(q), Lt = l(Ge);
          B(() => I(Lt, t.user.has_password ? "Change My Password" : "Create A Password")), E(C, q);
        };
        Y(ha, (C) => {
          t.isUserProfile && C(Ml);
        });
      }
      var ma = f(ha, 2);
      let pa;
      var ba = l(ma), Ol = l(ba), ga = l(Ol), ya = l(ga), os = f(l(ya), 2), wa = f(os, 2);
      let ka;
      var Rl = l(wa), xa = f(ya, 2), Ul = f(l(xa), 2), Fl = f(xa, 2), Ea = f(l(Fl), 2);
      pn(Ea, 21, n, (C) => C.value, (C, q) => {
        var Ge = Yd(), Lt = l(Ge), Yt = {};
        B(() => {
          I(Lt, a(q).label), Yt !== (Yt = a(q).value) && (Ge.value = (Ge.__value = a(q).value) ?? "");
        }), E(C, Ge);
      });
      var jl = f(ga, 2), Sa = l(jl);
      {
        var Vl = (C) => {
          var q = Gd(), Ge = l(q), Lt = l(Ge);
          Va(Lt, () => a(A), (Yt) => b(A, Yt)), E(C, q);
        };
        Y(Sa, (C) => {
          t.isUserProfile || C(Vl);
        });
      }
      var zl = f(Sa, 2);
      {
        var ql = (C) => {
          var q = Wd(), Ge = l(q), Lt = l(Ge);
          Va(Lt, () => a(H), (Yt) => b(H, Yt)), E(C, q);
        };
        Y(zl, (C) => {
          t.isUserProfile && C(ql);
        });
      }
      B(
        (C, q) => {
          fe = Se(U, "", fe, { display: a(i) ? "none" : "" }), I(Dt, t.user.username), I(tt, t.user.user_email || "Not provided"), I(Al, C), I(Pl, q), I(Cl, t.user.timezone_display || "UTC"), pa = Se(ma, "", pa, { display: a(i) ? "block" : "none" }), ka = Se(wa, "", ka, { display: a(F) ? "block" : "none" }), I(Rl, a(F));
        },
        [
          () => Q(t.user.created_at) || "Unknown",
          () => Q(t.user.last_login) || "Never"
        ]
      ), Vn("submit", ba, (C) => C.preventDefault()), Vn("blur", os, _e), We(os, () => a(k), (C) => b(k, C)), We(Ul, () => a(w), (C) => b(w, C)), Gs(Ea, () => a(m), (C) => b(m, C)), E(_, S);
    }, ol = (_) => {
      var S = Kd();
      E(_, S);
    };
    Y(il, (_) => {
      t.user ? _(ll) : _(ol, -1);
    });
  }
  var ls = f(ia, 2);
  let la;
  var oa = l(ls), dl = f(oa, 2), ul = f(ls, 2);
  {
    var cl = (_) => {
      var S = $d(), U = f(l(S), 2), fe = l(U);
      {
        var se = (ke) => {
          var xe = Zd(), tt = f(Oe(xe), 2), Nt = l(tt), vt = f(tt, 2), ir = l(vt);
          B(() => {
            I(Nt, `Deactivating ${t.person.name ?? ""} will prevent them from being added to any sessions, session instances, or tune sets.
            Existing associations will not be affected.`), I(ir, `Deactivate ${t.person.first_name ?? ""}`);
          }), M("click", vt, () => Bt(!1)), E(ke, xe);
        }, $e = (ke) => {
          var xe = Xd(), tt = f(Oe(xe), 4), Nt = l(tt), vt = f(tt, 2), ir = l(vt);
          B(() => {
            I(Nt, `Reactivating ${t.person.name ?? ""} will allow them to be added to sessions, session instances, and tune sets again.`), I(ir, `Reactivate ${t.person.first_name ?? ""}`);
          }), M("click", vt, () => Bt(!0)), E(ke, xe);
        };
        Y(fe, (ke) => {
          t.person.active ? ke(se) : ke($e, -1);
        });
      }
      var ft = f(fe, 2);
      let et;
      var Dt = l(ft);
      {
        var Ht = (ke) => {
          var xe = Qd(), tt = l(xe);
          B(() => {
            je(xe, 1, `alert alert-${a(Ue).kind ?? ""}`), I(tt, a(Ue).text);
          }), E(ke, xe);
        };
        Y(Dt, (ke) => {
          a(Ue) && ke(Ht);
        });
      }
      B(() => et = Se(ft, "", et, { display: a(Ue) ? "block" : "none" })), E(_, S);
    };
    Y(ul, (_) => {
      t.isUserProfile || _(cl);
    });
  }
  var da = f(dn, 2);
  {
    var fl = (_) => {
      var S = eu(), U = l(S), fe = l(U), se = l(fe), $e = l(se), ft = f(se, 2), et = f(fe, 2), Dt = l(et), Ht = l(Dt), ke = f(Dt, 2), xe = l(ke), tt = f(et, 2), Nt = l(tt);
      B(() => {
        I($e, a(Z)), Ls(Ht, !!(a(Et) && a(Et).is_auto)), Ls(xe, !(a(Et) && a(Et).is_auto));
      }), M("click", S, (vt) => {
        vt.target === vt.currentTarget && ut();
      }), M("click", ft, ut), M("change", Ht, () => St(!0)), M("change", xe, () => St(!1)), M("click", Nt, (vt) => {
        vt.preventDefault(), qt();
      }), E(_, S);
    };
    Y(da, (_) => {
      a(Z) && _(fl);
    });
  }
  var vl = f(da, 2);
  {
    var _l = (_) => {
      var S = tu(), U = l(S), fe = l(U), se = f(l(fe), 2), $e = f(fe, 2), ft = l($e), et = f(l(ft)), Dt = l(et), Ht = f(et), ke = f($e, 2), xe = l(ke), tt = f(xe, 2);
      B(() => {
        I(Dt, a(Re).name), I(Ht, ` will delete its saved status for ${a(Re).tunesText ?? ""} that you've customized away from your other instruments. Re-adding it later starts fresh on Auto. This can't be undone.`);
      }), M("click", S, (Nt) => {
        Nt.target === Nt.currentTarget && At();
      }), M("click", se, At), M("click", xe, At), M("click", tt, on), E(_, S);
    };
    Y(vl, (_) => {
      a(Re) && _(_l);
    });
  }
  B(() => {
    x = Se(Ct, "", x, { display: a(i) ? "none" : "" }), X = Se(R, "", X, { display: a(i) ? "block" : "none" }), Le = Se(be, "", Le, { display: a(i) ? "none" : "" }), I(ne, t.person.name), I(Me, t.person.email || "Not provided"), I(It, t.person.sms_number || "Not provided"), I(Rn, t.person.city || "Not provided"), I(ns, t.person.state || "Not provided"), I(rs, t.person.country || "Not provided"), Js = Se(Ws, "", Js, { display: a(i) ? "block" : "none" }), aa = Se(sa, "", aa, {
      display: a(Pe) && a(qe).length ? "block" : "none"
    }), la = Se(ls, "", la, { display: a(i) ? "block" : "none" });
  }), M("click", Ct, () => ae(!0)), M("click", we, ue), M("click", de, () => ae(!1)), Vn("submit", Ks, (_) => _.preventDefault()), We(zi, () => a(o), (_) => b(o, _)), We(qi, () => a(u), (_) => b(u, _)), We(Hi, () => a(d), (_) => b(d, _)), We(Gi, () => a(v), (_) => b(v, _)), We(Wi, () => a(p), (_) => b(p, _)), We(Ji, () => a(y), (_) => b(y, _)), We(Ki, () => a(h), (_) => b(h, _)), We(Xi, () => a(g), (_) => b(g, _)), M("input", ar, kt), Vn("focus", ar, kt), M("keydown", ar, $t), We(ar, () => a(ie), (_) => b(ie, _)), M("click", oa, ue), M("click", dl, () => ae(!1)), E(e, en), On();
}
ts(["click", "input", "keydown", "mousedown", "change"]);
var su = /* @__PURE__ */ T('&middot; <span class="session-role-badge"> </span>', 1), au = /* @__PURE__ */ T('<button type="button" class="btn btn-link text-danger p-0 leave-session-btn" title="Leave this session"><span class="leave-x">&times;</span></button>'), iu = /* @__PURE__ */ T('<div class="custom-control custom-switch"><input type="checkbox" class="custom-control-input admin-toggle"/> <label class="custom-control-label">Admin</label></div>'), lu = /* @__PURE__ */ T('<div class="session-card card mb-2"><div class="card-body d-flex justify-content-between align-items-center py-2 px-3"><div class="session-info"><a class="session-title h6 mb-0 d-block text-decoration-none"> </a> <small class="text-muted"> <!></small></div> <!></div></div>'), ou = /* @__PURE__ */ T(`<div class="mt-3"><a href="#add" id="add-to-session-link" class="btn btn-outline-primary btn-sm">Add another session I've been to</a></div>`), du = /* @__PURE__ */ T('<div class="mt-3"><a href="#add" id="add-to-session-link" class="btn btn-outline-primary btn-sm">Add this person to a session</a></div>'), uu = /* @__PURE__ */ T('<div class="mb-3"><select id="session-filter" class="form-select"><option>All Sessions</option><option>Regular Sessions Only</option></select></div> <div class="sessions-card-list"></div> <!>', 1), cu = /* @__PURE__ */ T('<div class="alert alert-info" role="alert"><a href="#add" id="add-to-session-link" class="btn btn-outline-primary btn-sm">add your first session</a></div>'), fu = /* @__PURE__ */ T('<div class="alert alert-info" role="alert">No sessions associated with this person.</div> <div class="mt-3"><a href="#add" id="add-to-session-link" class="btn btn-outline-primary btn-sm">Add this person to a session</a></div>', 1), vu = /* @__PURE__ */ T('<div class="alert alert-danger"> </div>'), _u = /* @__PURE__ */ T('<p class="text-muted">No sessions found.</p>'), hu = /* @__PURE__ */ T('<div class="session-item"><div class="session-info"><div class="session-name"> </div> <div class="session-location"> </div></div> <button class="btn btn-sm btn-primary add-session-btn">Add</button></div>'), mu = /* @__PURE__ */ T('<p class="text-muted mt-2"><small>Showing top 10 results. Use search to narrow down.</small></p>'), pu = /* @__PURE__ */ T(`<div class="sessions-list"></div> <!> <p class="mt-3">Don't see the session here? <a href="/add-session" target="_blank">Add it!</a></p>`, 1), bu = /* @__PURE__ */ T(`<div class="mt-3"><!></div>  <div id="addToSessionModal" role="presentation"><div class="modal-content"><div class="modal-header"><h3> </h3> <span class="modal-close" role="button" tabindex="0">&times;</span></div> <div class="modal-body"><div class="search-section"><div class="mb-3"><label for="session-search" class="form-label">Search Sessions:</label> <input type="text" id="session-search" class="form-control" placeholder="Type to search sessions..."/></div></div> <div class="role-section mb-3"><span class="form-label"> </span> <div class="form-check"><input class="form-check-input" type="radio" name="user-role" id="role-regular"/> <label class="form-check-label" for="role-regular">Regular</label></div> <div class="form-check"><input class="form-check-input" type="radio" name="user-role" id="role-attendee"/> <label class="form-check-label" for="role-attendee">Attendee</label></div></div> <div id="sessions-loading" class="text-center"><span class="loading-spinner"></span> <span style="margin-left: 8px;">Loading sessions...</span></div> <div id="sessions-results"><!></div> <div id="no-sessions-message"><p>Don't see the session here? <a href="/add-session" target="_blank">Add it!</a></p></div></div></div></div>`, 1);
function gu(e, t) {
  Mn(t, !0);
  const n = [], r = (x, R) => window.showMessage && window.showMessage(x, R);
  let s = /* @__PURE__ */ P(me([...t.initialSessions])), i = /* @__PURE__ */ P("all");
  const o = (x) => a(i) === "all" || `${x.location} · ${x.role}`.includes("Regular");
  function u(x) {
    confirm(`Are you sure you want to leave "${x.session_name}"?

This will remove you from the session's member list. Your attendance history will be preserved.`) && fetch(`/api/sessions/${x.session_path}/leave`, {
      method: "DELETE",
      headers: { "Content-Type": "application/json" }
    }).then((R) => R.json()).then((R) => {
      R.success ? (b(s, a(s).filter((X) => X.session_path !== x.session_path), !0), r(R.message, "success")) : r("Error: " + R.message, "error");
    }).catch((R) => {
      r("Error leaving session: " + R.message, "error");
    });
  }
  function d(x, R) {
    const X = R.currentTarget.checked, we = R.currentTarget;
    fetch(`/api/admin/sessions/${x.session_path}/people/${t.personId}/admin`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ is_admin: X })
    }).then((de) => de.json()).then((de) => {
      de.success ? (x.role = X ? "Admin" : x.is_regular ? "Regular" : "Attendee", x.is_admin = X, b(s, [...a(s)], !0)) : (we.checked = !X, r("Error: " + (de.error || de.message), "error"));
    }).catch((de) => {
      we.checked = !X, r("Error updating admin status: " + de.message, "error");
    });
  }
  let v = /* @__PURE__ */ P(!1), p = /* @__PURE__ */ P(""), y = /* @__PURE__ */ P(!1), h = /* @__PURE__ */ P(null), g = /* @__PURE__ */ P(
    null
    // null until first load
  ), k = /* @__PURE__ */ P(!1), w = /* @__PURE__ */ P("regular"), m;
  function A() {
    b(p, ""), ae(), b(v, !0), document.body.classList.add("modal-open");
  }
  function H() {
    b(v, !1), document.body.classList.remove("modal-open");
  }
  function V(x) {
    x.key === "Escape" && a(v) && H();
  }
  function F(x) {
    b(y, x, !0), x && (b(g, null), b(h, null), b(k, !1));
  }
  function Q(x) {
    b(h, null), b(g, x, !0), b(k, x.length === 0);
  }
  function ae() {
    F(!0), fetch(`/api/person/${t.personId}/available-sessions`).then((x) => x.json()).then((x) => {
      F(!1), x.success ? Q(x.sessions) : b(h, "Failed to load sessions: " + x.message);
    }).catch((x) => {
      F(!1), b(h, "Error loading sessions: " + x.message);
    });
  }
  function te(x) {
    F(!0), fetch(`/api/person/${t.personId}/search-sessions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ search_term: x })
    }).then((R) => R.json()).then((R) => {
      F(!1), R.success ? Q(R.sessions) : b(h, "Failed to search sessions: " + R.message);
    }).catch((R) => {
      F(!1), b(h, "Error searching sessions: " + R.message);
    });
  }
  function _e() {
    clearTimeout(m);
    const x = a(p).trim();
    m = setTimeout(
      () => {
        te(x);
      },
      300
    );
  }
  const ue = (x) => x.location_name && x.location_name !== x.location_display ? `${x.location_name} - ${x.location_display}` : x.location_display;
  function $(x, R) {
    confirm(`Add ${t.person.name} to "${R}" as a ${a(w)}?`) && fetch("/api/add-person-to-session", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        person_id: t.personId,
        session_id: parseInt(x),
        role: a(w)
      })
    }).then((X) => X.json()).then((X) => {
      X.success ? (H(), sessionStorage.setItem("personSavedMessage", X.message), window.location.reload()) : r("Error: " + X.message, "error");
    }).catch((X) => {
      r("Error adding person to session: " + X.message, "error");
    });
  }
  var oe = bu();
  Vn("keydown", Ps, V);
  var he = Oe(oe), Te = l(he);
  {
    var W = (x) => {
      var R = uu(), X = Oe(R), we = l(X), de = l(we);
      de.value = de.__value = "all";
      var Ce = f(de);
      Ce.value = Ce.__value = "regular";
      var le = f(X, 2);
      pn(le, 23, () => a(s), (O) => O.session_path, (O, D, ne) => {
        var ce = lu();
        let Me;
        var Be = l(ce), It = l(Be), Qe = l(It), tn = l(Qe), un = f(Qe, 2), Rn = l(un), Un = f(Rn);
        {
          var ns = (He) => {
            var Ye = su(), ct = f(Oe(Ye)), sr = l(ct);
            B(() => {
              Ee(ct, "data-session-path", a(D).session_path), I(sr, a(D).role);
            }), E(He, Ye);
          };
          Y(Un, (He) => {
            a(D).role && He(ns);
          });
        }
        var Pr = f(It, 2);
        {
          var rs = (He) => {
            var Ye = au();
            B(() => {
              Ee(Ye, "data-session-path", a(D).session_path), Ee(Ye, "data-session-name", a(D).session_name);
            }), M("click", Ye, (ct) => {
              ct.preventDefault(), u(a(D));
            }), E(He, Ye);
          }, ss = (He) => {
            var Ye = iu(), ct = l(Ye), sr = f(ct, 2);
            B(() => {
              Ee(ct, "id", `admin-toggle-${a(ne) + 1}`), Ee(ct, "data-session-path", a(D).session_path), Ls(ct, a(D).is_admin), Ee(sr, "for", `admin-toggle-${a(ne) + 1}`);
            }), M("change", ct, (as) => d(a(D), as)), E(He, Ye);
          };
          Y(Pr, (He) => {
            t.isUserProfile ? He(rs) : t.isSystemAdmin && He(ss, 1);
          });
        }
        B(
          (He, Ye) => {
            Ee(ce, "data-session-path", a(D).session_path), Ee(ce, "data-is-regular", He), Me = Se(ce, "", Me, Ye), Ee(Qe, "href", `/sessions/${a(D).session_path ?? ""}`), I(tn, a(D).session_name), I(Rn, a(D).location);
          },
          [
            () => String(a(D).is_regular).toLowerCase(),
            () => ({ display: o(a(D)) ? "" : "none" })
          ]
        ), E(O, ce);
      });
      var be = f(le, 2);
      {
        var Le = (O) => {
          var D = ou(), ne = l(D);
          M("click", ne, (ce) => {
            ce.preventDefault(), A();
          }), E(O, D);
        }, N = (O) => {
          var D = du(), ne = l(D);
          M("click", ne, (ce) => {
            ce.preventDefault(), A();
          }), E(O, D);
        };
        Y(be, (O) => {
          t.isUserProfile ? O(Le) : O(N, -1);
        });
      }
      Gs(we, () => a(i), (O) => b(i, O)), E(x, R);
    }, J = (x) => {
      var R = cu(), X = l(R);
      M("click", X, (we) => {
        we.preventDefault(), A();
      }), E(x, R);
    }, Z = (x) => {
      var R = fu(), X = f(Oe(R), 2), we = l(X);
      M("click", we, (de) => {
        de.preventDefault(), A();
      }), E(x, R);
    };
    Y(Te, (x) => {
      a(s).length ? x(W) : t.isUserProfile ? x(J, 1) : x(Z, -1);
    });
  }
  var Ae = f(he, 2);
  let Re;
  var ie = l(Ae), Pe = l(ie), it = l(Pe), lt = l(it), ot = f(it, 2), zt = f(Pe, 2), qe = l(zt), kt = l(qe), $t = f(l(kt), 2), xt = f(qe, 2), dt = l(xt), ut = l(dt), Et = f(dt, 2), St = l(Et);
  St.value = St.__value = "regular";
  var qt = f(Et, 2), Tt = l(qt);
  Tt.value = Tt.__value = "attendee";
  var on = f(xt, 2);
  let At;
  var Ue = f(on, 2), Bt = l(Ue);
  {
    var en = (x) => {
      var R = vu(), X = l(R);
      B(() => I(X, a(h))), E(x, R);
    }, dn = (x) => {
      var R = Di(), X = Oe(R);
      {
        var we = (Ce) => {
          var le = _u();
          E(Ce, le);
        }, de = (Ce) => {
          var le = pu(), be = Oe(le);
          pn(be, 21, () => a(g), (O) => O.session_id, (O, D) => {
            var ne = hu(), ce = l(ne), Me = l(ce), Be = l(Me), It = f(Me, 2), Qe = l(It), tn = f(ce, 2);
            B(
              (un) => {
                I(Be, a(D).name), I(Qe, un), Ee(tn, "data-session-id", a(D).session_id), Ee(tn, "data-session-name", a(D).name);
              },
              [() => ue(a(D))]
            ), M("click", tn, () => $(a(D).session_id, a(D).name)), E(O, ne);
          });
          var Le = f(be, 2);
          {
            var N = (O) => {
              var D = mu();
              E(O, D);
            };
            Y(Le, (O) => {
              a(g).length === 10 && O(N);
            });
          }
          E(Ce, le);
        };
        Y(X, (Ce) => {
          a(g).length === 0 ? Ce(we) : Ce(de, -1);
        });
      }
      E(x, R);
    };
    Y(Bt, (x) => {
      a(h) ? x(en) : a(g) && x(dn, 1);
    });
  }
  var Pt = f(Ue, 2);
  let Ct;
  B(() => {
    je(Ae, 1, `modal${a(v) ? " show" : ""}`), Re = Se(Ae, "", Re, { display: a(v) ? "flex" : "none" }), I(lt, t.isUserProfile ? "Add me to a Session" : `Add ${t.person.name} to a Session`), I(ut, t.isUserProfile ? "Add me as:" : "Add as:"), At = Se(on, "", At, { display: a(y) ? "block" : "none" }), Ct = Se(Pt, "", Ct, { display: a(k) ? "block" : "none" });
  }), M("click", Ae, (x) => {
    x.target === x.currentTarget && H();
  }), M("click", ot, H), M("keydown", ot, (x) => {
    x.key === "Enter" && H();
  }), M("input", $t, _e), We($t, () => a(p), (x) => b(p, x)), ja(n, [], St, () => a(w), (x) => b(w, x)), ja(n, [], Tt, () => a(w), (x) => b(w, x)), E(e, oe), On();
}
ts(["click", "change", "keydown", "input"]);
var yu = /* @__PURE__ */ T('<div class="alert alert-danger" role="alert">Error loading attendance data.</div>'), wu = /* @__PURE__ */ T("<tr><td> </td><td> </td><td><span> </span></td></tr>"), ku = /* @__PURE__ */ T('<div class="table-responsive"><table class="table table-striped"><thead><tr><th>Session Name</th><th>Instance Date</th><th>Attended</th></tr></thead><tbody></tbody></table></div>'), xu = /* @__PURE__ */ T('<div class="alert alert-info" role="alert">No attendance records found.</div>'), Eu = /* @__PURE__ */ T('<div class="mt-3"><div id="attended-loading" class="text-center"><span class="loading-spinner" style="display: inline-block; width: 16px; height: 16px; border: 2px solid var(--border-color); border-top: 2px solid var(--primary); border-radius: 50%; animation: spin 1s linear infinite;"></span> <span style="margin-left: 8px;">Loading attendance history...</span></div> <div id="attended-content"><!></div></div>');
function Su(e, t) {
  Mn(t, !0);
  let n = /* @__PURE__ */ P(!0), r = /* @__PURE__ */ P(
    null
    // null = not yet loaded / failed
  ), s = /* @__PURE__ */ P(!1), i = !1;
  es(() => {
    t.load && !i && (i = !0, fetch(`/api/person/${t.personId}/attended`).then((w) => w.json()).then((w) => {
      b(n, !1), w.success && w.attendance.length > 0 ? b(r, w.attendance, !0) : b(r, [], !0);
    }).catch((w) => {
      b(n, !1), b(s, !0), console.error("Error:", w);
    }));
  });
  const o = (w) => w === "yes" ? { cls: "text-success", label: "✓ Yes" } : w === "maybe" ? { cls: "text-warning", label: "? Maybe" } : w === "no" ? { cls: "text-danger", label: "✗ No" } : { cls: "text-muted", label: "- Unknown" };
  var u = Eu(), d = l(u);
  let v;
  var p = f(d, 2), y = l(p);
  {
    var h = (w) => {
      var m = yu();
      E(w, m);
    }, g = (w) => {
      var m = ku(), A = l(m), H = f(l(A));
      pn(H, 21, () => a(r), Ni, (V, F) => {
        var Q = wu(), ae = l(Q), te = l(ae), _e = f(ae), ue = l(_e), $ = f(_e), oe = l($), he = l(oe);
        B(
          (Te, W) => {
            I(te, a(F).session_name), I(ue, a(F).instance_date), je(oe, 1, Te), I(he, W);
          },
          [
            () => Mi(o(a(F).attendance).cls),
            () => o(a(F).attendance).label
          ]
        ), E(V, Q);
      }), E(w, m);
    }, k = (w) => {
      var m = xu();
      E(w, m);
    };
    Y(y, (w) => {
      a(s) ? w(h) : a(r) && a(r).length > 0 ? w(g, 1) : a(r) && w(k, 2);
    });
  }
  B(() => v = Se(d, "", v, { display: a(n) ? "" : "none" })), E(e, u), On();
}
var Tu = /* @__PURE__ */ T('<div class="alert alert-info" role="alert">No tune statistics available.</div> <div class="mt-3"><a href="/my-tunes" class="tune-list-link">View tune list</a></div>', 1), Au = /* @__PURE__ */ T("<option> </option>"), Pu = /* @__PURE__ */ T('<div class="filter-group"><label for="tune-type-filter" class="filter-label">Type:</label> <select id="tune-type-filter" class="form-select tune-type-select"><option>All Types</option><!></select></div>'), Cu = /* @__PURE__ */ T('<span class="date-filter-summary"><span class="date-filter-text"> </span> <a href="#edit" id="edit-date-filter" class="date-filter-link">edit</a> <a href="#clear" id="clear-date-filter" class="date-filter-link date-filter-clear">clear</a></span>'), Iu = /* @__PURE__ */ T('<a href="#filter" id="show-date-filter" class="date-filter-link">Filter by date</a>'), Du = /* @__PURE__ */ T('<div class="tune-stats"><div class="tune-filter-row mb-3"><!> <!> <a class="tune-list-link">View tune list</a></div> <div id="date-filter-panel" class="date-filter-panel"><div class="date-filter-row"><label for="tune-start-date" class="filter-label">From:</label> <input type="date" id="tune-start-date" class="form-control date-input"/></div> <div class="date-filter-row"><label for="tune-end-date" class="filter-label">To:</label> <input type="date" id="tune-end-date" class="form-control date-input"/></div> <div class="date-filter-row"><button id="apply-date-filter" class="btn btn-sm btn-primary">Apply</button> <button id="cancel-date-filter" class="btn btn-sm btn-outline-secondary">Cancel</button></div></div> <div class="row"><div class="col-md-6 col-lg-3 mb-3"><div class="stat-card"><div class="stat-value"> </div> <div class="stat-label">Total Tunes</div></div></div> <div class="col-md-6 col-lg-3 mb-3"><div class="stat-card"><div class="stat-value"> </div> <div class="stat-label">Learned</div></div></div> <div class="col-md-6 col-lg-3 mb-3"><div class="stat-card"><div class="stat-value"> </div> <div class="stat-label">Learning</div></div></div> <div class="col-md-6 col-lg-3 mb-3"><div class="stat-card"><div class="stat-value"> </div> <div class="stat-label">Bookmarked</div></div></div></div></div>'), Nu = /* @__PURE__ */ T('<div class="mt-3"><div id="tunes-loading" class="text-center"><span class="loading-spinner" style="display: inline-block; width: 16px; height: 16px; border: 2px solid var(--border-color); border-top: 2px solid var(--primary); border-radius: 50%; animation: spin 1s linear infinite;"></span> <span style="margin-left: 8px;">Loading tune statistics...</span></div> <div id="tunes-content"><!></div></div>');
function Lu(e, t) {
  Mn(t, !0);
  let n = /* @__PURE__ */ P(!0), r = /* @__PURE__ */ P(
    null
    // the /tunes-stats stats object
  ), s = /* @__PURE__ */ P(!1), i = /* @__PURE__ */ P(""), o = /* @__PURE__ */ P(""), u = /* @__PURE__ */ P(""), d = /* @__PURE__ */ P(""), v = /* @__PURE__ */ P(""), p = /* @__PURE__ */ P(!1), y = !1;
  function h() {
    let W = `/api/person/${t.personId}/tunes-stats`;
    const J = new URLSearchParams();
    a(o) && J.append("start_date", a(o)), a(u) && J.append("end_date", a(u)), J.toString() && (W += "?" + J.toString()), b(n, !0), b(s, !1), b(r, null), b(p, !1), fetch(W).then((Z) => Z.json()).then((Z) => {
      b(n, !1), Z.success ? b(r, Z.stats, !0) : b(s, !0);
    }).catch((Z) => {
      b(n, !1), b(s, !0), console.error("Error:", Z);
    });
  }
  es(() => {
    t.load && !y && (y = !0, h());
  });
  const g = /* @__PURE__ */ Ut(() => a(r) ? a(i) && a(r).by_type_detailed && a(r).by_type_detailed[a(i)] ? a(r).by_type_detailed[a(i)] : {
    total: a(r).total_tunes,
    learned: a(r).learned,
    learning: a(r).learning,
    bookmarked: a(r).bookmarked
  } : null), k = /* @__PURE__ */ Ut(() => {
    const W = new URLSearchParams();
    return a(i) && a(r) && a(r).by_type_detailed && a(r).by_type_detailed[a(i)] && W.append("type", a(i)), a(o) && W.append("start_date", a(o)), a(u) && W.append("end_date", a(u)), W.toString() ? `/my-tunes?${W.toString()}` : "/my-tunes";
  }), w = /* @__PURE__ */ Ut(() => a(r) && a(r).by_type ? Object.keys(a(r).by_type).sort() : []), m = /* @__PURE__ */ Ut(() => !!(a(o) || a(u))), A = /* @__PURE__ */ Ut(() => a(o) && a(u) ? `${a(o)} – ${a(u)}` : a(o) ? `from ${a(o)}` : `until ${a(u)}`);
  function H() {
    b(d, a(o), !0), b(v, a(u), !0), b(p, !0);
  }
  function V() {
    b(o, a(d), !0), b(u, a(v), !0), h();
  }
  function F() {
    b(o, ""), b(u, ""), h();
  }
  function Q(W) {
    W.currentTarget.showPicker && W.currentTarget.showPicker();
  }
  function ae(W) {
    W.preventDefault();
  }
  var te = Nu(), _e = l(te);
  let ue;
  var $ = f(_e, 2), oe = l($);
  {
    var he = (W) => {
      var J = Tu();
      E(W, J);
    }, Te = (W) => {
      var J = Du(), Z = l(J), Ae = l(Z);
      {
        var Re = (le) => {
          var be = Pu(), Le = f(l(be), 2), N = l(Le);
          N.value = N.__value = "";
          var O = f(N);
          pn(O, 16, () => a(w), (D) => D, (D, ne) => {
            var ce = Au(), Me = l(ce), Be = {};
            B(() => {
              I(Me, `${ne ?? ""} (${a(r).by_type[ne] ?? ""})`), Be !== (Be = ne) && (ce.value = (ce.__value = ne) ?? "");
            }), E(D, ce);
          }), Gs(Le, () => a(i), (D) => b(i, D)), E(le, be);
        };
        Y(Ae, (le) => {
          a(w).length > 0 && le(Re);
        });
      }
      var ie = f(Ae, 2);
      {
        var Pe = (le) => {
          var be = Cu(), Le = l(be), N = l(Le), O = f(Le, 2), D = f(O, 2);
          B(() => I(N, a(A))), M("click", O, (ne) => {
            ne.preventDefault(), H();
          }), M("click", D, (ne) => {
            ne.preventDefault(), F();
          }), E(le, be);
        }, it = (le) => {
          var be = Iu();
          M("click", be, (Le) => {
            Le.preventDefault(), H();
          }), E(le, be);
        };
        Y(ie, (le) => {
          a(m) ? le(Pe) : le(it, -1);
        });
      }
      var lt = f(ie, 2), ot = f(Z, 2);
      let zt;
      var qe = l(ot), kt = f(l(qe), 2), $t = f(qe, 2), xt = f(l($t), 2), dt = f($t, 2), ut = l(dt), Et = f(ut, 2), St = f(ot, 2), qt = l(St), Tt = l(qt), on = l(Tt), At = l(on), Ue = f(qt, 2), Bt = l(Ue), en = l(Bt), dn = l(en), Pt = f(Ue, 2), Ct = l(Pt), x = l(Ct), R = l(x), X = f(Pt, 2), we = l(X), de = l(we), Ce = l(de);
      B(() => {
        Ee(lt, "href", a(k)), zt = Se(ot, "", zt, { display: a(p) ? "block" : "none" }), I(At, a(g).total || 0), I(dn, a(g).learned || 0), I(R, a(g).learning || 0), I(Ce, a(g).bookmarked || 0);
      }), M("click", kt, Q), M("keydown", kt, ae), We(kt, () => a(d), (le) => b(d, le)), M("click", xt, Q), M("keydown", xt, ae), We(xt, () => a(v), (le) => b(v, le)), M("click", ut, V), M("click", Et, () => b(p, !1)), E(W, J);
    };
    Y(oe, (W) => {
      a(s) ? W(he) : a(r) && W(Te, 1);
    });
  }
  B(() => ue = Se(_e, "", ue, { display: a(n) ? "block" : "none" })), E(e, te), On();
}
ts(["click", "keydown"]);
var Mu = /* @__PURE__ */ T('<div class="alert alert-danger" role="alert">Error loading login history.</div>'), Ou = /* @__PURE__ */ T('<tr><td> </td><td><span> </span></td><td> </td><td style="font-size: 0.8em; max-width: 200px; overflow: hidden; text-overflow: ellipsis;"> </td></tr>'), Ru = /* @__PURE__ */ T('<div class="table-responsive"><table class="table table-striped"><thead><tr><th>Time</th><th>Event</th><th>IP Address</th><th>User Agent</th></tr></thead><tbody></tbody></table></div>'), Uu = /* @__PURE__ */ T("<br/><small> </small>", 1), Fu = /* @__PURE__ */ T('<div class="alert alert-info" role="alert">No login history found.<!></div>'), ju = /* @__PURE__ */ T('<div class="mt-3"><div id="logins-loading" class="text-center"><span class="loading-spinner" style="display: inline-block; width: 16px; height: 16px; border: 2px solid var(--border-color); border-top: 2px solid var(--primary); border-radius: 50%; animation: spin 1s linear infinite;"></span> <span style="margin-left: 8px;">Loading login history...</span></div> <div id="logins-content"><!></div></div>');
function Vu(e, t) {
  Mn(t, !0);
  let n = /* @__PURE__ */ P(!0), r = /* @__PURE__ */ P(null), s = /* @__PURE__ */ P(null), i = /* @__PURE__ */ P(!1), o = !1;
  es(() => {
    t.load && !o && (o = !0, fetch(`/api/person/${t.personId}/logins`).then((m) => m.json()).then((m) => {
      b(n, !1), m.success && m.logins.length > 0 ? b(r, m.logins, !0) : (b(r, [], !0), b(s, m.debug || null, !0));
    }).catch((m) => {
      b(n, !1), b(i, !0), console.error("Error:", m);
    }));
  });
  const u = (m) => m === "LOGIN_SUCCESS" ? "text-success" : m === "LOGIN_FAILURE" ? "text-danger" : "text-muted";
  var d = ju(), v = l(d);
  let p;
  var y = f(v, 2), h = l(y);
  {
    var g = (m) => {
      var A = Mu();
      E(m, A);
    }, k = (m) => {
      var A = Ru(), H = l(A), V = f(l(H));
      pn(V, 21, () => a(r), Ni, (F, Q) => {
        var ae = Ou(), te = l(ae), _e = l(te), ue = f(te), $ = l(ue), oe = l($), he = f(ue), Te = l(he), W = f(he), J = l(W);
        B(
          (Z) => {
            I(_e, a(Q).login_time), je($, 1, Z), I(oe, a(Q).event_type), I(Te, a(Q).ip_address), I(J, a(Q).user_agent);
          },
          [() => Mi(u(a(Q).event_type))]
        ), E(F, ae);
      }), E(m, A);
    }, w = (m) => {
      var A = Fu(), H = f(l(A));
      {
        var V = (F) => {
          var Q = Uu(), ae = f(Oe(Q)), te = l(ae);
          B(() => I(te, `Debug: ${a(s) ?? ""}`)), E(F, Q);
        };
        Y(H, (F) => {
          a(s) && F(V);
        });
      }
      E(m, A);
    };
    Y(h, (m) => {
      a(i) ? m(g) : a(r) && a(r).length > 0 ? m(k, 1) : a(r) && m(w, 2);
    });
  }
  B(() => p = Se(v, "", p, { display: a(n) ? "" : "none" })), E(e, d), On();
}
var zu = /* @__PURE__ */ T('<header class="docs-header"><h1 class="docs-heading"> </h1></header>'), qu = /* @__PURE__ */ T('<span id="breadcrumb-person-name"><a href="#profile" class="breadcrumb-item"> </a></span> <span id="breadcrumb-tab-separator" class="breadcrumb-separator">&gt;&gt;</span> <span id="breadcrumb-tab-name" class="breadcrumb-current"> </span>', 1), Bu = /* @__PURE__ */ T('<span id="breadcrumb-person-name" class="breadcrumb-current"> </span> <span id="breadcrumb-tab-separator" class="breadcrumb-separator" style="display: none;">&gt;&gt;</span> <span id="breadcrumb-tab-name" class="breadcrumb-current" style="display: none;"></span>', 1), Hu = /* @__PURE__ */ T('<nav class="admin-breadcrumb" aria-label="breadcrumb"><a href="/admin" class="breadcrumb-item">Admin</a> <span class="breadcrumb-separator">&gt;&gt;</span> <a href="/admin/people" class="breadcrumb-item">People</a> <span class="breadcrumb-separator">&gt;&gt;</span> <!></nav>'), Yu = /* @__PURE__ */ T("<option>Logins</option>"), Gu = /* @__PURE__ */ T('<li class="nav-item" role="presentation"><button id="logins-tab" data-bs-toggle="tab" data-bs-target="#logins" type="button" role="tab" aria-controls="logins">Logins</button></li>'), Wu = /* @__PURE__ */ T('<div id="logins" role="tabpanel" aria-labelledby="logins-tab"><!></div>'), Ju = /* @__PURE__ */ T('<!> <div class="profile-mobile-nav d-md-none mb-3"><select id="profile-tab-select" class="form-select"><option>Profile</option><option> </option><option> </option><option>Tunes</option><!></select></div> <ul class="nav nav-tabs d-none d-md-flex" id="profileTabs" role="tablist"><li class="nav-item" role="presentation"><button id="profile-tab" data-bs-toggle="tab" data-bs-target="#profile" type="button" role="tab" aria-controls="profile">Profile</button></li> <li class="nav-item" role="presentation"><button id="sessions-tab" data-bs-toggle="tab" data-bs-target="#sessions" type="button" role="tab" aria-controls="sessions"> </button></li> <li class="nav-item" role="presentation"><button id="attended-tab" data-bs-toggle="tab" data-bs-target="#attended" type="button" role="tab" aria-controls="attended"> </button></li> <li class="nav-item" role="presentation"><button id="tunes-tab" data-bs-toggle="tab" data-bs-target="#tunes" type="button" role="tab" aria-controls="tunes">Tunes</button></li> <!></ul> <div class="tab-content" id="profileTabContent"><div id="profile" role="tabpanel" aria-labelledby="profile-tab"><!></div> <div id="sessions" role="tabpanel" aria-labelledby="sessions-tab"><!></div> <div id="attended" role="tabpanel" aria-labelledby="attended-tab"><!></div> <div id="tunes" role="tabpanel" aria-labelledby="tunes-tab"><!></div> <!></div>', 1);
function Ku(e, t) {
  Mn(t, !0);
  let n = Ms(t, "ctx", 19, () => ({}));
  const r = t.pageData.person, s = t.pageData.user, i = t.pageData.is_user_profile, o = t.pageData.is_system_admin, u = r.id, d = (N, O) => window.showMessage && window.showMessage(N, O), v = ["profile", "sessions", "attended", "tunes", "logins"], p = (() => {
    const N = new URLSearchParams(window.location.search).get("tab");
    return N && v.includes(N) ? N : "profile";
  })();
  let y = /* @__PURE__ */ P(me(p)), h = /* @__PURE__ */ P(!1), g = /* @__PURE__ */ P(!1), k = /* @__PURE__ */ P(!1);
  function w(N) {
    N === "attended" ? b(h, !0) : N === "tunes" ? b(g, !0) : N === "logins" && b(k, !0);
  }
  w(p);
  function m(N, O = !0) {
    if (b(y, N, !0), w(N), O) {
      const D = new URL(window.location);
      N === "profile" ? D.searchParams.delete("tab") : D.searchParams.set("tab", N), window.history.replaceState({}, "", D);
    }
  }
  const A = {
    profile: null,
    sessions: "Sessions",
    attended: "Attended",
    tunes: "Tunes",
    logins: "Logins"
  }, H = /* @__PURE__ */ Ut(() => A[a(y)] || null), V = i ? "My Sessions" : "Sessions", F = i ? "I've Attended" : "Attended";
  es(() => {
    Ar(() => {
      const N = sessionStorage.getItem("personSavedMessage");
      N && (d(N, "success"), sessionStorage.removeItem("personSavedMessage"));
    });
  });
  var Q = Ju(), ae = Oe(Q);
  {
    var te = (N) => {
      var O = zu(), D = l(O), ne = l(D);
      B(() => I(ne, `Profile: ${r.name ?? ""}`)), E(N, O);
    }, _e = (N) => {
      var O = Hu(), D = f(l(O), 8);
      {
        var ne = (Me) => {
          var Be = qu(), It = Oe(Be), Qe = l(It), tn = l(Qe), un = f(It, 4), Rn = l(un);
          B(() => {
            I(tn, r.name), I(Rn, a(H));
          }), M("click", Qe, (Un) => {
            Un.preventDefault(), m("profile");
          }), E(Me, Be);
        }, ce = (Me) => {
          var Be = Bu(), It = Oe(Be), Qe = l(It);
          B(() => I(Qe, r.name)), E(Me, Be);
        };
        Y(D, (Me) => {
          a(H) ? Me(ne) : Me(ce, -1);
        });
      }
      E(N, O);
    };
    Y(ae, (N) => {
      i ? N(te) : N(_e, -1);
    });
  }
  var ue = f(ae, 2), $ = l(ue), oe = l($);
  oe.value = oe.__value = "profile";
  var he = f(oe), Te = l(he);
  he.value = he.__value = "sessions";
  var W = f(he), J = l(W);
  W.value = W.__value = "attended";
  var Z = f(W);
  Z.value = Z.__value = "tunes";
  var Ae = f(Z);
  {
    var Re = (N) => {
      var O = Yu();
      O.value = O.__value = "logins", E(N, O);
    };
    Y(Ae, (N) => {
      s && N(Re);
    });
  }
  var ie;
  Oi($);
  var Pe = f(ue, 2), it = l(Pe), lt = l(it);
  let ot;
  var zt = f(it, 2), qe = l(zt);
  let kt;
  var $t = l(qe), xt = f(zt, 2), dt = l(xt);
  let ut;
  var Et = l(dt), St = f(xt, 2), qt = l(St);
  let Tt;
  var on = f(St, 2);
  {
    var At = (N) => {
      var O = Gu(), D = l(O);
      let ne;
      B(() => {
        ne = je(D, 1, "nav-link", null, ne, { active: a(y) === "logins" }), Ee(D, "aria-selected", a(y) === "logins");
      }), M("click", D, () => m("logins")), E(N, O);
    };
    Y(on, (N) => {
      s && N(At);
    });
  }
  var Ue = f(Pe, 2), Bt = l(Ue);
  let en;
  var dn = l(Bt);
  {
    let N = /* @__PURE__ */ Ut(() => t.pageData.timezone_options || []), O = /* @__PURE__ */ Ut(() => n().canonicalInstruments || []);
    ru(dn, {
      get person() {
        return r;
      },
      get user() {
        return s;
      },
      get isUserProfile() {
        return i;
      },
      get personId() {
        return u;
      },
      get timezoneOptions() {
        return a(N);
      },
      get canonicalInstruments() {
        return a(O);
      }
    });
  }
  var Pt = f(Bt, 2);
  let Ct;
  var x = l(Pt);
  {
    let N = /* @__PURE__ */ Ut(() => t.pageData.sessions || []);
    gu(x, {
      get initialSessions() {
        return a(N);
      },
      get person() {
        return r;
      },
      get personId() {
        return u;
      },
      get isUserProfile() {
        return i;
      },
      get isSystemAdmin() {
        return o;
      }
    });
  }
  var R = f(Pt, 2);
  let X;
  var we = l(R);
  Su(we, {
    get personId() {
      return u;
    },
    get load() {
      return a(h);
    }
  });
  var de = f(R, 2);
  let Ce;
  var le = l(de);
  Lu(le, {
    get personId() {
      return u;
    },
    get load() {
      return a(g);
    }
  });
  var be = f(de, 2);
  {
    var Le = (N) => {
      var O = Wu();
      let D;
      var ne = l(O);
      Vu(ne, {
        get personId() {
          return u;
        },
        get load() {
          return a(k);
        }
      }), B(() => D = je(O, 1, "tab-pane fade", null, D, {
        show: a(y) === "logins",
        active: a(y) === "logins"
      })), E(N, O);
    };
    Y(be, (N) => {
      s && N(Le);
    });
  }
  B(() => {
    I(Te, V), I(J, F), ie !== (ie = a(y)) && ($.value = ($.__value = a(y)) ?? "", Ys($, a(y))), ot = je(lt, 1, "nav-link", null, ot, { active: a(y) === "profile" }), Ee(lt, "aria-selected", a(y) === "profile"), kt = je(qe, 1, "nav-link", null, kt, { active: a(y) === "sessions" }), Ee(qe, "aria-selected", a(y) === "sessions"), I($t, V), ut = je(dt, 1, "nav-link", null, ut, { active: a(y) === "attended" }), Ee(dt, "aria-selected", a(y) === "attended"), I(Et, F), Tt = je(qt, 1, "nav-link", null, Tt, { active: a(y) === "tunes" }), Ee(qt, "aria-selected", a(y) === "tunes"), en = je(Bt, 1, "tab-pane fade", null, en, {
      show: a(y) === "profile",
      active: a(y) === "profile"
    }), Ct = je(Pt, 1, "tab-pane fade", null, Ct, {
      show: a(y) === "sessions",
      active: a(y) === "sessions"
    }), X = je(R, 1, "tab-pane fade", null, X, {
      show: a(y) === "attended",
      active: a(y) === "attended"
    }), Ce = je(de, 1, "tab-pane fade", null, Ce, {
      show: a(y) === "tunes",
      active: a(y) === "tunes"
    });
  }), M("change", $, (N) => m(N.currentTarget.value)), M("click", lt, () => m("profile")), M("click", qe, () => m("sessions")), M("click", dt, () => m("attended")), M("click", qt, () => m("tunes")), E(e, Q), On();
}
ts(["click", "change"]);
const za = document.getElementById("person-details-root");
za && window.__PAGE_DATA__ && ud(Ku, {
  target: za,
  props: {
    pageData: window.__PAGE_DATA__,
    ctx: window.__PAGE_CTX__ || {}
  }
});
