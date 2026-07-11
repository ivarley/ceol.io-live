var el = Object.defineProperty;
var bs = (e) => {
  throw TypeError(e);
};
var tl = (e, t, n) => t in e ? el(e, t, { enumerable: !0, configurable: !0, writable: !0, value: n }) : e[t] = n;
var Ct = (e, t, n) => tl(e, typeof t != "symbol" ? t + "" : t, n), Ii = (e, t, n) => t.has(e) || bs("Cannot " + n);
var d = (e, t, n) => (Ii(e, t, "read from private field"), n ? n.call(e) : t.get(e)), ae = (e, t, n) => t.has(e) ? bs("Cannot add the same private member more than once") : t instanceof WeakSet ? t.add(e) : t.set(e, n), ie = (e, t, n, i) => (Ii(e, t, "write to private field"), i ? i.call(e, n) : t.set(e, n), n), xe = (e, t, n) => (Ii(e, t, "access private method"), n);
var us = Array.isArray, nl = Array.prototype.indexOf, oi = Array.prototype.includes, yi = Array.from, rl = Object.defineProperty, cr = Object.getOwnPropertyDescriptor, $s = Object.getOwnPropertyDescriptors, il = Object.prototype, sl = Array.prototype, cs = Object.getPrototypeOf, ws = Object.isExtensible;
function al(e) {
  return typeof e == "function";
}
const lr = () => {
};
function ll(e) {
  for (var t = 0; t < e.length; t++)
    e[t]();
}
function ea() {
  var e, t, n = new Promise((i, a) => {
    e = i, t = a;
  });
  return { promise: n, resolve: e, reject: t };
}
function ks(e, t) {
  if (Array.isArray(e))
    return e;
  if (!(Symbol.iterator in e))
    return Array.from(e);
  const n = [];
  for (const i of e)
    if (n.push(i), n.length === t) break;
  return n;
}
const ht = 2, yr = 4, bi = 8, ta = 1 << 24, Wt = 16, rn = 32, Nn = 64, Hi = 128, Xt = 512, at = 1024, vt = 2048, vn = 4096, kt = 8192, Rt = 16384, er = 32768, Yi = 1 << 25, Qn = 65536, ui = 1 << 17, ol = 1 << 18, Sr = 1 << 19, ul = 1 << 20, fn = 1 << 25, Jn = 65536, ci = 1 << 21, fr = 1 << 22, Rn = 1 << 23, kn = Symbol("$state"), cl = Symbol("legacy props"), fl = Symbol(""), ni = Symbol("attributes"), Vi = Symbol("class"), Wi = Symbol("style"), Mr = Symbol("text"), ri = Symbol("form reset"), wi = new class extends Error {
  constructor() {
    super(...arguments);
    Ct(this, "name", "StaleReactionError");
    Ct(this, "message", "The reaction that called `getAbortSignal()` was re-run or destroyed");
  }
}();
function na(e) {
  throw new Error("https://svelte.dev/e/lifecycle_outside_component");
}
function dl() {
  throw new Error("https://svelte.dev/e/async_derived_orphan");
}
function vl(e, t, n) {
  throw new Error("https://svelte.dev/e/each_key_duplicate");
}
function _l(e) {
  throw new Error("https://svelte.dev/e/effect_in_teardown");
}
function hl() {
  throw new Error("https://svelte.dev/e/effect_in_unowned_derived");
}
function pl(e) {
  throw new Error("https://svelte.dev/e/effect_orphan");
}
function gl() {
  throw new Error("https://svelte.dev/e/effect_update_depth_exceeded");
}
function ml(e) {
  throw new Error("https://svelte.dev/e/props_invalid_value");
}
function yl() {
  throw new Error("https://svelte.dev/e/state_descriptors_fixed");
}
function bl() {
  throw new Error("https://svelte.dev/e/state_prototype_fixed");
}
function wl() {
  throw new Error("https://svelte.dev/e/state_unsafe_mutation");
}
function kl() {
  throw new Error("https://svelte.dev/e/svelte_boundary_reset_onerror");
}
const xl = 1, Sl = 2, ra = 4, Tl = 8, El = 16, Al = 1, Il = 4, Ml = 8, Ll = 16, Cl = 4, Pl = 1, Dl = 2, rt = Symbol("uninitialized"), Ol = "http://www.w3.org/1999/xhtml";
function Rl() {
  console.warn("https://svelte.dev/e/derived_inert");
}
function Nl() {
  console.warn("https://svelte.dev/e/select_multiple_invalid_value");
}
function jl() {
  console.warn("https://svelte.dev/e/svelte_boundary_reset_noop");
}
function ia(e) {
  return e === this.v;
}
function sa(e, t) {
  return e != e ? t == t : e !== t || e !== null && typeof e == "object" || typeof e == "function";
}
function aa(e) {
  return !sa(e, this.v);
}
let _t = null;
function br(e) {
  _t = e;
}
function tr(e, t = !1, n) {
  _t = {
    p: _t,
    i: !1,
    c: null,
    e: null,
    s: e,
    x: null,
    r: (
      /** @type {Effect} */
      ve
    ),
    l: null
  };
}
function nr(e) {
  var t = (
    /** @type {ComponentContext} */
    _t
  ), n = t.e;
  if (n !== null) {
    t.e = null;
    for (var i of n)
      Aa(i);
  }
  return e !== void 0 && (t.x = e), t.i = !0, _t = t.p, e ?? /** @type {T} */
  {};
}
function la() {
  return !0;
}
let Un = [];
function oa() {
  var e = Un;
  Un = [], ll(e);
}
function xn(e) {
  if (Un.length === 0 && !Rr) {
    var t = Un;
    queueMicrotask(() => {
      t === Un && oa();
    });
  }
  Un.push(e);
}
function Fl() {
  for (; Un.length > 0; )
    oa();
}
function ua(e) {
  var t = ve;
  if (t === null)
    return de.f |= Rn, e;
  if (!(t.f & er) && !(t.f & yr))
    throw e;
  On(e, t);
}
function On(e, t) {
  if (!(t !== null && t.f & Rt)) {
    for (; t !== null; ) {
      if (t.f & Hi) {
        if (!(t.f & er))
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
const Ul = -7169;
function Xe(e, t) {
  e.f = e.f & Ul | t;
}
function fs(e) {
  e.f & Xt || e.deps === null ? Xe(e, at) : Xe(e, vn);
}
function ca(e) {
  if (e !== null)
    for (const t of e)
      !(t.f & ht) || !(t.f & Jn) || (t.f ^= Jn, ca(
        /** @type {Derived} */
        t.deps
      ));
}
function fa(e, t, n) {
  e.f & vt ? t.add(e) : e.f & vn && n.add(e), ca(e.deps), Xe(e, at);
}
let ei = !1;
function ql(e) {
  var t = ei;
  try {
    return ei = !1, [e(), ei];
  } finally {
    ei = t;
  }
}
function Bl(e) {
  let t = 0, n = $n(0), i;
  return () => {
    hs() && (r(n), xi(() => (t === 0 && (i = st(() => e(() => Nr(n)))), t += 1, () => {
      xn(() => {
        t -= 1, t === 0 && (i == null || i(), i = void 0, Nr(n));
      });
    })));
  };
}
var zl = Qn | Sr;
function Hl(e, t, n, i) {
  new Yl(e, t, n, i);
}
var Bt, os, zt, zn, St, Ht, wt, Dt, gn, Hn, Pn, dr, qr, Br, mn, pi, Ve, Vl, Wl, Xl, Xi, ii, si, Gi, Ki;
class Yl {
  /**
   * @param {TemplateNode} node
   * @param {BoundaryProps} props
   * @param {((anchor: Node) => void)} children
   * @param {((error: unknown) => unknown) | undefined} [transform_error]
   */
  constructor(t, n, i, a) {
    ae(this, Ve);
    /** @type {Boundary | null} */
    Ct(this, "parent");
    Ct(this, "is_pending", !1);
    /**
     * API-level transformError transform function. Transforms errors before they reach the `failed` snippet.
     * Inherited from parent boundary, or defaults to identity.
     * @type {(error: unknown) => unknown}
     */
    Ct(this, "transform_error");
    /** @type {TemplateNode} */
    ae(this, Bt);
    /** @type {TemplateNode | null} */
    ae(this, os, null);
    /** @type {BoundaryProps} */
    ae(this, zt);
    /** @type {((anchor: Node) => void)} */
    ae(this, zn);
    /** @type {Effect} */
    ae(this, St);
    /** @type {Effect | null} */
    ae(this, Ht, null);
    /** @type {Effect | null} */
    ae(this, wt, null);
    /** @type {Effect | null} */
    ae(this, Dt, null);
    /** @type {DocumentFragment | null} */
    ae(this, gn, null);
    ae(this, Hn, 0);
    ae(this, Pn, 0);
    ae(this, dr, !1);
    /** @type {Set<Effect>} */
    ae(this, qr, /* @__PURE__ */ new Set());
    /** @type {Set<Effect>} */
    ae(this, Br, /* @__PURE__ */ new Set());
    /**
     * A source containing the number of pending async deriveds/expressions.
     * Only created if `$effect.pending()` is used inside the boundary,
     * otherwise updating the source results in needless `Batch.ensure()`
     * calls followed by no-op flushes
     * @type {Source<number> | null}
     */
    ae(this, mn, null);
    ae(this, pi, Bl(() => (ie(this, mn, $n(d(this, Hn))), () => {
      ie(this, mn, null);
    })));
    var s;
    ie(this, Bt, t), ie(this, zt, n), ie(this, zn, (l) => {
      var o = (
        /** @type {Effect} */
        ve
      );
      o.b = this, o.f |= Hi, i(l);
    }), this.parent = /** @type {Effect} */
    ve.b, this.transform_error = a ?? ((s = this.parent) == null ? void 0 : s.transform_error) ?? ((l) => l), ie(this, St, Si(() => {
      xe(this, Ve, Xi).call(this);
    }, zl));
  }
  /**
   * Defer an effect inside a pending boundary until the boundary resolves
   * @param {Effect} effect
   */
  defer_effect(t) {
    fa(t, d(this, qr), d(this, Br));
  }
  /**
   * Returns `false` if the effect exists inside a boundary whose pending snippet is shown
   * @returns {boolean}
   */
  is_rendered() {
    return !this.is_pending && (!this.parent || this.parent.is_rendered());
  }
  has_pending_snippet() {
    return !!d(this, zt).pending;
  }
  /**
   * Update the source that powers `$effect.pending()` inside this boundary,
   * and controls when the current `pending` snippet (if any) is removed.
   * Do not call from inside the class
   * @param {1 | -1} d
   * @param {Batch} batch
   */
  update_pending_count(t, n) {
    xe(this, Ve, Gi).call(this, t, n), ie(this, Hn, d(this, Hn) + t), !(!d(this, mn) || d(this, dr)) && (ie(this, dr, !0), xn(() => {
      ie(this, dr, !1), d(this, mn) && wr(d(this, mn), d(this, Hn));
    }));
  }
  get_effect_pending() {
    return d(this, pi).call(this), r(
      /** @type {Source<number>} */
      d(this, mn)
    );
  }
  /** @param {unknown} error */
  error(t) {
    if (!d(this, zt).onerror && !d(this, zt).failed)
      throw t;
    $ != null && $.is_fork ? (d(this, Ht) && $.skip_effect(d(this, Ht)), d(this, wt) && $.skip_effect(d(this, wt)), d(this, Dt) && $.skip_effect(d(this, Dt)), $.oncommit(() => {
      xe(this, Ve, Ki).call(this, t);
    })) : xe(this, Ve, Ki).call(this, t);
  }
}
Bt = new WeakMap(), os = new WeakMap(), zt = new WeakMap(), zn = new WeakMap(), St = new WeakMap(), Ht = new WeakMap(), wt = new WeakMap(), Dt = new WeakMap(), gn = new WeakMap(), Hn = new WeakMap(), Pn = new WeakMap(), dr = new WeakMap(), qr = new WeakMap(), Br = new WeakMap(), mn = new WeakMap(), pi = new WeakMap(), Ve = new WeakSet(), Vl = function() {
  try {
    ie(this, Ht, Yt(() => d(this, zn).call(this, d(this, Bt))));
  } catch (t) {
    this.error(t);
  }
}, /**
 * @param {unknown} error The deserialized error from the server's hydration comment
 */
Wl = function(t) {
  const n = d(this, zt).failed;
  n && ie(this, Dt, Yt(() => {
    n(
      d(this, Bt),
      () => t,
      () => () => {
      }
    );
  }));
}, Xl = function() {
  const t = d(this, zt).pending;
  t && (this.is_pending = !0, ie(this, wt, Yt(() => t(d(this, Bt)))), xn(() => {
    var n = ie(this, gn, document.createDocumentFragment()), i = Sn();
    n.append(i), ie(this, Ht, xe(this, Ve, si).call(this, () => Yt(() => d(this, zn).call(this, i)))), d(this, Pn) === 0 && (d(this, Bt).before(n), ie(this, gn, null), Gn(
      /** @type {Effect} */
      d(this, wt),
      () => {
        ie(this, wt, null);
      }
    ), xe(this, Ve, ii).call(
      this,
      /** @type {Batch} */
      $
    ));
  }));
}, Xi = function() {
  try {
    if (this.is_pending = this.has_pending_snippet(), ie(this, Pn, 0), ie(this, Hn, 0), ie(this, Ht, Yt(() => {
      d(this, zn).call(this, d(this, Bt));
    })), d(this, Pn) > 0) {
      var t = ie(this, gn, document.createDocumentFragment());
      ms(d(this, Ht), t);
      const n = (
        /** @type {(anchor: Node) => void} */
        d(this, zt).pending
      );
      ie(this, wt, Yt(() => n(d(this, Bt))));
    } else
      xe(this, Ve, ii).call(
        this,
        /** @type {Batch} */
        $
      );
  } catch (n) {
    this.error(n);
  }
}, /**
 * @param {Batch} batch
 */
ii = function(t) {
  this.is_pending = !1, t.transfer_effects(d(this, qr), d(this, Br));
}, /**
 * @template T
 * @param {() => T} fn
 */
si = function(t) {
  var n = ve, i = de, a = _t;
  _n(d(this, St)), Gt(d(this, St)), br(d(this, St).ctx);
  try {
    return Zn.ensure(), t();
  } catch (s) {
    return ua(s), null;
  } finally {
    _n(n), Gt(i), br(a);
  }
}, /**
 * Updates the pending count associated with the currently visible pending snippet,
 * if any, such that we can replace the snippet with content once work is done
 * @param {1 | -1} d
 * @param {Batch} batch
 */
Gi = function(t, n) {
  var i;
  if (!this.has_pending_snippet()) {
    this.parent && xe(i = this.parent, Ve, Gi).call(i, t, n);
    return;
  }
  ie(this, Pn, d(this, Pn) + t), d(this, Pn) === 0 && (xe(this, Ve, ii).call(this, n), d(this, wt) && Gn(d(this, wt), () => {
    ie(this, wt, null);
  }), d(this, gn) && (d(this, Bt).before(d(this, gn)), ie(this, gn, null)));
}, /**
 * @param {unknown} error
 */
Ki = function(t) {
  d(this, Ht) && (It(d(this, Ht)), ie(this, Ht, null)), d(this, wt) && (It(d(this, wt)), ie(this, wt, null)), d(this, Dt) && (It(d(this, Dt)), ie(this, Dt, null));
  var n = d(this, zt).onerror;
  let i = d(this, zt).failed;
  var a = !1, s = !1;
  const l = () => {
    if (a) {
      jl();
      return;
    }
    a = !0, s && kl(), d(this, Dt) !== null && Gn(d(this, Dt), () => {
      ie(this, Dt, null);
    }), xe(this, Ve, si).call(this, () => {
      xe(this, Ve, Xi).call(this);
    });
  }, o = (u) => {
    try {
      s = !0, n == null || n(u, l), s = !1;
    } catch (f) {
      On(f, d(this, St) && d(this, St).parent);
    }
    i && ie(this, Dt, xe(this, Ve, si).call(this, () => {
      try {
        return Yt(() => {
          var f = (
            /** @type {Effect} */
            ve
          );
          f.b = this, f.f |= Hi, i(
            d(this, Bt),
            () => u,
            () => l
          );
        });
      } catch (f) {
        return On(
          f,
          /** @type {Effect} */
          d(this, St).parent
        ), null;
      }
    }));
  };
  xn(() => {
    var u;
    try {
      u = this.transform_error(t);
    } catch (f) {
      On(f, d(this, St) && d(this, St).parent);
      return;
    }
    u !== null && typeof u == "object" && typeof /** @type {any} */
    u.then == "function" ? u.then(
      o,
      /** @param {unknown} e */
      (f) => On(f, d(this, St) && d(this, St).parent)
    ) : o(u);
  });
};
function Gl(e, t, n, i) {
  const a = jr;
  var s = e.filter((y) => !y.settled), l = t.map(a);
  if (n.length === 0 && s.length === 0) {
    i(l);
    return;
  }
  var o = (
    /** @type {Effect} */
    ve
  ), u = Kl(), f = s.length === 1 ? s[0].promise : s.length > 1 ? Promise.all(s.map((y) => y.promise)) : null;
  function h(y) {
    if (!(o.f & Rt)) {
      u();
      try {
        i([...l, ...y]);
      } catch (p) {
        On(p, o);
      }
      fi();
    }
  }
  var w = da();
  if (n.length === 0) {
    f.then(() => h([])).finally(w);
    return;
  }
  function _() {
    Promise.all(n.map((y) => /* @__PURE__ */ Ql(y))).then(h).catch((y) => On(y, o)).finally(w);
  }
  f ? f.then(() => {
    u(), _(), fi();
  }) : _();
}
function Kl() {
  var e = (
    /** @type {Effect} */
    ve
  ), t = de, n = _t, i = (
    /** @type {Batch} */
    $
  );
  return function(s = !0) {
    _n(e), Gt(t), br(n), s && !(e.f & Rt) && (i == null || i.activate(), i == null || i.apply());
  };
}
function fi(e = !0) {
  _n(null), Gt(null), br(null), e && ($ == null || $.deactivate());
}
function da() {
  var e = (
    /** @type {Effect} */
    ve
  ), t = e.b, n = (
    /** @type {Batch} */
    $
  ), i = !!(t != null && t.is_rendered());
  return t == null || t.update_pending_count(1, n), n.increment(i, e), () => {
    t == null || t.update_pending_count(-1, n), n.decrement(i, e);
  };
}
// @__NO_SIDE_EFFECTS__
function jr(e) {
  var t = ht | vt;
  return ve !== null && (ve.f |= Sr), {
    ctx: _t,
    deps: null,
    effects: null,
    equals: ia,
    f: t,
    fn: e,
    reactions: null,
    rv: 0,
    v: (
      /** @type {V} */
      rt
    ),
    wv: 0,
    parent: ve,
    ac: null
  };
}
const Lr = Symbol("obsolete");
// @__NO_SIDE_EFFECTS__
function Ql(e, t, n) {
  let i = (
    /** @type {Effect | null} */
    ve
  );
  i === null && dl();
  var a = (
    /** @type {Promise<V>} */
    /** @type {unknown} */
    void 0
  ), s = $n(
    /** @type {V} */
    rt
  ), l = !de, o = /* @__PURE__ */ new Set();
  return ho(() => {
    var y, p;
    var u = (
      /** @type {Effect} */
      ve
    ), f = ea();
    a = f.promise;
    try {
      Promise.resolve(e()).then(f.resolve, (b) => {
        b !== wi && f.reject(b);
      }).finally(fi);
    } catch (b) {
      f.reject(b), fi();
    }
    var h = (
      /** @type {Batch} */
      $
    );
    if (l) {
      if (u.f & er)
        var w = da();
      if (
        // boundary can be null if the async derived is inside an $effect.root not connected to the component render tree
        (y = i.b) != null && y.is_rendered()
      )
        (p = h.async_deriveds.get(u)) == null || p.reject(Lr);
      else
        for (const b of o.values())
          b.reject(Lr);
      o.add(f), h.async_deriveds.set(u, f);
    }
    const _ = (b, m = void 0) => {
      w == null || w(), o.delete(f), m !== Lr && (h.activate(), m ? (s.f |= Rn, wr(s, m)) : (s.f & Rn && (s.f ^= Rn), wr(s, b)), h.deactivate());
    };
    f.promise.then(_, (b) => _(null, b || "unknown"));
  }), ps(() => {
    for (const u of o)
      u.reject(Lr);
  }), new Promise((u) => {
    function f(h) {
      function w() {
        h === a ? u(s) : f(a);
      }
      h.then(w, w);
    }
    f(a);
  });
}
// @__NO_SIDE_EFFECTS__
function Ae(e) {
  const t = /* @__PURE__ */ jr(e);
  return Pa(t), t;
}
// @__NO_SIDE_EFFECTS__
function va(e) {
  const t = /* @__PURE__ */ jr(e);
  return t.equals = aa, t;
}
function Jl(e) {
  var t = e.effects;
  if (t !== null) {
    e.effects = null;
    for (var n = 0; n < t.length; n += 1)
      It(
        /** @type {Effect} */
        t[n]
      );
  }
}
function ds(e) {
  var t, n = ve, i = e.parent;
  if (!Tn && i !== null && e.v !== rt && // if it was never evaluated before, it's guaranteed to fail downstream, so we try to execute instead
  i.f & (Rt | kt))
    return Rl(), e.v;
  _n(i);
  try {
    e.f &= ~Jn, Jl(e), t = Na(e);
  } finally {
    _n(n);
  }
  return t;
}
function _a(e) {
  var t = ds(e);
  if (!e.equals(t) && (e.wv = Oa(), (!($ != null && $.is_fork) || e.deps === null) && ($ !== null ? ($.capture(e, t, !0), Or == null || Or.capture(e, t, !0)) : e.v = t, e.deps === null))) {
    Xe(e, at);
    return;
  }
  Tn || (dt !== null ? (hs() || $ != null && $.is_fork) && dt.set(e, t) : fs(e));
}
function Zl(e) {
  var t, n;
  if (e.effects !== null)
    for (const i of e.effects)
      (i.teardown || i.ac) && ((t = i.teardown) == null || t.call(i), (n = i.ac) == null || n.abort(wi), i.fn !== null && (i.teardown = lr), i.ac = null, Fr(i, 0), gs(i));
}
function ha(e) {
  if (e.effects !== null)
    for (const t of e.effects)
      t.teardown && t.fn !== null && kr(t);
}
let Mi = null, sr = null, $ = null, Or = null, dt = null, Qi = null, Rr = !1, Li = !1, ur = null, ai = null;
var xs = 0;
let $l = 1;
var vr, Dn, Yn, _r, hr, pr, yn, gr, Tt, zr, bn, en, on, mr, Vn, Le, Ji, Cr, Zi, pa, ga, or, eo, Pr;
const gi = class gi {
  constructor() {
    ae(this, Le);
    Ct(this, "id", $l++);
    /** True as soon as `#process` was called */
    ae(this, vr, !1);
    Ct(this, "linked", !0);
    /** @type {Batch | null} */
    ae(this, Dn, null);
    /** @type {Batch | null} */
    ae(this, Yn, null);
    /** @type {Map<Effect, ReturnType<typeof deferred<any>>>} */
    Ct(this, "async_deriveds", /* @__PURE__ */ new Map());
    /**
     * The current values of any signals that are updated in this batch.
     * Tuple format: [value, is_derived] (note: is_derived is false for deriveds, too, if they were overridden via assignment)
     * They keys of this map are identical to `this.#previous`
     * @type {Map<Value, [any, boolean]>}
     */
    Ct(this, "current", /* @__PURE__ */ new Map());
    /**
     * The values of any signals (sources and deriveds) that are updated in this batch _before_ those updates took place.
     * They keys of this map are identical to `this.#current`
     * @type {Map<Value, any>}
     */
    Ct(this, "previous", /* @__PURE__ */ new Map());
    /**
     * When the batch is committed (and the DOM is updated), we need to remove old branches
     * and append new ones by calling the functions added inside (if/each/key/etc) blocks
     * @type {Set<(batch: Batch) => void>}
     */
    ae(this, _r, /* @__PURE__ */ new Set());
    /**
     * If a fork is discarded, we need to destroy any effects that are no longer needed
     * @type {Set<(batch: Batch) => void>}
     */
    ae(this, hr, /* @__PURE__ */ new Set());
    /**
     * The number of async effects that are currently in flight
     */
    ae(this, pr, 0);
    /**
     * Async effects that are currently in flight, _not_ inside a pending boundary
     * @type {Map<Effect, number>}
     */
    ae(this, yn, /* @__PURE__ */ new Map());
    /**
     * A deferred that resolves when the batch is committed, used with `settled()`
     * TODO replace with Promise.withResolvers once supported widely enough
     * @type {{ promise: Promise<void>, resolve: (value?: any) => void, reject: (reason: unknown) => void } | null}
     */
    ae(this, gr, null);
    /**
     * The root effects that need to be flushed
     * @type {Effect[]}
     */
    ae(this, Tt, []);
    /**
     * Effects created while this batch was active.
     * @type {Effect[]}
     */
    ae(this, zr, []);
    /**
     * Deferred effects (which run after async work has completed) that are DIRTY
     * @type {Set<Effect>}
     */
    ae(this, bn, /* @__PURE__ */ new Set());
    /**
     * Deferred effects that are MAYBE_DIRTY
     * @type {Set<Effect>}
     */
    ae(this, en, /* @__PURE__ */ new Set());
    /**
     * A map of branches that still exist, but will be destroyed when this batch
     * is committed — we skip over these during `process`.
     * The value contains child effects that were dirty/maybe_dirty before being reset,
     * so they can be rescheduled if the branch survives.
     * @type {Map<Effect, { d: Effect[], m: Effect[] }>}
     */
    ae(this, on, /* @__PURE__ */ new Map());
    /**
     * Inverse of #skipped_branches which we need to tell prior batches to unskip them when committing
     * @type {Set<Effect>}
     */
    ae(this, mr, /* @__PURE__ */ new Set());
    Ct(this, "is_fork", !1);
    ae(this, Vn, !1);
    sr === null ? Mi = sr = this : (ie(sr, Yn, this), ie(this, Dn, sr)), sr = this;
  }
  /**
   * Add an effect to the #skipped_branches map and reset its children
   * @param {Effect} effect
   */
  skip_effect(t) {
    d(this, on).has(t) || d(this, on).set(t, { d: [], m: [] }), d(this, mr).delete(t);
  }
  /**
   * Remove an effect from the #skipped_branches map and reschedule
   * any tracked dirty/maybe_dirty child effects
   * @param {Effect} effect
   * @param {(e: Effect) => void} callback
   */
  unskip_effect(t, n = (i) => this.schedule(i)) {
    var i = d(this, on).get(t);
    if (i) {
      d(this, on).delete(t);
      for (var a of i.d)
        Xe(a, vt), n(a);
      for (a of i.m)
        Xe(a, vn), n(a);
    }
    d(this, mr).add(t);
  }
  /**
   * Associate a change to a given source with the current
   * batch, noting its previous and current values
   * @param {Value} source
   * @param {any} value
   * @param {boolean} [is_derived]
   */
  capture(t, n, i = !1) {
    t.v !== rt && !this.previous.has(t) && this.previous.set(t, t.v), t.f & Rn || (this.current.set(t, [n, i]), dt == null || dt.set(t, n)), this.is_fork || (t.v = n);
  }
  activate() {
    $ = this;
  }
  deactivate() {
    $ = null, dt = null;
  }
  flush() {
    try {
      Li = !0, $ = this, xe(this, Le, Cr).call(this);
    } finally {
      xs = 0, Qi = null, ur = null, ai = null, Li = !1, $ = null, dt = null, Xn.clear();
    }
  }
  discard() {
    var t;
    for (const n of d(this, hr)) n(this);
    d(this, hr).clear();
    for (const n of this.async_deriveds.values())
      n.reject(Lr);
    xe(this, Le, Pr).call(this), (t = d(this, gr)) == null || t.resolve();
  }
  /**
   * @param {Effect} effect
   */
  register_created_effect(t) {
    d(this, zr).push(t);
  }
  /**
   * @param {boolean} blocking
   * @param {Effect} effect
   */
  increment(t, n) {
    if (ie(this, pr, d(this, pr) + 1), t) {
      let i = d(this, yn).get(n) ?? 0;
      d(this, yn).set(n, i + 1);
    }
  }
  /**
   * @param {boolean} blocking
   * @param {Effect} effect
   */
  decrement(t, n) {
    if (ie(this, pr, d(this, pr) - 1), t) {
      let i = d(this, yn).get(n) ?? 0;
      i === 1 ? d(this, yn).delete(n) : d(this, yn).set(n, i - 1);
    }
    d(this, Vn) || (ie(this, Vn, !0), xn(() => {
      ie(this, Vn, !1), this.linked && this.flush();
    }));
  }
  /**
   * @param {Set<Effect>} dirty_effects
   * @param {Set<Effect>} maybe_dirty_effects
   */
  transfer_effects(t, n) {
    for (const i of t)
      d(this, bn).add(i);
    for (const i of n)
      d(this, en).add(i);
    t.clear(), n.clear();
  }
  /** @param {(batch: Batch) => void} fn */
  oncommit(t) {
    d(this, _r).add(t);
  }
  /** @param {(batch: Batch) => void} fn */
  ondiscard(t) {
    d(this, hr).add(t);
  }
  settled() {
    return (d(this, gr) ?? ie(this, gr, ea())).promise;
  }
  static ensure() {
    if ($ === null) {
      const t = $ = new gi();
      !Li && !Rr && xn(() => {
        d(t, vr) || t.flush();
      });
    }
    return $;
  }
  apply() {
    {
      dt = null;
      return;
    }
  }
  /**
   *
   * @param {Effect} effect
   */
  schedule(t) {
    var a;
    if (Qi = t, (a = t.b) != null && a.is_pending && t.f & (yr | bi | ta) && !(t.f & er)) {
      t.b.defer_effect(t);
      return;
    }
    for (var n = t; n.parent !== null; ) {
      n = n.parent;
      var i = n.f;
      if (ur !== null && n === ve && (de === null || !(de.f & ht)))
        return;
      if (i & (Nn | rn)) {
        if (!(i & at))
          return;
        n.f ^= at;
      }
    }
    d(this, Tt).push(n);
  }
};
vr = new WeakMap(), Dn = new WeakMap(), Yn = new WeakMap(), _r = new WeakMap(), hr = new WeakMap(), pr = new WeakMap(), yn = new WeakMap(), gr = new WeakMap(), Tt = new WeakMap(), zr = new WeakMap(), bn = new WeakMap(), en = new WeakMap(), on = new WeakMap(), mr = new WeakMap(), Vn = new WeakMap(), Le = new WeakSet(), Ji = function() {
  if (this.is_fork) return !0;
  for (const i of d(this, yn).keys()) {
    for (var t = i, n = !1; t.parent !== null; ) {
      if (d(this, on).has(t)) {
        n = !0;
        break;
      }
      t = t.parent;
    }
    if (!n)
      return !0;
  }
  return !1;
}, Cr = function() {
  var u, f, h, w;
  ie(this, vr, !0), xs++ > 1e3 && (xe(this, Le, Pr).call(this), no());
  for (const _ of d(this, bn))
    d(this, en).delete(_), Xe(_, vt), this.schedule(_);
  for (const _ of d(this, en))
    Xe(_, vn), this.schedule(_);
  const t = d(this, Tt);
  ie(this, Tt, []), this.apply();
  var n = ur = [], i = [], a = ai = [];
  for (const _ of t)
    try {
      xe(this, Le, Zi).call(this, _, n, i);
    } catch (y) {
      throw ba(_), xe(this, Le, Ji).call(this) || this.discard(), y;
    }
  if ($ = null, a.length > 0) {
    var s = gi.ensure();
    for (const _ of a)
      s.schedule(_);
  }
  if (ur = null, ai = null, xe(this, Le, Ji).call(this)) {
    xe(this, Le, or).call(this, i), xe(this, Le, or).call(this, n);
    for (const [_, y] of d(this, on))
      ya(_, y);
    a.length > 0 && /** @type {unknown} */
    xe(u = $, Le, Cr).call(u);
    return;
  }
  const l = xe(this, Le, pa).call(this);
  if (l) {
    xe(this, Le, or).call(this, i), xe(this, Le, or).call(this, n), xe(f = l, Le, ga).call(f, this);
    return;
  }
  d(this, bn).clear(), d(this, en).clear();
  for (const _ of d(this, _r)) _(this);
  d(this, _r).clear(), Or = this, Ss(i), Ss(n), Or = null, (h = d(this, gr)) == null || h.resolve();
  var o = (
    /** @type {Batch | null} */
    /** @type {unknown} */
    $
  );
  if (d(this, pr) === 0 && (d(this, Tt).length === 0 || o !== null) && xe(this, Le, Pr).call(this), d(this, Tt).length > 0)
    if (o !== null) {
      const _ = o;
      d(_, Tt).push(...d(this, Tt).filter((y) => !d(_, Tt).includes(y)));
    } else
      o = this;
  o !== null && xe(w = o, Le, Cr).call(w);
}, /**
 * Traverse the effect tree, executing effects or stashing
 * them for later execution as appropriate
 * @param {Effect} root
 * @param {Effect[]} effects
 * @param {Effect[]} render_effects
 */
Zi = function(t, n, i) {
  t.f ^= at;
  for (var a = t.first; a !== null; ) {
    var s = a.f, l = (s & (rn | Nn)) !== 0, o = l && (s & at) !== 0, u = o || (s & kt) !== 0 || d(this, on).has(a);
    if (!u && a.fn !== null) {
      l ? a.f ^= at : s & yr ? n.push(a) : Wr(a) && (s & Wt && d(this, en).add(a), kr(a));
      var f = a.first;
      if (f !== null) {
        a = f;
        continue;
      }
    }
    for (; a !== null; ) {
      var h = a.next;
      if (h !== null) {
        a = h;
        break;
      }
      a = a.parent;
    }
  }
}, pa = function() {
  for (var t = d(this, Dn); t !== null; ) {
    if (!t.is_fork) {
      for (const [n, [, i]] of this.current)
        if (t.current.has(n) && !i)
          return t;
    }
    t = d(t, Dn);
  }
  return null;
}, /**
 * @param {Batch} batch
 */
ga = function(t) {
  var i;
  for (const [a, s] of t.current)
    !this.previous.has(a) && t.previous.has(a) && this.previous.set(a, t.previous.get(a)), this.current.set(a, s);
  for (const [a, s] of t.async_deriveds) {
    const l = this.async_deriveds.get(a);
    l && s.promise.then(l.resolve).catch(l.reject);
  }
  t.async_deriveds.clear(), this.transfer_effects(d(t, bn), d(t, en));
  const n = (a) => {
    var s = a.reactions;
    if (s !== null)
      for (const u of s) {
        var l = u.f;
        if (l & ht)
          n(
            /** @type {Derived} */
            u
          );
        else {
          var o = (
            /** @type {Effect} */
            u
          );
          l & (fr | Wt) && !this.async_deriveds.has(o) && (d(this, en).delete(o), Xe(o, vt), this.schedule(o));
        }
      }
  };
  for (const a of this.current.keys())
    n(a);
  this.oncommit(() => t.discard()), xe(i = t, Le, Pr).call(i), $ = this, xe(this, Le, Cr).call(this);
}, /**
 * @param {Effect[]} effects
 */
or = function(t) {
  for (var n = 0; n < t.length; n += 1)
    fa(t[n], d(this, bn), d(this, en));
}, eo = function() {
  var w;
  for (let _ = Mi; _ !== null; _ = d(_, Yn)) {
    var t = _.id < this.id, n = [];
    for (const [y, [p, b]] of this.current) {
      if (_.current.has(y)) {
        var i = (
          /** @type {[any, boolean]} */
          _.current.get(y)[0]
        );
        if (t && p !== i)
          _.current.set(y, [p, b]);
        else
          continue;
      }
      n.push(y);
    }
    if (t)
      for (const [y, p] of this.async_deriveds) {
        const b = _.async_deriveds.get(y);
        b && p.promise.then(b.resolve).catch(b.reject);
      }
    var a = [..._.current.keys()].filter(
      (y) => !/** @type {[any, boolean]} */
      _.current.get(y)[1]
    );
    if (!(!d(_, vr) || a.length === 0)) {
      var s = a.filter((y) => !this.current.has(y));
      if (s.length === 0)
        t && _.discard();
      else if (n.length > 0) {
        if (t)
          for (const y of d(this, mr))
            _.unskip_effect(y, (p) => {
              var b;
              p.f & (Wt | fr) ? _.schedule(p) : xe(b = _, Le, or).call(b, [p]);
            });
        _.activate();
        var l = /* @__PURE__ */ new Set(), o = /* @__PURE__ */ new Map();
        for (var u of n)
          ma(u, s, l, o);
        o = /* @__PURE__ */ new Map();
        var f = [..._.current].filter(([y, p]) => {
          const b = this.current.get(y);
          return b ? b[0] !== p[0] || b[1] !== p[1] : !0;
        }).map(([y]) => y);
        if (f.length > 0)
          for (const y of d(this, zr))
            !(y.f & (Rt | kt | ui)) && vs(y, f, o) && (y.f & (fr | Wt) ? (Xe(y, vt), _.schedule(y)) : d(_, bn).add(y));
        if (d(_, Tt).length > 0 && !d(_, Vn)) {
          _.apply();
          for (var h of d(_, Tt))
            xe(w = _, Le, Zi).call(w, h, [], []);
          ie(_, Tt, []);
        }
        _.deactivate();
      }
    }
  }
}, Pr = function() {
  if (this.linked) {
    var t = d(this, Dn), n = d(this, Yn);
    t === null ? Mi = n : ie(t, Yn, n), n === null ? sr = t : ie(n, Dn, t), this.linked = !1;
  }
};
let Zn = gi;
function to(e) {
  var t = Rr;
  Rr = !0;
  try {
    for (var n; ; ) {
      if (Fl(), $ === null)
        return (
          /** @type {T} */
          n
        );
      $.flush();
    }
  } finally {
    Rr = t;
  }
}
function no() {
  try {
    gl();
  } catch (e) {
    On(e, Qi);
  }
}
let $t = null;
function Ss(e) {
  var t = e.length;
  if (t !== 0) {
    for (var n = 0; n < t; ) {
      var i = e[n++];
      if (!(i.f & (Rt | kt)) && Wr(i) && ($t = /* @__PURE__ */ new Set(), kr(i), i.deps === null && i.first === null && i.nodes === null && i.teardown === null && i.ac === null && Ma(i), ($t == null ? void 0 : $t.size) > 0)) {
        Xn.clear();
        for (const a of $t) {
          if (a.f & (Rt | kt)) continue;
          const s = [a];
          let l = a.parent;
          for (; l !== null; )
            $t.has(l) && ($t.delete(l), s.push(l)), l = l.parent;
          for (let o = s.length - 1; o >= 0; o--) {
            const u = s[o];
            u.f & (Rt | kt) || kr(u);
          }
        }
        $t.clear();
      }
    }
    $t = null;
  }
}
function ma(e, t, n, i) {
  if (!n.has(e) && (n.add(e), e.reactions !== null))
    for (const a of e.reactions) {
      const s = a.f;
      s & ht ? ma(
        /** @type {Derived} */
        a,
        t,
        n,
        i
      ) : s & (fr | Wt) && !(s & vt) && vs(a, t, i) && (Xe(a, vt), _s(
        /** @type {Effect} */
        a
      ));
    }
}
function vs(e, t, n) {
  const i = n.get(e);
  if (i !== void 0) return i;
  if (e.deps !== null)
    for (const a of e.deps) {
      if (oi.call(t, a))
        return !0;
      if (a.f & ht && vs(
        /** @type {Derived} */
        a,
        t,
        n
      ))
        return n.set(
          /** @type {Derived} */
          a,
          !0
        ), !0;
    }
  return n.set(e, !1), !1;
}
function _s(e) {
  $.schedule(e);
}
function ya(e, t) {
  if (!(e.f & rn && e.f & at)) {
    e.f & vt ? t.d.push(e) : e.f & vn && t.m.push(e), Xe(e, at);
    for (var n = e.first; n !== null; )
      ya(n, t), n = n.next;
  }
}
function ba(e) {
  Xe(e, at);
  for (var t = e.first; t !== null; )
    ba(t), t = t.next;
}
let di = /* @__PURE__ */ new Set();
const Xn = /* @__PURE__ */ new Map();
let wa = !1;
function $n(e, t) {
  var n = {
    f: 0,
    // TODO ideally we could skip this altogether, but it causes type errors
    v: e,
    reactions: null,
    equals: ia,
    rv: 0,
    wv: 0
  };
  return n;
}
// @__NO_SIDE_EFFECTS__
function I(e, t) {
  const n = $n(e);
  return Pa(n), n;
}
// @__NO_SIDE_EFFECTS__
function ro(e, t = !1, n = !0) {
  const i = $n(e);
  return t || (i.equals = aa), i;
}
function c(e, t, n = !1) {
  de !== null && // since we are untracking the function inside `$inspect.with` we need to add this check
  // to ensure we error if state is set inside an inspect effect
  (!nn || de.f & ui) && la() && de.f & (ht | Wt | fr | ui) && (dn === null || !dn.has(e)) && wl();
  let i = n ? Ge(t) : t;
  return wr(e, i, ai);
}
function wr(e, t, n = null) {
  if (!e.equals(t)) {
    Xn.set(e, Tn ? t : e.v);
    var i = Zn.ensure();
    if (i.capture(e, t), e.f & ht) {
      const a = (
        /** @type {Derived} */
        e
      );
      e.f & vt && ds(a), dt === null && fs(a);
    }
    e.wv = Oa(), ka(e, vt, n), ve !== null && ve.f & at && !(ve.f & (rn | Nn)) && (qt === null ? mo([e]) : qt.push(e)), !i.is_fork && di.size > 0 && !wa && io();
  }
  return t;
}
function io() {
  wa = !1;
  for (const e of di) {
    e.f & at && Xe(e, vn);
    let t;
    try {
      t = Wr(e);
    } catch {
      t = !0;
    }
    t && kr(e);
  }
  di.clear();
}
function Nr(e) {
  c(e, e.v + 1);
}
function ka(e, t, n) {
  var i = e.reactions;
  if (i !== null)
    for (var a = i.length, s = 0; s < a; s++) {
      var l = i[s], o = l.f, u = (o & vt) === 0;
      if (u && Xe(l, t), o & ui)
        di.add(
          /** @type {Effect} */
          l
        );
      else if (o & ht) {
        var f = (
          /** @type {Derived} */
          l
        );
        dt == null || dt.delete(f), o & Jn || (o & Xt && (ve === null || !(ve.f & ci)) && (l.f |= Jn), ka(f, vn, n));
      } else if (u) {
        var h = (
          /** @type {Effect} */
          l
        );
        o & Wt && $t !== null && $t.add(h), n !== null ? n.push(h) : _s(h);
      }
    }
}
function Ge(e) {
  if (typeof e != "object" || e === null || kn in e)
    return e;
  const t = cs(e);
  if (t !== il && t !== sl)
    return e;
  var n = /* @__PURE__ */ new Map(), i = us(e), a = /* @__PURE__ */ I(0), s = Kn, l = (o) => {
    if (Kn === s)
      return o();
    var u = de, f = Kn;
    Gt(null), Is(s);
    var h = o();
    return Gt(u), Is(f), h;
  };
  return i && n.set("length", /* @__PURE__ */ I(
    /** @type {any[]} */
    e.length
  )), new Proxy(
    /** @type {any} */
    e,
    {
      defineProperty(o, u, f) {
        (!("value" in f) || f.configurable === !1 || f.enumerable === !1 || f.writable === !1) && yl();
        var h = n.get(u);
        return h === void 0 ? l(() => {
          var w = /* @__PURE__ */ I(f.value);
          return n.set(u, w), w;
        }) : c(h, f.value, !0), !0;
      },
      deleteProperty(o, u) {
        var f = n.get(u);
        if (f === void 0) {
          if (u in o) {
            const h = l(() => /* @__PURE__ */ I(rt));
            n.set(u, h), Nr(a);
          }
        } else
          c(f, rt), Nr(a);
        return !0;
      },
      get(o, u, f) {
        var y;
        if (u === kn)
          return e;
        var h = n.get(u), w = u in o;
        if (h === void 0 && (!w || (y = cr(o, u)) != null && y.writable) && (h = l(() => {
          var p = Ge(w ? o[u] : rt), b = /* @__PURE__ */ I(p);
          return b;
        }), n.set(u, h)), h !== void 0) {
          var _ = r(h);
          return _ === rt ? void 0 : _;
        }
        return Reflect.get(o, u, f);
      },
      getOwnPropertyDescriptor(o, u) {
        var f = Reflect.getOwnPropertyDescriptor(o, u);
        if (f && "value" in f) {
          var h = n.get(u);
          h && (f.value = r(h));
        } else if (f === void 0) {
          var w = n.get(u), _ = w == null ? void 0 : w.v;
          if (w !== void 0 && _ !== rt)
            return {
              enumerable: !0,
              configurable: !0,
              value: _,
              writable: !0
            };
        }
        return f;
      },
      has(o, u) {
        var _;
        if (u === kn)
          return !0;
        var f = n.get(u), h = f !== void 0 && f.v !== rt || Reflect.has(o, u);
        if (f !== void 0 || ve !== null && (!h || (_ = cr(o, u)) != null && _.writable)) {
          f === void 0 && (f = l(() => {
            var y = h ? Ge(o[u]) : rt, p = /* @__PURE__ */ I(y);
            return p;
          }), n.set(u, f));
          var w = r(f);
          if (w === rt)
            return !1;
        }
        return h;
      },
      set(o, u, f, h) {
        var P;
        var w = n.get(u), _ = u in o;
        if (i && u === "length")
          for (var y = f; y < /** @type {Source<number>} */
          w.v; y += 1) {
            var p = n.get(y + "");
            p !== void 0 ? c(p, rt) : y in o && (p = l(() => /* @__PURE__ */ I(rt)), n.set(y + "", p));
          }
        if (w === void 0)
          (!_ || (P = cr(o, u)) != null && P.writable) && (w = l(() => /* @__PURE__ */ I(void 0)), c(w, Ge(f)), n.set(u, w));
        else {
          _ = w.v !== rt;
          var b = l(() => Ge(f));
          c(w, b);
        }
        var m = Reflect.getOwnPropertyDescriptor(o, u);
        if (m != null && m.set && m.set.call(h, f), !_) {
          if (i && typeof u == "string") {
            var T = (
              /** @type {Source<number>} */
              n.get("length")
            ), V = Number(u);
            Number.isInteger(V) && V >= T.v && c(T, V + 1);
          }
          Nr(a);
        }
        return !0;
      },
      ownKeys(o) {
        r(a);
        var u = Reflect.ownKeys(o).filter((w) => {
          var _ = n.get(w);
          return _ === void 0 || _.v !== rt;
        });
        for (var [f, h] of n)
          h.v !== rt && !(f in o) && u.push(f);
        return u;
      },
      setPrototypeOf() {
        bl();
      }
    }
  );
}
function Ts(e) {
  try {
    if (e !== null && typeof e == "object" && kn in e)
      return e[kn];
  } catch {
  }
  return e;
}
function so(e, t) {
  return Object.is(Ts(e), Ts(t));
}
var $i, xa, Sa, Ta;
function ao() {
  if ($i === void 0) {
    $i = window, xa = /Firefox/.test(navigator.userAgent);
    var e = Element.prototype, t = Node.prototype, n = Text.prototype;
    Sa = cr(t, "firstChild").get, Ta = cr(t, "nextSibling").get, ws(e) && (e[Vi] = void 0, e[ni] = null, e[Wi] = void 0, e.__e = void 0), ws(n) && (n[Mr] = void 0);
  }
}
function Sn(e = "") {
  return document.createTextNode(e);
}
// @__NO_SIDE_EFFECTS__
function vi(e) {
  return (
    /** @type {TemplateNode | null} */
    Sa.call(e)
  );
}
// @__NO_SIDE_EFFECTS__
function Vr(e) {
  return (
    /** @type {TemplateNode | null} */
    Ta.call(e)
  );
}
function g(e, t) {
  return /* @__PURE__ */ vi(e);
}
function Ke(e, t = !1) {
  {
    var n = /* @__PURE__ */ vi(e);
    return n instanceof Comment && n.data === "" ? /* @__PURE__ */ Vr(n) : n;
  }
}
function S(e, t = 1, n = !1) {
  let i = e;
  for (; t--; )
    i = /** @type {TemplateNode} */
    /* @__PURE__ */ Vr(i);
  return i;
}
function lo(e) {
  e.textContent = "";
}
function Ea() {
  return !1;
}
function oo(e, t, n) {
  return (
    /** @type {T extends keyof HTMLElementTagNameMap ? HTMLElementTagNameMap[T] : Element} */
    n ? document.createElement(e, { is: n }) : document.createElement(e)
  );
}
let Es = !1;
function uo() {
  Es || (Es = !0, document.addEventListener(
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
            (t = n[ri]) == null || t.call(n);
      });
    },
    // In the capture phase to guarantee we get noticed of it (no possibility of stopPropagation)
    { capture: !0 }
  ));
}
function Tr(e) {
  var t = de, n = ve;
  Gt(null), _n(null);
  try {
    return e();
  } finally {
    Gt(t), _n(n);
  }
}
function co(e, t, n, i = n) {
  e.addEventListener(t, () => Tr(n));
  const a = (
    /** @type {any} */
    e[ri]
  );
  a ? e[ri] = () => {
    a(), i(!0);
  } : e[ri] = () => i(!0), uo();
}
function fo(e) {
  ve === null && (de === null && pl(), hl()), Tn && _l();
}
function vo(e, t) {
  var n = t.last;
  n === null ? t.last = t.first = e : (n.next = e, e.prev = n, t.last = e);
}
function En(e, t) {
  var n = ve;
  n !== null && n.f & kt && (e |= kt);
  var i = {
    ctx: _t,
    deps: null,
    nodes: null,
    f: e | vt | Xt,
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
  $ == null || $.register_created_effect(i);
  var a = i;
  if (e & yr)
    ur !== null ? ur.push(i) : Zn.ensure().schedule(i);
  else if (t !== null) {
    try {
      kr(i);
    } catch (l) {
      throw It(i), l;
    }
    a.deps === null && a.teardown === null && a.nodes === null && a.first === a.last && // either `null`, or a singular child
    !(a.f & Sr) && (a = a.first, e & Wt && e & Qn && a !== null && (a.f |= Qn));
  }
  if (a !== null && (a.parent = n, n !== null && vo(a, n), de !== null && de.f & ht && !(e & Nn))) {
    var s = (
      /** @type {Derived} */
      de
    );
    (s.effects ?? (s.effects = [])).push(a);
  }
  return i;
}
function hs() {
  return de !== null && !nn;
}
function ps(e) {
  const t = En(bi, null);
  return Xe(t, at), t.teardown = e, t;
}
function Vt(e) {
  fo();
  var t = (
    /** @type {Effect} */
    ve.f
  ), n = !de && (t & rn) !== 0 && _t !== null && !_t.i;
  if (n) {
    var i = (
      /** @type {ComponentContext} */
      _t
    );
    (i.e ?? (i.e = [])).push(e);
  } else
    return Aa(e);
}
function Aa(e) {
  return En(yr | ul, e);
}
function _o(e) {
  Zn.ensure();
  const t = En(Nn | Sr, e);
  return (n = {}) => new Promise((i) => {
    n.outro ? Gn(t, () => {
      It(t), i(void 0);
    }) : (It(t), i(void 0));
  });
}
function ki(e) {
  return En(yr, e);
}
function ho(e) {
  return En(fr | Sr, e);
}
function xi(e, t = 0) {
  return En(bi | t, e);
}
function G(e, t = [], n = [], i = []) {
  Gl(i, t, n, (a) => {
    En(bi, () => {
      e(...a.map(r));
    });
  });
}
function Si(e, t = 0) {
  var n = En(Wt | t, e);
  return n;
}
function Yt(e) {
  return En(rn | Sr, e);
}
function Ia(e) {
  var t = e.teardown;
  if (t !== null) {
    const n = Tn, i = de;
    As(!0), Gt(null);
    try {
      t.call(null);
    } finally {
      As(n), Gt(i);
    }
  }
}
function gs(e, t = !1) {
  var n = e.first;
  for (e.first = e.last = null; n !== null; ) {
    const a = n.ac;
    a !== null && Tr(() => {
      a.abort(wi);
    });
    var i = n.next;
    n.f & Nn ? n.parent = null : It(n, t), n = i;
  }
}
function po(e) {
  for (var t = e.first; t !== null; ) {
    var n = t.next;
    t.f & rn || It(t), t = n;
  }
}
function It(e, t = !0) {
  var n = !1;
  (t || e.f & ol) && e.nodes !== null && e.nodes.end !== null && (go(
    e.nodes.start,
    /** @type {TemplateNode} */
    e.nodes.end
  ), n = !0), e.f |= Yi, gs(e, t && !n), Fr(e, 0);
  var i = e.nodes && e.nodes.t;
  if (i !== null)
    for (const s of i)
      s.stop();
  Ia(e), e.f ^= Yi, e.f |= Rt;
  var a = e.parent;
  a !== null && a.first !== null && Ma(e), e.next = e.prev = e.teardown = e.ctx = e.deps = e.fn = e.nodes = e.ac = e.b = null;
}
function go(e, t) {
  for (; e !== null; ) {
    var n = e === t ? null : /* @__PURE__ */ Vr(e);
    e.remove(), e = n;
  }
}
function Ma(e) {
  var t = e.parent, n = e.prev, i = e.next;
  n !== null && (n.next = i), i !== null && (i.prev = n), t !== null && (t.first === e && (t.first = i), t.last === e && (t.last = n));
}
function Gn(e, t, n = !0) {
  var i = [];
  La(e, i, !0);
  var a = () => {
    n && It(e), t && t();
  }, s = i.length;
  if (s > 0) {
    var l = () => --s || a();
    for (var o of i)
      o.out(l);
  } else
    a();
}
function La(e, t, n) {
  if (!(e.f & kt)) {
    e.f ^= kt;
    var i = e.nodes && e.nodes.t;
    if (i !== null)
      for (const o of i)
        (o.is_global || n) && t.push(o);
    for (var a = e.first; a !== null; ) {
      var s = a.next;
      if (!(a.f & Nn)) {
        var l = (a.f & Qn) !== 0 || // If this is a branch effect without a block effect parent,
        // it means the parent block effect was pruned. In that case,
        // transparency information was transferred to the branch effect.
        (a.f & rn) !== 0 && (e.f & Wt) !== 0;
        La(a, t, l ? n : !1);
      }
      a = s;
    }
  }
}
function _i(e) {
  Ca(e, !0);
}
function Ca(e, t) {
  if (e.f & kt) {
    e.f ^= kt, e.f & at || (Xe(e, vt), Zn.ensure().schedule(e));
    for (var n = e.first; n !== null; ) {
      var i = n.next, a = (n.f & Qn) !== 0 || (n.f & rn) !== 0;
      Ca(n, a ? t : !1), n = i;
    }
    var s = e.nodes && e.nodes.t;
    if (s !== null)
      for (const l of s)
        (l.is_global || t) && l.in();
  }
}
function ms(e, t) {
  if (e.nodes)
    for (var n = e.nodes.start, i = e.nodes.end; n !== null; ) {
      var a = n === i ? null : /* @__PURE__ */ Vr(n);
      t.append(n), n = a;
    }
}
let li = !1, Tn = !1;
function As(e) {
  Tn = e;
}
let de = null, nn = !1;
function Gt(e) {
  de = e;
}
let ve = null;
function _n(e) {
  ve = e;
}
let dn = null;
function Pa(e) {
  de !== null && (dn ?? (dn = /* @__PURE__ */ new Set())).add(e);
}
let Et = null, Pt = 0, qt = null;
function mo(e) {
  qt = e;
}
let Da = 1, qn = 0, Kn = qn;
function Is(e) {
  Kn = e;
}
function Oa() {
  return ++Da;
}
function Wr(e) {
  var t = e.f;
  if (t & vt)
    return !0;
  if (t & ht && (e.f &= ~Jn), t & vn) {
    for (var n = (
      /** @type {Value[]} */
      e.deps
    ), i = n.length, a = 0; a < i; a++) {
      var s = n[a];
      if (Wr(
        /** @type {Derived} */
        s
      ) && _a(
        /** @type {Derived} */
        s
      ), s.wv > e.wv)
        return !0;
    }
    t & Xt && // During time traveling we don't want to reset the status so that
    // traversal of the graph in the other batches still happens
    dt === null && Xe(e, at);
  }
  return !1;
}
function Ra(e, t, n = !0) {
  var i = e.reactions;
  if (i !== null && !(dn !== null && dn.has(e)))
    for (var a = 0; a < i.length; a++) {
      var s = i[a];
      s.f & ht ? Ra(
        /** @type {Derived} */
        s,
        t,
        !1
      ) : t === s && (n ? Xe(s, vt) : s.f & at && Xe(s, vn), _s(
        /** @type {Effect} */
        s
      ));
    }
}
function Na(e) {
  var b;
  var t = Et, n = Pt, i = qt, a = de, s = dn, l = _t, o = nn, u = Kn, f = e.f;
  Et = /** @type {null | Value[]} */
  null, Pt = 0, qt = null, de = f & (rn | Nn) ? null : e, dn = null, br(e.ctx), nn = !1, Kn = ++qn, e.ac !== null && (Tr(() => {
    e.ac.abort(wi);
  }), e.ac = null);
  try {
    e.f |= ci;
    var h = (
      /** @type {Function} */
      e.fn
    ), w = h();
    e.f |= er;
    var _ = e.deps, y = $ == null ? void 0 : $.is_fork;
    if (Et !== null) {
      var p;
      if (y || Fr(e, Pt), _ !== null && Pt > 0)
        for (_.length = Pt + Et.length, p = 0; p < Et.length; p++)
          _[Pt + p] = Et[p];
      else
        e.deps = _ = Et;
      if (hs() && e.f & Xt)
        for (p = Pt; p < _.length; p++)
          ((b = _[p]).reactions ?? (b.reactions = [])).push(e);
    } else !y && _ !== null && Pt < _.length && (Fr(e, Pt), _.length = Pt);
    if (la() && qt !== null && !nn && _ !== null && !(e.f & (ht | vn | vt)))
      for (p = 0; p < /** @type {Source[]} */
      qt.length; p++)
        Ra(
          qt[p],
          /** @type {Effect} */
          e
        );
    if (a !== null && a !== e) {
      if (qn++, a.deps !== null)
        for (let m = 0; m < n; m += 1)
          a.deps[m].rv = qn;
      if (t !== null)
        for (const m of t)
          m.rv = qn;
      qt !== null && (i === null ? i = qt : i.push(.../** @type {Source[]} */
      qt));
    }
    return e.f & Rn && (e.f ^= Rn), w;
  } catch (m) {
    return ua(m);
  } finally {
    e.f ^= ci, Et = t, Pt = n, qt = i, de = a, dn = s, br(l), nn = o, Kn = u;
  }
}
function yo(e, t) {
  let n = t.reactions;
  if (n !== null) {
    var i = nl.call(n, e);
    if (i !== -1) {
      var a = n.length - 1;
      a === 0 ? n = t.reactions = null : (n[i] = n[a], n.pop());
    }
  }
  if (n === null && t.f & ht && // Destroying a child effect while updating a parent effect can cause a dependency to appear
  // to be unused, when in fact it is used by the currently-updating parent. Checking `new_deps`
  // allows us to skip the expensive work of disconnecting and immediately reconnecting it
  (Et === null || !oi.call(Et, t))) {
    var s = (
      /** @type {Derived} */
      t
    );
    s.f & Xt && (s.f ^= Xt, s.f &= ~Jn), s.v !== rt && fs(s), Zl(s), Fr(s, 0);
  }
}
function Fr(e, t) {
  var n = e.deps;
  if (n !== null)
    for (var i = t; i < n.length; i++)
      yo(e, n[i]);
}
function kr(e) {
  var t = e.f;
  if (!(t & Rt)) {
    Xe(e, at);
    var n = ve, i = li;
    ve = e, li = !0;
    try {
      t & (Wt | ta) ? po(e) : gs(e), Ia(e);
      var a = Na(e);
      e.teardown = typeof a == "function" ? a : null, e.wv = Da;
      var s;
    } finally {
      li = i, ve = n;
    }
  }
}
async function ja() {
  await Promise.resolve(), to();
}
function r(e) {
  var t = e.f, n = (t & ht) !== 0;
  if (de !== null && !nn) {
    var i = ve !== null && (ve.f & Rt) !== 0;
    if (!i && (dn === null || !dn.has(e))) {
      var a = de.deps;
      if (de.f & ci)
        e.rv < qn && (e.rv = qn, Et === null && a !== null && a[Pt] === e ? Pt++ : Et === null ? Et = [e] : Et.push(e));
      else {
        de.deps ?? (de.deps = []), oi.call(de.deps, e) || de.deps.push(e);
        var s = e.reactions;
        s === null ? e.reactions = [de] : oi.call(s, de) || s.push(de);
      }
    }
  }
  if (Tn && Xn.has(e))
    return Xn.get(e);
  if (n) {
    var l = (
      /** @type {Derived} */
      e
    );
    if (Tn) {
      var o = l.v;
      return (!(l.f & at) && l.reactions !== null || Ua(l)) && (o = ds(l)), Xn.set(l, o), o;
    }
    var u = (l.f & Xt) === 0 && !nn && de !== null && (li || (de.f & Xt) !== 0), f = (l.f & er) === 0;
    Wr(l) && (u && (l.f |= Xt), _a(l)), u && !f && (ha(l), Fa(l));
  }
  if (dt != null && dt.has(e))
    return dt.get(e);
  if (e.f & Rn)
    throw e.v;
  return e.v;
}
function Fa(e) {
  if (e.f |= Xt, e.deps !== null)
    for (const t of e.deps)
      (t.reactions ?? (t.reactions = [])).push(e), t.f & ht && !(t.f & Xt) && (ha(
        /** @type {Derived} */
        t
      ), Fa(
        /** @type {Derived} */
        t
      ));
}
function Ua(e) {
  if (e.v === rt) return !0;
  if (e.deps === null) return !1;
  for (const t of e.deps)
    if (Xn.has(t) || t.f & ht && Ua(
      /** @type {Derived} */
      t
    ))
      return !0;
  return !1;
}
function st(e) {
  var t = nn;
  try {
    return nn = !0, e();
  } finally {
    nn = t;
  }
}
function bo(e) {
  if (!(typeof e != "object" || !e || e instanceof EventTarget)) {
    if (kn in e)
      es(e);
    else if (!Array.isArray(e))
      for (let t in e) {
        const n = e[t];
        typeof n == "object" && n && kn in n && es(n);
      }
  }
}
function es(e, t = /* @__PURE__ */ new Set()) {
  if (typeof e == "object" && e !== null && // We don't want to traverse DOM elements
  !(e instanceof EventTarget) && !t.has(e)) {
    t.add(e), e instanceof Date && e.getTime();
    for (let i in e)
      try {
        es(e[i], t);
      } catch {
      }
    const n = cs(e);
    if (n !== Object.prototype && n !== Array.prototype && n !== Map.prototype && n !== Set.prototype && n !== Date.prototype) {
      const i = $s(n);
      for (let a in i) {
        const s = i[a].get;
        if (s)
          try {
            s.call(e);
          } catch {
          }
      }
    }
  }
}
const wo = ["touchstart", "touchmove"];
function ko(e) {
  return wo.includes(e);
}
const Bn = Symbol("events"), qa = /* @__PURE__ */ new Set(), ts = /* @__PURE__ */ new Set();
function xo(e, t, n, i = {}) {
  function a(s) {
    if (i.capture || ns.call(t, s), !s.cancelBubble)
      return Tr(() => n == null ? void 0 : n.call(this, s));
  }
  return e.startsWith("pointer") || e.startsWith("touch") || e === "wheel" ? xn(() => {
    t.addEventListener(e, a, i);
  }) : t.addEventListener(e, a, i), a;
}
function So(e, t, n, i, a) {
  var s = { capture: i, passive: a }, l = xo(e, t, n, s);
  (t === document.body || // @ts-ignore
  t === window || // @ts-ignore
  t === document || // Firefox has quirky behavior, it can happen that we still get "canplay" events when the element is already removed
  t instanceof HTMLMediaElement) && ps(() => {
    t.removeEventListener(e, l, s);
  });
}
function D(e, t, n) {
  (t[Bn] ?? (t[Bn] = {}))[e] = n;
}
function Xr(e) {
  for (var t = 0; t < e.length; t++)
    qa.add(e[t]);
  for (var n of ts)
    n(e);
}
let Ms = null;
function ns(e) {
  var b, m;
  var t = this, n = (
    /** @type {Node} */
    t.ownerDocument
  ), i = e.type, a = ((b = e.composedPath) == null ? void 0 : b.call(e)) || [], s = (
    /** @type {null | Element} */
    a[0] || e.target
  );
  Ms = e;
  var l = 0, o = Ms === e && e[Bn];
  if (o) {
    var u = a.indexOf(o);
    if (u !== -1 && (t === document || t === /** @type {any} */
    window)) {
      e[Bn] = t;
      return;
    }
    var f = a.indexOf(t);
    if (f === -1)
      return;
    u <= f && (l = u);
  }
  if (s = /** @type {Element} */
  a[l] || e.target, s !== t) {
    rl(e, "currentTarget", {
      configurable: !0,
      get() {
        return s || n;
      }
    });
    var h = de, w = ve;
    Gt(null), _n(null);
    try {
      for (var _, y = []; s !== null && s !== t; ) {
        try {
          var p = (m = s[Bn]) == null ? void 0 : m[i];
          p != null && (!/** @type {any} */
          s.disabled || // DOM could've been updated already by the time this is reached, so we check this as well
          // -> the target could not have been disabled because it emits the event in the first place
          e.target === s) && p.call(s, e);
        } catch (T) {
          _ ? y.push(T) : _ = T;
        }
        if (e.cancelBubble) break;
        l++, s = l < a.length ? (
          /** @type {Element} */
          a[l]
        ) : null;
      }
      if (_) {
        for (let T of y)
          queueMicrotask(() => {
            throw T;
          });
        throw _;
      }
    } finally {
      e[Bn] = t, delete e.currentTarget, Gt(h), _n(w);
    }
  }
}
var Js;
const Ci = (
  // We gotta write it like this because after downleveling the pure comment may end up in the wrong location
  ((Js = globalThis == null ? void 0 : globalThis.window) == null ? void 0 : Js.trustedTypes) && /* @__PURE__ */ globalThis.window.trustedTypes.createPolicy("svelte-trusted-html", {
    /** @param {string} html */
    createHTML: (e) => e
  })
);
function To(e) {
  return (
    /** @type {string} */
    (Ci == null ? void 0 : Ci.createHTML(e)) ?? e
  );
}
function Eo(e) {
  var t = oo("template");
  return t.innerHTML = To(e.replaceAll("<!>", "<!---->")), t.content;
}
function hi(e, t) {
  var n = (
    /** @type {Effect} */
    ve
  );
  n.nodes === null && (n.nodes = { start: e, end: t, a: null, t: null });
}
// @__NO_SIDE_EFFECTS__
function E(e, t) {
  var n = (t & Pl) !== 0, i = (t & Dl) !== 0, a, s = !e.startsWith("<!>");
  return () => {
    a === void 0 && (a = Eo(s ? e : "<!>" + e), n || (a = /** @type {TemplateNode} */
    /* @__PURE__ */ vi(a)));
    var l = (
      /** @type {TemplateNode} */
      i || xa ? document.importNode(a, !0) : a.cloneNode(!0)
    );
    if (n) {
      var o = (
        /** @type {TemplateNode} */
        /* @__PURE__ */ vi(l)
      ), u = (
        /** @type {TemplateNode} */
        l.lastChild
      );
      hi(o, u);
    } else
      hi(l, l);
    return l;
  };
}
function Ba(e = "") {
  {
    var t = Sn(e + "");
    return hi(t, t), t;
  }
}
function cn() {
  var e = document.createDocumentFragment(), t = document.createComment(""), n = Sn();
  return e.append(t, n), hi(t, n), e;
}
function x(e, t) {
  e !== null && e.before(
    /** @type {Node} */
    t
  );
}
let rs = !0;
function Z(e, t) {
  var n = t == null ? "" : typeof t == "object" ? `${t}` : t;
  n !== /** @type {any} */
  (e[Mr] ?? (e[Mr] = e.nodeValue)) && (e[Mr] = n, e.nodeValue = `${n}`);
}
function Ao(e, t) {
  return Io(e, t);
}
const ti = /* @__PURE__ */ new Map();
function Io(e, { target: t, anchor: n, props: i = {}, events: a, context: s, intro: l = !0, transformError: o }) {
  ao();
  var u = void 0, f = _o(() => {
    var h = n ?? t.appendChild(Sn());
    Hl(
      /** @type {TemplateNode} */
      h,
      {
        pending: () => {
        }
      },
      (y) => {
        tr({});
        var p = (
          /** @type {ComponentContext} */
          _t
        );
        s && (p.c = s), a && (i.$$events = a), rs = l, u = e(y, i) || {}, rs = !0, nr();
      },
      o
    );
    var w = /* @__PURE__ */ new Set(), _ = (y) => {
      for (var p = 0; p < y.length; p++) {
        var b = y[p];
        if (!w.has(b)) {
          w.add(b);
          var m = ko(b);
          for (const P of [t, document]) {
            var T = ti.get(P);
            T === void 0 && (T = /* @__PURE__ */ new Map(), ti.set(P, T));
            var V = T.get(b);
            V === void 0 ? (P.addEventListener(b, ns, { passive: m }), T.set(b, 1)) : T.set(b, V + 1);
          }
        }
      }
    };
    return _(yi(qa)), ts.add(_), () => {
      var m;
      for (var y of w)
        for (const T of [t, document]) {
          var p = (
            /** @type {Map<string, number>} */
            ti.get(T)
          ), b = (
            /** @type {number} */
            p.get(y)
          );
          --b == 0 ? (T.removeEventListener(y, ns), p.delete(y), p.size === 0 && ti.delete(T)) : p.set(y, b);
        }
      ts.delete(_), h !== n && ((m = h.parentNode) == null || m.removeChild(h));
    };
  });
  return Mo.set(u, f), u;
}
let Mo = /* @__PURE__ */ new WeakMap();
var tn, un, Ot, Wn, Hr, Yr, mi;
class za {
  /**
   * @param {TemplateNode} anchor
   * @param {boolean} transition
   */
  constructor(t, n = !0) {
    /** @type {TemplateNode} */
    Ct(this, "anchor");
    /** @type {Map<Batch, Key>} */
    ae(this, tn, /* @__PURE__ */ new Map());
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
    ae(this, un, /* @__PURE__ */ new Map());
    /**
     * Similar to #onscreen with respect to the keys, but contains branches that are not yet
     * in the DOM, because their insertion is deferred.
     * @type {Map<Key, Branch>}
     */
    ae(this, Ot, /* @__PURE__ */ new Map());
    /**
     * Keys of effects that are currently outroing
     * @type {Set<Key>}
     */
    ae(this, Wn, /* @__PURE__ */ new Set());
    /**
     * Whether to pause (i.e. outro) on change, or destroy immediately.
     * This is necessary for `<svelte:element>`
     */
    ae(this, Hr, !0);
    /**
     * @param {Batch} batch
     */
    ae(this, Yr, (t) => {
      if (d(this, tn).has(t)) {
        var n = (
          /** @type {Key} */
          d(this, tn).get(t)
        ), i = d(this, un).get(n);
        if (i)
          _i(i), d(this, Wn).delete(n);
        else {
          var a = d(this, Ot).get(n);
          a && (_i(a.effect), d(this, un).set(n, a.effect), d(this, Ot).delete(n), a.fragment.lastChild.remove(), this.anchor.before(a.fragment), i = a.effect);
        }
        for (const [s, l] of d(this, tn)) {
          if (d(this, tn).delete(s), s === t)
            break;
          const o = d(this, Ot).get(l);
          o && (It(o.effect), d(this, Ot).delete(l));
        }
        for (const [s, l] of d(this, un)) {
          if (s === n || d(this, Wn).has(s)) continue;
          const o = () => {
            if (Array.from(d(this, tn).values()).includes(s)) {
              var f = document.createDocumentFragment();
              ms(l, f), f.append(Sn()), d(this, Ot).set(s, { effect: l, fragment: f });
            } else
              It(l);
            d(this, Wn).delete(s), d(this, un).delete(s);
          };
          d(this, Hr) || !i ? (d(this, Wn).add(s), Gn(l, o, !1)) : o();
        }
      }
    });
    /**
     * @param {Batch} batch
     */
    ae(this, mi, (t) => {
      d(this, tn).delete(t);
      const n = Array.from(d(this, tn).values());
      for (const [i, a] of d(this, Ot))
        n.includes(i) || (It(a.effect), d(this, Ot).delete(i));
    });
    this.anchor = t, ie(this, Hr, n);
  }
  /**
   *
   * @param {any} key
   * @param {null | ((target: TemplateNode) => void)} fn
   */
  ensure(t, n) {
    var i = (
      /** @type {Batch} */
      $
    ), a = Ea();
    if (n && !d(this, un).has(t) && !d(this, Ot).has(t))
      if (a) {
        var s = document.createDocumentFragment(), l = Sn();
        s.append(l), d(this, Ot).set(t, {
          effect: Yt(() => n(l)),
          fragment: s
        });
      } else
        d(this, un).set(
          t,
          Yt(() => n(this.anchor))
        );
    if (d(this, tn).set(i, t), a) {
      for (const [o, u] of d(this, un))
        o === t ? i.unskip_effect(u) : i.skip_effect(u);
      for (const [o, u] of d(this, Ot))
        o === t ? i.unskip_effect(u.effect) : i.skip_effect(u.effect);
      i.oncommit(d(this, Yr)), i.ondiscard(d(this, mi));
    } else
      d(this, Yr).call(this, i);
  }
}
tn = new WeakMap(), un = new WeakMap(), Ot = new WeakMap(), Wn = new WeakMap(), Hr = new WeakMap(), Yr = new WeakMap(), mi = new WeakMap();
function F(e, t, n = !1) {
  var i = new za(e), a = n ? Qn : 0;
  function s(l, o) {
    i.ensure(l, o);
  }
  Si(() => {
    var l = !1;
    t((o, u = 0) => {
      l = !0, s(u, o);
    }), l || s(-1, null);
  }, a);
}
const Lo = Symbol("NaN");
function Co(e, t, n) {
  var i = new za(e);
  Si(() => {
    var a = t();
    a !== a && (a = /** @type {any} */
    Lo), i.ensure(a, n);
  });
}
function is(e, t) {
  return t;
}
function Po(e, t, n) {
  for (var i = [], a = t.length, s, l = t.length, o = 0; o < a; o++) {
    let w = t[o];
    Gn(
      w,
      () => {
        if (s) {
          if (s.pending.delete(w), s.done.add(w), s.pending.size === 0) {
            var _ = (
              /** @type {Set<EachOutroGroup>} */
              e.outrogroups
            );
            ss(e, yi(s.done)), _.delete(s), _.size === 0 && (e.outrogroups = null);
          }
        } else
          l -= 1;
      },
      !1
    );
  }
  if (l === 0) {
    var u = i.length === 0 && n !== null;
    if (u) {
      var f = (
        /** @type {Element} */
        n
      ), h = (
        /** @type {Element} */
        f.parentNode
      );
      lo(h), h.append(f), e.items.clear();
    }
    ss(e, t, !u);
  } else
    s = {
      pending: new Set(t),
      done: /* @__PURE__ */ new Set()
    }, (e.outrogroups ?? (e.outrogroups = /* @__PURE__ */ new Set())).add(s);
}
function ss(e, t, n = !0) {
  var i;
  if (e.pending.size > 0) {
    i = /* @__PURE__ */ new Set();
    for (const l of e.pending.values())
      for (const o of l)
        i.add(
          /** @type {EachItem} */
          e.items.get(o).e
        );
  }
  for (var a = 0; a < t.length; a++) {
    var s = t[a];
    if (i != null && i.has(s)) {
      s.f |= fn;
      const l = document.createDocumentFragment();
      ms(s, l);
    } else
      It(t[a], n);
  }
}
var Ls;
function At(e, t, n, i, a, s = null) {
  var l = e, o = /* @__PURE__ */ new Map(), u = (t & ra) !== 0;
  if (u) {
    var f = (
      /** @type {Element} */
      e
    );
    l = f.appendChild(Sn());
  }
  var h = null, w = /* @__PURE__ */ va(() => {
    var P = n();
    return (
      /** @type {V[]} */
      us(P) ? P : P == null ? [] : yi(P)
    );
  }), _, y = /* @__PURE__ */ new Map(), p = !0;
  function b(P) {
    V.effect.f & Rt || (V.pending.delete(P), V.fallback = h, Do(V, _, l, t, i), h !== null && (_.length === 0 ? h.f & fn ? (h.f ^= fn, Dr(h, null, l)) : _i(h) : Gn(h, () => {
      h = null;
    })));
  }
  function m(P) {
    V.pending.delete(P);
  }
  var T = Si(() => {
    _ = /** @type {V[]} */
    r(w);
    for (var P = _.length, C = /* @__PURE__ */ new Set(), K = (
      /** @type {Batch} */
      $
    ), W = Ea(), R = 0; R < P; R += 1) {
      var Q = _[R], _e = i(Q, R), se = p ? null : o.get(_e);
      se ? (se.v && wr(se.v, Q), se.i && wr(se.i, R), W && K.unskip_effect(se.e)) : (se = Oo(
        o,
        p ? l : Ls ?? (Ls = Sn()),
        Q,
        _e,
        R,
        a,
        t,
        n
      ), p || (se.e.f |= fn), o.set(_e, se)), C.add(_e);
    }
    if (P === 0 && s && !h && (p ? h = Yt(() => s(l)) : (h = Yt(() => s(Ls ?? (Ls = Sn()))), h.f |= fn)), P > C.size && vl(), !p)
      if (y.set(K, C), W) {
        for (const [Se, Ue] of o)
          C.has(Se) || K.skip_effect(Ue.e);
        K.oncommit(b), K.ondiscard(m);
      } else
        b(K);
    r(w);
  }), V = { effect: T, items: o, pending: y, outrogroups: null, fallback: h };
  p = !1;
}
function Ir(e) {
  for (; e !== null && !(e.f & rn); )
    e = e.next;
  return e;
}
function Do(e, t, n, i, a) {
  var se, Se, Ue, be, De, Oe, Re, We, pt;
  var s = (i & Tl) !== 0, l = t.length, o = e.items, u = Ir(e.effect.first), f, h = null, w, _ = [], y = [], p, b, m, T;
  if (s)
    for (T = 0; T < l; T += 1)
      p = t[T], b = a(p, T), m = /** @type {EachItem} */
      o.get(b).e, m.f & fn || ((Se = (se = m.nodes) == null ? void 0 : se.a) == null || Se.measure(), (w ?? (w = /* @__PURE__ */ new Set())).add(m));
  for (T = 0; T < l; T += 1) {
    if (p = t[T], b = a(p, T), m = /** @type {EachItem} */
    o.get(b).e, e.outrogroups !== null)
      for (const He of e.outrogroups)
        He.pending.delete(m), He.done.delete(m);
    if (m.f & kt && (_i(m), s && ((be = (Ue = m.nodes) == null ? void 0 : Ue.a) == null || be.unfix(), (w ?? (w = /* @__PURE__ */ new Set())).delete(m))), m.f & fn)
      if (m.f ^= fn, m === u)
        Dr(m, null, n);
      else {
        var V = h ? h.next : u;
        m === e.effect.last && (e.effect.last = m.prev), m.prev && (m.prev.next = m.next), m.next && (m.next.prev = m.prev), Cn(e, h, m), Cn(e, m, V), Dr(m, V, n), h = m, _ = [], y = [], u = Ir(h.next);
        continue;
      }
    if (m !== u) {
      if (f !== void 0 && f.has(m)) {
        if (_.length < y.length) {
          var P = y[0], C;
          h = P.prev;
          var K = _[0], W = _[_.length - 1];
          for (C = 0; C < _.length; C += 1)
            Dr(_[C], P, n);
          for (C = 0; C < y.length; C += 1)
            f.delete(y[C]);
          Cn(e, K.prev, W.next), Cn(e, h, K), Cn(e, W, P), u = P, h = W, T -= 1, _ = [], y = [];
        } else
          f.delete(m), Dr(m, u, n), Cn(e, m.prev, m.next), Cn(e, m, h === null ? e.effect.first : h.next), Cn(e, h, m), h = m;
        continue;
      }
      for (_ = [], y = []; u !== null && u !== m; )
        (f ?? (f = /* @__PURE__ */ new Set())).add(u), y.push(u), u = Ir(u.next);
      if (u === null)
        continue;
    }
    m.f & fn || _.push(m), h = m, u = Ir(m.next);
  }
  if (e.outrogroups !== null) {
    for (const He of e.outrogroups)
      He.pending.size === 0 && (ss(e, yi(He.done)), (De = e.outrogroups) == null || De.delete(He));
    e.outrogroups.size === 0 && (e.outrogroups = null);
  }
  if (u !== null || f !== void 0) {
    var R = [];
    if (f !== void 0)
      for (m of f)
        m.f & kt || R.push(m);
    for (; u !== null; )
      !(u.f & kt) && u !== e.fallback && R.push(u), u = Ir(u.next);
    var Q = R.length;
    if (Q > 0) {
      var _e = i & ra && l === 0 ? n : null;
      if (s) {
        for (T = 0; T < Q; T += 1)
          (Re = (Oe = R[T].nodes) == null ? void 0 : Oe.a) == null || Re.measure();
        for (T = 0; T < Q; T += 1)
          (pt = (We = R[T].nodes) == null ? void 0 : We.a) == null || pt.fix();
      }
      Po(e, R, _e);
    }
  }
  s && xn(() => {
    var He, gt;
    if (w !== void 0)
      for (m of w)
        (gt = (He = m.nodes) == null ? void 0 : He.a) == null || gt.apply();
  });
}
function Oo(e, t, n, i, a, s, l, o) {
  var u = l & xl ? l & El ? $n(n) : /* @__PURE__ */ ro(n, !1, !1) : null, f = l & Sl ? $n(a) : null;
  return {
    v: u,
    i: f,
    e: Yt(() => (s(t, u ?? n, f ?? a, o), () => {
      e.delete(i);
    }))
  };
}
function Dr(e, t, n) {
  if (e.nodes)
    for (var i = e.nodes.start, a = e.nodes.end, s = t && !(t.f & fn) ? (
      /** @type {EffectNodes} */
      t.nodes.start
    ) : n; i !== null; ) {
      var l = (
        /** @type {TemplateNode} */
        /* @__PURE__ */ Vr(i)
      );
      if (s.before(i), i === a)
        return;
      i = l;
    }
}
function Cn(e, t, n) {
  t === null ? e.effect.first = n : t.next = n, n === null ? e.effect.last = t : n.prev = t;
}
const Ro = () => performance.now(), wn = {
  // don't access requestAnimationFrame eagerly outside method
  // this allows basic testing of user code without JSDOM
  // bunder will eval and remove ternary when the user's app is built
  tick: (
    /** @param {any} _ */
    (e) => requestAnimationFrame(e)
  ),
  now: () => Ro(),
  tasks: /* @__PURE__ */ new Set()
};
function Ha() {
  const e = wn.now();
  wn.tasks.forEach((t) => {
    t.c(e) || (wn.tasks.delete(t), t.f());
  }), wn.tasks.size !== 0 && wn.tick(Ha);
}
function No(e) {
  let t;
  return wn.tasks.size === 0 && wn.tick(Ha), {
    promise: new Promise((n) => {
      wn.tasks.add(t = { c: e, f: n });
    }),
    abort() {
      wn.tasks.delete(t);
    }
  };
}
function Cs(e, t) {
  Tr(() => {
    e.dispatchEvent(new CustomEvent(t));
  });
}
function jo(e) {
  if (e === "float") return "cssFloat";
  if (e === "offset") return "cssOffset";
  if (e.startsWith("--")) return e;
  const t = e.split("-");
  return t.length === 1 ? t[0] : t[0] + t.slice(1).map(
    /** @param {any} word */
    (n) => n[0].toUpperCase() + n.slice(1)
  ).join("");
}
function Ps(e) {
  const t = {}, n = e.split(";");
  for (const i of n) {
    const [a, s] = i.split(":");
    if (!a || s === void 0) break;
    const l = jo(a.trim());
    t[l] = s.trim();
  }
  return t;
}
const Fo = (e) => e;
function Uo(e, t, n, i) {
  var m;
  var a = (e & Cl) !== 0, s = "in", l, o = t.inert, u = t.style.overflow, f, h;
  function w() {
    return Tr(() => l ?? (l = n()(t, (i == null ? void 0 : i()) ?? /** @type {P} */
    {}, {
      direction: s
    })));
  }
  var _ = {
    is_global: a,
    in() {
      t.inert = o, f == null || f.abort(), f = Ya(
        t,
        w(),
        h,
        1,
        () => {
          Cs(t, "introstart");
        },
        () => {
          Cs(t, "introend"), f == null || f.abort(), f = l = void 0, t.style.overflow = u;
        }
      );
    },
    out(T) {
      {
        T == null || T(), l = void 0;
        return;
      }
    },
    stop: () => {
      f == null || f.abort();
    }
  }, y = (
    /** @type {Effect & { nodes: EffectNodes }} */
    ve
  );
  if (((m = y.nodes).t ?? (m.t = [])).push(_), rs) {
    var p = a;
    if (!p) {
      for (var b = (
        /** @type {Effect | null} */
        y.parent
      ); b && b.f & Qn; )
        for (; (b = b.parent) && !(b.f & Wt); )
          ;
      p = !b || (b.f & er) !== 0;
    }
    p && ki(() => {
      st(() => _.in());
    });
  }
}
function Ya(e, t, n, i, a, s) {
  if (al(t)) {
    var l, o = !1;
    return xn(() => {
      if (!o) {
        var m = t({ direction: "in" });
        l = Ya(e, m, n, i, a, s);
      }
    }), {
      abort: () => {
        o = !0, l == null || l.abort();
      },
      deactivate: () => l.deactivate(),
      reset: () => l.reset(),
      t: () => l.t()
    };
  }
  if (!(t != null && t.duration) && !(t != null && t.delay))
    return a(), s(), {
      abort: lr,
      deactivate: lr,
      reset: lr,
      t: () => i
    };
  const { delay: u = 0, css: f, tick: h, easing: w = Fo } = t;
  var _ = [];
  if (h && h(0, 1), f) {
    var y = Ps(f(0, 1));
    _.push(y, y);
  }
  var p = () => 1 - i, b = e.animate(_, { duration: u, fill: "forwards" });
  return b.onfinish = () => {
    b.cancel(), a();
    var m = 1 - i, T = i - m, V = (
      /** @type {number} */
      t.duration * Math.abs(T)
    ), P = [];
    if (V > 0) {
      var C = !1;
      if (f)
        for (var K = Math.ceil(V / 16.666666666666668), W = 0; W <= K; W += 1) {
          var R = m + T * w(W / K), Q = Ps(f(R, 1 - R));
          P.push(Q), C || (C = Q.overflow === "hidden");
        }
      C && (e.style.overflow = "hidden"), p = () => {
        var _e = (
          /** @type {number} */
          /** @type {globalThis.Animation} */
          b.currentTime
        );
        return m + T * w(_e / V);
      }, h && No(() => {
        if (b.playState !== "running") return !1;
        var _e = p();
        return h(_e, 1 - _e), !0;
      });
    }
    b = e.animate(P, { duration: V, fill: "forwards" }), b.onfinish = () => {
      p = () => i, h == null || h(i, 1 - i), s();
    };
  }, {
    abort: () => {
      b && (b.cancel(), b.effect = null, b.onfinish = lr);
    },
    deactivate: () => {
      s = lr;
    },
    reset: () => {
    },
    t: () => p()
  };
}
function qo(e, t, n) {
  ki(() => {
    var i = st(() => t(e, n == null ? void 0 : n()) || {});
    if (n && (i != null && i.update)) {
      var a = !1, s = (
        /** @type {any} */
        {}
      );
      xi(() => {
        var l = n();
        bo(l), a && sa(s, l) && (s = l, i.update(l));
      }), a = !0;
    }
    if (i != null && i.destroy)
      return () => (
        /** @type {Function} */
        i.destroy()
      );
  });
}
const Ds = [...` 	
\r\f \v\uFEFF`];
function Bo(e, t, n) {
  var i = e == null ? "" : "" + e;
  if (t && (i = i ? i + " " + t : t), n) {
    for (var a of Object.keys(n))
      if (n[a])
        i = i ? i + " " + a : a;
      else if (i.length)
        for (var s = a.length, l = 0; (l = i.indexOf(a, l)) >= 0; ) {
          var o = l + s;
          (l === 0 || Ds.includes(i[l - 1])) && (o === i.length || Ds.includes(i[o])) ? i = (l === 0 ? "" : i.substring(0, l)) + i.substring(o + 1) : l = o;
        }
  }
  return i === "" ? null : i;
}
function zo(e, t) {
  return e == null ? null : String(e);
}
function Fe(e, t, n, i, a, s) {
  var l = (
    /** @type {any} */
    e[Vi]
  );
  if (l !== n || l === void 0) {
    var o = Bo(n, i, s);
    o == null ? e.removeAttribute("class") : e.className = o, e[Vi] = n;
  } else if (s && a !== s)
    for (var u in s) {
      var f = !!s[u];
      (a == null || f !== !!a[u]) && e.classList.toggle(u, f);
    }
  return s;
}
function Pi(e, t, n, i) {
  var a = (
    /** @type {any} */
    e[Wi]
  );
  if (a !== t) {
    var s = zo(t);
    s == null ? e.removeAttribute("style") : e.style.cssText = s, e[Wi] = t;
  }
  return i;
}
function Va(e, t, n = !1) {
  if (e.multiple) {
    if (t == null)
      return;
    if (!us(t))
      return Nl();
    for (var i of e.options)
      i.selected = t.includes(Os(i));
    return;
  }
  for (i of e.options) {
    var a = Os(i);
    if (so(a, t)) {
      i.selected = !0;
      return;
    }
  }
  (!n || t !== void 0) && (e.selectedIndex = -1);
}
function Ho(e) {
  var t = new MutationObserver(() => {
    Va(e, e.__value);
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
  }), ps(() => {
    t.disconnect();
  });
}
function Os(e) {
  return "__value" in e ? e.__value : e.value;
}
const Yo = Symbol("is custom element"), Vo = Symbol("is html");
function Ie(e, t, n, i) {
  var a = Wo(e);
  a[t] !== (a[t] = n) && (t === "loading" && (e[fl] = n), n == null ? e.removeAttribute(t) : typeof n != "string" && Xo(e).includes(t) ? e[t] = n : e.setAttribute(t, n));
}
function Wo(e) {
  return (
    /** @type {Record<string | symbol, unknown>} **/
    /** @type {any} */
    e[ni] ?? (e[ni] = {
      [Yo]: e.nodeName.includes("-"),
      [Vo]: e.namespaceURI === Ol
    })
  );
}
var Rs = /* @__PURE__ */ new Map();
function Xo(e) {
  var t = e.getAttribute("is") || e.nodeName, n = Rs.get(t);
  if (n) return n;
  Rs.set(t, n = []);
  for (var i, a = e, s = Element.prototype; s !== a; ) {
    i = $s(a);
    for (var l in i)
      i[l].set && // better safe than sorry, we don't want spread attributes to mess with HTML content
      l !== "innerHTML" && l !== "textContent" && l !== "innerText" && n.push(l);
    a = cs(a);
  }
  return n;
}
function Ur(e, t, n = t) {
  var i = /* @__PURE__ */ new WeakSet();
  co(e, "input", async (a) => {
    var s = a ? e.defaultValue : e.value;
    if (s = Di(e) ? Oi(s) : s, n(s), $ !== null && i.add($), await ja(), s !== (s = t())) {
      var l = e.selectionStart, o = e.selectionEnd, u = e.value.length;
      if (e.value = s ?? "", o !== null) {
        var f = e.value.length;
        l === o && o === u && f > u ? (e.selectionStart = f, e.selectionEnd = f) : (e.selectionStart = l, e.selectionEnd = Math.min(o, f));
      }
    }
  }), // If we are hydrating and the value has since changed,
  // then use the updated value from the input instead.
  // If defaultValue is set, then value == defaultValue
  // TODO Svelte 6: remove input.value check and set to empty string?
  st(t) == null && e.value && (n(Di(e) ? Oi(e.value) : e.value), $ !== null && i.add($)), xi(() => {
    var a = t();
    if (e === document.activeElement) {
      var s = (
        /** @type {Batch} */
        $
      );
      if (i.has(s))
        return;
    }
    Di(e) && a === Oi(e.value) || e.type === "date" && !a && !e.value || a !== e.value && (e.value = a ?? "");
  });
}
function Di(e) {
  var t = e.type;
  return t === "number" || t === "range";
}
function Oi(e) {
  return e === "" ? null : +e;
}
function Ri(e, t) {
  return e === t || (e == null ? void 0 : e[kn]) === t;
}
function xr(e = {}, t, n, i) {
  var a = (
    /** @type {ComponentContext} */
    _t.r
  ), s = (
    /** @type {Effect} */
    ve
  );
  return ki(() => {
    var l, o;
    return xi(() => {
      l = o, o = [], st(() => {
        Ri(n(...o), e) || (t(e, ...o), l && Ri(n(...l), e) && t(null, ...l));
      });
    }), () => {
      let u = s;
      for (; u !== a && u.parent !== null && u.parent.f & Yi; )
        u = u.parent;
      const f = () => {
        o && Ri(n(...o), e) && t(null, ...o);
      }, h = u.teardown;
      u.teardown = () => {
        f(), h == null || h();
      };
    };
  }), e;
}
function it(e, t, n, i) {
  var C;
  var a = !0, s = (n & Ml) !== 0, l = (n & Ll) !== 0, o = (
    /** @type {V} */
    i
  ), u = !0, f = (
    /** @type {Derived<V> | undefined} */
    void 0
  ), h = () => l && a ? (f ?? (f = /* @__PURE__ */ jr(
    /** @type {() => V} */
    i
  )), r(f)) : (u && (u = !1, o = l ? st(
    /** @type {() => V} */
    i
  ) : (
    /** @type {V} */
    i
  )), o);
  let w;
  if (s) {
    var _ = kn in e || cl in e;
    w = ((C = cr(e, t)) == null ? void 0 : C.set) ?? (_ && t in e ? (K) => e[t] = K : void 0);
  }
  var y, p = !1;
  s ? [y, p] = ql(() => (
    /** @type {V} */
    e[t]
  )) : y = /** @type {V} */
  e[t], y === void 0 && i !== void 0 && (y = h(), w && (ml(), w(y)));
  var b;
  if (b = () => {
    var K = (
      /** @type {V} */
      e[t]
    );
    return K === void 0 ? h() : (u = !0, K);
  }, !(n & Il))
    return b;
  if (w) {
    var m = e.$$legacy;
    return (
      /** @type {() => V} */
      function(K, W) {
        return arguments.length > 0 ? ((!W || m || p) && w(W ? b() : K), K) : b();
      }
    );
  }
  var T = !1, V = (n & Al ? jr : va)(() => (T = !1, b()));
  s && r(V);
  var P = (
    /** @type {Effect} */
    ve
  );
  return (
    /** @type {() => V} */
    function(K, W) {
      if (arguments.length > 0) {
        const R = W ? r(V) : s ? Ge(K) : K;
        return c(V, R), T = !0, o !== void 0 && (o = R), K;
      }
      return Tn && T || P.f & Rt ? V.v : r(V);
    }
  );
}
function Go(e) {
  _t === null && na(), Vt(() => {
    const t = st(e);
    if (typeof t == "function") return (
      /** @type {() => void} */
      t
    );
  });
}
function Ko(e) {
  _t === null && na(), Go(() => () => st(e));
}
const Qo = "5";
var Zs;
typeof window < "u" && ((Zs = window.__svelte ?? (window.__svelte = {})).v ?? (Zs.v = /* @__PURE__ */ new Set())).add(Qo);
const rr = (e) => e.searchApiBase || `/api/live/instances/${e.sessionInstanceId}`;
async function Jo(e, t, n, i, a) {
  const s = new URLSearchParams({ limit: "30" });
  t && s.set("q", t), n && s.set("type", n), i && s.set("prefer_type", i), a && s.set("mode", a);
  try {
    const l = await fetch(`${rr(e)}/deep-search?${s}`, {
      headers: { Accept: "application/json" },
      credentials: "same-origin"
    });
    return l.ok ? (await l.json()).results || [] : [];
  } catch {
    return [];
  }
}
async function Zo(e, t, n) {
  const i = new URLSearchParams({ q: t });
  n && i.set("type", n);
  try {
    const a = await fetch(`${rr(e)}/thesession-search?${i}`, {
      headers: { Accept: "application/json" },
      credentials: "same-origin"
    });
    if (!a.ok) return [];
    const s = await a.json();
    return s.success ? s.results || [] : [];
  } catch {
    return [];
  }
}
async function $o(e, t, n) {
  const i = "";
  try {
    const a = await fetch(`${rr(e)}/incipit/${t}${i}`, {
      headers: { Accept: "application/json" },
      credentials: "same-origin"
    });
    return a.ok && (await a.json()).image || null;
  } catch {
    return null;
  }
}
const Ni = /* @__PURE__ */ new Map(), ji = /* @__PURE__ */ new Map();
function Wa(e, t) {
  if (Ni.has(e)) return Promise.resolve(Ni.get(e));
  let n = ji.get(e);
  return n || (n = t().catch(() => null).then((i) => (ji.delete(e), i && Ni.set(e, i), i)), ji.set(e, n)), n;
}
async function as(e, t) {
  const n = await fetch(`${rr(e)}/tune-preview/${t}`, {
    headers: { Accept: "application/json" },
    credentials: "same-origin"
  }), i = await n.json().catch(() => ({}));
  if (!n.ok || !i.success) throw new Error(i.error || `tune preview failed: ${n.status}`);
  return i;
}
function eu(e, t, n) {
  return Wa(`s:${t}:${n}`, async () => {
    const i = await fetch(`${rr(e)}/setting-image/${t}?kind=${n}`, {
      headers: { Accept: "application/json" },
      credentials: "same-origin"
    });
    return i.ok && (await i.json()).image || null;
  });
}
const Fi = /* @__PURE__ */ new Map();
async function ls(e, t, n = !1) {
  const i = `${t}:${n ? 1 : 0}`;
  if (Fi.has(i)) return Fi.get(i);
  const a = await fetch(`${rr(e)}/thesession-preview/${t}${n ? "?full=1" : ""}`, {
    headers: { Accept: "application/json" },
    credentials: "same-origin"
  }), s = await a.json().catch(() => ({}));
  if (!a.ok || !s.success) throw new Error(s.error || `thesession preview failed: ${a.status}`);
  return Fi.set(i, s), s;
}
function tu(e, t, n) {
  return Wa(t, async () => {
    const i = await fetch(`${rr(e)}/render-abc`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify(n)
    });
    return i.ok && (await i.json()).image || null;
  });
}
var nu = /* @__PURE__ */ E('<img class="incipit-img" alt="notation"/>'), ru = /* @__PURE__ */ E('<span class="deep-noabc">♪ rendering…</span>'), iu = /* @__PURE__ */ E('<span class="deep-noabc">♪</span>'), su = /* @__PURE__ */ E('<span class="deep-noabc">♪ no notation</span>'), au = /* @__PURE__ */ E('<div class="incipit"><!></div>');
function Xa(e, t) {
  tr(t, !0);
  let n = it(t, "image", 3, null), i = it(t, "canRender", 3, !1), a = /* @__PURE__ */ I(Ge(
    st(() => n())
    // initial cached image; the lazy fetch fills it in if absent
  )), s = /* @__PURE__ */ I(!1), l, o = /* @__PURE__ */ I(!1);
  Vt(() => {
    if (!l || r(o)) return;
    const p = new IntersectionObserver(
      (b) => {
        b[0].isIntersecting && (c(o, !0), p.disconnect());
      },
      { rootMargin: "150px" }
    );
    return p.observe(l), () => p.disconnect();
  }), Vt(() => {
    r(a) || !r(o) || !i() || !t.tuneId || (c(s, !0), $o(t.config, t.tuneId).then((p) => {
      p && c(a, p, !0);
    }).finally(() => {
      c(s, !1);
    }));
  });
  var u = au(), f = g(u);
  {
    var h = (p) => {
      var b = nu();
      G(() => Ie(b, "src", `data:image/png;base64,${r(a)}`)), x(p, b);
    }, w = (p) => {
      var b = ru();
      x(p, b);
    }, _ = (p) => {
      var b = iu();
      x(p, b);
    }, y = (p) => {
      var b = su();
      x(p, b);
    };
    F(f, (p) => {
      r(a) ? p(h) : r(s) ? p(w, 1) : i() ? p(_, 2) : p(y, -1);
    });
  }
  xr(u, (p) => l = p, () => l), x(e, u), nr();
}
function lu(e) {
  const t = e - 1;
  return t * t * t + 1;
}
function Ns(e) {
  const t = typeof e == "string" && e.match(/^\s*(-?[\d.]+)([^\s]*)\s*$/);
  return t ? [parseFloat(t[1]), t[2] || "px"] : [
    /** @type {number} */
    e,
    "px"
  ];
}
function ou(e, { delay: t = 0, duration: n = 400, easing: i = lu, x: a = 0, y: s = 0, opacity: l = 0 } = {}) {
  const o = getComputedStyle(e), u = +o.opacity, f = o.transform === "none" ? "" : o.transform, h = u * (1 - l), [w, _] = Ns(a), [y, p] = Ns(s);
  return {
    delay: t,
    duration: n,
    easing: i,
    css: (b, m) => `
			transform: ${f} translate(${(1 - b) * w}${_}, ${(1 - b) * y}${p});
			opacity: ${u - h * m}`
  };
}
var uu = /* @__PURE__ */ E('<div class="pv-skel" style="width:60%"></div> <div class="pv-skel" style="height:96px"></div> <div class="pv-skel" style="width:40%"></div>', 1), cu = /* @__PURE__ */ E('<p class="pv-fail"> </p>'), fu = /* @__PURE__ */ E('<span class="pv-fact-here"> </span>'), du = /* @__PURE__ */ E('<span class="pv-fact-none">Not played here yet</span>'), vu = /* @__PURE__ */ E('<span class="deep-badge star">★ on your list</span>'), _u = /* @__PURE__ */ E('<button class="pv-more">More …</button>'), hu = /* @__PURE__ */ E("<div> </div> <!>", 1), pu = /* @__PURE__ */ E('<span class="pv-sesset">· ★ this session’s</span>'), gu = /* @__PURE__ */ E('<span class="pv-spin" aria-hidden="true"></span>'), mu = /* @__PURE__ */ E('<div class="pv-setnav"><button class="pv-step" aria-label="Previous setting">‹</button> <span class="pv-setlabel"> <!></span> <button class="pv-step" aria-label="Next setting"><!></button></div>'), yu = /* @__PURE__ */ E('<button class="nb-abc"> </button>'), js = /* @__PURE__ */ E('<div class="nb-pend"><span class="deep-noabc">♪ no notation</span></div>'), bu = /* @__PURE__ */ E('<button class="nb-imgbtn"><img/></button>'), wu = /* @__PURE__ */ E('<button class="nb-pend"><span class="spinner"></span> rendering notation…</button>'), ku = /* @__PURE__ */ E('<button class="nb-pend"><span class="deep-noabc">♪ no notation image</span></button>'), xu = /* @__PURE__ */ E('<div class="pv-import-note">Not in the library yet — it will be imported from thesession.org when you add it.</div>'), Su = /* @__PURE__ */ E('<div class="pv-facts"><!> <span class="pv-fact-pop"><b> </b> tunebooks</span> <!></div> <div><!></div> <!> <div class="nb"><!> <div class="nb-foot"><button>notes</button> <button>abc</button> <a class="nb-ext" target="_blank" rel="noopener">thesession</a></div></div> <!>', 1), Tu = /* @__PURE__ */ E('<div class="pv"><div class="pv-head"><button class="pv-back">‹ Results</button> <span class="pv-count"> </span> <button class="pv-step" aria-label="Previous result">‹</button> <button class="pv-step" aria-label="Next result">›</button></div> <div class="pv-body"><div class="pv-name"> <span class="pv-type"> </span></div> <!></div> <div class="pv-foot"><button class="pv-action"> </button></div></div>');
function Fs(e, t) {
  tr(t, !0);
  let n = it(
    t,
    "index",
    3,
    0
    // start position
  ), i = it(
    t,
    "initialSettingId",
    3,
    null
    // a pasted URL's ?setting=/#setting deep link — land the pager there (counts as CHOSEN)
  ), a = it(t, "actionLabel", 3, "＋ Log This Tune"), s = /* @__PURE__ */ I(Ge(
    st(() => n())
    // seed once; stepping is internal
  )), l = /* @__PURE__ */ I(
    "notes"
    // 'notes' | 'abc'
  ), o = /* @__PURE__ */ I(
    "incipit"
    // 'incipit' | 'full' (flips on content click)
  ), u = /* @__PURE__ */ I(
    0
    // which setting the pager is on
  ), f = !1, h = st(() => i()), w = /* @__PURE__ */ I(
    null
    // tune-preview / thesession-preview response
  ), _ = /* @__PURE__ */ I(!0), y = /* @__PURE__ */ I(!1), p = /* @__PURE__ */ I(null), b = /* @__PURE__ */ I(!1), m = /* @__PURE__ */ I(
    !1
    // thesession settings backfill in flight (the › slot hints it)
  ), T = /* @__PURE__ */ I(
    !1
    // "Also known as" is clamped to 3 lines until expanded
  ), V = /* @__PURE__ */ I(
    !1
    // does the collapsed block actually overflow?
  ), P = /* @__PURE__ */ I(null), C = 0, K = 0;
  Vt(() => {
    var M;
    (M = r(w)) == null || M.aliases, !(!r(P) || r(T)) && c(V, r(P).scrollHeight > r(P).clientHeight + 1);
  });
  const W = /* @__PURE__ */ Ae(() => t.items[r(s)]), R = /* @__PURE__ */ Ae(() => {
    var M;
    return ((M = r(w)) == null ? void 0 : M.settings) || [];
  }), Q = /* @__PURE__ */ Ae(() => r(R)[r(u)] || null), _e = /* @__PURE__ */ Ae(() => {
    var M, B, he;
    return r(w) ? r(w).is_local === !1 : !!((M = r(W)) != null && M.remote) && !((he = (B = r(W)) == null ? void 0 : B.r) != null && he.is_local);
  }), se = /* @__PURE__ */ Ae(() => {
    var he, Be, ge, Pe;
    const M = `https://thesession.org/tunes/${((he = r(w)) == null ? void 0 : he.tune_id) ?? ((ge = (Be = r(W)) == null ? void 0 : Be.r) == null ? void 0 : ge.tune_id) ?? ""}`, B = (Pe = r(Q)) == null ? void 0 : Pe.setting_id;
    return B != null ? `${M}?setting=${B}#setting${B}` : M;
  });
  function Se(M) {
    c(s, M, !0), c(l, "notes"), c(o, "incipit"), c(u, 0), f = !1, c(T, !1), c(V, !1), c(w, null), c(y, !1), c(_, !0), c(p, null), c(b, !1);
    const B = t.items[M], he = ++C;
    (B.remote && !B.r.is_local ? ls(t.config, B.r.tune_id).then((ge) => ge.is_local ? as(t.config, ge.tune_id) : ge) : as(t.config, B.r.tune_id)).then((ge) => {
      if (he !== C) return;
      c(w, ge, !0);
      let Pe = -1;
      h != null && (Pe = (ge.settings || []).findIndex((yt) => yt.setting_id === h), Pe >= 0 && (f = !0, h = null)), Pe < 0 && ge.session_setting_id != null && (Pe = (ge.settings || []).findIndex((yt) => yt.setting_id === ge.session_setting_id)), Pe > 0 && c(u, Pe, !0), c(_, !1), be(), ge.is_local !== !1 && Ue(ge, he);
    }).catch(() => {
      he === C && (c(y, !0), c(_, !1));
    });
  }
  async function Ue(M, B) {
    var Lt;
    c(m, !0);
    let he;
    try {
      he = await ls(t.config, M.tune_id, !0);
    } catch {
      B === C && c(m, !1);
      return;
    }
    if (B !== C || (c(m, !1), !((Lt = he == null ? void 0 : he.settings) != null && Lt.length))) return;
    const Be = new Set((M.settings || []).map((Je) => Je.setting_id)), ge = he.settings.filter((Je) => !Be.has(Je.setting_id)).map((Je) => ({ ...Je, remote: !0 })), Pe = [...M.aliases || []];
    for (const Je of he.aliases || []) Pe.includes(Je) || Pe.push(Je);
    if (!ge.length && Pe.length === (M.aliases || []).length) return;
    const yt = !(M.settings || []).length;
    if (c(w, { ...M, settings: [...M.settings || [], ...ge], aliases: Pe }, !0), h != null && !f) {
      const Je = r(w).settings.findIndex((Jt) => Jt.setting_id === h);
      if (h = null, Je >= 0) {
        c(u, Je, !0), f = !0, c(o, "incipit"), r(l) === "notes" && be();
        return;
      }
    }
    h = null, yt && ge.length && r(
      l
      // was "no notation"; now renderable
    ) === "notes" && be();
  }
  function be() {
    var ge;
    const M = r(w), B = (ge = M == null ? void 0 : M.settings) == null ? void 0 : ge[r(u)];
    if (!M || !B || r(l) !== "notes") return;
    if (r(o) === "incipit" && B.incipit_image) {
      c(p, B.incipit_image, !0), c(b, !1);
      return;
    }
    const he = ++K;
    c(p, null), c(b, !0), (B.remote || M.is_local === !1 ? tu(t.config, `ts:${M.tune_id}:${B.setting_id ?? r(u)}:${r(o)}`, {
      abc: B.abc,
      key: B.key,
      tune_type: M.tune_type,
      kind: r(o)
    }) : eu(t.config, B.setting_id, r(o))).then((Pe) => {
      he === K && (c(p, Pe, !0), c(b, !1));
    });
  }
  function De(M) {
    r(l) !== M && (c(l, M, !0), M === "notes" && be());
  }
  function Oe() {
    c(o, r(o) === "incipit" ? "full" : "incipit", !0), r(l) === "notes" && be();
  }
  function Re(M) {
    const B = r(u) + M;
    !r(R).length || B < 0 || B >= r(R).length || (c(u, B), f = !0, c(o, "incipit"), r(l) === "notes" && be());
  }
  function We(M) {
    const B = r(s) + M;
    B < 0 || B >= t.items.length || (h = null, Se(B));
  }
  function pt() {
    var B;
    const M = f && ((B = r(Q)) == null ? void 0 : B.setting_id) != null ? r(Q).setting_id : null;
    t.onAction(t.items[r(s)], r(w), M);
  }
  function He(M) {
    if (M.key === "Escape")
      M.preventDefault(), M.stopPropagation(), t.onClose();
    else if (M.key === "ArrowLeft")
      M.preventDefault(), We(-1);
    else if (M.key === "ArrowRight")
      M.preventDefault(), We(1);
    else if (M.key === "Enter") {
      if (M.target.closest("button, a, input, textarea, select")) return;
      M.preventDefault(), pt();
    }
  }
  Se(st(() => r(s)));
  var gt = Tu();
  So("keydown", $i, He);
  var we = g(gt), Me = g(we), ut = S(Me, 2), H = g(ut), U = S(ut, 2), J = S(U, 2), Ce = S(we, 2), qe = g(Ce), Qe = g(qe), xt = S(Qe), Nt = g(xt), An = S(qe, 2);
  {
    var Mt = (M) => {
      var B = uu();
      x(M, B);
    }, sn = (M) => {
      var B = cu(), he = g(B);
      G(() => {
        var Be;
        return Z(he, `Couldn’t load tune details${(Be = r(W)) != null && Be.remote ? " from thesession.org" : ""}. Check your connection and try again.`);
      }), x(M, B);
    }, Kt = (M) => {
      var B = Su(), he = Ke(B), Be = g(he);
      {
        var ge = (q) => {
          var j = fu(), oe = g(j);
          G((je) => Z(oe, `♪ Played here ${r(w).played_here ?? ""}×${je ?? ""}`), [
            () => {
              var je;
              return (je = r(w).dates) != null && je.length ? ` — last: ${r(w).dates.join(", ")}` : "";
            }
          ]), x(q, j);
        }, Pe = (q) => {
          var j = du();
          x(q, j);
        };
        F(Be, (q) => {
          r(w).played_here ? q(ge) : q(Pe, -1);
        });
      }
      var yt = S(Be, 2), Lt = g(yt), Je = g(Lt), Jt = S(yt, 2);
      {
        var jn = (q) => {
          var j = vu();
          x(q, j);
        };
        F(Jt, (q) => {
          var j, oe;
          (oe = (j = r(W)) == null ? void 0 : j.r) != null && oe.on_list && q(jn);
        });
      }
      var pn = S(he, 2);
      let In;
      var Mn = g(pn);
      {
        var k = (q) => {
          var j = hu(), oe = Ke(j);
          let je;
          var mt = g(oe);
          xr(oe, (et) => c(P, et), () => r(P));
          var lt = S(oe, 2);
          {
            var $e = (et) => {
              var Zt = _u();
              D("click", Zt, () => c(T, !0)), x(et, Zt);
            };
            F(lt, (et) => {
              r(V) && !r(T) && et($e);
            });
          }
          G(
            (et) => {
              je = Fe(oe, 1, "pv-aliases", null, je, { clamped: !r(T) }), Z(mt, `Also known as: ${et ?? ""}`);
            },
            [() => r(w).aliases.join(", ")]
          ), x(q, j);
        };
        F(Mn, (q) => {
          var j;
          (j = r(w).aliases) != null && j.length && q(k);
        });
      }
      var O = S(pn, 2);
      {
        var ze = (q) => {
          var j = mu(), oe = g(j), je = S(oe, 2), mt = g(je), lt = S(mt);
          {
            var $e = (ee) => {
              var te = pu();
              x(ee, te);
            };
            F(lt, (ee) => {
              var te;
              ((te = r(Q)) == null ? void 0 : te.setting_id) != null && r(Q).setting_id === r(w).session_setting_id && ee($e);
            });
          }
          var et = S(je, 2), Zt = g(et);
          {
            var L = (ee) => {
              var te = gu();
              x(ee, te);
            }, X = (ee) => {
              var te = Ba("›");
              x(ee, te);
            };
            F(Zt, (ee) => {
              r(m) && r(u) >= r(R).length - 1 ? ee(L) : ee(X, -1);
            });
          }
          G(() => {
            var ee, te;
            oe.disabled = r(u) === 0, Z(mt, `Setting ${r(u) + 1} of ${r(R).length ?? ""}${((ee = r(Q)) == null ? void 0 : ee.setting_id) != null ? ` · #${r(Q).setting_id}` : ""}${(te = r(Q)) != null && te.key ? ` · ${r(Q).key}` : ""}`), et.disabled = r(u) >= r(R).length - 1;
          }), D("click", oe, () => Re(-1)), D("click", et, () => Re(1)), x(q, j);
        };
        F(O, (q) => {
          r(R).length && q(ze);
        });
      }
      var Ye = S(O, 2), Ze = g(Ye);
      {
        var Ft = (q) => {
          var j = cn(), oe = Ke(j);
          {
            var je = (lt) => {
              var $e = yu(), et = g($e);
              G(() => {
                Ie($e, "title", `Click to show ${r(o) === "full" ? "the incipit" : "the full tune"}`), Z(et, r(o) === "full" ? r(Q).abc : r(Q).incipit_abc);
              }), D("click", $e, Oe), x(lt, $e);
            }, mt = (lt) => {
              var $e = js();
              x(lt, $e);
            };
            F(oe, (lt) => {
              r(Q) ? lt(je) : lt(mt, -1);
            });
          }
          x(q, j);
        }, v = (q) => {
          var j = bu(), oe = g(j);
          G(() => {
            Ie(j, "title", `Click to show ${r(o) === "full" ? "the incipit" : "the full tune"}`), Ie(oe, "src", `data:image/png;base64,${r(p)}`), Ie(oe, "alt", `notation (${r(o) ?? ""})`);
          }), D("click", j, Oe), x(q, j);
        }, A = (q) => {
          var j = wu();
          G(() => Ie(j, "title", `Click to show ${r(o) === "full" ? "the incipit" : "the full tune"}`)), D("click", j, Oe), x(q, j);
        }, N = (q) => {
          var j = ku();
          G(() => Ie(j, "title", `Click to show ${r(o) === "full" ? "the incipit" : "the full tune"}`)), D("click", j, Oe), x(q, j);
        }, z = (q) => {
          var j = js();
          x(q, j);
        };
        F(Ze, (q) => {
          r(l) === "abc" ? q(Ft) : r(p) ? q(v, 1) : r(b) ? q(A, 2) : r(Q) ? q(N, 3) : q(z, -1);
        });
      }
      var me = S(Ze, 2), le = g(me);
      let ke;
      var Ne = S(le, 2);
      let ye;
      var Y = S(Ne, 2), ne = S(Ye, 2);
      {
        var fe = (q) => {
          var j = xu();
          x(q, j);
        };
        F(ne, (q) => {
          r(_e) && q(fe);
        });
      }
      G(() => {
        Z(Je, r(w).tunebook_count ?? 0), In = Fe(pn, 1, "pv-aliaswrap", null, In, { fixed: !r(T) }), ke = Fe(le, 1, "nb-tab", null, ke, { active: r(l) === "notes" }), ye = Fe(Ne, 1, "nb-tab", null, ye, { active: r(l) === "abc" }), Ne.disabled = !r(Q), Ie(Y, "href", r(se));
      }), D("click", le, () => De("notes")), D("click", Ne, () => De("abc")), x(M, B);
    };
    F(An, (M) => {
      r(_) ? M(Mt) : r(y) ? M(sn, 1) : M(Kt, -1);
    });
  }
  var Qt = S(Ce, 2), jt = g(Qt), hn = g(jt);
  G(() => {
    var M, B, he, Be, ge, Pe;
    Z(H, `${r(s) + 1} of ${t.items.length ?? ""}`), U.disabled = r(s) === 0, J.disabled = r(s) >= t.items.length - 1, Z(Qe, ((M = r(w)) == null ? void 0 : M.name) ?? ((he = (B = r(W)) == null ? void 0 : B.r) == null ? void 0 : he.name) ?? ""), Z(Nt, ((Be = r(w)) == null ? void 0 : Be.tune_type) ?? ((Pe = (ge = r(W)) == null ? void 0 : ge.r) == null ? void 0 : Pe.tune_type) ?? ""), Z(hn, a());
  }), D("click", Me, function(...M) {
    var B;
    (B = t.onClose) == null || B.apply(this, M);
  }), D("click", U, () => We(-1)), D("click", J, () => We(1)), D("click", jt, pt), Uo(1, gt, () => ou, () => ({ x: 32, duration: 180 })), x(e, gt), nr();
}
Xr(["click"]);
function Us(e) {
  return e && (/(s|z|ch|sh|x)$/i.test(e) ? e + "es" : e + "s");
}
function Eu(e) {
  if (e == null) return null;
  const t = String(e).trim(), n = t.match(/thesession\.org\/tunes\/(\d+)/);
  return n ? parseInt(n[1], 10) : /^\d+$/.test(t) ? parseInt(t, 10) : null;
}
function Au(e) {
  if (e == null) return null;
  const t = String(e).trim();
  if (!t.includes("thesession.org")) return null;
  const n = t.match(/[?&]setting=(\d+)/);
  if (n) return parseInt(n[1], 10);
  const i = t.match(/#setting(\d+)/);
  return i ? parseInt(i[1], 10) : null;
}
function Iu(e, t, n) {
  const i = e.length;
  if (!i) return null;
  if (n < 0) {
    const a = t == null ? i - 1 : Math.max(0, t - 1);
    return { pos: a, value: e[a] };
  }
  return t == null ? null : t >= i - 1 ? { pos: null, value: "" } : { pos: t + 1, value: e[t + 1] };
}
var Mu = /* @__PURE__ */ E('<div class="deep-head"><span class="deep-title"> </span> <button class="deep-done">Done</button></div>'), Lu = /* @__PURE__ */ E('<button class="deep-clear" title="Clear search" aria-label="Clear search">×</button>'), Cu = /* @__PURE__ */ E("<option> </option>"), Pu = /* @__PURE__ */ E('<div class="deep-filter-panel"><div class="deep-filter-modes"><button>By name</button> <button>By ABC</button></div> <select class="deep-type-select" aria-label="Tune type"><option>Any tune type</option><!></select></div>'), qs = /* @__PURE__ */ E('<button class="filter-pill"> <span class="x">✕</span></button>'), Du = /* @__PURE__ */ E('<div class="deep-filters"><!> <!></div>'), Ou = /* @__PURE__ */ E('<button class="deep-asis deep-asis-remote"> </button>'), Ru = /* @__PURE__ */ E('<button class="deep-asis"> </button>'), Nu = /* @__PURE__ */ E('<p class="deep-empty">Searching…</p>'), ju = /* @__PURE__ */ E('<p class="deep-empty">Search the tune catalog by name or ABC notes.</p>'), Bs = /* @__PURE__ */ E('<p class="deep-empty"> </p>'), Fu = /* @__PURE__ */ E('<span class="deep-badge">♪ notation</span>'), zs = /* @__PURE__ */ E('<span class="deep-badge star">★ on your list</span>'), Uu = /* @__PURE__ */ E('<span class="deep-badge">in this session</span>'), qu = /* @__PURE__ */ E('<span class="deep-badge"> </span>'), Bu = /* @__PURE__ */ E('<div role="option"><button class="deep-card-body"><div class="deep-card-head"><span class="deep-name"> </span> <span class="deep-type"> </span></div> <div class="deep-staff"><!></div> <div class="deep-meta"><!> <!> <!> <!> <span class="deep-books"> </span></div></button> <button class="deep-quick" title="Add without previewing">＋</button></div>'), zu = /* @__PURE__ */ E('<p class="deep-empty">Searching thesession.org…</p>'), Hu = /* @__PURE__ */ E('<span class="deep-alias"> </span>'), Yu = /* @__PURE__ */ E('<span class="deep-badge">already in library</span>'), Vu = /* @__PURE__ */ E('<span class="deep-badge star">★ in this session</span>'), Wu = /* @__PURE__ */ E('<div><button class="deep-card-body"><div class="deep-card-head"><span class="deep-name"> </span> <span class="deep-type"> </span></div> <div class="deep-meta"><!> <!> <!> <!></div></button> <button class="deep-quick" title="Add without previewing">＋</button></div>'), Xu = /* @__PURE__ */ E('<p class="deep-paste-error"> </p>'), Gu = /* @__PURE__ */ E('<div class="deep-remote"><div class="deep-remote-head">From thesession.org</div> <!> <div class="deep-paste"><input class="deep-paste-field" placeholder="Have a link? Paste a thesession.org URL or tune ID"/> <button class="deep-paste-btn">Add</button></div> <!></div>'), Ku = /* @__PURE__ */ E('<!> <div class="deep-field-row"><div class="deep-field-wrap"><input class="deep-field" role="combobox" aria-controls="deep-results-list"/> <!></div> <button title="Search filters" aria-label="Search filters"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="4" y1="21" x2="4" y2="14"></line><line x1="4" y1="10" x2="4" y2="3"></line><line x1="12" y1="21" x2="12" y2="12"></line><line x1="12" y1="8" x2="12" y2="3"></line><line x1="20" y1="21" x2="20" y2="16"></line><line x1="20" y1="12" x2="20" y2="3"></line><line x1="1" y1="14" x2="7" y2="14"></line><line x1="9" y1="8" x2="15" y2="8"></line><line x1="17" y1="16" x2="23" y2="16"></line></svg></button></div> <!> <!> <!> <div class="deep-results" id="deep-results-list" role="listbox"><!></div> <!>', 1);
function Qu(e, t) {
  tr(t, !0);
  let n = it(
    t,
    "initialQuery",
    3,
    ""
    // seed: the composer text (modal) or '' (pane)
  ), i = it(
    t,
    "initialPreview",
    3,
    null
    // {items, index}: open JUMPED into a preview (the composer's 🔍) — Back lands on the search
  ), a = it(
    t,
    "preferType",
    3,
    null
    // the cursor set's type — a soft ranking preference, not a filter
  ), s = it(
    t,
    "displayStatus",
    3,
    "live"
    // gates the remote search (online-only)
  ), l = it(
    t,
    "variant",
    3,
    "pane"
    // 'modal' shows the Done header + autofocuses the field
  ), o = it(
    t,
    "title",
    3,
    "Find a tune"
    // modal header text (the add pane says "Search for a tune")
  ), u = it(
    t,
    "allowAsIs",
    3,
    !0
    // "log as-is (unlinked)" escape — off for My Tunes (needs a catalog tune)
  ), f = it(
    t,
    "actionLabel",
    3,
    "＋ Log This Tune"
    // the preview's primary action (context-specific verb)
  ), h = it(
    t,
    "dimOnList",
    3,
    !1
    // dim results already on the person's list (My Tunes add pane)
  ), w = it(
    t,
    "dimInSession",
    3,
    !1
    // dim results already in the session's repertoire (session-tunes add pane)
  ), _ = it(t, "history", 19, () => []), y = it(
    t,
    "onRemember",
    3,
    () => {
    }
    // record a used query into the shared history
  ), p = it(t, "onClose", 3, () => {
  });
  const b = [
    "Reel",
    "Jig",
    "Slip Jig",
    "Hornpipe",
    "Polka",
    "Slide",
    "Waltz",
    "Barndance",
    "Mazurka",
    "March",
    "Strathspey",
    "Three-Two"
  ];
  let m = /* @__PURE__ */ I(Ge(
    st(() => n())
    // seed once; the field owns it after
  )), T = /* @__PURE__ */ I(
    null
    // hard tune-type filter (the popout)
  ), V = /* @__PURE__ */ I(
    "mixed"
    // 'mixed' (name + ABC) | 'name' | 'abc' search mode
  ), P = /* @__PURE__ */ I(
    !1
    // type-filter popout visible
  ), C = /* @__PURE__ */ I(Ge([])), K = /* @__PURE__ */ I(!1), W = null, R = 0, Q = /* @__PURE__ */ I(
    -1
    // keyboard-highlighted index into deepResults (-1 = none)
  ), _e = /* @__PURE__ */ I(
    null
    // recall cursor into `history` (null = live draft, not navigating)
  ), se = /* @__PURE__ */ I(Ge(
    []
    // remote hits for the current query, already deduped
  )), Se = /* @__PURE__ */ I(!1), Ue = /* @__PURE__ */ I(
    !1
    // has the user run a remote search for this query yet?
  ), be = /* @__PURE__ */ I(
    ""
    // the "paste a URL / tune ID" field inside the remote section
  ), De = /* @__PURE__ */ I(""), Oe = /* @__PURE__ */ I(
    null
    // index into previewItems, or null (search showing)
  ), Re = /* @__PURE__ */ I(Ge(st(() => i()))), We = /* @__PURE__ */ I(
    null
    // the .deep-results scroller (to restore scroll on back)
  ), pt = 0, He = /* @__PURE__ */ I(!!st(() => i()));
  const gt = /* @__PURE__ */ Ae(() => [
    ...r(C).map((k) => ({ r: k, remote: !1 })),
    ...r(se).map((k) => ({ r: k, remote: !0 }))
  ]);
  function we(k) {
    var O;
    c(He, !0), pt = ((O = r(We)) == null ? void 0 : O.scrollTop) ?? 0, c(Oe, k, !0);
  }
  async function Me() {
    c(Oe, null), await ja(), r(We) && (r(We).scrollTop = pt);
  }
  function ut(k, O, ze = null) {
    const Ye = (O == null ? void 0 : O.name) ?? k.r.name, Ze = (O == null ? void 0 : O.tune_type) ?? k.r.tune_type, Ft = ze != null ? { setting_id: ze } : {};
    return k.remote ? O && O.is_local !== !1 ? jt({
      ...k.r,
      tune_id: O.tune_id ?? k.r.tune_id,
      name: Ye,
      tune_type: Ze,
      ...Ft
    }) : Be({ ...k.r, name: Ye, tune_type: Ze, ...Ft }) : jt({ ...k.r, name: Ye, tune_type: Ze, ...Ft });
  }
  function H(k, O) {
    O && k.focus();
  }
  function U() {
    W && clearTimeout(W), c(K, !0), c(
      Q,
      -1
      // a new query invalidates the keyboard highlight
    ), B(), W = setTimeout(
      async () => {
        const k = ++R, O = await Jo(t.config, r(m).trim(), r(T), a(), r(V));
        k === R && (c(C, O, !0), c(K, !1));
      },
      160
    );
  }
  Vt(() => {
    r(Q) >= r(C).length && c(Q, -1);
  });
  function J(k) {
    const O = r(C).length;
    return O ? (c(
      Q,
      r(Q) < 0 ? k > 0 ? 0 : O - 1 : Math.max(0, Math.min(O - 1, r(Q) + k)),
      !0
    ), queueMicrotask(() => {
      var ze;
      return (ze = document.querySelector(".deep-results .deep-card.hl")) == null ? void 0 : ze.scrollIntoView({ block: "nearest" });
    }), !0) : !1;
  }
  let Ce = null;
  function qe() {
    c(
      _e,
      null
      // typing leaves history-recall mode
    ), Ce && clearTimeout(Ce), Ce = setTimeout(() => y()(r(m)), 800), U();
  }
  function Qe(k) {
    const O = Iu(_(), r(_e), k);
    return O ? (c(_e, O.pos, !0), c(m, O.value, !0), O.value.trim() ? U() : (c(
      C,
      [],
      // back to the empty draft
      !0
    ), c(K, !1), R++), !0) : !1;
  }
  const xt = () => y()(r(m));
  function Nt(k) {
    const O = r(V) === k ? "mixed" : k;
    r(V) !== O && (c(V, O, !0), U());
  }
  const An = () => {
    c(P, !r(P));
  };
  function Mt(k) {
    c(T, r(T) === k ? null : k, !0), c(P, !1), U();
  }
  function sn(k) {
    c(T, k || null, !0), U();
  }
  function Kt() {
    W && (clearTimeout(W), W = null), R++, c(m, ""), c(C, [], !0), c(K, !1), c(Oe, null), c(Re, null), B();
  }
  function Qt(k) {
    return xt(), c(_e, null), k === !1 || (c(Oe, null), c(Re, null), l() === "pane" && Kt()), k;
  }
  function jt(k) {
    const O = { tune_id: k.tune_id, name: k.name, tune_type: k.tune_type };
    return k.setting_id != null && (O.setting_id = k.setting_id), Qt(t.onAdd(O, k.name, k));
  }
  function hn() {
    const k = r(m).trim();
    k && Qt(t.onAdd({ name: k }, k));
  }
  function M(k) {
    if (!(r(
      Oe
      // the preview owns the keys while it's open
    ) != null || r(Re))) {
      if (k.key === "ArrowDown" || k.key === "ArrowUp") {
        const O = k.key === "ArrowDown" ? 1 : -1;
        r(
          _e
          // cycling history
        ) != null ? Qe(O) && k.preventDefault() : O < 0 && !r(
          m
          // empty box: recall
        ).trim() ? Qe(-1) && k.preventDefault() : r(
          C
          // result nav
        ).length && J(O) && k.preventDefault();
      } else if (k.key === "Escape")
        l() === "modal" && (k.preventDefault(), p()());
      else if (k.key === "Enter") {
        k.preventDefault();
        const O = r(Q) >= 0 && r(C)[r(Q)] ? r(Q) : r(C).length ? 0 : -1;
        O >= 0 ? k.metaKey || k.ctrlKey ? jt(r(C)[O]) : we(O) : u() && r(_e) == null && r(m).trim() && hn();
      }
    }
  }
  function B() {
    c(se, [], !0), c(Se, !1), c(Ue, !1), c(be, ""), c(De, "");
  }
  async function he() {
    const k = r(m).trim();
    if (!k || r(Se) || s() === "offline") return;
    c(Se, !0), c(Ue, !0);
    const O = new Set(r(C).map((Ye) => Ye.tune_id)), ze = await Zo(t.config, k, r(T));
    c(se, ze.filter((Ye) => !O.has(Ye.tune_id)), !0), c(Se, !1);
  }
  function Be(k) {
    const O = {
      thesession_id: k.tune_id,
      tune_id: k.tune_id,
      name: k.name,
      tune_type: k.tune_type
    };
    return k.setting_id != null && (O.setting_id = k.setting_id), Qt(t.onAdd(O, k.name, k));
  }
  function ge() {
    const k = r(be), O = Eu(k);
    if (O == null) {
      c(De, "Enter a thesession.org tune URL or numeric ID.");
      return;
    }
    c(He, !0), c(
      Re,
      {
        items: [
          {
            r: { tune_id: O, name: `#${O}`, tune_type: null },
            remote: !0
          }
        ],
        index: 0,
        settingId: Au(k)
      },
      !0
    ), Lt(O);
  }
  function Pe(k) {
    c(Oe, null), c(Re, null), c(m, k, !0), c(_e, null), U();
  }
  function yt(k) {
    c(He, !0), c(Re, k, !0), (k == null ? void 0 : k.reseedId) != null && Lt(k.reseedId);
  }
  async function Lt(k) {
    var O;
    try {
      const ze = await ls(t.config, k), Ye = ze.is_local ? await as(t.config, ze.tune_id) : ze, Ze = ((ze.is_local && ((O = Ye.aliases) != null && O.length) ? Ye.aliases[0] : "") || Ye.name || "").trim();
      Ze && (c(m, Ze, !0), c(_e, null), U());
    } catch {
    }
  }
  st(() => l() === "modal" || n().trim()) && U(), st(() => {
    var k;
    return ((k = i()) == null ? void 0 : k.reseedId) != null;
  }) && Lt(st(() => i().reseedId)), Ko(() => {
    W && clearTimeout(W), Ce && clearTimeout(Ce), R++;
  });
  var Je = { reset: Kt, seed: Pe, openExternalPreview: yt }, Jt = cn(), jn = Ke(Jt);
  {
    var pn = (k) => {
      var O = cn(), ze = Ke(O);
      Co(ze, () => r(Re), (Ye) => {
        {
          let Ze = /* @__PURE__ */ Ae(() => r(Re).settingId ?? null);
          Fs(Ye, {
            get config() {
              return t.config;
            },
            get items() {
              return r(Re).items;
            },
            get index() {
              return r(Re).index;
            },
            get initialSettingId() {
              return r(Ze);
            },
            get actionLabel() {
              return f();
            },
            onAction: ut,
            onClose: () => {
              c(Re, null);
            }
          });
        }
      }), x(k, O);
    }, In = (k) => {
      Fs(k, {
        get config() {
          return t.config;
        },
        get items() {
          return r(gt);
        },
        get index() {
          return r(Oe);
        },
        get actionLabel() {
          return f();
        },
        onAction: ut,
        onClose: Me
      });
    }, Mn = (k) => {
      var O = Ku(), ze = Ke(O);
      {
        var Ye = (L) => {
          var X = Mu(), ee = g(X), te = g(ee), ue = S(ee, 2);
          G(() => Z(te, o())), D("click", ue, function(...Te) {
            var ce;
            (ce = p()) == null || ce.apply(this, Te);
          }), x(L, X);
        };
        F(ze, (L) => {
          l() === "modal" && L(Ye);
        });
      }
      var Ze = S(ze, 2), Ft = g(Ze), v = g(Ft);
      ki(() => Ur(v, () => r(m), (L) => c(m, L))), qo(v, (L, X) => H == null ? void 0 : H(L, X), () => l() === "modal" && !r(He));
      var A = S(v, 2);
      {
        var N = (L) => {
          var X = Lu();
          D("click", X, Kt), x(L, X);
        };
        F(A, (L) => {
          r(m) && L(N);
        });
      }
      var z = S(Ft, 2);
      let me;
      var le = S(Ze, 2);
      {
        var ke = (L) => {
          var X = Pu(), ee = g(X), te = g(ee);
          let ue;
          var Te = S(te, 2);
          let ce;
          var re = S(ee, 2), pe = g(re);
          pe.value = pe.__value = "";
          var tt = S(pe);
          At(tt, 17, () => b, is, (Ee, nt) => {
            var Ut = Cu(), an = g(Ut), ft = {};
            G(
              (Er) => {
                Z(an, Er), ft !== (ft = r(nt)) && (Ut.value = (Ut.__value = r(nt)) ?? "");
              },
              [() => Us(r(nt))]
            ), x(Ee, Ut);
          });
          var ct;
          Ho(re), G(() => {
            ue = Fe(te, 1, "deep-tab", null, ue, { active: r(V) === "name" }), ce = Fe(Te, 1, "deep-tab", null, ce, { active: r(V) === "abc" }), ct !== (ct = r(T) ?? "") && (re.value = (re.__value = r(T) ?? "") ?? "", Va(re, r(T) ?? ""));
          }), D("click", te, () => Nt("name")), D("click", Te, () => Nt("abc")), D("change", re, (Ee) => sn(Ee.currentTarget.value)), x(L, X);
        }, Ne = (L) => {
          var X = Du(), ee = g(X);
          {
            var te = (ce) => {
              var re = qs(), pe = g(re);
              G(() => Z(pe, `${r(V) === "abc" ? "By ABC" : "By name"} `)), D("click", re, () => Nt(r(V))), x(ce, re);
            };
            F(ee, (ce) => {
              r(V) !== "mixed" && ce(te);
            });
          }
          var ue = S(ee, 2);
          {
            var Te = (ce) => {
              var re = qs(), pe = g(re);
              G((tt) => Z(pe, `${tt ?? ""} `), [() => Us(r(T))]), D("click", re, () => Mt(r(T))), x(ce, re);
            };
            F(ue, (ce) => {
              r(T) && ce(Te);
            });
          }
          x(L, X);
        };
        F(le, (L) => {
          r(P) ? L(ke) : (r(T) || r(V) !== "mixed") && L(Ne, 1);
        });
      }
      var ye = S(le, 2);
      {
        var Y = (L) => {
          var X = Ou(), ee = g(X);
          G((te) => Z(ee, `🔎 Search on thesession.org for “${te ?? ""}”`), [() => r(m).trim()]), D("click", X, he), x(L, X);
        }, ne = /* @__PURE__ */ Ae(() => r(m).trim() && s() !== "offline" && !r(Ue));
        F(ye, (L) => {
          r(ne) && L(Y);
        });
      }
      var fe = S(ye, 2);
      {
        var q = (L) => {
          var X = Ru(), ee = g(X);
          G((te) => Z(ee, `＋ Log “${te ?? ""}” as-is (unlinked)`), [() => r(m).trim()]), D("click", X, hn), x(L, X);
        }, j = /* @__PURE__ */ Ae(() => u() && r(V) !== "abc" && r(m).trim());
        F(fe, (L) => {
          r(j) && L(q);
        });
      }
      var oe = S(fe, 2), je = g(oe);
      {
        var mt = (L) => {
          var X = Nu();
          x(L, X);
        }, lt = (L) => {
          var X = cn(), ee = Ke(X);
          {
            var te = (ce) => {
              var re = ju();
              x(ce, re);
            }, ue = /* @__PURE__ */ Ae(() => l() === "pane" && !r(m).trim()), Te = (ce) => {
              var re = Bs(), pe = g(re);
              G((tt, ct) => Z(pe, `No${tt ?? ""} tunes match${ct ?? ""}.`), [
                () => r(T) ? ` ${r(T).toLowerCase()}` : "",
                () => r(m).trim() ? ` “${r(m).trim()}”` : ""
              ]), x(ce, re);
            };
            F(ee, (ce) => {
              r(ue) ? ce(te) : ce(Te, -1);
            });
          }
          x(L, X);
        }, $e = (L) => {
          var X = cn(), ee = Ke(X);
          At(ee, 19, () => r(C), (te) => te.tune_id, (te, ue, Te) => {
            var ce = Bu();
            let re;
            var pe = g(ce), tt = g(pe), ct = g(tt), Ee = g(ct), nt = S(ct, 2), Ut = g(nt), an = S(tt, 2), ft = g(an);
            Xa(ft, {
              get config() {
                return t.config;
              },
              get tuneId() {
                return r(ue).tune_id;
              },
              get image() {
                return r(ue).incipit_image;
              },
              get canRender() {
                return r(ue).can_render;
              }
            });
            var Er = S(an, 2), ir = g(Er);
            {
              var Gr = (ot) => {
                var ln = Fu();
                x(ot, ln);
              };
              F(ir, (ot) => {
                r(ue).abc_only && ot(Gr);
              });
            }
            var Fn = S(ir, 2);
            {
              var Kr = (ot) => {
                var ln = zs();
                x(ot, ln);
              };
              F(Fn, (ot) => {
                r(ue).on_list && ot(Kr);
              });
            }
            var Ar = S(Fn, 2);
            {
              var Ti = (ot) => {
                var ln = Uu();
                x(ot, ln);
              };
              F(Ar, (ot) => {
                r(ue).in_session && ot(Ti);
              });
            }
            var Qr = S(Ar, 2);
            {
              var Ei = (ot) => {
                var ln = qu(), $r = g(ln);
                G(() => Z($r, `played here ${r(ue).played_here ?? ""}×`)), x(ot, ln);
              };
              F(Qr, (ot) => {
                r(ue).played_here && ot(Ei);
              });
            }
            var Ai = S(Qr, 2), Jr = g(Ai), Zr = S(pe, 2);
            G(() => {
              Ie(ce, "id", `dres-${r(Te) ?? ""}`), re = Fe(ce, 1, "deep-card deep-card-split", null, re, {
                hl: r(Q) === r(Te),
                onlist: h() && r(ue).on_list || w() && r(ue).in_session
              }), Ie(ce, "aria-selected", r(Q) === r(Te)), Ie(pe, "aria-label", `Preview ${r(ue).name}`), Z(Ee, r(ue).name), Z(Ut, r(ue).tune_type || ""), Z(Jr, `${r(ue).tunebook_count ?? 0 ?? ""} tunebooks`), Ie(Zr, "aria-label", `Add ${r(ue).name} without previewing`);
            }), D("click", pe, () => we(r(Te))), D("click", Zr, () => jt(r(ue))), x(te, ce);
          }), x(L, X);
        };
        F(je, (L) => {
          r(K) && !r(C).length ? L(mt) : r(C).length ? L($e, -1) : L(lt, 1);
        });
      }
      xr(oe, (L) => c(We, L), () => r(We));
      var et = S(oe, 2);
      {
        var Zt = (L) => {
          var X = Gu(), ee = S(g(X), 2);
          {
            var te = (Ee) => {
              var nt = zu();
              x(Ee, nt);
            }, ue = (Ee) => {
              var nt = Bs(), Ut = g(nt);
              G((an) => Z(Ut, `No new tunes on thesession.org for “${an ?? ""}”.`), [() => r(m).trim()]), x(Ee, nt);
            }, Te = (Ee) => {
              var nt = cn(), Ut = Ke(nt);
              At(Ut, 19, () => r(se), (an) => an.tune_id, (an, ft, Er) => {
                var ir = Wu();
                let Gr;
                var Fn = g(ir), Kr = g(Fn), Ar = g(Kr), Ti = g(Ar), Qr = S(Ar, 2), Ei = g(Qr), Ai = S(Kr, 2), Jr = g(Ai);
                {
                  var Zr = (bt) => {
                    var Ln = Hu(), $a = g(Ln);
                    G(() => Z($a, `“${r(ft).alias ?? ""}”`)), x(bt, Ln);
                  };
                  F(Jr, (bt) => {
                    r(ft).alias && bt(Zr);
                  });
                }
                var ot = S(Jr, 2);
                {
                  var ln = (bt) => {
                    var Ln = Yu();
                    x(bt, Ln);
                  };
                  F(ot, (bt) => {
                    r(ft).is_local && bt(ln);
                  });
                }
                var $r = S(ot, 2);
                {
                  var Qa = (bt) => {
                    var Ln = Vu();
                    x(bt, Ln);
                  };
                  F($r, (bt) => {
                    r(ft).in_session && bt(Qa);
                  });
                }
                var Ja = S($r, 2);
                {
                  var Za = (bt) => {
                    var Ln = zs();
                    x(bt, Ln);
                  };
                  F(Ja, (bt) => {
                    r(ft).on_list && bt(Za);
                  });
                }
                var ys = S(Fn, 2);
                G(() => {
                  Gr = Fe(ir, 1, "deep-card deep-card-split deep-remote-card", null, Gr, {
                    onlist: h() && r(ft).on_list || w() && r(ft).in_session
                  }), Ie(Fn, "aria-label", `Preview ${r(ft).name}`), Z(Ti, r(ft).name), Z(Ei, r(ft).tune_type || ""), Ie(ys, "aria-label", `Add ${r(ft).name} without previewing`);
                }), D("click", Fn, () => we(r(C).length + r(Er))), D("click", ys, () => Be(r(ft))), x(an, ir);
              }), x(Ee, nt);
            };
            F(ee, (Ee) => {
              r(Se) ? Ee(te) : r(se).length ? Ee(Te, -1) : Ee(ue, 1);
            });
          }
          var ce = S(ee, 2), re = g(ce), pe = S(re, 2), tt = S(ce, 2);
          {
            var ct = (Ee) => {
              var nt = Xu(), Ut = g(nt);
              G(() => Z(Ut, r(De))), x(Ee, nt);
            };
            F(tt, (Ee) => {
              r(De) && Ee(ct);
            });
          }
          G((Ee) => pe.disabled = Ee, [() => !r(be).trim()]), D("input", re, () => c(De, "")), D("keydown", re, (Ee) => {
            Ee.key === "Enter" && (Ee.preventDefault(), ge());
          }), Ur(re, () => r(be), (Ee) => c(be, Ee)), D("click", pe, ge), x(L, X);
        };
        F(et, (L) => {
          r(Ue) && L(Zt);
        });
      }
      G(() => {
        Ie(v, "aria-expanded", r(C).length > 0), Ie(v, "aria-activedescendant", r(Q) >= 0 ? `dres-${r(Q)}` : void 0), Ie(v, "placeholder", r(V) === "abc" ? "Search by notes, e.g. GED or EBBA…" : r(V) === "name" ? "Search by name…" : "Search by name or notes…"), me = Fe(z, 1, "deep-filter-tab", null, me, {
          active: r(P) || r(T) != null || r(V) !== "mixed"
        }), Ie(z, "aria-expanded", r(P));
      }), D("input", v, qe), D("keydown", v, M), D("click", z, An), x(k, O);
    };
    F(jn, (k) => {
      r(Re) ? k(pn) : r(Oe) != null && r(gt)[r(Oe)] ? k(In, 1) : k(Mn, -1);
    });
  }
  return x(e, Jt), nr(Je);
}
Xr(["click", "input", "keydown", "change"]);
function Ju(e = "mt-add-open") {
  let t = /* @__PURE__ */ I(
    !1
    // pane in the DOM
  ), n = /* @__PURE__ */ I(
    !1
    // slide-in transform applied (one frame later, so it animates)
  ), i = null;
  return {
    get visible() {
      return r(t);
    },
    get shown() {
      return r(n);
    },
    open() {
      i && (clearTimeout(i), i = null), c(t, !0), document.body.classList.add(e), requestAnimationFrame(() => requestAnimationFrame(() => c(n, !0)));
    },
    close(a = () => {
    }) {
      i && clearTimeout(i), c(n, !1), document.body.classList.remove(e), i = setTimeout(
        () => {
          i = null, c(t, !1), a();
        },
        300
      );
    }
  };
}
var Zu = /* @__PURE__ */ E('<div class="deep-staff"><!></div>'), $u = /* @__PURE__ */ E('<span class="deep-badge">importing from thesession.org</span>'), ec = /* @__PURE__ */ E('<span class="deep-books"> </span>'), Hs = /* @__PURE__ */ E("<button> </button>"), tc = /* @__PURE__ */ E('<span class="mt-manual-badge">manual</span>'), nc = /* @__PURE__ */ E('<span class="mt-untracked">not tracking</span>'), rc = /* @__PURE__ */ E('<div class="tsc-block tsc-inst-block"><div class="tsc-label-line mt-label"> <!> <!></div> <div class="tunebook-status-seg"></div></div>'), ic = /* @__PURE__ */ E('<div class="tsc-instruments"></div>'), sc = /* @__PURE__ */ E('<button class="tsc-expand-link mt-expand"> </button> <!>', 1), Ys = /* @__PURE__ */ E('<p class="mt-error"> </p>'), ac = /* @__PURE__ */ E('<div class="mt-advanced"><label class="mt-label" for="mt-add-setting">Setting (optional)</label> <input id="mt-add-setting" class="mt-setting" placeholder="Setting number or thesession.org URL"/> <p class="mt-help">If you play a specific setting of the tune, paste its URL or setting number.</p> <!></div>'), lc = /* @__PURE__ */ E('<div class="deep-head"><button class="mt-back" aria-label="Back to search">‹</button> <span class="deep-title">Add to My Tunes</span> <button class="deep-done">Cancel</button></div> <div class="mt-config"><div class="deep-card mt-picked"><div class="deep-card-head"><span class="deep-name"> </span> <span class="deep-type"> </span></div> <!> <div class="deep-meta"><!> <!></div> <button class="mt-change">Not this one? Back to search</button></div> <div class="mt-section"><div class="tsc-label-line mt-label">Add as</div> <div class="tunebook-status-seg"></div> <!></div> <div class="mt-section"><label class="mt-label" for="mt-add-notes">Notes</label> <textarea id="mt-add-notes" class="mt-notes" placeholder="Add any notes about this tune…"></textarea></div> <div class="mt-section"><button class="mt-advanced-toggle"> </button> <!></div> <!> <button class="mt-submit"> </button></div>', 1), oc = /* @__PURE__ */ E('<div aria-hidden="true"></div> <div role="dialog" aria-label="Add a tune to My Tunes"><!></div>', 1);
function uc(e, t) {
  tr(t, !0);
  const n = { searchApiBase: "/api/my-tunes" }, i = ["want to learn", "learning", "learned"], a = {
    "want to learn": "Want To Learn",
    learning: "Learning",
    learned: "Learned"
  }, s = Ju();
  let l = /* @__PURE__ */ I(
    null
    // null = search phase; else {tune_id?, thesession_id?, name, tune_type, ...}
  ), o = /* @__PURE__ */ I(Ge(
    []
    // the person's instruments [{instrument, is_auto}], from the page
  )), u = /* @__PURE__ */ I(""), f = /* @__PURE__ */ I(Ge(
    []
    // search recall (MRU), kept across open/close for the page's lifetime
  )), h = /* @__PURE__ */ I("want to learn"), w = /* @__PURE__ */ I(!1), _ = /* @__PURE__ */ I(Ge(
    {}
    // instrument -> status ('want to learn'|...|null). Missing key = default.
  )), y = /* @__PURE__ */ I(""), p = /* @__PURE__ */ I(!1), b = /* @__PURE__ */ I(""), m = /* @__PURE__ */ I(""), T = /* @__PURE__ */ I(!1), V = /* @__PURE__ */ I(""), P = () => {
  }, C = () => {
  }, K = () => {
  };
  function W(H = {}) {
    c(o, H.instruments || [], !0), c(u, H.query || "", !0), P = H.onAdded || (() => {
    }), C = H.onAlready || (() => {
    }), K = H.onClosed || (() => {
    }), _e(), c(l, null), s.open();
  }
  function R() {
    const H = K;
    s.close(() => {
      c(l, null), H();
    });
  }
  function Q() {
    return s.visible;
  }
  function _e() {
    c(h, "want to learn"), c(w, !1), c(_, {}, !0), c(y, ""), c(p, !1), c(b, ""), c(m, ""), c(T, !1), c(V, "");
  }
  function se(H) {
    const U = (H || "").trim();
    U && c(f, [U, ...r(f).filter((J) => J !== U)].slice(0, 20), !0);
  }
  function Se(H, U, J) {
    if (J != null && J.on_list) {
      const Ce = H.tune_id ?? H.thesession_id;
      return R(), C(Ce, U), !1;
    }
    return c(
      l,
      {
        ...H,
        tunebook_count: J == null ? void 0 : J.tunebook_count,
        incipit_image: (J == null ? void 0 : J.incipit_image) ?? null,
        can_render: (J == null ? void 0 : J.can_render) ?? !1
      },
      !0
    ), _e(), H.setting_id != null && (c(b, String(H.setting_id), !0), c(p, !0)), !1;
  }
  function Ue() {
    c(l, null), c(V, "");
  }
  function be(H) {
    return H.instrument in r(_) ? r(_)[H.instrument] : H.is_auto ? r(h) : null;
  }
  function De(H, U) {
    be(H) === U ? H.is_auto ? delete r(_)[H.instrument] : r(_)[H.instrument] = null : H.is_auto && U === r(h) ? delete r(
      _
      // choosing the base status = just follow it
    )[H.instrument] : r(_)[H.instrument] = U, c(_, { ...r(_) }, !0);
  }
  function Oe() {
    const H = [];
    for (const U of r(o)) {
      const J = U.instrument in r(_) ? r(_)[U.instrument] : void 0;
      J !== void 0 && (U.is_auto && J === r(h) || !U.is_auto && J === null || H.push({ instrument: U.instrument, status: J }));
    }
    return H;
  }
  function Re(H) {
    const U = (H || "").trim();
    if (!U) return { ok: !0, id: null };
    if (/^\d+$/.test(U)) return { ok: !0, id: parseInt(U, 10) };
    if (U.includes("thesession.org")) {
      const J = U.match(/[?&]setting=(\d+)/);
      if (J) return { ok: !0, id: parseInt(J[1], 10) };
      const Ce = U.match(/#setting(\d+)/);
      if (Ce) return { ok: !0, id: parseInt(Ce[1], 10) };
    }
    return { ok: !1, id: null };
  }
  function We(H) {
    return window.MyTunesOffline ? window.MyTunesOffline.submit(H) : fetch("/api/my-tunes/ops", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify(H)
    }).then(async (U) => {
      const J = await U.json().catch(() => ({}));
      if (!U.ok || J.success === !1) throw new Error(J.error || `op failed: ${U.status}`);
      return J;
    });
  }
  async function pt(H) {
    for (const U of Oe())
      await We({
        type: "set_instrument_status",
        tune_id: H,
        instrument: U.instrument,
        status: U.status
      });
  }
  async function He() {
    var Ce;
    if (r(T)) return;
    c(V, "");
    const H = Re(r(b));
    if (!H.ok) {
      c(m, "Enter a setting number or paste a thesession.org URL."), c(p, !0);
      return;
    }
    c(m, ""), c(T, !0);
    const U = r(l).tune_id ?? r(l).thesession_id, J = r(y).trim();
    try {
      if (r(l).thesession_id != null || H.id != null) {
        if (!navigator.onLine)
          throw new Error(r(l).thesession_id != null ? "You are offline. Tunes from thesession.org can only be added online." : "You are offline. A specific setting can only be saved online.");
        const qe = await fetch("/api/my-tunes", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "same-origin",
          body: JSON.stringify({
            tune_id: r(l).tune_id ?? null,
            thesession_id: r(l).thesession_id ?? null,
            learn_status: r(h),
            notes: J || null,
            setting_id: H.id
          })
        }), Qe = await qe.json().catch(() => ({})), xt = ((Ce = Qe.person_tune) == null ? void 0 : Ce.tune_id) ?? Qe.redirect_to_tune_id ?? U;
        if (qe.status === 409) {
          R(), C(xt, r(l).name);
          return;
        }
        if (!qe.ok || !Qe.success) throw new Error(Qe.error || "Could not add the tune.");
        await pt(xt), R(), P(xt, r(l).name);
      } else
        await We({
          type: "add",
          tune_id: U,
          learn_status: r(h),
          name: r(l).name,
          tune_type: r(l).tune_type
        }), J && await We({ type: "set_notes", tune_id: U, notes: J }), await pt(U), R(), P(U, r(l).name);
    } catch (qe) {
      c(V, (qe == null ? void 0 : qe.message) || "Could not add the tune. Please try again.", !0), c(T, !1);
    }
  }
  var gt = { open: W, close: R, isOpen: Q }, we = cn(), Me = Ke(we);
  {
    var ut = (H) => {
      var U = oc(), J = Ke(U);
      let Ce;
      var qe = S(J, 2);
      let Qe;
      var xt = g(qe);
      {
        var Nt = (Mt) => {
          Qu(Mt, {
            get config() {
              return n;
            },
            variant: "modal",
            title: "Search for a tune",
            allowAsIs: !1,
            actionLabel: "＋ Add This Tune",
            dimOnList: !0,
            get initialQuery() {
              return r(u);
            },
            get history() {
              return r(f);
            },
            onRemember: se,
            onAdd: Se,
            onClose: R
          });
        }, An = (Mt) => {
          var sn = lc(), Kt = Ke(sn), Qt = g(Kt), jt = S(Qt, 4), hn = S(Kt, 2), M = g(hn), B = g(M), he = g(B), Be = g(he), ge = S(he, 2), Pe = g(ge), yt = S(B, 2);
          {
            var Lt = (Y) => {
              var ne = Zu(), fe = g(ne);
              Xa(fe, {
                get config() {
                  return n;
                },
                get tuneId() {
                  return r(l).tune_id;
                },
                get image() {
                  return r(l).incipit_image;
                },
                get canRender() {
                  return r(l).can_render;
                }
              }), x(Y, ne);
            };
            F(yt, (Y) => {
              r(l).tune_id != null && (r(l).incipit_image || r(l).can_render) && Y(Lt);
            });
          }
          var Je = S(yt, 2), Jt = g(Je);
          {
            var jn = (Y) => {
              var ne = $u();
              x(Y, ne);
            };
            F(Jt, (Y) => {
              r(l).thesession_id != null && r(l).tune_id == null && Y(jn);
            });
          }
          var pn = S(Jt, 2);
          {
            var In = (Y) => {
              var ne = ec(), fe = g(ne);
              G(() => Z(fe, `${r(l).tunebook_count ?? ""} tunebooks`)), x(Y, ne);
            };
            F(pn, (Y) => {
              r(l).tunebook_count != null && Y(In);
            });
          }
          var Mn = S(Je, 2), k = S(M, 2), O = S(g(k), 2);
          At(O, 21, () => i, is, (Y, ne) => {
            var fe = Hs();
            let q;
            var j = g(fe);
            G(() => {
              q = Fe(fe, 1, "tunebook-status-opt", null, q, { active: r(h) === r(ne) }), Ie(fe, "data-status", r(ne)), Z(j, a[r(ne)]);
            }), D("click", fe, () => c(h, r(ne), !0)), x(Y, fe);
          });
          var ze = S(O, 2);
          {
            var Ye = (Y) => {
              var ne = sc(), fe = Ke(ne), q = g(fe), j = S(fe, 2);
              {
                var oe = (je) => {
                  var mt = ic();
                  At(mt, 21, () => r(o), (lt) => lt.instrument, (lt, $e) => {
                    var et = rc(), Zt = g(et), L = g(Zt), X = S(L);
                    {
                      var ee = (re) => {
                        var pe = tc();
                        x(re, pe);
                      };
                      F(X, (re) => {
                        r($e).is_auto || re(ee);
                      });
                    }
                    var te = S(X, 2);
                    {
                      var ue = (re) => {
                        var pe = nc();
                        x(re, pe);
                      }, Te = /* @__PURE__ */ Ae(() => be(r($e)) === null);
                      F(te, (re) => {
                        r(Te) && re(ue);
                      });
                    }
                    var ce = S(Zt, 2);
                    At(ce, 21, () => i, is, (re, pe) => {
                      var tt = Hs();
                      let ct;
                      var Ee = g(tt);
                      G(
                        (nt) => {
                          ct = Fe(tt, 1, "tunebook-status-opt", null, ct, nt), Ie(tt, "data-status", r(pe)), Z(Ee, a[r(pe)]);
                        },
                        [
                          () => ({ active: be(r($e)) === r(pe) })
                        ]
                      ), D("click", tt, () => De(r($e), r(pe))), x(re, tt);
                    }), G(() => Z(L, `${r($e).instrument ?? ""} `)), x(lt, et);
                  }), x(je, mt);
                };
                F(j, (je) => {
                  r(w) && je(oe);
                });
              }
              G(() => Z(q, r(w) ? "Hide Instruments" : "View By Instrument")), D("click", fe, () => c(w, !r(w))), x(Y, ne);
            };
            F(ze, (Y) => {
              r(o).length >= 2 && Y(Ye);
            });
          }
          var Ze = S(k, 2), Ft = S(g(Ze), 2), v = S(Ze, 2), A = g(v), N = g(A), z = S(A, 2);
          {
            var me = (Y) => {
              var ne = ac(), fe = S(g(ne), 2), q = S(fe, 4);
              {
                var j = (oe) => {
                  var je = Ys(), mt = g(je);
                  G(() => Z(mt, r(m))), x(oe, je);
                };
                F(q, (oe) => {
                  r(m) && oe(j);
                });
              }
              D("input", fe, () => c(m, "")), Ur(fe, () => r(b), (oe) => c(b, oe)), x(Y, ne);
            };
            F(z, (Y) => {
              r(p) && Y(me);
            });
          }
          var le = S(v, 2);
          {
            var ke = (Y) => {
              var ne = Ys(), fe = g(ne);
              G(() => Z(fe, r(V))), x(Y, ne);
            };
            F(le, (Y) => {
              r(V) && Y(ke);
            });
          }
          var Ne = S(le, 2), ye = g(Ne);
          G(() => {
            Z(Be, r(l).name), Z(Pe, r(l).tune_type || ""), Z(N, `${r(p) ? "▾" : "▸"} Advanced`), Ne.disabled = r(T), Z(ye, r(T) ? "Adding…" : "Add to My Tunes");
          }), D("click", Qt, Ue), D("click", jt, R), D("click", Mn, Ue), Ur(Ft, () => r(y), (Y) => c(y, Y)), D("click", A, () => c(p, !r(p))), D("click", Ne, He), x(Mt, sn);
        };
        F(xt, (Mt) => {
          r(l) ? Mt(An, -1) : Mt(Nt);
        });
      }
      G(() => {
        Ce = Fe(J, 1, "mt-add-backdrop", null, Ce, { "mt-open": s.shown }), Qe = Fe(qe, 1, "mt-add-pane", null, Qe, { "mt-open": s.shown });
      }), D("click", J, R), x(H, U);
    };
    F(Me, (H) => {
      s.visible && H(ut);
    });
  }
  return x(e, we), nr(gt);
}
Xr(["click", "input"]);
const ar = { closeRevealed: null };
var cc = /* @__PURE__ */ E('<span class="pending-sync-badge" title="Queued - will sync when you are back online" style="flex:0 0 auto;white-space:nowrap;font-size:11px;font-weight:600;color:#b58900;">pending</span>'), fc = /* @__PURE__ */ E('<span class="tune-type"> </span>'), dc = /* @__PURE__ */ E('<span>Heard at sessions:</span> <span class="heard-count"> </span> <button class="increment-heard-btn" title="Increment heard count">+</button>', 1), vc = /* @__PURE__ */ E('<button class="increment-heard-btn" title="Mark as heard">+</button> <span style="font-size: 12px;">Mark as heard</span>', 1), _c = /* @__PURE__ */ E('<div class="heard-count-container"><!></div>'), hc = /* @__PURE__ */ E('<a target="_blank" class="tune-action-btn">View on TheSession.org</a>'), pc = /* @__PURE__ */ E('<div class="tune-card-header"><h3 class="tune-name"> </h3> <!> <!></div> <div class="tune-meta"><div class="tune-meta-item"><span style="cursor:pointer;" title="Tap to change status" role="button" tabindex="0"> </span></div></div> <!> <div class="tune-actions"><!></div>', 1), gc = /* @__PURE__ */ E('<div class="tune-card-swipe-container"><div class="tune-card-swipe-action"><button class="swipe-action-btn" data-action="increment"><span class="swipe-action-icon">+</span></button></div> <div role="button" tabindex="0"><!></div></div>'), mc = /* @__PURE__ */ E('<div role="button" tabindex="0"><!></div>');
function Ui(e, t) {
  tr(t, !0);
  const n = (P) => {
    var C = pc(), K = Ke(C), W = g(K), R = g(W), Q = S(W, 2);
    {
      var _e = (we) => {
        var Me = cc();
        x(we, Me);
      };
      F(Q, (we) => {
        t.tune.pending_sync && we(_e);
      });
    }
    var se = S(Q, 2);
    {
      var Se = (we) => {
        var Me = fc(), ut = g(Me);
        G(() => Z(ut, t.typeLabel)), x(we, Me);
      };
      F(se, (we) => {
        t.typeLabel && we(Se);
      });
    }
    var Ue = S(K, 2), be = g(Ue), De = g(be), Oe = g(De), Re = S(Ue, 2);
    {
      var We = (we) => {
        var Me = _c(), ut = g(Me);
        {
          var H = (J) => {
            var Ce = dc(), qe = S(Ke(Ce), 2), Qe = g(qe), xt = S(qe, 2);
            G(() => Z(Qe, t.tune.heard_count)), D("click", xt, (Nt) => {
              Nt.stopPropagation(), t.onincrement(t.tune);
            }), x(J, Ce);
          }, U = (J) => {
            var Ce = vc(), qe = Ke(Ce);
            D("click", qe, (Qe) => {
              Qe.stopPropagation(), t.onincrement(t.tune);
            }), x(J, Ce);
          };
          F(ut, (J) => {
            t.tune.heard_count > 0 ? J(H) : J(U, -1);
          });
        }
        x(we, Me);
      };
      F(Re, (we) => {
        t.displayStatus === "want to learn" && we(We);
      });
    }
    var pt = S(Re, 2), He = g(pt);
    {
      var gt = (we) => {
        var Me = hc();
        G(() => Ie(Me, "href", r(_))), D("click", Me, (ut) => ut.stopPropagation()), x(we, Me);
      };
      F(He, (we) => {
        r(_) && we(gt);
      });
    }
    G(() => {
      Z(R, t.tune.tune_name || "Unknown"), Fe(De, 1, `status-badge ${r(w) ?? ""}`), Z(Oe, t.displayStatus);
    }), D("click", De, (we) => {
      we.stopPropagation(), t.oncycle(t.tune, t.displayStatus, t.cycleIsInstrument);
    }), D("keydown", De, (we) => {
      we.key === "Enter" && (we.stopPropagation(), t.oncycle(t.tune, t.displayStatus, t.cycleIsInstrument));
    }), x(P, C);
  }, i = 80;
  let a = /* @__PURE__ */ I(null), s = /* @__PURE__ */ I(null), l = /* @__PURE__ */ I(0), o = /* @__PURE__ */ I(!1), u = /* @__PURE__ */ I(!1), f = /* @__PURE__ */ I(!1), h = /* @__PURE__ */ I(!1);
  const w = /* @__PURE__ */ Ae(() => "status-" + t.displayStatus.replace(/ /g, "-")), _ = /* @__PURE__ */ Ae(() => t.tune.tune_id ? t.tune.setting_id ? `https://thesession.org/tunes/${t.tune.tune_id}?setting=${t.tune.setting_id}#setting${t.tune.setting_id}` : `https://thesession.org/tunes/${t.tune.tune_id}` : "");
  function y() {
    c(o, !1), c(l, 0), ar.closeRevealed === y && (ar.closeRevealed = null);
  }
  function p() {
    c(h, !0), setTimeout(() => c(h, !1), 200), t.onincrement(t.tune);
  }
  Vt(() => {
    const P = r(a);
    if (!P) return;
    let C = 0, K = 0, W = !1, R = null;
    const Q = (Se) => {
      C = Se.touches[0].clientX, K = Se.touches[0].clientY, W = !0, R = null, ar.closeRevealed && ar.closeRevealed !== y && ar.closeRevealed(), ar.closeRevealed = y, r(o) && y();
    }, _e = (Se) => {
      if (!W) return;
      const Ue = Se.touches[0].clientX - C, be = Se.touches[0].clientY - K;
      R === null && (Math.abs(Ue) > 5 || Math.abs(be) > 5) && (R = Math.abs(Ue) > Math.abs(be) ? "horizontal" : "vertical", R === "horizontal" && c(u, !0)), R === "horizontal" && Ue > 0 && (c(f, !0), c(l, Math.min(Ue, i * 2), !0), Se.preventDefault());
    }, se = () => {
      W && (W = !1, c(u, !1), c(f, !1), R === "horizontal" && (r(l) > i ? (y(), p()) : r(l) > i * 0.25 ? (c(o, !0), c(l, i)) : y()), R = null);
    };
    return P.addEventListener("touchstart", Q, { passive: !0 }), P.addEventListener("touchmove", _e, { passive: !1 }), P.addEventListener("touchend", se, { passive: !0 }), () => {
      P.removeEventListener("touchstart", Q), P.removeEventListener("touchmove", _e), P.removeEventListener("touchend", se);
    };
  }), Vt(() => {
    if (!r(o)) return;
    const P = (C) => {
      r(s) && !r(s).contains(C.target) && y();
    };
    return document.addEventListener("click", P), () => document.removeEventListener("click", P);
  });
  var b = cn(), m = Ke(b);
  {
    var T = (P) => {
      var C = gc(), K = g(C), W = g(K), R = S(K, 2);
      let Q;
      var _e = g(R);
      n(_e), xr(R, (se) => c(a, se), () => r(a)), xr(C, (se) => c(s, se), () => r(s)), G(() => {
        Ie(C, "data-person-tune-id", t.tune.person_tune_id), Ie(C, "data-tune-id", t.tune.tune_id), Pi(K, `width: ${r(l) ?? ""}px;`), Ie(W, "data-person-tune-id", t.tune.person_tune_id), Pi(W, r(h) ? "background-color: #218838;" : ""), Q = Fe(R, 1, "tune-card tune-card-swipeable", null, Q, {
          "tune-card-dimmed": t.tune._instDimmed,
          swiping: r(u),
          revealed: r(o)
        }), Pi(R, r(f) || r(o) ? `transform: translateX(${r(l)}px);` : "");
      }), D("click", W, (se) => {
        se.stopPropagation(), y(), p();
      }), D("click", R, () => t.onshow(t.tune)), D("keydown", R, (se) => se.key === "Enter" && t.onshow(t.tune)), x(P, C);
    }, V = (P) => {
      var C = mc();
      let K;
      var W = g(C);
      n(W), G(() => {
        K = Fe(C, 1, "tune-card", null, K, { "tune-card-dimmed": t.tune._instDimmed }), Ie(C, "data-person-tune-id", t.tune.person_tune_id), Ie(C, "data-tune-id", t.tune.tune_id);
      }), D("click", C, () => t.onshow(t.tune)), D("keydown", C, (R) => R.key === "Enter" && t.onshow(t.tune)), x(P, C);
    };
    F(m, (P) => {
      t.isMobile ? P(T) : P(V, -1);
    });
  }
  x(e, b), nr();
}
Xr(["click", "keydown"]);
const qi = ["want to learn", "learning", "learned"];
function Ga(e) {
  if (!e) return null;
  const t = e.trim();
  if (/^\d+$/.test(t)) return parseInt(t, 10);
  const n = t.match(/thesession\.org\/tunes\/(\d+)/i);
  return n ? parseInt(n[1], 10) : null;
}
function Ka(e, t, n) {
  const i = (t || []).find(
    (s) => s.instrument.toLowerCase() === n.toLowerCase()
  );
  if (!i) return null;
  const a = e.instrument_status || {};
  return Object.prototype.hasOwnProperty.call(a, i.instrument) ? a[i.instrument] : i.is_auto ? e.learn_status : null;
}
const Vs = {
  alpha: (e, t) => (e.tune_name || "").localeCompare(t.tune_name || ""),
  popularity: (e, t) => (e.tunebook_count || 0) - (t.tunebook_count || 0),
  heard: (e, t) => (e.heard_count || 0) - (t.heard_count || 0),
  plays: (e, t) => (e.session_play_count || 0) - (t.session_play_count || 0)
};
function yc(e) {
  const t = Vs[e.type];
  if (!t) return null;
  const n = e.dir === "desc" ? -1 : 1, i = e.type2 ? Vs[e.type2] : null, a = e.dir2 === "desc" ? -1 : 1;
  return (s, l) => {
    const o = t(s, l) * n;
    return o !== 0 || !i ? o : i(s, l) * a;
  };
}
function Ws(e, t) {
  if (typeof window < "u" && window.AccentUtils)
    return window.AccentUtils.includes(e, t);
  const n = (i) => (i || "").normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[‘’]/g, "'").toLowerCase();
  return n(e).includes(n(t));
}
function bc(e, t, n, i) {
  const a = [];
  for (const l of e) {
    if (t.search) {
      const o = Ga(t.search), u = Ws(l.tune_name || "", t.search), f = Ws(l.notes || "", t.search);
      if (!(o && l.tune_id === o) && !u && !f) continue;
    }
    if (!(t.type && l.tune_type !== t.type))
      if (t.instrument) {
        const o = Ka(l, i, t.instrument), u = o === null, f = u ? l.learn_status : o;
        if (t.status && f !== t.status) continue;
        a.push({ ...l, _instDimmed: u });
      } else {
        if (t.status && l.learn_status !== t.status) continue;
        a.push(l);
      }
  }
  const s = yc(n);
  return t.instrument ? a.sort(
    (l, o) => (l._instDimmed ? 1 : 0) - (o._instDimmed ? 1 : 0) || (s ? s(l, o) : 0)
  ) : s && a.sort(s), a;
}
function wc(e) {
  const t = e.search ? Ga(e.search) : null;
  if (t) return `No tune with ID ${t} found`;
  const n = [];
  if (e.type ? n.push(e.type.charAt(0).toUpperCase() + e.type.slice(1) + "s") : n.push("tunes"), e.search && n.push(`containing '${e.search}'`), e.status) {
    const a = { learned: "Learned", learning: "Learning", "want to learn": "Want To Learn" };
    n.push(`in '${a[e.status] || e.status}' status`);
  }
  let i = "No " + n[0];
  return n.length > 1 && (i += " " + n.slice(1).join(" ")), i + " found";
}
function kc(e, t, n) {
  const i = e.length;
  return n.instrument ? `${e.filter((s) => !s._instDimmed).length} of ${i} tune${i !== 1 ? "s" : ""} on ${n.instrument}` : i < t ? `Showing ${i} of ${t} tunes` : `${t} tune${t !== 1 ? "s" : ""}`;
}
function Bi(e, t) {
  return t === "popularity" ? String(e.tunebook_count || 0) : t === "heard" ? String(e.heard_count || 0) : t === "plays" ? String(e.session_play_count || 0) : e.tune_type || "";
}
function xc(e) {
  const t = {
    search: e.get("search") || "",
    type: e.get("type") || "",
    status: e.get("status") || "",
    instrument: e.get("instrument") || ""
  }, n = {
    type: e.get("sortType") || "alpha",
    dir: e.get("sortDir") || "asc",
    type2: e.get("sortType2") || null,
    dir2: e.get("sortDir2") || null
  };
  return { filters: t, sort: n };
}
function Sc(e, t) {
  const n = new URLSearchParams();
  return e.search && n.set("search", e.search), e.type && n.set("type", e.type), e.status && n.set("status", e.status), e.instrument && n.set("instrument", e.instrument), (t.type !== "alpha" || t.dir !== "asc") && (n.set("sortType", t.type), n.set("sortDir", t.dir)), t.type2 && (n.set("sortType2", t.type2), n.set("sortDir2", t.dir2)), n;
}
function Tc(e, t) {
  if (!t || !t.length) return e;
  const n = {}, i = e.slice();
  i.forEach((s) => {
    n[s.tune_id] = s;
  });
  const a = (s, l) => {
    const o = { ...s, ...l, pending_sync: !0 };
    return n[o.tune_id] = o, i[i.indexOf(s)] = o, o;
  };
  return t.slice().sort((s, l) => s.ts - l.ts).forEach((s) => {
    const l = n[s.tune_id];
    if (s.type === "add")
      if (l)
        a(l, {});
      else {
        const o = {
          tune_id: s.tune_id,
          tune_name: s.name || "Tune #" + s.tune_id,
          tune_type: s.tune_type || null,
          learn_status: s.learn_status || "want to learn",
          heard_count: 0,
          notes: null,
          person_tune_id: "pending-" + s.tune_id,
          tunebook_count: s.tunebook_count || 0,
          pending_sync: !0
        };
        n[s.tune_id] = o, i.push(o);
      }
    else if (s.type === "remove")
      l && a(l, { _removed: !0 });
    else if (s.type === "set_status" && l)
      a(l, { learn_status: s.learn_status });
    else if (s.type === "set_heard" && l)
      a(l, { heard_count: s.heard_count });
    else if (s.type === "set_notes" && l)
      a(l, { notes: s.notes });
    else if (s.type === "set_instrument_status" && l) {
      const o = { ...l.instrument_status || {} };
      s.status === null || s.status === void 0 ? delete o[s.instrument] : o[s.instrument] = s.status, a(l, { instrument_status: o });
    }
  }), i.filter((s) => !s._removed);
}
function Ec(e) {
  return typeof window > "u" || !window.MyTunesOffline || !window.MyTunesOffline.pending ? Promise.resolve(e) : window.MyTunesOffline.pending().then((t) => Tc(e, t)).catch(() => e);
}
function zi(e) {
  return typeof window < "u" && window.MyTunesOffline ? window.MyTunesOffline.submit(e) : fetch("/api/my-tunes/ops", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
    body: JSON.stringify(e)
  }).then((t) => t.json()).then((t) => {
    if (!t.success) throw new Error(t.error || "op failed");
    return { online: !0, data: t };
  });
}
function Xs(e) {
  return qi[(qi.indexOf(e) + 1) % qi.length];
}
function Ac(e, t, n) {
  const i = { ...e.instrument_status || {} };
  return t.is_auto && n === e.learn_status ? delete i[t.instrument] : i[t.instrument] = n, i;
}
async function Ic(e) {
  let t = null;
  const n = [];
  for (let i = 1; ; i++) {
    const a = await fetch(
      `/api/my-tunes?per_page=2000&page=${i}&sort=${encodeURIComponent(e)}`,
      { headers: { Accept: "application/json" }, credentials: "same-origin" }
    );
    if (!a.ok) throw new Error("my-tunes failed: " + a.status);
    const s = await a.json();
    if (i === 1 && (t = s.instruments || []), n.push(...s.tunes || []), !s.pagination || !s.pagination.has_next) break;
  }
  return { tunes: n, instruments: t };
}
var Gs = /* @__PURE__ */ E("<button> </button>"), Ks = /* @__PURE__ */ E('<button type="button"> </button>'), Mc = /* @__PURE__ */ E('<div class="filter-panel-row" id="instrument-filter-row"><div id="instrument-filter"><button type="button" class="inst-select-trigger"><span id="instrument-filter-label"> </span> <span class="inst-select-caret">▾</span></button> <div class="inst-select-menu" id="instrument-filter-menu"></div></div></div>'), Lc = /* @__PURE__ */ E('<button id="clear-filters-btn" class="filter-panel-clear-btn">Clear Filters</button>'), Cc = /* @__PURE__ */ E('<div id="filter-panel"><div class="filter-panel-row"><div class="filter-button-group"></div></div> <div class="filter-panel-row"><button id="sort-direction-toggle" class="filter-sort-direction-btn" title="Toggle sort direction"><span id="sort-direction-icon"> </span></button> <div class="filter-button-group"></div></div> <div class="filter-panel-row"><div id="type-filter"><button type="button" class="inst-select-trigger"><span id="type-filter-label"> </span> <span class="inst-select-caret">▾</span></button> <div class="inst-select-menu" id="type-filter-menu"></div></div></div> <!> <div class="filter-panel-actions"><!></div></div>'), Pc = /* @__PURE__ */ E('<span class="filter-pill"> <button type="button" class="filter-pill-x" title="Remove this filter">×</button></span>'), Dc = /* @__PURE__ */ E('<div id="active-filter-pills" class="active-filter-pills" style="display: flex;"></div>'), Oc = /* @__PURE__ */ E('<div class="tunes-grid" id="tunes-grid" style="display: grid;"><div class="error-state"><div class="error-state-icon">⚠️</div> <div class="error-state-title">Failed to Load Tunes</div> <div class="error-state-message">There was a problem loading your tune collection.</div> <div class="error-state-action"><button class="retry-btn"><span class="retry-icon">↻</span> Retry</button></div></div></div>'), Rc = /* @__PURE__ */ E('<a href="#clear" class="btn">Clear Filters</a>'), Nc = /* @__PURE__ */ E('<a class="btn">Add Tune</a>'), jc = /* @__PURE__ */ E('<div id="no-results" class="no-results"><h3>No tunes found</h3> <p id="no-results-message"> </p> <div id="no-results-action" style="margin-top: 15px;"><!></div></div>'), Fc = /* @__PURE__ */ E('<div id="loading" class="loading"><p>Loading your tunes...</p></div>'), Uc = /* @__PURE__ */ E('<!> <div class="tune-group-heading">Tunes on other instruments</div> <!>', 1), qc = /* @__PURE__ */ E('<div class="tunes-grid" id="tunes-grid" style="display: grid;"><!></div>'), Bc = /* @__PURE__ */ E('<div class="my-tunes-container svelte-1g74klt"><div class="my-tunes-header-section"><div class="page-header"><h1>My Tunes <a href="/help/my-tunes" class="help-icon" title="How to use My Tunes"><svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path><line x1="12" y1="17" x2="12.01" y2="17"></line></svg></a></h1> <div class="page-actions"><a href="/my-tunes/sync" class="btn btn-secondary sync-btn">Sync With TheSession.org</a></div></div> <div class="filters-container"><div class="filter-top-row"><input type="text" id="search-input" class="filter-search-input" placeholder="Search" title="Search tunes" autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false"/> <a class="filter-panel-toggle" id="add-tune-btn" title="Add tune" style="text-decoration: none; font-size: 24px; font-weight: 300; line-height: 1;">+</a> <button id="filter-panel-toggle" title="Show filters"><svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="4" y1="21" x2="4" y2="14"></line><line x1="4" y1="10" x2="4" y2="3"></line><line x1="12" y1="21" x2="12" y2="12"></line><line x1="12" y1="8" x2="12" y2="3"></line><line x1="20" y1="21" x2="20" y2="16"></line><line x1="20" y1="12" x2="20" y2="3"></line><line x1="1" y1="14" x2="7" y2="14"></line><line x1="9" y1="8" x2="15" y2="8"></line><line x1="17" y1="16" x2="23" y2="16"></line></svg></button></div> <!></div> <!> <div class="results-count"><span id="results-count-text"><!></span></div></div> <!> <div id="loading-more"><span class="loading-spinner"></span> <span>Loading more tunes...</span></div></div> <!>', 1);
function zc(e, t) {
  tr(t, !0);
  let n = it(t, "pageData", 3, null);
  const i = (v, A) => window.showMessage && window.showMessage(v, A), a = xc(new URLSearchParams(window.location.search));
  let s = Ge(a.filters), l = Ge(a.sort), o = /* @__PURE__ */ I(Ge(a.filters.search)), u = /* @__PURE__ */ I(Ge([])), f = /* @__PURE__ */ I(Ge([])), h = /* @__PURE__ */ I(
    !1
    // suppresses no-results/count until the list is complete
  ), w = /* @__PURE__ */ I(!1), _ = /* @__PURE__ */ I(!1);
  const y = window.matchMedia("(max-width: 768px)");
  let p = /* @__PURE__ */ I(Ge(y.matches));
  y.addEventListener("change", (v) => c(p, v.matches, !0));
  const b = /* @__PURE__ */ Ae(() => bc(r(u), s, l, r(f))), m = /* @__PURE__ */ Ae(() => [
    ...new Set(r(u).map((v) => v.tune_type).filter(Boolean))
  ].sort()), T = /* @__PURE__ */ Ae(() => !!(s.type || s.status || s.instrument)), V = /* @__PURE__ */ Ae(() => r(b).filter((v) => !v._instDimmed)), P = /* @__PURE__ */ Ae(() => r(b).filter((v) => v._instDimmed)), C = () => `${l.type}-${l.dir === "desc" ? "desc" : "asc"}`;
  function K(v, A, N) {
    return Ec(v).then((z) => {
      c(u, z, !0), A && c(f, A, !0), N && c(h, !0);
    });
  }
  function W() {
    return c(w, !0), Ic(C()).then((v) => (c(_, !1), K(v.tunes, v.instruments, !0))).catch(() => {
      r(u).length === 0 && (c(_, !0), i("Server error. Please try again.", "error"));
    }).finally(() => {
      c(w, !1);
    });
  }
  n() && n().tunes && K(n().tunes, n().instruments, !(n().pagination || {}).has_next), Vt(() => {
    st(() => W()), window.CeolOffline && window.CeolOffline.sync();
    const v = () => W();
    return window.addEventListener("mytunes-synced", v), () => window.removeEventListener("mytunes-synced", v);
  }), Vt(() => {
    const A = Sc(s, l).toString(), N = A ? `${window.location.pathname}?${A}` : window.location.pathname, z = new URLSearchParams(window.location.search);
    z.has("show") || z.has("added") || z.has("already") || z.has("ptid") || window.history.replaceState({}, "", N);
  });
  let R = null;
  function Q() {
    clearTimeout(R), R = setTimeout(
      () => {
        s.search = r(o).toLowerCase().trim();
      },
      300
    );
  }
  let _e = /* @__PURE__ */ I(!1), se = /* @__PURE__ */ I(
    ""
    // '', 'opening', 'closing'
  ), Se = /* @__PURE__ */ I(!1);
  function Ue() {
    r(Se) ? (c(se, "closing"), c(_e, !1), setTimeout(
      () => {
        c(Se, !1), c(se, "");
      },
      300
    )) : (c(Se, !0), c(_e, !0), c(se, "opening"), setTimeout(() => c(se, ""), 300));
  }
  let be = /* @__PURE__ */ I(!1), De = /* @__PURE__ */ I(!1);
  Vt(() => {
    if (!r(be) && !r(De)) return;
    const v = (A) => {
      A.target.closest(".inst-select") || (c(be, !1), c(De, !1));
    };
    return document.addEventListener("click", v), () => document.removeEventListener("click", v);
  });
  const Oe = (v) => v.replace(/\b\w/g, (A) => A.toUpperCase()), Re = /* @__PURE__ */ Ae(() => s.type ? Oe(s.type) : "All Tune Types"), We = /* @__PURE__ */ Ae(() => {
    if (s.instrument) return s.instrument;
    if (!r(p) && r(f).length >= 2) {
      const v = r(f).map((N) => N.instrument);
      return "All My Instruments (" + (v.length === 2 ? v.join(" and ") : v.slice(0, -1).join(", ") + ", and " + v[v.length - 1]) + ")";
    }
    return "All My Instruments";
  }), pt = /* @__PURE__ */ Ae(() => {
    if (r(Se)) return [];
    const v = [];
    return s.status && v.push({ key: "status", label: Oe(s.status) }), s.type && v.push({ key: "type", label: Oe(s.type) }), s.instrument && v.push({ key: "instrument", label: s.instrument }), v;
  });
  function He(v) {
    v === "status" ? s.status = "" : v === "type" ? s.type = "" : v === "instrument" && (s.instrument = "");
  }
  function gt() {
    s.type = "", s.status = "", s.instrument = "", l.type2 = null, l.dir2 = null;
  }
  function we(v) {
    if (l.type === v) {
      l.dir = l.dir === "asc" ? "desc" : "asc";
      return;
    }
    l.type2 = l.type, l.dir2 = l.dir, l.type = v, l.dir = v === "popularity" || v === "heard" || v === "plays" ? "desc" : "asc";
  }
  function Me(v, A) {
    c(u, r(u).map((N) => N.tune_id === v ? { ...N, ...A } : N), !0);
  }
  function ut(v, A, N) {
    if (N) {
      const z = r(f).find((ke) => ke.instrument.toLowerCase() === s.instrument.toLowerCase());
      if (!z) return;
      const me = Xs(A), le = { ...v.instrument_status || {} };
      Me(v.tune_id, { instrument_status: Ac(v, z, me) }), zi({
        type: "set_instrument_status",
        tune_id: v.tune_id,
        instrument: z.instrument,
        status: me
      }).then((ke) => {
        ke && ke.queued && Me(v.tune_id, { pending_sync: !0 });
      }).catch(() => {
        Me(v.tune_id, { instrument_status: le }), i("Could not change status. Please try again.", "error");
      });
    } else {
      const z = Xs(v.learn_status), me = v.learn_status;
      Me(v.tune_id, { learn_status: z }), zi({
        type: "set_status",
        tune_id: v.tune_id,
        learn_status: z
      }).then((le) => {
        le && le.queued && Me(v.tune_id, { pending_sync: !0 });
      }).catch(() => {
        Me(v.tune_id, { learn_status: me }), i("Could not change status. Please try again.", "error");
      });
    }
  }
  function H(v) {
    const A = v.heard_count || 0, N = A + 1;
    i(`Heard count: ${A} → ${N}`, "success"), Me(v.tune_id, { heard_count: N }), zi({
      type: "set_heard",
      tune_id: v.tune_id,
      heard_count: N
    }).then((z) => {
      z && z.data && typeof z.data.heard_count == "number" && z.data.heard_count !== N && Me(v.tune_id, { heard_count: z.data.heard_count });
    }).catch(() => {
      Me(v.tune_id, { heard_count: A }), i("An error occurred. Please try again.", "error");
    });
  }
  function U(v) {
    const A = r(u).find((N) => String(N.person_tune_id) === String(v));
    window.TuneDetailModal.show({
      context: "my_tunes",
      tuneId: A ? A.tune_id : null,
      apiEndpoint: `/api/my-tunes/${v}`,
      onSave: () => W(),
      // Filtering by an instrument means you care about per-instrument statuses,
      // so open the modal with those rows already revealed.
      expandInstrumentStatus: s.instrument ? !0 : void 0,
      onStatusChange: (N) => {
        r(u).find((me) => me.tune_id === N.tune_id) && Me(N.tune_id, {
          learn_status: N.learn_status,
          instrument_status: N.instrument_status
        });
      },
      additionalData: {
        personTuneId: v,
        tuneName: A ? A.tune_name : "Loading...",
        tuneType: A ? A.tune_type : "",
        isUserLoggedIn: !0
      }
    });
  }
  let J = /* @__PURE__ */ I(null);
  function Ce(v) {
    v.preventDefault(), r(J).open({
      query: r(o).trim(),
      instruments: r(f),
      onAdded: (A, N) => Qe(A, N, !1),
      onAlready: (A, N) => Qe(A, N, !0)
    });
  }
  const qe = /* @__PURE__ */ Ae(() => r(o).trim() ? `/my-tunes/add?q=${encodeURIComponent(r(o).trim())}` : "/my-tunes/add");
  function Qe(v, A, N) {
    const z = new URLSearchParams(window.location.search);
    z.delete("show"), z.delete("added"), z.delete("already"), z.set("show", v), N ? z.set("already", "1") : z.set("added", A || ""), window.history.replaceState({}, "", `${window.location.pathname}?${z.toString()}`), W(), xt(), An();
  }
  function xt() {
    const v = new URLSearchParams(window.location.search);
    v.has("added") ? i(`Successfully added "${v.get("added")}" to your collection!`, "success") : v.has("already") && i("This tune is already on your list", "info");
  }
  function Nt() {
    const v = new URLSearchParams(window.location.search);
    v.delete("show"), v.delete("added"), v.delete("already");
    const A = v.toString();
    window.history.replaceState({}, "", A ? `${window.location.pathname}?${A}` : window.location.pathname);
  }
  function An() {
    const v = new URLSearchParams(window.location.search);
    if (!(v.has("show") || v.has("added") || v.has("already"))) return;
    const A = v.get("show");
    let N = 0;
    const z = () => {
      if (N++, A) {
        const me = document.querySelector(`[data-tune-id="${A}"]`);
        if (me) {
          me.scrollIntoView({ behavior: "instant", block: "start" });
          const le = Math.max(120, window.innerHeight * 0.33);
          window.scrollBy({ top: -le, behavior: "instant" });
          const ke = me.querySelector(".tune-card") || me;
          setTimeout(
            () => {
              const Ne = Date.now(), ye = () => {
                const Y = Math.min((Date.now() - Ne) / 3e3, 1);
                ke.style.backgroundColor = `rgba(255, 243, 205, ${0.8 * (1 - Y)})`, Y < 1 ? requestAnimationFrame(ye) : ke.style.backgroundColor = "";
              };
              requestAnimationFrame(ye);
            },
            100
          ), Nt();
          return;
        }
      }
      N < 30 ? setTimeout(z, 100) : Nt();
    };
    setTimeout(z, 100);
  }
  function Mt(v, A = 0) {
    r(u).find((z) => String(z.person_tune_id) === String(v)) ? U(v) : A < 20 ? setTimeout(() => Mt(v, A + 1), 250) : U(v);
  }
  Vt(() => {
    xt();
    const v = sessionStorage.getItem("copyTunesMessage");
    v && (sessionStorage.removeItem("copyTunesMessage"), i(v, "success"));
    const A = sessionStorage.getItem("myTunesToast");
    A && (sessionStorage.removeItem("myTunesToast"), i(A, "success")), An();
    const N = window.TuneDetailModal && window.TuneDetailModal.getTuneIdFromUrl ? window.TuneDetailModal.getTuneIdFromUrl() : null;
    N && Mt(N);
  }), Vt(() => {
    const v = document.querySelector("#tune-detail-modal .modal-dialog") || document.querySelector(".modal-dialog");
    if (!v) return;
    let A = 0, N = 0, z = !1;
    const me = (ye) => ["INPUT", "TEXTAREA", "SELECT", "BUTTON", "A"].includes(ye.tagName), le = (ye) => {
      me(ye.target) || (A = ye.touches[0].clientX, N = ye.touches[0].clientY, z = !1);
    }, ke = (ye) => {
      if (!A || me(ye.target)) return;
      const Y = ye.touches[0].clientX - A, ne = ye.touches[0].clientY - N;
      Math.abs(Y) > Math.abs(ne) && Math.abs(Y) > 10 && (z = !0);
    }, Ne = (ye) => {
      if (!A || !z || me(ye.target)) {
        A = 0, z = !1;
        return;
      }
      const Y = ye.changedTouches[0].clientX - A, ne = ye.changedTouches[0].clientY - N;
      Y > 50 && Math.abs(Y) > Math.abs(ne) * 2 && window.TuneDetailModal && window.TuneDetailModal.close(), A = 0, z = !1;
    };
    return v.addEventListener("touchstart", le, { passive: !0 }), v.addEventListener("touchmove", ke, { passive: !0 }), v.addEventListener("touchend", Ne, { passive: !0 }), () => {
      v.removeEventListener("touchstart", le), v.removeEventListener("touchmove", ke), v.removeEventListener("touchend", Ne);
    };
  });
  function sn(v) {
    const A = s.instrument && !v._instDimmed ? Ka(v, r(f), s.instrument) : null;
    return {
      status: A || v.learn_status,
      isInstrument: !!A
    };
  }
  var Kt = Bc(), Qt = Ke(Kt), jt = g(Qt), hn = S(g(jt), 2), M = g(hn), B = g(M), he = S(B, 2), Be = S(he, 2);
  let ge;
  var Pe = S(M, 2);
  {
    var yt = (v) => {
      var A = Cc(), N = g(A), z = g(N);
      At(
        z,
        20,
        () => [
          ["", "All"],
          ["learned", "Learned"],
          ["learning", "Learning"],
          ["want to learn", "Want To Learn"]
        ],
        ([L, X]) => L,
        (L, X) => {
          var ee = /* @__PURE__ */ Ae(() => ks(X, 2));
          let te = () => r(ee)[0], ue = () => r(ee)[1];
          var Te = Gs();
          let ce;
          var re = g(Te);
          G(() => {
            ce = Fe(Te, 1, "filter-status-btn", null, ce, { active: s.status === te() }), Ie(Te, "data-status", te()), Z(re, ue());
          }), D("click", Te, () => s.status = te()), x(L, Te);
        }
      );
      var me = S(N, 2), le = g(me), ke = g(le), Ne = g(ke), ye = S(le, 2);
      At(
        ye,
        20,
        () => [
          ["alpha", "a-z"],
          ["popularity", "popularity"],
          ["plays", "plays"],
          ["heard", "heard"]
        ],
        ([L, X]) => L,
        (L, X) => {
          var ee = /* @__PURE__ */ Ae(() => ks(X, 2));
          let te = () => r(ee)[0], ue = () => r(ee)[1];
          var Te = Gs();
          let ce;
          var re = g(Te);
          G(() => {
            ce = Fe(Te, 1, "filter-sort-btn", null, ce, {
              active: l.type === te(),
              "active-secondary": l.type2 === te() && l.type !== te()
            }), Ie(Te, "data-sort", te()), Z(re, ue());
          }), D("click", Te, () => we(te())), x(L, Te);
        }
      );
      var Y = S(me, 2), ne = g(Y);
      let fe;
      var q = g(ne), j = g(q), oe = g(j), je = S(q, 2);
      At(
        je,
        21,
        () => [
          { value: "", label: "All Tune Types" },
          ...r(m).map((L) => ({ value: L, label: Oe(L) }))
        ],
        (L) => L.value,
        (L, X) => {
          var ee = Ks();
          let te;
          var ue = g(ee);
          G(() => {
            te = Fe(ee, 1, "inst-select-option", null, te, { active: r(X).value === s.type }), Z(ue, r(X).label);
          }), D("click", ee, () => {
            c(be, !1), s.type = r(X).value;
          }), x(L, ee);
        }
      );
      var mt = S(Y, 2);
      {
        var lt = (L) => {
          var X = Mc(), ee = g(X);
          let te;
          var ue = g(ee), Te = g(ue), ce = g(Te), re = S(ue, 2);
          At(
            re,
            21,
            () => [
              { value: "", label: "All My Instruments" },
              ...r(f).map((pe) => ({ value: pe.instrument, label: pe.instrument }))
            ],
            (pe) => pe.value,
            (pe, tt) => {
              var ct = Ks();
              let Ee;
              var nt = g(ct);
              G(() => {
                Ee = Fe(ct, 1, "inst-select-option", null, Ee, { active: r(tt).value === s.instrument }), Z(nt, r(tt).label);
              }), D("click", ct, () => {
                c(De, !1), s.instrument = r(tt).value;
              }), x(pe, ct);
            }
          ), G(() => {
            te = Fe(ee, 1, "inst-select", null, te, { open: r(De) }), Z(ce, r(We));
          }), D("click", ue, (pe) => {
            pe.stopPropagation(), c(be, !1), c(De, !r(De));
          }), x(L, X);
        };
        F(mt, (L) => {
          r(f).length >= 2 && L(lt);
        });
      }
      var $e = S(mt, 2), et = g($e);
      {
        var Zt = (L) => {
          var X = Lc();
          D("click", X, gt), x(L, X);
        };
        F(et, (L) => {
          r(T) && L(Zt);
        });
      }
      G(() => {
        Fe(A, 1, `filter-panel ${r(se) ?? ""}`, "svelte-1g74klt"), Z(Ne, l.dir === "desc" ? "↓" : "↑"), fe = Fe(ne, 1, "inst-select", null, fe, { open: r(be) }), Z(oe, r(Re));
      }), D("click", le, () => l.dir = l.dir === "asc" ? "desc" : "asc"), D("click", q, (L) => {
        L.stopPropagation(), c(De, !1), c(be, !r(be));
      }), x(v, A);
    };
    F(Pe, (v) => {
      r(Se) && v(yt);
    });
  }
  var Lt = S(hn, 2);
  {
    var Je = (v) => {
      var A = Dc();
      At(A, 21, () => r(pt), (N) => N.key, (N, z) => {
        var me = Pc(), le = g(me), ke = S(le);
        G(() => Z(le, r(z).label)), D("click", ke, () => He(r(z).key)), x(N, me);
      }), x(v, A);
    };
    F(Lt, (v) => {
      r(pt).length > 0 && v(Je);
    });
  }
  var Jt = S(Lt, 2), jn = g(Jt), pn = g(jn);
  {
    var In = (v) => {
      var A = Ba();
      G((N) => Z(A, N), [
        () => kc(r(b), r(u).length, s)
      ]), x(v, A);
    };
    F(pn, (v) => {
      r(h) && r(b).length > 0 && v(In);
    });
  }
  var Mn = S(jt, 2);
  {
    var k = (v) => {
      var A = Oc(), N = g(A), z = S(g(N), 6), me = g(z);
      D("click", me, () => W()), x(v, A);
    }, O = (v) => {
      var A = cn(), N = Ke(A);
      {
        var z = (le) => {
          var ke = jc(), Ne = S(g(ke), 2), ye = g(Ne), Y = S(Ne, 2), ne = g(Y);
          {
            var fe = (j) => {
              var oe = Rc();
              D("click", oe, (je) => {
                je.preventDefault(), gt();
              }), x(j, oe);
            }, q = (j) => {
              var oe = Nc();
              G(() => Ie(oe, "href", r(qe))), D("click", oe, Ce), x(j, oe);
            };
            F(ne, (j) => {
              r(T) ? j(fe) : j(q, -1);
            });
          }
          G((j) => Z(ye, j), [
            () => r(u).length === 0 && !s.search && !r(T) ? "Try adjusting your filters or add your first tune to get started!" : wc(s)
          ]), x(le, ke);
        }, me = (le) => {
          var ke = Fc();
          x(le, ke);
        };
        F(N, (le) => {
          r(h) ? le(z) : !r(_) && r(u).length === 0 && le(me, 1);
        });
      }
      x(v, A);
    }, ze = (v) => {
      var A = qc(), N = g(A);
      {
        var z = (le) => {
          var ke = Uc(), Ne = Ke(ke);
          At(Ne, 17, () => r(V), (Y) => Y.person_tune_id, (Y, ne) => {
            const fe = /* @__PURE__ */ Ae(() => sn(r(ne)));
            {
              let q = /* @__PURE__ */ Ae(() => Bi(r(ne), l.type));
              Ui(Y, {
                get tune() {
                  return r(ne);
                },
                get isMobile() {
                  return r(p);
                },
                get displayStatus() {
                  return r(fe).status;
                },
                get cycleIsInstrument() {
                  return r(fe).isInstrument;
                },
                get typeLabel() {
                  return r(q);
                },
                onshow: (j) => U(j.person_tune_id),
                oncycle: ut,
                onincrement: H
              });
            }
          });
          var ye = S(Ne, 4);
          At(ye, 17, () => r(P), (Y) => Y.person_tune_id, (Y, ne) => {
            const fe = /* @__PURE__ */ Ae(() => sn(r(ne)));
            {
              let q = /* @__PURE__ */ Ae(() => Bi(r(ne), l.type));
              Ui(Y, {
                get tune() {
                  return r(ne);
                },
                get isMobile() {
                  return r(p);
                },
                get displayStatus() {
                  return r(fe).status;
                },
                get cycleIsInstrument() {
                  return r(fe).isInstrument;
                },
                get typeLabel() {
                  return r(q);
                },
                onshow: (j) => U(j.person_tune_id),
                oncycle: ut,
                onincrement: H
              });
            }
          }), x(le, ke);
        }, me = (le) => {
          var ke = cn(), Ne = Ke(ke);
          At(Ne, 17, () => r(b), (ye) => ye.person_tune_id, (ye, Y) => {
            const ne = /* @__PURE__ */ Ae(() => sn(r(Y)));
            {
              let fe = /* @__PURE__ */ Ae(() => Bi(r(Y), l.type));
              Ui(ye, {
                get tune() {
                  return r(Y);
                },
                get isMobile() {
                  return r(p);
                },
                get displayStatus() {
                  return r(ne).status;
                },
                get cycleIsInstrument() {
                  return r(ne).isInstrument;
                },
                get typeLabel() {
                  return r(fe);
                },
                onshow: (q) => U(q.person_tune_id),
                oncycle: ut,
                onincrement: H
              });
            }
          }), x(le, ke);
        };
        F(N, (le) => {
          s.instrument && r(P).length > 0 ? le(z) : le(me, -1);
        });
      }
      x(v, A);
    };
    F(Mn, (v) => {
      r(_) && r(u).length === 0 ? v(k) : r(b).length === 0 ? v(O, 1) : v(ze, -1);
    });
  }
  var Ye = S(Mn, 2);
  let Ze;
  var Ft = S(Qt, 2);
  xr(uc(Ft, {}), (v) => c(J, v, !0), () => r(J)), G(() => {
    Ie(he, "href", r(qe)), ge = Fe(Be, 1, "filter-panel-toggle", null, ge, { active: r(Se) || r(T) }), Ze = Fe(Ye, 1, "loading-more", null, Ze, { visible: r(w) && !r(h) });
  }), D("input", B, Q), Ur(B, () => r(o), (v) => c(o, v)), D("click", he, Ce), D("click", Be, Ue), x(e, Kt), nr();
}
Xr(["input", "click"]);
const Qs = document.getElementById("my-tunes-root");
Qs && Ao(zc, {
  target: Qs,
  props: { pageData: window.__PAGE_DATA__ ?? null }
});
