var ll = Object.defineProperty;
var Bs = (e) => {
  throw TypeError(e);
};
var ul = (e, t, i) => t in e ? ll(e, t, { enumerable: !0, configurable: !0, writable: !0, value: i }) : e[t] = i;
var et = (e, t, i) => ul(e, typeof t != "symbol" ? t + "" : t, i), _r = (e, t, i) => t.has(e) || Bs("Cannot " + i);
var c = (e, t, i) => (_r(e, t, "read from private field"), i ? i.call(e) : t.get(e)), H = (e, t, i) => t.has(e) ? Bs("Cannot add the same private member more than once") : t instanceof WeakSet ? t.add(e) : t.set(e, i), j = (e, t, i, r) => (_r(e, t, "write to private field"), r ? r.call(e, i) : t.set(e, i), i), ie = (e, t, i) => (_r(e, t, "access private method"), i);
var zr = Array.isArray, cl = Array.prototype.indexOf, ji = Array.prototype.includes, Zi = Array.from, fl = Object.defineProperty, fi = Object.getOwnPropertyDescriptor, dl = Object.getOwnPropertyDescriptors, vl = Object.prototype, _l = Array.prototype, wa = Object.getPrototypeOf, Ds = Object.isExtensible;
const hl = () => {
};
function pl(e) {
  for (var t = 0; t < e.length; t++)
    e[t]();
}
function ka() {
  var e, t, i = new Promise((r, s) => {
    e = r, t = s;
  });
  return { promise: i, resolve: e, reject: t };
}
function Gs(e, t) {
  if (Array.isArray(e))
    return e;
  if (!(Symbol.iterator in e))
    return Array.from(e);
  const i = [];
  for (const r of e)
    if (i.push(r), i.length === t) break;
  return i;
}
const Re = 2, qn = 4, Xi = 8, Sa = 1 << 24, yt = 16, kt = 32, Qt = 64, Tr = 128, ut = 512, Ie = 1024, $e = 2048, Ot = 4096, Be = 8192, ct = 16384, Gn = 32768, Er = 1 << 25, Wn = 65536, zi = 1 << 17, ml = 1 << 18, Yn = 1 << 19, gl = 1 << 20, Ct = 1 << 25, wn = 65536, Hi = 1 << 21, Pn = 1 << 22, Zt = 1 << 23, Fn = Symbol("$state"), bl = Symbol(""), Pi = Symbol("attributes"), xr = Symbol("class"), Ir = Symbol("style"), ai = Symbol("text"), Fi = Symbol("form reset"), Qi = new class extends Error {
  constructor() {
    super(...arguments);
    et(this, "name", "StaleReactionError");
    et(this, "message", "The reaction that called `getAbortSignal()` was re-run or destroyed");
  }
}();
function yl() {
  throw new Error("https://svelte.dev/e/async_derived_orphan");
}
function wl(e, t, i) {
  throw new Error("https://svelte.dev/e/each_key_duplicate");
}
function kl(e) {
  throw new Error("https://svelte.dev/e/effect_in_teardown");
}
function Sl() {
  throw new Error("https://svelte.dev/e/effect_in_unowned_derived");
}
function Tl(e) {
  throw new Error("https://svelte.dev/e/effect_orphan");
}
function El() {
  throw new Error("https://svelte.dev/e/effect_update_depth_exceeded");
}
function xl() {
  throw new Error("https://svelte.dev/e/state_descriptors_fixed");
}
function Il() {
  throw new Error("https://svelte.dev/e/state_prototype_fixed");
}
function Cl() {
  throw new Error("https://svelte.dev/e/state_unsafe_mutation");
}
function Al() {
  throw new Error("https://svelte.dev/e/svelte_boundary_reset_onerror");
}
const Ol = 1, Ml = 2, Ta = 4, Ll = 8, Pl = 16, Fl = 1, Nl = 2, xe = Symbol("uninitialized"), $l = "http://www.w3.org/1999/xhtml";
function Rl() {
  console.warn("https://svelte.dev/e/derived_inert");
}
function Ul() {
  console.warn("https://svelte.dev/e/select_multiple_invalid_value");
}
function jl() {
  console.warn("https://svelte.dev/e/svelte_boundary_reset_noop");
}
function Ea(e) {
  return e === this.v;
}
function zl(e, t) {
  return e != e ? t == t : e !== t || e !== null && typeof e == "object" || typeof e == "function";
}
function xa(e) {
  return !zl(e, this.v);
}
let De = null;
function Vn(e) {
  De = e;
}
function Hr(e, t = !1, i) {
  De = {
    p: De,
    i: !1,
    c: null,
    e: null,
    s: e,
    x: null,
    r: (
      /** @type {Effect} */
      X
    ),
    l: null
  };
}
function qr(e) {
  var t = (
    /** @type {ComponentContext} */
    De
  ), i = t.e;
  if (i !== null) {
    t.e = null;
    for (var r of i)
      Ga(r);
  }
  return e !== void 0 && (t.x = e), t.i = !0, De = t.p, e ?? /** @type {T} */
  {};
}
function Ia() {
  return !0;
}
let un = [];
function Ca() {
  var e = un;
  un = [], pl(e);
}
function Xt(e) {
  if (un.length === 0 && !vi) {
    var t = un;
    queueMicrotask(() => {
      t === un && Ca();
    });
  }
  un.push(e);
}
function Hl() {
  for (; un.length > 0; )
    Ca();
}
function Aa(e) {
  var t = X;
  if (t === null)
    return Y.f |= Zt, e;
  if (!(t.f & Gn) && !(t.f & qn))
    throw e;
  Jt(e, t);
}
function Jt(e, t) {
  if (!(t !== null && t.f & ct)) {
    for (; t !== null; ) {
      if (t.f & Tr) {
        if (!(t.f & Gn))
          throw e;
        try {
          t.b.error(e);
          return;
        } catch (i) {
          e = i;
        }
      }
      t = t.parent;
    }
    throw e;
  }
}
const ql = -7169;
function ke(e, t) {
  e.f = e.f & ql | t;
}
function Wr(e) {
  e.f & ut || e.deps === null ? ke(e, Ie) : ke(e, Ot);
}
function Oa(e) {
  if (e !== null)
    for (const t of e)
      !(t.f & Re) || !(t.f & wn) || (t.f ^= wn, Oa(
        /** @type {Derived} */
        t.deps
      ));
}
function Ma(e, t, i) {
  e.f & $e ? t.add(e) : e.f & Ot && i.add(e), Oa(e.deps), ke(e, Ie);
}
function Wl(e) {
  let t = 0, i = Sn(0), r;
  return () => {
    Yr() && (n(i), Jr(() => (t === 0 && (r = es(() => e(() => _i(i)))), t += 1, () => {
      Xt(() => {
        t -= 1, t === 0 && (r == null || r(), r = void 0, _i(i));
      });
    })));
  };
}
var Vl = Wn | Yn;
function Bl(e, t, i, r) {
  new Dl(e, t, i, r);
}
var st, jr, at, vn, Ke, ot, Ve, nt, $t, _n, Yt, Nn, mi, gi, Rt, Yi, be, Gl, Yl, Kl, Cr, Ni, $i, Ar, Or;
class Dl {
  /**
   * @param {TemplateNode} node
   * @param {BoundaryProps} props
   * @param {((anchor: Node) => void)} children
   * @param {((error: unknown) => unknown) | undefined} [transform_error]
   */
  constructor(t, i, r, s) {
    H(this, be);
    /** @type {Boundary | null} */
    et(this, "parent");
    et(this, "is_pending", !1);
    /**
     * API-level transformError transform function. Transforms errors before they reach the `failed` snippet.
     * Inherited from parent boundary, or defaults to identity.
     * @type {(error: unknown) => unknown}
     */
    et(this, "transform_error");
    /** @type {TemplateNode} */
    H(this, st);
    /** @type {TemplateNode | null} */
    H(this, jr, null);
    /** @type {BoundaryProps} */
    H(this, at);
    /** @type {((anchor: Node) => void)} */
    H(this, vn);
    /** @type {Effect} */
    H(this, Ke);
    /** @type {Effect | null} */
    H(this, ot, null);
    /** @type {Effect | null} */
    H(this, Ve, null);
    /** @type {Effect | null} */
    H(this, nt, null);
    /** @type {DocumentFragment | null} */
    H(this, $t, null);
    H(this, _n, 0);
    H(this, Yt, 0);
    H(this, Nn, !1);
    /** @type {Set<Effect>} */
    H(this, mi, /* @__PURE__ */ new Set());
    /** @type {Set<Effect>} */
    H(this, gi, /* @__PURE__ */ new Set());
    /**
     * A source containing the number of pending async deriveds/expressions.
     * Only created if `$effect.pending()` is used inside the boundary,
     * otherwise updating the source results in needless `Batch.ensure()`
     * calls followed by no-op flushes
     * @type {Source<number> | null}
     */
    H(this, Rt, null);
    H(this, Yi, Wl(() => (j(this, Rt, Sn(c(this, _n))), () => {
      j(this, Rt, null);
    })));
    var o;
    j(this, st, t), j(this, at, i), j(this, vn, (l) => {
      var a = (
        /** @type {Effect} */
        X
      );
      a.b = this, a.f |= Tr, r(l);
    }), this.parent = /** @type {Effect} */
    X.b, this.transform_error = s ?? ((o = this.parent) == null ? void 0 : o.transform_error) ?? ((l) => l), j(this, Ke, Zr(() => {
      ie(this, be, Cr).call(this);
    }, Vl));
  }
  /**
   * Defer an effect inside a pending boundary until the boundary resolves
   * @param {Effect} effect
   */
  defer_effect(t) {
    Ma(t, c(this, mi), c(this, gi));
  }
  /**
   * Returns `false` if the effect exists inside a boundary whose pending snippet is shown
   * @returns {boolean}
   */
  is_rendered() {
    return !this.is_pending && (!this.parent || this.parent.is_rendered());
  }
  has_pending_snippet() {
    return !!c(this, at).pending;
  }
  /**
   * Update the source that powers `$effect.pending()` inside this boundary,
   * and controls when the current `pending` snippet (if any) is removed.
   * Do not call from inside the class
   * @param {1 | -1} d
   * @param {Batch} batch
   */
  update_pending_count(t, i) {
    ie(this, be, Ar).call(this, t, i), j(this, _n, c(this, _n) + t), !(!c(this, Rt) || c(this, Nn)) && (j(this, Nn, !0), Xt(() => {
      j(this, Nn, !1), c(this, Rt) && Bn(c(this, Rt), c(this, _n));
    }));
  }
  get_effect_pending() {
    return c(this, Yi).call(this), n(
      /** @type {Source<number>} */
      c(this, Rt)
    );
  }
  /** @param {unknown} error */
  error(t) {
    if (!c(this, at).onerror && !c(this, at).failed)
      throw t;
    $ != null && $.is_fork ? (c(this, ot) && $.skip_effect(c(this, ot)), c(this, Ve) && $.skip_effect(c(this, Ve)), c(this, nt) && $.skip_effect(c(this, nt)), $.oncommit(() => {
      ie(this, be, Or).call(this, t);
    })) : ie(this, be, Or).call(this, t);
  }
}
st = new WeakMap(), jr = new WeakMap(), at = new WeakMap(), vn = new WeakMap(), Ke = new WeakMap(), ot = new WeakMap(), Ve = new WeakMap(), nt = new WeakMap(), $t = new WeakMap(), _n = new WeakMap(), Yt = new WeakMap(), Nn = new WeakMap(), mi = new WeakMap(), gi = new WeakMap(), Rt = new WeakMap(), Yi = new WeakMap(), be = new WeakSet(), Gl = function() {
  try {
    j(this, ot, lt(() => c(this, vn).call(this, c(this, st))));
  } catch (t) {
    this.error(t);
  }
}, /**
 * @param {unknown} error The deserialized error from the server's hydration comment
 */
Yl = function(t) {
  const i = c(this, at).failed;
  i && j(this, nt, lt(() => {
    i(
      c(this, st),
      () => t,
      () => () => {
      }
    );
  }));
}, Kl = function() {
  const t = c(this, at).pending;
  t && (this.is_pending = !0, j(this, Ve, lt(() => t(c(this, st)))), Xt(() => {
    var i = j(this, $t, document.createDocumentFragment()), r = Ht();
    i.append(r), j(this, ot, ie(this, be, $i).call(this, () => lt(() => c(this, vn).call(this, r)))), c(this, Yt) === 0 && (c(this, st).before(i), j(this, $t, null), bn(
      /** @type {Effect} */
      c(this, Ve),
      () => {
        j(this, Ve, null);
      }
    ), ie(this, be, Ni).call(
      this,
      /** @type {Batch} */
      $
    ));
  }));
}, Cr = function() {
  try {
    if (this.is_pending = this.has_pending_snippet(), j(this, Yt, 0), j(this, _n, 0), j(this, ot, lt(() => {
      c(this, vn).call(this, c(this, st));
    })), c(this, Yt) > 0) {
      var t = j(this, $t, document.createDocumentFragment());
      Qr(c(this, ot), t);
      const i = (
        /** @type {(anchor: Node) => void} */
        c(this, at).pending
      );
      j(this, Ve, lt(() => i(c(this, st))));
    } else
      ie(this, be, Ni).call(
        this,
        /** @type {Batch} */
        $
      );
  } catch (i) {
    this.error(i);
  }
}, /**
 * @param {Batch} batch
 */
Ni = function(t) {
  this.is_pending = !1, t.transfer_effects(c(this, mi), c(this, gi));
}, /**
 * @template T
 * @param {() => T} fn
 */
$i = function(t) {
  var i = X, r = Y, s = De;
  Mt(c(this, Ke)), ft(c(this, Ke)), Vn(c(this, Ke).ctx);
  try {
    return kn.ensure(), t();
  } catch (o) {
    return Aa(o), null;
  } finally {
    Mt(i), ft(r), Vn(s);
  }
}, /**
 * Updates the pending count associated with the currently visible pending snippet,
 * if any, such that we can replace the snippet with content once work is done
 * @param {1 | -1} d
 * @param {Batch} batch
 */
Ar = function(t, i) {
  var r;
  if (!this.has_pending_snippet()) {
    this.parent && ie(r = this.parent, be, Ar).call(r, t, i);
    return;
  }
  j(this, Yt, c(this, Yt) + t), c(this, Yt) === 0 && (ie(this, be, Ni).call(this, i), c(this, Ve) && bn(c(this, Ve), () => {
    j(this, Ve, null);
  }), c(this, $t) && (c(this, st).before(c(this, $t)), j(this, $t, null)));
}, /**
 * @param {unknown} error
 */
