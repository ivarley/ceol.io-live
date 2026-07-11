var Fi = Object.defineProperty;
var ia = (e) => {
  throw TypeError(e);
};
var ji = (e, t, n) => t in e ? Fi(e, t, { enumerable: !0, configurable: !0, writable: !0, value: n }) : e[t] = n;
var Ge = (e, t, n) => ji(e, typeof t != "symbol" ? t + "" : t, n), os = (e, t, n) => t.has(e) || ia("Cannot " + n);
var u = (e, t, n) => (os(e, t, "read from private field"), n ? n.call(e) : t.get(e)), j = (e, t, n) => t.has(e) ? ia("Cannot add the same private member more than once") : t instanceof WeakSet ? t.add(e) : t.set(e, n), I = (e, t, n, r) => (os(e, t, "write to private field"), r ? r.call(e, n) : t.set(e, n), n), $ = (e, t, n) => (os(e, t, "access private method"), n);
var Ps = Array.isArray, qi = Array.prototype.indexOf, Cr = Array.prototype.includes, qr = Array.from, zi = Object.defineProperty, Kn = Object.getOwnPropertyDescriptor, Ui = Object.getOwnPropertyDescriptors, Hi = Object.prototype, Wi = Array.prototype, Ca = Object.getPrototypeOf, la = Object.isExtensible;
const Vi = () => {
};
function Bi(e) {
  for (var t = 0; t < e.length; t++)
    e[t]();
}
function La() {
  var e, t, n = new Promise((r, s) => {
    e = r, t = s;
  });
  return { promise: n, resolve: e, reject: t };
}
const De = 2, Ln = 4, zr = 8, Pa = 1 << 24, ut = 16, ft = 32, Ft = 64, _s = 128, nt = 512, Te = 1024, Ne = 2048, bt = 4096, Ue = 8192, rt = 16384, On = 32768, oa = 1 << 25, Pn = 65536, Lr = 1 << 17, Ji = 1 << 18, In = 1 << 19, Gi = 1 << 20, pt = 1 << 25, rn = 65536, Pr = 1 << 21, wn = 1 << 22, Ot = 1 << 23, Xn = Symbol("$state"), Yi = Symbol(""), wr = Symbol("attributes"), ps = Symbol("class"), ms = Symbol("style"), Vn = Symbol("text"), kr = Symbol("form reset"), Ur = new class extends Error {
  constructor() {
    super(...arguments);
    Ge(this, "name", "StaleReactionError");
    Ge(this, "message", "The reaction that called `getAbortSignal()` was re-run or destroyed");
  }
}();
var Ea;
const Ki = (
  // We gotta write it like this because after downleveling the pure comment may end up in the wrong location
  !!((Ea = globalThis.document) != null && Ea.contentType) && /* @__PURE__ */ globalThis.document.contentType.includes("xml")
);
function Xi() {
  throw new Error("https://svelte.dev/e/async_derived_orphan");
}
function Zi(e, t, n) {
  throw new Error("https://svelte.dev/e/each_key_duplicate");
}
function Qi(e) {
  throw new Error("https://svelte.dev/e/effect_in_teardown");
}
function $i() {
  throw new Error("https://svelte.dev/e/effect_in_unowned_derived");
}
function el(e) {
  throw new Error("https://svelte.dev/e/effect_orphan");
}
function tl() {
  throw new Error("https://svelte.dev/e/effect_update_depth_exceeded");
}
function nl() {
  throw new Error("https://svelte.dev/e/state_descriptors_fixed");
}
function rl() {
  throw new Error("https://svelte.dev/e/state_prototype_fixed");
}
function sl() {
  throw new Error("https://svelte.dev/e/state_unsafe_mutation");
}
function al() {
  throw new Error("https://svelte.dev/e/svelte_boundary_reset_onerror");
}
const il = 1, ll = 2, Ma = 4, ol = 8, cl = 16, ul = 1, dl = 2, Ee = Symbol("uninitialized"), fl = "http://www.w3.org/1999/xhtml";
function vl() {
  console.warn("https://svelte.dev/e/derived_inert");
}
function hl() {
  console.warn("https://svelte.dev/e/select_multiple_invalid_value");
}
function _l() {
  console.warn("https://svelte.dev/e/svelte_boundary_reset_noop");
}
function Na(e) {
  return e === this.v;
}
function pl(e, t) {
  return e != e ? t == t : e !== t || e !== null && typeof e == "object" || typeof e == "function";
}
function Da(e) {
  return !pl(e, this.v);
}
let Be = null;
function Mn(e) {
  Be = e;
}
function ln(e, t = !1, n) {
  Be = {
    p: Be,
    i: !1,
    c: null,
    e: null,
    s: e,
    x: null,
    r: (
      /** @type {Effect} */
      Q
    ),
    l: null
  };
}
function on(e) {
  var t = (
    /** @type {ComponentContext} */
    Be
  ), n = t.e;
  if (n !== null) {
    t.e = null;
    for (var r of n)
      $a(r);
  }
  return t.i = !0, Be = t.p, /** @type {T} */
  {};
}
function Oa() {
  return !0;
}
let Jt = [];
function Ia() {
  var e = Jt;
  Jt = [], Bi(e);
}
function It(e) {
  if (Jt.length === 0 && !Qn) {
    var t = Jt;
    queueMicrotask(() => {
      t === Jt && Ia();
    });
  }
  Jt.push(e);
}
function ml() {
  for (; Jt.length > 0; )
    Ia();
}
function Ra(e) {
  var t = Q;
  if (t === null)
    return H.f |= Ot, e;
  if (!(t.f & On) && !(t.f & Ln))
    throw e;
  Dt(e, t);
}
function Dt(e, t) {
  if (!(t !== null && t.f & rt)) {
    for (; t !== null; ) {
      if (t.f & _s) {
        if (!(t.f & On))
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
const bl = -7169;
function we(e, t) {
  e.f = e.f & bl | t;
}
function Ms(e) {
  e.f & nt || e.deps === null ? we(e, Te) : we(e, bt);
}
function Fa(e) {
  if (e !== null)
    for (const t of e)
      !(t.f & De) || !(t.f & rn) || (t.f ^= rn, Fa(
        /** @type {Derived} */
        t.deps
      ));
}
function ja(e, t, n) {
  e.f & Ne ? t.add(e) : e.f & bt && n.add(e), Fa(e.deps), we(e, Te);
}
function gl(e) {
  let t = 0, n = an(0), r;
  return () => {
    Rs() && (i(n), js(() => (t === 0 && (r = Hs(() => e(() => $n(n)))), t += 1, () => {
      It(() => {
        t -= 1, t === 0 && (r == null || r(), r = void 0, $n(n));
      });
    })));
  };
}
var yl = Pn | In;
function wl(e, t, n, r) {
  new kl(e, t, n, r);
}
var Qe, Ls, $e, Kt, He, et, ze, Ke, xt, Xt, Mt, kn, rr, sr, St, Rr, ye, xl, Sl, El, bs, xr, Sr, gs, ys;
class kl {
  /**
   * @param {TemplateNode} node
   * @param {BoundaryProps} props
   * @param {((anchor: Node) => void)} children
   * @param {((error: unknown) => unknown) | undefined} [transform_error]
   */
  constructor(t, n, r, s) {
    j(this, ye);
    /** @type {Boundary | null} */
    Ge(this, "parent");
    Ge(this, "is_pending", !1);
    /**
     * API-level transformError transform function. Transforms errors before they reach the `failed` snippet.
     * Inherited from parent boundary, or defaults to identity.
     * @type {(error: unknown) => unknown}
     */
    Ge(this, "transform_error");
    /** @type {TemplateNode} */
    j(this, Qe);
    /** @type {TemplateNode | null} */
    j(this, Ls, null);
    /** @type {BoundaryProps} */
    j(this, $e);
    /** @type {((anchor: Node) => void)} */
    j(this, Kt);
    /** @type {Effect} */
    j(this, He);
    /** @type {Effect | null} */
    j(this, et, null);
    /** @type {Effect | null} */
    j(this, ze, null);
    /** @type {Effect | null} */
    j(this, Ke, null);
    /** @type {DocumentFragment | null} */
    j(this, xt, null);
    j(this, Xt, 0);
    j(this, Mt, 0);
    j(this, kn, !1);
    /** @type {Set<Effect>} */
    j(this, rr, /* @__PURE__ */ new Set());
    /** @type {Set<Effect>} */
    j(this, sr, /* @__PURE__ */ new Set());
    /**
     * A source containing the number of pending async deriveds/expressions.
     * Only created if `$effect.pending()` is used inside the boundary,
     * otherwise updating the source results in needless `Batch.ensure()`
     * calls followed by no-op flushes
     * @type {Source<number> | null}
     */
    j(this, St, null);
    j(this, Rr, gl(() => (I(this, St, an(u(this, Xt))), () => {
      I(this, St, null);
    })));
    var a;
    I(this, Qe, t), I(this, $e, n), I(this, Kt, (l) => {
      var d = (
        /** @type {Effect} */
        Q
      );
      d.b = this, d.f |= _s, r(l);
    }), this.parent = /** @type {Effect} */
    Q.b, this.transform_error = s ?? ((a = this.parent) == null ? void 0 : a.transform_error) ?? ((l) => l), I(this, He, qs(() => {
      $(this, ye, bs).call(this);
    }, yl));
  }
  /**
   * Defer an effect inside a pending boundary until the boundary resolves
   * @param {Effect} effect
   */
  defer_effect(t) {
    ja(t, u(this, rr), u(this, sr));
  }
  /**
   * Returns `false` if the effect exists inside a boundary whose pending snippet is shown
   * @returns {boolean}
   */
  is_rendered() {
    return !this.is_pending && (!this.parent || this.parent.is_rendered());
  }
  has_pending_snippet() {
    return !!u(this, $e).pending;
  }
  /**
   * Update the source that powers `$effect.pending()` inside this boundary,
   * and controls when the current `pending` snippet (if any) is removed.
   * Do not call from inside the class
   * @param {1 | -1} d
   * @param {Batch} batch
   */
  update_pending_count(t, n) {
    $(this, ye, gs).call(this, t, n), I(this, Xt, u(this, Xt) + t), !(!u(this, St) || u(this, kn)) && (I(this, kn, !0), It(() => {
      I(this, kn, !1), u(this, St) && Nn(u(this, St), u(this, Xt));
    }));
  }
  get_effect_pending() {
    return u(this, Rr).call(this), i(
      /** @type {Source<number>} */
      u(this, St)
    );
  }
  /** @param {unknown} error */
  error(t) {
    if (!u(this, $e).onerror && !u(this, $e).failed)
      throw t;
    D != null && D.is_fork ? (u(this, et) && D.skip_effect(u(this, et)), u(this, ze) && D.skip_effect(u(this, ze)), u(this, Ke) && D.skip_effect(u(this, Ke)), D.oncommit(() => {
      $(this, ye, ys).call(this, t);
    })) : $(this, ye, ys).call(this, t);
  }
}
Qe = new WeakMap(), Ls = new WeakMap(), $e = new WeakMap(), Kt = new WeakMap(), He = new WeakMap(), et = new WeakMap(), ze = new WeakMap(), Ke = new WeakMap(), xt = new WeakMap(), Xt = new WeakMap(), Mt = new WeakMap(), kn = new WeakMap(), rr = new WeakMap(), sr = new WeakMap(), St = new WeakMap(), Rr = new WeakMap(), ye = new WeakSet(), xl = function() {
  try {
    I(this, et, tt(() => u(this, Kt).call(this, u(this, Qe))));
  } catch (t) {
    this.error(t);
  }
}, /**
 * @param {unknown} error The deserialized error from the server's hydration comment
 */
Sl = function(t) {
  const n = u(this, $e).failed;
  n && I(this, Ke, tt(() => {
    n(
      u(this, Qe),
      () => t,
      () => () => {
      }
    );
  }));
}, El = function() {
  const t = u(this, $e).pending;
  t && (this.is_pending = !0, I(this, ze, tt(() => t(u(this, Qe)))), It(() => {
    var n = I(this, xt, document.createDocumentFragment()), r = Rt();
    n.append(r), I(this, et, $(this, ye, Sr).call(this, () => tt(() => u(this, Kt).call(this, r)))), u(this, Mt) === 0 && (u(this, Qe).before(n), I(this, xt, null), tn(
      /** @type {Effect} */
      u(this, ze),
      () => {
        I(this, ze, null);
      }
    ), $(this, ye, xr).call(
      this,
      /** @type {Batch} */
      D
    ));
  }));
}, bs = function() {
  try {
    if (this.is_pending = this.has_pending_snippet(), I(this, Mt, 0), I(this, Xt, 0), I(this, et, tt(() => {
      u(this, Kt).call(this, u(this, Qe));
    })), u(this, Mt) > 0) {
      var t = I(this, xt, document.createDocumentFragment());
      Us(u(this, et), t);
      const n = (
        /** @type {(anchor: Node) => void} */
        u(this, $e).pending
      );
      I(this, ze, tt(() => n(u(this, Qe))));
    } else
      $(this, ye, xr).call(
        this,
        /** @type {Batch} */
        D
      );
  } catch (n) {
    this.error(n);
  }
}, /**
 * @param {Batch} batch
 */
xr = function(t) {
  this.is_pending = !1, t.transfer_effects(u(this, rr), u(this, sr));
}, /**
 * @template T
 * @param {() => T} fn
 */
Sr = function(t) {
  var n = Q, r = H, s = Be;
  gt(u(this, He)), st(u(this, He)), Mn(u(this, He).ctx);
  try {
    return sn.ensure(), t();
  } catch (a) {
    return Ra(a), null;
  } finally {
    gt(n), st(r), Mn(s);
  }
}, /**
 * Updates the pending count associated with the currently visible pending snippet,
 * if any, such that we can replace the snippet with content once work is done
 * @param {1 | -1} d
 * @param {Batch} batch
 */
gs = function(t, n) {
  var r;
  if (!this.has_pending_snippet()) {
    this.parent && $(r = this.parent, ye, gs).call(r, t, n);
    return;
  }
  I(this, Mt, u(this, Mt) + t), u(this, Mt) === 0 && ($(this, ye, xr).call(this, n), u(this, ze) && tn(u(this, ze), () => {
    I(this, ze, null);
  }), u(this, xt) && (u(this, Qe).before(u(this, xt)), I(this, xt, null)));
}, /**
 * @param {unknown} error
 */
ys = function(t) {
  u(this, et) && (Je(u(this, et)), I(this, et, null)), u(this, ze) && (Je(u(this, ze)), I(this, ze, null)), u(this, Ke) && (Je(u(this, Ke)), I(this, Ke, null));
  var n = u(this, $e).onerror;
  let r = u(this, $e).failed;
  var s = !1, a = !1;
  const l = () => {
    if (s) {
      _l();
      return;
    }
    s = !0, a && al(), u(this, Ke) !== null && tn(u(this, Ke), () => {
      I(this, Ke, null);
    }), $(this, ye, Sr).call(this, () => {
      $(this, ye, bs).call(this);
    });
  }, d = (c) => {
    try {
      a = !0, n == null || n(c, l), a = !1;
    } catch (h) {
      Dt(h, u(this, He) && u(this, He).parent);
    }
    r && I(this, Ke, $(this, ye, Sr).call(this, () => {
      try {
        return tt(() => {
          var h = (
            /** @type {Effect} */
            Q
          );
          h.b = this, h.f |= _s, r(
            u(this, Qe),
            () => c,
            () => l
          );
        });
      } catch (h) {
        return Dt(
          h,
          /** @type {Effect} */
          u(this, He).parent
        ), null;
      }
    }));
  };
  It(() => {
    var c;
    try {
      c = this.transform_error(t);
    } catch (h) {
      Dt(h, u(this, He) && u(this, He).parent);
      return;
    }
    c !== null && typeof c == "object" && typeof /** @type {any} */
    c.then == "function" ? c.then(
      d,
      /** @param {unknown} e */
      (h) => Dt(h, u(this, He) && u(this, He).parent)
    ) : d(c);
  });
};
function Tl(e, t, n, r) {
  const s = Hr;
  var a = e.filter((b) => !b.settled), l = t.map(s);
  if (n.length === 0 && a.length === 0) {
    r(l);
    return;
  }
  var d = (
    /** @type {Effect} */
    Q
  ), c = Al(), h = a.length === 1 ? a[0].promise : a.length > 1 ? Promise.all(a.map((b) => b.promise)) : null;
  function p(b) {
    if (!(d.f & rt)) {
      c();
      try {
        r([...l, ...b]);
      } catch (S) {
        Dt(S, d);
      }
      Mr();
    }
  }
  var x = qa();
  if (n.length === 0) {
    h.then(() => p([])).finally(x);
    return;
  }
  function _() {
    Promise.all(n.map((b) => /* @__PURE__ */ Cl(b))).then(p).catch((b) => Dt(b, d)).finally(x);
  }
  h ? h.then(() => {
    c(), _(), Mr();
  }) : _();
}
function Al() {
  var e = (
    /** @type {Effect} */
    Q
  ), t = H, n = Be, r = (
    /** @type {Batch} */
    D
  );
  return function(a = !0) {
    gt(e), st(t), Mn(n), a && !(e.f & rt) && (r == null || r.activate(), r == null || r.apply());
  };
}
function Mr(e = !0) {
  gt(null), st(null), Mn(null), e && (D == null || D.deactivate());
}
function qa() {
  var e = (
    /** @type {Effect} */
    Q
  ), t = e.b, n = (
    /** @type {Batch} */
    D
  ), r = !!(t != null && t.is_rendered());
  return t == null || t.update_pending_count(1, n), n.increment(r, e), () => {
    t == null || t.update_pending_count(-1, n), n.decrement(r, e);
  };
}
// @__NO_SIDE_EFFECTS__
function Hr(e) {
  var t = De | Ne;
  return Q !== null && (Q.f |= In), {
    ctx: Be,
    deps: null,
    effects: null,
    equals: Na,
    f: t,
    fn: e,
    reactions: null,
    rv: 0,
    v: (
      /** @type {V} */
      Ee
    ),
    wv: 0,
    parent: Q,
    ac: null
  };
}
const Bn = Symbol("obsolete");
// @__NO_SIDE_EFFECTS__
function Cl(e, t, n) {
  let r = (
    /** @type {Effect | null} */
    Q
  );
  r === null && Xi();
  var s = (
    /** @type {Promise<V>} */
    /** @type {unknown} */
    void 0
  ), a = an(
    /** @type {V} */
    Ee
  ), l = !H, d = /* @__PURE__ */ new Set();
  return Gl(() => {
    var b, S;
    var c = (
      /** @type {Effect} */
      Q
    ), h = La();
    s = h.promise;
    try {
      Promise.resolve(e()).then(h.resolve, (T) => {
        T !== Ur && h.reject(T);
      }).finally(Mr);
    } catch (T) {
      h.reject(T), Mr();
    }
    var p = (
      /** @type {Batch} */
      D
    );
    if (l) {
      if (c.f & On)
        var x = qa();
      if (
        // boundary can be null if the async derived is inside an $effect.root not connected to the component render tree
        (b = r.b) != null && b.is_rendered()
      )
        (S = p.async_deriveds.get(c)) == null || S.reject(Bn);
      else
        for (const T of d.values())
          T.reject(Bn);
      d.add(h), p.async_deriveds.set(c, h);
    }
    const _ = (T, y = void 0) => {
      x == null || x(), d.delete(h), y !== Bn && (p.activate(), y ? (a.f |= Ot, Nn(a, y)) : (a.f & Ot && (a.f ^= Ot), Nn(a, T)), p.deactivate());
    };
    h.promise.then(_, (T) => _(null, T || "unknown"));
  }), Fs(() => {
    for (const c of d)
      c.reject(Bn);
  }), new Promise((c) => {
    function h(p) {
      function x() {
        p === s ? c(a) : h(s);
      }
      p.then(x, x);
    }
    h(s);
  });
}
// @__NO_SIDE_EFFECTS__
function Pt(e) {
  const t = /* @__PURE__ */ Hr(e);
  return si(t), t;
}
// @__NO_SIDE_EFFECTS__
function Ll(e) {
  const t = /* @__PURE__ */ Hr(e);
  return t.equals = Da, t;
}
function Pl(e) {
  var t = e.effects;
  if (t !== null) {
    e.effects = null;
    for (var n = 0; n < t.length; n += 1)
      Je(
        /** @type {Effect} */
        t[n]
      );
  }
}
function Ns(e) {
  var t, n = Q, r = e.parent;
  if (!jt && r !== null && e.v !== Ee && // if it was never evaluated before, it's guaranteed to fail downstream, so we try to execute instead
  r.f & (rt | Ue))
    return vl(), e.v;
  gt(r);
  try {
    e.f &= ~rn, Pl(e), t = oi(e);
  } finally {
    gt(n);
  }
  return t;
}
function za(e) {
  var t = Ns(e);
  if (!e.equals(t) && (e.wv = ii(), (!(D != null && D.is_fork) || e.deps === null) && (D !== null ? (D.capture(e, t, !0), Zn == null || Zn.capture(e, t, !0)) : e.v = t, e.deps === null))) {
    we(e, Te);
    return;
  }
  jt || (Me !== null ? (Rs() || D != null && D.is_fork) && Me.set(e, t) : Ms(e));
}
function Ml(e) {
  var t, n;
  if (e.effects !== null)
    for (const r of e.effects)
      (r.teardown || r.ac) && ((t = r.teardown) == null || t.call(r), (n = r.ac) == null || n.abort(Ur), r.fn !== null && (r.teardown = Vi), r.ac = null, nr(r, 0), zs(r));
}
function Ua(e) {
  if (e.effects !== null)
    for (const t of e.effects)
      t.teardown && t.fn !== null && Dn(t);
}
let cs = null, mn = null, D = null, Zn = null, Me = null, ws = null, Qn = !1, us = !1, yn = null, Er = null;
var ca = 0;
let Nl = 1;
var xn, Nt, Zt, Sn, En, Tn, Et, An, We, ar, Tt, lt, ht, Cn, Qt, oe, ks, Jn, xs, Ha, Wa, gn, Dl, Gn;
const Fr = class Fr {
  constructor() {
    j(this, oe);
    Ge(this, "id", Nl++);
    /** True as soon as `#process` was called */
    j(this, xn, !1);
    Ge(this, "linked", !0);
    /** @type {Batch | null} */
    j(this, Nt, null);
    /** @type {Batch | null} */
    j(this, Zt, null);
    /** @type {Map<Effect, ReturnType<typeof deferred<any>>>} */
    Ge(this, "async_deriveds", /* @__PURE__ */ new Map());
    /**
     * The current values of any signals that are updated in this batch.
     * Tuple format: [value, is_derived] (note: is_derived is false for deriveds, too, if they were overridden via assignment)
     * They keys of this map are identical to `this.#previous`
     * @type {Map<Value, [any, boolean]>}
     */
    Ge(this, "current", /* @__PURE__ */ new Map());
    /**
     * The values of any signals (sources and deriveds) that are updated in this batch _before_ those updates took place.
     * They keys of this map are identical to `this.#current`
     * @type {Map<Value, any>}
     */
    Ge(this, "previous", /* @__PURE__ */ new Map());
    /**
     * When the batch is committed (and the DOM is updated), we need to remove old branches
     * and append new ones by calling the functions added inside (if/each/key/etc) blocks
     * @type {Set<(batch: Batch) => void>}
     */
    j(this, Sn, /* @__PURE__ */ new Set());
    /**
     * If a fork is discarded, we need to destroy any effects that are no longer needed
     * @type {Set<(batch: Batch) => void>}
     */
    j(this, En, /* @__PURE__ */ new Set());
    /**
     * The number of async effects that are currently in flight
     */
    j(this, Tn, 0);
    /**
     * Async effects that are currently in flight, _not_ inside a pending boundary
     * @type {Map<Effect, number>}
     */
    j(this, Et, /* @__PURE__ */ new Map());
    /**
     * A deferred that resolves when the batch is committed, used with `settled()`
     * TODO replace with Promise.withResolvers once supported widely enough
     * @type {{ promise: Promise<void>, resolve: (value?: any) => void, reject: (reason: unknown) => void } | null}
     */
    j(this, An, null);
    /**
     * The root effects that need to be flushed
     * @type {Effect[]}
     */
    j(this, We, []);
    /**
     * Effects created while this batch was active.
     * @type {Effect[]}
     */
    j(this, ar, []);
    /**
     * Deferred effects (which run after async work has completed) that are DIRTY
     * @type {Set<Effect>}
     */
    j(this, Tt, /* @__PURE__ */ new Set());
    /**
     * Deferred effects that are MAYBE_DIRTY
     * @type {Set<Effect>}
     */
    j(this, lt, /* @__PURE__ */ new Set());
    /**
     * A map of branches that still exist, but will be destroyed when this batch
     * is committed — we skip over these during `process`.
     * The value contains child effects that were dirty/maybe_dirty before being reset,
     * so they can be rescheduled if the branch survives.
     * @type {Map<Effect, { d: Effect[], m: Effect[] }>}
     */
    j(this, ht, /* @__PURE__ */ new Map());
    /**
     * Inverse of #skipped_branches which we need to tell prior batches to unskip them when committing
     * @type {Set<Effect>}
     */
    j(this, Cn, /* @__PURE__ */ new Set());
    Ge(this, "is_fork", !1);
    j(this, Qt, !1);
    mn === null ? cs = mn = this : (I(mn, Zt, this), I(this, Nt, mn)), mn = this;
  }
  /**
   * Add an effect to the #skipped_branches map and reset its children
   * @param {Effect} effect
   */
  skip_effect(t) {
    u(this, ht).has(t) || u(this, ht).set(t, { d: [], m: [] }), u(this, Cn).delete(t);
  }
  /**
   * Remove an effect from the #skipped_branches map and reschedule
   * any tracked dirty/maybe_dirty child effects
   * @param {Effect} effect
   * @param {(e: Effect) => void} callback
   */
  unskip_effect(t, n = (r) => this.schedule(r)) {
    var r = u(this, ht).get(t);
    if (r) {
      u(this, ht).delete(t);
      for (var s of r.d)
        we(s, Ne), n(s);
      for (s of r.m)
        we(s, bt), n(s);
    }
    u(this, Cn).add(t);
  }
  /**
   * Associate a change to a given source with the current
   * batch, noting its previous and current values
   * @param {Value} source
   * @param {any} value
   * @param {boolean} [is_derived]
   */
  capture(t, n, r = !1) {
    t.v !== Ee && !this.previous.has(t) && this.previous.set(t, t.v), t.f & Ot || (this.current.set(t, [n, r]), Me == null || Me.set(t, n)), this.is_fork || (t.v = n);
  }
  activate() {
    D = this;
  }
  deactivate() {
    D = null, Me = null;
  }
  flush() {
    try {
      us = !0, D = this, $(this, oe, Jn).call(this);
    } finally {
      ca = 0, ws = null, yn = null, Er = null, us = !1, D = null, Me = null, en.clear();
    }
  }
  discard() {
    var t;
    for (const n of u(this, En)) n(this);
    u(this, En).clear();
    for (const n of this.async_deriveds.values())
      n.reject(Bn);
    $(this, oe, Gn).call(this), (t = u(this, An)) == null || t.resolve();
  }
  /**
   * @param {Effect} effect
   */
  register_created_effect(t) {
    u(this, ar).push(t);
  }
  /**
   * @param {boolean} blocking
   * @param {Effect} effect
   */
  increment(t, n) {
    if (I(this, Tn, u(this, Tn) + 1), t) {
      let r = u(this, Et).get(n) ?? 0;
      u(this, Et).set(n, r + 1);
    }
  }
  /**
   * @param {boolean} blocking
   * @param {Effect} effect
   */
  decrement(t, n) {
    if (I(this, Tn, u(this, Tn) - 1), t) {
      let r = u(this, Et).get(n) ?? 0;
      r === 1 ? u(this, Et).delete(n) : u(this, Et).set(n, r - 1);
    }
    u(this, Qt) || (I(this, Qt, !0), It(() => {
      I(this, Qt, !1), this.linked && this.flush();
    }));
  }
  /**
   * @param {Set<Effect>} dirty_effects
   * @param {Set<Effect>} maybe_dirty_effects
   */
  transfer_effects(t, n) {
    for (const r of t)
      u(this, Tt).add(r);
    for (const r of n)
      u(this, lt).add(r);
    t.clear(), n.clear();
  }
  /** @param {(batch: Batch) => void} fn */
  oncommit(t) {
    u(this, Sn).add(t);
  }
  /** @param {(batch: Batch) => void} fn */
  ondiscard(t) {
    u(this, En).add(t);
  }
  settled() {
    return (u(this, An) ?? I(this, An, La())).promise;
  }
  static ensure() {
    if (D === null) {
      const t = D = new Fr();
      !us && !Qn && It(() => {
        u(t, xn) || t.flush();
      });
    }
    return D;
  }
  apply() {
    {
      Me = null;
      return;
    }
  }
  /**
   *
   * @param {Effect} effect
   */
  schedule(t) {
    var s;
    if (ws = t, (s = t.b) != null && s.is_pending && t.f & (Ln | zr | Pa) && !(t.f & On)) {
      t.b.defer_effect(t);
      return;
    }
    for (var n = t; n.parent !== null; ) {
      n = n.parent;
      var r = n.f;
      if (yn !== null && n === Q && (H === null || !(H.f & De)))
        return;
      if (r & (Ft | ft)) {
        if (!(r & Te))
          return;
        n.f ^= Te;
      }
    }
    u(this, We).push(n);
  }
};
xn = new WeakMap(), Nt = new WeakMap(), Zt = new WeakMap(), Sn = new WeakMap(), En = new WeakMap(), Tn = new WeakMap(), Et = new WeakMap(), An = new WeakMap(), We = new WeakMap(), ar = new WeakMap(), Tt = new WeakMap(), lt = new WeakMap(), ht = new WeakMap(), Cn = new WeakMap(), Qt = new WeakMap(), oe = new WeakSet(), ks = function() {
  if (this.is_fork) return !0;
  for (const r of u(this, Et).keys()) {
    for (var t = r, n = !1; t.parent !== null; ) {
      if (u(this, ht).has(t)) {
        n = !0;
        break;
      }
      t = t.parent;
    }
    if (!n)
      return !0;
  }
  return !1;
}, Jn = function() {
  var c, h, p, x;
  I(this, xn, !0), ca++ > 1e3 && ($(this, oe, Gn).call(this), Il());
  for (const _ of u(this, Tt))
    u(this, lt).delete(_), we(_, Ne), this.schedule(_);
  for (const _ of u(this, lt))
    we(_, bt), this.schedule(_);
  const t = u(this, We);
  I(this, We, []), this.apply();
  var n = yn = [], r = [], s = Er = [];
  for (const _ of t)
    try {
      $(this, oe, xs).call(this, _, n, r);
    } catch (b) {
      throw Ja(_), $(this, oe, ks).call(this) || this.discard(), b;
    }
  if (D = null, s.length > 0) {
    var a = Fr.ensure();
    for (const _ of s)
      a.schedule(_);
  }
  if (yn = null, Er = null, $(this, oe, ks).call(this)) {
    $(this, oe, gn).call(this, r), $(this, oe, gn).call(this, n);
    for (const [_, b] of u(this, ht))
      Ba(_, b);
    s.length > 0 && /** @type {unknown} */
    $(c = D, oe, Jn).call(c);
    return;
  }
  const l = $(this, oe, Ha).call(this);
  if (l) {
    $(this, oe, gn).call(this, r), $(this, oe, gn).call(this, n), $(h = l, oe, Wa).call(h, this);
    return;
  }
  u(this, Tt).clear(), u(this, lt).clear();
  for (const _ of u(this, Sn)) _(this);
  u(this, Sn).clear(), Zn = this, ua(r), ua(n), Zn = null, (p = u(this, An)) == null || p.resolve();
  var d = (
    /** @type {Batch | null} */
    /** @type {unknown} */
    D
  );
  if (u(this, Tn) === 0 && (u(this, We).length === 0 || d !== null) && $(this, oe, Gn).call(this), u(this, We).length > 0)
    if (d !== null) {
      const _ = d;
      u(_, We).push(...u(this, We).filter((b) => !u(_, We).includes(b)));
    } else
      d = this;
  d !== null && $(x = d, oe, Jn).call(x);
}, /**
 * Traverse the effect tree, executing effects or stashing
 * them for later execution as appropriate
 * @param {Effect} root
 * @param {Effect[]} effects
 * @param {Effect[]} render_effects
 */
xs = function(t, n, r) {
  t.f ^= Te;
  for (var s = t.first; s !== null; ) {
    var a = s.f, l = (a & (ft | Ft)) !== 0, d = l && (a & Te) !== 0, c = d || (a & Ue) !== 0 || u(this, ht).has(s);
    if (!c && s.fn !== null) {
      l ? s.f ^= Te : a & Ln ? n.push(s) : cr(s) && (a & ut && u(this, lt).add(s), Dn(s));
      var h = s.first;
      if (h !== null) {
        s = h;
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
}, Ha = function() {
  for (var t = u(this, Nt); t !== null; ) {
    if (!t.is_fork) {
      for (const [n, [, r]] of this.current)
        if (t.current.has(n) && !r)
          return t;
    }
    t = u(t, Nt);
  }
  return null;
}, /**
 * @param {Batch} batch
 */
Wa = function(t) {
  var r;
  for (const [s, a] of t.current)
    !this.previous.has(s) && t.previous.has(s) && this.previous.set(s, t.previous.get(s)), this.current.set(s, a);
  for (const [s, a] of t.async_deriveds) {
    const l = this.async_deriveds.get(s);
    l && a.promise.then(l.resolve).catch(l.reject);
  }
  t.async_deriveds.clear(), this.transfer_effects(u(t, Tt), u(t, lt));
  const n = (s) => {
    var a = s.reactions;
    if (a !== null)
      for (const c of a) {
        var l = c.f;
        if (l & De)
          n(
            /** @type {Derived} */
            c
          );
        else {
          var d = (
            /** @type {Effect} */
            c
          );
          l & (wn | ut) && !this.async_deriveds.has(d) && (u(this, lt).delete(d), we(d, Ne), this.schedule(d));
        }
      }
  };
  for (const s of this.current.keys())
    n(s);
  this.oncommit(() => t.discard()), $(r = t, oe, Gn).call(r), D = this, $(this, oe, Jn).call(this);
}, /**
 * @param {Effect[]} effects
 */
gn = function(t) {
  for (var n = 0; n < t.length; n += 1)
    ja(t[n], u(this, Tt), u(this, lt));
}, Dl = function() {
  var x;
  for (let _ = cs; _ !== null; _ = u(_, Zt)) {
    var t = _.id < this.id, n = [];
    for (const [b, [S, T]] of this.current) {
      if (_.current.has(b)) {
        var r = (
          /** @type {[any, boolean]} */
          _.current.get(b)[0]
        );
        if (t && S !== r)
          _.current.set(b, [S, T]);
        else
          continue;
      }
      n.push(b);
    }
    if (t)
      for (const [b, S] of this.async_deriveds) {
        const T = _.async_deriveds.get(b);
        T && S.promise.then(T.resolve).catch(T.reject);
      }
    var s = [..._.current.keys()].filter(
      (b) => !/** @type {[any, boolean]} */
      _.current.get(b)[1]
    );
    if (!(!u(_, xn) || s.length === 0)) {
      var a = s.filter((b) => !this.current.has(b));
      if (a.length === 0)
        t && _.discard();
      else if (n.length > 0) {
        if (t)
          for (const b of u(this, Cn))
            _.unskip_effect(b, (S) => {
              var T;
              S.f & (ut | wn) ? _.schedule(S) : $(T = _, oe, gn).call(T, [S]);
            });
        _.activate();
        var l = /* @__PURE__ */ new Set(), d = /* @__PURE__ */ new Map();
        for (var c of n)
          Va(c, a, l, d);
        d = /* @__PURE__ */ new Map();
        var h = [..._.current].filter(([b, S]) => {
          const T = this.current.get(b);
          return T ? T[0] !== S[0] || T[1] !== S[1] : !0;
        }).map(([b]) => b);
        if (h.length > 0)
          for (const b of u(this, ar))
            !(b.f & (rt | Ue | Lr)) && Ds(b, h, d) && (b.f & (wn | ut) ? (we(b, Ne), _.schedule(b)) : u(_, Tt).add(b));
        if (u(_, We).length > 0 && !u(_, Qt)) {
          _.apply();
          for (var p of u(_, We))
            $(x = _, oe, xs).call(x, p, [], []);
          I(_, We, []);
        }
        _.deactivate();
      }
    }
  }
}, Gn = function() {
  if (this.linked) {
    var t = u(this, Nt), n = u(this, Zt);
    t === null ? cs = n : I(t, Zt, n), n === null ? mn = t : I(n, Nt, t), this.linked = !1;
  }
};
let sn = Fr;
function Ol(e) {
  var t = Qn;
  Qn = !0;
  try {
    for (var n; ; ) {
      if (ml(), D === null)
        return (
          /** @type {T} */
          n
        );
      D.flush();
    }
  } finally {
    Qn = t;
  }
}
function Il() {
  try {
    tl();
  } catch (e) {
    Dt(e, ws);
  }
}
let it = null;
function ua(e) {
  var t = e.length;
  if (t !== 0) {
    for (var n = 0; n < t; ) {
      var r = e[n++];
      if (!(r.f & (rt | Ue)) && cr(r) && (it = /* @__PURE__ */ new Set(), Dn(r), r.deps === null && r.first === null && r.nodes === null && r.teardown === null && r.ac === null && ti(r), (it == null ? void 0 : it.size) > 0)) {
        en.clear();
        for (const s of it) {
          if (s.f & (rt | Ue)) continue;
          const a = [s];
          let l = s.parent;
          for (; l !== null; )
            it.has(l) && (it.delete(l), a.push(l)), l = l.parent;
          for (let d = a.length - 1; d >= 0; d--) {
            const c = a[d];
            c.f & (rt | Ue) || Dn(c);
          }
        }
        it.clear();
      }
    }
    it = null;
  }
}
function Va(e, t, n, r) {
  if (!n.has(e) && (n.add(e), e.reactions !== null))
    for (const s of e.reactions) {
      const a = s.f;
      a & De ? Va(
        /** @type {Derived} */
        s,
        t,
        n,
        r
      ) : a & (wn | ut) && !(a & Ne) && Ds(s, t, r) && (we(s, Ne), Os(
        /** @type {Effect} */
        s
      ));
    }
}
function Ds(e, t, n) {
  const r = n.get(e);
  if (r !== void 0) return r;
  if (e.deps !== null)
    for (const s of e.deps) {
      if (Cr.call(t, s))
        return !0;
      if (s.f & De && Ds(
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
function Os(e) {
  D.schedule(e);
}
function Ba(e, t) {
  if (!(e.f & ft && e.f & Te)) {
    e.f & Ne ? t.d.push(e) : e.f & bt && t.m.push(e), we(e, Te);
    for (var n = e.first; n !== null; )
      Ba(n, t), n = n.next;
  }
}
function Ja(e) {
  we(e, Te);
  for (var t = e.first; t !== null; )
    Ja(t), t = t.next;
}
let Nr = /* @__PURE__ */ new Set();
const en = /* @__PURE__ */ new Map();
let Ga = !1;
function an(e, t) {
  var n = {
    f: 0,
    // TODO ideally we could skip this altogether, but it causes type errors
    v: e,
    reactions: null,
    equals: Na,
    rv: 0,
    wv: 0
  };
  return n;
}
// @__NO_SIDE_EFFECTS__
function M(e, t) {
  const n = an(e);
  return si(n), n;
}
// @__NO_SIDE_EFFECTS__
function Rl(e, t = !1, n = !0) {
  const r = an(e);
  return t || (r.equals = Da), r;
}
function w(e, t, n = !1) {
  H !== null && // since we are untracking the function inside `$inspect.with` we need to add this check
  // to ensure we error if state is set inside an inspect effect
  (!dt || H.f & Lr) && Oa() && H.f & (De | ut | wn | Lr) && (mt === null || !mt.has(e)) && sl();
  let r = n ? ge(t) : t;
  return Nn(e, r, Er);
}
function Nn(e, t, n = null) {
  if (!e.equals(t)) {
    en.set(e, jt ? t : e.v);
    var r = sn.ensure();
    if (r.capture(e, t), e.f & De) {
      const s = (
        /** @type {Derived} */
        e
      );
      e.f & Ne && Ns(s), Me === null && Ms(s);
    }
    e.wv = ii(), Ya(e, Ne, n), Q !== null && Q.f & Te && !(Q.f & (ft | Ft)) && (Ze === null ? Xl([e]) : Ze.push(e)), !r.is_fork && Nr.size > 0 && !Ga && Fl();
  }
  return t;
}
function Fl() {
  Ga = !1;
  for (const e of Nr) {
    e.f & Te && we(e, bt);
    let t;
    try {
      t = cr(e);
    } catch {
      t = !0;
    }
    t && Dn(e);
  }
  Nr.clear();
}
function $n(e) {
  w(e, e.v + 1);
}
function Ya(e, t, n) {
  var r = e.reactions;
  if (r !== null)
    for (var s = r.length, a = 0; a < s; a++) {
      var l = r[a], d = l.f, c = (d & Ne) === 0;
      if (c && we(l, t), d & Lr)
        Nr.add(
          /** @type {Effect} */
          l
        );
      else if (d & De) {
        var h = (
          /** @type {Derived} */
          l
        );
        Me == null || Me.delete(h), d & rn || (d & nt && (Q === null || !(Q.f & Pr)) && (l.f |= rn), Ya(h, bt, n));
      } else if (c) {
        var p = (
          /** @type {Effect} */
          l
        );
        d & ut && it !== null && it.add(p), n !== null ? n.push(p) : Os(p);
      }
    }
}
function ge(e) {
  if (typeof e != "object" || e === null || Xn in e)
    return e;
  const t = Ca(e);
  if (t !== Hi && t !== Wi)
    return e;
  var n = /* @__PURE__ */ new Map(), r = Ps(e), s = /* @__PURE__ */ M(0), a = nn, l = (d) => {
    if (nn === a)
      return d();
    var c = H, h = nn;
    st(null), ha(a);
    var p = d();
    return st(c), ha(h), p;
  };
  return r && n.set("length", /* @__PURE__ */ M(
    /** @type {any[]} */
    e.length
  )), new Proxy(
    /** @type {any} */
    e,
    {
      defineProperty(d, c, h) {
        (!("value" in h) || h.configurable === !1 || h.enumerable === !1 || h.writable === !1) && nl();
        var p = n.get(c);
        return p === void 0 ? l(() => {
          var x = /* @__PURE__ */ M(h.value);
          return n.set(c, x), x;
        }) : w(p, h.value, !0), !0;
      },
      deleteProperty(d, c) {
        var h = n.get(c);
        if (h === void 0) {
          if (c in d) {
            const p = l(() => /* @__PURE__ */ M(Ee));
            n.set(c, p), $n(s);
          }
        } else
          w(h, Ee), $n(s);
        return !0;
      },
      get(d, c, h) {
        var b;
        if (c === Xn)
          return e;
        var p = n.get(c), x = c in d;
        if (p === void 0 && (!x || (b = Kn(d, c)) != null && b.writable) && (p = l(() => {
          var S = ge(x ? d[c] : Ee), T = /* @__PURE__ */ M(S);
          return T;
        }), n.set(c, p)), p !== void 0) {
          var _ = i(p);
          return _ === Ee ? void 0 : _;
        }
        return Reflect.get(d, c, h);
      },
      getOwnPropertyDescriptor(d, c) {
        var h = Reflect.getOwnPropertyDescriptor(d, c);
        if (h && "value" in h) {
          var p = n.get(c);
          p && (h.value = i(p));
        } else if (h === void 0) {
          var x = n.get(c), _ = x == null ? void 0 : x.v;
          if (x !== void 0 && _ !== Ee)
            return {
              enumerable: !0,
              configurable: !0,
              value: _,
              writable: !0
            };
        }
        return h;
      },
      has(d, c) {
        var _;
        if (c === Xn)
          return !0;
        var h = n.get(c), p = h !== void 0 && h.v !== Ee || Reflect.has(d, c);
        if (h !== void 0 || Q !== null && (!p || (_ = Kn(d, c)) != null && _.writable)) {
          h === void 0 && (h = l(() => {
            var b = p ? ge(d[c]) : Ee, S = /* @__PURE__ */ M(b);
            return S;
          }), n.set(c, h));
          var x = i(h);
          if (x === Ee)
            return !1;
        }
        return p;
      },
      set(d, c, h, p) {
        var F;
        var x = n.get(c), _ = c in d;
        if (r && c === "length")
          for (var b = h; b < /** @type {Source<number>} */
          x.v; b += 1) {
            var S = n.get(b + "");
            S !== void 0 ? w(S, Ee) : b in d && (S = l(() => /* @__PURE__ */ M(Ee)), n.set(b + "", S));
          }
        if (x === void 0)
          (!_ || (F = Kn(d, c)) != null && F.writable) && (x = l(() => /* @__PURE__ */ M(void 0)), w(x, ge(h)), n.set(c, x));
        else {
          _ = x.v !== Ee;
          var T = l(() => ge(h));
          w(x, T);
        }
        var y = Reflect.getOwnPropertyDescriptor(d, c);
        if (y != null && y.set && y.set.call(p, h), !_) {
          if (r && typeof c == "string") {
            var C = (
              /** @type {Source<number>} */
              n.get("length")
            ), ee = Number(c);
            Number.isInteger(ee) && ee >= C.v && w(C, ee + 1);
          }
          $n(s);
        }
        return !0;
      },
      ownKeys(d) {
        i(s);
        var c = Reflect.ownKeys(d).filter((x) => {
          var _ = n.get(x);
          return _ === void 0 || _.v !== Ee;
        });
        for (var [h, p] of n)
          p.v !== Ee && !(h in d) && c.push(h);
        return c;
      },
      setPrototypeOf() {
        rl();
      }
    }
  );
}
function da(e) {
  try {
    if (e !== null && typeof e == "object" && Xn in e)
      return e[Xn];
  } catch {
  }
  return e;
}
function jl(e, t) {
  return Object.is(da(e), da(t));
}
var Dr, Ka, Xa, Za;
function ql() {
  if (Dr === void 0) {
    Dr = window, Ka = /Firefox/.test(navigator.userAgent);
    var e = Element.prototype, t = Node.prototype, n = Text.prototype;
    Xa = Kn(t, "firstChild").get, Za = Kn(t, "nextSibling").get, la(e) && (e[ps] = void 0, e[wr] = null, e[ms] = void 0, e.__e = void 0), la(n) && (n[Vn] = void 0);
  }
}
function Rt(e = "") {
  return document.createTextNode(e);
}
// @__NO_SIDE_EFFECTS__
function Or(e) {
  return (
    /** @type {TemplateNode | null} */
    Xa.call(e)
  );
}
// @__NO_SIDE_EFFECTS__
function or(e) {
  return (
    /** @type {TemplateNode | null} */
    Za.call(e)
  );
}
function o(e, t) {
  return /* @__PURE__ */ Or(e);
}
function tr(e, t = !1) {
  {
    var n = /* @__PURE__ */ Or(e);
    return n instanceof Comment && n.data === "" ? /* @__PURE__ */ or(n) : n;
  }
}
function f(e, t = 1, n = !1) {
  let r = e;
  for (; t--; )
    r = /** @type {TemplateNode} */
    /* @__PURE__ */ or(r);
  return r;
}
function zl(e) {
  e.textContent = "";
}
function Qa() {
  return !1;
}
function Ul(e, t, n) {
  return (
    /** @type {T extends keyof HTMLElementTagNameMap ? HTMLElementTagNameMap[T] : Element} */
    n ? document.createElement(e, { is: n }) : document.createElement(e)
  );
}
let fa = !1;
function Hl() {
  fa || (fa = !0, document.addEventListener(
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
            (t = n[kr]) == null || t.call(n);
      });
    },
    // In the capture phase to guarantee we get noticed of it (no possibility of stopPropagation)
    { capture: !0 }
  ));
}
function Wr(e) {
  var t = H, n = Q;
  st(null), gt(null);
  try {
    return e();
  } finally {
    st(t), gt(n);
  }
}
function Is(e, t, n, r = n) {
  e.addEventListener(t, () => Wr(n));
  const s = (
    /** @type {any} */
    e[kr]
  );
  s ? e[kr] = () => {
    s(), r(!0);
  } : e[kr] = () => r(!0), Hl();
}
function Wl(e) {
  Q === null && (H === null && el(), $i()), jt && Qi();
}
function Vl(e, t) {
  var n = t.last;
  n === null ? t.last = t.first = e : (n.next = e, e.prev = n, t.last = e);
}
function Ct(e, t) {
  var n = Q;
  n !== null && n.f & Ue && (e |= Ue);
  var r = {
    ctx: Be,
    deps: null,
    nodes: null,
    f: e | Ne | nt,
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
  D == null || D.register_created_effect(r);
  var s = r;
  if (e & Ln)
    yn !== null ? yn.push(r) : sn.ensure().schedule(r);
  else if (t !== null) {
    try {
      Dn(r);
    } catch (l) {
      throw Je(r), l;
    }
    s.deps === null && s.teardown === null && s.nodes === null && s.first === s.last && // either `null`, or a singular child
    !(s.f & In) && (s = s.first, e & ut && e & Pn && s !== null && (s.f |= Pn));
  }
  if (s !== null && (s.parent = n, n !== null && Vl(s, n), H !== null && H.f & De && !(e & Ft))) {
    var a = (
      /** @type {Derived} */
      H
    );
    (a.effects ?? (a.effects = [])).push(s);
  }
  return r;
}
function Rs() {
  return H !== null && !dt;
}
function Fs(e) {
  const t = Ct(zr, null);
  return we(t, Te), t.teardown = e, t;
}
function Vr(e) {
  Wl();
  var t = (
    /** @type {Effect} */
    Q.f
  ), n = !H && (t & ft) !== 0 && Be !== null && !Be.i;
  if (n) {
    var r = (
      /** @type {ComponentContext} */
      Be
    );
    (r.e ?? (r.e = [])).push(e);
  } else
    return $a(e);
}
function $a(e) {
  return Ct(Ln | Gi, e);
}
function Bl(e) {
  sn.ensure();
  const t = Ct(Ft | In, e);
  return (n = {}) => new Promise((r) => {
    n.outro ? tn(t, () => {
      Je(t), r(void 0);
    }) : (Je(t), r(void 0));
  });
}
function Jl(e) {
  return Ct(Ln, e);
}
function Gl(e) {
  return Ct(wn | In, e);
}
function js(e, t = 0) {
  return Ct(zr | t, e);
}
function K(e, t = [], n = [], r = []) {
  Tl(r, t, n, (s) => {
    Ct(zr, () => {
      e(...s.map(i));
    });
  });
}
function qs(e, t = 0) {
  var n = Ct(ut | t, e);
  return n;
}
function tt(e) {
  return Ct(ft | In, e);
}
function ei(e) {
  var t = e.teardown;
  if (t !== null) {
    const n = jt, r = H;
    va(!0), st(null);
    try {
      t.call(null);
    } finally {
      va(n), st(r);
    }
  }
}
function zs(e, t = !1) {
  var n = e.first;
  for (e.first = e.last = null; n !== null; ) {
    const s = n.ac;
    s !== null && Wr(() => {
      s.abort(Ur);
    });
    var r = n.next;
    n.f & Ft ? n.parent = null : Je(n, t), n = r;
  }
}
function Yl(e) {
  for (var t = e.first; t !== null; ) {
    var n = t.next;
    t.f & ft || Je(t), t = n;
  }
}
function Je(e, t = !0) {
  var n = !1;
  (t || e.f & Ji) && e.nodes !== null && e.nodes.end !== null && (Kl(
    e.nodes.start,
    /** @type {TemplateNode} */
    e.nodes.end
  ), n = !0), e.f |= oa, zs(e, t && !n), nr(e, 0);
  var r = e.nodes && e.nodes.t;
  if (r !== null)
    for (const a of r)
      a.stop();
  ei(e), e.f ^= oa, e.f |= rt;
  var s = e.parent;
  s !== null && s.first !== null && ti(e), e.next = e.prev = e.teardown = e.ctx = e.deps = e.fn = e.nodes = e.ac = e.b = null;
}
function Kl(e, t) {
  for (; e !== null; ) {
    var n = e === t ? null : /* @__PURE__ */ or(e);
    e.remove(), e = n;
  }
}
function ti(e) {
  var t = e.parent, n = e.prev, r = e.next;
  n !== null && (n.next = r), r !== null && (r.prev = n), t !== null && (t.first === e && (t.first = r), t.last === e && (t.last = n));
}
function tn(e, t, n = !0) {
  var r = [];
  ni(e, r, !0);
  var s = () => {
    n && Je(e), t && t();
  }, a = r.length;
  if (a > 0) {
    var l = () => --a || s();
    for (var d of r)
      d.out(l);
  } else
    s();
}
function ni(e, t, n) {
  if (!(e.f & Ue)) {
    e.f ^= Ue;
    var r = e.nodes && e.nodes.t;
    if (r !== null)
      for (const d of r)
        (d.is_global || n) && t.push(d);
    for (var s = e.first; s !== null; ) {
      var a = s.next;
      if (!(s.f & Ft)) {
        var l = (s.f & Pn) !== 0 || // If this is a branch effect without a block effect parent,
        // it means the parent block effect was pruned. In that case,
        // transparency information was transferred to the branch effect.
        (s.f & ft) !== 0 && (e.f & ut) !== 0;
        ni(s, t, l ? n : !1);
      }
      s = a;
    }
  }
}
function Ir(e) {
  ri(e, !0);
}
function ri(e, t) {
  if (e.f & Ue) {
    e.f ^= Ue, e.f & Te || (we(e, Ne), sn.ensure().schedule(e));
    for (var n = e.first; n !== null; ) {
      var r = n.next, s = (n.f & Pn) !== 0 || (n.f & ft) !== 0;
      ri(n, s ? t : !1), n = r;
    }
    var a = e.nodes && e.nodes.t;
    if (a !== null)
      for (const l of a)
        (l.is_global || t) && l.in();
  }
}
function Us(e, t) {
  if (e.nodes)
    for (var n = e.nodes.start, r = e.nodes.end; n !== null; ) {
      var s = n === r ? null : /* @__PURE__ */ or(n);
      t.append(n), n = s;
    }
}
let Tr = !1, jt = !1;
function va(e) {
  jt = e;
}
let H = null, dt = !1;
function st(e) {
  H = e;
}
let Q = null;
function gt(e) {
  Q = e;
}
let mt = null;
function si(e) {
  H !== null && (mt ?? (mt = /* @__PURE__ */ new Set())).add(e);
}
let Ve = null, Ye = 0, Ze = null;
function Xl(e) {
  Ze = e;
}
let ai = 1, Gt = 0, nn = Gt;
function ha(e) {
  nn = e;
}
function ii() {
  return ++ai;
}
function cr(e) {
  var t = e.f;
  if (t & Ne)
    return !0;
  if (t & De && (e.f &= ~rn), t & bt) {
    for (var n = (
      /** @type {Value[]} */
      e.deps
    ), r = n.length, s = 0; s < r; s++) {
      var a = n[s];
      if (cr(
        /** @type {Derived} */
        a
      ) && za(
        /** @type {Derived} */
        a
      ), a.wv > e.wv)
        return !0;
    }
    t & nt && // During time traveling we don't want to reset the status so that
    // traversal of the graph in the other batches still happens
    Me === null && we(e, Te);
  }
  return !1;
}
function li(e, t, n = !0) {
  var r = e.reactions;
  if (r !== null && !(mt !== null && mt.has(e)))
    for (var s = 0; s < r.length; s++) {
      var a = r[s];
      a.f & De ? li(
        /** @type {Derived} */
        a,
        t,
        !1
      ) : t === a && (n ? we(a, Ne) : a.f & Te && we(a, bt), Os(
        /** @type {Effect} */
        a
      ));
    }
}
function oi(e) {
  var T;
  var t = Ve, n = Ye, r = Ze, s = H, a = mt, l = Be, d = dt, c = nn, h = e.f;
  Ve = /** @type {null | Value[]} */
  null, Ye = 0, Ze = null, H = h & (ft | Ft) ? null : e, mt = null, Mn(e.ctx), dt = !1, nn = ++Gt, e.ac !== null && (Wr(() => {
    e.ac.abort(Ur);
  }), e.ac = null);
  try {
    e.f |= Pr;
    var p = (
      /** @type {Function} */
      e.fn
    ), x = p();
    e.f |= On;
    var _ = e.deps, b = D == null ? void 0 : D.is_fork;
    if (Ve !== null) {
      var S;
      if (b || nr(e, Ye), _ !== null && Ye > 0)
        for (_.length = Ye + Ve.length, S = 0; S < Ve.length; S++)
          _[Ye + S] = Ve[S];
      else
        e.deps = _ = Ve;
      if (Rs() && e.f & nt)
        for (S = Ye; S < _.length; S++)
          ((T = _[S]).reactions ?? (T.reactions = [])).push(e);
    } else !b && _ !== null && Ye < _.length && (nr(e, Ye), _.length = Ye);
    if (Oa() && Ze !== null && !dt && _ !== null && !(e.f & (De | bt | Ne)))
      for (S = 0; S < /** @type {Source[]} */
      Ze.length; S++)
        li(
          Ze[S],
          /** @type {Effect} */
          e
        );
    if (s !== null && s !== e) {
      if (Gt++, s.deps !== null)
        for (let y = 0; y < n; y += 1)
          s.deps[y].rv = Gt;
      if (t !== null)
        for (const y of t)
          y.rv = Gt;
      Ze !== null && (r === null ? r = Ze : r.push(.../** @type {Source[]} */
      Ze));
    }
    return e.f & Ot && (e.f ^= Ot), x;
  } catch (y) {
    return Ra(y);
  } finally {
    e.f ^= Pr, Ve = t, Ye = n, Ze = r, H = s, mt = a, Mn(l), dt = d, nn = c;
  }
}
function Zl(e, t) {
  let n = t.reactions;
  if (n !== null) {
    var r = qi.call(n, e);
    if (r !== -1) {
      var s = n.length - 1;
      s === 0 ? n = t.reactions = null : (n[r] = n[s], n.pop());
    }
  }
  if (n === null && t.f & De && // Destroying a child effect while updating a parent effect can cause a dependency to appear
  // to be unused, when in fact it is used by the currently-updating parent. Checking `new_deps`
  // allows us to skip the expensive work of disconnecting and immediately reconnecting it
  (Ve === null || !Cr.call(Ve, t))) {
    var a = (
      /** @type {Derived} */
      t
    );
    a.f & nt && (a.f ^= nt, a.f &= ~rn), a.v !== Ee && Ms(a), Ml(a), nr(a, 0);
  }
}
function nr(e, t) {
  var n = e.deps;
  if (n !== null)
    for (var r = t; r < n.length; r++)
      Zl(e, n[r]);
}
function Dn(e) {
  var t = e.f;
  if (!(t & rt)) {
    we(e, Te);
    var n = Q, r = Tr;
    Q = e, Tr = !0;
    try {
      t & (ut | Pa) ? Yl(e) : zs(e), ei(e);
      var s = oi(e);
      e.teardown = typeof s == "function" ? s : null, e.wv = ai;
      var a;
    } finally {
      Tr = r, Q = n;
    }
  }
}
async function Ql() {
  await Promise.resolve(), Ol();
}
function i(e) {
  var t = e.f, n = (t & De) !== 0;
  if (H !== null && !dt) {
    var r = Q !== null && (Q.f & rt) !== 0;
    if (!r && (mt === null || !mt.has(e))) {
      var s = H.deps;
      if (H.f & Pr)
        e.rv < Gt && (e.rv = Gt, Ve === null && s !== null && s[Ye] === e ? Ye++ : Ve === null ? Ve = [e] : Ve.push(e));
      else {
        H.deps ?? (H.deps = []), Cr.call(H.deps, e) || H.deps.push(e);
        var a = e.reactions;
        a === null ? e.reactions = [H] : Cr.call(a, H) || a.push(H);
      }
    }
  }
  if (jt && en.has(e))
    return en.get(e);
  if (n) {
    var l = (
      /** @type {Derived} */
      e
    );
    if (jt) {
      var d = l.v;
      return (!(l.f & Te) && l.reactions !== null || ui(l)) && (d = Ns(l)), en.set(l, d), d;
    }
    var c = (l.f & nt) === 0 && !dt && H !== null && (Tr || (H.f & nt) !== 0), h = (l.f & On) === 0;
    cr(l) && (c && (l.f |= nt), za(l)), c && !h && (Ua(l), ci(l));
  }
  if (Me != null && Me.has(e))
    return Me.get(e);
  if (e.f & Ot)
    throw e.v;
  return e.v;
}
function ci(e) {
  if (e.f |= nt, e.deps !== null)
    for (const t of e.deps)
      (t.reactions ?? (t.reactions = [])).push(e), t.f & De && !(t.f & nt) && (Ua(
        /** @type {Derived} */
        t
      ), ci(
        /** @type {Derived} */
        t
      ));
}
function ui(e) {
  if (e.v === Ee) return !0;
  if (e.deps === null) return !1;
  for (const t of e.deps)
    if (en.has(t) || t.f & De && ui(
      /** @type {Derived} */
      t
    ))
      return !0;
  return !1;
}
function Hs(e) {
  var t = dt;
  try {
    return dt = !0, e();
  } finally {
    dt = t;
  }
}
const $l = ["touchstart", "touchmove"];
function eo(e) {
  return $l.includes(e);
}
const Yt = Symbol("events"), di = /* @__PURE__ */ new Set(), Ss = /* @__PURE__ */ new Set();
function to(e, t, n, r = {}) {
  function s(a) {
    if (r.capture || Ts.call(t, a), !a.cancelBubble)
      return Wr(() => n == null ? void 0 : n.call(this, a));
  }
  return e.startsWith("pointer") || e.startsWith("touch") || e === "wheel" ? It(() => {
    t.addEventListener(e, s, r);
  }) : t.addEventListener(e, s, r), s;
}
function Es(e, t, n, r, s) {
  var a = { capture: r, passive: s }, l = to(e, t, n, a);
  (t === document.body || // @ts-ignore
  t === window || // @ts-ignore
  t === document || // Firefox has quirky behavior, it can happen that we still get "canplay" events when the element is already removed
  t instanceof HTMLMediaElement) && Fs(() => {
    t.removeEventListener(e, l, a);
  });
}
function Y(e, t, n) {
  (t[Yt] ?? (t[Yt] = {}))[e] = n;
}
function Rn(e) {
  for (var t = 0; t < e.length; t++)
    di.add(e[t]);
  for (var n of Ss)
    n(e);
}
let _a = null;
function Ts(e) {
  var T, y;
  var t = this, n = (
    /** @type {Node} */
    t.ownerDocument
  ), r = e.type, s = ((T = e.composedPath) == null ? void 0 : T.call(e)) || [], a = (
    /** @type {null | Element} */
    s[0] || e.target
  );
  _a = e;
  var l = 0, d = _a === e && e[Yt];
  if (d) {
    var c = s.indexOf(d);
    if (c !== -1 && (t === document || t === /** @type {any} */
    window)) {
      e[Yt] = t;
      return;
    }
    var h = s.indexOf(t);
    if (h === -1)
      return;
    c <= h && (l = c);
  }
  if (a = /** @type {Element} */
  s[l] || e.target, a !== t) {
    zi(e, "currentTarget", {
      configurable: !0,
      get() {
        return a || n;
      }
    });
    var p = H, x = Q;
    st(null), gt(null);
    try {
      for (var _, b = []; a !== null && a !== t; ) {
        try {
          var S = (y = a[Yt]) == null ? void 0 : y[r];
          S != null && (!/** @type {any} */
          a.disabled || // DOM could've been updated already by the time this is reached, so we check this as well
          // -> the target could not have been disabled because it emits the event in the first place
          e.target === a) && S.call(a, e);
        } catch (C) {
          _ ? b.push(C) : _ = C;
        }
        if (e.cancelBubble) break;
        l++, a = l < s.length ? (
          /** @type {Element} */
          s[l]
        ) : null;
      }
      if (_) {
        for (let C of b)
          queueMicrotask(() => {
            throw C;
          });
        throw _;
      }
    } finally {
      e[Yt] = t, delete e.currentTarget, st(p), gt(x);
    }
  }
}
var Ta;
const ds = (
  // We gotta write it like this because after downleveling the pure comment may end up in the wrong location
  ((Ta = globalThis == null ? void 0 : globalThis.window) == null ? void 0 : Ta.trustedTypes) && /* @__PURE__ */ globalThis.window.trustedTypes.createPolicy("svelte-trusted-html", {
    /** @param {string} html */
    createHTML: (e) => e
  })
);
function no(e) {
  return (
    /** @type {string} */
    (ds == null ? void 0 : ds.createHTML(e)) ?? e
  );
}
function ro(e) {
  var t = Ul("template");
  return t.innerHTML = no(e.replaceAll("<!>", "<!---->")), t.content;
}
function As(e, t) {
  var n = (
    /** @type {Effect} */
    Q
  );
  n.nodes === null && (n.nodes = { start: e, end: t, a: null, t: null });
}
// @__NO_SIDE_EFFECTS__
function L(e, t) {
  var n = (t & ul) !== 0, r = (t & dl) !== 0, s, a = !e.startsWith("<!>");
  return () => {
    s === void 0 && (s = ro(a ? e : "<!>" + e), n || (s = /** @type {TemplateNode} */
    /* @__PURE__ */ Or(s)));
    var l = (
      /** @type {TemplateNode} */
      r || Ka ? document.importNode(s, !0) : s.cloneNode(!0)
    );
    if (n) {
      var d = (
        /** @type {TemplateNode} */
        /* @__PURE__ */ Or(l)
      ), c = (
        /** @type {TemplateNode} */
        l.lastChild
      );
      As(d, c);
    } else
      As(l, l);
    return l;
  };
}
function ct(e = "") {
  {
    var t = Rt(e + "");
    return As(t, t), t;
  }
}
function E(e, t) {
  e !== null && e.before(
    /** @type {Node} */
    t
  );
}
function N(e, t) {
  var n = t == null ? "" : typeof t == "object" ? `${t}` : t;
  n !== /** @type {any} */
  (e[Vn] ?? (e[Vn] = e.nodeValue)) && (e[Vn] = n, e.nodeValue = `${n}`);
}
function so(e, t) {
  return ao(e, t);
}
const yr = /* @__PURE__ */ new Map();
function ao(e, { target: t, anchor: n, props: r = {}, events: s, context: a, intro: l = !0, transformError: d }) {
  ql();
  var c = void 0, h = Bl(() => {
    var p = n ?? t.appendChild(Rt());
    wl(
      /** @type {TemplateNode} */
      p,
      {
        pending: () => {
        }
      },
      (b) => {
        ln({});
        var S = (
          /** @type {ComponentContext} */
          Be
        );
        a && (S.c = a), s && (r.$$events = s), c = e(b, r) || {}, on();
      },
      d
    );
    var x = /* @__PURE__ */ new Set(), _ = (b) => {
      for (var S = 0; S < b.length; S++) {
        var T = b[S];
        if (!x.has(T)) {
          x.add(T);
          var y = eo(T);
          for (const F of [t, document]) {
            var C = yr.get(F);
            C === void 0 && (C = /* @__PURE__ */ new Map(), yr.set(F, C));
            var ee = C.get(T);
            ee === void 0 ? (F.addEventListener(T, Ts, { passive: y }), C.set(T, 1)) : C.set(T, ee + 1);
          }
        }
      }
    };
    return _(qr(di)), Ss.add(_), () => {
      var y;
      for (var b of x)
        for (const C of [t, document]) {
          var S = (
            /** @type {Map<string, number>} */
            yr.get(C)
          ), T = (
            /** @type {number} */
            S.get(b)
          );
          --T == 0 ? (C.removeEventListener(b, Ts), S.delete(b), S.size === 0 && yr.delete(C)) : S.set(b, T);
        }
      Ss.delete(_), p !== n && ((y = p.parentNode) == null || y.removeChild(p));
    };
  });
  return io.set(c, h), c;
}
let io = /* @__PURE__ */ new WeakMap();
var ot, _t, Xe, $t, ir, lr, jr;
class lo {
  /**
   * @param {TemplateNode} anchor
   * @param {boolean} transition
   */
  constructor(t, n = !0) {
    /** @type {TemplateNode} */
    Ge(this, "anchor");
    /** @type {Map<Batch, Key>} */
    j(this, ot, /* @__PURE__ */ new Map());
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
    j(this, _t, /* @__PURE__ */ new Map());
    /**
     * Similar to #onscreen with respect to the keys, but contains branches that are not yet
     * in the DOM, because their insertion is deferred.
     * @type {Map<Key, Branch>}
     */
    j(this, Xe, /* @__PURE__ */ new Map());
    /**
     * Keys of effects that are currently outroing
     * @type {Set<Key>}
     */
    j(this, $t, /* @__PURE__ */ new Set());
    /**
     * Whether to pause (i.e. outro) on change, or destroy immediately.
     * This is necessary for `<svelte:element>`
     */
    j(this, ir, !0);
    /**
     * @param {Batch} batch
     */
    j(this, lr, (t) => {
      if (u(this, ot).has(t)) {
        var n = (
          /** @type {Key} */
          u(this, ot).get(t)
        ), r = u(this, _t).get(n);
        if (r)
          Ir(r), u(this, $t).delete(n);
        else {
          var s = u(this, Xe).get(n);
          s && (Ir(s.effect), u(this, _t).set(n, s.effect), u(this, Xe).delete(n), s.fragment.lastChild.remove(), this.anchor.before(s.fragment), r = s.effect);
        }
        for (const [a, l] of u(this, ot)) {
          if (u(this, ot).delete(a), a === t)
            break;
          const d = u(this, Xe).get(l);
          d && (Je(d.effect), u(this, Xe).delete(l));
        }
        for (const [a, l] of u(this, _t)) {
          if (a === n || u(this, $t).has(a)) continue;
          const d = () => {
            if (Array.from(u(this, ot).values()).includes(a)) {
              var h = document.createDocumentFragment();
              Us(l, h), h.append(Rt()), u(this, Xe).set(a, { effect: l, fragment: h });
            } else
              Je(l);
            u(this, $t).delete(a), u(this, _t).delete(a);
          };
          u(this, ir) || !r ? (u(this, $t).add(a), tn(l, d, !1)) : d();
        }
      }
    });
    /**
     * @param {Batch} batch
     */
    j(this, jr, (t) => {
      u(this, ot).delete(t);
      const n = Array.from(u(this, ot).values());
      for (const [r, s] of u(this, Xe))
        n.includes(r) || (Je(s.effect), u(this, Xe).delete(r));
    });
    this.anchor = t, I(this, ir, n);
  }
  /**
   *
   * @param {any} key
   * @param {null | ((target: TemplateNode) => void)} fn
   */
  ensure(t, n) {
    var r = (
      /** @type {Batch} */
      D
    ), s = Qa();
    if (n && !u(this, _t).has(t) && !u(this, Xe).has(t))
      if (s) {
        var a = document.createDocumentFragment(), l = Rt();
        a.append(l), u(this, Xe).set(t, {
          effect: tt(() => n(l)),
          fragment: a
        });
      } else
        u(this, _t).set(
          t,
          tt(() => n(this.anchor))
        );
    if (u(this, ot).set(r, t), s) {
      for (const [d, c] of u(this, _t))
        d === t ? r.unskip_effect(c) : r.skip_effect(c);
      for (const [d, c] of u(this, Xe))
        d === t ? r.unskip_effect(c.effect) : r.skip_effect(c.effect);
      r.oncommit(u(this, lr)), r.ondiscard(u(this, jr));
    } else
      u(this, lr).call(this, r);
  }
}
ot = new WeakMap(), _t = new WeakMap(), Xe = new WeakMap(), $t = new WeakMap(), ir = new WeakMap(), lr = new WeakMap(), jr = new WeakMap();
function de(e, t, n = !1) {
  var r = new lo(e), s = n ? Pn : 0;
  function a(l, d) {
    r.ensure(l, d);
  }
  qs(() => {
    var l = !1;
    t((d, c = 0) => {
      l = !0, a(c, d);
    }), l || a(-1, null);
  }, s);
}
function fi(e, t) {
  return t;
}
function oo(e, t, n) {
  for (var r = [], s = t.length, a, l = t.length, d = 0; d < s; d++) {
    let x = t[d];
    tn(
      x,
      () => {
        if (a) {
          if (a.pending.delete(x), a.done.add(x), a.pending.size === 0) {
            var _ = (
              /** @type {Set<EachOutroGroup>} */
              e.outrogroups
            );
            Cs(e, qr(a.done)), _.delete(a), _.size === 0 && (e.outrogroups = null);
          }
        } else
          l -= 1;
      },
      !1
    );
  }
  if (l === 0) {
    var c = r.length === 0 && n !== null;
    if (c) {
      var h = (
        /** @type {Element} */
        n
      ), p = (
        /** @type {Element} */
        h.parentNode
      );
      zl(p), p.append(h), e.items.clear();
    }
    Cs(e, t, !c);
  } else
    a = {
      pending: new Set(t),
      done: /* @__PURE__ */ new Set()
    }, (e.outrogroups ?? (e.outrogroups = /* @__PURE__ */ new Set())).add(a);
}
function Cs(e, t, n = !0) {
  var r;
  if (e.pending.size > 0) {
    r = /* @__PURE__ */ new Set();
    for (const l of e.pending.values())
      for (const d of l)
        r.add(
          /** @type {EachItem} */
          e.items.get(d).e
        );
  }
  for (var s = 0; s < t.length; s++) {
    var a = t[s];
    if (r != null && r.has(a)) {
      a.f |= pt;
      const l = document.createDocumentFragment();
      Us(a, l);
    } else
      Je(t[s], n);
  }
}
var pa;
function At(e, t, n, r, s, a = null) {
  var l = e, d = /* @__PURE__ */ new Map(), c = (t & Ma) !== 0;
  if (c) {
    var h = (
      /** @type {Element} */
      e
    );
    l = h.appendChild(Rt());
  }
  var p = null, x = /* @__PURE__ */ Ll(() => {
    var F = n();
    return (
      /** @type {V[]} */
      Ps(F) ? F : F == null ? [] : qr(F)
    );
  }), _, b = /* @__PURE__ */ new Map(), S = !0;
  function T(F) {
    ee.effect.f & rt || (ee.pending.delete(F), ee.fallback = p, co(ee, _, l, t, r), p !== null && (_.length === 0 ? p.f & pt ? (p.f ^= pt, Yn(p, null, l)) : Ir(p) : tn(p, () => {
      p = null;
    })));
  }
  function y(F) {
    ee.pending.delete(F);
  }
  var C = qs(() => {
    _ = /** @type {V[]} */
    i(x);
    for (var F = _.length, se = /* @__PURE__ */ new Set(), ae = (
      /** @type {Batch} */
      D
    ), fe = Qa(), A = 0; A < F; A += 1) {
      var te = _[A], ne = r(te, A), ce = S ? null : d.get(ne);
      ce ? (ce.v && Nn(ce.v, te), ce.i && Nn(ce.i, A), fe && ae.unskip_effect(ce.e)) : (ce = uo(
        d,
        S ? l : pa ?? (pa = Rt()),
        te,
        ne,
        A,
        s,
        t,
        n
      ), S || (ce.e.f |= pt), d.set(ne, ce)), se.add(ne);
    }
    if (F === 0 && a && !p && (S ? p = tt(() => a(l)) : (p = tt(() => a(pa ?? (pa = Rt()))), p.f |= pt)), F > se.size && Zi(), !S)
      if (b.set(ae, se), fe) {
        for (const [Ae, ke] of d)
          se.has(Ae) || ae.skip_effect(ke.e);
        ae.oncommit(T), ae.ondiscard(y);
      } else
        T(ae);
    i(x);
  }), ee = { effect: C, items: d, pending: b, outrogroups: null, fallback: p };
  S = !1;
}
function Wn(e) {
  for (; e !== null && !(e.f & ft); )
    e = e.next;
  return e;
}
function co(e, t, n, r, s) {
  var ce, Ae, ke, Oe, P, le, m, k, W;
  var a = (r & ol) !== 0, l = t.length, d = e.items, c = Wn(e.effect.first), h, p = null, x, _ = [], b = [], S, T, y, C;
  if (a)
    for (C = 0; C < l; C += 1)
      S = t[C], T = s(S, C), y = /** @type {EachItem} */
      d.get(T).e, y.f & pt || ((Ae = (ce = y.nodes) == null ? void 0 : ce.a) == null || Ae.measure(), (x ?? (x = /* @__PURE__ */ new Set())).add(y));
  for (C = 0; C < l; C += 1) {
    if (S = t[C], T = s(S, C), y = /** @type {EachItem} */
    d.get(T).e, e.outrogroups !== null)
      for (const R of e.outrogroups)
        R.pending.delete(y), R.done.delete(y);
    if (y.f & Ue && (Ir(y), a && ((Oe = (ke = y.nodes) == null ? void 0 : ke.a) == null || Oe.unfix(), (x ?? (x = /* @__PURE__ */ new Set())).delete(y))), y.f & pt)
      if (y.f ^= pt, y === c)
        Yn(y, null, n);
      else {
        var ee = p ? p.next : c;
        y === e.effect.last && (e.effect.last = y.prev), y.prev && (y.prev.next = y.next), y.next && (y.next.prev = y.prev), Lt(e, p, y), Lt(e, y, ee), Yn(y, ee, n), p = y, _ = [], b = [], c = Wn(p.next);
        continue;
      }
    if (y !== c) {
      if (h !== void 0 && h.has(y)) {
        if (_.length < b.length) {
          var F = b[0], se;
          p = F.prev;
          var ae = _[0], fe = _[_.length - 1];
          for (se = 0; se < _.length; se += 1)
            Yn(_[se], F, n);
          for (se = 0; se < b.length; se += 1)
            h.delete(b[se]);
          Lt(e, ae.prev, fe.next), Lt(e, p, ae), Lt(e, fe, F), c = F, p = fe, C -= 1, _ = [], b = [];
        } else
          h.delete(y), Yn(y, c, n), Lt(e, y.prev, y.next), Lt(e, y, p === null ? e.effect.first : p.next), Lt(e, p, y), p = y;
        continue;
      }
      for (_ = [], b = []; c !== null && c !== y; )
        (h ?? (h = /* @__PURE__ */ new Set())).add(c), b.push(c), c = Wn(c.next);
      if (c === null)
        continue;
    }
    y.f & pt || _.push(y), p = y, c = Wn(y.next);
  }
  if (e.outrogroups !== null) {
    for (const R of e.outrogroups)
      R.pending.size === 0 && (Cs(e, qr(R.done)), (P = e.outrogroups) == null || P.delete(R));
    e.outrogroups.size === 0 && (e.outrogroups = null);
  }
  if (c !== null || h !== void 0) {
    var A = [];
    if (h !== void 0)
      for (y of h)
        y.f & Ue || A.push(y);
    for (; c !== null; )
      !(c.f & Ue) && c !== e.fallback && A.push(c), c = Wn(c.next);
    var te = A.length;
    if (te > 0) {
      var ne = r & Ma && l === 0 ? n : null;
      if (a) {
        for (C = 0; C < te; C += 1)
          (m = (le = A[C].nodes) == null ? void 0 : le.a) == null || m.measure();
        for (C = 0; C < te; C += 1)
          (W = (k = A[C].nodes) == null ? void 0 : k.a) == null || W.fix();
      }
      oo(e, A, ne);
    }
  }
  a && It(() => {
    var R, V;
    if (x !== void 0)
      for (y of x)
        (V = (R = y.nodes) == null ? void 0 : R.a) == null || V.apply();
  });
}
function uo(e, t, n, r, s, a, l, d) {
  var c = l & il ? l & cl ? an(n) : /* @__PURE__ */ Rl(n, !1, !1) : null, h = l & ll ? an(s) : null;
  return {
    v: c,
    i: h,
    e: tt(() => (a(t, c ?? n, h ?? s, d), () => {
      e.delete(r);
    }))
  };
}
function Yn(e, t, n) {
  if (e.nodes)
    for (var r = e.nodes.start, s = e.nodes.end, a = t && !(t.f & pt) ? (
      /** @type {EffectNodes} */
      t.nodes.start
    ) : n; r !== null; ) {
      var l = (
        /** @type {TemplateNode} */
        /* @__PURE__ */ or(r)
      );
      if (a.before(r), r === s)
        return;
      r = l;
    }
}
function Lt(e, t, n) {
  t === null ? e.effect.first = n : t.next = n, n === null ? e.effect.last = t : n.prev = t;
}
function fo(e, t, n) {
  var r = e == null ? "" : "" + e;
  return r === "" ? null : r;
}
function ma(e, t = !1) {
  var n = t ? " !important;" : ";", r = "";
  for (var s of Object.keys(e)) {
    var a = e[s];
    a != null && a !== "" && (r += " " + s + ": " + a + n);
  }
  return r;
}
function vo(e, t) {
  if (t) {
    var n = "", r, s;
    return Array.isArray(t) ? (r = t[0], s = t[1]) : r = t, r && (n += ma(r)), s && (n += ma(s, !0)), n = n.trim(), n === "" ? null : n;
  }
  return String(e);
}
function at(e, t, n, r, s, a) {
  var l = (
    /** @type {any} */
    e[ps]
  );
  if (l !== n || l === void 0) {
    var d = fo(n);
    d == null ? e.removeAttribute("class") : e.className = d, e[ps] = n;
  }
  return a;
}
function fs(e, t = {}, n, r) {
  for (var s in n) {
    var a = n[s];
    t[s] !== a && (n[s] == null ? e.style.removeProperty(s) : e.style.setProperty(s, a, r));
  }
}
function bn(e, t, n, r) {
  var s = (
    /** @type {any} */
    e[ms]
  );
  if (s !== t) {
    var a = vo(t, r);
    a == null ? e.removeAttribute("style") : e.style.cssText = a, e[ms] = t;
  } else r && (Array.isArray(r) ? (fs(e, n == null ? void 0 : n[0], r[0]), fs(e, n == null ? void 0 : n[1], r[1], "important")) : fs(e, n, r));
  return r;
}
function Ws(e, t, n = !1) {
  if (e.multiple) {
    if (t == null)
      return;
    if (!Ps(t))
      return hl();
    for (var r of e.options)
      r.selected = t.includes(er(r));
    return;
  }
  for (r of e.options) {
    var s = er(r);
    if (jl(s, t)) {
      r.selected = !0;
      return;
    }
  }
  (!n || t !== void 0) && (e.selectedIndex = -1);
}
function vi(e) {
  var t = new MutationObserver(() => {
    Ws(e, e.__value);
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
  }), Fs(() => {
    t.disconnect();
  });
}
function Ar(e, t, n = t) {
  var r = /* @__PURE__ */ new WeakSet(), s = !0;
  Is(e, "change", (a) => {
    var l = a ? "[selected]" : ":checked", d;
    if (e.multiple)
      d = [].map.call(e.querySelectorAll(l), er);
    else {
      var c = e.querySelector(l) ?? // will fall back to first non-disabled option if no option is selected
      e.querySelector("option:not([disabled])");
      d = c && er(c);
    }
    n(d), e.__value = d, D !== null && r.add(D);
  }), Jl(() => {
    var a = t();
    if (e === document.activeElement) {
      var l = (
        /** @type {Batch} */
        D
      );
      if (r.has(l))
        return;
    }
    if (Ws(e, a, s), s && a === void 0) {
      var d = e.querySelector(":checked");
      d !== null && (a = er(d), n(a));
    }
    e.__value = a, s = !1;
  }), vi(e);
}
function er(e) {
  return "__value" in e ? e.__value : e.value;
}
const ho = Symbol("is custom element"), _o = Symbol("is html"), po = Ki ? "progress" : "PROGRESS";
function ba(e, t) {
  var n = Vs(e);
  n.value === (n.value = // treat null and undefined the same for the initial value
  t ?? void 0) || // @ts-expect-error
  // `progress` elements always need their value set when it's `0`
  e.value === t && (t !== 0 || e.nodeName !== po) || (e.value = t ?? "");
}
function mo(e, t) {
  var n = Vs(e);
  n.checked !== (n.checked = // treat null and undefined the same for the initial value
  t ?? void 0) && (e.checked = t);
}
function ue(e, t, n, r) {
  var s = Vs(e);
  s[t] !== (s[t] = n) && (t === "loading" && (e[Yi] = n), n == null ? e.removeAttribute(t) : typeof n != "string" && bo(e).includes(t) ? e[t] = n : e.setAttribute(t, n));
}
function Vs(e) {
  return (
    /** @type {Record<string | symbol, unknown>} **/
    /** @type {any} */
    e[wr] ?? (e[wr] = {
      [ho]: e.nodeName.includes("-"),
      [_o]: e.namespaceURI === fl
    })
  );
}
var ga = /* @__PURE__ */ new Map();
function bo(e) {
  var t = e.getAttribute("is") || e.nodeName, n = ga.get(t);
  if (n) return n;
  ga.set(t, n = []);
  for (var r, s = e, a = Element.prototype; a !== s; ) {
    r = Ui(s);
    for (var l in r)
      r[l].set && // better safe than sorry, we don't want spread attributes to mess with HTML content
      l !== "innerHTML" && l !== "textContent" && l !== "innerText" && n.push(l);
    s = Ca(s);
  }
  return n;
}
function ve(e, t, n = t) {
  var r = /* @__PURE__ */ new WeakSet();
  Is(e, "input", async (s) => {
    var a = s ? e.defaultValue : e.value;
    if (a = vs(e) ? hs(a) : a, n(a), D !== null && r.add(D), await Ql(), a !== (a = t())) {
      var l = e.selectionStart, d = e.selectionEnd, c = e.value.length;
      if (e.value = a ?? "", d !== null) {
        var h = e.value.length;
        l === d && d === c && h > c ? (e.selectionStart = h, e.selectionEnd = h) : (e.selectionStart = l, e.selectionEnd = Math.min(d, h));
      }
    }
  }), // If we are hydrating and the value has since changed,
  // then use the updated value from the input instead.
  // If defaultValue is set, then value == defaultValue
  // TODO Svelte 6: remove input.value check and set to empty string?
  Hs(t) == null && e.value && (n(vs(e) ? hs(e.value) : e.value), D !== null && r.add(D)), js(() => {
    var s = t();
    if (e === document.activeElement) {
      var a = (
        /** @type {Batch} */
        D
      );
      if (r.has(a))
        return;
    }
    vs(e) && s === hs(e.value) || e.type === "date" && !s && !e.value || s !== e.value && (e.value = s ?? "");
  });
}
function ya(e, t, n = t) {
  Is(e, "change", (r) => {
    var s = r ? e.defaultChecked : e.checked;
    n(s);
  }), // If we are hydrating and the value has since changed,
  // then use the update value from the input instead.
  // If defaultChecked is set, then checked == defaultChecked
  Hs(t) == null && n(e.checked), js(() => {
    var r = t();
    e.checked = !!r;
  });
}
function vs(e) {
  var t = e.type;
  return t === "number" || t === "range";
}
function hs(e) {
  return e === "" ? null : +e;
}
function hi(e, t, n, r) {
  var s = (
    /** @type {Derived<V> | undefined} */
    void 0
  ), a = () => (s ?? (s = /* @__PURE__ */ Hr(
    /** @type {() => V} */
    r
  )), i(s)), l;
  l = /** @type {V} */
  e[t], l === void 0 && r !== void 0 && (l = a());
  var d;
  return d = () => {
    var c = (
      /** @type {V} */
      e[t]
    );
    return c === void 0 ? a() : c;
  }, d;
}
const go = "5";
var Aa;
typeof window < "u" && ((Aa = window.__svelte ?? (window.__svelte = {})).v ?? (Aa.v = /* @__PURE__ */ new Set())).add(go);
function _i(e) {
  return e.replace(/[\u2018\u2019]/g, "'").replace(/[\u201C\u201D]/g, '"');
}
function yo(e) {
  if (!e) return null;
  const t = e.trim();
  if (/^\d+$/.test(t))
    return parseInt(t);
  const n = t.match(/thesession\.org\/tunes\/(\d+)/i);
  return n ? parseInt(n[1]) : null;
}
function wa(e) {
  const [t, n] = e.split(":"), r = parseInt(t), s = r >= 12 ? "pm" : "am";
  return `${r === 0 ? 12 : r > 12 ? r - 12 : r}:${n}${s}`;
}
function pi(e, t, n) {
  return e < t ? n === "asc" ? -1 : 1 : e > t ? n === "asc" ? 1 : -1 : 0;
}
function ka(e, t) {
  switch (t) {
    case "name":
      return e.name.toLowerCase();
    case "email":
      return (e.email || "").toLowerCase();
    case "attendance":
      return e.attendance_count || 0;
    case "last_attended":
      return e.last_attended ? new Date(e.last_attended).getTime() : 0;
    default:
      return 0;
  }
}
function xa(e, t) {
  switch (t) {
    case "tune_name":
      return e.tune_name.toLowerCase();
    case "session_alias":
      return (e.session_alias || "").toLowerCase();
    case "tune_type":
      return (e.tune_type || "").toLowerCase();
    case "session_key":
      return (e.session_key || "").toLowerCase();
    case "setting_key":
      return (e.setting_key || "").toLowerCase();
    case "play_count":
      return e.play_count || 0;
    case "want_to_learn":
      return e.want_to_learn_count || 0;
    case "learning":
      return e.learning_count || 0;
    case "learned":
      return e.learned_count || 0;
    default:
      return 0;
  }
}
function wo(e, t) {
  const n = _i(t.toLowerCase());
  if (!n) return e;
  const r = yo(t);
  return e.filter((s) => {
    const a = r && s.tune_id === r, l = s.tune_name.toLowerCase().includes(n) || (s.session_alias || "").toLowerCase().includes(n) || s.tune_type && s.tune_type.toLowerCase().includes(n) || (s.session_key || "").toLowerCase().includes(n) || (s.setting_key || "").toLowerCase().includes(n);
    return a || l;
  });
}
var ko = /* @__PURE__ */ L("<option> </option>"), xo = /* @__PURE__ */ L('<div class="mb-3"><label for="termination-date" class="form-label">Last Session Date</label> <input type="date" class="form-control" id="termination-date"/> <div class="mt-2"><a href="#reactivate" id="reactivate-session-link" class="text-success"><i class="fas fa-play-circle"></i> Reactivate session</a></div></div>'), So = /* @__PURE__ */ L('<div class="mb-3"><div class="alert alert-warning"><strong>Session Status:</strong> This session is currently active</div> <a href="#deactivate" id="deactivate-session-link" class="text-danger"><i class="fas fa-stop-circle"></i> Mark this session as inactive</a></div>'), Eo = /* @__PURE__ */ L('<div class="recurrence-display p-3 border rounded bg-light"><div class="d-flex justify-content-between align-items-start"><div class="recurrence-text"> </div> <button type="button" class="btn btn-sm btn-outline-primary"><i class="fas fa-edit"></i> Edit</button></div></div>'), To = /* @__PURE__ */ L('<div class="recurrence-display p-3 border rounded bg-light text-muted"><div class="d-flex justify-content-between align-items-center"><div>No recurrence pattern set</div> <button type="button" class="btn btn-sm btn-primary"><i class="fas fa-plus"></i> Add Schedule</button></div></div>'), Ao = /* @__PURE__ */ L('<button type="button"> </button>'), Co = /* @__PURE__ */ L('<label class="nth-checkbox-label"><input type="checkbox" class="nth-occurrence"/> <span> </span></label>'), Lo = /* @__PURE__ */ L('<div class="schedule-form"><div class="schedule-form-header"><span class="schedule-form-title"> </span> <button type="button" class="btn btn-sm btn-outline-danger"><i class="fas fa-trash"></i> Remove</button></div> <div class="mb-3"><span class="form-label">Pattern Type</span> <select class="form-select schedule-type"><option>Weekly</option><option>Monthly (Nth Weekday)</option></select></div> <div class="mb-3"><span class="form-label">Weekday</span> <div class="weekday-buttons"></div></div> <div class="weekly-options"><div class="mb-3"><span class="form-label">Frequency</span> <select class="form-select schedule-frequency"><option>Every week</option><option>Every 2 weeks</option><option>Every 3 weeks</option><option>Every 4 weeks</option></select></div></div> <div class="monthly-options"><div class="mb-3"><span class="form-label">Which occurrences?</span> <div class="nth-occurrence-checkboxes"></div></div></div> <div class="row"><div class="col-md-6 mb-3"><label class="form-label">Start Time</label> <input type="time" class="form-control schedule-start-time"/></div> <div class="col-md-6 mb-3"><label class="form-label">End Time</label> <input type="time" class="form-control schedule-end-time"/></div></div></div>'), Po = /* @__PURE__ */ L("<li> </li>"), Mo = /* @__PURE__ */ L('<div class="modal show" id="terminationDateModal" aria-labelledby="terminationDateModalLabel" style="display: flex;" role="presentation"><div class="modal-dialog"><div class="modal-content"><div class="modal-header"><h5 class="modal-title" id="terminationDateModalLabel">Set Session End Date</h5> <button type="button" class="btn-close" aria-label="Close">&times;</button></div> <div class="modal-body"><p class="mb-3">What was the last date of the session?</p> <div class="mb-3"><label for="modal-termination-date" class="form-label">Last Session Date</label> <input type="date" class="form-control" id="modal-termination-date" required=""/></div> <div id="modal-error-message" class="alert alert-danger"> </div></div> <div class="modal-footer"><button type="button" class="btn btn-secondary">Cancel</button> <button type="button" class="btn btn-danger" id="save-termination-date">Save</button></div></div></div></div>'), No = /* @__PURE__ */ L(
  `<section class="docs-section"><h2 class="section-heading">Session Details</h2> <form id="session-details-form"><input type="hidden" id="session-id"/> <div class="row"><div class="col-md-6"><div class="mb-3"><label for="session-name" class="form-label">Session Name</label> <input type="text" class="form-control" id="session-name"/></div> <div class="mb-3"><label for="session-path" class="form-label">URL Path</label> <input type="text" class="form-control" id="session-path"/></div> <div class="mb-3"><label for="location-name" class="form-label">Location Name</label> <input type="text" class="form-control" id="location-name"/></div> <div class="mb-3"><label for="location-street" class="form-label">Street Address</label> <input type="text" class="form-control" id="location-street"/></div></div> <div class="col-md-6"><div class="mb-3"><label for="city" class="form-label">City</label> <input type="text" class="form-control" id="city"/></div> <div class="mb-3"><label for="state" class="form-label">State</label> <input type="text" class="form-control" id="state"/></div> <div class="mb-3"><label for="country" class="form-label">Country</label> <input type="text" class="form-control" id="country"/></div> <div class="mb-3"><label for="timezone" class="form-label">Timezone</label> <select class="form-select" id="timezone" name="timezone"></select></div></div></div> <div class="row"><div class="col-md-6"><div class="mb-3"><label for="location-phone" class="form-label">Location Phone</label> <input type="tel" class="form-control" id="location-phone"/></div> <div class="mb-3"><label for="location-website" class="form-label">Location Website</label> <input type="url" class="form-control" id="location-website"/></div> <div class="mb-3"><label for="initiation-date" class="form-label">First Session Date</label> <input type="date" class="form-control" id="initiation-date"/></div></div> <div class="col-md-6"><!> <div class="mb-3"><div class="form-check"><input class="form-check-input" type="checkbox" id="unlisted-address"/> <label class="form-check-label" for="unlisted-address">Hide address from public</label></div></div></div></div> <div class="mb-3"><span class="form-label">Recurrence Schedule</span> <div id="recurrence-readonly-view"><!></div> <div id="recurrence-edit-view"><div id="recurrence-schedules-container"></div> <button type="button" class="btn btn-sm btn-outline-primary mt-2"><i class="fas fa-plus"></i> Add Schedule</button> <div id="recurrence-preview" class="mt-3 p-3 border rounded bg-light"><h6 class="mb-2">Next 5 Occurrences:</h6> <ul id="recurrence-preview-list" class="mb-0"></ul></div> <div class="mt-3"><button type="button" class="btn btn-sm btn-secondary">Cancel</button> <button type="button" class="btn btn-sm btn-primary">Save</button></div></div></div> <div class="mb-3"><span class="form-label">Auto-Create Instances</span> <div class="p-3 border rounded bg-light"><div class="form-check mb-2"><input class="form-check-input" type="checkbox" id="auto-create-instances"/> <label class="form-check-label" for="auto-create-instances">Automatically create session instances ahead of time</label></div> <div class="d-flex align-items-center gap-2" id="auto-create-hours-container"><label for="auto-create-hours" class="form-label mb-0">Create instances</label> <input type="number" class="form-control" id="auto-create-hours" min="1" max="168" style="width: 80px;"/> <span>hours ahead</span></div> <small class="text-muted d-block mt-2">When enabled, the system will automatically create upcoming session instances based on the recurrence pattern.
          This runs every 15 minutes.</small></div></div> <div class="mb-3"><label for="comments" class="form-label">Comments</label> <textarea class="form-control" id="comments" rows="4"></textarea></div> <button type="submit" class="btn btn-primary">Save Changes</button></form></section> <!>`,
  1
);
function Do(e, t) {
  ln(t, !0);
  let n = hi(t, "timezoneOptions", 19, () => []);
  const r = (v, g) => window.showMessage && window.showMessage(v, g);
  let s = /* @__PURE__ */ M(ge(t.session.name || "")), a = /* @__PURE__ */ M(ge(t.session.path || "")), l = /* @__PURE__ */ M(ge(t.session.location_name || "")), d = /* @__PURE__ */ M(ge(t.session.location_street || "")), c = /* @__PURE__ */ M(ge(t.session.city || "")), h = /* @__PURE__ */ M(ge(t.session.state || "")), p = /* @__PURE__ */ M(ge(t.session.country || "")), x = /* @__PURE__ */ M(ge(t.session.timezone)), _ = /* @__PURE__ */ M(ge(t.session.location_phone || "")), b = /* @__PURE__ */ M(ge(t.session.location_website || "")), S = /* @__PURE__ */ M(ge(t.session.initiation_date || "")), T = /* @__PURE__ */ M(ge(t.session.termination_date || "")), y = /* @__PURE__ */ M(!!t.session.unlisted_address), C = /* @__PURE__ */ M(ge(t.session.comments || "")), ee = /* @__PURE__ */ M(!!t.session.auto_create_instances), F = /* @__PURE__ */ M(ge(String(t.session.auto_create_hours_ahead)));
  function se() {
    const v = {
      name: i(s).trim(),
      path: i(a).trim(),
      location_name: i(l).trim(),
      location_street: i(d).trim(),
      city: i(c).trim(),
      state: i(h).trim(),
      country: i(p).trim(),
      timezone: i(x),
      location_website: i(b).trim(),
      location_phone: i(_).trim(),
      initiation_date: i(S),
      unlisted_address: i(y),
      comments: i(C).trim(),
      auto_create_instances: i(ee),
      auto_create_hours_ahead: parseInt(i(F)) || 24
    };
    if (t.session.termination_date && (v.termination_date = i(T)), !v.name) {
      r("Session name is required", "error");
      return;
    }
    if (!v.path) {
      r("URL path is required", "error");
      return;
    }
    fetch(`/api/sessions/${t.sessionPath}/admin-update`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(v)
    }).then((g) => g.json()).then((g) => {
      g.success ? r(g.message || "Session details saved successfully", "success") : r(g.error || "Failed to save session details", "error");
    }).catch((g) => {
      console.error("Error saving session details:", g), r("An error occurred while saving session details", "error");
    });
  }
  let ae = /* @__PURE__ */ M(!1), fe = /* @__PURE__ */ M(""), A = /* @__PURE__ */ M("");
  function te() {
    w(A, ""), w(fe, ""), w(ae, !0), document.body.classList.add("modal-open");
  }
  function ne() {
    w(ae, !1), document.body.classList.remove("modal-open");
  }
  function ce(v) {
    v.key === "Escape" && i(ae) && ne();
  }
  function Ae() {
    if (!i(fe)) {
      w(A, "Please select a date.");
      return;
    }
    ke(i(fe));
  }
  function ke(v) {
    fetch(`/api/admin/sessions/${t.sessionPath}/terminate`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ termination_date: v })
    }).then((g) => g.json()).then((g) => {
      g.success ? (ne(), window.location.reload()) : w(A, g.error || "Failed to set termination date", !0);
    }).catch((g) => {
      console.error("Error setting termination date:", g), w(A, "An error occurred while setting the termination date");
    });
  }
  function Oe() {
    fetch(`/api/admin/sessions/${t.sessionPath}/reactivate`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" }
    }).then((v) => v.json()).then((v) => {
      v.success ? window.location.reload() : alert("Error: " + (v.error || "Failed to reactivate session"));
    }).catch((v) => {
      console.error("Error reactivating session:", v), alert("An error occurred while reactivating the session");
    });
  }
  const P = [
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday"
  ], le = [
    { value: 1, label: "1st" },
    { value: 2, label: "2nd" },
    { value: 3, label: "3rd" },
    { value: 4, label: "4th" },
    { value: -1, label: "Last" }
  ];
  let m = /* @__PURE__ */ M(!1), k = /* @__PURE__ */ M(ge(
    []
    // [{id, type, weekday, start_time, end_time, every_n_weeks, which:Set-like array}]
  )), W = 0;
  function R(v = null) {
    return {
      id: W++,
      type: (v == null ? void 0 : v.type) || "weekly",
      weekday: (v == null ? void 0 : v.weekday) || "monday",
      start_time: (v == null ? void 0 : v.start_time) || "19:00",
      end_time: (v == null ? void 0 : v.end_time) || "22:00",
      every_n_weeks: (v == null ? void 0 : v.every_n_weeks) || 1,
      which: v != null && v.which ? [...v.which] : [1]
    };
  }
  function V() {
    w(m, !0), w(k, [], !0), W = 0;
    const v = t.session.recurrence || "";
    if (v)
      try {
        const g = typeof v == "string" ? JSON.parse(v) : v;
        g.schedules && Array.isArray(g.schedules) && w(k, g.schedules.map((U) => R(U)), !0);
      } catch (g) {
        console.error("Error parsing recurrence JSON:", g);
      }
    i(k).length === 0 && w(k, [R()], !0);
  }
  function B() {
    w(m, !1), w(k, [], !0), W = 0;
  }
  function ie() {
    w(k, [...i(k), R()], !0);
  }
  function he(v) {
    w(k, i(k).filter((g) => g.id !== v), !0);
  }
  function xe(v, g) {
    v.weekday = g, w(k, [...i(k)], !0);
  }
  function Ce(v, g, U) {
    U ? v.which.includes(g) || (v.which = [...v.which, g]) : v.which = v.which.filter((be) => be !== g), w(k, [...i(k)], !0);
  }
  function Ie() {
    return i(k).map((v) => {
      const g = {
        type: v.type,
        weekday: v.weekday,
        start_time: v.start_time,
        end_time: v.end_time
      };
      return v.type === "weekly" ? g.every_n_weeks = parseInt(v.every_n_weeks) : v.type === "monthly_nth_weekday" && (g.which = v.which.map((U) => parseInt(U))), g;
    });
  }
  const q = /* @__PURE__ */ Pt(() => Ie().map((v, g) => {
    let U = `Schedule ${g + 1}: ${v.weekday}s`;
    if (v.type === "weekly")
      U += v.every_n_weeks > 1 ? ` (every ${v.every_n_weeks} weeks)` : "";
    else {
      const be = (v.which || []).map((je) => je === -1 ? "last" : ["1st", "2nd", "3rd", "4th"][je - 1]);
      U += ` (${be.join(", ")} of month)`;
    }
    return U += ` from ${wa(v.start_time)} to ${wa(v.end_time)}`, U;
  }));
  function X() {
    const v = Ie();
    if (v.length === 0) {
      z("");
      return;
    }
    for (let U of v) {
      if (!U.weekday || !U.start_time || !U.end_time) {
        r("All schedules must have a weekday, start time, and end time", "error");
        return;
      }
      if (U.type === "monthly_nth_weekday" && (!U.which || U.which.length === 0)) {
        r("Monthly patterns must have at least one occurrence selected", "error");
        return;
      }
    }
    const g = JSON.stringify({ schedules: v }, null, 2);
    z(g);
  }
  function z(v) {
    if (v)
      try {
        JSON.parse(v);
      } catch {
        r("Invalid JSON format. Please check your recurrence pattern.", "error");
        return;
      }
    fetch(`/api/sessions/${t.sessionPath}/admin-update`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ recurrence: v })
    }).then((g) => g.json()).then((g) => {
      g.success ? (r("Recurrence schedule updated successfully", "success"), setTimeout(() => window.location.reload(), 1e3)) : r(g.error || "Failed to update recurrence schedule", "error");
    }).catch((g) => {
      console.error("Error saving recurrence:", g), r("An error occurred while saving the recurrence schedule", "error");
    });
  }
  const Le = (v) => v.charAt(0).toUpperCase() + v.slice(1, 3);
  var me = No();
  Es("keydown", Dr, ce);
  var G = tr(me), Re = f(o(G), 2), Fe = o(Re), _e = f(Fe, 2), Se = o(_e), re = o(Se), Pe = f(o(re), 2), yt = f(re, 2), Fn = f(o(yt), 2), qt = f(yt, 2), jn = f(o(qt), 2), cn = f(qt, 2), qn = f(o(cn), 2), zt = f(Se, 2), un = o(zt), zn = f(o(un), 2), dn = f(un, 2), fn = f(o(dn), 2), Ut = f(dn, 2), Un = f(o(Ut), 2), Hn = f(Ut, 2), Ht = f(o(Hn), 2);
  At(Ht, 21, n, (v) => v.value, (v, g) => {
    var U = ko(), be = o(U), je = {};
    K(() => {
      N(be, i(g).label), je !== (je = i(g).value) && (U.value = (U.__value = i(g).value) ?? "");
    }), E(v, U);
  });
  var Z = f(_e, 2), pe = o(Z), vn = o(pe), Br = f(o(vn), 2), ur = f(vn, 2), dr = f(o(ur), 2), Jr = f(ur, 2), Gr = f(o(Jr), 2), Yr = f(pe, 2), fr = o(Yr);
  {
    var Kr = (v) => {
      var g = xo(), U = f(o(g), 2), be = f(U, 2), je = o(be);
      ve(U, () => i(T), (vt) => w(T, vt)), Y("click", je, (vt) => {
        vt.preventDefault(), confirm("Are you sure you want to reactivate this session? This will remove the termination date.") && Oe();
      }), E(v, g);
    }, Xr = (v) => {
      var g = So(), U = f(o(g), 2);
      Y("click", U, (be) => {
        be.preventDefault(), te();
      }), E(v, g);
    };
    de(fr, (v) => {
      t.session.termination_date ? v(Kr) : v(Xr, -1);
    });
  }
  var Zr = f(fr, 2), O = o(Zr), J = o(O), Bs = f(Z, 2), Qr = f(o(Bs), 2);
  let Js;
  var mi = o(Qr);
  {
    var bi = (v) => {
      var g = Eo(), U = o(g), be = o(U), je = o(be), vt = f(be, 2);
      K(() => N(je, t.session.recurrence_readable)), Y("click", vt, V), E(v, g);
    }, gi = (v) => {
      var g = To(), U = o(g), be = f(o(U), 2);
      Y("click", be, V), E(v, g);
    };
    de(mi, (v) => {
      t.session.recurrence_readable ? v(bi) : v(gi, -1);
    });
  }
  var Gs = f(Qr, 2);
  let Ys;
  var Ks = o(Gs);
  At(Ks, 23, () => i(k), (v) => v.id, (v, g, U) => {
    var be = Lo(), je = o(be), vt = o(je), vr = o(vt), hr = f(vt, 2), _r = f(je, 2), hn = f(o(_r), 2), _n = o(hn);
    _n.value = _n.__value = "weekly";
    var pr = f(_n);
    pr.value = pr.__value = "monthly_nth_weekday";
    var mr = f(_r, 2), br = f(o(mr), 2);
    At(br, 20, () => P, (qe) => qe, (qe, wt) => {
      var kt = Ao(), Vt = o(kt);
      K(
        (is) => {
          at(kt, 1, `weekday-btn ${wt === i(g).weekday ? "active" : ""}`), ue(kt, "data-schedule-id", i(g).id), ue(kt, "data-weekday", wt), N(Vt, is);
        },
        [() => Le(wt)]
      ), Y("click", kt, () => xe(i(g), wt)), E(qe, kt);
    });
    var pn = f(mr, 2);
    let Wt;
    var Mi = o(pn), es = f(o(Mi), 2), ts = o(es);
    ts.value = ts.__value = 1;
    var ns = f(ts);
    ns.value = ns.__value = 2;
    var rs = f(ns);
    rs.value = rs.__value = 3;
    var ta = f(rs);
    ta.value = ta.__value = 4;
    var gr = f(pn, 2);
    let na;
    var Ni = o(gr), Di = f(o(Ni), 2);
    At(Di, 21, () => le, (qe) => qe.value, (qe, wt) => {
      var kt = Co(), Vt = o(kt), is = f(Vt, 2), Ri = o(is);
      K(
        (ls) => {
          ue(Vt, "data-schedule-id", i(g).id), ba(Vt, i(wt).value), mo(Vt, ls), N(Ri, i(wt).label);
        },
        [() => i(g).which.includes(i(wt).value)]
      ), Y("change", Vt, (ls) => Ce(i(g), i(wt).value, ls.currentTarget.checked)), E(qe, kt);
    });
    var Oi = f(gr, 2), ra = o(Oi), sa = o(ra), ss = f(sa, 2), Ii = f(ra, 2), aa = o(Ii), as = f(aa, 2);
    K(() => {
      ue(be, "id", `schedule-${i(g).id ?? ""}`), N(vr, `Schedule ${i(g).id + 1}`), ue(hn, "data-schedule-id", i(g).id), ue(pn, "id", `weekly-options-${i(g).id ?? ""}`), Wt = bn(pn, "", Wt, { display: i(g).type === "weekly" ? "" : "none" }), ue(es, "data-schedule-id", i(g).id), ue(gr, "id", `monthly-options-${i(g).id ?? ""}`), na = bn(gr, "", na, {
        display: i(g).type === "monthly_nth_weekday" ? "" : "none"
      }), ue(sa, "for", `schedule-start-${i(g).id ?? ""}`), ue(ss, "id", `schedule-start-${i(g).id ?? ""}`), ue(ss, "data-schedule-id", i(g).id), ue(aa, "for", `schedule-end-${i(g).id ?? ""}`), ue(as, "id", `schedule-end-${i(g).id ?? ""}`), ue(as, "data-schedule-id", i(g).id);
    }), Y("click", hr, () => he(i(g).id)), Ar(hn, () => i(g).type, (qe) => i(g).type = qe), Ar(es, () => i(g).every_n_weeks, (qe) => i(g).every_n_weeks = qe), ve(ss, () => i(g).start_time, (qe) => i(g).start_time = qe), ve(as, () => i(g).end_time, (qe) => i(g).end_time = qe), E(v, be);
  });
  var Xs = f(Ks, 2), $r = f(Xs, 2);
  let Zs;
  var yi = f(o($r), 2);
  At(yi, 21, () => i(q), fi, (v, g) => {
    var U = Po(), be = o(U);
    K(() => N(be, i(g))), E(v, U);
  });
  var wi = f($r, 2), Qs = o(wi), ki = f(Qs, 2), $s = f(Bs, 2), xi = f(o($s), 2), ea = o(xi), Si = o(ea), Ei = f(ea, 2), Ti = f(o(Ei), 2), Ai = f($s, 2), Ci = f(o(Ai), 2), Li = f(G, 2);
  {
    var Pi = (v) => {
      var g = Mo(), U = o(g), be = o(U), je = o(be), vt = f(o(je), 2), vr = f(je, 2), hr = f(o(vr), 2), _r = f(o(hr), 2), hn = f(hr, 2);
      let _n;
      var pr = o(hn), mr = f(vr, 2), br = o(mr), pn = f(br, 2);
      K(() => {
        _n = bn(hn, "", _n, { display: i(A) ? "block" : "none" }), N(pr, i(A));
      }), Y("click", g, (Wt) => {
        Wt.target === Wt.currentTarget && ne();
      }), Y("click", vt, ne), ve(_r, () => i(fe), (Wt) => w(fe, Wt)), Y("click", br, ne), Y("click", pn, Ae), E(v, g);
    };
    de(Li, (v) => {
      i(ae) && v(Pi);
    });
  }
  K(() => {
    ba(Fe, t.session.session_id), Js = bn(Qr, "", Js, { display: i(m) ? "none" : "" }), Ys = bn(Gs, "", Ys, { display: i(m) ? "" : "none" }), Zs = bn($r, "", Zs, { display: i(q).length ? "block" : "none" });
  }), Es("submit", Re, (v) => {
    v.preventDefault(), se();
  }), ve(Pe, () => i(s), (v) => w(s, v)), ve(Fn, () => i(a), (v) => w(a, v)), ve(jn, () => i(l), (v) => w(l, v)), ve(qn, () => i(d), (v) => w(d, v)), ve(zn, () => i(c), (v) => w(c, v)), ve(fn, () => i(h), (v) => w(h, v)), ve(Un, () => i(p), (v) => w(p, v)), Ar(Ht, () => i(x), (v) => w(x, v)), ve(Br, () => i(_), (v) => w(_, v)), ve(dr, () => i(b), (v) => w(b, v)), ve(Gr, () => i(S), (v) => w(S, v)), ya(J, () => i(y), (v) => w(y, v)), Y("click", Xs, ie), Y("click", Qs, B), Y("click", ki, X), ya(Si, () => i(ee), (v) => w(ee, v)), ve(Ti, () => i(F), (v) => w(F, v)), ve(Ci, () => i(C), (v) => w(C, v)), E(e, me), on();
}
Rn(["click", "change"]);
var Oo = /* @__PURE__ */ L('<div class="alert alert-danger"> </div>'), Io = /* @__PURE__ */ L('<p class="text-muted">Loading tunes...</p>'), Ro = /* @__PURE__ */ L('<div class="alert alert-info">No tunes have been played at this session yet.</div>'), Fo = /* @__PURE__ */ L('<div class="alert alert-info">No tunes match the search criteria.</div>'), Bt = /* @__PURE__ */ L('<span class="text-muted">-</span>'), jo = /* @__PURE__ */ L('<tr><td class="tune-name"><a class="tune-link"> </a></td><td class="tune-alias"><!></td><td class="tune-type"><!></td><td class="tune-session-key"><!></td><td class="tune-setting-key"><!></td><td class="tune-play-count text-center"> </td><td class="tune-want-to-learn text-center"><!></td><td class="tune-learning text-center"><!></td><td class="tune-learned text-center"><!></td></tr>'), qo = /* @__PURE__ */ L('<div class="table-responsive"><table class="table table-striped" id="tunes-table"><thead><tr><th style="cursor: pointer;"> </th><th style="cursor: pointer;"> </th><th style="cursor: pointer;"> </th><th style="cursor: pointer;"> </th><th style="cursor: pointer;"> </th><th style="cursor: pointer; text-align: center;"> </th><th style="cursor: pointer; text-align: center;"> </th><th style="cursor: pointer; text-align: center;"> </th><th style="cursor: pointer; text-align: center;"> </th></tr></thead><tbody></tbody></table></div>'), zo = /* @__PURE__ */ L('<section class="docs-section"><div class="mb-3"><div class="d-flex align-items-center gap-3"><div class="flex-grow-1"><input type="text" class="form-control" id="tunes-search" placeholder="Search tunes..." autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false"/></div></div></div> <div id="tunes-content"><!></div></section>');
function Uo(e, t) {
  ln(t, !0);
  let n = /* @__PURE__ */ M(
    null
    // null until loaded
  ), r = /* @__PURE__ */ M(null), s = /* @__PURE__ */ M(""), a = /* @__PURE__ */ M("tune_name"), l = /* @__PURE__ */ M("asc"), d = !1;
  Vr(() => {
    t.load && !d && (d = !0, fetch(`/api/admin/sessions/${t.sessionPath}/tunes`).then((A) => A.json()).then((A) => {
      if (A.error) {
        w(r, A.error, !0);
        return;
      }
      w(n, A.tunes, !0);
    }).catch((A) => {
      w(r, `Failed to load tunes: ${A}`);
    }));
  });
  function c(A) {
    i(a) === A ? w(l, i(l) === "asc" ? "desc" : "asc", !0) : (w(a, A, !0), w(l, "asc"));
  }
  const h = /* @__PURE__ */ Pt(() => i(n) ? [...wo(i(n), i(s))].sort((te, ne) => pi(xa(te, i(a)), xa(ne, i(a)), i(l))) : []), p = (A) => i(a) !== A ? "" : i(l) === "asc" ? " ↑" : " ↓";
  var x = zo(), _ = o(x), b = o(_), S = o(b), T = o(S), y = f(_, 2), C = o(y);
  {
    var ee = (A) => {
      var te = Oo(), ne = o(te);
      K(() => N(ne, i(r))), E(A, te);
    }, F = (A) => {
      var te = Io();
      E(A, te);
    }, se = (A) => {
      var te = Ro();
      E(A, te);
    }, ae = (A) => {
      var te = Fo();
      E(A, te);
    }, fe = (A) => {
      var te = qo(), ne = o(te), ce = o(ne), Ae = o(ce), ke = o(Ae), Oe = o(ke), P = f(ke), le = o(P), m = f(P), k = o(m), W = f(m), R = o(W), V = f(W), B = o(V), ie = f(V), he = o(ie), xe = f(ie), Ce = o(xe), Ie = f(xe), q = o(Ie), X = f(Ie), z = o(X), Le = f(ce);
      At(Le, 21, () => i(h), (me) => me.tune_id, (me, G) => {
        var Re = jo(), Fe = o(Re), _e = o(Fe), Se = o(_e), re = f(Fe), Pe = o(re);
        {
          var yt = (O) => {
            var J = ct();
            K(() => N(J, i(G).session_alias)), E(O, J);
          }, Fn = (O) => {
            var J = Bt();
            E(O, J);
          };
          de(Pe, (O) => {
            i(G).session_alias && i(G).session_alias !== i(G).tune_name ? O(yt) : O(Fn, -1);
          });
        }
        var qt = f(re), jn = o(qt);
        {
          var cn = (O) => {
            var J = ct();
            K(() => N(J, i(G).tune_type)), E(O, J);
          }, qn = (O) => {
            var J = Bt();
            E(O, J);
          };
          de(jn, (O) => {
            i(G).tune_type ? O(cn) : O(qn, -1);
          });
        }
        var zt = f(qt), un = o(zt);
        {
          var zn = (O) => {
            var J = ct();
            K(() => N(J, i(G).session_key)), E(O, J);
          }, dn = (O) => {
            var J = Bt();
            E(O, J);
          };
          de(un, (O) => {
            i(G).session_key ? O(zn) : O(dn, -1);
          });
        }
        var fn = f(zt), Ut = o(fn);
        {
          var Un = (O) => {
            var J = ct();
            K(() => N(J, i(G).setting_key)), E(O, J);
          }, Hn = (O) => {
            var J = Bt();
            E(O, J);
          };
          de(Ut, (O) => {
            i(G).setting_key ? O(Un) : O(Hn, -1);
          });
        }
        var Ht = f(fn), Z = o(Ht), pe = f(Ht), vn = o(pe);
        {
          var Br = (O) => {
            var J = ct();
            K(() => N(J, i(G).want_to_learn_count)), E(O, J);
          }, ur = (O) => {
            var J = Bt();
            E(O, J);
          };
          de(vn, (O) => {
            i(G).want_to_learn_count > 0 ? O(Br) : O(ur, -1);
          });
        }
        var dr = f(pe), Jr = o(dr);
        {
          var Gr = (O) => {
            var J = ct();
            K(() => N(J, i(G).learning_count)), E(O, J);
          }, Yr = (O) => {
            var J = Bt();
            E(O, J);
          };
          de(Jr, (O) => {
            i(G).learning_count > 0 ? O(Gr) : O(Yr, -1);
          });
        }
        var fr = f(dr), Kr = o(fr);
        {
          var Xr = (O) => {
            var J = ct();
            K(() => N(J, i(G).learned_count)), E(O, J);
          }, Zr = (O) => {
            var J = Bt();
            E(O, J);
          };
          de(Kr, (O) => {
            i(G).learned_count > 0 ? O(Xr) : O(Zr, -1);
          });
        }
        K(() => {
          ue(_e, "href", `/sessions/${t.sessionPath ?? ""}/tunes/${i(G).tune_id ?? ""}`), N(Se, i(G).tune_name), N(Z, i(G).play_count);
        }), E(me, Re);
      }), K(
        (me, G, Re, Fe, _e, Se, re, Pe, yt) => {
          N(Oe, `Tune Name${me ?? ""}`), N(le, `Session Alias${G ?? ""}`), N(k, `Type${Re ?? ""}`), N(R, `Session Key${Fe ?? ""}`), N(B, `Setting Key${_e ?? ""}`), N(he, `Plays${Se ?? ""}`), N(Ce, `Want${re ?? ""}`), N(q, `Learning${Pe ?? ""}`), N(z, `Learned${yt ?? ""}`);
        },
        [
          () => p("tune_name"),
          () => p("session_alias"),
          () => p("tune_type"),
          () => p("session_key"),
          () => p("setting_key"),
          () => p("play_count"),
          () => p("want_to_learn"),
          () => p("learning"),
          () => p("learned")
        ]
      ), Y("click", ke, () => c("tune_name")), Y("click", P, () => c("session_alias")), Y("click", m, () => c("tune_type")), Y("click", W, () => c("session_key")), Y("click", V, () => c("setting_key")), Y("click", ie, () => c("play_count")), Y("click", xe, () => c("want_to_learn")), Y("click", Ie, () => c("learning")), Y("click", X, () => c("learned")), E(A, te);
    };
    de(C, (A) => {
      i(r) ? A(ee) : i(n) ? i(n).length === 0 ? A(se, 2) : i(h).length === 0 ? A(ae, 3) : A(fe, -1) : A(F, 1);
    });
  }
  ve(T, () => i(s), (A) => w(s, A)), E(e, x), on();
}
Rn(["click"]);
var Ho = /* @__PURE__ */ L('<div class="alert alert-danger"> </div>'), Wo = /* @__PURE__ */ L('<p class="text-muted">Loading members...</p>'), Vo = /* @__PURE__ */ L('<div class="alert alert-info">No members found for this session.</div>'), Bo = /* @__PURE__ */ L('<div class="alert alert-info">No members match the current filter.</div>'), Jo = /* @__PURE__ */ L('<span class="text-muted">No email</span>'), Go = /* @__PURE__ */ L('<span class="badge bg-success">Regular</span>'), Yo = /* @__PURE__ */ L('<span class="badge bg-info">User</span>'), Ko = /* @__PURE__ */ L('<span class="text-muted">Never</span>'), Xo = /* @__PURE__ */ L('<span class="badge bg-primary">Session</span>'), Zo = /* @__PURE__ */ L('<span class="badge bg-warning">System</span>'), Qo = /* @__PURE__ */ L('<tr><td class="person-name"><a class="person-link"> </a></td><td class="person-email"><!></td><td class="person-status"><!> <!></td><td class="person-attendance"> </td><td class="person-last-attended"><!></td><td class="person-admin"><!> <!></td></tr>'), $o = /* @__PURE__ */ L('<div class="table-responsive"><table class="table table-striped"><thead><tr><th style="cursor: pointer;"> </th><th style="cursor: pointer;"> </th><th>Status</th><th style="cursor: pointer;"> </th><th style="cursor: pointer;"> </th><th>Admin</th></tr></thead><tbody></tbody></table></div>'), ec = /* @__PURE__ */ L('<section class="docs-section"><div class="mb-3"><div class="d-flex align-items-center gap-3"><div class="flex-grow-1"><input type="text" class="form-control" id="people-search" placeholder="Search by name..."/></div> <div><a class="btn btn-outline-primary btn-sm"><i class="fas fa-upload me-1"></i>Bulk Import</a></div> <div class="ms-auto"><select class="form-select people-filter-select" id="people-filter"><option>Regulars Only</option><option>Everyone</option></select></div></div></div> <div id="people-content"><!></div></section>');
function tc(e, t) {
  ln(t, !0);
  let n = /* @__PURE__ */ M(
    null
    // null until loaded
  ), r = /* @__PURE__ */ M(null), s = /* @__PURE__ */ M("regulars"), a = /* @__PURE__ */ M(""), l = /* @__PURE__ */ M("name"), d = /* @__PURE__ */ M("asc"), c = !1;
  Vr(() => {
    t.load && !c && (c = !0, fetch(`/api/admin/sessions/${t.sessionPath}/people`).then((P) => P.json()).then((P) => {
      if (P.error) {
        w(r, P.error, !0);
        return;
      }
      w(n, P.players, !0);
    }).catch((P) => {
      w(r, `Failed to load members: ${P}`);
    }));
  });
  function h(P) {
    i(l) === P ? w(d, i(d) === "asc" ? "desc" : "asc", !0) : (w(l, P, !0), w(d, "asc"));
  }
  const p = /* @__PURE__ */ Pt(() => {
    if (!i(n)) return [];
    let P = i(n);
    i(s) === "regulars" && (P = P.filter((m) => m.is_regular));
    const le = _i(i(a).toLowerCase());
    return le && (P = P.filter((m) => m.name.toLowerCase().includes(le) || (m.email || "").toLowerCase().includes(le))), [...P].sort((m, k) => pi(ka(m, i(l)), ka(k, i(l)), i(d)));
  }), x = (P) => i(l) !== P ? "" : i(d) === "asc" ? " ↑" : " ↓";
  var _ = ec(), b = o(_), S = o(b), T = o(S), y = o(T), C = f(T, 2), ee = o(C), F = f(C, 2), se = o(F), ae = o(se);
  ae.value = ae.__value = "regulars";
  var fe = f(ae);
  fe.value = fe.__value = "everyone";
  var A = f(b, 2), te = o(A);
  {
    var ne = (P) => {
      var le = Ho(), m = o(le);
      K(() => N(m, i(r))), E(P, le);
    }, ce = (P) => {
      var le = Wo();
      E(P, le);
    }, Ae = (P) => {
      var le = Vo();
      E(P, le);
    }, ke = (P) => {
      var le = Bo();
      E(P, le);
    }, Oe = (P) => {
      var le = $o(), m = o(le), k = o(m), W = o(k), R = o(W), V = o(R), B = f(R), ie = o(B), he = f(B, 2), xe = o(he), Ce = f(he), Ie = o(Ce), q = f(k);
      At(q, 21, () => i(p), (X) => X.person_id, (X, z) => {
        var Le = Qo(), me = o(Le), G = o(me), Re = o(G), Fe = f(me), _e = o(Fe);
        {
          var Se = (Z) => {
            var pe = ct();
            K(() => N(pe, i(z).email)), E(Z, pe);
          }, re = (Z) => {
            var pe = Jo();
            E(Z, pe);
          };
          de(_e, (Z) => {
            i(z).email ? Z(Se) : Z(re, -1);
          });
        }
        var Pe = f(Fe), yt = o(Pe);
        {
          var Fn = (Z) => {
            var pe = Go();
            E(Z, pe);
          };
          de(yt, (Z) => {
            i(z).is_regular && Z(Fn);
          });
        }
        var qt = f(yt, 2);
        {
          var jn = (Z) => {
            var pe = Yo();
            E(Z, pe);
          };
          de(qt, (Z) => {
            i(z).username && Z(jn);
          });
        }
        var cn = f(Pe), qn = o(cn), zt = f(cn), un = o(zt);
        {
          var zn = (Z) => {
            var pe = ct();
            K((vn) => N(pe, vn), [
              () => new Date(i(z).last_attended).toLocaleDateString()
            ]), E(Z, pe);
          }, dn = (Z) => {
            var pe = Ko();
            E(Z, pe);
          };
          de(un, (Z) => {
            i(z).last_attended ? Z(zn) : Z(dn, -1);
          });
        }
        var fn = f(zt), Ut = o(fn);
        {
          var Un = (Z) => {
            var pe = Xo();
            E(Z, pe);
          };
          de(Ut, (Z) => {
            i(z).is_admin && Z(Un);
          });
        }
        var Hn = f(Ut, 2);
        {
          var Ht = (Z) => {
            var pe = Zo();
            E(Z, pe);
          };
          de(Hn, (Z) => {
            i(z).is_system_admin && Z(Ht);
          });
        }
        K(() => {
          ue(G, "href", `/admin/sessions/${t.sessionPath ?? ""}/people/${i(z).person_id ?? ""}`), N(Re, i(z).name), N(qn, `${i(z).attendance_count ?? ""} sessions`);
        }), E(X, Le);
      }), K(
        (X, z, Le, me) => {
          N(V, `Name${X ?? ""}`), N(ie, `Email${z ?? ""}`), N(xe, `Attendance${Le ?? ""}`), N(Ie, `Last Attended${me ?? ""}`);
        },
        [
          () => x("name"),
          () => x("email"),
          () => x("attendance"),
          () => x("last_attended")
        ]
      ), Y("click", R, () => h("name")), Y("click", B, () => h("email")), Y("click", he, () => h("attendance")), Y("click", Ce, () => h("last_attended")), E(P, le);
    };
    de(te, (P) => {
      i(r) ? P(ne) : i(n) ? i(n).length === 0 ? P(Ae, 2) : i(p).length === 0 ? P(ke, 3) : P(Oe, -1) : P(ce, 1);
    });
  }
  K(() => ue(ee, "href", `/admin/sessions/${t.sessionPath ?? ""}/bulk-import`)), ve(y, () => i(a), (P) => w(a, P)), Ar(se, () => i(s), (P) => w(s, P)), E(e, _), on();
}
Rn(["click"]);
var nc = /* @__PURE__ */ L('<div class="alert alert-danger"> </div>'), rc = /* @__PURE__ */ L('<p class="text-muted">Loading session history...</p>'), sc = /* @__PURE__ */ L('<div class="alert alert-info">No session instances found.</div>'), ac = /* @__PURE__ */ L('<span class="badge bg-danger">Cancelled</span>'), ic = /* @__PURE__ */ L('<span class="badge bg-success">Held</span>'), lc = /* @__PURE__ */ L('<tr class="log-row" style="cursor: pointer;"><td class="log-date"><strong> </strong> <br/> <small class="text-muted"> </small></td><td class="log-tunes text-center"> </td><td class="log-attendance text-center"> </td><td class="log-status text-center"><!></td></tr>'), oc = /* @__PURE__ */ L('<div class="table-responsive"><table class="table table-striped table-hover" id="logs-table"><thead><tr><th>Date</th><th class="text-center">Tunes</th><th class="text-center">Players</th><th class="text-center">Status</th></tr></thead><tbody></tbody></table></div>'), cc = /* @__PURE__ */ L('<div id="add-session-instance-modal" class="modal-overlay show" style="display: flex;"><div class="modal-dialog"><div class="modal-dialog-content"><div class="modal-header"><h3 class="modal-title">Add Session Instance</h3></div> <div class="modal-body"><div class="mb-3"><label for="session-date-input" class="form-label">Session Date:</label> <input type="date" id="session-date-input" class="form-control" required=""/></div> <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;"><div class="mb-3"><label for="session-start-time-input" class="form-label">Start Time:</label> <input type="time" id="session-start-time-input" class="form-control"/></div> <div class="mb-3"><label for="session-end-time-input" class="form-label">End Time:</label> <input type="time" id="session-end-time-input" class="form-control"/></div></div> <div class="mb-3"><label for="session-location-input" class="form-label">Location:</label> <input type="text" id="session-location-input" class="form-control"/></div> <div class="mb-3"><label for="session-comments-input" class="form-label">Comments:</label> <textarea id="session-comments-input" class="form-control" placeholder="Notes about this session" rows="3" style="resize: vertical;"></textarea></div></div> <div class="modal-footer"><button type="button" class="btn btn-secondary" id="add-session-cancel-btn">Cancel</button> <button type="button" class="btn btn-primary" id="add-session-confirm-btn">Add Session</button></div></div></div></div>'), uc = /* @__PURE__ */ L('<section class="docs-section"><div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;"><h2 class="section-heading" style="margin-bottom: 0;">Session Instance History</h2> <button type="button" class="btn btn-primary" id="add-session-instance-btn">Add Session Instance</button></div> <div id="logs-content"><!></div></section> <!>', 1);
function dc(e, t) {
  ln(t, !0);
  const n = (m, k) => window.showMessage && window.showMessage(m, k);
  function r() {
    return window.SessionInstanceModal ? window.SessionInstanceModal : typeof SessionInstanceModal < "u" ? SessionInstanceModal : null;
  }
  let s = /* @__PURE__ */ M(
    null
    // null until loaded
  ), a = /* @__PURE__ */ M(null), l = !1;
  function d() {
    fetch(`/api/admin/sessions/${t.sessionPath}/logs`).then((m) => m.json()).then((m) => {
      if (m.error) {
        w(a, m.error, !0);
        return;
      }
      w(s, m.logs, !0);
      const W = new URLSearchParams(window.location.search).get("instance");
      if (W) {
        const R = m.logs.find((B) => B.session_instance_id == W), V = r();
        R && V && V.show(parseInt(W), t.sessionPath, R.date), window.history.replaceState({}, "", window.location.pathname);
      }
    }).catch((m) => {
      w(a, `Failed to load session logs: ${m}`);
    });
  }
  Vr(() => {
    t.load && !l && (l = !0, d());
  });
  const c = (m) => {
    const k = new Date(m);
    return {
      main: k.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }),
      weekday: k.toLocaleDateString("en-US", { weekday: "long" })
    };
  };
  function h(m) {
    const k = r();
    k && k.show(m.session_instance_id, t.sessionPath, m.date);
  }
  let p = /* @__PURE__ */ M(!1), x = /* @__PURE__ */ M(""), _ = /* @__PURE__ */ M(""), b = /* @__PURE__ */ M(""), S = /* @__PURE__ */ M(""), T = /* @__PURE__ */ M("");
  async function y() {
    w(x, (/* @__PURE__ */ new Date()).toISOString().split("T")[0], !0), w(_, ""), w(b, ""), w(S, ""), w(T, ""), w(p, !0), document.body.classList.add("modal-open");
    try {
      const k = await (await fetch(`/api/sessions/${t.sessionPath}/next_instance_suggestion`)).json();
      k.success && (w(x, k.date || i(x), !0), w(_, k.start_time || "", !0), w(b, k.end_time || "", !0));
    } catch (m) {
      console.error("Failed to get next session suggestion:", m);
    }
  }
  function C() {
    w(p, !1), document.body.classList.remove("modal-open");
  }
  function ee(m) {
    m.key === "Escape" && C();
  }
  function F() {
    const m = i(x).trim(), k = i(_).trim(), W = i(b).trim(), R = i(S).trim(), V = i(T).trim();
    if (!m) {
      n("Please enter a session date", "error");
      return;
    }
    const B = { date: m };
    k && (B.start_time = k), W && (B.end_time = W), R && (B.location = R), V && (B.comments = V), fetch(`/api/sessions/${t.sessionPath}/add_instance`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(B)
    }).then((ie) => ie.json()).then((ie) => {
      ie.success ? (n(ie.message), C(), d()) : n(ie.message, "error");
    }).catch((ie) => {
      n("Failed to add session instance", "error"), console.error("Error:", ie);
    });
  }
  var se = uc();
  Es("keydown", Dr, ee);
  var ae = tr(se), fe = o(ae), A = f(o(fe), 2), te = f(fe, 2), ne = o(te);
  {
    var ce = (m) => {
      var k = nc(), W = o(k);
      K(() => N(W, i(a))), E(m, k);
    }, Ae = (m) => {
      var k = rc();
      E(m, k);
    }, ke = (m) => {
      var k = sc();
      E(m, k);
    }, Oe = (m) => {
      var k = oc(), W = o(k), R = f(o(W));
      At(R, 21, () => i(s), (V) => V.session_instance_id, (V, B) => {
        var ie = lc(), he = o(ie), xe = o(he), Ce = o(xe), Ie = f(xe, 4), q = o(Ie), X = f(he), z = o(X), Le = f(X), me = o(Le), G = f(Le), Re = o(G);
        {
          var Fe = (Se) => {
            var re = ac();
            E(Se, re);
          }, _e = (Se) => {
            var re = ic();
            E(Se, re);
          };
          de(Re, (Se) => {
            i(B).is_cancelled ? Se(Fe) : Se(_e, -1);
          });
        }
        K(
          (Se, re) => {
            ue(ie, "data-instance-id", i(B).session_instance_id), ue(ie, "data-date", i(B).date), N(Ce, Se), N(q, re), N(z, i(B).tune_count), N(me, i(B).attendance_count);
          },
          [
            () => c(i(B).date).main,
            () => c(i(B).date).weekday
          ]
        ), Y("click", ie, () => h(i(B))), E(V, ie);
      }), E(m, k);
    };
    de(ne, (m) => {
      i(a) ? m(ce) : i(s) ? i(s).length === 0 ? m(ke, 2) : m(Oe, -1) : m(Ae, 1);
    });
  }
  var P = f(ae, 2);
  {
    var le = (m) => {
      var k = cc(), W = o(k), R = o(W), V = f(o(R), 2), B = o(V), ie = f(o(B), 2), he = f(B, 2), xe = o(he), Ce = f(o(xe), 2), Ie = f(xe, 2), q = f(o(Ie), 2), X = f(he, 2), z = f(o(X), 2), Le = f(X, 2), me = f(o(Le), 2), G = f(V, 2), Re = o(G), Fe = f(Re, 2);
      K(() => ue(z, "placeholder", `The usual: ${t.locationName ?? ""}`)), ve(ie, () => i(x), (_e) => w(x, _e)), ve(Ce, () => i(_), (_e) => w(_, _e)), ve(q, () => i(b), (_e) => w(b, _e)), ve(z, () => i(S), (_e) => w(S, _e)), ve(me, () => i(T), (_e) => w(T, _e)), Y("click", Re, C), Y("click", Fe, F), E(m, k);
    };
    de(P, (m) => {
      i(p) && m(le);
    });
  }
  Y("click", A, y), E(e, se), on();
}
Rn(["click"]);
var fc = /* @__PURE__ */ L("Caching <strong> </strong> <strong> </strong> globally-popular = <strong> </strong> ", 1), vc = /* @__PURE__ */ L('<div class="alert alert-danger"> </div>'), hc = /* @__PURE__ */ L('<div class="alert alert-info">No tunes would be cached with these settings.</div>'), _c = /* @__PURE__ */ L('<span class="text-muted">-</span>'), pc = /* @__PURE__ */ L('<span class="badge badge-primary">session</span>'), mc = /* @__PURE__ */ L('<span class="badge badge-secondary">global</span>'), bc = /* @__PURE__ */ L('<tr><td class="text-muted"></td><td><a class="tune-link"> </a></td><td><!></td><td><!></td><td class="text-muted"> </td></tr>'), gc = /* @__PURE__ */ L('<table class="table table-sm" id="cache-table"><thead><tr><th style="width:3rem;">#</th><th>Tune</th><th>Type</th><th>Tier</th><th>Popularity</th></tr></thead><tbody></tbody></table>'), yc = /* @__PURE__ */ L(`<section class="docs-section"><h2 class="section-heading">Local Tune Cache</h2> <p class="text-muted">The live-logging screen preloads a list of tunes onto each device so typed
    tune names match instantly &mdash; even offline. It holds the <strong>N</strong> most-played tunes from <em>this</em> session, plus the <strong>M</strong> most globally-popular tunes not already in that set.
    Bigger numbers match more tunes without a network call, but make each
    device download a little more.</p> <div class="d-flex flex-wrap align-items-end gap-3 mb-3"><div><label for="cache-session-limit" class="form-label mb-1">N &mdash; this session's top tunes</label> <input type="number" class="form-control" id="cache-session-limit" min="0" max="2000" style="width: 120px;"/></div> <div><label for="cache-global-limit" class="form-label mb-1">M &mdash; globally-popular extras</label> <input type="number" class="form-control" id="cache-global-limit" min="0" max="1000" style="width: 120px;"/></div> <button type="button" class="btn btn-primary" id="cache-save-btn">Save</button></div> <div id="cache-summary" class="mb-3 text-muted"><!></div> <div id="cache-content"><!></div></section>`);
