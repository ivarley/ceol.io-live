var wi = Object.defineProperty;
var nr = (e) => {
  throw TypeError(e);
};
var mi = (e, t, n) => t in e ? wi(e, t, { enumerable: !0, configurable: !0, writable: !0, value: n }) : e[t] = n;
var J = (e, t, n) => mi(e, typeof t != "symbol" ? t + "" : t, n), An = (e, t, n) => t.has(e) || nr("Cannot " + n);
var l = (e, t, n) => (An(e, t, "read from private field"), n ? n.call(e) : t.get(e)), S = (e, t, n) => t.has(e) ? nr("Cannot add the same private member more than once") : t instanceof WeakSet ? t.add(e) : t.set(e, n), m = (e, t, n, r) => (An(e, t, "write to private field"), r ? r.call(e, n) : t.set(e, n), n), T = (e, t, n) => (An(e, t, "access private method"), n);
var Er = Array.isArray, yi = Array.prototype.indexOf, dn = Array.prototype.includes, bn = Array.from, Ei = Object.defineProperty, jt = Object.getOwnPropertyDescriptor, bi = Object.getOwnPropertyDescriptors, Si = Object.prototype, ki = Array.prototype, br = Object.getPrototypeOf, rr = Object.isExtensible;
const xi = () => {
};
function Ti(e) {
  for (var t = 0; t < e.length; t++)
    e[t]();
}
function Sr() {
  var e, t, n = new Promise((r, i) => {
    e = r, t = i;
  });
  return { promise: n, resolve: e, reject: t };
}
const B = 2, Ht = 4, Sn = 8, kr = 1 << 24, ge = 16, me = 32, Ue = 64, Rn = 128, ae = 512, I = 1024, j = 2048, Ae = 4096, U = 8192, ue = 16384, Dt = 32768, ir = 1 << 25, Tt = 65536, hn = 1 << 17, Ai = 1 << 18, Nt = 1 << 19, Ci = 1 << 20, xe = 1 << 25, lt = 65536, vn = 1 << 21, wt = 1 << 22, qe = 1 << 23, Cn = Symbol("$state"), Mi = Symbol(""), fn = Symbol("attributes"), Di = Symbol("class"), Ni = Symbol("style"), Rt = Symbol("text"), kn = new class extends Error {
  constructor() {
    super(...arguments);
    J(this, "name", "StaleReactionError");
    J(this, "message", "The reaction that called `getAbortSignal()` was re-run or destroyed");
  }
}();
function Oi() {
  throw new Error("https://svelte.dev/e/async_derived_orphan");
}
function Ri(e, t, n) {
  throw new Error("https://svelte.dev/e/each_key_duplicate");
}
function Ii(e) {
  throw new Error("https://svelte.dev/e/effect_in_teardown");
}
function Li() {
  throw new Error("https://svelte.dev/e/effect_in_unowned_derived");
}
function Fi(e) {
  throw new Error("https://svelte.dev/e/effect_orphan");
}
function Pi() {
  throw new Error("https://svelte.dev/e/effect_update_depth_exceeded");
}
function ji() {
  throw new Error("https://svelte.dev/e/state_descriptors_fixed");
}
function Bi() {
  throw new Error("https://svelte.dev/e/state_prototype_fixed");
}
function zi() {
  throw new Error("https://svelte.dev/e/state_unsafe_mutation");
}
function Hi() {
  throw new Error("https://svelte.dev/e/svelte_boundary_reset_onerror");
}
const qi = 1, Vi = 2, xr = 4, Ui = 8, Yi = 16, Gi = 1, $i = 2, R = Symbol("uninitialized"), Ki = "http://www.w3.org/1999/xhtml";
function Wi() {
  console.warn("https://svelte.dev/e/derived_inert");
}
function Qi() {
  console.warn("https://svelte.dev/e/svelte_boundary_reset_noop");
}
function Tr(e) {
  return e === this.v;
}
function Zi(e, t) {
  return e != e ? t == t : e !== t || e !== null && typeof e == "object" || typeof e == "function";
}
function Ar(e) {
  return !Zi(e, this.v);
}
let Q = null;
function At(e) {
  Q = e;
}
function Cr(e, t = !1, n) {
  Q = {
    p: Q,
    i: !1,
    c: null,
    e: null,
    s: e,
    x: null,
    r: (
      /** @type {Effect} */
      x
    ),
    l: null
  };
}
function Mr(e) {
  var t = (
    /** @type {ComponentContext} */
    Q
  ), n = t.e;
  if (n !== null) {
    t.e = null;
    for (var r of n)
      Wr(r);
  }
  return t.i = !0, Q = t.p, /** @type {T} */
  {};
}
function Dr() {
  return !0;
}
let _t = [];
function Ji() {
  var e = _t;
  _t = [], Ti(e);
}
function nt(e) {
  if (_t.length === 0) {
    var t = _t;
    queueMicrotask(() => {
      t === _t && Ji();
    });
  }
  _t.push(e);
}
function Nr(e) {
  var t = x;
  if (t === null)
    return k.f |= qe, e;
  if (!(t.f & Dt) && !(t.f & Ht))
    throw e;
  He(e, t);
}
function He(e, t) {
  if (!(t !== null && t.f & ue)) {
    for (; t !== null; ) {
      if (t.f & Rn) {
        if (!(t.f & Dt))
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
const Xi = -7169;
function O(e, t) {
  e.f = e.f & Xi | t;
}
function Un(e) {
  e.f & ae || e.deps === null ? O(e, I) : O(e, Ae);
}
function Or(e) {
  if (e !== null)
    for (const t of e)
      !(t.f & B) || !(t.f & lt) || (t.f ^= lt, Or(
        /** @type {Derived} */
        t.deps
      ));
}
function Rr(e, t, n) {
  e.f & j ? t.add(e) : e.f & Ae && n.add(e), Or(e.deps), O(e, I);
}
function es(e) {
  let t = 0, n = ot(0), r;
  return () => {
    Wn() && (w(n), Cs(() => (t === 0 && (r = fi(() => e(() => zt(n)))), t += 1, () => {
      nt(() => {
        t -= 1, t === 0 && (r == null || r(), r = void 0, zt(n));
      });
    })));
  };
}
var ts = Tt | Nt;
function ns(e, t, n, r) {
  new rs(e, t, n, r);
}
var se, Vn, le, Ze, G, fe, V, ee, Oe, Je, Be, mt, Vt, Ut, Re, mn, N, is, ss, ls, In, on, an, Ln, Fn;
class rs {
  /**
   * @param {TemplateNode} node
   * @param {BoundaryProps} props
   * @param {((anchor: Node) => void)} children
   * @param {((error: unknown) => unknown) | undefined} [transform_error]
   */
  constructor(t, n, r, i) {
    S(this, N);
    /** @type {Boundary | null} */
    J(this, "parent");
    J(this, "is_pending", !1);
    /**
     * API-level transformError transform function. Transforms errors before they reach the `failed` snippet.
     * Inherited from parent boundary, or defaults to identity.
     * @type {(error: unknown) => unknown}
     */
    J(this, "transform_error");
    /** @type {TemplateNode} */
    S(this, se);
    /** @type {TemplateNode | null} */
    S(this, Vn, null);
    /** @type {BoundaryProps} */
    S(this, le);
    /** @type {((anchor: Node) => void)} */
    S(this, Ze);
    /** @type {Effect} */
    S(this, G);
    /** @type {Effect | null} */
    S(this, fe, null);
    /** @type {Effect | null} */
    S(this, V, null);
    /** @type {Effect | null} */
    S(this, ee, null);
    /** @type {DocumentFragment | null} */
    S(this, Oe, null);
    S(this, Je, 0);
    S(this, Be, 0);
    S(this, mt, !1);
    /** @type {Set<Effect>} */
    S(this, Vt, /* @__PURE__ */ new Set());
    /** @type {Set<Effect>} */
    S(this, Ut, /* @__PURE__ */ new Set());
    /**
     * A source containing the number of pending async deriveds/expressions.
     * Only created if `$effect.pending()` is used inside the boundary,
     * otherwise updating the source results in needless `Batch.ensure()`
     * calls followed by no-op flushes
     * @type {Source<number> | null}
     */
    S(this, Re, null);
    S(this, mn, es(() => (m(this, Re, ot(l(this, Je))), () => {
      m(this, Re, null);
    })));
    var s;
    m(this, se, t), m(this, le, n), m(this, Ze, (o) => {
      var a = (
        /** @type {Effect} */
        x
      );
      a.b = this, a.f |= Rn, r(o);
    }), this.parent = /** @type {Effect} */
    x.b, this.transform_error = i ?? ((s = this.parent) == null ? void 0 : s.transform_error) ?? ((o) => o), m(this, G, Qn(() => {
      T(this, N, In).call(this);
    }, ts));
  }
  /**
   * Defer an effect inside a pending boundary until the boundary resolves
   * @param {Effect} effect
   */
  defer_effect(t) {
    Rr(t, l(this, Vt), l(this, Ut));
  }
  /**
   * Returns `false` if the effect exists inside a boundary whose pending snippet is shown
   * @returns {boolean}
   */
  is_rendered() {
    return !this.is_pending && (!this.parent || this.parent.is_rendered());
  }
  has_pending_snippet() {
    return !!l(this, le).pending;
  }
  /**
   * Update the source that powers `$effect.pending()` inside this boundary,
   * and controls when the current `pending` snippet (if any) is removed.
   * Do not call from inside the class
   * @param {1 | -1} d
   * @param {Batch} batch
   */
  update_pending_count(t, n) {
    T(this, N, Ln).call(this, t, n), m(this, Je, l(this, Je) + t), !(!l(this, Re) || l(this, mt)) && (m(this, mt, !0), nt(() => {
      m(this, mt, !1), l(this, Re) && Ct(l(this, Re), l(this, Je));
    }));
  }
  get_effect_pending() {
    return l(this, mn).call(this), w(
      /** @type {Source<number>} */
      l(this, Re)
    );
  }
  /** @param {unknown} error */
  error(t) {
    if (!l(this, le).onerror && !l(this, le).failed)
      throw t;
    y != null && y.is_fork ? (l(this, fe) && y.skip_effect(l(this, fe)), l(this, V) && y.skip_effect(l(this, V)), l(this, ee) && y.skip_effect(l(this, ee)), y.oncommit(() => {
      T(this, N, Fn).call(this, t);
    })) : T(this, N, Fn).call(this, t);
  }
}
se = new WeakMap(), Vn = new WeakMap(), le = new WeakMap(), Ze = new WeakMap(), G = new WeakMap(), fe = new WeakMap(), V = new WeakMap(), ee = new WeakMap(), Oe = new WeakMap(), Je = new WeakMap(), Be = new WeakMap(), mt = new WeakMap(), Vt = new WeakMap(), Ut = new WeakMap(), Re = new WeakMap(), mn = new WeakMap(), N = new WeakSet(), is = function() {
  try {
    m(this, fe, oe(() => l(this, Ze).call(this, l(this, se))));
  } catch (t) {
    this.error(t);
  }
}, /**
 * @param {unknown} error The deserialized error from the server's hydration comment
 */
ss = function(t) {
  const n = l(this, le).failed;
  n && m(this, ee, oe(() => {
    n(
      l(this, se),
      () => t,
      () => () => {
      }
    );
  }));
}, ls = function() {
  const t = l(this, le).pending;
  t && (this.is_pending = !0, m(this, V, oe(() => t(l(this, se)))), nt(() => {
    var n = m(this, Oe, document.createDocumentFragment()), r = Ve();
    n.append(r), m(this, fe, T(this, N, an).call(this, () => oe(() => l(this, Ze).call(this, r)))), l(this, Be) === 0 && (l(this, se).before(n), m(this, Oe, null), it(
      /** @type {Effect} */
      l(this, V),
      () => {
        m(this, V, null);
      }
    ), T(this, N, on).call(
      this,
      /** @type {Batch} */
      y
    ));
  }));
}, In = function() {
  try {
    if (this.is_pending = this.has_pending_snippet(), m(this, Be, 0), m(this, Je, 0), m(this, fe, oe(() => {
      l(this, Ze).call(this, l(this, se));
    })), l(this, Be) > 0) {
      var t = m(this, Oe, document.createDocumentFragment());
      Jn(l(this, fe), t);
      const n = (
        /** @type {(anchor: Node) => void} */
        l(this, le).pending
      );
      m(this, V, oe(() => n(l(this, se))));
    } else
      T(this, N, on).call(
        this,
        /** @type {Batch} */
        y
      );
  } catch (n) {
    this.error(n);
  }
}, /**
 * @param {Batch} batch
 */
on = function(t) {
  this.is_pending = !1, t.transfer_effects(l(this, Vt), l(this, Ut));
}, /**
 * @template T
 * @param {() => T} fn
 */
an = function(t) {
  var n = x, r = k, i = Q;
  Ce(l(this, G)), ce(l(this, G)), At(l(this, G).ctx);
  try {
    return ft.ensure(), t();
  } catch (s) {
    return Nr(s), null;
  } finally {
    Ce(n), ce(r), At(i);
  }
}, /**
 * Updates the pending count associated with the currently visible pending snippet,
 * if any, such that we can replace the snippet with content once work is done
 * @param {1 | -1} d
 * @param {Batch} batch
 */
Ln = function(t, n) {
  var r;
  if (!this.has_pending_snippet()) {
    this.parent && T(r = this.parent, N, Ln).call(r, t, n);
    return;
  }
  m(this, Be, l(this, Be) + t), l(this, Be) === 0 && (T(this, N, on).call(this, n), l(this, V) && it(l(this, V), () => {
    m(this, V, null);
  }), l(this, Oe) && (l(this, se).before(l(this, Oe)), m(this, Oe, null)));
}, /**
 * @param {unknown} error
 */
Fn = function(t) {
  l(this, fe) && (Z(l(this, fe)), m(this, fe, null)), l(this, V) && (Z(l(this, V)), m(this, V, null)), l(this, ee) && (Z(l(this, ee)), m(this, ee, null));
  var n = l(this, le).onerror;
  let r = l(this, le).failed;
  var i = !1, s = !1;
  const o = () => {
    if (i) {
      Qi();
      return;
    }
    i = !0, s && Hi(), l(this, ee) !== null && it(l(this, ee), () => {
      m(this, ee, null);
    }), T(this, N, an).call(this, () => {
      T(this, N, In).call(this);
    });
  }, a = (f) => {
    try {
      s = !0, n == null || n(f, o), s = !1;
    } catch (c) {
      He(c, l(this, G) && l(this, G).parent);
    }
    r && m(this, ee, T(this, N, an).call(this, () => {
      try {
        return oe(() => {
          var c = (
            /** @type {Effect} */
            x
          );
          c.b = this, c.f |= Rn, r(
            l(this, se),
            () => f,
            () => o
          );
        });
      } catch (c) {
        return He(
          c,
          /** @type {Effect} */
          l(this, G).parent
        ), null;
      }
    }));
  };
  nt(() => {
    var f;
    try {
      f = this.transform_error(t);
    } catch (c) {
      He(c, l(this, G) && l(this, G).parent);
      return;
    }
    f !== null && typeof f == "object" && typeof /** @type {any} */
    f.then == "function" ? f.then(
      a,
      /** @param {unknown} e */
      (c) => He(c, l(this, G) && l(this, G).parent)
    ) : a(f);
  });
};
function fs(e, t, n, r) {
  const i = Yn;
  var s = e.filter((h) => !h.settled), o = t.map(i);
  if (n.length === 0 && s.length === 0) {
    r(o);
    return;
  }
  var a = (
    /** @type {Effect} */
    x
  ), f = os(), c = s.length === 1 ? s[0].promise : s.length > 1 ? Promise.all(s.map((h) => h.promise)) : null;
  function d(h) {
    if (!(a.f & ue)) {
      f();
      try {
        r([...o, ...h]);
      } catch (_) {
        He(_, a);
      }
      _n();
    }
  }
  var p = Ir();
  if (n.length === 0) {
    c.then(() => d([])).finally(p);
    return;
  }
  function u() {
    Promise.all(n.map((h) => /* @__PURE__ */ as(h))).then(d).catch((h) => He(h, a)).finally(p);
  }
  c ? c.then(() => {
    f(), u(), _n();
  }) : u();
}
function os() {
  var e = (
    /** @type {Effect} */
    x
  ), t = k, n = Q, r = (
    /** @type {Batch} */
    y
  );
  return function(s = !0) {
    Ce(e), ce(t), At(n), s && !(e.f & ue) && (r == null || r.activate(), r == null || r.apply());
  };
}
function _n(e = !0) {
  Ce(null), ce(null), At(null), e && (y == null || y.deactivate());
}
function Ir() {
  var e = (
    /** @type {Effect} */
    x
  ), t = e.b, n = (
    /** @type {Batch} */
    y
  ), r = !!(t != null && t.is_rendered());
  return t == null || t.update_pending_count(1, n), n.increment(r, e), () => {
    t == null || t.update_pending_count(-1, n), n.decrement(r, e);
  };
}
// @__NO_SIDE_EFFECTS__
function Yn(e) {
  var t = B | j;
  return x !== null && (x.f |= Nt), {
    ctx: Q,
    deps: null,
    effects: null,
    equals: Tr,
    f: t,
    fn: e,
    reactions: null,
    rv: 0,
    v: (
      /** @type {V} */
      R
    ),
    wv: 0,
    parent: x,
    ac: null
  };
}
const It = Symbol("obsolete");
// @__NO_SIDE_EFFECTS__
function as(e, t, n) {
  let r = (
    /** @type {Effect | null} */
    x
  );
  r === null && Oi();
  var i = (
    /** @type {Promise<V>} */
    /** @type {unknown} */
    void 0
  ), s = ot(
    /** @type {V} */
    R
  ), o = !k, a = /* @__PURE__ */ new Set();
  return As(() => {
    var h, _;
    var f = (
      /** @type {Effect} */
      x
    ), c = Sr();
    i = c.promise;
    try {
      Promise.resolve(e()).then(c.resolve, (g) => {
        g !== kn && c.reject(g);
      }).finally(_n);
    } catch (g) {
      c.reject(g), _n();
    }
    var d = (
      /** @type {Batch} */
      y
    );
    if (o) {
      if (f.f & Dt)
        var p = Ir();
      if (
        // boundary can be null if the async derived is inside an $effect.root not connected to the component render tree
        (h = r.b) != null && h.is_rendered()
      )
        (_ = d.async_deriveds.get(f)) == null || _.reject(It);
      else
        for (const g of a.values())
          g.reject(It);
      a.add(c), d.async_deriveds.set(f, c);
    }
    const u = (g, v = void 0) => {
      p == null || p(), a.delete(c), v !== It && (d.activate(), v ? (s.f |= qe, Ct(s, v)) : (s.f & qe && (s.f ^= qe), Ct(s, g)), d.deactivate());
    };
    c.promise.then(u, (g) => u(null, g || "unknown"));
  }), ks(() => {
    for (const f of a)
      f.reject(It);
  }), new Promise((f) => {
    function c(d) {
      function p() {
        d === i ? f(s) : c(i);
      }
      d.then(p, p);
    }
    c(i);
  });
}
// @__NO_SIDE_EFFECTS__
function sr(e) {
  const t = /* @__PURE__ */ Yn(e);
  return ei(t), t;
}
// @__NO_SIDE_EFFECTS__
function us(e) {
  const t = /* @__PURE__ */ Yn(e);
  return t.equals = Ar, t;
}
function cs(e) {
  var t = e.effects;
  if (t !== null) {
    e.effects = null;
    for (var n = 0; n < t.length; n += 1)
      Z(
        /** @type {Effect} */
        t[n]
      );
  }
}
function Gn(e) {
  var t, n = x, r = e.parent;
  if (!Ye && r !== null && e.v !== R && // if it was never evaluated before, it's guaranteed to fail downstream, so we try to execute instead
  r.f & (ue | U))
    return Wi(), e.v;
  Ce(r);
  try {
    e.f &= ~lt, cs(e), t = ii(e);
  } finally {
    Ce(n);
  }
  return t;
}
function Lr(e) {
  var t = Gn(e);
  if (!e.equals(t) && (e.wv = ni(), (!(y != null && y.is_fork) || e.deps === null) && (y !== null ? (y.capture(e, t, !0), Bt == null || Bt.capture(e, t, !0)) : e.v = t, e.deps === null))) {
    O(e, I);
    return;
  }
  Ye || (P !== null ? (Wn() || y != null && y.is_fork) && P.set(e, t) : Un(e));
}
function ds(e) {
  var t, n;
  if (e.effects !== null)
    for (const r of e.effects)
      (r.teardown || r.ac) && ((t = r.teardown) == null || t.call(r), (n = r.ac) == null || n.abort(kn), r.fn !== null && (r.teardown = xi), r.ac = null, qt(r, 0), Zn(r));
}
function Fr(e) {
  if (e.effects !== null)
    for (const t of e.effects)
      t.teardown && t.fn !== null && Mt(t);
}
let Mn = null, dt = null, y = null, Bt = null, P = null, Pn = null, Dn = !1, pt = null, un = null;
var lr = 0;
let hs = 1;
var yt, ze, Xe, Et, bt, St, Ie, kt, $, Yt, Le, _e, Se, xt, et, C, jn, Lt, Bn, Pr, jr, vt, vs, Ft;
const yn = class yn {
  constructor() {
    S(this, C);
    J(this, "id", hs++);
    /** True as soon as `#process` was called */
    S(this, yt, !1);
    J(this, "linked", !0);
    /** @type {Batch | null} */
    S(this, ze, null);
    /** @type {Batch | null} */
    S(this, Xe, null);
    /** @type {Map<Effect, ReturnType<typeof deferred<any>>>} */
    J(this, "async_deriveds", /* @__PURE__ */ new Map());
    /**
     * The current values of any signals that are updated in this batch.
     * Tuple format: [value, is_derived] (note: is_derived is false for deriveds, too, if they were overridden via assignment)
     * They keys of this map are identical to `this.#previous`
     * @type {Map<Value, [any, boolean]>}
     */
    J(this, "current", /* @__PURE__ */ new Map());
    /**
     * The values of any signals (sources and deriveds) that are updated in this batch _before_ those updates took place.
     * They keys of this map are identical to `this.#current`
     * @type {Map<Value, any>}
     */
    J(this, "previous", /* @__PURE__ */ new Map());
    /**
     * When the batch is committed (and the DOM is updated), we need to remove old branches
     * and append new ones by calling the functions added inside (if/each/key/etc) blocks
     * @type {Set<(batch: Batch) => void>}
     */
    S(this, Et, /* @__PURE__ */ new Set());
    /**
     * If a fork is discarded, we need to destroy any effects that are no longer needed
     * @type {Set<(batch: Batch) => void>}
     */
    S(this, bt, /* @__PURE__ */ new Set());
    /**
     * The number of async effects that are currently in flight
     */
    S(this, St, 0);
    /**
     * Async effects that are currently in flight, _not_ inside a pending boundary
     * @type {Map<Effect, number>}
     */
    S(this, Ie, /* @__PURE__ */ new Map());
    /**
     * A deferred that resolves when the batch is committed, used with `settled()`
     * TODO replace with Promise.withResolvers once supported widely enough
     * @type {{ promise: Promise<void>, resolve: (value?: any) => void, reject: (reason: unknown) => void } | null}
     */
    S(this, kt, null);
    /**
     * The root effects that need to be flushed
     * @type {Effect[]}
     */
    S(this, $, []);
    /**
     * Effects created while this batch was active.
     * @type {Effect[]}
     */
    S(this, Yt, []);
    /**
     * Deferred effects (which run after async work has completed) that are DIRTY
     * @type {Set<Effect>}
     */
    S(this, Le, /* @__PURE__ */ new Set());
    /**
     * Deferred effects that are MAYBE_DIRTY
     * @type {Set<Effect>}
     */
    S(this, _e, /* @__PURE__ */ new Set());
    /**
     * A map of branches that still exist, but will be destroyed when this batch
     * is committed — we skip over these during `process`.
     * The value contains child effects that were dirty/maybe_dirty before being reset,
     * so they can be rescheduled if the branch survives.
     * @type {Map<Effect, { d: Effect[], m: Effect[] }>}
     */
    S(this, Se, /* @__PURE__ */ new Map());
    /**
     * Inverse of #skipped_branches which we need to tell prior batches to unskip them when committing
     * @type {Set<Effect>}
     */
    S(this, xt, /* @__PURE__ */ new Set());
    J(this, "is_fork", !1);
    S(this, et, !1);
    dt === null ? Mn = dt = this : (m(dt, Xe, this), m(this, ze, dt)), dt = this;
  }
  /**
   * Add an effect to the #skipped_branches map and reset its children
   * @param {Effect} effect
   */
  skip_effect(t) {
    l(this, Se).has(t) || l(this, Se).set(t, { d: [], m: [] }), l(this, xt).delete(t);
  }
  /**
   * Remove an effect from the #skipped_branches map and reschedule
   * any tracked dirty/maybe_dirty child effects
   * @param {Effect} effect
   * @param {(e: Effect) => void} callback
   */
  unskip_effect(t, n = (r) => this.schedule(r)) {
    var r = l(this, Se).get(t);
    if (r) {
      l(this, Se).delete(t);
      for (var i of r.d)
        O(i, j), n(i);
      for (i of r.m)
        O(i, Ae), n(i);
    }
    l(this, xt).add(t);
  }
  /**
   * Associate a change to a given source with the current
   * batch, noting its previous and current values
   * @param {Value} source
   * @param {any} value
   * @param {boolean} [is_derived]
   */
  capture(t, n, r = !1) {
    t.v !== R && !this.previous.has(t) && this.previous.set(t, t.v), t.f & qe || (this.current.set(t, [n, r]), P == null || P.set(t, n)), this.is_fork || (t.v = n);
  }
  activate() {
    y = this;
  }
  deactivate() {
    y = null, P = null;
  }
  flush() {
    try {
      Dn = !0, y = this, T(this, C, Lt).call(this);
    } finally {
      lr = 0, Pn = null, pt = null, un = null, Dn = !1, y = null, P = null, rt.clear();
    }
  }
  discard() {
    var t;
    for (const n of l(this, bt)) n(this);
    l(this, bt).clear();
    for (const n of this.async_deriveds.values())
      n.reject(It);
    T(this, C, Ft).call(this), (t = l(this, kt)) == null || t.resolve();
  }
  /**
   * @param {Effect} effect
   */
  register_created_effect(t) {
    l(this, Yt).push(t);
  }
  /**
   * @param {boolean} blocking
   * @param {Effect} effect
   */
  increment(t, n) {
    if (m(this, St, l(this, St) + 1), t) {
      let r = l(this, Ie).get(n) ?? 0;
      l(this, Ie).set(n, r + 1);
    }
  }
  /**
   * @param {boolean} blocking
   * @param {Effect} effect
   */
  decrement(t, n) {
    if (m(this, St, l(this, St) - 1), t) {
      let r = l(this, Ie).get(n) ?? 0;
      r === 1 ? l(this, Ie).delete(n) : l(this, Ie).set(n, r - 1);
    }
    l(this, et) || (m(this, et, !0), nt(() => {
      m(this, et, !1), this.linked && this.flush();
    }));
  }
  /**
   * @param {Set<Effect>} dirty_effects
   * @param {Set<Effect>} maybe_dirty_effects
   */
  transfer_effects(t, n) {
    for (const r of t)
      l(this, Le).add(r);
    for (const r of n)
      l(this, _e).add(r);
    t.clear(), n.clear();
  }
  /** @param {(batch: Batch) => void} fn */
  oncommit(t) {
    l(this, Et).add(t);
  }
  /** @param {(batch: Batch) => void} fn */
  ondiscard(t) {
    l(this, bt).add(t);
  }
  settled() {
    return (l(this, kt) ?? m(this, kt, Sr())).promise;
  }
  static ensure() {
    if (y === null) {
      const t = y = new yn();
      Dn || nt(() => {
        l(t, yt) || t.flush();
      });
    }
    return y;
  }
  apply() {
    {
      P = null;
      return;
    }
  }
  /**
   *
   * @param {Effect} effect
   */
  schedule(t) {
    var i;
    if (Pn = t, (i = t.b) != null && i.is_pending && t.f & (Ht | Sn | kr) && !(t.f & Dt)) {
      t.b.defer_effect(t);
      return;
    }
    for (var n = t; n.parent !== null; ) {
      n = n.parent;
      var r = n.f;
      if (pt !== null && n === x && (k === null || !(k.f & B)))
        return;
      if (r & (Ue | me)) {
        if (!(r & I))
          return;
        n.f ^= I;
      }
    }
    l(this, $).push(n);
  }
};
yt = new WeakMap(), ze = new WeakMap(), Xe = new WeakMap(), Et = new WeakMap(), bt = new WeakMap(), St = new WeakMap(), Ie = new WeakMap(), kt = new WeakMap(), $ = new WeakMap(), Yt = new WeakMap(), Le = new WeakMap(), _e = new WeakMap(), Se = new WeakMap(), xt = new WeakMap(), et = new WeakMap(), C = new WeakSet(), jn = function() {
  if (this.is_fork) return !0;
  for (const r of l(this, Ie).keys()) {
    for (var t = r, n = !1; t.parent !== null; ) {
      if (l(this, Se).has(t)) {
        n = !0;
        break;
      }
      t = t.parent;
    }
    if (!n)
      return !0;
  }
  return !1;
}, Lt = function() {
  var f, c, d, p;
  m(this, yt, !0), lr++ > 1e3 && (T(this, C, Ft).call(this), _s());
  for (const u of l(this, Le))
    l(this, _e).delete(u), O(u, j), this.schedule(u);
  for (const u of l(this, _e))
    O(u, Ae), this.schedule(u);
  const t = l(this, $);
  m(this, $, []), this.apply();
  var n = pt = [], r = [], i = un = [];
  for (const u of t)
    try {
      T(this, C, Bn).call(this, u, n, r);
    } catch (h) {
      throw Hr(u), T(this, C, jn).call(this) || this.discard(), h;
    }
  if (y = null, i.length > 0) {
    var s = yn.ensure();
    for (const u of i)
      s.schedule(u);
  }
  if (pt = null, un = null, T(this, C, jn).call(this)) {
    T(this, C, vt).call(this, r), T(this, C, vt).call(this, n);
    for (const [u, h] of l(this, Se))
      zr(u, h);
    i.length > 0 && /** @type {unknown} */
    T(f = y, C, Lt).call(f);
    return;
  }
  const o = T(this, C, Pr).call(this);
  if (o) {
    T(this, C, vt).call(this, r), T(this, C, vt).call(this, n), T(c = o, C, jr).call(c, this);
    return;
  }
  l(this, Le).clear(), l(this, _e).clear();
  for (const u of l(this, Et)) u(this);
  l(this, Et).clear(), Bt = this, fr(r), fr(n), Bt = null, (d = l(this, kt)) == null || d.resolve();
  var a = (
    /** @type {Batch | null} */
    /** @type {unknown} */
    y
  );
  if (l(this, St) === 0 && (l(this, $).length === 0 || a !== null) && T(this, C, Ft).call(this), l(this, $).length > 0)
    if (a !== null) {
      const u = a;
      l(u, $).push(...l(this, $).filter((h) => !l(u, $).includes(h)));
    } else
      a = this;
  a !== null && T(p = a, C, Lt).call(p);
}, /**
 * Traverse the effect tree, executing effects or stashing
 * them for later execution as appropriate
 * @param {Effect} root
 * @param {Effect[]} effects
 * @param {Effect[]} render_effects
 */
Bn = function(t, n, r) {
  t.f ^= I;
  for (var i = t.first; i !== null; ) {
    var s = i.f, o = (s & (me | Ue)) !== 0, a = o && (s & I) !== 0, f = a || (s & U) !== 0 || l(this, Se).has(i);
    if (!f && i.fn !== null) {
      o ? i.f ^= I : s & Ht ? n.push(i) : Wt(i) && (s & ge && l(this, _e).add(i), Mt(i));
      var c = i.first;
      if (c !== null) {
        i = c;
        continue;
      }
    }
    for (; i !== null; ) {
      var d = i.next;
      if (d !== null) {
        i = d;
        break;
      }
      i = i.parent;
    }
  }
}, Pr = function() {
  for (var t = l(this, ze); t !== null; ) {
    if (!t.is_fork) {
      for (const [n, [, r]] of this.current)
        if (t.current.has(n) && !r)
          return t;
    }
    t = l(t, ze);
  }
  return null;
}, /**
 * @param {Batch} batch
 */
jr = function(t) {
  var r;
  for (const [i, s] of t.current)
    !this.previous.has(i) && t.previous.has(i) && this.previous.set(i, t.previous.get(i)), this.current.set(i, s);
  for (const [i, s] of t.async_deriveds) {
    const o = this.async_deriveds.get(i);
    o && s.promise.then(o.resolve).catch(o.reject);
  }
  t.async_deriveds.clear(), this.transfer_effects(l(t, Le), l(t, _e));
  const n = (i) => {
    var s = i.reactions;
    if (s !== null)
      for (const f of s) {
        var o = f.f;
        if (o & B)
          n(
            /** @type {Derived} */
            f
          );
        else {
          var a = (
            /** @type {Effect} */
            f
          );
          o & (wt | ge) && !this.async_deriveds.has(a) && (l(this, _e).delete(a), O(a, j), this.schedule(a));
        }
      }
  };
  for (const i of this.current.keys())
    n(i);
  this.oncommit(() => t.discard()), T(r = t, C, Ft).call(r), y = this, T(this, C, Lt).call(this);
}, /**
 * @param {Effect[]} effects
 */
vt = function(t) {
  for (var n = 0; n < t.length; n += 1)
    Rr(t[n], l(this, Le), l(this, _e));
}, vs = function() {
  var p;
  for (let u = Mn; u !== null; u = l(u, Xe)) {
    var t = u.id < this.id, n = [];
    for (const [h, [_, g]] of this.current) {
      if (u.current.has(h)) {
        var r = (
          /** @type {[any, boolean]} */
          u.current.get(h)[0]
        );
        if (t && _ !== r)
          u.current.set(h, [_, g]);
        else
          continue;
      }
      n.push(h);
    }
    if (t)
      for (const [h, _] of this.async_deriveds) {
        const g = u.async_deriveds.get(h);
        g && _.promise.then(g.resolve).catch(g.reject);
      }
    var i = [...u.current.keys()].filter(
      (h) => !/** @type {[any, boolean]} */
      u.current.get(h)[1]
    );
    if (!(!l(u, yt) || i.length === 0)) {
      var s = i.filter((h) => !this.current.has(h));
      if (s.length === 0)
        t && u.discard();
      else if (n.length > 0) {
        if (t)
          for (const h of l(this, xt))
            u.unskip_effect(h, (_) => {
              var g;
              _.f & (ge | wt) ? u.schedule(_) : T(g = u, C, vt).call(g, [_]);
            });
        u.activate();
        var o = /* @__PURE__ */ new Set(), a = /* @__PURE__ */ new Map();
        for (var f of n)
          Br(f, s, o, a);
        a = /* @__PURE__ */ new Map();
        var c = [...u.current].filter(([h, _]) => {
          const g = this.current.get(h);
          return g ? g[0] !== _[0] || g[1] !== _[1] : !0;
        }).map(([h]) => h);
        if (c.length > 0)
          for (const h of l(this, Yt))
            !(h.f & (ue | U | hn)) && $n(h, c, a) && (h.f & (wt | ge) ? (O(h, j), u.schedule(h)) : l(u, Le).add(h));
        if (l(u, $).length > 0 && !l(u, et)) {
          u.apply();
          for (var d of l(u, $))
            T(p = u, C, Bn).call(p, d, [], []);
          m(u, $, []);
        }
        u.deactivate();
      }
    }
  }
}, Ft = function() {
  if (this.linked) {
    var t = l(this, ze), n = l(this, Xe);
    t === null ? Mn = n : m(t, Xe, n), n === null ? dt = t : m(n, ze, t), this.linked = !1;
  }
};
let ft = yn;
function _s() {
  try {
    Pi();
  } catch (e) {
    He(e, Pn);
  }
}
let ve = null;
function fr(e) {
  var t = e.length;
  if (t !== 0) {
    for (var n = 0; n < t; ) {
      var r = e[n++];
      if (!(r.f & (ue | U)) && Wt(r) && (ve = /* @__PURE__ */ new Set(), Mt(r), r.deps === null && r.first === null && r.nodes === null && r.teardown === null && r.ac === null && Zr(r), (ve == null ? void 0 : ve.size) > 0)) {
        rt.clear();
        for (const i of ve) {
          if (i.f & (ue | U)) continue;
          const s = [i];
          let o = i.parent;
          for (; o !== null; )
            ve.has(o) && (ve.delete(o), s.push(o)), o = o.parent;
          for (let a = s.length - 1; a >= 0; a--) {
            const f = s[a];
            f.f & (ue | U) || Mt(f);
          }
        }
        ve.clear();
      }
    }
    ve = null;
  }
}
function Br(e, t, n, r) {
  if (!n.has(e) && (n.add(e), e.reactions !== null))
    for (const i of e.reactions) {
      const s = i.f;
      s & B ? Br(
        /** @type {Derived} */
        i,
        t,
        n,
        r
      ) : s & (wt | ge) && !(s & j) && $n(i, t, r) && (O(i, j), Kn(
        /** @type {Effect} */
        i
      ));
    }
}
function $n(e, t, n) {
  const r = n.get(e);
  if (r !== void 0) return r;
  if (e.deps !== null)
    for (const i of e.deps) {
      if (dn.call(t, i))
        return !0;
      if (i.f & B && $n(
        /** @type {Derived} */
        i,
        t,
        n
      ))
        return n.set(
          /** @type {Derived} */
          i,
          !0
        ), !0;
    }
  return n.set(e, !1), !1;
}
function Kn(e) {
  y.schedule(e);
}
function zr(e, t) {
  if (!(e.f & me && e.f & I)) {
    e.f & j ? t.d.push(e) : e.f & Ae && t.m.push(e), O(e, I);
    for (var n = e.first; n !== null; )
      zr(n, t), n = n.next;
  }
}
function Hr(e) {
  O(e, I);
  for (var t = e.first; t !== null; )
    Hr(t), t = t.next;
}
let pn = /* @__PURE__ */ new Set();
const rt = /* @__PURE__ */ new Map();
let qr = !1;
function ot(e, t) {
  var n = {
    f: 0,
    // TODO ideally we could skip this altogether, but it causes type errors
    v: e,
    reactions: null,
    equals: Tr,
    rv: 0,
    wv: 0
  };
  return n;
}
// @__NO_SIDE_EFFECTS__
function ne(e, t) {
  const n = ot(e);
  return ei(n), n;
}
// @__NO_SIDE_EFFECTS__
function ps(e, t = !1, n = !0) {
  const r = ot(e);
  return t || (r.equals = Ar), r;
}
function W(e, t, n = !1) {
  k !== null && // since we are untracking the function inside `$inspect.with` we need to add this check
  // to ensure we error if state is set inside an inspect effect
  (!we || k.f & hn) && Dr() && k.f & (B | ge | wt | hn) && (Te === null || !Te.has(e)) && zi();
  let r = n ? gt(t) : t;
  return Ct(e, r, un);
}
function Ct(e, t, n = null) {
  if (!e.equals(t)) {
    rt.set(e, Ye ? t : e.v);
    var r = ft.ensure();
    if (r.capture(e, t), e.f & B) {
      const i = (
        /** @type {Derived} */
        e
      );
      e.f & j && Gn(i), P === null && Un(i);
    }
    e.wv = ni(), Vr(e, j, n), x !== null && x.f & I && !(x.f & (me | Ue)) && (ie === null ? Ns([e]) : ie.push(e)), !r.is_fork && pn.size > 0 && !qr && gs();
  }
  return t;
}
function gs() {
  qr = !1;
  for (const e of pn) {
    e.f & I && O(e, Ae);
    let t;
    try {
      t = Wt(e);
    } catch {
      t = !0;
    }
    t && Mt(e);
  }
  pn.clear();
}
function zt(e) {
  W(e, e.v + 1);
}
function Vr(e, t, n) {
  var r = e.reactions;
  if (r !== null)
    for (var i = r.length, s = 0; s < i; s++) {
      var o = r[s], a = o.f, f = (a & j) === 0;
      if (f && O(o, t), a & hn)
        pn.add(
          /** @type {Effect} */
          o
        );
      else if (a & B) {
        var c = (
          /** @type {Derived} */
          o
        );
        P == null || P.delete(c), a & lt || (a & ae && (x === null || !(x.f & vn)) && (o.f |= lt), Vr(c, Ae, n));
      } else if (f) {
        var d = (
          /** @type {Effect} */
          o
        );
        a & ge && ve !== null && ve.add(d), n !== null ? n.push(d) : Kn(d);
      }
    }
}
function gt(e) {
  if (typeof e != "object" || e === null || Cn in e)
    return e;
  const t = br(e);
  if (t !== Si && t !== ki)
    return e;
  var n = /* @__PURE__ */ new Map(), r = Er(e), i = /* @__PURE__ */ ne(0), s = st, o = (a) => {
    if (st === s)
      return a();
    var f = k, c = st;
    ce(null), ur(s);
    var d = a();
    return ce(f), ur(c), d;
  };
  return r && n.set("length", /* @__PURE__ */ ne(
    /** @type {any[]} */
    e.length
  )), new Proxy(
    /** @type {any} */
    e,
    {
      defineProperty(a, f, c) {
        (!("value" in c) || c.configurable === !1 || c.enumerable === !1 || c.writable === !1) && ji();
        var d = n.get(f);
        return d === void 0 ? o(() => {
          var p = /* @__PURE__ */ ne(c.value);
          return n.set(f, p), p;
        }) : W(d, c.value, !0), !0;
      },
      deleteProperty(a, f) {
        var c = n.get(f);
        if (c === void 0) {
          if (f in a) {
            const d = o(() => /* @__PURE__ */ ne(R));
            n.set(f, d), zt(i);
          }
        } else
          W(c, R), zt(i);
        return !0;
      },
      get(a, f, c) {
        var h;
        if (f === Cn)
          return e;
        var d = n.get(f), p = f in a;
        if (d === void 0 && (!p || (h = jt(a, f)) != null && h.writable) && (d = o(() => {
          var _ = gt(p ? a[f] : R), g = /* @__PURE__ */ ne(_);
          return g;
        }), n.set(f, d)), d !== void 0) {
          var u = w(d);
          return u === R ? void 0 : u;
        }
        return Reflect.get(a, f, c);
      },
      getOwnPropertyDescriptor(a, f) {
        var c = Reflect.getOwnPropertyDescriptor(a, f);
        if (c && "value" in c) {
          var d = n.get(f);
          d && (c.value = w(d));
        } else if (c === void 0) {
          var p = n.get(f), u = p == null ? void 0 : p.v;
          if (p !== void 0 && u !== R)
            return {
              enumerable: !0,
              configurable: !0,
              value: u,
              writable: !0
            };
        }
        return c;
      },
      has(a, f) {
        var u;
        if (f === Cn)
          return !0;
        var c = n.get(f), d = c !== void 0 && c.v !== R || Reflect.has(a, f);
        if (c !== void 0 || x !== null && (!d || (u = jt(a, f)) != null && u.writable)) {
          c === void 0 && (c = o(() => {
            var h = d ? gt(a[f]) : R, _ = /* @__PURE__ */ ne(h);
            return _;
          }), n.set(f, c));
          var p = w(c);
          if (p === R)
            return !1;
        }
        return d;
      },
      set(a, f, c, d) {
        var M;
        var p = n.get(f), u = f in a;
        if (r && f === "length")
          for (var h = c; h < /** @type {Source<number>} */
          p.v; h += 1) {
            var _ = n.get(h + "");
            _ !== void 0 ? W(_, R) : h in a && (_ = o(() => /* @__PURE__ */ ne(R)), n.set(h + "", _));
          }
        if (p === void 0)
          (!u || (M = jt(a, f)) != null && M.writable) && (p = o(() => /* @__PURE__ */ ne(void 0)), W(p, gt(c)), n.set(f, p));
        else {
          u = p.v !== R;
          var g = o(() => gt(c));
          W(p, g);
        }
        var v = Reflect.getOwnPropertyDescriptor(a, f);
        if (v != null && v.set && v.set.call(d, c), !u) {
          if (r && typeof f == "string") {
            var E = (
              /** @type {Source<number>} */
              n.get("length")
            ), L = Number(f);
            Number.isInteger(L) && L >= E.v && W(E, L + 1);
          }
          zt(i);
        }
        return !0;
      },
      ownKeys(a) {
        w(i);
        var f = Reflect.ownKeys(a).filter((p) => {
          var u = n.get(p);
          return u === void 0 || u.v !== R;
        });
        for (var [c, d] of n)
          d.v !== R && !(c in a) && f.push(c);
        return f;
      },
      setPrototypeOf() {
        Bi();
      }
    }
  );
}
var or, Ur, Yr, Gr;
function ws() {
  if (or === void 0) {
    or = window, Ur = /Firefox/.test(navigator.userAgent);
    var e = Element.prototype, t = Node.prototype, n = Text.prototype;
    Yr = jt(t, "firstChild").get, Gr = jt(t, "nextSibling").get, rr(e) && (e[Di] = void 0, e[fn] = null, e[Ni] = void 0, e.__e = void 0), rr(n) && (n[Rt] = void 0);
  }
}
function Ve(e = "") {
  return document.createTextNode(e);
}
// @__NO_SIDE_EFFECTS__
function gn(e) {
  return (
    /** @type {TemplateNode | null} */
    Yr.call(e)
  );
}
// @__NO_SIDE_EFFECTS__
function Kt(e) {
  return (
    /** @type {TemplateNode | null} */
    Gr.call(e)
  );
}
function q(e, t) {
  return /* @__PURE__ */ gn(e);
}
function ms(e, t = !1) {
  {
    var n = /* @__PURE__ */ gn(e);
    return n instanceof Comment && n.data === "" ? /* @__PURE__ */ Kt(n) : n;
  }
}
function Ee(e, t = 1, n = !1) {
  let r = e;
  for (; t--; )
    r = /** @type {TemplateNode} */
    /* @__PURE__ */ Kt(r);
  return r;
}
function ys(e) {
  e.textContent = "";
}
function $r() {
  return !1;
}
function Es(e, t, n) {
  return (
    /** @type {T extends keyof HTMLElementTagNameMap ? HTMLElementTagNameMap[T] : Element} */
    n ? document.createElement(e, { is: n }) : document.createElement(e)
  );
}
function Kr(e) {
  var t = k, n = x;
  ce(null), Ce(null);
  try {
    return e();
  } finally {
    ce(t), Ce(n);
  }
}
function bs(e) {
  x === null && (k === null && Fi(), Li()), Ye && Ii();
}
function Ss(e, t) {
  var n = t.last;
  n === null ? t.last = t.first = e : (n.next = e, e.prev = n, t.last = e);
}
function Ge(e, t) {
  var n = x;
  n !== null && n.f & U && (e |= U);
  var r = {
    ctx: Q,
    deps: null,
    nodes: null,
    f: e | j | ae,
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
  y == null || y.register_created_effect(r);
  var i = r;
  if (e & Ht)
    pt !== null ? pt.push(r) : ft.ensure().schedule(r);
  else if (t !== null) {
    try {
      Mt(r);
    } catch (o) {
      throw Z(r), o;
    }
    i.deps === null && i.teardown === null && i.nodes === null && i.first === i.last && // either `null`, or a singular child
    !(i.f & Nt) && (i = i.first, e & ge && e & Tt && i !== null && (i.f |= Tt));
  }
  if (i !== null && (i.parent = n, n !== null && Ss(i, n), k !== null && k.f & B && !(e & Ue))) {
    var s = (
      /** @type {Derived} */
      k
    );
    (s.effects ?? (s.effects = [])).push(i);
  }
  return r;
}
function Wn() {
  return k !== null && !we;
}
function ks(e) {
  const t = Ge(Sn, null);
  return O(t, I), t.teardown = e, t;
}
function xs(e) {
  bs();
  var t = (
    /** @type {Effect} */
    x.f
  ), n = !k && (t & me) !== 0 && Q !== null && !Q.i;
  if (n) {
    var r = (
      /** @type {ComponentContext} */
      Q
    );
    (r.e ?? (r.e = [])).push(e);
  } else
    return Wr(e);
}
function Wr(e) {
  return Ge(Ht | Ci, e);
}
function Ts(e) {
  ft.ensure();
  const t = Ge(Ue | Nt, e);
  return (n = {}) => new Promise((r) => {
    n.outro ? it(t, () => {
      Z(t), r(void 0);
    }) : (Z(t), r(void 0));
  });
}
function As(e) {
  return Ge(wt | Nt, e);
}
function Cs(e, t = 0) {
  return Ge(Sn | t, e);
}
function rn(e, t = [], n = [], r = []) {
  fs(r, t, n, (i) => {
    Ge(Sn, () => {
      e(...i.map(w));
    });
  });
}
function Qn(e, t = 0) {
  var n = Ge(ge | t, e);
  return n;
}
function oe(e) {
  return Ge(me | Nt, e);
}
function Qr(e) {
  var t = e.teardown;
  if (t !== null) {
    const n = Ye, r = k;
    ar(!0), ce(null);
    try {
      t.call(null);
    } finally {
      ar(n), ce(r);
    }
  }
}
function Zn(e, t = !1) {
  var n = e.first;
  for (e.first = e.last = null; n !== null; ) {
    const i = n.ac;
    i !== null && Kr(() => {
      i.abort(kn);
    });
    var r = n.next;
    n.f & Ue ? n.parent = null : Z(n, t), n = r;
  }
}
function Ms(e) {
  for (var t = e.first; t !== null; ) {
    var n = t.next;
    t.f & me || Z(t), t = n;
  }
}
function Z(e, t = !0) {
  var n = !1;
  (t || e.f & Ai) && e.nodes !== null && e.nodes.end !== null && (Ds(
    e.nodes.start,
    /** @type {TemplateNode} */
    e.nodes.end
  ), n = !0), e.f |= ir, Zn(e, t && !n), qt(e, 0);
  var r = e.nodes && e.nodes.t;
  if (r !== null)
    for (const s of r)
      s.stop();
  Qr(e), e.f ^= ir, e.f |= ue;
  var i = e.parent;
  i !== null && i.first !== null && Zr(e), e.next = e.prev = e.teardown = e.ctx = e.deps = e.fn = e.nodes = e.ac = e.b = null;
}
function Ds(e, t) {
  for (; e !== null; ) {
    var n = e === t ? null : /* @__PURE__ */ Kt(e);
    e.remove(), e = n;
  }
}
function Zr(e) {
  var t = e.parent, n = e.prev, r = e.next;
  n !== null && (n.next = r), r !== null && (r.prev = n), t !== null && (t.first === e && (t.first = r), t.last === e && (t.last = n));
}
function it(e, t, n = !0) {
  var r = [];
  Jr(e, r, !0);
  var i = () => {
    n && Z(e), t && t();
  }, s = r.length;
  if (s > 0) {
    var o = () => --s || i();
    for (var a of r)
      a.out(o);
  } else
    i();
}
function Jr(e, t, n) {
  if (!(e.f & U)) {
    e.f ^= U;
    var r = e.nodes && e.nodes.t;
    if (r !== null)
      for (const a of r)
        (a.is_global || n) && t.push(a);
    for (var i = e.first; i !== null; ) {
      var s = i.next;
      if (!(i.f & Ue)) {
        var o = (i.f & Tt) !== 0 || // If this is a branch effect without a block effect parent,
        // it means the parent block effect was pruned. In that case,
        // transparency information was transferred to the branch effect.
        (i.f & me) !== 0 && (e.f & ge) !== 0;
        Jr(i, t, o ? n : !1);
      }
      i = s;
    }
  }
}
function wn(e) {
  Xr(e, !0);
}
function Xr(e, t) {
  if (e.f & U) {
    e.f ^= U, e.f & I || (O(e, j), ft.ensure().schedule(e));
    for (var n = e.first; n !== null; ) {
      var r = n.next, i = (n.f & Tt) !== 0 || (n.f & me) !== 0;
      Xr(n, i ? t : !1), n = r;
    }
    var s = e.nodes && e.nodes.t;
    if (s !== null)
      for (const o of s)
        (o.is_global || t) && o.in();
  }
}
function Jn(e, t) {
  if (e.nodes)
    for (var n = e.nodes.start, r = e.nodes.end; n !== null; ) {
      var i = n === r ? null : /* @__PURE__ */ Kt(n);
      t.append(n), n = i;
    }
}
let cn = !1, Ye = !1;
function ar(e) {
  Ye = e;
}
let k = null, we = !1;
function ce(e) {
  k = e;
}
let x = null;
function Ce(e) {
  x = e;
}
let Te = null;
function ei(e) {
  k !== null && (Te ?? (Te = /* @__PURE__ */ new Set())).add(e);
}
let K = null, X = 0, ie = null;
function Ns(e) {
  ie = e;
}
let ti = 1, We = 0, st = We;
function ur(e) {
  st = e;
}
function ni() {
  return ++ti;
}
function Wt(e) {
  var t = e.f;
  if (t & j)
    return !0;
  if (t & B && (e.f &= ~lt), t & Ae) {
    for (var n = (
      /** @type {Value[]} */
      e.deps
    ), r = n.length, i = 0; i < r; i++) {
      var s = n[i];
      if (Wt(
        /** @type {Derived} */
        s
      ) && Lr(
        /** @type {Derived} */
        s
      ), s.wv > e.wv)
        return !0;
    }
    t & ae && // During time traveling we don't want to reset the status so that
    // traversal of the graph in the other batches still happens
    P === null && O(e, I);
  }
  return !1;
}
function ri(e, t, n = !0) {
  var r = e.reactions;
  if (r !== null && !(Te !== null && Te.has(e)))
    for (var i = 0; i < r.length; i++) {
      var s = r[i];
      s.f & B ? ri(
        /** @type {Derived} */
        s,
        t,
        !1
      ) : t === s && (n ? O(s, j) : s.f & I && O(s, Ae), Kn(
        /** @type {Effect} */
        s
      ));
    }
}
function ii(e) {
  var g;
  var t = K, n = X, r = ie, i = k, s = Te, o = Q, a = we, f = st, c = e.f;
  K = /** @type {null | Value[]} */
  null, X = 0, ie = null, k = c & (me | Ue) ? null : e, Te = null, At(e.ctx), we = !1, st = ++We, e.ac !== null && (Kr(() => {
    e.ac.abort(kn);
  }), e.ac = null);
  try {
    e.f |= vn;
    var d = (
      /** @type {Function} */
      e.fn
    ), p = d();
    e.f |= Dt;
    var u = e.deps, h = y == null ? void 0 : y.is_fork;
    if (K !== null) {
      var _;
      if (h || qt(e, X), u !== null && X > 0)
        for (u.length = X + K.length, _ = 0; _ < K.length; _++)
          u[X + _] = K[_];
      else
        e.deps = u = K;
      if (Wn() && e.f & ae)
        for (_ = X; _ < u.length; _++)
          ((g = u[_]).reactions ?? (g.reactions = [])).push(e);
    } else !h && u !== null && X < u.length && (qt(e, X), u.length = X);
    if (Dr() && ie !== null && !we && u !== null && !(e.f & (B | Ae | j)))
      for (_ = 0; _ < /** @type {Source[]} */
      ie.length; _++)
        ri(
          ie[_],
          /** @type {Effect} */
          e
        );
    if (i !== null && i !== e) {
      if (We++, i.deps !== null)
        for (let v = 0; v < n; v += 1)
          i.deps[v].rv = We;
      if (t !== null)
        for (const v of t)
          v.rv = We;
      ie !== null && (r === null ? r = ie : r.push(.../** @type {Source[]} */
      ie));
    }
    return e.f & qe && (e.f ^= qe), p;
  } catch (v) {
    return Nr(v);
  } finally {
    e.f ^= vn, K = t, X = n, ie = r, k = i, Te = s, At(o), we = a, st = f;
  }
}
function Os(e, t) {
  let n = t.reactions;
  if (n !== null) {
    var r = yi.call(n, e);
    if (r !== -1) {
      var i = n.length - 1;
      i === 0 ? n = t.reactions = null : (n[r] = n[i], n.pop());
    }
  }
  if (n === null && t.f & B && // Destroying a child effect while updating a parent effect can cause a dependency to appear
  // to be unused, when in fact it is used by the currently-updating parent. Checking `new_deps`
  // allows us to skip the expensive work of disconnecting and immediately reconnecting it
  (K === null || !dn.call(K, t))) {
    var s = (
      /** @type {Derived} */
      t
    );
    s.f & ae && (s.f ^= ae, s.f &= ~lt), s.v !== R && Un(s), ds(s), qt(s, 0);
  }
}
function qt(e, t) {
  var n = e.deps;
  if (n !== null)
    for (var r = t; r < n.length; r++)
      Os(e, n[r]);
}
function Mt(e) {
  var t = e.f;
  if (!(t & ue)) {
    O(e, I);
    var n = x, r = cn;
    x = e, cn = !0;
    try {
      t & (ge | kr) ? Ms(e) : Zn(e), Qr(e);
      var i = ii(e);
      e.teardown = typeof i == "function" ? i : null, e.wv = ti;
      var s;
    } finally {
      cn = r, x = n;
    }
  }
}
function w(e) {
  var t = e.f, n = (t & B) !== 0;
  if (k !== null && !we) {
    var r = x !== null && (x.f & ue) !== 0;
    if (!r && (Te === null || !Te.has(e))) {
      var i = k.deps;
      if (k.f & vn)
        e.rv < We && (e.rv = We, K === null && i !== null && i[X] === e ? X++ : K === null ? K = [e] : K.push(e));
      else {
        k.deps ?? (k.deps = []), dn.call(k.deps, e) || k.deps.push(e);
        var s = e.reactions;
        s === null ? e.reactions = [k] : dn.call(s, k) || s.push(k);
      }
    }
  }
  if (Ye && rt.has(e))
    return rt.get(e);
  if (n) {
    var o = (
      /** @type {Derived} */
      e
    );
    if (Ye) {
      var a = o.v;
      return (!(o.f & I) && o.reactions !== null || li(o)) && (a = Gn(o)), rt.set(o, a), a;
    }
    var f = (o.f & ae) === 0 && !we && k !== null && (cn || (k.f & ae) !== 0), c = (o.f & Dt) === 0;
    Wt(o) && (f && (o.f |= ae), Lr(o)), f && !c && (Fr(o), si(o));
  }
  if (P != null && P.has(e))
    return P.get(e);
  if (e.f & qe)
    throw e.v;
  return e.v;
}
function si(e) {
  if (e.f |= ae, e.deps !== null)
    for (const t of e.deps)
      (t.reactions ?? (t.reactions = [])).push(e), t.f & B && !(t.f & ae) && (Fr(
        /** @type {Derived} */
        t
      ), si(
        /** @type {Derived} */
        t
      ));
}
function li(e) {
  if (e.v === R) return !0;
  if (e.deps === null) return !1;
  for (const t of e.deps)
    if (rt.has(t) || t.f & B && li(
      /** @type {Derived} */
      t
    ))
      return !0;
  return !1;
}
function fi(e) {
  var t = we;
  try {
    return we = !0, e();
  } finally {
    we = t;
  }
}
const Rs = ["touchstart", "touchmove"];
function Is(e) {
  return Rs.includes(e);
}
const Qe = Symbol("events"), oi = /* @__PURE__ */ new Set(), zn = /* @__PURE__ */ new Set();
function sn(e, t, n) {
  (t[Qe] ?? (t[Qe] = {}))[e] = n;
}
function Ls(e) {
  for (var t = 0; t < e.length; t++)
    oi.add(e[t]);
  for (var n of zn)
    n(e);
}
let cr = null;
function dr(e) {
  var g, v;
  var t = this, n = (
    /** @type {Node} */
    t.ownerDocument
  ), r = e.type, i = ((g = e.composedPath) == null ? void 0 : g.call(e)) || [], s = (
    /** @type {null | Element} */
    i[0] || e.target
  );
  cr = e;
  var o = 0, a = cr === e && e[Qe];
  if (a) {
    var f = i.indexOf(a);
    if (f !== -1 && (t === document || t === /** @type {any} */
    window)) {
      e[Qe] = t;
      return;
    }
    var c = i.indexOf(t);
    if (c === -1)
      return;
    f <= c && (o = f);
  }
  if (s = /** @type {Element} */
  i[o] || e.target, s !== t) {
    Ei(e, "currentTarget", {
      configurable: !0,
      get() {
        return s || n;
      }
    });
    var d = k, p = x;
    ce(null), Ce(null);
    try {
      for (var u, h = []; s !== null && s !== t; ) {
        try {
          var _ = (v = s[Qe]) == null ? void 0 : v[r];
          _ != null && (!/** @type {any} */
          s.disabled || // DOM could've been updated already by the time this is reached, so we check this as well
          // -> the target could not have been disabled because it emits the event in the first place
          e.target === s) && _.call(s, e);
        } catch (E) {
          u ? h.push(E) : u = E;
        }
        if (e.cancelBubble) break;
        o++, s = o < i.length ? (
          /** @type {Element} */
          i[o]
        ) : null;
      }
      if (u) {
        for (let E of h)
          queueMicrotask(() => {
            throw E;
          });
        throw u;
      }
    } finally {
      e[Qe] = t, delete e.currentTarget, ce(d), Ce(p);
    }
  }
}
var mr;
const Nn = (
  // We gotta write it like this because after downleveling the pure comment may end up in the wrong location
  ((mr = globalThis == null ? void 0 : globalThis.window) == null ? void 0 : mr.trustedTypes) && /* @__PURE__ */ globalThis.window.trustedTypes.createPolicy("svelte-trusted-html", {
    /** @param {string} html */
    createHTML: (e) => e
  })
);
function Fs(e) {
  return (
    /** @type {string} */
    (Nn == null ? void 0 : Nn.createHTML(e)) ?? e
  );
}
function Ps(e) {
  var t = Es("template");
  return t.innerHTML = Fs(e.replaceAll("<!>", "<!---->")), t.content;
}
function Hn(e, t) {
  var n = (
    /** @type {Effect} */
    x
  );
  n.nodes === null && (n.nodes = { start: e, end: t, a: null, t: null });
}
// @__NO_SIDE_EFFECTS__
function Fe(e, t) {
  var n = (t & Gi) !== 0, r = (t & $i) !== 0, i, s = !e.startsWith("<!>");
  return () => {
    i === void 0 && (i = Ps(s ? e : "<!>" + e), n || (i = /** @type {TemplateNode} */
    /* @__PURE__ */ gn(i)));
    var o = (
      /** @type {TemplateNode} */
      r || Ur ? document.importNode(i, !0) : i.cloneNode(!0)
    );
    if (n) {
      var a = (
        /** @type {TemplateNode} */
        /* @__PURE__ */ gn(o)
      ), f = (
        /** @type {TemplateNode} */
        o.lastChild
      );
      Hn(a, f);
    } else
      Hn(o, o);
    return o;
  };
}
function js(e = "") {
  {
    var t = Ve(e + "");
    return Hn(t, t), t;
  }
}
function be(e, t) {
  e !== null && e.before(
    /** @type {Node} */
    t
  );
}
function ht(e, t) {
  var n = t == null ? "" : typeof t == "object" ? `${t}` : t;
  n !== /** @type {any} */
  (e[Rt] ?? (e[Rt] = e.nodeValue)) && (e[Rt] = n, e.nodeValue = `${n}`);
}
function Bs(e, t) {
  return zs(e, t);
}
const ln = /* @__PURE__ */ new Map();
function zs(e, { target: t, anchor: n, props: r = {}, events: i, context: s, intro: o = !0, transformError: a }) {
  ws();
  var f = void 0, c = Ts(() => {
    var d = n ?? t.appendChild(Ve());
    ns(
      /** @type {TemplateNode} */
      d,
      {
        pending: () => {
        }
      },
      (h) => {
        Cr({});
        var _ = (
          /** @type {ComponentContext} */
          Q
        );
        s && (_.c = s), i && (r.$$events = i), f = e(h, r) || {}, Mr();
      },
      a
    );
    var p = /* @__PURE__ */ new Set(), u = (h) => {
      for (var _ = 0; _ < h.length; _++) {
        var g = h[_];
        if (!p.has(g)) {
          p.add(g);
          var v = Is(g);
          for (const M of [t, document]) {
            var E = ln.get(M);
            E === void 0 && (E = /* @__PURE__ */ new Map(), ln.set(M, E));
            var L = E.get(g);
            L === void 0 ? (M.addEventListener(g, dr, { passive: v }), E.set(g, 1)) : E.set(g, L + 1);
          }
        }
      }
    };
    return u(bn(oi)), zn.add(u), () => {
      var v;
      for (var h of p)
        for (const E of [t, document]) {
          var _ = (
            /** @type {Map<string, number>} */
            ln.get(E)
          ), g = (
            /** @type {number} */
            _.get(h)
          );
          --g == 0 ? (E.removeEventListener(h, dr), _.delete(h), _.size === 0 && ln.delete(E)) : _.set(h, g);
        }
      zn.delete(u), d !== n && ((v = d.parentNode) == null || v.removeChild(d));
    };
  });
  return Hs.set(f, c), f;
}
let Hs = /* @__PURE__ */ new WeakMap();
var pe, ke, te, tt, Gt, $t, En;
class qs {
  /**
   * @param {TemplateNode} anchor
   * @param {boolean} transition
   */
  constructor(t, n = !0) {
    /** @type {TemplateNode} */
    J(this, "anchor");
    /** @type {Map<Batch, Key>} */
    S(this, pe, /* @__PURE__ */ new Map());
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
    S(this, ke, /* @__PURE__ */ new Map());
    /**
     * Similar to #onscreen with respect to the keys, but contains branches that are not yet
     * in the DOM, because their insertion is deferred.
     * @type {Map<Key, Branch>}
     */
    S(this, te, /* @__PURE__ */ new Map());
    /**
     * Keys of effects that are currently outroing
     * @type {Set<Key>}
     */
    S(this, tt, /* @__PURE__ */ new Set());
    /**
     * Whether to pause (i.e. outro) on change, or destroy immediately.
     * This is necessary for `<svelte:element>`
     */
    S(this, Gt, !0);
    /**
     * @param {Batch} batch
     */
    S(this, $t, (t) => {
      if (l(this, pe).has(t)) {
        var n = (
          /** @type {Key} */
          l(this, pe).get(t)
        ), r = l(this, ke).get(n);
        if (r)
          wn(r), l(this, tt).delete(n);
        else {
          var i = l(this, te).get(n);
          i && (wn(i.effect), l(this, ke).set(n, i.effect), l(this, te).delete(n), i.fragment.lastChild.remove(), this.anchor.before(i.fragment), r = i.effect);
        }
        for (const [s, o] of l(this, pe)) {
          if (l(this, pe).delete(s), s === t)
            break;
          const a = l(this, te).get(o);
          a && (Z(a.effect), l(this, te).delete(o));
        }
        for (const [s, o] of l(this, ke)) {
          if (s === n || l(this, tt).has(s)) continue;
          const a = () => {
            if (Array.from(l(this, pe).values()).includes(s)) {
              var c = document.createDocumentFragment();
              Jn(o, c), c.append(Ve()), l(this, te).set(s, { effect: o, fragment: c });
            } else
              Z(o);
            l(this, tt).delete(s), l(this, ke).delete(s);
          };
          l(this, Gt) || !r ? (l(this, tt).add(s), it(o, a, !1)) : a();
        }
      }
    });
    /**
     * @param {Batch} batch
     */
    S(this, En, (t) => {
      l(this, pe).delete(t);
      const n = Array.from(l(this, pe).values());
      for (const [r, i] of l(this, te))
        n.includes(r) || (Z(i.effect), l(this, te).delete(r));
    });
    this.anchor = t, m(this, Gt, n);
  }
  /**
   *
   * @param {any} key
   * @param {null | ((target: TemplateNode) => void)} fn
   */
  ensure(t, n) {
    var r = (
      /** @type {Batch} */
      y
    ), i = $r();
    if (n && !l(this, ke).has(t) && !l(this, te).has(t))
      if (i) {
        var s = document.createDocumentFragment(), o = Ve();
        s.append(o), l(this, te).set(t, {
          effect: oe(() => n(o)),
          fragment: s
        });
      } else
        l(this, ke).set(
          t,
          oe(() => n(this.anchor))
        );
    if (l(this, pe).set(r, t), i) {
      for (const [a, f] of l(this, ke))
        a === t ? r.unskip_effect(f) : r.skip_effect(f);
      for (const [a, f] of l(this, te))
        a === t ? r.unskip_effect(f.effect) : r.skip_effect(f.effect);
      r.oncommit(l(this, $t)), r.ondiscard(l(this, En));
    } else
      l(this, $t).call(this, r);
  }
}
pe = new WeakMap(), ke = new WeakMap(), te = new WeakMap(), tt = new WeakMap(), Gt = new WeakMap(), $t = new WeakMap(), En = new WeakMap();
function On(e, t, n = !1) {
  var r = new qs(e), i = n ? Tt : 0;
  function s(o, a) {
    r.ensure(o, a);
  }
  Qn(() => {
    var o = !1;
    t((a, f = 0) => {
      o = !0, s(f, a);
    }), o || s(-1, null);
  }, i);
}
function Vs(e, t, n) {
  for (var r = [], i = t.length, s, o = t.length, a = 0; a < i; a++) {
    let p = t[a];
    it(
      p,
      () => {
        if (s) {
          if (s.pending.delete(p), s.done.add(p), s.pending.size === 0) {
            var u = (
              /** @type {Set<EachOutroGroup>} */
              e.outrogroups
            );
            qn(e, bn(s.done)), u.delete(s), u.size === 0 && (e.outrogroups = null);
          }
        } else
          o -= 1;
      },
      !1
    );
  }
  if (o === 0) {
    var f = r.length === 0 && n !== null;
    if (f) {
      var c = (
        /** @type {Element} */
        n
      ), d = (
        /** @type {Element} */
        c.parentNode
      );
      ys(d), d.append(c), e.items.clear();
    }
    qn(e, t, !f);
  } else
    s = {
      pending: new Set(t),
      done: /* @__PURE__ */ new Set()
    }, (e.outrogroups ?? (e.outrogroups = /* @__PURE__ */ new Set())).add(s);
}
function qn(e, t, n = !0) {
  var r;
  if (e.pending.size > 0) {
    r = /* @__PURE__ */ new Set();
    for (const o of e.pending.values())
      for (const a of o)
        r.add(
          /** @type {EachItem} */
          e.items.get(a).e
        );
  }
  for (var i = 0; i < t.length; i++) {
    var s = t[i];
    if (r != null && r.has(s)) {
      s.f |= xe;
      const o = document.createDocumentFragment();
      Jn(s, o);
    } else
      Z(t[i], n);
  }
}
var hr;
function vr(e, t, n, r, i, s = null) {
  var o = e, a = /* @__PURE__ */ new Map(), f = (t & xr) !== 0;
  if (f) {
    var c = (
      /** @type {Element} */
      e
    );
    o = c.appendChild(Ve());
  }
  var d = null, p = /* @__PURE__ */ us(() => {
    var M = n();
    return (
      /** @type {V[]} */
      Er(M) ? M : M == null ? [] : bn(M)
    );
  }), u, h = /* @__PURE__ */ new Map(), _ = !0;
  function g(M) {
    L.effect.f & ue || (L.pending.delete(M), L.fallback = d, Us(L, u, o, t, r), d !== null && (u.length === 0 ? d.f & xe ? (d.f ^= xe, Pt(d, null, o)) : wn(d) : it(d, () => {
      d = null;
    })));
  }
  function v(M) {
    L.pending.delete(M);
  }
  var E = Qn(() => {
    u = /** @type {V[]} */
    w(p);
    for (var M = u.length, z = /* @__PURE__ */ new Set(), re = (
      /** @type {Batch} */
      y
    ), Me = $r(), H = 0; H < M; H += 1) {
      var ye = u[H], De = r(ye, H), Y = _ ? null : a.get(De);
      Y ? (Y.v && Ct(Y.v, ye), Y.i && Ct(Y.i, H), Me && re.unskip_effect(Y.e)) : (Y = Ys(
        a,
        _ ? o : hr ?? (hr = Ve()),
        ye,
        De,
        H,
        i,
        t,
        n
      ), _ || (Y.e.f |= xe), a.set(De, Y)), z.add(De);
    }
    if (M === 0 && s && !d && (_ ? d = oe(() => s(o)) : (d = oe(() => s(hr ?? (hr = Ve()))), d.f |= xe)), M > z.size && Ri(), !_)
      if (h.set(re, z), Me) {
        for (const [at, $e] of a)
          z.has(at) || re.skip_effect($e.e);
        re.oncommit(g), re.ondiscard(v);
      } else
        g(re);
    w(p);
  }), L = { effect: E, items: a, pending: h, outrogroups: null, fallback: d };
  _ = !1;
}
function Ot(e) {
  for (; e !== null && !(e.f & me); )
    e = e.next;
  return e;
}
function Us(e, t, n, r, i) {
  var Y, at, $e, Qt, Zt, Jt, Xt, en, tn;
  var s = (r & Ui) !== 0, o = t.length, a = e.items, f = Ot(e.effect.first), c, d = null, p, u = [], h = [], _, g, v, E;
  if (s)
    for (E = 0; E < o; E += 1)
      _ = t[E], g = i(_, E), v = /** @type {EachItem} */
      a.get(g).e, v.f & xe || ((at = (Y = v.nodes) == null ? void 0 : Y.a) == null || at.measure(), (p ?? (p = /* @__PURE__ */ new Set())).add(v));
  for (E = 0; E < o; E += 1) {
    if (_ = t[E], g = i(_, E), v = /** @type {EachItem} */
    a.get(g).e, e.outrogroups !== null)
      for (const de of e.outrogroups)
        de.pending.delete(v), de.done.delete(v);
    if (v.f & U && (wn(v), s && ((Qt = ($e = v.nodes) == null ? void 0 : $e.a) == null || Qt.unfix(), (p ?? (p = /* @__PURE__ */ new Set())).delete(v))), v.f & xe)
      if (v.f ^= xe, v === f)
        Pt(v, null, n);
      else {
        var L = d ? d.next : f;
        v === e.effect.last && (e.effect.last = v.prev), v.prev && (v.prev.next = v.next), v.next && (v.next.prev = v.prev), je(e, d, v), je(e, v, L), Pt(v, L, n), d = v, u = [], h = [], f = Ot(d.next);
        continue;
      }
    if (v !== f) {
      if (c !== void 0 && c.has(v)) {
        if (u.length < h.length) {
          var M = h[0], z;
          d = M.prev;
          var re = u[0], Me = u[u.length - 1];
          for (z = 0; z < u.length; z += 1)
            Pt(u[z], M, n);
          for (z = 0; z < h.length; z += 1)
            c.delete(h[z]);
          je(e, re.prev, Me.next), je(e, d, re), je(e, Me, M), f = M, d = Me, E -= 1, u = [], h = [];
        } else
          c.delete(v), Pt(v, f, n), je(e, v.prev, v.next), je(e, v, d === null ? e.effect.first : d.next), je(e, d, v), d = v;
        continue;
      }
      for (u = [], h = []; f !== null && f !== v; )
        (c ?? (c = /* @__PURE__ */ new Set())).add(f), h.push(f), f = Ot(f.next);
      if (f === null)
        continue;
    }
    v.f & xe || u.push(v), d = v, f = Ot(v.next);
  }
  if (e.outrogroups !== null) {
    for (const de of e.outrogroups)
      de.pending.size === 0 && (qn(e, bn(de.done)), (Zt = e.outrogroups) == null || Zt.delete(de));
    e.outrogroups.size === 0 && (e.outrogroups = null);
  }
  if (f !== null || c !== void 0) {
    var H = [];
    if (c !== void 0)
      for (v of c)
        v.f & U || H.push(v);
    for (; f !== null; )
      !(f.f & U) && f !== e.fallback && H.push(f), f = Ot(f.next);
    var ye = H.length;
    if (ye > 0) {
      var De = r & xr && o === 0 ? n : null;
      if (s) {
        for (E = 0; E < ye; E += 1)
          (Xt = (Jt = H[E].nodes) == null ? void 0 : Jt.a) == null || Xt.measure();
        for (E = 0; E < ye; E += 1)
          (tn = (en = H[E].nodes) == null ? void 0 : en.a) == null || tn.fix();
      }
      Vs(e, H, De);
    }
  }
  s && nt(() => {
    var de, b;
    if (p !== void 0)
      for (v of p)
        (b = (de = v.nodes) == null ? void 0 : de.a) == null || b.apply();
  });
}
function Ys(e, t, n, r, i, s, o, a) {
  var f = o & qi ? o & Yi ? ot(n) : /* @__PURE__ */ ps(n, !1, !1) : null, c = o & Vi ? ot(i) : null;
  return {
    v: f,
    i: c,
    e: oe(() => (s(t, f ?? n, c ?? i, a), () => {
      e.delete(r);
    }))
  };
}
function Pt(e, t, n) {
  if (e.nodes)
    for (var r = e.nodes.start, i = e.nodes.end, s = t && !(t.f & xe) ? (
      /** @type {EffectNodes} */
      t.nodes.start
    ) : n; r !== null; ) {
      var o = (
        /** @type {TemplateNode} */
        /* @__PURE__ */ Kt(r)
      );
      if (s.before(r), r === i)
        return;
      r = o;
    }
}
function je(e, t, n) {
  t === null ? e.effect.first = n : t.next = n, n === null ? e.effect.last = t : n.prev = t;
}
const Gs = Symbol("is custom element"), $s = Symbol("is html");
function _r(e, t, n, r) {
  var i = Ks(e);
  i[t] !== (i[t] = n) && (t === "loading" && (e[Mi] = n), n == null ? e.removeAttribute(t) : typeof n != "string" && Ws(e).includes(t) ? e[t] = n : e.setAttribute(t, n));
}
function Ks(e) {
  return (
    /** @type {Record<string | symbol, unknown>} **/
    /** @type {any} */
    e[fn] ?? (e[fn] = {
      [Gs]: e.nodeName.includes("-"),
      [$s]: e.namespaceURI === Ki
    })
  );
}
var pr = /* @__PURE__ */ new Map();
function Ws(e) {
  var t = e.getAttribute("is") || e.nodeName, n = pr.get(t);
  if (n) return n;
  pr.set(t, n = []);
  for (var r, i = e, s = Element.prototype; s !== i; ) {
    r = bi(i);
    for (var o in r)
      r[o].set && // better safe than sorry, we don't want spread attributes to mess with HTML content
      o !== "innerHTML" && o !== "textContent" && o !== "innerText" && n.push(o);
    i = br(i);
  }
  return n;
}
function gr(e, t, n, r) {
  var i = (
    /** @type {V} */
    r
  ), s = !0, o = () => (s && (s = !1, i = /** @type {V} */
  r), i), a;
  a = /** @type {V} */
  e[t], a === void 0 && r !== void 0 && (a = o());
  var f;
  return f = () => {
    var c = (
      /** @type {V} */
      e[t]
    );
    return c === void 0 ? o() : (s = !0, c);
  }, f;
}
const Qs = "5";
var yr;
typeof window < "u" && ((yr = window.__svelte ?? (window.__svelte = {})).v ?? (yr.v = /* @__PURE__ */ new Set())).add(Qs);
var Zs = /* @__PURE__ */ Fe('Loading<span class="loading-dots">...</span>', 1), Js = /* @__PURE__ */ Fe('<div id="loading-message" class="loading-message"><!></div>'), Xs = /* @__PURE__ */ Fe('<div id="no-results" class="no-sessions">No sessions found.</div>'), el = /* @__PURE__ */ Fe('<button class="today-action-btn btn-goto-today">On Now</button>'), tl = /* @__PURE__ */ Fe("<option> </option>"), nl = /* @__PURE__ */ Fe('<select class="today-action-btn btn-goto-today"><option>On Now ...</option><!></select>'), rl = /* @__PURE__ */ Fe('<tr><td><a> </a></td><td> </td><td class="action-cell"><!></td></tr>'), il = /* @__PURE__ */ Fe('<table class="sessions-grid" id="sessions-table"><thead><tr><th>Name</th><th>Location</th><th></th></tr></thead><tbody id="sessions-tbody"></tbody></table>'), sl = /* @__PURE__ */ Fe(`<h1>Sessions</h1> <div class="sessions-controls"><div class="search-and-toggle"><input type="text" id="search-bar" class="search-bar" placeholder="Search by name or location..."/> <button class="filter-toggle-button" id="filter-toggle-button"> </button></div> <div class="session-count" id="session-count">Showing <span id="count-number"> </span> <span id="count-filter-type"> </span>.</div></div> <!> <p style="font-size: 0.85rem; color: var(--secondary-text);">Don't see your session? <a href="/add-session">Add it!</a></p> <p><a href="/">← Back to home</a></p>`, 1);
function ll(e, t) {
  Cr(t, !0);
  let n = gr(t, "pageData", 3, null), r = gr(t, "isLoggedIn", 3, !1);
  const i = r() ? ["my", "active", "all", "inactive"] : ["active", "all", "inactive"], s = {
    my: "My Sessions",
    active: "All Active",
    all: "All",
    inactive: "Inactive"
  }, o = {
    my: "sessions in your list",
    active: "active sessions",
    all: "sessions",
    inactive: "inactive sessions"
  };
  let a = /* @__PURE__ */ ne(gt([])), f = /* @__PURE__ */ ne(!1), c = /* @__PURE__ */ ne(!1), d = /* @__PURE__ */ ne(0), p = /* @__PURE__ */ ne("");
  const u = /* @__PURE__ */ sr(() => i[w(d)]), h = (b) => b.replace(/[‘’]/g, "'").replace(/[“”]/g, '"');
  function _(b) {
    W(a, b || [], !0), r() && i[w(d)] === "my" && !w(a).some((A) => A.user_is_member) && W(d, i.indexOf("active"), !0), W(f, !0);
  }
  n() && n().success && _(n().sessions), xs(() => {
    fi(() => {
      fetch("/api/sessions/with-today-status", { credentials: "same-origin" }).then((b) => b.json()).then((b) => {
        b.success ? _(b.sessions) : w(f) || W(c, !0);
      }).catch(() => {
        w(f) || W(c, !0);
      });
    });
  });
  const g = /* @__PURE__ */ sr(() => {
    const b = /* @__PURE__ */ new Date();
    return b.setHours(0, 0, 0, 0), w(a).filter((A) => {
      let D = !1;
      if (w(u) === "my" ? D = A.user_is_member : w(u) === "active" ? D = !A.termination_date || new Date(A.termination_date) > b : w(u) === "all" ? D = !0 : w(u) === "inactive" && (D = !!A.termination_date && new Date(A.termination_date) <= b), !D) return !1;
      if (w(p)) {
        const he = [A.city, A.state, A.country].filter(Boolean).join(", ").toLowerCase();
        return A.name.toLowerCase().includes(w(p)) || he.includes(w(p));
      }
      return !0;
    });
  });
  function v(b) {
    if (!b) return "";
    const A = b.split(":");
    let D = parseInt(A[0], 10);
    const he = A[1], F = D >= 12 ? "pm" : "am";
    return D = D > 12 ? D - 12 : D === 0 ? 12 : D, `${D}:${he}${F}`;
  }
  function E(b, A) {
    if (!b) return "";
    const D = v(b);
    return A ? `${D}-${v(A)}` : D + " - ?";
  }
  const L = (b) => [b.city, b.state, b.country].filter(Boolean).join(", ") || "Unknown";
  function M(b, A) {
    const D = E(A.start_time, A.end_time), he = A.location_override || b.location_name || "";
    return [D, he].filter(Boolean).join(" @ ");
  }
  const z = (b) => window.location.href = b;
  var re = sl(), Me = Ee(ms(re), 2), H = q(Me), ye = q(H), De = Ee(ye, 2), Y = q(De), at = Ee(H, 2), $e = Ee(q(at)), Qt = q($e), Zt = Ee($e, 2), Jt = q(Zt), Xt = Ee(Me, 2);
  {
    var en = (b) => {
      var A = Js(), D = q(A);
      {
        var he = (Ne) => {
          var ut = js("Error loading sessions");
          be(Ne, ut);
        }, F = (Ne) => {
          var ut = Zs();
          be(Ne, ut);
        };
        On(D, (Ne) => {
          w(c) ? Ne(he) : Ne(F, -1);
        });
      }
      be(b, A);
    }, tn = (b) => {
      var A = Xs();
      be(b, A);
    }, de = (b) => {
      var A = il(), D = Ee(q(A));
      vr(D, 21, () => w(g), (he) => he.session_id, (he, F) => {
        var Ne = rl(), ut = q(Ne), Xn = q(ut), ai = q(Xn), er = Ee(ut), ui = q(er), ci = Ee(er), di = q(ci);
        {
          var hi = (Pe) => {
            var Ke = el();
            sn("click", Ke, () => z(`/sessions/${w(F).path}/${w(F).active_instances[0].date}`)), be(Pe, Ke);
          }, vi = (Pe) => {
            var Ke = nl(), xn = q(Ke);
            xn.value = xn.__value = "";
            var _i = Ee(xn);
            vr(_i, 17, () => w(F).active_instances, (ct) => ct.session_instance_id, (ct, Tn) => {
              var nn = tl(), pi = q(nn), tr = {};
              rn(
                (gi) => {
                  ht(pi, gi), tr !== (tr = w(Tn).date) && (nn.value = (nn.__value = w(Tn).date) ?? "");
                },
                [() => M(w(F), w(Tn))]
              ), be(ct, nn);
            }), rn(() => _r(Ke, "id", `dropdown-${w(F).session_id ?? ""}`)), sn("change", Ke, (ct) => ct.target.value && z(`/sessions/${w(F).path}/${ct.target.value}`)), be(Pe, Ke);
          };
          On(di, (Pe) => {
            w(F).active_instances && w(F).active_instances.length === 1 ? Pe(hi) : w(F).active_instances && w(F).active_instances.length > 1 && Pe(vi, 1);
          });
        }
        rn(
          (Pe) => {
            _r(Xn, "href", `/sessions/${w(F).path ?? ""}`), ht(ai, w(F).name), ht(ui, Pe);
          },
          [() => L(w(F))]
        ), be(he, Ne);
      }), be(b, A);
    };
    On(Xt, (b) => {
      w(f) ? w(g).length === 0 ? b(tn, 1) : b(de, -1) : b(en);
    });
  }
  rn(() => {
    ht(Y, s[w(u)]), ht(Qt, w(g).length), ht(Jt, o[w(u)] || "sessions");
  }), sn("input", ye, (b) => W(p, h(b.target.value.toLowerCase()), !0)), sn("click", De, () => W(d, (w(d) + 1) % i.length)), be(e, re), Mr();
}
Ls(["input", "click", "change"]);
const wr = document.getElementById("sessions-root");
wr && Bs(ll, {
  target: wr,
  props: {
    pageData: window.__PAGE_DATA__ ?? null,
    isLoggedIn: !!window.__IS_LOGGED_IN__
  }
});