Or = function(t) {
  c(this, ot) && (Xe(c(this, ot)), j(this, ot, null)), c(this, Ve) && (Xe(c(this, Ve)), j(this, Ve, null)), c(this, nt) && (Xe(c(this, nt)), j(this, nt, null));
  var i = c(this, at).onerror;
  let r = c(this, at).failed;
  var s = !1, o = !1;
  const l = () => {
    if (s) {
      jl();
      return;
    }
    s = !0, o && Al(), c(this, nt) !== null && bn(c(this, nt), () => {
      j(this, nt, null);
    }), ie(this, be, $i).call(this, () => {
      ie(this, be, Cr).call(this);
    });
  }, a = (f) => {
    try {
      o = !0, i == null || i(f, l), o = !1;
    } catch (_) {
      Jt(_, c(this, Ke) && c(this, Ke).parent);
    }
    r && j(this, nt, ie(this, be, $i).call(this, () => {
      try {
        return lt(() => {
          var _ = (
            /** @type {Effect} */
            X
          );
          _.b = this, _.f |= Tr, r(
            c(this, st),
            () => f,
            () => l
          );
        });
      } catch (_) {
        return Jt(
          _,
          /** @type {Effect} */
          c(this, Ke).parent
        ), null;
      }
    }));
  };
  Xt(() => {
    var f;
    try {
      f = this.transform_error(t);
    } catch (_) {
      Jt(_, c(this, Ke) && c(this, Ke).parent);
      return;
    }
    f !== null && typeof f == "object" && typeof /** @type {any} */
    f.then == "function" ? f.then(
      a,
      /** @param {unknown} e */
      (_) => Jt(_, c(this, Ke) && c(this, Ke).parent)
    ) : a(f);
  });
};
function Jl(e, t, i, r) {
  const s = Vr;
  var o = e.filter((b) => !b.settled), l = t.map(s);
  if (i.length === 0 && o.length === 0) {
    r(l);
    return;
  }
  var a = (
    /** @type {Effect} */
    X
  ), f = Zl(), _ = o.length === 1 ? o[0].promise : o.length > 1 ? Promise.all(o.map((b) => b.promise)) : null;
  function h(b) {
    if (!(a.f & ct)) {
      f();
      try {
        r([...l, ...b]);
      } catch (C) {
        Jt(C, a);
      }
      qi();
    }
  }
  var x = La();
  if (i.length === 0) {
    _.then(() => h([])).finally(x);
    return;
  }
  function d() {
    Promise.all(i.map((b) => /* @__PURE__ */ Xl(b))).then(h).catch((b) => Jt(b, a)).finally(x);
  }
  _ ? _.then(() => {
    f(), d(), qi();
  }) : d();
}
function Zl() {
  var e = (
    /** @type {Effect} */
    X
  ), t = Y, i = De, r = (
    /** @type {Batch} */
    $
  );
  return function(o = !0) {
    Mt(e), ft(t), Vn(i), o && !(e.f & ct) && (r == null || r.activate(), r == null || r.apply());
  };
}
function qi(e = !0) {
  Mt(null), ft(null), Vn(null), e && ($ == null || $.deactivate());
}
function La() {
  var e = (
    /** @type {Effect} */
    X
  ), t = e.b, i = (
    /** @type {Batch} */
    $
  ), r = !!(t != null && t.is_rendered());
  return t == null || t.update_pending_count(1, i), i.increment(r, e), () => {
    t == null || t.update_pending_count(-1, i), i.decrement(r, e);
  };
}
// @__NO_SIDE_EFFECTS__
function Vr(e) {
  var t = Re | $e;
  return X !== null && (X.f |= Yn), {
    ctx: De,
    deps: null,
    effects: null,
    equals: Ea,
    f: t,
    fn: e,
    reactions: null,
    rv: 0,
    v: (
      /** @type {V} */
      xe
    ),
    wv: 0,
    parent: X,
    ac: null
  };
}
const oi = Symbol("obsolete");
// @__NO_SIDE_EFFECTS__
function Xl(e, t, i) {
  let r = (
    /** @type {Effect | null} */
    X
  );
  r === null && yl();
  var s = (
    /** @type {Promise<V>} */
    /** @type {unknown} */
    void 0
  ), o = Sn(
    /** @type {V} */
    xe
  ), l = !Y, a = /* @__PURE__ */ new Set();
  return gu(() => {
    var b, C;
    var f = (
      /** @type {Effect} */
      X
    ), _ = ka();
    s = _.promise;
    try {
      Promise.resolve(e()).then(_.resolve, (p) => {
        p !== Qi && _.reject(p);
      }).finally(qi);
    } catch (p) {
      _.reject(p), qi();
    }
    var h = (
      /** @type {Batch} */
      $
    );
    if (l) {
      if (f.f & Gn)
        var x = La();
      if (
        // boundary can be null if the async derived is inside an $effect.root not connected to the component render tree
        (b = r.b) != null && b.is_rendered()
      )
        (C = h.async_deriveds.get(f)) == null || C.reject(oi);
      else
        for (const p of a.values())
          p.reject(oi);
      a.add(_), h.async_deriveds.set(f, _);
    }
    const d = (p, m = void 0) => {
      x == null || x(), a.delete(_), m !== oi && (h.activate(), m ? (o.f |= Zt, Bn(o, m)) : (o.f & Zt && (o.f ^= Zt), Bn(o, p)), h.deactivate());
    };
    _.promise.then(d, (p) => d(null, p || "unknown"));
  }), Kr(() => {
    for (const f of a)
      f.reject(oi);
  }), new Promise((f) => {
    function _(h) {
      function x() {
        h === s ? f(o) : _(s);
      }
      h.then(x, x);
    }
    _(s);
  });
}
// @__NO_SIDE_EFFECTS__
function ne(e) {
  const t = /* @__PURE__ */ Vr(e);
  return Qa(t), t;
}
// @__NO_SIDE_EFFECTS__
function Ql(e) {
  const t = /* @__PURE__ */ Vr(e);
  return t.equals = xa, t;
}
function eu(e) {
  var t = e.effects;
  if (t !== null) {
    e.effects = null;
    for (var i = 0; i < t.length; i += 1)
      Xe(
        /** @type {Effect} */
        t[i]
      );
  }
}
function Br(e) {
  var t, i = X, r = e.parent;
  if (!en && r !== null && e.v !== xe && // if it was never evaluated before, it's guaranteed to fail downstream, so we try to execute instead
  r.f & (ct | Be))
    return Rl(), e.v;
  Mt(r);
  try {
    e.f &= ~wn, eu(e), t = io(e);
  } finally {
    Mt(i);
  }
  return t;
}
function Pa(e) {
  var t = Br(e);
  if (!e.equals(t) && (e.wv = to(), (!($ != null && $.is_fork) || e.deps === null) && ($ !== null ? ($.capture(e, t, !0), di == null || di.capture(e, t, !0)) : e.v = t, e.deps === null))) {
    ke(e, Ie);
    return;
  }
  en || (Ne !== null ? (Yr() || $ != null && $.is_fork) && Ne.set(e, t) : Wr(e));
}
function tu(e) {
  var t, i;
  if (e.effects !== null)
    for (const r of e.effects)
      (r.teardown || r.ac) && ((t = r.teardown) == null || t.call(r), (i = r.ac) == null || i.abort(Qi), r.fn !== null && (r.teardown = hl), r.ac = null, pi(r, 0), Xr(r));
}
function Fa(e) {
  if (e.effects !== null)
    for (const t of e.effects)
      t.teardown && t.fn !== null && Dn(t);
}
let hr = null, Cn = null, $ = null, di = null, Ne = null, Mr = null, vi = !1, pr = !1, Ln = null, Ri = null;
var Ys = 0;
let nu = 1;
var $n, Kt, hn, Rn, Un, jn, Ut, zn, Je, bi, jt, gt, xt, Hn, pn, ae, Lr, li, Pr, Na, $a, Mn, iu, ui;
const Ki = class Ki {
  constructor() {
    H(this, ae);
    et(this, "id", nu++);
    /** True as soon as `#process` was called */
    H(this, $n, !1);
    et(this, "linked", !0);
    /** @type {Batch | null} */
    H(this, Kt, null);
    /** @type {Batch | null} */
    H(this, hn, null);
    /** @type {Map<Effect, ReturnType<typeof deferred<any>>>} */
    et(this, "async_deriveds", /* @__PURE__ */ new Map());
    /**
     * The current values of any signals that are updated in this batch.
     * Tuple format: [value, is_derived] (note: is_derived is false for deriveds, too, if they were overridden via assignment)
     * They keys of this map are identical to `this.#previous`
     * @type {Map<Value, [any, boolean]>}
     */
    et(this, "current", /* @__PURE__ */ new Map());
    /**
     * The values of any signals (sources and deriveds) that are updated in this batch _before_ those updates took place.
     * They keys of this map are identical to `this.#current`
     * @type {Map<Value, any>}
     */
    et(this, "previous", /* @__PURE__ */ new Map());
    /**
     * When the batch is committed (and the DOM is updated), we need to remove old branches
     * and append new ones by calling the functions added inside (if/each/key/etc) blocks
     * @type {Set<(batch: Batch) => void>}
     */
    H(this, Rn, /* @__PURE__ */ new Set());
    /**
     * If a fork is discarded, we need to destroy any effects that are no longer needed
     * @type {Set<(batch: Batch) => void>}
     */
    H(this, Un, /* @__PURE__ */ new Set());
    /**
     * The number of async effects that are currently in flight
     */
    H(this, jn, 0);
    /**
     * Async effects that are currently in flight, _not_ inside a pending boundary
     * @type {Map<Effect, number>}
     */
    H(this, Ut, /* @__PURE__ */ new Map());
    /**
     * A deferred that resolves when the batch is committed, used with `settled()`
     * TODO replace with Promise.withResolvers once supported widely enough
     * @type {{ promise: Promise<void>, resolve: (value?: any) => void, reject: (reason: unknown) => void } | null}
     */
    H(this, zn, null);
    /**
     * The root effects that need to be flushed
     * @type {Effect[]}
     */
    H(this, Je, []);
    /**
     * Effects created while this batch was active.
     * @type {Effect[]}
     */
    H(this, bi, []);
    /**
     * Deferred effects (which run after async work has completed) that are DIRTY
     * @type {Set<Effect>}
     */
    H(this, jt, /* @__PURE__ */ new Set());
    /**
     * Deferred effects that are MAYBE_DIRTY
     * @type {Set<Effect>}
     */
    H(this, gt, /* @__PURE__ */ new Set());
    /**
     * A map of branches that still exist, but will be destroyed when this batch
     * is committed — we skip over these during `process`.
     * The value contains child effects that were dirty/maybe_dirty before being reset,
     * so they can be rescheduled if the branch survives.
     * @type {Map<Effect, { d: Effect[], m: Effect[] }>}
     */
    H(this, xt, /* @__PURE__ */ new Map());
    /**
     * Inverse of #skipped_branches which we need to tell prior batches to unskip them when committing
     * @type {Set<Effect>}
     */
    H(this, Hn, /* @__PURE__ */ new Set());
    et(this, "is_fork", !1);
    H(this, pn, !1);
    Cn === null ? hr = Cn = this : (j(Cn, hn, this), j(this, Kt, Cn)), Cn = this;
  }
  /**
   * Add an effect to the #skipped_branches map and reset its children
   * @param {Effect} effect
   */
  skip_effect(t) {
    c(this, xt).has(t) || c(this, xt).set(t, { d: [], m: [] }), c(this, Hn).delete(t);
  }
  /**
   * Remove an effect from the #skipped_branches map and reschedule
   * any tracked dirty/maybe_dirty child effects
   * @param {Effect} effect
   * @param {(e: Effect) => void} callback
   */
  unskip_effect(t, i = (r) => this.schedule(r)) {
    var r = c(this, xt).get(t);
    if (r) {
      c(this, xt).delete(t);
      for (var s of r.d)
        ke(s, $e), i(s);
      for (s of r.m)
        ke(s, Ot), i(s);
    }
    c(this, Hn).add(t);
  }
  /**
   * Associate a change to a given source with the current
   * batch, noting its previous and current values
   * @param {Value} source
   * @param {any} value
   * @param {boolean} [is_derived]
   */
  capture(t, i, r = !1) {
    t.v !== xe && !this.previous.has(t) && this.previous.set(t, t.v), t.f & Zt || (this.current.set(t, [i, r]), Ne == null || Ne.set(t, i)), this.is_fork || (t.v = i);
  }
  activate() {
    $ = this;
  }
  deactivate() {
    $ = null, Ne = null;
  }
  flush() {
    try {
      pr = !0, $ = this, ie(this, ae, li).call(this);
    } finally {
      Ys = 0, Mr = null, Ln = null, Ri = null, pr = !1, $ = null, Ne = null, gn.clear();
    }
  }
  discard() {
    var t;
    for (const i of c(this, Un)) i(this);
    c(this, Un).clear();
    for (const i of this.async_deriveds.values())
      i.reject(oi);
    ie(this, ae, ui).call(this), (t = c(this, zn)) == null || t.resolve();
  }
  /**
   * @param {Effect} effect
   */
  register_created_effect(t) {
    c(this, bi).push(t);
  }
  /**
   * @param {boolean} blocking
   * @param {Effect} effect
   */
  increment(t, i) {
    if (j(this, jn, c(this, jn) + 1), t) {
      let r = c(this, Ut).get(i) ?? 0;
      c(this, Ut).set(i, r + 1);
    }
  }
  /**
   * @param {boolean} blocking
   * @param {Effect} effect
   */
  decrement(t, i) {
    if (j(this, jn, c(this, jn) - 1), t) {
      let r = c(this, Ut).get(i) ?? 0;
      r === 1 ? c(this, Ut).delete(i) : c(this, Ut).set(i, r - 1);
    }
    c(this, pn) || (j(this, pn, !0), Xt(() => {
      j(this, pn, !1), this.linked && this.flush();
    }));
  }
  /**
   * @param {Set<Effect>} dirty_effects
   * @param {Set<Effect>} maybe_dirty_effects
   */
  transfer_effects(t, i) {
    for (const r of t)
      c(this, jt).add(r);
    for (const r of i)
      c(this, gt).add(r);
    t.clear(), i.clear();
  }
  /** @param {(batch: Batch) => void} fn */
  oncommit(t) {
    c(this, Rn).add(t);
  }
  /** @param {(batch: Batch) => void} fn */
  ondiscard(t) {
    c(this, Un).add(t);
  }
  settled() {
    return (c(this, zn) ?? j(this, zn, ka())).promise;
  }
  static ensure() {
    if ($ === null) {
      const t = $ = new Ki();
      !pr && !vi && Xt(() => {
        c(t, $n) || t.flush();
      });
    }
    return $;
  }
  apply() {
    {
      Ne = null;
      return;
    }
  }
  /**
   *
   * @param {Effect} effect
   */
  schedule(t) {
    var s;
    if (Mr = t, (s = t.b) != null && s.is_pending && t.f & (qn | Xi | Sa) && !(t.f & Gn)) {
      t.b.defer_effect(t);
      return;
    }
    for (var i = t; i.parent !== null; ) {
      i = i.parent;
      var r = i.f;
      if (Ln !== null && i === X && (Y === null || !(Y.f & Re)))
        return;
      if (r & (Qt | kt)) {
        if (!(r & Ie))
          return;
        i.f ^= Ie;
      }
    }
    c(this, Je).push(i);
  }
};
$n = new WeakMap(), Kt = new WeakMap(), hn = new WeakMap(), Rn = new WeakMap(), Un = new WeakMap(), jn = new WeakMap(), Ut = new WeakMap(), zn = new WeakMap(), Je = new WeakMap(), bi = new WeakMap(), jt = new WeakMap(), gt = new WeakMap(), xt = new WeakMap(), Hn = new WeakMap(), pn = new WeakMap(), ae = new WeakSet(), Lr = function() {
  if (this.is_fork) return !0;
  for (const r of c(this, Ut).keys()) {
    for (var t = r, i = !1; t.parent !== null; ) {
      if (c(this, xt).has(t)) {
        i = !0;
        break;
      }
      t = t.parent;
    }
    if (!i)
      return !0;
  }
  return !1;
}, li = function() {
  var f, _, h, x;
  j(this, $n, !0), Ys++ > 1e3 && (ie(this, ae, ui).call(this), su());
  for (const d of c(this, jt))
    c(this, gt).delete(d), ke(d, $e), this.schedule(d);
  for (const d of c(this, gt))
    ke(d, Ot), this.schedule(d);
  const t = c(this, Je);
  j(this, Je, []), this.apply();
  var i = Ln = [], r = [], s = Ri = [];
  for (const d of t)
    try {
      ie(this, ae, Pr).call(this, d, i, r);
    } catch (b) {
      throw ja(d), ie(this, ae, Lr).call(this) || this.discard(), b;
    }
  if ($ = null, s.length > 0) {
    var o = Ki.ensure();
    for (const d of s)
      o.schedule(d);
  }
  if (Ln = null, Ri = null, ie(this, ae, Lr).call(this)) {
    ie(this, ae, Mn).call(this, r), ie(this, ae, Mn).call(this, i);
    for (const [d, b] of c(this, xt))
      Ua(d, b);
    s.length > 0 && /** @type {unknown} */
    ie(f = $, ae, li).call(f);
    return;
  }
  const l = ie(this, ae, Na).call(this);
  if (l) {
    ie(this, ae, Mn).call(this, r), ie(this, ae, Mn).call(this, i), ie(_ = l, ae, $a).call(_, this);
    return;
  }
  c(this, jt).clear(), c(this, gt).clear();
  for (const d of c(this, Rn)) d(this);
  c(this, Rn).clear(), di = this, Ks(r), Ks(i), di = null, (h = c(this, zn)) == null || h.resolve();
  var a = (
    /** @type {Batch | null} */
    /** @type {unknown} */
    $
  );
  if (c(this, jn) === 0 && (c(this, Je).length === 0 || a !== null) && ie(this, ae, ui).call(this), c(this, Je).length > 0)
    if (a !== null) {
      const d = a;
      c(d, Je).push(...c(this, Je).filter((b) => !c(d, Je).includes(b)));
    } else
      a = this;
  a !== null && ie(x = a, ae, li).call(x);
}, /**
 * Traverse the effect tree, executing effects or stashing
 * them for later execution as appropriate
 * @param {Effect} root
 * @param {Effect[]} effects
 * @param {Effect[]} render_effects
 */
Pr = function(t, i, r) {
  t.f ^= Ie;
  for (var s = t.first; s !== null; ) {
    var o = s.f, l = (o & (kt | Qt)) !== 0, a = l && (o & Ie) !== 0, f = a || (o & Be) !== 0 || c(this, xt).has(s);
    if (!f && s.fn !== null) {
      l ? s.f ^= Ie : o & qn ? i.push(s) : Si(s) && (o & yt && c(this, gt).add(s), Dn(s));
      var _ = s.first;
      if (_ !== null) {
        s = _;
        continue;
      }
    }
    for (; s !== null; ) {
      var h = s.next;
      if (h !== null) {
        s = h;
        break;
      }
      s = s.parent;
    }
  }
}, Na = function() {
  for (var t = c(this, Kt); t !== null; ) {
    if (!t.is_fork) {
      for (const [i, [, r]] of this.current)
        if (t.current.has(i) && !r)
          return t;
    }
    t = c(t, Kt);
  }
  return null;
}, /**
 * @param {Batch} batch
 */
$a = function(t) {
  var r;
  for (const [s, o] of t.current)
    !this.previous.has(s) && t.previous.has(s) && this.previous.set(s, t.previous.get(s)), this.current.set(s, o);
  for (const [s, o] of t.async_deriveds) {
    const l = this.async_deriveds.get(s);
    l && o.promise.then(l.resolve).catch(l.reject);
  }
  t.async_deriveds.clear(), this.transfer_effects(c(t, jt), c(t, gt));
  const i = (s) => {
    var o = s.reactions;
    if (o !== null)
      for (const f of o) {
        var l = f.f;
        if (l & Re)
          i(
            /** @type {Derived} */
            f
          );
        else {
          var a = (
            /** @type {Effect} */
            f
          );
          l & (Pn | yt) && !this.async_deriveds.has(a) && (c(this, gt).delete(a), ke(a, $e), this.schedule(a));
        }
      }
  };
  for (const s of this.current.keys())
    i(s);
  this.oncommit(() => t.discard()), ie(r = t, ae, ui).call(r), $ = this, ie(this, ae, li).call(this);
}, /**
 * @param {Effect[]} effects
 */