function wc(e, t) {
  ln(t, !0);
  const n = (m, k) => window.showMessage && window.showMessage(m, k);
  let r = /* @__PURE__ */ M(ge(String(t.sessionLimit))), s = /* @__PURE__ */ M(ge(String(t.globalLimit))), a = /* @__PURE__ */ M(
    null
    // {session_count, global_count, total, kb}
  ), l = /* @__PURE__ */ M("Loading preview…"), d = /* @__PURE__ */ M(null), c = /* @__PURE__ */ M(null), h = null, p = !1;
  function x() {
    clearTimeout(h), h = setTimeout(_, 300);
  }
  function _() {
    w(l, "Computing preview…"), w(a, null), fetch(`/api/admin/sessions/${t.sessionPath}/tune-cache?n=${encodeURIComponent(i(r))}&m=${encodeURIComponent(i(s))}`).then((m) => m.json()).then((m) => {
      if (!m.success) {
        w(l, ""), w(d, null), w(c, m.error || "Failed to load preview", !0);
        return;
      }
      b(m);
    }).catch((m) => {
      w(c, `Failed to load preview: ${m}`);
    });
  }
  function b(m) {
    const k = m.tunes.map((R) => ({
      tune_id: R.tune_id,
      name: R.name,
      alias: R.alias,
      tune_type: R.tune_type
    })), W = (new Blob([JSON.stringify(k)]).size / 1024).toFixed(1);
    w(c, null), w(l, null), w(
      a,
      {
        session_count: m.session_count,
        global_count: m.global_count,
        total: m.tunes.length,
        kb: W
      },
      !0
    ), w(d, m.tunes, !0);
  }
  function S() {
    const m = {
      live_cache_session_limit: parseInt(i(r)) || 0,
      live_cache_global_limit: parseInt(i(s)) || 0
    };
    fetch(`/api/sessions/${t.sessionPath}/admin-update`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(m)
    }).then((k) => k.json()).then((k) => {
      k.success ? (n("Local cache settings saved", "success"), _()) : n(k.error || "Failed to save cache settings", "error");
    }).catch((k) => {
      console.error("Error saving cache settings:", k), n("An error occurred while saving cache settings", "error");
    });
  }
  Vr(() => {
    t.load && !p && (p = !0, _());
  });
  const T = (m) => m.tier === "session" ? `${m.plays} play${m.plays === 1 ? "" : "s"} here` : `${(m.tunebook_count || 0).toLocaleString()} tunebooks`;
  var y = yc(), C = f(o(y), 4), ee = o(C), F = f(o(ee), 2), se = f(ee, 2), ae = f(o(se), 2), fe = f(se, 2), A = f(C, 2), te = o(A);
  {
    var ne = (m) => {
      var k = fc(), W = f(tr(k)), R = o(W), V = f(W), B = f(V), ie = o(B), he = f(B, 2), xe = o(he), Ce = f(he);
      K(() => {
        N(R, i(a).session_count), N(V, ` session tune${i(a).session_count === 1 ? "" : "s"}
      + `), N(ie, i(a).global_count), N(xe, i(a).total), N(Ce, ` total
      (~${i(a).kb ?? ""} KB per device).`);
      }), E(m, k);
    }, ce = (m) => {
      var k = ct();
      K(() => N(k, i(l))), E(m, k);
    };
    de(te, (m) => {
      i(a) ? m(ne) : i(l) && m(ce, 1);
    });
  }
  var Ae = f(A, 2), ke = o(Ae);
  {
    var Oe = (m) => {
      var k = vc(), W = o(k);
      K(() => N(W, i(c))), E(m, k);
    }, P = (m) => {
      var k = hc();
      E(m, k);
    }, le = (m) => {
      var k = gc(), W = f(o(k));
      At(W, 21, () => i(d), fi, (R, V, B) => {
        var ie = bc(), he = o(ie);
        he.textContent = B + 1;
        var xe = f(he), Ce = o(xe), Ie = o(Ce), q = f(xe), X = o(q);
        {
          var z = (re) => {
            var Pe = ct();
            K(() => N(Pe, i(V).tune_type)), E(re, Pe);
          }, Le = (re) => {
            var Pe = _c();
            E(re, Pe);
          };
          de(X, (re) => {
            i(V).tune_type ? re(z) : re(Le, -1);
          });
        }
        var me = f(q), G = o(me);
        {
          var Re = (re) => {
            var Pe = pc();
            E(re, Pe);
          }, Fe = (re) => {
            var Pe = mc();
            E(re, Pe);
          };
          de(G, (re) => {
            i(V).tier === "session" ? re(Re) : re(Fe, -1);
          });
        }
        var _e = f(me), Se = o(_e);
        K(
          (re) => {
            ue(Ce, "href", `/sessions/${t.sessionPath ?? ""}/tunes/${i(V).tune_id ?? ""}`), N(Ie, i(V).name), N(Se, re);
          },
          [() => T(i(V))]
        ), E(R, ie);
      }), E(m, k);
    };
    de(ke, (m) => {
      i(c) ? m(Oe) : i(d) && i(d).length === 0 ? m(P, 1) : i(d) && m(le, 2);
    });
  }
  Y("input", F, x), ve(F, () => i(r), (m) => w(r, m)), Y("input", ae, x), ve(ae, () => i(s), (m) => w(s, m)), Y("click", fe, S), E(e, y), on();
}
Rn(["input", "click"]);
var kc = /* @__PURE__ */ L('<a href="/admin" class="breadcrumb-item">Admin</a> <span class="breadcrumb-separator">&gt;&gt;</span> <a href="/admin/sessions" class="breadcrumb-item">Sessions</a>', 1), xc = /* @__PURE__ */ L('<a href="/admin/sessions" class="breadcrumb-item">My Sessions</a>'), Sc = /* @__PURE__ */ L('<span class="breadcrumb-current"> </span>'), Ec = /* @__PURE__ */ L('<a class="breadcrumb-item"> </a> <span class="breadcrumb-separator">&gt;&gt;</span> <span class="breadcrumb-current"> </span>', 1), Tc = /* @__PURE__ */ L('<nav class="admin-breadcrumb" aria-label="breadcrumb"><!> <span class="breadcrumb-separator">&gt;&gt;</span> <!></nav> <nav class="session-admin-tabs-nav"><div class="nav nav-tabs" id="session-admin-tabs" role="tablist"><a>Details</a> <a>Tunes</a> <a>Members</a> <a>Logs</a> <a>Local Cache</a></div> <div class="session-admin-tabs-mobile"><select class="form-select" id="session-admin-mobile-select"><option>Details</option><option>Tunes</option><option>Members</option><option>Logs</option><option>Local Cache</option></select></div></nav> <div class="tab-content" id="session-admin-tab-content"><div id="details" role="tabpanel"><!></div> <div id="tunes" role="tabpanel"><!></div> <div id="people" role="tabpanel"><!></div> <div id="logs" role="tabpanel"><!></div> <div id="cache" role="tabpanel"><!></div></div>', 1);
function Ac(e, t) {
  ln(t, !0);
  let n = hi(t, "ctx", 19, () => ({}));
  const r = t.pageData.session, s = n().sessionPath || r.path, a = n().activeTab || "details", l = !!n().isSystemAdmin, d = a === "tunes" ? "Tunes" : a === "people" ? "Members" : a === "logs" ? "Logs" : "";
  function c(q) {
    const X = q.currentTarget.value;
    let z;
    X === "details" ? z = `/admin/sessions/${s}` : X === "tunes" ? z = `/admin/sessions/${s}/tunes` : X === "people" ? z = `/admin/sessions/${s}/people` : X === "logs" ? z = `/admin/sessions/${s}/logs` : X === "cache" && (z = `/admin/sessions/${s}/cache`), z && (window.location.href = z);
  }
  var h = Tc(), p = tr(h), x = o(p);
  {
    var _ = (q) => {
      var X = kc();
      E(q, X);
    }, b = (q) => {
      var X = xc();
      E(q, X);
    };
    de(x, (q) => {
      l ? q(_) : q(b, -1);
    });
  }
  var S = f(x, 4);
  {
    var T = (q) => {
      var X = Sc(), z = o(X);
      K(() => N(z, r.name)), E(q, X);
    }, y = (q) => {
      var X = Ec(), z = tr(X), Le = o(z), me = f(z, 4), G = o(me);
      K(() => {
        ue(z, "href", `/admin/sessions/${r.path ?? ""}`), N(Le, r.name), N(G, d);
      }), E(q, X);
    };
    de(S, (q) => {
      a === "details" ? q(T) : q(y, -1);
    });
  }
  var C = f(p, 2), ee = o(C), F = o(ee), se = f(F, 2), ae = f(se, 2), fe = f(ae, 2), A = f(fe, 2), te = f(ee, 2), ne = o(te), ce = o(ne);
  ce.value = ce.__value = "details";
  var Ae = f(ce);
  Ae.value = Ae.__value = "tunes";
  var ke = f(Ae);
  ke.value = ke.__value = "people";
  var Oe = f(ke);
  Oe.value = Oe.__value = "logs";
  var P = f(Oe);
  P.value = P.__value = "cache";
  var le;
  vi(ne);
  var m = f(C, 2), k = o(m), W = o(k);
  {
    let q = /* @__PURE__ */ Pt(() => t.pageData.timezone_options || []);
    Do(W, {
      get session() {
        return r;
      },
      get sessionPath() {
        return s;
      },
      get timezoneOptions() {
        return i(q);
      }
    });
  }
  var R = f(k, 2), V = o(R);
  {
    let q = /* @__PURE__ */ Pt(() => a === "tunes");
    Uo(V, {
      get sessionPath() {
        return s;
      },
      get load() {
        return i(q);
      }
    });
  }
  var B = f(R, 2), ie = o(B);
  {
    let q = /* @__PURE__ */ Pt(() => a === "people");
    tc(ie, {
      get sessionPath() {
        return s;
      },
      get load() {
        return i(q);
      }
    });
  }
  var he = f(B, 2), xe = o(he);
  {
    let q = /* @__PURE__ */ Pt(() => a === "logs");
    dc(xe, {
      get sessionPath() {
        return s;
      },
      get locationName() {
        return r.location_name;
      },
      get load() {
        return i(q);
      }
    });
  }
  var Ce = f(he, 2), Ie = o(Ce);
  {
    let q = /* @__PURE__ */ Pt(() => a === "cache");
    wc(Ie, {
      get sessionPath() {
        return s;
      },
      get sessionLimit() {
        return r.live_cache_session_limit;
      },
      get globalLimit() {
        return r.live_cache_global_limit;
      },
      get load() {
        return i(q);
      }
    });
  }
  K(() => {
    at(F, 1, `nav-link ${a === "details" ? "active" : ""}`), ue(F, "href", `/admin/sessions/${r.path ?? ""}`), at(se, 1, `nav-link ${a === "tunes" ? "active" : ""}`), ue(se, "href", `/admin/sessions/${r.path ?? ""}/tunes`), at(ae, 1, `nav-link ${a === "people" ? "active" : ""}`), ue(ae, "href", `/admin/sessions/${r.path ?? ""}/people`), at(fe, 1, `nav-link ${a === "logs" ? "active" : ""}`), ue(fe, "href", `/admin/sessions/${r.path ?? ""}/logs`), at(A, 1, `nav-link ${a === "cache" ? "active" : ""}`), ue(A, "href", `/admin/sessions/${r.path ?? ""}/cache`), le !== (le = a) && (ne.value = (ne.__value = a) ?? "", Ws(ne, a)), at(k, 1, `tab-pane fade ${a === "details" ? "show active" : ""}`), at(R, 1, `tab-pane fade ${a === "tunes" ? "show active" : ""}`), at(B, 1, `tab-pane fade ${a === "people" ? "show active" : ""}`), at(he, 1, `tab-pane fade ${a === "logs" ? "show active" : ""}`), at(Ce, 1, `tab-pane fade ${a === "cache" ? "show active" : ""}`);
  }), Y("change", ne, c), E(e, h), on();
}
Rn(["change"]);
const Sa = document.getElementById("session-admin-root");
Sa && window.__PAGE_DATA__ && so(Ac, {
  target: Sa,
  props: {
    pageData: window.__PAGE_DATA__,
    ctx: window.__PAGE_CTX__ || {}
  }
});