Mn = function(t) {
  for (var i = 0; i < t.length; i += 1)
    Ma(t[i], c(this, jt), c(this, gt));
}, iu = function() {
  var x;
  for (let d = hr; d !== null; d = c(d, hn)) {
    var t = d.id < this.id, i = [];
    for (const [b, [C, p]] of this.current) {
      if (d.current.has(b)) {
        var r = (
          /** @type {[any, boolean]} */
          d.current.get(b)[0]
        );
        if (t && C !== r)
          d.current.set(b, [C, p]);
        else
          continue;
      }
      i.push(b);
    }
    if (t)
      for (const [b, C] of this.async_deriveds) {
        const p = d.async_deriveds.get(b);
        p && C.promise.then(p.resolve).catch(p.reject);
      }
    var s = [...d.current.keys()].filter(
      (b) => !/** @type {[any, boolean]} */
      d.current.get(b)[1]
    );
    if (!(!c(d, $n) || s.length === 0)) {
      var o = s.filter((b) => !this.current.has(b));
      if (o.length === 0)
        t && d.discard();
      else if (i.length > 0) {
        if (t)
          for (const b of c(this, Hn))
            d.unskip_effect(b, (C) => {
              var p;
              C.f & (yt | Pn) ? d.schedule(C) : ie(p = d, ae, Mn).call(p, [C]);
            });
        d.activate();
        var l = /* @__PURE__ */ new Set(), a = /* @__PURE__ */ new Map();
        for (var f of i)
          Ra(f, o, l, a);
        a = /* @__PURE__ */ new Map();
        var _ = [...d.current].filter(([b, C]) => {
          const p = this.current.get(b);
          return p ? p[0] !== C[0] || p[1] !== C[1] : !0;
        }).map(([b]) => b);
        if (_.length > 0)
          for (const b of c(this, bi))
            !(b.f & (ct | Be | zi)) && Dr(b, _, a) && (b.f & (Pn | yt) ? (ke(b, $e), d.schedule(b)) : c(d, jt).add(b));
        if (c(d, Je).length > 0 && !c(d, pn)) {
          d.apply();
          for (var h of c(d, Je))
            ie(x = d, ae, Pr).call(x, h, [], []);
          j(d, Je, []);
        }
        d.deactivate();
      }
    }
  }
}, ui = function() {
  if (this.linked) {
    var t = c(this, Kt), i = c(this, hn);
    t === null ? hr = i : j(t, hn, i), i === null ? Cn = t : j(i, Kt, t), this.linked = !1;
  }
};
let kn = Ki;
function ru(e) {
  var t = vi;
  vi = !0;
  try {
    for (var i; ; ) {
      if (Hl(), $ === null)
        return (
          /** @type {T} */
          i
        );
      $.flush();
    }
  } finally {
    vi = t;
  }
}
function su() {
  try {
    El();
  } catch (e) {
    Jt(e, Mr);
  }
}
let mt = null;
function Ks(e) {
  var t = e.length;
  if (t !== 0) {
    for (var i = 0; i < t; ) {
      var r = e[i++];
      if (!(r.f & (ct | Be)) && Si(r) && (mt = /* @__PURE__ */ new Set(), Dn(r), r.deps === null && r.first === null && r.nodes === null && r.teardown === null && r.ac === null && Ja(r), (mt == null ? void 0 : mt.size) > 0)) {
        gn.clear();
        for (const s of mt) {
          if (s.f & (ct | Be)) continue;
          const o = [s];
          let l = s.parent;
          for (; l !== null; )
            mt.has(l) && (mt.delete(l), o.push(l)), l = l.parent;
          for (let a = o.length - 1; a >= 0; a--) {
            const f = o[a];
            f.f & (ct | Be) || Dn(f);
          }
        }
        mt.clear();
      }
    }
    mt = null;
  }
}
function Ra(e, t, i, r) {
  if (!i.has(e) && (i.add(e), e.reactions !== null))
    for (const s of e.reactions) {
      const o = s.f;
      o & Re ? Ra(
        /** @type {Derived} */
        s,
        t,
        i,
        r
      ) : o & (Pn | yt) && !(o & $e) && Dr(s, t, r) && (ke(s, $e), Gr(
        /** @type {Effect} */
        s
      ));
    }
}
function Dr(e, t, i) {
  const r = i.get(e);
  if (r !== void 0) return r;
  if (e.deps !== null)
    for (const s of e.deps) {
      if (ji.call(t, s))
        return !0;
      if (s.f & Re && Dr(
        /** @type {Derived} */
        s,
        t,
        i
      ))
        return i.set(
          /** @type {Derived} */
          s,
          !0
        ), !0;
    }
  return i.set(e, !1), !1;
}
function Gr(e) {
  $.schedule(e);
}
function Ua(e, t) {
  if (!(e.f & kt && e.f & Ie)) {
    e.f & $e ? t.d.push(e) : e.f & Ot && t.m.push(e), ke(e, Ie);
    for (var i = e.first; i !== null; )
      Ua(i, t), i = i.next;
  }
}
function ja(e) {
  ke(e, Ie);
  for (var t = e.first; t !== null; )
    ja(t), t = t.next;
}
let Wi = /* @__PURE__ */ new Set();
const gn = /* @__PURE__ */ new Map();
let za = !1;
function Sn(e, t) {
  var i = {
    f: 0,
    // TODO ideally we could skip this altogether, but it causes type errors
    v: e,
    reactions: null,
    equals: Ea,
    rv: 0,
    wv: 0
  };
  return i;
}
// @__NO_SIDE_EFFECTS__
function G(e, t) {
  const i = Sn(e);
  return Qa(i), i;
}
// @__NO_SIDE_EFFECTS__
function au(e, t = !1, i = !0) {
  const r = Sn(e);
  return t || (r.equals = xa), r;
}
function E(e, t, i = !1) {
  Y !== null && // since we are untracking the function inside `$inspect.with` we need to add this check
  // to ensure we error if state is set inside an inspect effect
  (!wt || Y.f & zi) && Ia() && Y.f & (Re | yt | Pn | zi) && (At === null || !At.has(e)) && Cl();
  let r = i ? zt(t) : t;
  return Bn(e, r, Ri);
}
function Bn(e, t, i = null) {
  if (!e.equals(t)) {
    gn.set(e, en ? t : e.v);
    var r = kn.ensure();
    if (r.capture(e, t), e.f & Re) {
      const s = (
        /** @type {Derived} */
        e
      );
      e.f & $e && Br(s), Ne === null && Wr(s);
    }
    e.wv = to(), Ha(e, $e, i), X !== null && X.f & Ie && !(X.f & (kt | Qt)) && (rt === null ? wu([e]) : rt.push(e)), !r.is_fork && Wi.size > 0 && !za && ou();
  }
  return t;
}
function ou() {
  za = !1;
  for (const e of Wi) {
    e.f & Ie && ke(e, Ot);
    let t;
    try {
      t = Si(e);
    } catch {
      t = !0;
    }
    t && Dn(e);
  }
  Wi.clear();
}
function lu(e, t = 1) {
  var i = n(e), r = t === 1 ? i++ : i--;
  return E(e, i), r;
}
function _i(e) {
  E(e, e.v + 1);
}
function Ha(e, t, i) {
  var r = e.reactions;
  if (r !== null)
    for (var s = r.length, o = 0; o < s; o++) {
      var l = r[o], a = l.f, f = (a & $e) === 0;
      if (f && ke(l, t), a & zi)
        Wi.add(
          /** @type {Effect} */
          l
        );
      else if (a & Re) {
        var _ = (
          /** @type {Derived} */
          l
        );
        Ne == null || Ne.delete(_), a & wn || (a & ut && (X === null || !(X.f & Hi)) && (l.f |= wn), Ha(_, Ot, i));
      } else if (f) {
        var h = (
          /** @type {Effect} */
          l
        );
        a & yt && mt !== null && mt.add(h), i !== null ? i.push(h) : Gr(h);
      }
    }
}
function zt(e) {
  if (typeof e != "object" || e === null || Fn in e)
    return e;
  const t = wa(e);
  if (t !== vl && t !== _l)
    return e;
  var i = /* @__PURE__ */ new Map(), r = zr(e), s = /* @__PURE__ */ G(0), o = yn, l = (a) => {
    if (yn === o)
      return a();
    var f = Y, _ = yn;
    ft(null), Qs(o);
    var h = a();
    return ft(f), Qs(_), h;
  };
  return r && i.set("length", /* @__PURE__ */ G(
    /** @type {any[]} */
    e.length
  )), new Proxy(
    /** @type {any} */
    e,
    {
      defineProperty(a, f, _) {
        (!("value" in _) || _.configurable === !1 || _.enumerable === !1 || _.writable === !1) && xl();
        var h = i.get(f);
        return h === void 0 ? l(() => {
          var x = /* @__PURE__ */ G(_.value);
          return i.set(f, x), x;
        }) : E(h, _.value, !0), !0;
      },
      deleteProperty(a, f) {
        var _ = i.get(f);
        if (_ === void 0) {
          if (f in a) {
            const h = l(() => /* @__PURE__ */ G(xe));
            i.set(f, h), _i(s);
          }
        } else
          E(_, xe), _i(s);
        return !0;
      },
      get(a, f, _) {
        var b;
        if (f === Fn)
          return e;
        var h = i.get(f), x = f in a;
        if (h === void 0 && (!x || (b = fi(a, f)) != null && b.writable) && (h = l(() => {
          var C = zt(x ? a[f] : xe), p = /* @__PURE__ */ G(C);
          return p;
        }), i.set(f, h)), h !== void 0) {
          var d = n(h);
          return d === xe ? void 0 : d;
        }
        return Reflect.get(a, f, _);
      },
      getOwnPropertyDescriptor(a, f) {
        var _ = Reflect.getOwnPropertyDescriptor(a, f);
        if (_ && "value" in _) {
          var h = i.get(f);
          h && (_.value = n(h));
        } else if (_ === void 0) {
          var x = i.get(f), d = x == null ? void 0 : x.v;
          if (x !== void 0 && d !== xe)
            return {
              enumerable: !0,
              configurable: !0,
              value: d,
              writable: !0
            };
        }
        return _;
      },
      has(a, f) {
        var d;
        if (f === Fn)
          return !0;
        var _ = i.get(f), h = _ !== void 0 && _.v !== xe || Reflect.has(a, f);
        if (_ !== void 0 || X !== null && (!h || (d = fi(a, f)) != null && d.writable)) {
          _ === void 0 && (_ = l(() => {
            var b = h ? zt(a[f]) : xe, C = /* @__PURE__ */ G(b);
            return C;
          }), i.set(f, _));
          var x = n(_);
          if (x === xe)
            return !1;
        }
        return h;
      },
      set(a, f, _, h) {
        var L;
        var x = i.get(f), d = f in a;
        if (r && f === "length")
          for (var b = _; b < /** @type {Source<number>} */
          x.v; b += 1) {
            var C = i.get(b + "");
            C !== void 0 ? E(C, xe) : b in a && (C = l(() => /* @__PURE__ */ G(xe)), i.set(b + "", C));
          }
        if (x === void 0)
          (!d || (L = fi(a, f)) != null && L.writable) && (x = l(() => /* @__PURE__ */ G(void 0)), E(x, zt(_)), i.set(f, x));
        else {
          d = x.v !== xe;
          var p = l(() => zt(_));
          E(x, p);
        }
        var m = Reflect.getOwnPropertyDescriptor(a, f);
        if (m != null && m.set && m.set.call(h, _), !d) {
          if (r && typeof f == "string") {
            var A = (
              /** @type {Source<number>} */
              i.get("length")
            ), q = Number(f);
            Number.isInteger(q) && q >= A.v && E(A, q + 1);
          }
          _i(s);
        }
        return !0;
      },
      ownKeys(a) {
        n(s);
        var f = Reflect.ownKeys(a).filter((x) => {
          var d = i.get(x);
          return d === void 0 || d.v !== xe;
        });
        for (var [_, h] of i)
          h.v !== xe && !(_ in a) && f.push(_);
        return f;
      },
      setPrototypeOf() {
        Il();
      }
    }
  );
}
function Js(e) {
  try {
    if (e !== null && typeof e == "object" && Fn in e)
      return e[Fn];
  } catch {
  }
  return e;
}
function uu(e, t) {
  return Object.is(Js(e), Js(t));
}
var Fr, qa, Wa, Va;
function cu() {
  if (Fr === void 0) {
    Fr = window, qa = /Firefox/.test(navigator.userAgent);
    var e = Element.prototype, t = Node.prototype, i = Text.prototype;
    Wa = fi(t, "firstChild").get, Va = fi(t, "nextSibling").get, Ds(e) && (e[xr] = void 0, e[Pi] = null, e[Ir] = void 0, e.__e = void 0), Ds(i) && (i[ai] = void 0);
  }
}
function Ht(e = "") {
  return document.createTextNode(e);
}
// @__NO_SIDE_EFFECTS__
function Vi(e) {
  return (
    /** @type {TemplateNode | null} */
    Wa.call(e)
  );
}
// @__NO_SIDE_EFFECTS__
function ki(e) {
  return (
    /** @type {TemplateNode | null} */
    Va.call(e)
  );
}
function v(e, t) {
  return /* @__PURE__ */ Vi(e);
}
function Le(e, t = !1) {
  {
    var i = /* @__PURE__ */ Vi(e);
    return i instanceof Comment && i.data === "" ? /* @__PURE__ */ ki(i) : i;
  }
}
function w(e, t = 1, i = !1) {
  let r = e;
  for (; t--; )
    r = /** @type {TemplateNode} */
    /* @__PURE__ */ ki(r);
  return r;
}
function fu(e) {
  e.textContent = "";
}
function Ba() {
  return !1;
}
function du(e, t, i) {
  return (
    /** @type {T extends keyof HTMLElementTagNameMap ? HTMLElementTagNameMap[T] : Element} */
    i ? document.createElement(e, { is: i }) : document.createElement(e)
  );
}
let Zs = !1;
function vu() {
  Zs || (Zs = !0, document.addEventListener(
    "reset",
    (e) => {
      Promise.resolve().then(() => {
        var t;
        if (!e.defaultPrevented)
          for (
            const i of
            /**@type {HTMLFormElement} */
            e.target.elements
          )
            (t = i[Fi]) == null || t.call(i);
      });
    },
    // In the capture phase to guarantee we get noticed of it (no possibility of stopPropagation)
    { capture: !0 }
  ));
}
function er(e) {
  var t = Y, i = X;
  ft(null), Mt(null);
  try {
    return e();
  } finally {
    ft(t), Mt(i);
  }
}
function Da(e, t, i, r = i) {
  e.addEventListener(t, () => er(i));
  const s = (
    /** @type {any} */
    e[Fi]
  );
  s ? e[Fi] = () => {
    s(), r(!0);
  } : e[Fi] = () => r(!0), vu();
}
function _u(e) {
  X === null && (Y === null && Tl(), Sl()), en && kl();
}
function hu(e, t) {
  var i = t.last;
  i === null ? t.last = t.first = e : (i.next = e, e.prev = i, t.last = e);
}
function qt(e, t) {
  var i = X;
  i !== null && i.f & Be && (e |= Be);
  var r = {
    ctx: De,
    deps: null,
    nodes: null,
    f: e | $e | ut,
    first: null,
    fn: t,
    last: null,
    next: null,
    parent: i,
    b: i && i.b,
    prev: null,
    teardown: null,
    wv: 0,
    ac: null
  };
  $ == null || $.register_created_effect(r);
  var s = r;
  if (e & qn)
    Ln !== null ? Ln.push(r) : kn.ensure().schedule(r);
  else if (t !== null) {
    try {
      Dn(r);
    } catch (l) {
      throw Xe(r), l;
    }
    s.deps === null && s.teardown === null && s.nodes === null && s.first === s.last && // either `null`, or a singular child
    !(s.f & Yn) && (s = s.first, e & yt && e & Wn && s !== null && (s.f |= Wn));
  }
  if (s !== null && (s.parent = i, i !== null && hu(s, i), Y !== null && Y.f & Re && !(e & Qt))) {
    var o = (
      /** @type {Derived} */
      Y
    );
    (o.effects ?? (o.effects = [])).push(s);
  }
  return r;
}
function Yr() {
  return Y !== null && !wt;
}
function Kr(e) {
  const t = qt(Xi, null);
  return ke(t, Ie), t.teardown = e, t;
}
function pu(e) {
  _u();
  var t = (
    /** @type {Effect} */
    X.f
  ), i = !Y && (t & kt) !== 0 && De !== null && !De.i;
  if (i) {
    var r = (
      /** @type {ComponentContext} */
      De
    );
    (r.e ?? (r.e = [])).push(e);
  } else
    return Ga(e);
}
function Ga(e) {
  return qt(qn | gl, e);
}
function mu(e) {
  kn.ensure();
  const t = qt(Qt | Yn, e);
  return (i = {}) => new Promise((r) => {
    i.outro ? bn(t, () => {
      Xe(t), r(void 0);
    }) : (Xe(t), r(void 0));
  });
}
function Ya(e) {
  return qt(qn, e);
}
function gu(e) {
  return qt(Pn | Yn, e);
}
function Jr(e, t = 0) {
  return qt(Xi | t, e);
}
function z(e, t = [], i = [], r = []) {
  Jl(r, t, i, (s) => {
    qt(Xi, () => {
      e(...s.map(n));
    });
  });
}
function Zr(e, t = 0) {
  var i = qt(yt | t, e);
  return i;
}
function lt(e) {
  return qt(kt | Yn, e);
}
function Ka(e) {
  var t = e.teardown;
  if (t !== null) {
    const i = en, r = Y;
    Xs(!0), ft(null);
    try {
      t.call(null);
    } finally {
      Xs(i), ft(r);
    }
  }
}
function Xr(e, t = !1) {
  var i = e.first;
  for (e.first = e.last = null; i !== null; ) {
    const s = i.ac;
    s !== null && er(() => {
      s.abort(Qi);
    });
    var r = i.next;
    i.f & Qt ? i.parent = null : Xe(i, t), i = r;
  }
}
function bu(e) {
  for (var t = e.first; t !== null; ) {
    var i = t.next;
    t.f & kt || Xe(t), t = i;
  }
}
function Xe(e, t = !0) {
  var i = !1;
  (t || e.f & ml) && e.nodes !== null && e.nodes.end !== null && (yu(
    e.nodes.start,
    /** @type {TemplateNode} */
    e.nodes.end
  ), i = !0), e.f |= Er, Xr(e, t && !i), pi(e, 0);
  var r = e.nodes && e.nodes.t;
  if (r !== null)
    for (const o of r)
      o.stop();
  Ka(e), e.f ^= Er, e.f |= ct;
  var s = e.parent;
  s !== null && s.first !== null && Ja(e), e.next = e.prev = e.teardown = e.ctx = e.deps = e.fn = e.nodes = e.ac = e.b = null;
}
function yu(e, t) {
  for (; e !== null; ) {
    var i = e === t ? null : /* @__PURE__ */ ki(e);
    e.remove(), e = i;
  }
}
function Ja(e) {
  var t = e.parent, i = e.prev, r = e.next;
  i !== null && (i.next = r), r !== null && (r.prev = i), t !== null && (t.first === e && (t.first = r), t.last === e && (t.last = i));
}
function bn(e, t, i = !0) {
  var r = [];
  Za(e, r, !0);
  var s = () => {
    i && Xe(e), t && t();
  }, o = r.length;
  if (o > 0) {
    var l = () => --o || s();
    for (var a of r)
      a.out(l);
  } else
    s();
}
function Za(e, t, i) {
  if (!(e.f & Be)) {
    e.f ^= Be;
    var r = e.nodes && e.nodes.t;
    if (r !== null)
      for (const a of r)
        (a.is_global || i) && t.push(a);
    for (var s = e.first; s !== null; ) {
      var o = s.next;
      if (!(s.f & Qt)) {
        var l = (s.f & Wn) !== 0 || // If this is a branch effect without a block effect parent,
        // it means the parent block effect was pruned. In that case,
        // transparency information was transferred to the branch effect.
        (s.f & kt) !== 0 && (e.f & yt) !== 0;
        Za(s, t, l ? i : !1);
      }
      s = o;
    }
  }
}
function Bi(e) {
  Xa(e, !0);
}
function Xa(e, t) {
  if (e.f & Be) {
    e.f ^= Be, e.f & Ie || (ke(e, $e), kn.ensure().schedule(e));
    for (var i = e.first; i !== null; ) {
      var r = i.next, s = (i.f & Wn) !== 0 || (i.f & kt) !== 0;
      Xa(i, s ? t : !1), i = r;
    }
    var o = e.nodes && e.nodes.t;
    if (o !== null)
      for (const l of o)
        (l.is_global || t) && l.in();
  }
}
function Qr(e, t) {
  if (e.nodes)
    for (var i = e.nodes.start, r = e.nodes.end; i !== null; ) {
      var s = i === r ? null : /* @__PURE__ */ ki(i);
      t.append(i), i = s;
    }
}
let Ui = !1, en = !1;
function Xs(e) {
  en = e;
}
let Y = null, wt = !1;
function ft(e) {
  Y = e;
}
let X = null;
function Mt(e) {
  X = e;
}
let At = null;
function Qa(e) {
  Y !== null && (At ?? (At = /* @__PURE__ */ new Set())).add(e);
}
let Ze = null, tt = 0, rt = null;
function wu(e) {
  rt = e;
}
let eo = 1, cn = 0, yn = cn;
function Qs(e) {
  yn = e;
}
function to() {
  return ++eo;
}
function Si(e) {
  var t = e.f;
  if (t & $e)
    return !0;
  if (t & Re && (e.f &= ~wn), t & Ot) {
    for (var i = (
      /** @type {Value[]} */
      e.deps
    ), r = i.length, s = 0; s < r; s++) {
      var o = i[s];
      if (Si(
        /** @type {Derived} */
        o
      ) && Pa(
        /** @type {Derived} */
        o
      ), o.wv > e.wv)
        return !0;
    }
    t & ut && // During time traveling we don't want to reset the status so that
    // traversal of the graph in the other batches still happens
    Ne === null && ke(e, Ie);
  }
  return !1;
}
function no(e, t, i = !0) {
  var r = e.reactions;
  if (r !== null && !(At !== null && At.has(e)))
    for (var s = 0; s < r.length; s++) {
      var o = r[s];
      o.f & Re ? no(
        /** @type {Derived} */
        o,
        t,
        !1
      ) : t === o && (i ? ke(o, $e) : o.f & Ie && ke(o, Ot), Gr(
        /** @type {Effect} */
        o
      ));
    }
}
function io(e) {
  var p;
  var t = Ze, i = tt, r = rt, s = Y, o = At, l = De, a = wt, f = yn, _ = e.f;
  Ze = /** @type {null | Value[]} */
  null, tt = 0, rt = null, Y = _ & (kt | Qt) ? null : e, At = null, Vn(e.ctx), wt = !1, yn = ++cn, e.ac !== null && (er(() => {
    e.ac.abort(Qi);
  }), e.ac = null);
  try {
    e.f |= Hi;
    var h = (
      /** @type {Function} */
      e.fn
    ), x = h();
    e.f |= Gn;
    var d = e.deps, b = $ == null ? void 0 : $.is_fork;
    if (Ze !== null) {
      var C;
      if (b || pi(e, tt), d !== null && tt > 0)
        for (d.length = tt + Ze.length, C = 0; C < Ze.length; C++)
          d[tt + C] = Ze[C];
      else
        e.deps = d = Ze;
      if (Yr() && e.f & ut)
        for (C = tt; C < d.length; C++)
          ((p = d[C]).reactions ?? (p.reactions = [])).push(e);
    } else !b && d !== null && tt < d.length && (pi(e, tt), d.length = tt);
    if (Ia() && rt !== null && !wt && d !== null && !(e.f & (Re | Ot | $e)))
      for (C = 0; C < /** @type {Source[]} */
      rt.length; C++)
        no(
          rt[C],
          /** @type {Effect} */
          e
        );
    if (s !== null && s !== e) {
      if (cn++, s.deps !== null)
        for (let m = 0; m < i; m += 1)
          s.deps[m].rv = cn;
      if (t !== null)
        for (const m of t)
          m.rv = cn;
      rt !== null && (r === null ? r = rt : r.push(.../** @type {Source[]} */
      rt));
    }
    return e.f & Zt && (e.f ^= Zt), x;
  } catch (m) {
    return Aa(m);
  } finally {
    e.f ^= Hi, Ze = t, tt = i, rt = r, Y = s, At = o, Vn(l), wt = a, yn = f;
  }
}
function ku(e, t) {
  let i = t.reactions;
  if (i !== null) {
    var r = cl.call(i, e);
    if (r !== -1) {
      var s = i.length - 1;
      s === 0 ? i = t.reactions = null : (i[r] = i[s], i.pop());
    }
  }
  if (i === null && t.f & Re && // Destroying a child effect while updating a parent effect can cause a dependency to appear
  // to be unused, when in fact it is used by the currently-updating parent. Checking `new_deps`
  // allows us to skip the expensive work of disconnecting and immediately reconnecting it
  (Ze === null || !ji.call(Ze, t))) {
    var o = (
      /** @type {Derived} */
      t
    );
    o.f & ut && (o.f ^= ut, o.f &= ~wn), o.v !== xe && Wr(o), tu(o), pi(o, 0);
  }
}
function pi(e, t) {
  var i = e.deps;
  if (i !== null)
    for (var r = t; r < i.length; r++)
      ku(e, i[r]);
}
function Dn(e) {
  var t = e.f;
  if (!(t & ct)) {
    ke(e, Ie);
    var i = X, r = Ui;
    X = e, Ui = !0;
    try {
      t & (yt | Sa) ? bu(e) : Xr(e), Ka(e);
      var s = io(e);
      e.teardown = typeof s == "function" ? s : null, e.wv = eo;
      var o;
    } finally {
      Ui = r, X = i;
    }
  }
}
async function Su() {
  await Promise.resolve(), ru();
}
function n(e) {
  var t = e.f, i = (t & Re) !== 0;
  if (Y !== null && !wt) {
    var r = X !== null && (X.f & ct) !== 0;
    if (!r && (At === null || !At.has(e))) {
      var s = Y.deps;
      if (Y.f & Hi)
        e.rv < cn && (e.rv = cn, Ze === null && s !== null && s[tt] === e ? tt++ : Ze === null ? Ze = [e] : Ze.push(e));
      else {
        Y.deps ?? (Y.deps = []), ji.call(Y.deps, e) || Y.deps.push(e);
        var o = e.reactions;
        o === null ? e.reactions = [Y] : ji.call(o, Y) || o.push(Y);
      }
    }
  }
  if (en && gn.has(e))
    return gn.get(e);
  if (i) {
    var l = (
      /** @type {Derived} */
      e
    );
    if (en) {
      var a = l.v;
      return (!(l.f & Ie) && l.reactions !== null || so(l)) && (a = Br(l)), gn.set(l, a), a;
    }
    var f = (l.f & ut) === 0 && !wt && Y !== null && (Ui || (Y.f & ut) !== 0), _ = (l.f & Gn) === 0;
    Si(l) && (f && (l.f |= ut), Pa(l)), f && !_ && (Fa(l), ro(l));
  }
  if (Ne != null && Ne.has(e))
    return Ne.get(e);
  if (e.f & Zt)
    throw e.v;
  return e.v;
}
function ro(e) {
  if (e.f |= ut, e.deps !== null)
    for (const t of e.deps)
      (t.reactions ?? (t.reactions = [])).push(e), t.f & Re && !(t.f & ut) && (Fa(
        /** @type {Derived} */
        t
      ), ro(
        /** @type {Derived} */
        t
      ));
}
function so(e) {
  if (e.v === xe) return !0;
  if (e.deps === null) return !1;
  for (const t of e.deps)
    if (gn.has(t) || t.f & Re && so(
      /** @type {Derived} */
      t
    ))
      return !0;
  return !1;
}
function es(e) {
  var t = wt;
  try {
    return wt = !0, e();
  } finally {
    wt = t;
  }
}
const Tu = ["touchstart", "touchmove"];
function Eu(e) {
  return Tu.includes(e);
}
const fn = Symbol("events"), ao = /* @__PURE__ */ new Set(), Nr = /* @__PURE__ */ new Set();
function xu(e, t, i, r = {}) {
  function s(o) {
    if (r.capture || $r.call(t, o), !o.cancelBubble)
      return er(() => i == null ? void 0 : i.call(this, o));
  }
  return e.startsWith("pointer") || e.startsWith("touch") || e === "wheel" ? Xt(() => {
    t.addEventListener(e, s, r);
  }) : t.addEventListener(e, s, r), s;
}
function Iu(e, t, i, r, s) {
  var o = { capture: r, passive: s }, l = xu(e, t, i, o);
  (t === document.body || // @ts-ignore
  t === window || // @ts-ignore
  t === document || // Firefox has quirky behavior, it can happen that we still get "canplay" events when the element is already removed
  t instanceof HTMLMediaElement) && Kr(() => {
    t.removeEventListener(e, l, o);
  });
}
function W(e, t, i) {
  (t[fn] ?? (t[fn] = {}))[e] = i;
}
function oo(e) {
  for (var t = 0; t < e.length; t++)
    ao.add(e[t]);
  for (var i of Nr)
    i(e);
}
let ea = null;
function $r(e) {
  var p, m;
  var t = this, i = (
    /** @type {Node} */
    t.ownerDocument
  ), r = e.type, s = ((p = e.composedPath) == null ? void 0 : p.call(e)) || [], o = (
    /** @type {null | Element} */
    s[0] || e.target
  );
  ea = e;
  var l = 0, a = ea === e && e[fn];
  if (a) {
    var f = s.indexOf(a);
    if (f !== -1 && (t === document || t === /** @type {any} */
    window)) {
      e[fn] = t;
      return;
    }
    var _ = s.indexOf(t);
    if (_ === -1)
      return;
    f <= _ && (l = f);
  }
  if (o = /** @type {Element} */
  s[l] || e.target, o !== t) {
    fl(e, "currentTarget", {
      configurable: !0,
      get() {
        return o || i;
      }
    });
    var h = Y, x = X;
    ft(null), Mt(null);
    try {
      for (var d, b = []; o !== null && o !== t; ) {
        try {
          var C = (m = o[fn]) == null ? void 0 : m[r];
          C != null && (!/** @type {any} */
          o.disabled || // DOM could've been updated already by the time this is reached, so we check this as well
          // -> the target could not have been disabled because it emits the event in the first place
          e.target === o) && C.call(o, e);
        } catch (A) {
          d ? b.push(A) : d = A;
        }
        if (e.cancelBubble) break;
        l++, o = l < s.length ? (
          /** @type {Element} */
          s[l]
        ) : null;
      }
      if (d) {
        for (let A of b)
          queueMicrotask(() => {
            throw A;
          });
        throw d;
      }
    } finally {
      e[fn] = t, delete e.currentTarget, ft(h), Mt(x);
    }
  }
}
var ba;
const mr = (
  // We gotta write it like this because after downleveling the pure comment may end up in the wrong location
  ((ba = globalThis == null ? void 0 : globalThis.window) == null ? void 0 : ba.trustedTypes) && /* @__PURE__ */ globalThis.window.trustedTypes.createPolicy("svelte-trusted-html", {
    /** @param {string} html */
    createHTML: (e) => e
  })
);
function Cu(e) {
  return (
    /** @type {string} */
    (mr == null ? void 0 : mr.createHTML(e)) ?? e
  );
}
function Au(e) {
  var t = du("template");
  return t.innerHTML = Cu(e.replaceAll("<!>", "<!---->")), t.content;
}
function Di(e, t) {
  var i = (
    /** @type {Effect} */
    X
  );
  i.nodes === null && (i.nodes = { start: e, end: t, a: null, t: null });
}
// @__NO_SIDE_EFFECTS__
function M(e, t) {
  var i = (t & Fl) !== 0, r = (t & Nl) !== 0, s, o = !e.startsWith("<!>");
  return () => {
    s === void 0 && (s = Au(o ? e : "<!>" + e), i || (s = /** @type {TemplateNode} */
    /* @__PURE__ */ Vi(s)));
    var l = (
      /** @type {TemplateNode} */
      r || qa ? document.importNode(s, !0) : s.cloneNode(!0)
    );
    if (i) {
      var a = (
        /** @type {TemplateNode} */
        /* @__PURE__ */ Vi(l)
      ), f = (
        /** @type {TemplateNode} */
        l.lastChild
      );
      Di(a, f);
    } else
      Di(l, l);
    return l;
  };
}
function Vt(e = "") {
  {
    var t = Ht(e + "");
    return Di(t, t), t;
  }
}
function dn() {
  var e = document.createDocumentFragment(), t = document.createComment(""), i = Ht();
  return e.append(t, i), Di(t, i), e;
}
function T(e, t) {
  e !== null && e.before(
    /** @type {Node} */
    t
  );
}
function N(e, t) {
  var i = t == null ? "" : typeof t == "object" ? `${t}` : t;
  i !== /** @type {any} */
  (e[ai] ?? (e[ai] = e.nodeValue)) && (e[ai] = i, e.nodeValue = `${i}`);
}
function ta(e, t) {
  return Ou(e, t);
}
const Li = /* @__PURE__ */ new Map();
function Ou(e, { target: t, anchor: i, props: r = {}, events: s, context: o, intro: l = !0, transformError: a }) {
  cu();
  var f = void 0, _ = mu(() => {
    var h = i ?? t.appendChild(Ht());
    Bl(
      /** @type {TemplateNode} */
      h,
      {
        pending: () => {
        }
      },
      (b) => {
        Hr({});
        var C = (
          /** @type {ComponentContext} */
          De
        );
        o && (C.c = o), s && (r.$$events = s), f = e(b, r) || {}, qr();
      },
      a
    );
    var x = /* @__PURE__ */ new Set(), d = (b) => {
      for (var C = 0; C < b.length; C++) {
        var p = b[C];
        if (!x.has(p)) {
          x.add(p);
          var m = Eu(p);
          for (const L of [t, document]) {
            var A = Li.get(L);
            A === void 0 && (A = /* @__PURE__ */ new Map(), Li.set(L, A));
            var q = A.get(p);
            q === void 0 ? (L.addEventListener(p, $r, { passive: m }), A.set(p, 1)) : A.set(p, q + 1);
          }
        }
      }
    };
    return d(Zi(ao)), Nr.add(d), () => {
      var m;
      for (var b of x)
        for (const A of [t, document]) {
          var C = (
            /** @type {Map<string, number>} */
            Li.get(A)
          ), p = (
            /** @type {number} */
            C.get(b)
          );
          --p == 0 ? (A.removeEventListener(b, $r), C.delete(b), C.size === 0 && Li.delete(A)) : C.set(b, p);
        }
      Nr.delete(d), h !== i && ((m = h.parentNode) == null || m.removeChild(h));
    };
  });
  return Mu.set(f, _), f;
}
let Mu = /* @__PURE__ */ new WeakMap();
var bt, It, it, mn, yi, wi, Ji;
class Lu {
  /**
   * @param {TemplateNode} anchor
   * @param {boolean} transition
   */
  constructor(t, i = !0) {
    /** @type {TemplateNode} */
    et(this, "anchor");
    /** @type {Map<Batch, Key>} */
    H(this, bt, /* @__PURE__ */ new Map());
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
    H(this, It, /* @__PURE__ */ new Map());
    /**
     * Similar to #onscreen with respect to the keys, but contains branches that are not yet
     * in the DOM, because their insertion is deferred.
     * @type {Map<Key, Branch>}
     */
    H(this, it, /* @__PURE__ */ new Map());
    /**
     * Keys of effects that are currently outroing
     * @type {Set<Key>}
     */
    H(this, mn, /* @__PURE__ */ new Set());
    /**
     * Whether to pause (i.e. outro) on change, or destroy immediately.
     * This is necessary for `<svelte:element>`
     */
    H(this, yi, !0);
    /**
     * @param {Batch} batch
     */
    H(this, wi, (t) => {
      if (c(this, bt).has(t)) {
        var i = (
          /** @type {Key} */
          c(this, bt).get(t)
        ), r = c(this, It).get(i);
        if (r)
          Bi(r), c(this, mn).delete(i);
        else {
          var s = c(this, it).get(i);
          s && (Bi(s.effect), c(this, It).set(i, s.effect), c(this, it).delete(i), s.fragment.lastChild.remove(), this.anchor.before(s.fragment), r = s.effect);
        }
        for (const [o, l] of c(this, bt)) {
          if (c(this, bt).delete(o), o === t)
            break;
          const a = c(this, it).get(l);
          a && (Xe(a.effect), c(this, it).delete(l));
        }
        for (const [o, l] of c(this, It)) {
          if (o === i || c(this, mn).has(o)) continue;
          const a = () => {
            if (Array.from(c(this, bt).values()).includes(o)) {
              var _ = document.createDocumentFragment();
              Qr(l, _), _.append(Ht()), c(this, it).set(o, { effect: l, fragment: _ });
            } else
              Xe(l);
            c(this, mn).delete(o), c(this, It).delete(o);
          };
          c(this, yi) || !r ? (c(this, mn).add(o), bn(l, a, !1)) : a();
        }
      }
    });
    /**
     * @param {Batch} batch
     */
    H(this, Ji, (t) => {
      c(this, bt).delete(t);
      const i = Array.from(c(this, bt).values());
      for (const [r, s] of c(this, it))
        i.includes(r) || (Xe(s.effect), c(this, it).delete(r));
    });
    this.anchor = t, j(this, yi, i);
  }
  /**
   *
   * @param {any} key
   * @param {null | ((target: TemplateNode) => void)} fn
   */
  ensure(t, i) {
    var r = (
      /** @type {Batch} */
      $
    ), s = Ba();
    if (i && !c(this, It).has(t) && !c(this, it).has(t))
      if (s) {
        var o = document.createDocumentFragment(), l = Ht();
        o.append(l), c(this, it).set(t, {
          effect: lt(() => i(l)),
          fragment: o
        });
      } else
        c(this, It).set(
          t,
          lt(() => i(this.anchor))
        );
    if (c(this, bt).set(r, t), s) {
      for (const [a, f] of c(this, It))
        a === t ? r.unskip_effect(f) : r.skip_effect(f);
      for (const [a, f] of c(this, it))
        a === t ? r.unskip_effect(f.effect) : r.skip_effect(f.effect);
      r.oncommit(c(this, wi)), r.ondiscard(c(this, Ji));
    } else
      c(this, wi).call(this, r);
  }
}
bt = new WeakMap(), It = new WeakMap(), it = new WeakMap(), mn = new WeakMap(), yi = new WeakMap(), wi = new WeakMap(), Ji = new WeakMap();
function R(e, t, i = !1) {
  var r = new Lu(e), s = i ? Wn : 0;
  function o(l, a) {
    r.ensure(l, a);
  }
  Zr(() => {
    var l = !1;
    t((a, f = 0) => {
      l = !0, o(f, a);
    }), l || o(-1, null);
  }, s);
}
function Bt(e, t) {
  return t;
}
function Pu(e, t, i) {
  for (var r = [], s = t.length, o, l = t.length, a = 0; a < s; a++) {
    let x = t[a];
    bn(
      x,
      () => {
        if (o) {
          if (o.pending.delete(x), o.done.add(x), o.pending.size === 0) {
            var d = (
              /** @type {Set<EachOutroGroup>} */
              e.outrogroups
            );
            Rr(e, Zi(o.done)), d.delete(o), d.size === 0 && (e.outrogroups = null);
          }
        } else
          l -= 1;
      },
      !1
    );
  }
  if (l === 0) {
    var f = r.length === 0 && i !== null;
    if (f) {
      var _ = (
        /** @type {Element} */
        i
      ), h = (
        /** @type {Element} */
        _.parentNode
      );
      fu(h), h.append(_), e.items.clear();
    }
    Rr(e, t, !f);
  } else
    o = {
      pending: new Set(t),
      done: /* @__PURE__ */ new Set()
    }, (e.outrogroups ?? (e.outrogroups = /* @__PURE__ */ new Set())).add(o);
}
function Rr(e, t, i = !0) {
  var r;
  if (e.pending.size > 0) {
    r = /* @__PURE__ */ new Set();
    for (const l of e.pending.values())
      for (const a of l)
        r.add(
          /** @type {EachItem} */
          e.items.get(a).e
        );
  }
  for (var s = 0; s < t.length; s++) {
    var o = t[s];
    if (r != null && r.has(o)) {
      o.f |= Ct;
      const l = document.createDocumentFragment();
      Qr(o, l);
    } else
      Xe(t[s], i);
  }
}
var na;
function Nt(e, t, i, r, s, o = null) {
  var l = e, a = /* @__PURE__ */ new Map(), f = (t & Ta) !== 0;
  if (f) {
    var _ = (
      /** @type {Element} */
      e
    );
    l = _.appendChild(Ht());
  }
  var h = null, x = /* @__PURE__ */ Ql(() => {
    var L = i();
    return (
      /** @type {V[]} */
      zr(L) ? L : L == null ? [] : Zi(L)
    );
  }), d, b = /* @__PURE__ */ new Map(), C = !0;
  function p(L) {
    q.effect.f & ct || (q.pending.delete(L), q.fallback = h, Fu(q, d, l, t, r), h !== null && (d.length === 0 ? h.f & Ct ? (h.f ^= Ct, ci(h, null, l)) : Bi(h) : bn(h, () => {
      h = null;
    })));
  }
  function m(L) {
    q.pending.delete(L);
  }
  var A = Zr(() => {
    d = /** @type {V[]} */
    n(x);
    for (var L = d.length, Z = /* @__PURE__ */ new Set(), oe = (
      /** @type {Batch} */
      $
    ), Se = Ba(), le = 0; le < L; le += 1) {
      var he = d[le], Pe = r(he, le), pe = C ? null : a.get(Pe);
      pe ? (pe.v && Bn(pe.v, he), pe.i && Bn(pe.i, le), Se && oe.unskip_effect(pe.e)) : (pe = Nu(
        a,
        C ? l : na ?? (na = Ht()),
        he,
        Pe,
        le,
        s,
        t,
        i
      ), C || (pe.e.f |= Ct), a.set(Pe, pe)), Z.add(Pe);
    }
    if (L === 0 && o && !h && (C ? h = lt(() => o(l)) : (h = lt(() => o(na ?? (na = Ht()))), h.f |= Ct)), L > Z.size && wl(), !C)
      if (b.set(oe, Z), Se) {
        for (const [ye, Ue] of a)
          Z.has(ye) || oe.skip_effect(Ue.e);
        oe.oncommit(p), oe.ondiscard(m);
      } else
        p(oe);
    n(x);
  }), q = { effect: A, items: a, pending: b, outrogroups: null, fallback: h };
  C = !1;
}
function ri(e) {
  for (; e !== null && !(e.f & kt); )
    e = e.next;
  return e;
}
function Fu(e, t, i, r, s) {
  var pe, ye, Ue, O, Ge, dt, vt, St, tn;
  var o = (r & Ll) !== 0, l = t.length, a = e.items, f = ri(e.effect.first), _, h = null, x, d = [], b = [], C, p, m, A;
  if (o)
    for (A = 0; A < l; A += 1)
      C = t[A], p = s(C, A), m = /** @type {EachItem} */
      a.get(p).e, m.f & Ct || ((ye = (pe = m.nodes) == null ? void 0 : pe.a) == null || ye.measure(), (x ?? (x = /* @__PURE__ */ new Set())).add(m));
  for (A = 0; A < l; A += 1) {
    if (C = t[A], p = s(C, A), m = /** @type {EachItem} */
    a.get(p).e, e.outrogroups !== null)
      for (const qe of e.outrogroups)
        qe.pending.delete(m), qe.done.delete(m);
    if (m.f & Be && (Bi(m), o && ((O = (Ue = m.nodes) == null ? void 0 : Ue.a) == null || O.unfix(), (x ?? (x = /* @__PURE__ */ new Set())).delete(m))), m.f & Ct)
      if (m.f ^= Ct, m === f)
        ci(m, null, i);
      else {
        var q = h ? h.next : f;
        m === e.effect.last && (e.effect.last = m.prev), m.prev && (m.prev.next = m.next), m.next && (m.next.prev = m.prev), Dt(e, h, m), Dt(e, m, q), ci(m, q, i), h = m, d = [], b = [], f = ri(h.next);
        continue;
      }
    if (m !== f) {
      if (_ !== void 0 && _.has(m)) {
        if (d.length < b.length) {
          var L = b[0], Z;
          h = L.prev;
          var oe = d[0], Se = d[d.length - 1];
          for (Z = 0; Z < d.length; Z += 1)
            ci(d[Z], L, i);
          for (Z = 0; Z < b.length; Z += 1)
            _.delete(b[Z]);
          Dt(e, oe.prev, Se.next), Dt(e, h, oe), Dt(e, Se, L), f = L, h = Se, A -= 1, d = [], b = [];
        } else
          _.delete(m), ci(m, f, i), Dt(e, m.prev, m.next), Dt(e, m, h === null ? e.effect.first : h.next), Dt(e, h, m), h = m;
        continue;
      }
      for (d = [], b = []; f !== null && f !== m; )
        (_ ?? (_ = /* @__PURE__ */ new Set())).add(f), b.push(f), f = ri(f.next);
      if (f === null)
        continue;
    }
    m.f & Ct || d.push(m), h = m, f = ri(m.next);
  }
  if (e.outrogroups !== null) {
    for (const qe of e.outrogroups)
      qe.pending.size === 0 && (Rr(e, Zi(qe.done)), (Ge = e.outrogroups) == null || Ge.delete(qe));
    e.outrogroups.size === 0 && (e.outrogroups = null);
  }
  if (f !== null || _ !== void 0) {
    var le = [];
    if (_ !== void 0)
      for (m of _)
        m.f & Be || le.push(m);
    for (; f !== null; )
      !(f.f & Be) && f !== e.fallback && le.push(f), f = ri(f.next);
    var he = le.length;
    if (he > 0) {
      var Pe = r & Ta && l === 0 ? i : null;
      if (o) {
        for (A = 0; A < he; A += 1)
          (vt = (dt = le[A].nodes) == null ? void 0 : dt.a) == null || vt.measure();
        for (A = 0; A < he; A += 1)
          (tn = (St = le[A].nodes) == null ? void 0 : St.a) == null || tn.fix();
      }
      Pu(e, le, Pe);
    }
  }
  o && Xt(() => {
    var qe, _t;
    if (x !== void 0)
      for (m of x)
        (_t = (qe = m.nodes) == null ? void 0 : qe.a) == null || _t.apply();
  });
}
function Nu(e, t, i, r, s, o, l, a) {
  var f = l & Ol ? l & Pl ? Sn(i) : /* @__PURE__ */ au(i, !1, !1) : null, _ = l & Ml ? Sn(s) : null;
  return {
    v: f,
    i: _,
    e: lt(() => (o(t, f ?? i, _ ?? s, a), () => {
      e.delete(r);
    }))
  };
}
function ci(e, t, i) {
  if (e.nodes)
    for (var r = e.nodes.start, s = e.nodes.end, o = t && !(t.f & Ct) ? (
      /** @type {EffectNodes} */
      t.nodes.start
    ) : i; r !== null; ) {
      var l = (
        /** @type {TemplateNode} */
        /* @__PURE__ */ ki(r)
      );
      if (o.before(r), r === s)
        return;
      r = l;
    }
}
function Dt(e, t, i) {
  t === null ? e.effect.first = i : t.next = i, i === null ? e.effect.last = t : i.prev = t;
}
function $u(e, t, i) {
  var r = e == null ? "" : "" + e;
  return r === "" ? null : r;
}
function ia(e, t = !1) {
  var i = t ? " !important;" : ";", r = "";
  for (var s of Object.keys(e)) {
    var o = e[s];
    o != null && o !== "" && (r += " " + s + ": " + o + i);
  }
  return r;
}
function gr(e) {
  return e[0] !== "-" || e[1] !== "-" ? e.toLowerCase() : e;
}
function Ru(e, t) {
  if (t) {
    var i = "", r, s;
    if (Array.isArray(t) ? (r = t[0], s = t[1]) : r = t, e) {
      e = String(e).replaceAll(/\s*\/\*.*?\*\/\s*/g, "").trim();
      var o = !1, l = 0, a = !1, f = [];
      r && f.push(...Object.keys(r).map(gr)), s && f.push(...Object.keys(s).map(gr));
      var _ = 0, h = -1;
      const p = e.length;
      for (var x = 0; x < p; x++) {
        var d = e[x];
        if (a ? d === "/" && e[x - 1] === "*" && (a = !1) : o ? o === d && (o = !1) : d === "/" && e[x + 1] === "*" ? a = !0 : d === '"' || d === "'" ? o = d : d === "(" ? l++ : d === ")" && l--, !a && o === !1 && l === 0) {
          if (d === ":" && h === -1)
            h = x;
          else if (d === ";" || x === p - 1) {
            if (h !== -1) {
              var b = gr(e.substring(_, h).trim());
              if (!f.includes(b)) {
                d !== ";" && x++;
                var C = e.substring(_, x).trim();
                i += " " + C + ";";
              }
            }
            _ = x + 1, h = -1;
          }
        }
      }
    }
    return r && (i += ia(r)), s && (i += ia(s, !0)), i = i.trim(), i === "" ? null : i;
  }
  return e == null ? null : String(e);
}
function Te(e, t, i, r, s, o) {
  var l = (
    /** @type {any} */
    e[xr]
  );
  if (l !== i || l === void 0) {
    var a = $u(i);
    a == null ? e.removeAttribute("class") : e.className = a, e[xr] = i;
  }
  return o;
}
function br(e, t = {}, i, r) {
  for (var s in i) {
    var o = i[s];
    t[s] !== o && (i[s] == null ? e.style.removeProperty(s) : e.style.setProperty(s, o, r));
  }
}
function pt(e, t, i, r) {
  var s = (
    /** @type {any} */
    e[Ir]
  );
  if (s !== t) {
    var o = Ru(t, r);
    o == null ? e.removeAttribute("style") : e.style.cssText = o, e[Ir] = t;
  } else r && (Array.isArray(r) ? (br(e, i == null ? void 0 : i[0], r[0]), br(e, i == null ? void 0 : i[1], r[1], "important")) : br(e, i, r));
  return r;
}
function lo(e, t, i = !1) {
  if (e.multiple) {
    if (t == null)
      return;
    if (!zr(t))
      return Ul();
    for (var r of e.options)
      r.selected = t.includes(hi(r));
    return;
  }
  for (r of e.options) {
    var s = hi(r);
    if (uu(s, t)) {
      r.selected = !0;
      return;
    }
  }
  (!i || t !== void 0) && (e.selectedIndex = -1);
}
function Uu(e) {
  var t = new MutationObserver(() => {
    lo(e, e.__value);
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
  }), Kr(() => {
    t.disconnect();
  });
}
function ju(e, t, i = t) {
  var r = /* @__PURE__ */ new WeakSet(), s = !0;
  Da(e, "change", (o) => {
    var l = o ? "[selected]" : ":checked", a;
    if (e.multiple)
      a = [].map.call(e.querySelectorAll(l), hi);
    else {
      var f = e.querySelector(l) ?? // will fall back to first non-disabled option if no option is selected
      e.querySelector("option:not([disabled])");
      a = f && hi(f);
    }
    i(a), e.__value = a, $ !== null && r.add($);
  }), Ya(() => {
    var o = t();
    if (e === document.activeElement) {
      var l = (
        /** @type {Batch} */
        $
      );
      if (r.has(l))
        return;
    }
    if (lo(e, o, s), s && o === void 0) {
      var a = e.querySelector(":checked");
      a !== null && (o = hi(a), i(o));
    }
    e.__value = o, s = !1;
  }), Uu(e);
}
function hi(e) {
  return "__value" in e ? e.__value : e.value;
}
const zu = Symbol("is custom element"), Hu = Symbol("is html");
function We(e, t, i, r) {
  var s = qu(e);
  s[t] !== (s[t] = i) && (t === "loading" && (e[bl] = i), i == null ? e.removeAttribute(t) : typeof i != "string" && Wu(e).includes(t) ? e[t] = i : e.setAttribute(t, i));
}
function qu(e) {
  return (
    /** @type {Record<string | symbol, unknown>} **/
    /** @type {any} */
    e[Pi] ?? (e[Pi] = {
      [zu]: e.nodeName.includes("-"),
      [Hu]: e.namespaceURI === $l
    })
  );
}
var ra = /* @__PURE__ */ new Map();
function Wu(e) {
  var t = e.getAttribute("is") || e.nodeName, i = ra.get(t);
  if (i) return i;
  ra.set(t, i = []);
  for (var r, s = e, o = Element.prototype; o !== s; ) {
    r = dl(s);
    for (var l in r)
      r[l].set && // better safe than sorry, we don't want spread attributes to mess with HTML content
      l !== "innerHTML" && l !== "textContent" && l !== "innerText" && i.push(l);
    s = wa(s);
  }
  return i;
}
function on(e, t, i = t) {
  var r = /* @__PURE__ */ new WeakSet();
  Da(e, "input", async (s) => {
    var o = s ? e.defaultValue : e.value;
    if (o = yr(e) ? wr(o) : o, i(o), $ !== null && r.add($), await Su(), o !== (o = t())) {
      var l = e.selectionStart, a = e.selectionEnd, f = e.value.length;
      if (e.value = o ?? "", a !== null) {
        var _ = e.value.length;
        l === a && a === f && _ > f ? (e.selectionStart = _, e.selectionEnd = _) : (e.selectionStart = l, e.selectionEnd = Math.min(a, _));
      }
    }
  }), // If we are hydrating and the value has since changed,
  // then use the updated value from the input instead.
  // If defaultValue is set, then value == defaultValue
  // TODO Svelte 6: remove input.value check and set to empty string?
  es(t) == null && e.value && (i(yr(e) ? wr(e.value) : e.value), $ !== null && r.add($)), Jr(() => {
    var s = t();
    if (e === document.activeElement) {
      var o = (
        /** @type {Batch} */
        $
      );
      if (r.has(o))
        return;
    }
    yr(e) && s === wr(e.value) || e.type === "date" && !s && !e.value || s !== e.value && (e.value = s ?? "");
  });
}
function yr(e) {
  var t = e.type;
  return t === "number" || t === "range";
}
function wr(e) {
  return e === "" ? null : +e;
}
function kr(e, t) {
  return e === t || (e == null ? void 0 : e[Fn]) === t;
}
function Vu(e = {}, t, i, r) {
  var s = (
    /** @type {ComponentContext} */
    De.r
  ), o = (
    /** @type {Effect} */
    X
  );
  return Ya(() => {
    var l, a;
    return Jr(() => {
      l = a, a = [], es(() => {
        kr(i(...a), e) || (t(e, ...a), l && kr(i(...l), e) && t(null, ...l));
      });
    }), () => {
      let f = o;
      for (; f !== s && f.parent !== null && f.parent.f & Er; )
        f = f.parent;
      const _ = () => {
        a && kr(i(...a), e) && t(null, ...a);
      }, h = f.teardown;
      f.teardown = () => {
        _(), h == null || h();
      };
    };
  }), e;
}
const Bu = "5";
var ya;
typeof window < "u" && ((ya = window.__svelte ?? (window.__svelte = {})).v ?? (ya.v = /* @__PURE__ */ new Set())).add(Bu);
const Ur = "not on list", sa = { "want to learn": 1, learning: 2, learned: 3 }, Du = (e, t) => Object.prototype.hasOwnProperty.call(e || {}, t);
function aa(e, t) {
  return Du(e.instrument_status, t.instrument) ? e.instrument_status[t.instrument] : t.is_auto ? e.learn_status : null;
}
const Gu = (e, t) => t !== "all" && e.length >= 2 && e.some((i) => i.instrument === t);
function uo(e, t, i = "all") {
  if (!e) return Ur;
  const r = t || [];
  if (Gu(r, i)) {
    const o = r.find((l) => l.instrument === i);
    return aa(e, o) || Ur;
  }
  if (r.length < 2) return e.learn_status;
  let s = null;
  for (const o of r) {
    const l = aa(e, o);
    l && (!s || sa[l] > sa[s]) && (s = l);
  }
  return s || e.learn_status;
}
const Yu = [
  "",
  "Amajor",
  "Aminor",
  "Adorian",
  "Amixolydian",
  "Bminor",
  "Cmajor",
  "Dmajor",
  "Dminor",
  "Eminor",
  "Fmajor",
  "Gmajor",
  "Dmixolydian",
  "Bmixolydian",
  "Edorian",
  "Gdorian",
  "Gminor",
  "Ddorian",
  "Cdorian",
  "Fdorian",
  "Gmixolydian",
  "Emajor",
  "Bdorian",
  "Emixolydian"
];
function Sr(e, t) {
  switch (t) {
    case "my_tunes":
      return e.person_tune || {};
    case "session":
    case "session_instance":
      return e.session_tune || {};
    case "admin":
      return e.tune || {};
    default:
      return {};
  }
}
function Ku(e, t) {
  switch (t) {
    case "my_tunes":
      return e.name_alias || e.tune_name || "Unknown";
    case "session":
    case "session_instance":
      return e.alias || e.tune_name || "Unknown";
    case "admin":
      return e.name || e.tune_name || "Unknown";
    default:
      return "Unknown";
  }
}
function Ju(e) {
  return {
    polka: "2/4",
    barndance: "4/4",
    hornpipe: "4/4",
    waltz: "3/4",
    reel: "4/4",
    "hop jig": "9/8",
    jig: "6/8",
    "set dance": "6/8",
    march: "4/4",
    mazurka: "3/4",
    slide: "12/8"
  }[(e || "").toLowerCase()] || "";
}
function Gt(e) {
  if (!e || e.trim() === "") return null;
  const t = e.trim();
  if (/^\d+$/.test(t)) return parseInt(t);
  const i = t.match(/[?&]setting=(\d+)/);
  if (i) return parseInt(i[1]);
  const r = t.match(/#setting(\d+)/);
  return r ? parseInt(r[1]) : null;
}
function oa(e, t) {
  if (!e) return { valid: !0, settingId: null };
  if (/^\d+$/.test(e)) return { valid: !0, settingId: parseInt(e) };
  if (e.includes("thesession.org")) {
    const i = Gt(e);
    if (i === null)
      return { valid: !1, error: "Could not extract setting ID from URL" };
    const r = e.match(/thesession\.org\/tunes\/(\d+)/);
    return r && parseInt(r[1]) !== t ? { valid: !0, settingId: null } : { valid: !0, settingId: i };
  }
  return { valid: !1, error: "Please enter a number or paste a valid TheSession.org URL" };
}
function la(e) {
  var t, i;
  return e.context === "admin" || (t = e.additionalData) != null && t.global ? [{ key: "all", label: "All sessions" }] : (e.context === "session" || e.context === "session_instance") && ((i = e.additionalData) != null && i.sessionPath) ? [
    { key: "session", label: "This session" },
    { key: "all", label: "All sessions" }
  ] : e.context === "my_tunes" ? [
    { key: "mine", label: "My sessions" },
    { key: "all", label: "All sessions" }
  ] : [{ key: "all", label: "All sessions" }];
}
function ua(e) {
  var t, i;
  return (e.context === "session" || e.context === "session_instance") && !((t = e.additionalData) != null && t.global) && ((i = e.additionalData) != null && i.sessionPath) ? [
    { key: "session", label: "At This Session" },
    { key: "all", label: "Globally" }
  ] : [{ key: "all", label: "Globally" }];
}
function ca(e, t) {
  const i = window.location.pathname;
  if (i.includes("/sessions/") && !i.includes("/my-tunes")) {
    let r = i.replace(/\/tunes\/\d+$/, "");
    r.endsWith("/tunes") || (r = r.replace(/\/(logs|people)$/, "") + "/tunes"), window.history.replaceState({}, "", `${r}/${e}`);
  } else if (i.match(/^\/admin\/tunes(\/\d+)?$/))
    window.history.replaceState({}, "", `/admin/tunes/${e}`);
  else {
    const r = new URL(window.location), s = t === "my_tunes" ? "ptid" : "tune";
    r.searchParams.set(s, e), window.history.replaceState({}, "", r);
  }
}
function An(e) {
  const t = window.location.pathname;
  if (t.includes("/sessions/") && !t.includes("/my-tunes"))
    window.history.replaceState({}, "", t.replace(/\/tunes\/\d+$/, "/tunes"));
  else if (t.match(/^\/admin\/tunes\/\d+$/))
    window.history.replaceState({}, "", "/admin/tunes");
  else {
    const i = new URL(window.location), r = e === "my_tunes" ? "ptid" : "tune";
    i.searchParams.delete(r), window.history.replaceState({}, "", i);
  }
}
function Zu() {
  const e = window.location.pathname;
  if (e.includes("/sessions/") && !e.includes("/my-tunes")) {
    const o = e.match(/\/tunes\/(\d+)$/);
    if (o) return parseInt(o[1], 10);
  }
  const t = e.match(/^\/admin\/tunes\/(\d+)$/);
  if (t) return parseInt(t[1], 10);
  const i = new URLSearchParams(window.location.search), r = e.includes("/my-tunes") ? "ptid" : "tune", s = i.get(r);
  return s ? parseInt(s, 10) : null;
}
function ln(e, t) {
  if (t === "my_tunes")
    return { instruments: e.instruments || [], overrides: e.instrument_status || {} };
  const i = e.person_tune_status || {};
  return { instruments: i.instruments || [], overrides: i.instrument_status || {} };
}
function Gi(e, t) {
  return t === "my_tunes" ? e.learn_status || "want to learn" : e.person_tune_status && e.person_tune_status.learn_status || "want to learn";
}
function si(e, t, i) {
  t === "my_tunes" ? e.instrument_status = i : e.person_tune_status && (e.person_tune_status.instrument_status = i);
}
function fa(e, t, i) {
  const { instruments: r, overrides: s } = ln(e, t), o = uo(
    { learn_status: Gi(e, t), instrument_status: s || {} },
    r,
    i.instrument
  );
  return o === Ur ? null : o;
}
function Xu(e, t) {
  const { instruments: i, overrides: r } = ln(e, t);
  return uo(
    { learn_status: Gi(e, t), instrument_status: r || {} },
    i,
    "all"
  );
}
function Qu(e, t, i) {
  const r = Object.assign({}, e);
  return !r.tune_name && r.name && (r.tune_name = r.name), (t || []).filter((s) => Number(s.tune_id) === Number(i)).sort((s, o) => s.ts - o.ts).forEach((s) => {
    s.type === "set_status" ? r.learn_status = s.learn_status : s.type === "set_heard" ? r.heard_count = s.heard_count : s.type === "set_notes" ? r.notes = s.notes : s.type === "add" && !r.learn_status && (r.learn_status = s.learn_status || "want to learn");
  }), r;
}
function ec(e) {
  if (!e.tune_id) return "";
  const t = `https://thesession.org/tunes/${e.tune_id}`, i = e.setting_id || e.setting_override;
  return i ? `${t}#setting${i}` : t;
}
function tc(e) {
  const t = e.abc || e.incipit_abc;
  if (!t) return "";
  const i = typeof window < "u" ? window.LZString : void 0;
  if (!i) return "";
  const r = t.replace(/!/g, `
`), s = e.tune_name || e.name || e.name_alias || e.alias || "Tune", o = e.tune_type || "", l = e.setting_key || e.key || e.key_override || "", a = Ju(o), f = `X: 1
T: ${s}
R: ${o}${a ? `
M: ${a}` : ""}
L: 1/8
K: ${l}
${r}`;
  return `https://michaeleskin.com/abctools/abctools.html?lzw=${i.compressToEncodedURIComponent(f)}&format=noten&ssp=45&name=${encodeURIComponent(s)}&play=1`;
}
function da(e) {
  const t = !!(e.incipit_image || e.image), i = !!(e.incipit_abc || e.abc);
  return {
    hasDots: t,
    hasAbc: i,
    hasAny: t || i,
    initialMode: t ? "dots" : "abc",
    canToggleSize: !!(e.incipit_image && e.image || e.incipit_abc && e.abc)
  };
}
function nc(e, t, i) {
  return t === "dots" ? i === "incipit" && e.incipit_image ? { kind: "img", size: "incipit", src: e.incipit_image } : i === "full" && e.image ? { kind: "img", size: "full", src: e.image } : e.incipit_image ? { kind: "img", size: "incipit", src: e.incipit_image } : e.image ? { kind: "img", size: "full", src: e.image } : null : i === "incipit" && e.incipit_abc ? { kind: "pre", size: "incipit", text: e.incipit_abc.replace(/!/g, `
`) } : i === "full" && e.abc ? { kind: "pre", size: "full", text: e.abc.replace(/!/g, `
`) } : e.incipit_abc ? { kind: "pre", size: "incipit", text: e.incipit_abc.replace(/!/g, `
`) } : e.abc ? { kind: "pre", size: "full", text: e.abc.replace(/!/g, `
`) } : null;
}
function On(e) {
  return window.MyTunesOffline ? window.MyTunesOffline.submit(e) : fetch("/api/my-tunes/ops", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(e)
  }).then((t) => t.json()).then((t) => {
    if (!t.success) throw new Error(t.error || "op failed");
    return { online: !0, data: t };
  });
}
var va = /* @__PURE__ */ M('<td class="modal-header-pill-cell"><span class="tune-type-pill"> </span></td>'), ic = /* @__PURE__ */ M('<table class="modal-header-section"><tbody><tr><!><td class="modal-header-title-cell"><h2 class="modal-tune-title"> </h2></td><td class="modal-header-spacer-cell"></td><td class="modal-header-close-cell"><button class="modal-close-btn" title="Close">&times;</button></td></tr></tbody></table> <div class="modal-loading"><div class="loading-spinner"></div> <p>Loading tune details...</p></div>', 1), rc = /* @__PURE__ */ M('<table class="modal-header-section"><tbody><tr><td class="modal-header-title-cell"><h2 class="modal-tune-title">Error</h2></td><td class="modal-header-spacer-cell"></td><td class="modal-header-close-cell"><button class="modal-close-btn" title="Close">&times;</button></td></tr></tbody></table> <div class="modal-error"><p> </p></div>', 1), sc = /* @__PURE__ */ M('<div class="tune-merged-notice" style="background: var(--input-bg, #f8f9fa); border: 1px solid var(--border-color, #dee2e6); border-radius: 6px; padding: 0.5rem 0.75rem; margin-bottom: 0.75rem; font-size: 0.85rem; color: var(--secondary-text, #6c757d);"> </div>'), ac = /* @__PURE__ */ M('<h2 class="modal-tune-title modal-tune-title-clickable" title="Click to configure"> </h2>'), oc = /* @__PURE__ */ M('<h2 class="modal-tune-title"> </h2>'), lc = /* @__PURE__ */ M('<div class="active-session-log-section"><button class="active-session-log-btn"><span class="active-session-log-dot"></span> </button></div>'), _a = /* @__PURE__ */ M('<span class="fetch-setting-spinner"></span>'), uc = /* @__PURE__ */ M('<div class="configure-field-group-inline"><label class="configure-label" for="name-alias-input">I call this:</label> <input type="text" id="name-alias-input" class="configure-input" autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false" placeholder="Enter your name for this tune"/></div> <div class="configure-field-group-inline"><label class="configure-label" for="setting-input">My setting:</label> <div class="input-with-button"><input type="text" id="setting-input" class="configure-input" autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false" placeholder="e.g., 123 or paste URL"/> <button type="button" title="Fetch setting from TheSession.org"><!></button></div></div> <div id="setting-error" class="field-error"> </div>', 1), cc = /* @__PURE__ */ M("<option> </option>"), fc = /* @__PURE__ */ M('<div class="configure-field-group-inline"><label class="configure-label" for="alias-input"> </label> <input type="text" id="alias-input" class="configure-input" autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false"/></div> <div class="configure-field-group-inline"><label class="configure-label" for="setting-input"> </label> <div class="input-with-button"><input type="text" id="setting-input" class="configure-input" autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false" placeholder="e.g., 123 or paste URL"/> <button type="button" title="Fetch setting from TheSession.org"><!></button></div></div> <div id="setting-error" class="field-error"> </div> <div class="configure-field-group-inline"><label class="configure-label" for="key-select"> </label> <select id="key-select" class="configure-select"></select></div>', 1), dc = /* @__PURE__ */ M('<div class="configure-field-group"><label class="configure-label" for="tune-name-input">Tune Name:</label> <input type="text" id="tune-name-input" class="configure-input" autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false" placeholder="Enter tune name"/></div>'), vc = /* @__PURE__ */ M('<div id="configure-section" class="configure-section"><div class="configure-field-group-inline"><div class="configure-label">Official Name:</div> <div class="configure-value"> </div></div> <div class="configure-field-group-inline"><div class="configure-label">Tune ID:</div> <div class="configure-value"> </div></div> <!></div>'), _c = /* @__PURE__ */ M('<div class="tunebook-status-section tunebook-status-not-on-list"><div class="tunebook-status-seg tsc-notlist-seg" role="group" aria-label="Status"><span class="tunebook-status-opt tsc-notlist-label">This tune is not on your list</span> <button type="button" class="tunebook-status-opt tsc-notlist-add">Add</button></div></div>'), ha = /* @__PURE__ */ M('<button type="button"> </button>'), hc = /* @__PURE__ */ M('<span class="tsc-manual">manual</span>'), pc = /* @__PURE__ */ M('<button type="button" class="tsc-remove">× remove</button>'), mc = /* @__PURE__ */ M('<div class="tunebook-status-seg tsc-notlist-seg" role="group" aria-label="Status"><span class="tunebook-status-opt tsc-notlist-label">This tune is not on your list</span> <button type="button" class="tunebook-status-opt tsc-notlist-add">Add</button></div>'), gc = /* @__PURE__ */ M('<div class="tunebook-status-seg" role="group" aria-label="Status"></div>'), bc = /* @__PURE__ */ M('<div class="tsc-block tsc-inst-block"><div class="tsc-label-line"><span class="tsc-name"> <!></span> <!></div> <!></div>'), yc = /* @__PURE__ */ M('<div class="tsc-instruments"></div>'), wc = /* @__PURE__ */ M('<!> <button type="button" class="tsc-expand-link"> </button>', 1), kc = /* @__PURE__ */ M('<div><div class="tsc-block tsc-main-block"><div class="tsc-label-line"><span class="tsc-name tunebook-status-label">This tune is on your list as</span></div> <div role="group" aria-label="Status"></div></div> <!></div>'), Sc = /* @__PURE__ */ M(`<div class="heard-count-section"><div class="heard-count-label">You've heard this <span id="heard-count-value"> </span> </div> <div class="heard-count-controls"><span class="heard-count-spinner"><svg class="spinner-icon" viewBox="0 0 50 50"><circle class="spinner-path" cx="25" cy="25" r="20" fill="none" stroke-width="5"></circle></svg></span> <button class="heard-count-btn heard-count-btn-minus">−</button> <button class="heard-count-btn heard-count-btn-plus">+</button></div></div>`), Tc = /* @__PURE__ */ M("<img/>"), Ec = /* @__PURE__ */ M("<pre> </pre>"), xc = /* @__PURE__ */ M('<button data-mode="dots">notes</button> <button data-mode="abc">abc</button>', 1), Ic = /* @__PURE__ */ M('<a target="_blank" class="notation-external-link" title="View on TheSession.org">thesession</a>'), Cc = /* @__PURE__ */ M('<a target="_blank" class="notation-external-link" title="View in ABC Tools">abc-tools</a>'), Ac = /* @__PURE__ */ M('<div class="abc-notation-section"><div><!></div> <div class="notation-controls-row"><div class="notation-mode-tabs"><!></div> <div class="notation-external-links"><!><!></div></div></div>'), Oc = /* @__PURE__ */ M('<div class="notes-section"><textarea id="notes-textarea" class="notes-textarea" placeholder="Add notes about this tune..."></textarea></div>'), Mc = /* @__PURE__ */ M('<div class="modal-action-buttons"><button id="cancel-btn" class="btn-secondary">Cancel</button> <button id="save-btn" class="btn-primary"> </button></div>'), Lc = /* @__PURE__ */ M('<a href="#" class="remove-link">Remove From My Tunes</a>'), Pc = /* @__PURE__ */ M('<a href="#">Configure This Tune</a>'), Fc = /* @__PURE__ */ M('<a href="#" class="remove-link">Remove From Session</a>'), Nc = /* @__PURE__ */ M('<div class="modal-additional-links"><!><!><!></div>'), $c = /* @__PURE__ */ M('<div class="stat-card"><div class="stat-line">Saved in <span class="stat-number"> </span> </div></div>'), Rc = /* @__PURE__ */ M('<span class="stat-note"> </span>'), Uc = /* @__PURE__ */ M('<div class="stat-card"><div class="stat-line">Logged <span class="stat-number"> </span> </div></div> <div class="stat-card"><div class="stat-line">Logged <span class="stat-number"> </span> </div></div>', 1), jc = /* @__PURE__ */ M('<div class="stat-card"><div class="stat-line">Logged <span class="stat-number"> </span> </div></div>'), zc = /* @__PURE__ */ M('<!> <div class="stat-card"><div class="stat-line">Logged <span class="stat-number"> </span> </div></div>', 1), Hc = /* @__PURE__ */ M('<div class="stat-card"><div class="stat-line">Logged <span class="stat-number"> </span> </div></div> <div class="stat-card"><div class="stat-line">In the repertoire of <span class="stat-number"> </span> sessions</div></div>', 1), pa = /* @__PURE__ */ M("<button> </button>"), ma = /* @__PURE__ */ M('<div class="history-scope-toggle"></div>'), ga = /* @__PURE__ */ M('<div class="no-history">No play history recorded yet.</div>'), qc = /* @__PURE__ */ M('<div class="history-position"> </div>'), Wc = /* @__PURE__ */ M('<div class="history-setting"> </div>'), Vc = /* @__PURE__ */ M('<div class="history-item"><div class="history-instance-name"><a> </a></div> <!> <!></div>'), Bc = /* @__PURE__ */ M('<div class="history-truncated">Showing the 100 most recent sessions.</div>'), Dc = /* @__PURE__ */ M('<div class="history-list"></div> <!>', 1), Gc = /* @__PURE__ */ M('<div class="no-history">Could not load play history.</div>'), Yc = /* @__PURE__ */ M('<div class="history-loading">Loading play history…</div>'), Kc = /* @__PURE__ */ M('<div class="no-history"> </div>'), Jc = /* @__PURE__ */ M('<div class="played-with-item"><span class="played-with-name"> </span> <span class="played-with-count"> </span></div>'), Zc = /* @__PURE__ */ M('<div class="played-with-list"></div>'), Xc = /* @__PURE__ */ M('<div class="no-history">Could not load played-with tunes.</div>'), Qc = /* @__PURE__ */ M('<div class="no-history">No set history recorded yet.</div>'), ef = /* @__PURE__ */ M('<div class="history-loading">Loading tunes…</div>'), tf = /* @__PURE__ */ M('<!> <table class="modal-header-section"><tbody><tr><!><td class="modal-header-title-cell"><!></td><td class="modal-header-spacer-cell"></td><td class="modal-header-close-cell"><button class="modal-close-btn" title="Close">&times;</button></td></tr></tbody></table> <!> <!> <!> <!> <!> <!> <!> <!> <div class="modal-tabs-section"><div class="modal-tabs-header"><button data-tab="stats">Stats</button> <button data-tab="history">History</button> <button data-tab="played-with">Played With</button></div> <div class="modal-tabs-content"><div id="stats-tab"><!> <div class="stat-card"><div class="stat-line">Saved in <span class="stat-number" id="tunebook-count"> </span> <button class="refresh-btn" title="Refresh"> </button> <!></div></div> <!></div> <div id="history-tab"><!> <div id="history-list-container"><!></div></div> <div id="played-with-tab"><!> <div id="played-with-container"><!></div></div></div></div>', 1), nf = /* @__PURE__ */ M('<div id="tune-detail-modal"><div class="modal-dialog"><div id="tune-detail-content"><!></div></div></div>');
function rf(e, t) {
  Hr(t, !0);
  let i = /* @__PURE__ */ G(!1), r = /* @__PURE__ */ G(!1), s = /* @__PURE__ */ G(
    "loading"
    // 'loading' | 'error' | 'ready'
  ), o = /* @__PURE__ */ G(""), l = /* @__PURE__ */ G(
    null
    // current show() config
  ), a = /* @__PURE__ */ G(
    null
    // currentTuneData
  ), f = /* @__PURE__ */ G(
    null
    // healed merged-tune permalink (spec 030)
  ), _ = 0, h = null, x = /* @__PURE__ */ G(!1), d = /* @__PURE__ */ G(!1), b = /* @__PURE__ */ G("stats"), C = /* @__PURE__ */ G(
    null
    // window.activeSession snapshot at render time
  ), p = /* @__PURE__ */ G(zt({})), m = /* @__PURE__ */ G(zt({})), A = /* @__PURE__ */ G(""), q = /* @__PURE__ */ G(
    "idle"
    // idle | saving | saved | error
  ), L = /* @__PURE__ */ G(
    "idle"
    // idle | loading | ok | warn | err
  ), Z = /* @__PURE__ */ G(
    "idle"
    // idle | loading | ok | err
  ), oe = /* @__PURE__ */ G(!1), Se = /* @__PURE__ */ G(0), le = /* @__PURE__ */ G(
    "dots"
    // 'dots' | 'abc'
  ), he = /* @__PURE__ */ G(
    "incipit"
    // 'incipit' | 'full'
  ), Pe = /* @__PURE__ */ G("all"), pe = /* @__PURE__ */ G(zt({})), ye = /* @__PURE__ */ G("all"), Ue = /* @__PURE__ */ G(zt({}));
  const O = /* @__PURE__ */ ne(() => {
    var u;
    return (u = n(l)) == null ? void 0 : u.context;
  }), Ge = /* @__PURE__ */ ne(() => {
    var u;
    return ((u = n(l)) == null ? void 0 : u.additionalData) || {};
  }), dt = /* @__PURE__ */ ne(() => !!n(Ge).global), vt = /* @__PURE__ */ ne(() => n(O) !== "admin" && !n(dt)), St = /* @__PURE__ */ ne(() => n(a) ? Ku(n(a), n(O)) : ""), tn = /* @__PURE__ */ ne(() => n(a) && n(a).tune_type || n(Ge).tuneType || ""), qe = /* @__PURE__ */ ne(() => {
    var u;
    return n(a) ? n(O) === "my_tunes" ? !0 : ((u = n(a).person_tune_status) == null ? void 0 : u.on_list) || !1 : !1;
  }), _t = /* @__PURE__ */ ne(() => n(a) ? Xu(n(a), n(O)) : "want to learn"), Lt = /* @__PURE__ */ ne(() => n(a) ? ln(n(a), n(O)).instruments : []), Ti = /* @__PURE__ */ ne(() => n(Lt) && n(Lt).length >= 2), tr = /* @__PURE__ */ ne(() => {
    var y, k;
    if (!n(a) || n(O) === "admin") return !1;
    const u = ((y = n(a).person_tune_status) == null ? void 0 : y.learn_status) || n(a).learn_status;
    return !u || u === "learned" ? !1 : n(O) === "my_tunes" ? !!(n(a).person_tune_id || n(Ge).personTuneId) : !!((k = n(a).person_tune_status) != null && k.person_tune_id);
  }), Tn = /* @__PURE__ */ ne(() => {
    var u;
    return n(a) ? n(O) === "my_tunes" ? n(a).heard_count || 0 : ((u = n(a).person_tune_status) == null ? void 0 : u.heard_count) || 0 : 0;
  }), Pt = /* @__PURE__ */ ne(() => n(a) ? da(n(a)) : null), nn = /* @__PURE__ */ ne(() => n(a) ? nc(n(a), n(le), n(he)) : null), ts = /* @__PURE__ */ ne(() => n(a) ? ec(n(a)) : ""), ns = /* @__PURE__ */ ne(() => n(a) ? tc(n(a)) : ""), co = /* @__PURE__ */ ne(() => !!(n(a) && (n(a).abc || n(a).incipit_abc || n(a).image || n(a).incipit_image))), is = /* @__PURE__ */ ne(() => {
    if (!n(a)) return "Fetch";
    const u = (n(p).setting || "").trim(), y = (n(O) === "session_instance" ? n(m).setting_override : n(m).setting_id) || null, k = !u && !y || Gt(u) === y;
    return n(co) && k ? "Refresh" : "Fetch";
  }), fo = /* @__PURE__ */ ne(() => {
    if (!n(a) || !n(l)) return !1;
    switch (n(O)) {
      case "my_tunes":
        return n(p).name_alias !== n(m).name_alias || Gt(n(p).setting) !== (n(m).setting_id || null) || n(p).notes !== n(m).notes;
      case "session":
        return n(p).alias !== n(m).alias || Gt(n(p).setting) !== (n(m).setting_id || null) || n(p).key !== n(m).key;
      case "session_instance":
        return n(p).alias !== n(m).name || Gt(n(p).setting) !== (n(m).setting_override || null) || n(p).key !== n(m).key_override;
      case "admin":
        return n(p).name !== n(m).name;
      default:
        return !1;
    }
  }), rs = /* @__PURE__ */ ne(() => !n(fo) || n(q) !== "idle" || !!n(A)), vo = /* @__PURE__ */ ne(() => n(q) === "saving" ? "Saving..." : n(q) === "saved" ? "Saved!" : n(q) === "error" ? "Error" : "Save"), _o = /* @__PURE__ */ ne(() => n(q) === "saved" ? "#28a745" : n(q) === "error" ? "#dc3545" : ""), ss = /* @__PURE__ */ ne(() => n(l) ? la(n(l)) : []), as = /* @__PURE__ */ ne(() => n(l) ? ua(n(l)) : []), Kn = /* @__PURE__ */ ne(() => n(pe)[n(Pe)] || { status: "loading" }), Ei = /* @__PURE__ */ ne(() => n(Ue)[n(ye)] || { status: "loading" }), ho = /* @__PURE__ */ ne(() => n(O) === "my_tunes" || n(O) !== "admin" && !n(dt) || n(O) === "session" && !!n(Ge).isSessionAdmin);
  function os(u, y) {
    var P, S;
    const k = { context: y.context };
    switch (y.context) {
      case "my_tunes":
        k.name_alias = u.name_alias || "", k.setting_id = u.setting_id || "", k.notes = u.notes || "", k.learn_status = u.learn_status || "want to learn";
        break;
      case "session":
        k.alias = u.alias || "", k.setting_id = u.setting_id || "", k.key = u.key || "", k.learn_status = ((P = u.person_tune_status) == null ? void 0 : P.learn_status) || "";
        break;
      case "session_instance":
        k.name = u.name || "", k.setting_override = u.setting_override || "", k.key_override = u.key_override || "", k.learn_status = ((S = u.person_tune_status) == null ? void 0 : S.learn_status) || "";
        break;
      case "admin":
        k.name = u.name || "";
        break;
    }
    return k;
  }
  function po(u, y) {
    switch (y.context) {
      case "my_tunes":
        return {
          name_alias: u.name_alias || "",
          setting: String(u.setting_id || ""),
          notes: u.notes || ""
        };
      case "session":
        return {
          alias: u.alias || "",
          setting: String(u.setting_id || ""),
          key: u.key || ""
        };
      case "session_instance":
        return {
          alias: u.name || "",
          setting: String(u.setting_override || ""),
          key: u.key_override || ""
        };
      case "admin":
        return { name: u.name || "" };
      default:
        return {};
    }
  }
  function Wt(u) {
    E(a, u, !0), E(f, null), E(m, os(u, n(l)), !0), E(p, po(u, n(l)), !0), E(A, ""), E(q, "idle"), E(L, "idle"), E(Z, "idle"), E(oe, !1), E(d, n(l).context === "admin"), E(b, "stats");
    const y = da(u);
    E(le, y.initialMode, !0), E(he, "incipit"), E(C, window.activeSession || null, !0), E(s, "ready");
  }
  function xi(u) {
    E(o, u, !0), E(s, "error");
  }
  function ls(u, y) {
    if (!window.CeolOffline || !u.tuneId) {
      xi(y || "Failed to load tune details");
      return;
    }
    const k = window.MyTunesOffline && window.MyTunesOffline.pending ? window.MyTunesOffline.pending() : Promise.resolve([]);
    Promise.all([window.CeolOffline.getTune(u.tuneId), k]).then(([P, S]) => {
      if (!P) {
        xi(y || "Failed to load tune details");
        return;
      }
      const ee = Qu(P, S, u.tuneId);
      Wt(Sr({ person_tune: ee, session_tune: ee, tune: ee }, u.context));
    }).catch(() => xi(y || "Failed to load tune details"));
  }
  function nr(u) {
    var k;
    E(l, u, !0), E(pe, {}, !0), E(Ue, {}, !0), E(Pe, la(u)[0].key, !0), E(ye, ua(u)[0].key, !0), u.expandInstrumentStatus !== void 0 && E(x, !!u.expandInstrumentStatus), E(Se, 0), E(f, null);
    const y = u.context === "my_tunes" && ((k = u.additionalData) != null && k.personTuneId) ? u.additionalData.personTuneId : u.tuneId;
    ca(y, u.context), E(s, "loading"), clearTimeout(h), E(i, !0), setTimeout(
      () => {
        E(r, !0);
      },
      10
    ), _ = Date.now(), fetch(u.apiEndpoint).then((P) => {
      if (!P.ok) {
        const S = new Error(`HTTP error! status: ${P.status}`);
        throw S.status = P.status, S;
      }
      return P.json();
    }).then((P) => {
      if (P.success) {
        const S = Sr(P, u.context);
        if (P.redirected_from && S.tune_id) {
          const ee = P.redirected_from, de = S.tune_id;
          n(l).tuneId = de, n(l).apiEndpoint = n(l).apiEndpoint.replace(`/tunes/${ee}`, `/tunes/${de}`), u.context !== "my_tunes" && ca(de, u.context), Wt(S), E(f, ee, !0);
        } else
          Wt(S);
      } else
        ls(u, P.error);
    }).catch((P) => {
      if (console.error("Error loading tune details:", P), P.status === 404 && u.context === "my_tunes") {
        An(u.context), xi("This tunebook entry no longer exists — it may have been merged into another tune. Check your tunebook list for the merged tune.");
        return;
      }
      ls(u, "Failed to load tune details");
    });
  }
  function Tt() {
    E(r, !1), E(Se, 0), An(n(O)), clearTimeout(h), h = setTimeout(
      () => {
        E(i, !1);
      },
      300
    );
  }
  function ir() {
    n(
      O
      // always visible on admin
    ) !== "admin" && E(d, !n(d));
  }
  function us() {
    const u = window.activeSession;
    if (!u || !u.session_instance_id) return;
    const y = n(l) && n(l).tuneId || n(a) && n(a).tune_id;
    y && (An(n(O)), window.location.href = `/live/instances/${u.session_instance_id}?tune=${y}`);
  }
  function mo(u) {
    Date.now() - _ < 500 || u.target === u.currentTarget && Tt();
  }
  function go(u) {
    u.key === "Escape" && n(i) && Tt();
  }
  function Jn() {
    if (!n(l) || typeof n(l).onStatusChange != "function" || !n(a)) return;
    const u = ln(n(a), n(O));
    n(l).onStatusChange({
      tune_id: n(a).tune_id,
      learn_status: Gi(n(a), n(O)),
      instrument_status: { ...u.overrides }
    });
  }
  function cs(u) {
    u && u.stopPropagation(), E(x, !n(x));
  }
  function fs(u) {
    const y = n(a) && n(a).tune_id;
    if (!y) return;
    const k = ln(n(a), n(O)), P = (k.instruments || []).filter((Ee) => Ee.is_auto && Object.prototype.hasOwnProperty.call(k.overrides, Ee.instrument));
    if (u === n(
      m
      // nothing to do
    ).learn_status && P.length === 0) return;
    const S = n(m).learn_status, ee = { ...k.overrides }, de = { ...k.overrides };
    P.forEach((Ee) => delete de[Ee.instrument]);
    const we = (Ee, Ft) => {
      n(m).learn_status = Ee, n(a).learn_status = Ee, n(a).person_tune_status && (n(a).person_tune_status.learn_status = Ee), si(n(a), n(O), Ft), Jn();
    };
    we(u, de), E(oe, !0);
    const Fe = [
      On({ type: "set_status", tune_id: y, learn_status: u })
    ];
    P.forEach((Ee) => {
      Fe.push(On({
        type: "set_instrument_status",
        tune_id: y,
        instrument: Ee.instrument,
        status: null
      }));
    }), Promise.all(Fe).then(() => {
      E(
        oe,
        !1
        // success OR queued offline
      );
    }).catch(() => {
      E(oe, !1), we(S, ee);
    });
  }
  function rr(u, y) {
    const k = n(a) && n(a).tune_id;
    if (!k) return;
    const P = ln(n(a), n(O)), S = P.instruments[u];
    if (!S) return;
    const ee = Gi(n(a), n(O)), de = fa(n(a), n(O), S);
    let we = y;
    if (y === de) {
      if (S.is_auto) return;
      we = null;
    }
    const Fe = we !== null && !(S.is_auto && we === ee), Ee = { ...P.overrides }, Ft = { ...P.overrides };
    Fe ? Ft[S.instrument] = we : delete Ft[S.instrument], si(n(a), n(O), Ft), Jn(), On({
      type: "set_instrument_status",
      tune_id: k,
      instrument: S.instrument,
      status: we
    }).catch(() => {
      si(n(a), n(O), Ee), Jn();
    });
  }
  function ds(u) {
    const y = n(a) && n(a).tune_id;
    if (!y) return;
    const k = ln(n(a), n(O)), P = k.instruments[u];
    if (!P || P.is_auto) return;
    const S = { ...k.overrides }, ee = { ...k.overrides };
    delete ee[P.instrument], si(n(a), n(O), ee), Jn(), On({
      type: "set_instrument_status",
      tune_id: y,
      instrument: P.instrument,
      status: null
    }).catch(() => {
      si(n(a), n(O), S), Jn();
    });
  }
  function vs() {
    const u = n(a).tune_id;
    On({
      type: "add",
      tune_id: u,
      learn_status: "want to learn",
      name: n(a).name || n(a).tune_name,
      tune_type: n(a).tune_type
    }).then((y) => {
      if (y && y.queued) {
        try {
          sessionStorage.setItem("myTunesToast", "Added to your tunes. It will sync when you are back online.");
        } catch {
        }
        window.location.href = "/my-tunes";
        return;
      }
      n(l) && n(l).apiEndpoint && fetch(n(l).apiEndpoint).then((k) => k.json()).then((k) => {
        k.success && Wt(Sr(k, n(O)));
      });
    }).catch((y) => {
      console.error("Error adding to tunebook:", y), alert("Failed to add tune to your list");
    });
  }
  function _s(u) {
    if (n(O) === "admin") return;
    const y = n(Tn);
    if (u < 0 && y === 0) return;
    const k = Math.max(0, y + u), P = (de) => {
      n(O) === "my_tunes" ? n(a).heard_count = de : n(a).person_tune_status && (n(a).person_tune_status.heard_count = de);
    };
    P(k);
    const S = n(a).tune_id, ee = n(O) === "my_tunes" || !!n(a).person_tune_status;
    if (!S || !ee) {
      console.error("Cannot set heard count: tune is not in your collection"), P(y);
      return;
    }
    lu(Se), On({ type: "set_heard", tune_id: S, heard_count: k }).then(() => {
      E(Se, Math.max(0, n(
        Se
        // success OR queued offline: keep optimistic UI
      ) - 1), !0);
    }).catch((de) => {
      console.error("Error setting heard count:", de), P(y), E(Se, Math.max(0, n(Se) - 1), !0);
    });
  }
  function hs() {
    _s(1);
  }
  function ps() {
    _s(-1);
  }
  function ms() {
    const u = (n(p).setting || "").trim();
    if (!u) {
      E(A, "");
      return;
    }
    const y = oa(u, n(a).tune_id);
    y.valid ? (E(A, ""), y.settingId !== null && u !== y.settingId.toString() && (n(p).setting = y.settingId.toString())) : E(A, y.error, !0);
  }
  function gs() {
    if (!n(a) || !n(l) || n(rs)) return;
    const u = {};
    let y = "";
    switch (n(O)) {
      case "my_tunes": {
        n(p).name_alias !== n(m).name_alias && (u.name_alias = n(p).name_alias.trim() || null);
        const S = Gt(n(p).setting);
        S !== (n(m).setting_id || null) && (u.setting_id = S), n(p).notes !== n(m).notes && (u.notes = n(p).notes.trim() || null), y = `/api/my-tunes/${n(l).additionalData.personTuneId}`;
        break;
      }
      case "session": {
        n(p).alias !== n(m).alias && (u.alias = n(p).alias.trim() || null);
        const S = Gt(n(p).setting);
        S !== (n(m).setting_id || null) && (u.setting_id = S), n(p).key !== n(m).key && (u.key = n(p).key || null), y = `/api/sessions/${n(l).additionalData.sessionPath}/tunes/${n(a).tune_id}`;
        break;
      }
      case "session_instance": {
        n(p).alias !== n(m).name && (u.name = n(p).alias.trim() || null);
        const S = Gt(n(p).setting);
        S !== (n(m).setting_override || null) && (u.setting_override = S), n(p).key !== n(m).key_override && (u.key_override = n(p).key || null), y = `/api/sessions/${n(l).additionalData.sessionPath}/${n(l).additionalData.dateOrId}/tunes/${n(a).tune_id}`;
        break;
      }
      case "admin": {
        if (u.name = n(p).name.trim(), !u.name) {
          alert("Tune name cannot be empty");
          return;
        }
        y = `/api/admin/tunes/${n(a).tune_id}`;
        break;
      }
    }
    E(q, "saving"), (Object.keys(u).length > 0 ? fetch(y, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(u)
    }).then((S) => S.json()) : Promise.resolve({ success: !0, message: "No changes to save" })).then((S) => {
      S.success ? (E(q, "saved"), E(m, os({ ...n(a), ...u }, n(l)), !0), An(n(O)), n(l).onSave && typeof n(l).onSave == "function" && n(l).onSave(), setTimeout(() => Tt(), 1e3)) : (E(q, "error"), console.error("Error saving:", S.error || S.message), setTimeout(
        () => {
          n(q) === "error" && E(q, "idle");
        },
        2e3
      ));
    }).catch((S) => {
      console.error("Error:", S), E(q, "error"), setTimeout(
        () => {
          n(q) === "error" && E(q, "idle");
        },
        2e3
      );
    });
  }
  function sr() {
    if (!n(a) || n(L) === "loading") return;
    const u = n(a).tune_id, y = (n(p).setting || "").trim();
    E(L, "loading");
    const k = (S) => {
      E(L, S, !0), setTimeout(
        () => {
          n(L) === S && E(L, "idle");
        },
        2e3
      );
    };
    let P = `/api/tunes/${u}/settings/cache`;
    if (y) {
      const ee = oa(y, u).settingId || y;
      P += `?setting_id=${ee}`;
    }
    fetch(P, {
      method: "POST",
      headers: { "Content-Type": "application/json" }
    }).then((S) => S.json()).then((S) => {
      if (!S.success) {
        console.error("Error fetching setting:", S.message), k("err");
        return;
      }
      const ee = S.setting.setting_id;
      n(a).abc = S.setting.abc, n(a).incipit_abc = S.setting.incipit_abc, n(a).image = S.setting.image, n(a).incipit_image = S.setting.incipit_image;
      let de = "", we = {};
      n(O) === "my_tunes" ? (de = `/api/my-tunes/${n(l).additionalData.personTuneId}`, we = { setting_id: ee }) : n(O) === "session" ? (de = `/api/sessions/${n(l).additionalData.sessionPath}/tunes/${n(a).tune_id}`, we = { setting_id: ee }) : n(O) === "session_instance" && (de = `/api/sessions/${n(l).additionalData.sessionPath}/${n(l).additionalData.dateOrId}/tunes/${n(a).tune_id}`, we = { setting_override: ee }), de ? fetch(de, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(we)
      }).then((Fe) => Fe.json()).then((Fe) => {
        Fe.success ? (n(O) === "session_instance" ? n(a).setting_override = ee : n(a).setting_id = ee, Wt(n(
          a
          // legacy re-renders the modal here
        )), k("ok")) : (console.error("Error saving setting_id:", Fe.error), Wt(n(
          a
          // still re-render with the fetched data
        )), k("warn"));
      }).catch((Fe) => {
        console.error("Error saving setting_id:", Fe), Wt(n(
          a
          // still re-render with the fetched data
        ));
      }) : (Wt(n(a)), k("ok"));
    }).catch((S) => {
      console.error("Error:", S), k("err");
    });
  }
  function bs() {
    var y;
    if (!confirm("Are you sure you want to remove this tune from your list?")) return;
    const u = (y = n(l).additionalData) == null ? void 0 : y.personTuneId;
    if (!u) {
      alert("Unable to remove tune");
      return;
    }
    fetch(`/api/my-tunes/${u}`, { method: "DELETE" }).then((k) => k.json()).then((k) => {
      k.success ? (An(n(O)), n(l).onSave && typeof n(l).onSave == "function" && n(l).onSave(), Tt()) : (console.error("Error removing tune:", k.error), alert("Failed to remove tune from your list"));
    }).catch((k) => {
      console.error("Error:", k), alert("Failed to remove tune from your list");
    });
  }
  function ys() {
    var k, P;
    if (!confirm("Are you sure you want to remove this tune from the session tune list?")) return;
    const u = (k = n(l).additionalData) == null ? void 0 : k.sessionPath, y = (P = n(a)) == null ? void 0 : P.tune_id;
    if (!u || !y) {
      alert("Unable to remove tune from session");
      return;
    }
    fetch(`/api/sessions/${u}/tunes/${y}`, { method: "DELETE" }).then((S) => S.json()).then((S) => {
      S.success ? (An(n(O)), n(l).onSave && typeof n(l).onSave == "function" && n(l).onSave(), Tt()) : (console.error("Error removing tune from session:", S.message), alert(S.message || "Failed to remove tune from session"));
    }).catch((S) => {
      console.error("Error:", S), alert("Failed to remove tune from session");
    });
  }
  function ws() {
    if (!n(a) || n(Z) !== "idle") return;
    const u = n(a).tune_id;
    E(Z, "loading");
    let y;
    n(O) === "admin" ? y = `/api/admin/tunes/${u}/refresh_tunebook_count` : n(O) === "session" || n(O) === "session_instance" ? y = `/api/sessions/${n(l).additionalData.sessionPath}/tunes/${u}/refresh_tunebook_count` : y = `/api/admin/tunes/${u}/refresh_tunebook_count`, fetch(y, {
      method: "POST",
      headers: { "Content-Type": "application/json" }
    }).then((k) => k.json()).then((k) => {
      if (k.success) {
        const P = k.new_count || k.tunebook_count;
        n(a).tunebook_count = P, n(a).tunebook_count_cached = P, E(Z, "ok");
      } else
        E(Z, "err"), console.error("Error refreshing tunebook count:", k.error);
    }).catch((k) => {
      console.error("Error:", k), E(Z, "err");
    }).finally(() => {
      setTimeout(
        () => {
          E(Z, "idle");
        },
        2e3
      );
    });
  }
  function Ii(u) {
    E(b, u, !0), u === "history" && Ts(), u === "played-with" && Es();
  }
  function ks(u) {
    E(Pe, u, !0), Ts();
  }
  function Ss(u) {
    E(ye, u, !0), Es();
  }
  function Ts() {
    var P;
    if (!n(l)) return;
    const u = n(Pe), y = n(l).tuneId || n(a) && n(a).tune_id;
    if (!y) {
      n(pe)[u] = { status: "none" };
      return;
    }
    if (((P = n(pe)[u]) == null ? void 0 : P.status) === "ready") return;
    n(pe)[u] = { status: "loading" };
    let k = `/api/tunes/${y}/history`;
    u === "session" ? k += `?session_path=${encodeURIComponent(n(l).additionalData.sessionPath)}` : u === "mine" && (k += "?person=me"), fetch(k).then((S) => S.json()).then((S) => {
      if (u === n(
        Pe
        // user toggled scope while loading
      )) {
        if (!S.success) {
          n(pe)[u] = { status: "error" };
          return;
        }
        n(pe)[u] = { status: "ready", data: S };
      }
    }).catch(() => {
      u === n(Pe) && (n(pe)[u] = { status: "error" });
    });
  }
  function Es() {
    var P;
    if (!n(l)) return;
    const u = n(ye), y = n(l).tuneId || n(a) && n(a).tune_id;
    if (!y) {
      n(Ue)[u] = { status: "none" };
      return;
    }
    if (((P = n(Ue)[u]) == null ? void 0 : P.status) === "ready") return;
    n(Ue)[u] = { status: "loading" };
    let k = `/api/tunes/${y}/played-with`;
    u === "session" && (k += `?session_path=${encodeURIComponent(n(l).additionalData.sessionPath)}`), fetch(k).then((S) => S.json()).then((S) => {
      if (u === n(ye)) {
        if (!S.success) {
          n(Ue)[u] = { status: "error" };
          return;
        }
        n(Ue)[u] = { status: "ready", data: S };
      }
    }).catch(() => {
      u === n(ye) && (n(Ue)[u] = { status: "error" });
    });
  }
  function bo(u) {
    var S, ee;
    if (!u) return;
    const y = ((S = n(l)) == null ? void 0 : S.additionalData) || {}, k = y.isUserLoggedIn ?? (n(O) === "my_tunes" || !!((ee = n(a)) != null && ee.person_tune_status)), P = !y.global && (n(O) === "session" || n(O) === "session_instance") ? y.sessionPath : null;
    nr(P ? {
      context: "session",
      tuneId: u,
      apiEndpoint: `/api/sessions/${P}/tunes/${u}`,
      onSave: n(l).onSave,
      additionalData: {
        sessionPath: P,
        isUserLoggedIn: k,
        isSessionAdmin: !!y.isSessionAdmin
      }
    } : {
      context: "session_instance",
      tuneId: u,
      apiEndpoint: `/api/tunes/${u}/detail`,
      additionalData: { isUserLoggedIn: k, global: !0 }
    });
  }
  function ar(u) {
    !n(a) || n(le) === u || (u === "dots" ? n(he) === "incipit" && n(a).incipit_image || n(he) === "full" && n(a).image || (n(a).incipit_image ? E(he, "incipit") : n(a).image && E(he, "full")) : n(he) === "incipit" && n(a).incipit_abc || n(he) === "full" && n(a).abc || (n(a).incipit_abc ? E(he, "incipit") : n(a).abc && E(he, "full")), E(le, u, !0));
  }
  function xs() {
    if (!n(a)) return;
    const u = n(he) === "incipit" ? "full" : "incipit";
    if (n(le) === "dots") {
      if (!(u === "incipit" ? n(a).incipit_image : n(a).image)) return;
    } else if (!(u === "incipit" ? n(a).incipit_abc : n(a).abc)) return;
    E(he, u, !0);
  }
  function yo() {
    var u;
    (u = n(Pt)) != null && u.canToggleSize && xs();
  }
  const rn = (u, y) => u === 1 ? y : y + "s", Is = /* @__PURE__ */ ne(() => n(a) && (n(a).tunebook_count || n(a).tunebook_count_cached) || 0);
  var wo = {
    show: nr,
    close: Tt,
    toggleConfigSection: ir,
    logToActiveSession: us,
    toggleStatusExpand: cs,
    setTunebookStatus: fs,
    setInstrumentStatus: rr,
    removeInstrumentTune: ds,
    addToTunebook: vs,
    incrementHeardCount: hs,
    decrementHeardCount: ps,
    save: gs,
    fetchSetting: sr,
    removeFromMyTunes: bs,
    removeFromSession: ys,
    refreshTunebookCount: ws,
    switchTab: Ii,
    setHistoryScope: ks,
    setPlayedWithScope: Ss,
    switchNotationMode: ar,
    toggleNotationSize: xs
  }, Zn = nf();
  Iu("keydown", Fr, go);
  var ko = v(Zn), So = v(ko), To = v(So);
  {
    var Eo = (u) => {
      var y = ic(), k = Le(y), P = v(k), S = v(P), ee = v(S);
      {
        var de = (Xn) => {
          var Ci = va(), lr = v(Ci), Ai = v(lr);
          z(() => N(Ai, n(Ge).tuneType)), T(Xn, Ci);
        };
        R(ee, (Xn) => {
          n(Ge).tuneType && Xn(de);
        });
      }
      var we = w(ee), Fe = v(we), Ee = v(Fe), Ft = w(we, 2), or = v(Ft);
      z(() => N(Ee, n(Ge).tuneName || "Loading...")), W("click", or, Tt), T(u, y);
    }, xo = (u) => {
      var y = rc(), k = Le(y), P = v(k), S = v(P), ee = w(v(S), 2), de = v(ee), we = w(k, 2), Fe = v(we), Ee = v(Fe);
      z(() => N(Ee, n(o))), W("click", de, Tt), T(u, y);
    }, Io = (u) => {
      var y = tf(), k = Le(y);
      {
        var P = (g) => {
          var I = sc(), F = v(I);
          z(() => N(F, `Tune #${n(f) ?? ""} was merged into "${(n(a).tune_name || n(a).name || `#${n(a).tune_id}`) ?? ""}" (#${n(a).tune_id ?? ""})
            — you're viewing the merged tune.`)), T(g, I);
        };
        R(k, (g) => {
          n(f) != null && g(P);
        });
      }
      var S = w(k, 2), ee = v(S), de = v(ee), we = v(de);
      {
        var Fe = (g) => {
          var I = va(), F = v(I), U = v(F);
          z(() => N(U, n(tn))), T(g, I);
        };
        R(we, (g) => {
          n(tn) && g(Fe);
        });
      }
      var Ee = w(we), Ft = v(Ee);
      {
        var or = (g) => {
          var I = ac(), F = v(I);
          z(() => N(F, n(St))), W("click", I, ir), T(g, I);
        }, Xn = (g) => {
          var I = oc(), F = v(I);
          z(() => N(F, n(St))), T(g, I);
        };
        R(Ft, (g) => {
          n(vt) ? g(or) : g(Xn, -1);
        });
      }
      var Ci = w(Ee, 2), lr = v(Ci), Ai = w(S, 2);
      {
        var Co = (g) => {
          var I = lc(), F = v(I), U = w(v(F));
          z(() => N(U, ` Log to ${(n(C).session_name || "the current session") ?? ""}`)), W("click", F, us), T(g, I);
        };
        R(Ai, (g) => {
          n(C) && n(C).session_instance_id && (n(l).tuneId || n(a).tune_id) && g(Co);
        });
      }
      var Cs = w(Ai, 2);
      {
        var Ao = (g) => {
          var I = vc(), F = v(I), U = w(v(F), 2), V = v(U), te = w(F, 2), B = w(v(te), 2), re = v(B), D = w(te, 2);
          {
            var Q = (K) => {
              var ve = uc(), J = Le(ve), se = w(v(J), 2), _e = w(J, 2), Ce = w(v(_e), 2), Ae = v(Ce);
              let je;
              var me = w(Ae, 2);
              let Oe;
              var ze = v(me);
              {
                var ht = (ge) => {
                  var Ye = _a();
                  T(ge, Ye);
                }, Et = (ge) => {
                  var Ye = Vt("✓");
                  T(ge, Ye);
                }, sn = (ge) => {
                  var Ye = Vt("⚠");
                  T(ge, Ye);
                }, En = (ge) => {
                  var Ye = Vt("✗");
                  T(ge, Ye);
                }, ei = (ge) => {
                  var Ye = Vt();
                  z(() => N(Ye, n(is))), T(ge, Ye);
                };
                R(ze, (ge) => {
                  n(L) === "loading" ? ge(ht) : n(L) === "ok" ? ge(Et, 1) : n(L) === "warn" ? ge(sn, 2) : n(L) === "err" ? ge(En, 3) : ge(ei, -1);
                });
              }
              var xn = w(_e, 2), ti = v(xn);
              z(() => {
                je = pt(Ae, "", je, { "border-color": n(A) ? "#dc3545" : "" }), Te(me, 1, `fetch-setting-btn${n(L) === "loading" ? " fetch-setting-btn-loading" : ""}`), me.disabled = n(L) !== "idle", Oe = pt(me, "", Oe, {
                  "background-color": n(L) === "ok" ? "#28a745" : n(L) === "warn" ? "#f0ad4e" : n(L) === "err" ? "#dc3545" : "",
                  color: n(L) === "ok" || n(L) === "warn" || n(L) === "err" ? "white" : ""
                }), pt(xn, `display: ${n(A) ? "block" : "none"};`), N(ti, n(A));
              }), on(se, () => n(p).name_alias, (ge) => n(p).name_alias = ge), W("input", Ae, ms), on(Ae, () => n(p).setting, (ge) => n(p).setting = ge), W("click", me, sr), T(K, ve);
            }, ue = (K) => {
              var ve = fc(), J = Le(ve), se = v(J), _e = v(se), Ce = w(se, 2), Ae = w(J, 2), je = v(Ae), me = v(je), Oe = w(je, 2), ze = v(Oe);
              let ht;
              var Et = w(ze, 2);
              let sn;
              var En = v(Et);
              {
                var ei = (fe) => {
                  var Me = _a();
                  T(fe, Me);
                }, xn = (fe) => {
                  var Me = Vt("✓");
                  T(fe, Me);
                }, ti = (fe) => {
                  var Me = Vt("⚠");
                  T(fe, Me);
                }, ge = (fe) => {
                  var Me = Vt("✗");
                  T(fe, Me);
                }, Ye = (fe) => {
                  var Me = Vt();
                  z(() => N(Me, n(is))), T(fe, Me);
                };
                R(En, (fe) => {
                  n(L) === "loading" ? fe(ei) : n(L) === "ok" ? fe(xn, 1) : n(L) === "warn" ? fe(ti, 2) : n(L) === "err" ? fe(ge, 3) : fe(Ye, -1);
                });
              }
              var ni = w(Ae, 2), vr = v(ni), He = w(ni, 2), Qe = v(He), ii = v(Qe), Oi = w(Qe, 2);
              Nt(Oi, 21, () => Yu, Bt, (fe, Me) => {
                var In = cc(), an = v(In), Mi = {};
                z(() => {
                  N(an, n(Me) || "(not specified)"), Mi !== (Mi = n(Me)) && (In.value = (In.__value = n(Me)) ?? "");
                }), T(fe, In);
              }), z(() => {
                N(_e, n(O) === "session" ? "We call this:" : "In this case, we called it:"), We(Ce, "placeholder", n(O) === "session" ? "Enter session name for this tune" : "Enter name for this instance"), N(me, n(O) === "session" ? "Our setting:" : "This time, we played setting:"), ht = pt(ze, "", ht, { "border-color": n(A) ? "#dc3545" : "" }), Te(Et, 1, `fetch-setting-btn${n(L) === "loading" ? " fetch-setting-btn-loading" : ""}`), Et.disabled = n(L) !== "idle", sn = pt(Et, "", sn, {
                  "background-color": n(L) === "ok" ? "#28a745" : n(L) === "warn" ? "#f0ad4e" : n(L) === "err" ? "#dc3545" : "",
                  color: n(L) === "ok" || n(L) === "warn" || n(L) === "err" ? "white" : ""
                }), pt(ni, `display: ${n(A) ? "block" : "none"};`), N(vr, n(A)), N(ii, n(O) === "session" ? "We play this in:" : "This time, we played in:");
              }), on(Ce, () => n(p).alias, (fe) => n(p).alias = fe), W("input", ze, ms), on(ze, () => n(p).setting, (fe) => n(p).setting = fe), W("click", Et, sr), ju(Oi, () => n(p).key, (fe) => n(p).key = fe), T(K, ve);
            }, ce = (K) => {
              var ve = dc(), J = w(v(ve), 2);
              on(J, () => n(p).name, (se) => n(p).name = se), T(K, ve);
            };
            R(D, (K) => {
              n(O) === "my_tunes" ? K(Q) : n(O) === "session" || n(O) === "session_instance" ? K(ue, 1) : n(O) === "admin" && K(ce, 2);
            });
          }
          z(() => {
            pt(I, `display: ${n(d) ? "block" : "none"};`), N(V, n(a).tune_name || n(a).name || "Unknown"), N(re, n(a).tune_id || "Unknown");
          }), T(g, I);
        };
        R(Cs, (g) => {
          n(dt) || g(Ao);
        });
      }
      var As = w(Cs, 2);
      {
        var Oo = (g) => {
          var I = dn(), F = Le(I);
          {
            var U = (te) => {
              var B = _c(), re = v(B), D = w(v(re), 2);
              W("click", D, vs), T(te, B);
            }, V = (te) => {
              var B = kc(), re = v(B), D = w(v(re), 2);
              Nt(
                D,
                20,
                () => [
                  ["want to learn", "Want To Learn"],
                  ["learning", "Learning"],
                  ["learned", "Learned"]
                ],
                Bt,
                (ce, K) => {
                  var ve = /* @__PURE__ */ ne(() => Gs(K, 2));
                  let J = () => n(ve)[0], se = () => n(ve)[1];
                  var _e = ha(), Ce = v(_e);
                  z(() => {
                    Te(_e, 1, `tunebook-status-opt${n(_t) === J() ? " active" : ""}`), We(_e, "data-status", J()), N(Ce, se());
                  }), W("click", _e, () => fs(J())), T(ce, _e);
                }
              );
              var Q = w(re, 2);
              {
                var ue = (ce) => {
                  var K = wc(), ve = Le(K);
                  {
                    var J = (Ce) => {
                      var Ae = yc();
                      Nt(Ae, 21, () => n(Lt), Bt, (je, me, Oe) => {
                        const ze = /* @__PURE__ */ ne(() => fa(n(a), n(O), n(me)));
                        var ht = bc(), Et = v(ht), sn = v(Et), En = v(sn), ei = w(En);
                        {
                          var xn = (He) => {
                            var Qe = hc();
                            T(He, Qe);
                          };
                          R(ei, (He) => {
                            n(me).is_auto || He(xn);
                          });
                        }
                        var ti = w(sn, 2);
                        {
                          var ge = (He) => {
                            var Qe = pc();
                            W("click", Qe, () => ds(Oe)), T(He, Qe);
                          };
                          R(ti, (He) => {
                            !n(me).is_auto && n(ze) !== null && He(ge);
                          });
                        }
                        var Ye = w(Et, 2);
                        {
                          var ni = (He) => {
                            var Qe = mc(), ii = w(v(Qe), 2);
                            W("click", ii, () => rr(Oe, "want to learn")), T(He, Qe);
                          }, vr = (He) => {
                            var Qe = gc();
                            Nt(
                              Qe,
                              20,
                              () => [
                                ["want to learn", "Want To Learn"],
                                ["learning", "Learning"],
                                ["learned", "Learned"]
                              ],
                              Bt,
                              (ii, Oi) => {
                                var fe = /* @__PURE__ */ ne(() => Gs(Oi, 2));
                                let Me = () => n(fe)[0], In = () => n(fe)[1];
                                var an = ha(), Mi = v(an);
                                z(() => {
                                  Te(an, 1, `tunebook-status-opt${n(ze) === Me() ? " active" : ""}`), We(an, "data-status", Me()), N(Mi, In());
                                }), W("click", an, () => rr(Oe, Me())), T(ii, an);
                              }
                            ), T(He, Qe);
                          };
                          R(Ye, (He) => {
                            n(ze) === null ? He(ni) : He(vr, -1);
                          });
                        }
                        z(() => N(En, n(me).instrument)), T(je, ht);
                      }), T(Ce, Ae);
                    };
                    R(ve, (Ce) => {
                      n(x) && Ce(J);
                    });
                  }
                  var se = w(ve, 2), _e = v(se);
                  z(() => N(_e, n(x) ? "Hide Instruments" : "View By Instrument")), W("click", se, cs), T(ce, K);
                };
                R(Q, (ce) => {
                  n(Ti) && ce(ue);
                });
              }
              z(
                (ce) => {
                  Te(B, 1, `tunebook-status-section tunebook-status-${ce ?? ""}`), Te(D, 1, `tunebook-status-seg${n(oe) ? " saving" : ""}`);
                },
                [() => n(_t).replace(/ /g, "-")]
              ), T(te, B);
            };
            R(F, (te) => {
              n(qe) ? te(V, -1) : te(U);
            });
          }
          T(g, I);
        };
        R(As, (g) => {
          n(O) !== "admin" && n(Ge).isUserLoggedIn && g(Oo);
        });
      }
      var Os = w(As, 2);
      {
        var Mo = (g) => {
          var I = Sc(), F = v(I), U = w(v(F)), V = v(U), te = w(U), B = w(F, 2), re = v(B), D = w(re, 2), Q = w(D, 2);
          z(() => {
            N(V, n(Tn)), N(te, ` time${n(Tn) !== 1 ? "s" : ""}`), pt(re, `display: ${n(Se) > 0 ? "inline-block" : "none"};`), D.disabled = n(Tn) === 0;
          }), W("click", D, ps), W("click", Q, hs), T(g, I);
        };
        R(Os, (g) => {
          n(tr) && g(Mo);
        });
      }
      var Ms = w(Os, 2);
      {
        var Lo = (g) => {
          var I = Ac(), F = v(I), U = v(F);
          {
            var V = (J) => {
              var se = dn(), _e = Le(se);
              {
                var Ce = (je) => {
                  var me = Tc();
                  z(() => {
                    We(me, "src", `data:image/png;base64,${n(nn).src ?? ""}`), We(me, "alt", `${n(nn).size === "incipit" ? "Incipit" : "Full"} notation`), Te(me, 1, `abc-notation-image abc-notation-${n(nn).size ?? ""}`);
                  }), T(je, me);
                }, Ae = (je) => {
                  var me = Ec(), Oe = v(me);
                  z(() => {
                    Te(me, 1, `abc-notation-text abc-notation-${n(nn).size ?? ""}`), N(Oe, n(nn).text);
                  }), T(je, me);
                };
                R(_e, (je) => {
                  n(nn).kind === "img" ? je(Ce) : je(Ae, -1);
                });
              }
              T(J, se);
            };
            R(U, (J) => {
              n(nn) && J(V);
            });
          }
          var te = w(F, 2), B = v(te), re = v(B);
          {
            var D = (J) => {
              var se = xc(), _e = Le(se), Ce = w(_e, 2);
              z(() => {
                Te(_e, 1, `notation-mode-tab ${n(le) === "dots" ? "active" : ""}`), Te(Ce, 1, `notation-mode-tab ${n(le) === "abc" ? "active" : ""}`);
              }), W("click", _e, (Ae) => {
                Ae.stopPropagation(), ar("dots");
              }), W("click", Ce, (Ae) => {
                Ae.stopPropagation(), ar("abc");
              }), T(J, se);
            };
            R(re, (J) => {
              n(Pt).hasDots && n(Pt).hasAbc && J(D);
            });
          }
          var Q = w(B, 2), ue = v(Q);
          {
            var ce = (J) => {
              var se = Ic();
              z(() => We(se, "href", n(ts))), W("click", se, (_e) => _e.stopPropagation()), T(J, se);
            };
            R(ue, (J) => {
              n(ts) && J(ce);
            });
          }
          var K = w(ue);
          {
            var ve = (J) => {
              var se = Cc();
              z(() => We(se, "href", n(ns))), W("click", se, (_e) => _e.stopPropagation()), T(J, se);
            };
            R(K, (J) => {
              n(ns) && J(ve);
            });
          }
          z(() => {
            Te(F, 1, `abc-notation-display${n(Pt).canToggleSize ? " abc-notation-clickable" : ""}`), We(F, "data-current-mode", n(le)), We(F, "data-current-size", n(he)), We(F, "title", n(Pt).canToggleSize ? "Click to toggle between incipit and full notation" : void 0);
          }), W("click", F, yo), T(g, I);
        };
        R(Ms, (g) => {
          n(Pt) && n(Pt).hasAny && g(Lo);
        });
      }
      var Ls = w(Ms, 2);
      {
        var Po = (g) => {
          var I = Oc(), F = v(I);
          on(F, () => n(p).notes, (U) => n(p).notes = U), T(g, I);
        };
        R(Ls, (g) => {
          n(O) === "my_tunes" && g(Po);
        });
      }
      var Ps = w(Ls, 2);
      {
        var Fo = (g) => {
          var I = Mc(), F = v(I), U = w(F, 2);
          let V;
          var te = v(U);
          z(() => {
            U.disabled = n(rs), V = pt(U, "", V, { "background-color": n(_o) }), N(te, n(vo));
          }), W("click", F, Tt), W("click", U, gs), T(g, I);
        };
        R(Ps, (g) => {
          n(dt) || g(Fo);
        });
      }
      var Fs = w(Ps, 2);
      {
        var No = (g) => {
          var I = Nc(), F = v(I);
          {
            var U = (D) => {
              var Q = Lc();
              W("click", Q, (ue) => {
                ue.preventDefault(), bs();
              }), T(D, Q);
            };
            R(F, (D) => {
              n(O) === "my_tunes" && D(U);
            });
          }
          var V = w(F);
          {
            var te = (D) => {
              var Q = Pc();
              W("click", Q, (ue) => {
                ue.preventDefault(), ir();
              }), T(D, Q);
            };
            R(V, (D) => {
              n(O) !== "admin" && !n(dt) && D(te);
            });
          }
          var B = w(V);
          {
            var re = (D) => {
              var Q = Fc();
              W("click", Q, (ue) => {
                ue.preventDefault(), ys();
              }), T(D, Q);
            };
            R(B, (D) => {
              n(O) === "session" && n(Ge).isSessionAdmin && D(re);
            });
          }
          T(g, I);
        };
        R(Fs, (g) => {
          n(ho) && g(No);
        });
      }
      var $o = w(Fs, 2), Ns = v($o), ur = v(Ns), cr = w(ur, 2), $s = w(cr, 2), Ro = w(Ns, 2), fr = v(Ro), Rs = v(fr);
      {
        var Uo = (g) => {
          var I = $c(), F = v(I), U = w(v(F)), V = v(U), te = w(U);
          z(
            (B) => {
              N(V, n(a).person_list_count), N(te, ` tune ${B ?? ""} on Ceol.io`);
            },
            [() => rn(n(a).person_list_count, "list")]
          ), T(g, I);
        };
        R(Rs, (g) => {
          n(a).person_list_count != null && g(Uo);
        });
      }
      var Us = w(Rs, 2), jo = v(Us), js = w(v(jo)), zo = v(js), zs = w(js), Qn = w(zs);
      let Hs;
      var Ho = v(Qn), qo = w(Qn, 2);
      {
        var Wo = (g) => {
          var I = Rc(), F = v(I);
          z(() => N(F, `Last Updated ${n(a).tunebook_count_cached_date ?? ""}`)), T(g, I);
        };
        R(qo, (g) => {
          n(a).tunebook_count_cached_date && g(Wo);
        });
      }
      var Vo = w(Us, 2);
      {
        var Bo = (g) => {
          var I = Uc(), F = Le(I), U = v(F), V = w(v(U)), te = v(V), B = w(V), re = w(F, 2), D = v(re), Q = w(v(D)), ue = v(Q), ce = w(Q);
          z(
            (K, ve) => {
              N(te, n(a).session_play_count || 0), N(B, ` ${K ?? ""} at my sessions`), N(ue, n(a).global_play_count || 0), N(ce, ` ${ve ?? ""} at all sessions`);
            },
            [
              () => rn(n(a).session_play_count || 0, "time"),
              () => rn(n(a).global_play_count || 0, "time")
            ]
          ), T(g, I);
        }, Do = (g) => {
          var I = zc(), F = Le(I);
          {
            var U = (Q) => {
              var ue = jc(), ce = v(ue), K = w(v(ce)), ve = v(K), J = w(K);
              z(
                (se) => {
                  N(ve, n(a).times_played || 0), N(J, ` ${se ?? ""} at this session`);
                },
                [() => rn(n(a).times_played || 0, "time")]
              ), T(Q, ue);
            };
            R(F, (Q) => {
              n(dt) || Q(U);
            });
          }
          var V = w(F, 2), te = v(V), B = w(v(te)), re = v(B), D = w(B);
          z(
            (Q) => {
              N(re, n(a).global_play_count || 0), N(D, ` ${Q ?? ""} at all sessions`);
            },
            [() => rn(n(a).global_play_count || 0, "time")]
          ), T(g, I);
        }, Go = (g) => {
          var I = Hc(), F = Le(I), U = v(F), V = w(v(U)), te = v(V), B = w(V), re = w(F, 2), D = v(re), Q = w(v(D)), ue = v(Q);
          z(
            (ce) => {
              N(te, n(a).global_play_count || 0), N(B, ` ${ce ?? ""} at all sessions`), N(ue, n(a).session_count || 0);
            },
            [() => rn(n(a).global_play_count || 0, "time")]
          ), T(g, I);
        };
        R(Vo, (g) => {
          n(O) === "my_tunes" ? g(Bo) : n(O) === "session" || n(O) === "session_instance" ? g(Do, 1) : n(O) === "admin" && g(Go, 2);
        });
      }
      var dr = w(fr, 2), qs = v(dr);
      {
        var Yo = (g) => {
          var I = ma();
          Nt(I, 21, () => n(ss), Bt, (F, U) => {
            var V = pa(), te = v(V);
            z(() => {
              Te(V, 1, `history-scope-btn${n(U).key === n(Pe) ? " active" : ""}`), We(V, "data-scope", n(U).key), N(te, n(U).label);
            }), W("click", V, () => ks(n(U).key)), T(F, V);
          }), T(g, I);
        };
        R(qs, (g) => {
          n(ss).length > 1 && g(Yo);
        });
      }
      var Ko = w(qs, 2), Jo = v(Ko);
      {
        var Zo = (g) => {
          const I = /* @__PURE__ */ ne(() => n(Kn).data.play_instances || []);
          var F = dn(), U = Le(F);
          {
            var V = (B) => {
              var re = ga();
              T(B, re);
            }, te = (B) => {
              var re = Dc(), D = Le(re);
              Nt(D, 21, () => n(I), Bt, (ce, K) => {
                var ve = Vc(), J = v(ve), se = v(J), _e = v(se), Ce = w(J, 2);
                {
                  var Ae = (Oe) => {
                    var ze = qc(), ht = v(ze);
                    z(() => N(ht, `Set ${n(K).set_number ?? ""}, Tune ${n(K).position_in_set ?? ""}`)), T(Oe, ze);
                  };
                  R(Ce, (Oe) => {
                    n(K).set_number && n(K).position_in_set && Oe(Ae);
                  });
                }
                var je = w(Ce, 2);
                {
                  var me = (Oe) => {
                    var ze = Wc(), ht = v(ze);
                    z(() => N(ht, `Setting: #${n(K).setting_id_override ?? ""}`)), T(Oe, ze);
                  };
                  R(je, (Oe) => {
                    n(K).setting_id_override && Oe(me);
                  });
                }
                z(() => {
                  We(se, "href", n(K).link), N(_e, n(Pe) !== "session" ? n(K).full_name || n(K).date || "Unknown" : n(K).date || "Unknown");
                }), T(ce, ve);
              });
              var Q = w(D, 2);
              {
                var ue = (ce) => {
                  var K = Bc();
                  T(ce, K);
                };
                R(Q, (ce) => {
                  n(Kn).data.truncated && ce(ue);
                });
              }
              T(B, re);
            };
            R(U, (B) => {
              n(I).length === 0 ? B(V) : B(te, -1);
            });
          }
          T(g, F);
        }, Xo = (g) => {
          var I = Gc();
          T(g, I);
        }, Qo = (g) => {
          var I = ga();
          T(g, I);
        }, el = (g) => {
          var I = Yc();
          T(g, I);
        };
        R(Jo, (g) => {
          n(Kn).status === "ready" ? g(Zo) : n(Kn).status === "error" ? g(Xo, 1) : n(Kn).status === "none" ? g(Qo, 2) : g(el, -1);
        });
      }
      var Ws = w(dr, 2), Vs = v(Ws);
      {
        var tl = (g) => {
          var I = ma();
          Nt(I, 21, () => n(as), Bt, (F, U) => {
            var V = pa(), te = v(V);
            z(() => {
              Te(V, 1, `played-with-scope-btn history-scope-btn${n(U).key === n(ye) ? " active" : ""}`), We(V, "data-scope", n(U).key), N(te, n(U).label);
            }), W("click", V, () => Ss(n(U).key)), T(F, V);
          }), T(g, I);
        };
        R(Vs, (g) => {
          n(as).length > 1 && g(tl);
        });
      }
      var nl = w(Vs, 2), il = v(nl);
      {
        var rl = (g) => {
          const I = /* @__PURE__ */ ne(() => n(Ei).data.tunes || []);
          var F = dn(), U = Le(F);
          {
            var V = (B) => {
              var re = Kc(), D = v(re);
              z(() => N(D, `This tune has not been played in a set with any other tune${n(ye) === "session" ? " at this session" : ""} yet.`)), T(B, re);
            }, te = (B) => {
              var re = Zc();
              Nt(re, 21, () => n(I), Bt, (D, Q) => {
                var ue = Jc(), ce = v(ue), K = v(ce), ve = w(ce, 2), J = v(ve);
                z(() => {
                  We(ue, "data-tune-id", n(Q).tune_id), N(K, n(Q).name), N(J, n(Q).count);
                }), W("click", ue, () => bo(n(Q).tune_id)), T(D, ue);
              }), T(B, re);
            };
            R(U, (B) => {
              n(I).length === 0 ? B(V) : B(te, -1);
            });
          }
          T(g, F);
        }, sl = (g) => {
          var I = Xc();
          T(g, I);
        }, al = (g) => {
          var I = Qc();
          T(g, I);
        }, ol = (g) => {
          var I = ef();
          T(g, I);
        };
        R(il, (g) => {
          n(Ei).status === "ready" ? g(rl) : n(Ei).status === "error" ? g(sl, 1) : n(Ei).status === "none" ? g(al, 2) : g(ol, -1);
        });
      }
      z(
        (g) => {
          Te(ur, 1, `modal-tab${n(b) === "stats" ? " active" : ""}`), Te(cr, 1, `modal-tab${n(b) === "history" ? " active" : ""}`), Te($s, 1, `modal-tab${n(b) === "played-with" ? " active" : ""}`), Te(fr, 1, `modal-tab-pane${n(b) === "stats" ? " active" : ""}`), N(zo, n(Is)), N(zs, ` ${g ?? ""} on TheSession.org `), Qn.disabled = n(Z) === "loading", Hs = pt(Qn, "", Hs, {
            "background-color": n(Z) === "ok" ? "#28a745" : n(Z) === "err" ? "#dc3545" : "",
            color: n(Z) === "ok" || n(Z) === "err" ? "white" : ""
          }), N(Ho, n(Z) === "loading" ? "⟳" : n(Z) === "ok" ? "✓" : n(Z) === "err" ? "✗" : "↻"), Te(dr, 1, `modal-tab-pane${n(b) === "history" ? " active" : ""}`), Te(Ws, 1, `modal-tab-pane${n(b) === "played-with" ? " active" : ""}`);
        },
        [() => rn(n(Is), "tunebook")]
      ), W("click", lr, Tt), W("click", ur, () => Ii("stats")), W("click", cr, () => Ii("history")), W("click", $s, () => Ii("played-with")), W("click", Qn, ws), T(u, y);
    };
    R(To, (u) => {
      n(s) === "loading" ? u(Eo) : n(s) === "error" ? u(xo, 1) : n(s) === "ready" && n(a) && u(Io, 2);
    });
  }
  return z(() => {
    Te(Zn, 1, `modal-overlay${n(r) ? " show" : ""}`), pt(Zn, `display: ${n(i) ? "flex" : "none"};`);
  }), W("click", Zn, mo), T(e, Zn), qr(wo);
}
oo(["click", "input"]);
var sf = /* @__PURE__ */ M('<li class="ft-item" role="option" aria-selected="false" tabindex="0"> <span class="ft-type"> </span></li>'), af = /* @__PURE__ */ M('<li class="ft-empty">No tunes match</li>'), of = /* @__PURE__ */ M('<div id="find-tune-overlay"><div class="ft-scrim" role="presentation"></div> <div class="ft-panel" role="dialog" aria-modal="true"><div class="ft-head"><span>Find a tune</span> <button class="ft-close" aria-label="Close">✕</button></div> <input class="ft-input" type="text" placeholder="Search tunes…" autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false"/> <ul class="ft-results"><!></ul></div></div>');
function lf(e, t) {
  Hr(t, !0);
  let i = /* @__PURE__ */ G(!1), r = /* @__PURE__ */ G(""), s = /* @__PURE__ */ G(
    null
    // null = nothing to show; [] = "No tunes match"
  ), o = /* @__PURE__ */ G(null), l = null, a = 0;
  function f() {
    E(r, ""), E(s, null), E(i, !0), setTimeout(() => n(o) && n(o).focus(), 50);
  }
  function _() {
    E(i, !1), l && clearTimeout(l), a++;
  }
  async function h(A) {
    if (window.CeolOffline)
      try {
        return await window.CeolOffline.searchTunes(A, 10);
      } catch {
      }
    return null;
  }
  function x() {
    const A = n(r).trim();
    if (l && clearTimeout(l), A.length < 2) {
      E(s, null);
      return;
    }
    l = setTimeout(
      async () => {
        const q = ++a, L = (Z) => {
          q === a && E(s, Z || [], !0);
        };
        try {
          const oe = await (await fetch("/api/tunes/search?q=" + encodeURIComponent(A) + "&limit=10", { credentials: "same-origin" })).json();
          if (q !== a) return;
          if (oe && oe.success && (oe.tunes || []).length) {
            L(oe.tunes);
            return;
          }
          const Se = await h(A);
          L(Se !== null ? Se : oe.tunes || []);
        } catch {
          const oe = await h(A);
          oe !== null && L(oe);
        }
      },
      200
    );
  }
  function d(A) {
    _(), window.TuneDetailModal.show({
      context: "session_instance",
      tuneId: A.tune_id,
      apiEndpoint: "/api/tunes/" + A.tune_id + "/detail",
      additionalData: { isUserLoggedIn: !0, tuneName: A.name, global: !0 }
    });
  }
  pu(() => {
    if (!n(i)) return;
    const A = (q) => {
      q.key === "Escape" && _();
    };
    return document.addEventListener("keydown", A), () => document.removeEventListener("keydown", A);
  });
  var b = { show: f }, C = dn(), p = Le(C);
  {
    var m = (A) => {
      var q = of(), L = v(q), Z = w(L, 2), oe = v(Z), Se = w(v(oe), 2), le = w(oe, 2);
      Vu(le, (ye) => E(o, ye), () => n(o));
      var he = w(le, 2), Pe = v(he);
      {
        var pe = (ye) => {
          var Ue = dn(), O = Le(Ue);
          {
            var Ge = (vt) => {
              var St = dn(), tn = Le(St);
              Nt(tn, 17, () => n(s), (qe) => qe.tune_id, (qe, _t) => {
                var Lt = sf(), Ti = v(Lt), tr = w(Ti), Tn = v(tr);
                z(() => {
                  We(Lt, "data-tune-id", n(_t).tune_id), N(Ti, n(_t).name), N(Tn, n(_t).tune_type || "");
                }), W("click", Lt, () => d(n(_t))), W("keydown", Lt, (Pt) => Pt.key === "Enter" && d(n(_t))), T(qe, Lt);
              }), T(vt, St);
            }, dt = (vt) => {
              var St = af();
              T(vt, St);
            };
            R(O, (vt) => {
              n(s).length ? vt(Ge) : vt(dt, -1);
            });
          }
          T(ye, Ue);
        };
        R(Pe, (ye) => {
          n(s) !== null && ye(pe);
        });
      }
      W("click", L, _), W("click", Se, _), W("input", le, x), on(le, () => n(r), (ye) => E(r, ye)), T(A, q);
    };
    R(p, (A) => {
      n(i) && A(m);
    });
  }
  return T(e, C), qr(b);
}
oo(["click", "input", "keydown"]);
if (!window.TuneDetailModal) {
  const e = document.createElement("div");
  document.body.appendChild(e);
  const t = ta(rf, { target: e });
  window.TuneDetailModal = {
    // The Svelte component wires its own listeners; kept for legacy callers.
    init() {
    },
    show: (s) => t.show(s),
    close: () => t.close(),
    getTuneIdFromUrl: Zu,
    logToActiveSession: () => t.logToActiveSession(),
    toggleConfigSection: () => t.toggleConfigSection(),
    switchNotationMode: (s) => t.switchNotationMode(s),
    toggleNotationSize: () => t.toggleNotationSize(),
    switchTab: (s) => t.switchTab(s),
    setHistoryScope: (s) => t.setHistoryScope(s),
    setPlayedWithScope: (s) => t.setPlayedWithScope(s),
    save: () => t.save(),
    incrementHeardCount: () => t.incrementHeardCount(),
    decrementHeardCount: () => t.decrementHeardCount(),
    addToTunebook: () => t.addToTunebook(),
    setTunebookStatus: (s) => t.setTunebookStatus(s),
    setInstrumentStatus: (s, o) => t.setInstrumentStatus(s, o),
    removeInstrumentTune: (s) => t.removeInstrumentTune(s),
    toggleStatusExpand: (s) => t.toggleStatusExpand(s),
    removeFromMyTunes: () => t.removeFromMyTunes(),
    removeFromSession: () => t.removeFromSession(),
    refreshTunebookCount: () => t.refreshTunebookCount(),
    fetchSetting: () => t.fetchSetting(),
    // Dirty-checking is reactive in the Svelte port; kept as no-ops for legacy callers.
    onFieldChange() {
    },
    onSettingInput() {
    }
  };
  const i = document.createElement("div");
  document.body.appendChild(i);
  const r = ta(lf, { target: i });
  window.FindTuneOverlay = { open: () => r.show() };
}
