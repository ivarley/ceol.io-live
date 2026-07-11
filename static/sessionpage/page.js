var ja = Object.defineProperty;
var wi = (e) => {
  throw TypeError(e);
};
var za = (e, t, n) => t in e ? ja(e, t, { enumerable: !0, configurable: !0, writable: !0, value: n }) : e[t] = n;
var yt = (e, t, n) => za(e, typeof t != "symbol" ? t + "" : t, n), Os = (e, t, n) => t.has(e) || wi("Cannot " + n);
var c = (e, t, n) => (Os(e, t, "read from private field"), n ? n.call(e) : t.get(e)), q = (e, t, n) => t.has(e) ? wi("Cannot add the same private member more than once") : t instanceof WeakSet ? t.add(e) : t.set(e, n), Y = (e, t, n, r) => (Os(e, t, "write to private field"), r ? r.call(e, n) : t.set(e, n), n), re = (e, t, n) => (Os(e, t, "access private method"), n);
var oi = Array.isArray, Ua = Array.prototype.indexOf, cs = Array.prototype.includes, ks = Array.from, qa = Object.defineProperty, Jn = Object.getOwnPropertyDescriptor, $a = Object.getOwnPropertyDescriptors, Ba = Object.prototype, Va = Array.prototype, Vi = Object.getPrototypeOf, bi = Object.isExtensible;
const ds = () => {
};
function Ha(e) {
  for (var t = 0; t < e.length; t++)
    e[t]();
}
function Hi() {
  var e, t, n = new Promise((r, s) => {
    e = r, t = s;
  });
  return { promise: n, resolve: e, reject: t };
}
function Yi(e, t) {
  if (Array.isArray(e))
    return e;
  if (!(Symbol.iterator in e))
    return Array.from(e);
  const n = [];
  for (const r of e)
    if (n.push(r), n.length === t) break;
  return n;
}
const We = 2, ir = 4, Es = 8, Gi = 1 << 24, $t = 16, Vt = 32, An = 64, Hs = 128, Ot = 512, Re = 1024, Ge = 2048, sn = 4096, st = 8192, Tt = 16384, fr = 32768, Ys = 1 << 25, ar = 65536, fs = 1 << 17, Ya = 1 << 18, vr = 1 << 19, Ga = 1 << 20, nn = 1 << 25, $n = 65536, vs = 1 << 21, Xn = 1 << 22, Tn = 1 << 23, zn = Symbol("$state"), Wa = Symbol("legacy props"), Ja = Symbol(""), ss = Symbol("attributes"), Gs = Symbol("class"), Ws = Symbol("style"), Sr = Symbol("text"), is = Symbol("form reset"), As = new class extends Error {
  constructor() {
    super(...arguments);
    yt(this, "name", "StaleReactionError");
    yt(this, "message", "The reaction that called `getAbortSignal()` was re-run or destroyed");
  }
}();
var qi;
const Xa = (
  // We gotta write it like this because after downleveling the pure comment may end up in the wrong location
  !!((qi = globalThis.document) != null && qi.contentType) && /* @__PURE__ */ globalThis.document.contentType.includes("xml")
);
function Za() {
  throw new Error("https://svelte.dev/e/async_derived_orphan");
}
function Qa(e, t, n) {
  throw new Error("https://svelte.dev/e/each_key_duplicate");
}
function Ka(e) {
  throw new Error("https://svelte.dev/e/effect_in_teardown");
}
function eo() {
  throw new Error("https://svelte.dev/e/effect_in_unowned_derived");
}
function to(e) {
  throw new Error("https://svelte.dev/e/effect_orphan");
}
function no() {
  throw new Error("https://svelte.dev/e/effect_update_depth_exceeded");
}
function ro(e) {
  throw new Error("https://svelte.dev/e/props_invalid_value");
}
function so() {
  throw new Error("https://svelte.dev/e/state_descriptors_fixed");
}
function io() {
  throw new Error("https://svelte.dev/e/state_prototype_fixed");
}
function ao() {
  throw new Error("https://svelte.dev/e/state_unsafe_mutation");
}
function oo() {
  throw new Error("https://svelte.dev/e/svelte_boundary_reset_onerror");
}
const lo = 1, uo = 2, Wi = 4, co = 8, fo = 16, vo = 1, ho = 4, po = 8, _o = 16, go = 1, mo = 2, Oe = Symbol("uninitialized"), yo = "http://www.w3.org/1999/xhtml";
function wo() {
  console.warn("https://svelte.dev/e/derived_inert");
}
function bo() {
  console.warn("https://svelte.dev/e/select_multiple_invalid_value");
}
function xo() {
  console.warn("https://svelte.dev/e/svelte_boundary_reset_noop");
}
function Ji(e) {
  return e === this.v;
}
function So(e, t) {
  return e != e ? t == t : e !== t || e !== null && typeof e == "object" || typeof e == "function";
}
function Xi(e) {
  return !So(e, this.v);
}
let it = null;
function or(e) {
  it = e;
}
function hr(e, t = !1, n) {
  it = {
    p: it,
    i: !1,
    c: null,
    e: null,
    s: e,
    x: null,
    r: (
      /** @type {Effect} */
      ee
    ),
    l: null
  };
}
function pr(e) {
  var t = (
    /** @type {ComponentContext} */
    it
  ), n = t.e;
  if (n !== null) {
    t.e = null;
    for (var r of n)
      ga(r);
  }
  return e !== void 0 && (t.x = e), t.i = !0, it = t.p, e ?? /** @type {T} */
  {};
}
function Zi() {
  return !0;
}
let Mn = [];
function Qi() {
  var e = Mn;
  Mn = [], Ha(e);
}
function kn(e) {
  if (Mn.length === 0 && !Ir) {
    var t = Mn;
    queueMicrotask(() => {
      t === Mn && Qi();
    });
  }
  Mn.push(e);
}
function To() {
  for (; Mn.length > 0; )
    Qi();
}
function Ki(e) {
  var t = ee;
  if (t === null)
    return Q.f |= Tn, e;
  if (!(t.f & fr) && !(t.f & ir))
    throw e;
  xn(e, t);
}
function xn(e, t) {
  if (!(t !== null && t.f & Tt)) {
    for (; t !== null; ) {
      if (t.f & Hs) {
        if (!(t.f & fr))
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
const ko = -7169;
function Pe(e, t) {
  e.f = e.f & ko | t;
}
function li(e) {
  e.f & Ot || e.deps === null ? Pe(e, Re) : Pe(e, sn);
}
function ea(e) {
  if (e !== null)
    for (const t of e)
      !(t.f & We) || !(t.f & $n) || (t.f ^= $n, ea(
        /** @type {Derived} */
        t.deps
      ));
}
function ta(e, t, n) {
  e.f & Ge ? t.add(e) : e.f & sn && n.add(e), ea(e.deps), Pe(e, Re);
}
let ns = !1;
function Eo(e) {
  var t = ns;
  try {
    return ns = !1, [e(), ns];
  } finally {
    ns = t;
  }
}
function Ao(e) {
  let t = 0, n = Pn(0), r;
  return () => {
    vi() && (i(n), Is(() => (t === 0 && (r = gn(() => e(() => En(n)))), t += 1, () => {
      kn(() => {
        t -= 1, t === 0 && (r == null || r(), r = void 0, En(n));
      });
    })));
  };
}
var Po = ar | vr;
function Io(e, t, n, r) {
  new Lo(e, t, n, r);
}
var Mt, ai, Ct, Nn, ft, Dt, nt, bt, ln, On, yn, Zn, Or, Rr, un, ws, Te, Mo, Co, Do, Js, as, os, Xs, Zs;
class Lo {
  /**
   * @param {TemplateNode} node
   * @param {BoundaryProps} props
   * @param {((anchor: Node) => void)} children
   * @param {((error: unknown) => unknown) | undefined} [transform_error]
   */
  constructor(t, n, r, s) {
    q(this, Te);
    /** @type {Boundary | null} */
    yt(this, "parent");
    yt(this, "is_pending", !1);
    /**
     * API-level transformError transform function. Transforms errors before they reach the `failed` snippet.
     * Inherited from parent boundary, or defaults to identity.
     * @type {(error: unknown) => unknown}
     */
    yt(this, "transform_error");
    /** @type {TemplateNode} */
    q(this, Mt);
    /** @type {TemplateNode | null} */
    q(this, ai, null);
    /** @type {BoundaryProps} */
    q(this, Ct);
    /** @type {((anchor: Node) => void)} */
    q(this, Nn);
    /** @type {Effect} */
    q(this, ft);
    /** @type {Effect | null} */
    q(this, Dt, null);
    /** @type {Effect | null} */
    q(this, nt, null);
    /** @type {Effect | null} */
    q(this, bt, null);
    /** @type {DocumentFragment | null} */
    q(this, ln, null);
    q(this, On, 0);
    q(this, yn, 0);
    q(this, Zn, !1);
    /** @type {Set<Effect>} */
    q(this, Or, /* @__PURE__ */ new Set());
    /** @type {Set<Effect>} */
    q(this, Rr, /* @__PURE__ */ new Set());
    /**
     * A source containing the number of pending async deriveds/expressions.
     * Only created if `$effect.pending()` is used inside the boundary,
     * otherwise updating the source results in needless `Batch.ensure()`
     * calls followed by no-op flushes
     * @type {Source<number> | null}
     */
    q(this, un, null);
    q(this, ws, Ao(() => (Y(this, un, Pn(c(this, On))), () => {
      Y(this, un, null);
    })));
    var a;
    Y(this, Mt, t), Y(this, Ct, n), Y(this, Nn, (o) => {
      var l = (
        /** @type {Effect} */
        ee
      );
      l.b = this, l.f |= Hs, r(o);
    }), this.parent = /** @type {Effect} */
    ee.b, this.transform_error = s ?? ((a = this.parent) == null ? void 0 : a.transform_error) ?? ((o) => o), Y(this, ft, pi(() => {
      re(this, Te, Js).call(this);
    }, Po));
  }
  /**
   * Defer an effect inside a pending boundary until the boundary resolves
   * @param {Effect} effect
   */
  defer_effect(t) {
    ta(t, c(this, Or), c(this, Rr));
  }
  /**
   * Returns `false` if the effect exists inside a boundary whose pending snippet is shown
   * @returns {boolean}
   */
  is_rendered() {
    return !this.is_pending && (!this.parent || this.parent.is_rendered());
  }
  has_pending_snippet() {
    return !!c(this, Ct).pending;
  }
  /**
   * Update the source that powers `$effect.pending()` inside this boundary,
   * and controls when the current `pending` snippet (if any) is removed.
   * Do not call from inside the class
   * @param {1 | -1} d
   * @param {Batch} batch
   */
  update_pending_count(t, n) {
    re(this, Te, Xs).call(this, t, n), Y(this, On, c(this, On) + t), !(!c(this, un) || c(this, Zn)) && (Y(this, Zn, !0), kn(() => {
      Y(this, Zn, !1), c(this, un) && lr(c(this, un), c(this, On));
    }));
  }
  get_effect_pending() {
    return c(this, ws).call(this), i(
      /** @type {Source<number>} */
      c(this, un)
    );
  }
  /** @param {unknown} error */
  error(t) {
    if (!c(this, Ct).onerror && !c(this, Ct).failed)
      throw t;
    F != null && F.is_fork ? (c(this, Dt) && F.skip_effect(c(this, Dt)), c(this, nt) && F.skip_effect(c(this, nt)), c(this, bt) && F.skip_effect(c(this, bt)), F.oncommit(() => {
      re(this, Te, Zs).call(this, t);
    })) : re(this, Te, Zs).call(this, t);
  }
}
Mt = new WeakMap(), ai = new WeakMap(), Ct = new WeakMap(), Nn = new WeakMap(), ft = new WeakMap(), Dt = new WeakMap(), nt = new WeakMap(), bt = new WeakMap(), ln = new WeakMap(), On = new WeakMap(), yn = new WeakMap(), Zn = new WeakMap(), Or = new WeakMap(), Rr = new WeakMap(), un = new WeakMap(), ws = new WeakMap(), Te = new WeakSet(), Mo = function() {
  try {
    Y(this, Dt, Nt(() => c(this, Nn).call(this, c(this, Mt))));
  } catch (t) {
    this.error(t);
  }
}, /**
 * @param {unknown} error The deserialized error from the server's hydration comment
 */
Co = function(t) {
  const n = c(this, Ct).failed;
  n && Y(this, bt, Nt(() => {
    n(
      c(this, Mt),
      () => t,
      () => () => {
      }
    );
  }));
}, Do = function() {
  const t = c(this, Ct).pending;
  t && (this.is_pending = !0, Y(this, nt, Nt(() => t(c(this, Mt)))), kn(() => {
    var n = Y(this, ln, document.createDocumentFragment()), r = fn();
    n.append(r), Y(this, Dt, re(this, Te, os).call(this, () => Nt(() => c(this, Nn).call(this, r)))), c(this, yn) === 0 && (c(this, Mt).before(n), Y(this, ln, null), qn(
      /** @type {Effect} */
      c(this, nt),
      () => {
        Y(this, nt, null);
      }
    ), re(this, Te, as).call(
      this,
      /** @type {Batch} */
      F
    ));
  }));
}, Js = function() {
  try {
    if (this.is_pending = this.has_pending_snippet(), Y(this, yn, 0), Y(this, On, 0), Y(this, Dt, Nt(() => {
      c(this, Nn).call(this, c(this, Mt));
    })), c(this, yn) > 0) {
      var t = Y(this, ln, document.createDocumentFragment());
      gi(c(this, Dt), t);
      const n = (
        /** @type {(anchor: Node) => void} */
        c(this, Ct).pending
      );
      Y(this, nt, Nt(() => n(c(this, Mt))));
    } else
      re(this, Te, as).call(
        this,
        /** @type {Batch} */
        F
      );
  } catch (n) {
    this.error(n);
  }
}, /**
 * @param {Batch} batch
 */
as = function(t) {
  this.is_pending = !1, t.transfer_effects(c(this, Or), c(this, Rr));
}, /**
 * @template T
 * @param {() => T} fn
 */
os = function(t) {
  var n = ee, r = Q, s = it;
  an(c(this, ft)), Rt(c(this, ft)), or(c(this, ft).ctx);
  try {
    return Bn.ensure(), t();
  } catch (a) {
    return Ki(a), null;
  } finally {
    an(n), Rt(r), or(s);
  }
}, /**
 * Updates the pending count associated with the currently visible pending snippet,
 * if any, such that we can replace the snippet with content once work is done
 * @param {1 | -1} d
 * @param {Batch} batch
 */
Xs = function(t, n) {
  var r;
  if (!this.has_pending_snippet()) {
    this.parent && re(r = this.parent, Te, Xs).call(r, t, n);
    return;
  }
  Y(this, yn, c(this, yn) + t), c(this, yn) === 0 && (re(this, Te, as).call(this, n), c(this, nt) && qn(c(this, nt), () => {
    Y(this, nt, null);
  }), c(this, ln) && (c(this, Mt).before(c(this, ln)), Y(this, ln, null)));
}, /**
 * @param {unknown} error
 */
Zs = function(t) {
  c(this, Dt) && (pt(c(this, Dt)), Y(this, Dt, null)), c(this, nt) && (pt(c(this, nt)), Y(this, nt, null)), c(this, bt) && (pt(c(this, bt)), Y(this, bt, null));
  var n = c(this, Ct).onerror;
  let r = c(this, Ct).failed;
  var s = !1, a = !1;
  const o = () => {
    if (s) {
      xo();
      return;
    }
    s = !0, a && oo(), c(this, bt) !== null && qn(c(this, bt), () => {
      Y(this, bt, null);
    }), re(this, Te, os).call(this, () => {
      re(this, Te, Js).call(this);
    });
  }, l = (u) => {
    try {
      a = !0, n == null || n(u, o), a = !1;
    } catch (f) {
      xn(f, c(this, ft) && c(this, ft).parent);
    }
    r && Y(this, bt, re(this, Te, os).call(this, () => {
      try {
        return Nt(() => {
          var f = (
            /** @type {Effect} */
            ee
          );
          f.b = this, f.f |= Hs, r(
            c(this, Mt),
            () => u,
            () => o
          );
        });
      } catch (f) {
        return xn(
          f,
          /** @type {Effect} */
          c(this, ft).parent
        ), null;
      }
    }));
  };
  kn(() => {
    var u;
    try {
      u = this.transform_error(t);
    } catch (f) {
      xn(f, c(this, ft) && c(this, ft).parent);
      return;
    }
    u !== null && typeof u == "object" && typeof /** @type {any} */
    u.then == "function" ? u.then(
      l,
      /** @param {unknown} e */
      (f) => xn(f, c(this, ft) && c(this, ft).parent)
    ) : l(u);
  });
};
function No(e, t, n, r) {
  const s = Mr;
  var a = e.filter((m) => !m.settled), o = t.map(s);
  if (n.length === 0 && a.length === 0) {
    r(o);
    return;
  }
  var l = (
    /** @type {Effect} */
    ee
  ), u = Oo(), f = a.length === 1 ? a[0].promise : a.length > 1 ? Promise.all(a.map((m) => m.promise)) : null;
  function p(m) {
    if (!(l.f & Tt)) {
      u();
      try {
        r([...o, ...m]);
      } catch (y) {
        xn(y, l);
      }
      hs();
    }
  }
  var x = na();
  if (n.length === 0) {
    f.then(() => p([])).finally(x);
    return;
  }
  function h() {
    Promise.all(n.map((m) => /* @__PURE__ */ Ro(m))).then(p).catch((m) => xn(m, l)).finally(x);
  }
  f ? f.then(() => {
    u(), h(), hs();
  }) : h();
}
function Oo() {
  var e = (
    /** @type {Effect} */
    ee
  ), t = Q, n = it, r = (
    /** @type {Batch} */
    F
  );
  return function(a = !0) {
    an(e), Rt(t), or(n), a && !(e.f & Tt) && (r == null || r.activate(), r == null || r.apply());
  };
}
function hs(e = !0) {
  an(null), Rt(null), or(null), e && (F == null || F.deactivate());
}
function na() {
  var e = (
    /** @type {Effect} */
    ee
  ), t = e.b, n = (
    /** @type {Batch} */
    F
  ), r = !!(t != null && t.is_rendered());
  return t == null || t.update_pending_count(1, n), n.increment(r, e), () => {
    t == null || t.update_pending_count(-1, n), n.decrement(r, e);
  };
}
// @__NO_SIDE_EFFECTS__
function Mr(e) {
  var t = We | Ge;
  return ee !== null && (ee.f |= vr), {
    ctx: it,
    deps: null,
    effects: null,
    equals: Ji,
    f: t,
    fn: e,
    reactions: null,
    rv: 0,
    v: (
      /** @type {V} */
      Oe
    ),
    wv: 0,
    parent: ee,
    ac: null
  };
}
const Tr = Symbol("obsolete");
// @__NO_SIDE_EFFECTS__
function Ro(e, t, n) {
  let r = (
    /** @type {Effect | null} */
    ee
  );
  r === null && Za();
  var s = (
    /** @type {Promise<V>} */
    /** @type {unknown} */
    void 0
  ), a = Pn(
    /** @type {V} */
    Oe
  ), o = !Q, l = /* @__PURE__ */ new Set();
  return Ko(() => {
    var m, y;
    var u = (
      /** @type {Effect} */
      ee
    ), f = Hi();
    s = f.promise;
    try {
      Promise.resolve(e()).then(f.resolve, (T) => {
        T !== As && f.reject(T);
      }).finally(hs);
    } catch (T) {
      f.reject(T), hs();
    }
    var p = (
      /** @type {Batch} */
      F
    );
    if (o) {
      if (u.f & fr)
        var x = na();
      if (
        // boundary can be null if the async derived is inside an $effect.root not connected to the component render tree
        (m = r.b) != null && m.is_rendered()
      )
        (y = p.async_deriveds.get(u)) == null || y.reject(Tr);
      else
        for (const T of l.values())
          T.reject(Tr);
      l.add(f), p.async_deriveds.set(u, f);
    }
    const h = (T, w = void 0) => {
      x == null || x(), l.delete(f), w !== Tr && (p.activate(), w ? (a.f |= Tn, lr(a, w)) : (a.f & Tn && (a.f ^= Tn), lr(a, T)), p.deactivate());
    };
    f.promise.then(h, (T) => h(null, T || "unknown"));
  }), hi(() => {
    for (const u of l)
      u.reject(Tr);
  }), new Promise((u) => {
    function f(p) {
      function x() {
        p === s ? u(a) : f(s);
      }
      p.then(x, x);
    }
    f(s);
  });
}
// @__NO_SIDE_EFFECTS__
function he(e) {
  const t = /* @__PURE__ */ Mr(e);
  return Sa(t), t;
}
// @__NO_SIDE_EFFECTS__
function ra(e) {
  const t = /* @__PURE__ */ Mr(e);
  return t.equals = Xi, t;
}
function Fo(e) {
  var t = e.effects;
  if (t !== null) {
    e.effects = null;
    for (var n = 0; n < t.length; n += 1)
      pt(
        /** @type {Effect} */
        t[n]
      );
  }
}
function ui(e) {
  var t, n = ee, r = e.parent;
  if (!pn && r !== null && e.v !== Oe && // if it was never evaluated before, it's guaranteed to fail downstream, so we try to execute instead
  r.f & (Tt | st))
    return wo(), e.v;
  an(r);
  try {
    e.f &= ~$n, Fo(e), t = Aa(e);
  } finally {
    an(n);
  }
  return t;
}
function sa(e) {
  var t = ui(e);
  if (!e.equals(t) && (e.wv = ka(), (!(F != null && F.is_fork) || e.deps === null) && (F !== null ? (F.capture(e, t, !0), Pr == null || Pr.capture(e, t, !0)) : e.v = t, e.deps === null))) {
    Pe(e, Re);
    return;
  }
  pn || (He !== null ? (vi() || F != null && F.is_fork) && He.set(e, t) : li(e));
}
function jo(e) {
  var t, n;
  if (e.effects !== null)
    for (const r of e.effects)
      (r.teardown || r.ac) && ((t = r.teardown) == null || t.call(r), (n = r.ac) == null || n.abort(As), r.fn !== null && (r.teardown = ds), r.ac = null, Cr(r, 0), _i(r));
}
function ia(e) {
  if (e.effects !== null)
    for (const t of e.effects)
      t.teardown && t.fn !== null && ur(t);
}
let Rs = null, Hn = null, F = null, Pr = null, He = null, Qs = null, Ir = !1, Fs = !1, Wn = null, ls = null;
var xi = 0;
let zo = 1;
var Qn, wn, Rn, Kn, er, tr, cn, nr, vt, Fr, dn, zt, en, rr, Fn, ue, Ks, kr, ei, aa, oa, Yn, Uo, Er;
const bs = class bs {
  constructor() {
    q(this, ue);
    yt(this, "id", zo++);
    /** True as soon as `#process` was called */
    q(this, Qn, !1);
    yt(this, "linked", !0);
    /** @type {Batch | null} */
    q(this, wn, null);
    /** @type {Batch | null} */
    q(this, Rn, null);
    /** @type {Map<Effect, ReturnType<typeof deferred<any>>>} */
    yt(this, "async_deriveds", /* @__PURE__ */ new Map());
    /**
     * The current values of any signals that are updated in this batch.
     * Tuple format: [value, is_derived] (note: is_derived is false for deriveds, too, if they were overridden via assignment)
     * They keys of this map are identical to `this.#previous`
     * @type {Map<Value, [any, boolean]>}
     */
    yt(this, "current", /* @__PURE__ */ new Map());
    /**
     * The values of any signals (sources and deriveds) that are updated in this batch _before_ those updates took place.
     * They keys of this map are identical to `this.#current`
     * @type {Map<Value, any>}
     */
    yt(this, "previous", /* @__PURE__ */ new Map());
    /**
     * When the batch is committed (and the DOM is updated), we need to remove old branches
     * and append new ones by calling the functions added inside (if/each/key/etc) blocks
     * @type {Set<(batch: Batch) => void>}
     */
    q(this, Kn, /* @__PURE__ */ new Set());
    /**
     * If a fork is discarded, we need to destroy any effects that are no longer needed
     * @type {Set<(batch: Batch) => void>}
     */
    q(this, er, /* @__PURE__ */ new Set());
    /**
     * The number of async effects that are currently in flight
     */
    q(this, tr, 0);
    /**
     * Async effects that are currently in flight, _not_ inside a pending boundary
     * @type {Map<Effect, number>}
     */
    q(this, cn, /* @__PURE__ */ new Map());
    /**
     * A deferred that resolves when the batch is committed, used with `settled()`
     * TODO replace with Promise.withResolvers once supported widely enough
     * @type {{ promise: Promise<void>, resolve: (value?: any) => void, reject: (reason: unknown) => void } | null}
     */
    q(this, nr, null);
    /**
     * The root effects that need to be flushed
     * @type {Effect[]}
     */
    q(this, vt, []);
    /**
     * Effects created while this batch was active.
     * @type {Effect[]}
     */
    q(this, Fr, []);
    /**
     * Deferred effects (which run after async work has completed) that are DIRTY
     * @type {Set<Effect>}
     */
    q(this, dn, /* @__PURE__ */ new Set());
    /**
     * Deferred effects that are MAYBE_DIRTY
     * @type {Set<Effect>}
     */
    q(this, zt, /* @__PURE__ */ new Set());
    /**
     * A map of branches that still exist, but will be destroyed when this batch
     * is committed — we skip over these during `process`.
     * The value contains child effects that were dirty/maybe_dirty before being reset,
     * so they can be rescheduled if the branch survives.
     * @type {Map<Effect, { d: Effect[], m: Effect[] }>}
     */
    q(this, en, /* @__PURE__ */ new Map());
    /**
     * Inverse of #skipped_branches which we need to tell prior batches to unskip them when committing
     * @type {Set<Effect>}
     */
    q(this, rr, /* @__PURE__ */ new Set());
    yt(this, "is_fork", !1);
    q(this, Fn, !1);
    Hn === null ? Rs = Hn = this : (Y(Hn, Rn, this), Y(this, wn, Hn)), Hn = this;
  }
  /**
   * Add an effect to the #skipped_branches map and reset its children
   * @param {Effect} effect
   */
  skip_effect(t) {
    c(this, en).has(t) || c(this, en).set(t, { d: [], m: [] }), c(this, rr).delete(t);
  }
  /**
   * Remove an effect from the #skipped_branches map and reschedule
   * any tracked dirty/maybe_dirty child effects
   * @param {Effect} effect
   * @param {(e: Effect) => void} callback
   */
  unskip_effect(t, n = (r) => this.schedule(r)) {
    var r = c(this, en).get(t);
    if (r) {
      c(this, en).delete(t);
      for (var s of r.d)
        Pe(s, Ge), n(s);
      for (s of r.m)
        Pe(s, sn), n(s);
    }
    c(this, rr).add(t);
  }
  /**
   * Associate a change to a given source with the current
   * batch, noting its previous and current values
   * @param {Value} source
   * @param {any} value
   * @param {boolean} [is_derived]
   */
  capture(t, n, r = !1) {
    t.v !== Oe && !this.previous.has(t) && this.previous.set(t, t.v), t.f & Tn || (this.current.set(t, [n, r]), He == null || He.set(t, n)), this.is_fork || (t.v = n);
  }
  activate() {
    F = this;
  }
  deactivate() {
    F = null, He = null;
  }
  flush() {
    try {
      Fs = !0, F = this, re(this, ue, kr).call(this);
    } finally {
      xi = 0, Qs = null, Wn = null, ls = null, Fs = !1, F = null, He = null, Un.clear();
    }
  }
  discard() {
    var t;
    for (const n of c(this, er)) n(this);
    c(this, er).clear();
    for (const n of this.async_deriveds.values())
      n.reject(Tr);
    re(this, ue, Er).call(this), (t = c(this, nr)) == null || t.resolve();
  }
  /**
   * @param {Effect} effect
   */
  register_created_effect(t) {
    c(this, Fr).push(t);
  }
  /**
   * @param {boolean} blocking
   * @param {Effect} effect
   */
  increment(t, n) {
    if (Y(this, tr, c(this, tr) + 1), t) {
      let r = c(this, cn).get(n) ?? 0;
      c(this, cn).set(n, r + 1);
    }
  }
  /**
   * @param {boolean} blocking
   * @param {Effect} effect
   */
  decrement(t, n) {
    if (Y(this, tr, c(this, tr) - 1), t) {
      let r = c(this, cn).get(n) ?? 0;
      r === 1 ? c(this, cn).delete(n) : c(this, cn).set(n, r - 1);
    }
    c(this, Fn) || (Y(this, Fn, !0), kn(() => {
      Y(this, Fn, !1), this.linked && this.flush();
    }));
  }
  /**
   * @param {Set<Effect>} dirty_effects
   * @param {Set<Effect>} maybe_dirty_effects
   */
  transfer_effects(t, n) {
    for (const r of t)
      c(this, dn).add(r);
    for (const r of n)
      c(this, zt).add(r);
    t.clear(), n.clear();
  }
  /** @param {(batch: Batch) => void} fn */
  oncommit(t) {
    c(this, Kn).add(t);
  }
  /** @param {(batch: Batch) => void} fn */
  ondiscard(t) {
    c(this, er).add(t);
  }
  settled() {
    return (c(this, nr) ?? Y(this, nr, Hi())).promise;
  }
  static ensure() {
    if (F === null) {
      const t = F = new bs();
      !Fs && !Ir && kn(() => {
        c(t, Qn) || t.flush();
      });
    }
    return F;
  }
  apply() {
    {
      He = null;
      return;
    }
  }
  /**
   *
   * @param {Effect} effect
   */
  schedule(t) {
    var s;
    if (Qs = t, (s = t.b) != null && s.is_pending && t.f & (ir | Es | Gi) && !(t.f & fr)) {
      t.b.defer_effect(t);
      return;
    }
    for (var n = t; n.parent !== null; ) {
      n = n.parent;
      var r = n.f;
      if (Wn !== null && n === ee && (Q === null || !(Q.f & We)))
        return;
      if (r & (An | Vt)) {
        if (!(r & Re))
          return;
        n.f ^= Re;
      }
    }
    c(this, vt).push(n);
  }
};
Qn = new WeakMap(), wn = new WeakMap(), Rn = new WeakMap(), Kn = new WeakMap(), er = new WeakMap(), tr = new WeakMap(), cn = new WeakMap(), nr = new WeakMap(), vt = new WeakMap(), Fr = new WeakMap(), dn = new WeakMap(), zt = new WeakMap(), en = new WeakMap(), rr = new WeakMap(), Fn = new WeakMap(), ue = new WeakSet(), Ks = function() {
  if (this.is_fork) return !0;
  for (const r of c(this, cn).keys()) {
    for (var t = r, n = !1; t.parent !== null; ) {
      if (c(this, en).has(t)) {
        n = !0;
        break;
      }
      t = t.parent;
    }
    if (!n)
      return !0;
  }
  return !1;
}, kr = function() {
  var u, f, p, x;
  Y(this, Qn, !0), xi++ > 1e3 && (re(this, ue, Er).call(this), $o());
  for (const h of c(this, dn))
    c(this, zt).delete(h), Pe(h, Ge), this.schedule(h);
  for (const h of c(this, zt))
    Pe(h, sn), this.schedule(h);
  const t = c(this, vt);
  Y(this, vt, []), this.apply();
  var n = Wn = [], r = [], s = ls = [];
  for (const h of t)
    try {
      re(this, ue, ei).call(this, h, n, r);
    } catch (m) {
      throw ca(h), re(this, ue, Ks).call(this) || this.discard(), m;
    }
  if (F = null, s.length > 0) {
    var a = bs.ensure();
    for (const h of s)
      a.schedule(h);
  }
  if (Wn = null, ls = null, re(this, ue, Ks).call(this)) {
    re(this, ue, Yn).call(this, r), re(this, ue, Yn).call(this, n);
    for (const [h, m] of c(this, en))
      ua(h, m);
    s.length > 0 && /** @type {unknown} */
    re(u = F, ue, kr).call(u);
    return;
  }
  const o = re(this, ue, aa).call(this);
  if (o) {
    re(this, ue, Yn).call(this, r), re(this, ue, Yn).call(this, n), re(f = o, ue, oa).call(f, this);
    return;
  }
  c(this, dn).clear(), c(this, zt).clear();
  for (const h of c(this, Kn)) h(this);
  c(this, Kn).clear(), Pr = this, Si(r), Si(n), Pr = null, (p = c(this, nr)) == null || p.resolve();
  var l = (
    /** @type {Batch | null} */
    /** @type {unknown} */
    F
  );
  if (c(this, tr) === 0 && (c(this, vt).length === 0 || l !== null) && re(this, ue, Er).call(this), c(this, vt).length > 0)
    if (l !== null) {
      const h = l;
      c(h, vt).push(...c(this, vt).filter((m) => !c(h, vt).includes(m)));
    } else
      l = this;
  l !== null && re(x = l, ue, kr).call(x);
}, /**
 * Traverse the effect tree, executing effects or stashing
 * them for later execution as appropriate
 * @param {Effect} root
 * @param {Effect[]} effects
 * @param {Effect[]} render_effects
 */
ei = function(t, n, r) {
  t.f ^= Re;
  for (var s = t.first; s !== null; ) {
    var a = s.f, o = (a & (Vt | An)) !== 0, l = o && (a & Re) !== 0, u = l || (a & st) !== 0 || c(this, en).has(s);
    if (!u && s.fn !== null) {
      o ? s.f ^= Re : a & ir ? n.push(s) : qr(s) && (a & $t && c(this, zt).add(s), ur(s));
      var f = s.first;
      if (f !== null) {
        s = f;
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
}, aa = function() {
  for (var t = c(this, wn); t !== null; ) {
    if (!t.is_fork) {
      for (const [n, [, r]] of this.current)
        if (t.current.has(n) && !r)
          return t;
    }
    t = c(t, wn);
  }
  return null;
}, /**
 * @param {Batch} batch
 */
oa = function(t) {
  var r;
  for (const [s, a] of t.current)
    !this.previous.has(s) && t.previous.has(s) && this.previous.set(s, t.previous.get(s)), this.current.set(s, a);
  for (const [s, a] of t.async_deriveds) {
    const o = this.async_deriveds.get(s);
    o && a.promise.then(o.resolve).catch(o.reject);
  }
  t.async_deriveds.clear(), this.transfer_effects(c(t, dn), c(t, zt));
  const n = (s) => {
    var a = s.reactions;
    if (a !== null)
      for (const u of a) {
        var o = u.f;
        if (o & We)
          n(
            /** @type {Derived} */
            u
          );
        else {
          var l = (
            /** @type {Effect} */
            u
          );
          o & (Xn | $t) && !this.async_deriveds.has(l) && (c(this, zt).delete(l), Pe(l, Ge), this.schedule(l));
        }
      }
  };
  for (const s of this.current.keys())
    n(s);
  this.oncommit(() => t.discard()), re(r = t, ue, Er).call(r), F = this, re(this, ue, kr).call(this);
}, /**
 * @param {Effect[]} effects
 */
Yn = function(t) {
  for (var n = 0; n < t.length; n += 1)
    ta(t[n], c(this, dn), c(this, zt));
}, Uo = function() {
  var x;
  for (let h = Rs; h !== null; h = c(h, Rn)) {
    var t = h.id < this.id, n = [];
    for (const [m, [y, T]] of this.current) {
      if (h.current.has(m)) {
        var r = (
          /** @type {[any, boolean]} */
          h.current.get(m)[0]
        );
        if (t && y !== r)
          h.current.set(m, [y, T]);
        else
          continue;
      }
      n.push(m);
    }
    if (t)
      for (const [m, y] of this.async_deriveds) {
        const T = h.async_deriveds.get(m);
        T && y.promise.then(T.resolve).catch(T.reject);
      }
    var s = [...h.current.keys()].filter(
      (m) => !/** @type {[any, boolean]} */
      h.current.get(m)[1]
    );
    if (!(!c(h, Qn) || s.length === 0)) {
      var a = s.filter((m) => !this.current.has(m));
      if (a.length === 0)
        t && h.discard();
      else if (n.length > 0) {
        if (t)
          for (const m of c(this, rr))
            h.unskip_effect(m, (y) => {
              var T;
              y.f & ($t | Xn) ? h.schedule(y) : re(T = h, ue, Yn).call(T, [y]);
            });
        h.activate();
        var o = /* @__PURE__ */ new Set(), l = /* @__PURE__ */ new Map();
        for (var u of n)
          la(u, a, o, l);
        l = /* @__PURE__ */ new Map();
        var f = [...h.current].filter(([m, y]) => {
          const T = this.current.get(m);
          return T ? T[0] !== y[0] || T[1] !== y[1] : !0;
        }).map(([m]) => m);
        if (f.length > 0)
          for (const m of c(this, Fr))
            !(m.f & (Tt | st | fs)) && ci(m, f, l) && (m.f & (Xn | $t) ? (Pe(m, Ge), h.schedule(m)) : c(h, dn).add(m));
        if (c(h, vt).length > 0 && !c(h, Fn)) {
          h.apply();
          for (var p of c(h, vt))
            re(x = h, ue, ei).call(x, p, [], []);
          Y(h, vt, []);
        }
        h.deactivate();
      }
    }
  }
}, Er = function() {
  if (this.linked) {
    var t = c(this, wn), n = c(this, Rn);
    t === null ? Rs = n : Y(t, Rn, n), n === null ? Hn = t : Y(n, wn, t), this.linked = !1;
  }
};
let Bn = bs;
function qo(e) {
  var t = Ir;
  Ir = !0;
  try {
    for (var n; ; ) {
      if (To(), F === null)
        return (
          /** @type {T} */
          n
        );
      F.flush();
    }
  } finally {
    Ir = t;
  }
}
function $o() {
  try {
    no();
  } catch (e) {
    xn(e, Qs);
  }
}
let jt = null;
function Si(e) {
  var t = e.length;
  if (t !== 0) {
    for (var n = 0; n < t; ) {
      var r = e[n++];
      if (!(r.f & (Tt | st)) && qr(r) && (jt = /* @__PURE__ */ new Set(), ur(r), r.deps === null && r.first === null && r.nodes === null && r.teardown === null && r.ac === null && wa(r), (jt == null ? void 0 : jt.size) > 0)) {
        Un.clear();
        for (const s of jt) {
          if (s.f & (Tt | st)) continue;
          const a = [s];
          let o = s.parent;
          for (; o !== null; )
            jt.has(o) && (jt.delete(o), a.push(o)), o = o.parent;
          for (let l = a.length - 1; l >= 0; l--) {
            const u = a[l];
            u.f & (Tt | st) || ur(u);
          }
        }
        jt.clear();
      }
    }
    jt = null;
  }
}
function la(e, t, n, r) {
  if (!n.has(e) && (n.add(e), e.reactions !== null))
    for (const s of e.reactions) {
      const a = s.f;
      a & We ? la(
        /** @type {Derived} */
        s,
        t,
        n,
        r
      ) : a & (Xn | $t) && !(a & Ge) && ci(s, t, r) && (Pe(s, Ge), di(
        /** @type {Effect} */
        s
      ));
    }
}
function ci(e, t, n) {
  const r = n.get(e);
  if (r !== void 0) return r;
  if (e.deps !== null)
    for (const s of e.deps) {
      if (cs.call(t, s))
        return !0;
      if (s.f & We && ci(
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
function di(e) {
  F.schedule(e);
}
function ua(e, t) {
  if (!(e.f & Vt && e.f & Re)) {
    e.f & Ge ? t.d.push(e) : e.f & sn && t.m.push(e), Pe(e, Re);
    for (var n = e.first; n !== null; )
      ua(n, t), n = n.next;
  }
}
function ca(e) {
  Pe(e, Re);
  for (var t = e.first; t !== null; )
    ca(t), t = t.next;
}
let ps = /* @__PURE__ */ new Set();
const Un = /* @__PURE__ */ new Map();
let da = !1;
function Pn(e, t) {
  var n = {
    f: 0,
    // TODO ideally we could skip this altogether, but it causes type errors
    v: e,
    reactions: null,
    equals: Ji,
    rv: 0,
    wv: 0
  };
  return n;
}
// @__NO_SIDE_EFFECTS__
function P(e, t) {
  const n = Pn(e);
  return Sa(n), n;
}
// @__NO_SIDE_EFFECTS__
function Bo(e, t = !1, n = !0) {
  const r = Pn(e);
  return t || (r.equals = Xi), r;
}
function v(e, t, n = !1) {
  Q !== null && // since we are untracking the function inside `$inspect.with` we need to add this check
  // to ensure we error if state is set inside an inspect effect
  (!Bt || Q.f & fs) && Zi() && Q.f & (We | $t | Xn | fs) && (rn === null || !rn.has(e)) && ao();
  let r = n ? rt(t) : t;
  return lr(e, r, ls);
}
function lr(e, t, n = null) {
  if (!e.equals(t)) {
    Un.set(e, pn ? t : e.v);
    var r = Bn.ensure();
    if (r.capture(e, t), e.f & We) {
      const s = (
        /** @type {Derived} */
        e
      );
      e.f & Ge && ui(s), He === null && li(s);
    }
    e.wv = ka(), fa(e, Ge, n), ee !== null && ee.f & Re && !(ee.f & (Vt | An)) && (Lt === null ? nl([e]) : Lt.push(e)), !r.is_fork && ps.size > 0 && !da && Vo();
  }
  return t;
}
function Vo() {
  da = !1;
  for (const e of ps) {
    e.f & Re && Pe(e, sn);
    let t;
    try {
      t = qr(e);
    } catch {
      t = !0;
    }
    t && ur(e);
  }
  ps.clear();
}
function Ti(e, t = 1) {
  var n = i(e), r = t === 1 ? n++ : n--;
  return v(e, n), r;
}
function En(e) {
  v(e, e.v + 1);
}
function fa(e, t, n) {
  var r = e.reactions;
  if (r !== null)
    for (var s = r.length, a = 0; a < s; a++) {
      var o = r[a], l = o.f, u = (l & Ge) === 0;
      if (u && Pe(o, t), l & fs)
        ps.add(
          /** @type {Effect} */
          o
        );
      else if (l & We) {
        var f = (
          /** @type {Derived} */
          o
        );
        He == null || He.delete(f), l & $n || (l & Ot && (ee === null || !(ee.f & vs)) && (o.f |= $n), fa(f, sn, n));
      } else if (u) {
        var p = (
          /** @type {Effect} */
          o
        );
        l & $t && jt !== null && jt.add(p), n !== null ? n.push(p) : di(p);
      }
    }
}
function rt(e) {
  if (typeof e != "object" || e === null || zn in e)
    return e;
  const t = Vi(e);
  if (t !== Ba && t !== Va)
    return e;
  var n = /* @__PURE__ */ new Map(), r = oi(e), s = /* @__PURE__ */ P(0), a = hn, o = (l) => {
    if (hn === a)
      return l();
    var u = Q, f = hn;
    Rt(null), Pi(a);
    var p = l();
    return Rt(u), Pi(f), p;
  };
  return r && n.set("length", /* @__PURE__ */ P(
    /** @type {any[]} */
    e.length
  )), new Proxy(
    /** @type {any} */
    e,
    {
      defineProperty(l, u, f) {
        (!("value" in f) || f.configurable === !1 || f.enumerable === !1 || f.writable === !1) && so();
        var p = n.get(u);
        return p === void 0 ? o(() => {
          var x = /* @__PURE__ */ P(f.value);
          return n.set(u, x), x;
        }) : v(p, f.value, !0), !0;
      },
      deleteProperty(l, u) {
        var f = n.get(u);
        if (f === void 0) {
          if (u in l) {
            const p = o(() => /* @__PURE__ */ P(Oe));
            n.set(u, p), En(s);
          }
        } else
          v(f, Oe), En(s);
        return !0;
      },
      get(l, u, f) {
        var m;
        if (u === zn)
          return e;
        var p = n.get(u), x = u in l;
        if (p === void 0 && (!x || (m = Jn(l, u)) != null && m.writable) && (p = o(() => {
          var y = rt(x ? l[u] : Oe), T = /* @__PURE__ */ P(y);
          return T;
        }), n.set(u, p)), p !== void 0) {
          var h = i(p);
          return h === Oe ? void 0 : h;
        }
        return Reflect.get(l, u, f);
      },
      getOwnPropertyDescriptor(l, u) {
        var f = Reflect.getOwnPropertyDescriptor(l, u);
        if (f && "value" in f) {
          var p = n.get(u);
          p && (f.value = i(p));
        } else if (f === void 0) {
          var x = n.get(u), h = x == null ? void 0 : x.v;
          if (x !== void 0 && h !== Oe)
            return {
              enumerable: !0,
              configurable: !0,
              value: h,
              writable: !0
            };
        }
        return f;
      },
      has(l, u) {
        var h;
        if (u === zn)
          return !0;
        var f = n.get(u), p = f !== void 0 && f.v !== Oe || Reflect.has(l, u);
        if (f !== void 0 || ee !== null && (!p || (h = Jn(l, u)) != null && h.writable)) {
          f === void 0 && (f = o(() => {
            var m = p ? rt(l[u]) : Oe, y = /* @__PURE__ */ P(m);
            return y;
          }), n.set(u, f));
          var x = i(f);
          if (x === Oe)
            return !1;
        }
        return p;
      },
      set(l, u, f, p) {
        var $;
        var x = n.get(u), h = u in l;
        if (r && u === "length")
          for (var m = f; m < /** @type {Source<number>} */
          x.v; m += 1) {
            var y = n.get(m + "");
            y !== void 0 ? v(y, Oe) : m in l && (y = o(() => /* @__PURE__ */ P(Oe)), n.set(m + "", y));
          }
        if (x === void 0)
          (!h || ($ = Jn(l, u)) != null && $.writable) && (x = o(() => /* @__PURE__ */ P(void 0)), v(x, rt(f)), n.set(u, x));
        else {
          h = x.v !== Oe;
          var T = o(() => rt(f));
          v(x, T);
        }
        var w = Reflect.getOwnPropertyDescriptor(l, u);
        if (w != null && w.set && w.set.call(p, f), !h) {
          if (r && typeof u == "string") {
            var M = (
              /** @type {Source<number>} */
              n.get("length")
            ), J = Number(u);
            Number.isInteger(J) && J >= M.v && v(M, J + 1);
          }
          En(s);
        }
        return !0;
      },
      ownKeys(l) {
        i(s);
        var u = Reflect.ownKeys(l).filter((x) => {
          var h = n.get(x);
          return h === void 0 || h.v !== Oe;
        });
        for (var [f, p] of n)
          p.v !== Oe && !(f in l) && u.push(f);
        return u;
      },
      setPrototypeOf() {
        io();
      }
    }
  );
}
function ki(e) {
  try {
    if (e !== null && typeof e == "object" && zn in e)
      return e[zn];
  } catch {
  }
  return e;
}
function Ho(e, t) {
  return Object.is(ki(e), ki(t));
}
var _s, va, ha, pa;
function Yo() {
  if (_s === void 0) {
    _s = window, va = /Firefox/.test(navigator.userAgent);
    var e = Element.prototype, t = Node.prototype, n = Text.prototype;
    ha = Jn(t, "firstChild").get, pa = Jn(t, "nextSibling").get, bi(e) && (e[Gs] = void 0, e[ss] = null, e[Ws] = void 0, e.__e = void 0), bi(n) && (n[Sr] = void 0);
  }
}
function fn(e = "") {
  return document.createTextNode(e);
}
// @__NO_SIDE_EFFECTS__
function gs(e) {
  return (
    /** @type {TemplateNode | null} */
    ha.call(e)
  );
}
// @__NO_SIDE_EFFECTS__
function Ur(e) {
  return (
    /** @type {TemplateNode | null} */
    pa.call(e)
  );
}
function d(e, t) {
  return /* @__PURE__ */ gs(e);
}
function vn(e, t = !1) {
  {
    var n = /* @__PURE__ */ gs(e);
    return n instanceof Comment && n.data === "" ? /* @__PURE__ */ Ur(n) : n;
  }
}
function g(e, t = 1, n = !1) {
  let r = e;
  for (; t--; )
    r = /** @type {TemplateNode} */
    /* @__PURE__ */ Ur(r);
  return r;
}
function Go(e) {
  e.textContent = "";
}
function _a() {
  return !1;
}
function Wo(e, t, n) {
  return (
    /** @type {T extends keyof HTMLElementTagNameMap ? HTMLElementTagNameMap[T] : Element} */
    n ? document.createElement(e, { is: n }) : document.createElement(e)
  );
}
let Ei = !1;
function Jo() {
  Ei || (Ei = !0, document.addEventListener(
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
            (t = n[is]) == null || t.call(n);
      });
    },
    // In the capture phase to guarantee we get noticed of it (no possibility of stopPropagation)
    { capture: !0 }
  ));
}
function Ps(e) {
  var t = Q, n = ee;
  Rt(null), an(null);
  try {
    return e();
  } finally {
    Rt(t), an(n);
  }
}
function fi(e, t, n, r = n) {
  e.addEventListener(t, () => Ps(n));
  const s = (
    /** @type {any} */
    e[is]
  );
  s ? e[is] = () => {
    s(), r(!0);
  } : e[is] = () => r(!0), Jo();
}
function Xo(e) {
  ee === null && (Q === null && to(), eo()), pn && Ka();
}
function Zo(e, t) {
  var n = t.last;
  n === null ? t.last = t.first = e : (n.next = e, e.prev = n, t.last = e);
}
function _n(e, t) {
  var n = ee;
  n !== null && n.f & st && (e |= st);
  var r = {
    ctx: it,
    deps: null,
    nodes: null,
    f: e | Ge | Ot,
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
  F == null || F.register_created_effect(r);
  var s = r;
  if (e & ir)
    Wn !== null ? Wn.push(r) : Bn.ensure().schedule(r);
  else if (t !== null) {
    try {
      ur(r);
    } catch (o) {
      throw pt(r), o;
    }
    s.deps === null && s.teardown === null && s.nodes === null && s.first === s.last && // either `null`, or a singular child
    !(s.f & vr) && (s = s.first, e & $t && e & ar && s !== null && (s.f |= ar));
  }
  if (s !== null && (s.parent = n, n !== null && Zo(s, n), Q !== null && Q.f & We && !(e & An))) {
    var a = (
      /** @type {Derived} */
      Q
    );
    (a.effects ?? (a.effects = [])).push(s);
  }
  return r;
}
function vi() {
  return Q !== null && !Bt;
}
function hi(e) {
  const t = _n(Es, null);
  return Pe(t, Re), t.teardown = e, t;
}
function Vn(e) {
  Xo();
  var t = (
    /** @type {Effect} */
    ee.f
  ), n = !Q && (t & Vt) !== 0 && it !== null && !it.i;
  if (n) {
    var r = (
      /** @type {ComponentContext} */
      it
    );
    (r.e ?? (r.e = [])).push(e);
  } else
    return ga(e);
}
function ga(e) {
  return _n(ir | Ga, e);
}
function Qo(e) {
  Bn.ensure();
  const t = _n(An | vr, e);
  return (n = {}) => new Promise((r) => {
    n.outro ? qn(t, () => {
      pt(t), r(void 0);
    }) : (pt(t), r(void 0));
  });
}
function ma(e) {
  return _n(ir, e);
}
function Ko(e) {
  return _n(Xn | vr, e);
}
function Is(e, t = 0) {
  return _n(Es | t, e);
}
function R(e, t = [], n = [], r = []) {
  No(r, t, n, (s) => {
    _n(Es, () => {
      e(...s.map(i));
    });
  });
}
function pi(e, t = 0) {
  var n = _n($t | t, e);
  return n;
}
function Nt(e) {
  return _n(Vt | vr, e);
}
function ya(e) {
  var t = e.teardown;
  if (t !== null) {
    const n = pn, r = Q;
    Ai(!0), Rt(null);
    try {
      t.call(null);
    } finally {
      Ai(n), Rt(r);
    }
  }
}
function _i(e, t = !1) {
  var n = e.first;
  for (e.first = e.last = null; n !== null; ) {
    const s = n.ac;
    s !== null && Ps(() => {
      s.abort(As);
    });
    var r = n.next;
    n.f & An ? n.parent = null : pt(n, t), n = r;
  }
}
function el(e) {
  for (var t = e.first; t !== null; ) {
    var n = t.next;
    t.f & Vt || pt(t), t = n;
  }
}
function pt(e, t = !0) {
  var n = !1;
  (t || e.f & Ya) && e.nodes !== null && e.nodes.end !== null && (tl(
    e.nodes.start,
    /** @type {TemplateNode} */
    e.nodes.end
  ), n = !0), e.f |= Ys, _i(e, t && !n), Cr(e, 0);
  var r = e.nodes && e.nodes.t;
  if (r !== null)
    for (const a of r)
      a.stop();
  ya(e), e.f ^= Ys, e.f |= Tt;
  var s = e.parent;
  s !== null && s.first !== null && wa(e), e.next = e.prev = e.teardown = e.ctx = e.deps = e.fn = e.nodes = e.ac = e.b = null;
}
function tl(e, t) {
  for (; e !== null; ) {
    var n = e === t ? null : /* @__PURE__ */ Ur(e);
    e.remove(), e = n;
  }
}
function wa(e) {
  var t = e.parent, n = e.prev, r = e.next;
  n !== null && (n.next = r), r !== null && (r.prev = n), t !== null && (t.first === e && (t.first = r), t.last === e && (t.last = n));
}
function qn(e, t, n = !0) {
  var r = [];
  ba(e, r, !0);
  var s = () => {
    n && pt(e), t && t();
  }, a = r.length;
  if (a > 0) {
    var o = () => --a || s();
    for (var l of r)
      l.out(o);
  } else
    s();
}
function ba(e, t, n) {
  if (!(e.f & st)) {
    e.f ^= st;
    var r = e.nodes && e.nodes.t;
    if (r !== null)
      for (const l of r)
        (l.is_global || n) && t.push(l);
    for (var s = e.first; s !== null; ) {
      var a = s.next;
      if (!(s.f & An)) {
        var o = (s.f & ar) !== 0 || // If this is a branch effect without a block effect parent,
        // it means the parent block effect was pruned. In that case,
        // transparency information was transferred to the branch effect.
        (s.f & Vt) !== 0 && (e.f & $t) !== 0;
        ba(s, t, o ? n : !1);
      }
      s = a;
    }
  }
}
function ms(e) {
  xa(e, !0);
}
function xa(e, t) {
  if (e.f & st) {
    e.f ^= st, e.f & Re || (Pe(e, Ge), Bn.ensure().schedule(e));
    for (var n = e.first; n !== null; ) {
      var r = n.next, s = (n.f & ar) !== 0 || (n.f & Vt) !== 0;
      xa(n, s ? t : !1), n = r;
    }
    var a = e.nodes && e.nodes.t;
    if (a !== null)
      for (const o of a)
        (o.is_global || t) && o.in();
  }
}
function gi(e, t) {
  if (e.nodes)
    for (var n = e.nodes.start, r = e.nodes.end; n !== null; ) {
      var s = n === r ? null : /* @__PURE__ */ Ur(n);
      t.append(n), n = s;
    }
}
let us = !1, pn = !1;
function Ai(e) {
  pn = e;
}
let Q = null, Bt = !1;
function Rt(e) {
  Q = e;
}
let ee = null;
function an(e) {
  ee = e;
}
let rn = null;
function Sa(e) {
  Q !== null && (rn ?? (rn = /* @__PURE__ */ new Set())).add(e);
}
let ht = null, wt = 0, Lt = null;
function nl(e) {
  Lt = e;
}
let Ta = 1, Cn = 0, hn = Cn;
function Pi(e) {
  hn = e;
}
function ka() {
  return ++Ta;
}
function qr(e) {
  var t = e.f;
  if (t & Ge)
    return !0;
  if (t & We && (e.f &= ~$n), t & sn) {
    for (var n = (
      /** @type {Value[]} */
      e.deps
    ), r = n.length, s = 0; s < r; s++) {
      var a = n[s];
      if (qr(
        /** @type {Derived} */
        a
      ) && sa(
        /** @type {Derived} */
        a
      ), a.wv > e.wv)
        return !0;
    }
    t & Ot && // During time traveling we don't want to reset the status so that
    // traversal of the graph in the other batches still happens
    He === null && Pe(e, Re);
  }
  return !1;
}
function Ea(e, t, n = !0) {
  var r = e.reactions;
  if (r !== null && !(rn !== null && rn.has(e)))
    for (var s = 0; s < r.length; s++) {
      var a = r[s];
      a.f & We ? Ea(
        /** @type {Derived} */
        a,
        t,
        !1
      ) : t === a && (n ? Pe(a, Ge) : a.f & Re && Pe(a, sn), di(
        /** @type {Effect} */
        a
      ));
    }
}
function Aa(e) {
  var T;
  var t = ht, n = wt, r = Lt, s = Q, a = rn, o = it, l = Bt, u = hn, f = e.f;
  ht = /** @type {null | Value[]} */
  null, wt = 0, Lt = null, Q = f & (Vt | An) ? null : e, rn = null, or(e.ctx), Bt = !1, hn = ++Cn, e.ac !== null && (Ps(() => {
    e.ac.abort(As);
  }), e.ac = null);
  try {
    e.f |= vs;
    var p = (
      /** @type {Function} */
      e.fn
    ), x = p();
    e.f |= fr;
    var h = e.deps, m = F == null ? void 0 : F.is_fork;
    if (ht !== null) {
      var y;
      if (m || Cr(e, wt), h !== null && wt > 0)
        for (h.length = wt + ht.length, y = 0; y < ht.length; y++)
          h[wt + y] = ht[y];
      else
        e.deps = h = ht;
      if (vi() && e.f & Ot)
        for (y = wt; y < h.length; y++)
          ((T = h[y]).reactions ?? (T.reactions = [])).push(e);
    } else !m && h !== null && wt < h.length && (Cr(e, wt), h.length = wt);
    if (Zi() && Lt !== null && !Bt && h !== null && !(e.f & (We | sn | Ge)))
      for (y = 0; y < /** @type {Source[]} */
      Lt.length; y++)
        Ea(
          Lt[y],
          /** @type {Effect} */
          e
        );
    if (s !== null && s !== e) {
      if (Cn++, s.deps !== null)
        for (let w = 0; w < n; w += 1)
          s.deps[w].rv = Cn;
      if (t !== null)
        for (const w of t)
          w.rv = Cn;
      Lt !== null && (r === null ? r = Lt : r.push(.../** @type {Source[]} */
      Lt));
    }
    return e.f & Tn && (e.f ^= Tn), x;
  } catch (w) {
    return Ki(w);
  } finally {
    e.f ^= vs, ht = t, wt = n, Lt = r, Q = s, rn = a, or(o), Bt = l, hn = u;
  }
}
function rl(e, t) {
  let n = t.reactions;
  if (n !== null) {
    var r = Ua.call(n, e);
    if (r !== -1) {
      var s = n.length - 1;
      s === 0 ? n = t.reactions = null : (n[r] = n[s], n.pop());
    }
  }
  if (n === null && t.f & We && // Destroying a child effect while updating a parent effect can cause a dependency to appear
  // to be unused, when in fact it is used by the currently-updating parent. Checking `new_deps`
  // allows us to skip the expensive work of disconnecting and immediately reconnecting it
  (ht === null || !cs.call(ht, t))) {
    var a = (
      /** @type {Derived} */
      t
    );
    a.f & Ot && (a.f ^= Ot, a.f &= ~$n), a.v !== Oe && li(a), jo(a), Cr(a, 0);
  }
}
function Cr(e, t) {
  var n = e.deps;
  if (n !== null)
    for (var r = t; r < n.length; r++)
      rl(e, n[r]);
}
function ur(e) {
  var t = e.f;
  if (!(t & Tt)) {
    Pe(e, Re);
    var n = ee, r = us;
    ee = e, us = !0;
    try {
      t & ($t | Gi) ? el(e) : _i(e), ya(e);
      var s = Aa(e);
      e.teardown = typeof s == "function" ? s : null, e.wv = Ta;
      var a;
    } finally {
      us = r, ee = n;
    }
  }
}
async function sl() {
  await Promise.resolve(), qo();
}
function i(e) {
  var t = e.f, n = (t & We) !== 0;
  if (Q !== null && !Bt) {
    var r = ee !== null && (ee.f & Tt) !== 0;
    if (!r && (rn === null || !rn.has(e))) {
      var s = Q.deps;
      if (Q.f & vs)
        e.rv < Cn && (e.rv = Cn, ht === null && s !== null && s[wt] === e ? wt++ : ht === null ? ht = [e] : ht.push(e));
      else {
        Q.deps ?? (Q.deps = []), cs.call(Q.deps, e) || Q.deps.push(e);
        var a = e.reactions;
        a === null ? e.reactions = [Q] : cs.call(a, Q) || a.push(Q);
      }
    }
  }
  if (pn && Un.has(e))
    return Un.get(e);
  if (n) {
    var o = (
      /** @type {Derived} */
      e
    );
    if (pn) {
      var l = o.v;
      return (!(o.f & Re) && o.reactions !== null || Ia(o)) && (l = ui(o)), Un.set(o, l), l;
    }
    var u = (o.f & Ot) === 0 && !Bt && Q !== null && (us || (Q.f & Ot) !== 0), f = (o.f & fr) === 0;
    qr(o) && (u && (o.f |= Ot), sa(o)), u && !f && (ia(o), Pa(o));
  }
  if (He != null && He.has(e))
    return He.get(e);
  if (e.f & Tn)
    throw e.v;
  return e.v;
}
function Pa(e) {
  if (e.f |= Ot, e.deps !== null)
    for (const t of e.deps)
      (t.reactions ?? (t.reactions = [])).push(e), t.f & We && !(t.f & Ot) && (ia(
        /** @type {Derived} */
        t
      ), Pa(
        /** @type {Derived} */
        t
      ));
}
function Ia(e) {
  if (e.v === Oe) return !0;
  if (e.deps === null) return !1;
  for (const t of e.deps)
    if (Un.has(t) || t.f & We && Ia(
      /** @type {Derived} */
      t
    ))
      return !0;
  return !1;
}
function gn(e) {
  var t = Bt;
  try {
    return Bt = !0, e();
  } finally {
    Bt = t;
  }
}
const il = ["touchstart", "touchmove"];
function al(e) {
  return il.includes(e);
}
const Dn = Symbol("events"), La = /* @__PURE__ */ new Set(), ti = /* @__PURE__ */ new Set();
function ol(e, t, n, r = {}) {
  function s(a) {
    if (r.capture || ni.call(t, a), !a.cancelBubble)
      return Ps(() => n == null ? void 0 : n.call(this, a));
  }
  return e.startsWith("pointer") || e.startsWith("touch") || e === "wheel" ? kn(() => {
    t.addEventListener(e, s, r);
  }) : t.addEventListener(e, s, r), s;
}
function Ma(e, t, n, r, s) {
  var a = { capture: r, passive: s }, o = ol(e, t, n, a);
  (t === document.body || // @ts-ignore
  t === window || // @ts-ignore
  t === document || // Firefox has quirky behavior, it can happen that we still get "canplay" events when the element is already removed
  t instanceof HTMLMediaElement) && hi(() => {
    t.removeEventListener(e, o, a);
  });
}
function N(e, t, n) {
  (t[Dn] ?? (t[Dn] = {}))[e] = n;
}
function $r(e) {
  for (var t = 0; t < e.length; t++)
    La.add(e[t]);
  for (var n of ti)
    n(e);
}
let Ii = null;
function ni(e) {
  var T, w;
  var t = this, n = (
    /** @type {Node} */
    t.ownerDocument
  ), r = e.type, s = ((T = e.composedPath) == null ? void 0 : T.call(e)) || [], a = (
    /** @type {null | Element} */
    s[0] || e.target
  );
  Ii = e;
  var o = 0, l = Ii === e && e[Dn];
  if (l) {
    var u = s.indexOf(l);
    if (u !== -1 && (t === document || t === /** @type {any} */
    window)) {
      e[Dn] = t;
      return;
    }
    var f = s.indexOf(t);
    if (f === -1)
      return;
    u <= f && (o = u);
  }
  if (a = /** @type {Element} */
  s[o] || e.target, a !== t) {
    qa(e, "currentTarget", {
      configurable: !0,
      get() {
        return a || n;
      }
    });
    var p = Q, x = ee;
    Rt(null), an(null);
    try {
      for (var h, m = []; a !== null && a !== t; ) {
        try {
          var y = (w = a[Dn]) == null ? void 0 : w[r];
          y != null && (!/** @type {any} */
          a.disabled || // DOM could've been updated already by the time this is reached, so we check this as well
          // -> the target could not have been disabled because it emits the event in the first place
          e.target === a) && y.call(a, e);
        } catch (M) {
          h ? m.push(M) : h = M;
        }
        if (e.cancelBubble) break;
        o++, a = o < s.length ? (
          /** @type {Element} */
          s[o]
        ) : null;
      }
      if (h) {
        for (let M of m)
          queueMicrotask(() => {
            throw M;
          });
        throw h;
      }
    } finally {
      e[Dn] = t, delete e.currentTarget, Rt(p), an(x);
    }
  }
}
var $i;
const js = (
  // We gotta write it like this because after downleveling the pure comment may end up in the wrong location
  (($i = globalThis == null ? void 0 : globalThis.window) == null ? void 0 : $i.trustedTypes) && /* @__PURE__ */ globalThis.window.trustedTypes.createPolicy("svelte-trusted-html", {
    /** @param {string} html */
    createHTML: (e) => e
  })
);
function ll(e) {
  return (
    /** @type {string} */
    (js == null ? void 0 : js.createHTML(e)) ?? e
  );
}
function ul(e) {
  var t = Wo("template");
  return t.innerHTML = ll(e.replaceAll("<!>", "<!---->")), t.content;
}
function ys(e, t) {
  var n = (
    /** @type {Effect} */
    ee
  );
  n.nodes === null && (n.nodes = { start: e, end: t, a: null, t: null });
}
// @__NO_SIDE_EFFECTS__
function E(e, t) {
  var n = (t & go) !== 0, r = (t & mo) !== 0, s, a = !e.startsWith("<!>");
  return () => {
    s === void 0 && (s = ul(a ? e : "<!>" + e), n || (s = /** @type {TemplateNode} */
    /* @__PURE__ */ gs(s)));
    var o = (
      /** @type {TemplateNode} */
      r || va ? document.importNode(s, !0) : s.cloneNode(!0)
    );
    if (n) {
      var l = (
        /** @type {TemplateNode} */
        /* @__PURE__ */ gs(o)
      ), u = (
        /** @type {TemplateNode} */
        o.lastChild
      );
      ys(l, u);
    } else
      ys(o, o);
    return o;
  };
}
function cl(e = "") {
  {
    var t = fn(e + "");
    return ys(t, t), t;
  }
}
function cr() {
  var e = document.createDocumentFragment(), t = document.createComment(""), n = fn();
  return e.append(t, n), ys(t, n), e;
}
function b(e, t) {
  e !== null && e.before(
    /** @type {Node} */
    t
  );
}
function V(e, t) {
  var n = t == null ? "" : typeof t == "object" ? `${t}` : t;
  n !== /** @type {any} */
  (e[Sr] ?? (e[Sr] = e.nodeValue)) && (e[Sr] = n, e.nodeValue = `${n}`);
}
function dl(e, t) {
  return fl(e, t);
}
const rs = /* @__PURE__ */ new Map();
function fl(e, { target: t, anchor: n, props: r = {}, events: s, context: a, intro: o = !0, transformError: l }) {
  Yo();
  var u = void 0, f = Qo(() => {
    var p = n ?? t.appendChild(fn());
    Io(
      /** @type {TemplateNode} */
      p,
      {
        pending: () => {
        }
      },
      (m) => {
        hr({});
        var y = (
          /** @type {ComponentContext} */
          it
        );
        a && (y.c = a), s && (r.$$events = s), u = e(m, r) || {}, pr();
      },
      l
    );
    var x = /* @__PURE__ */ new Set(), h = (m) => {
      for (var y = 0; y < m.length; y++) {
        var T = m[y];
        if (!x.has(T)) {
          x.add(T);
          var w = al(T);
          for (const $ of [t, document]) {
            var M = rs.get($);
            M === void 0 && (M = /* @__PURE__ */ new Map(), rs.set($, M));
            var J = M.get(T);
            J === void 0 ? ($.addEventListener(T, ni, { passive: w }), M.set(T, 1)) : M.set(T, J + 1);
          }
        }
      }
    };
    return h(ks(La)), ti.add(h), () => {
      var w;
      for (var m of x)
        for (const M of [t, document]) {
          var y = (
            /** @type {Map<string, number>} */
            rs.get(M)
          ), T = (
            /** @type {number} */
            y.get(m)
          );
          --T == 0 ? (M.removeEventListener(m, ni), y.delete(m), y.size === 0 && rs.delete(M)) : y.set(m, T);
        }
      ti.delete(h), p !== n && ((w = p.parentNode) == null || w.removeChild(p));
    };
  });
  return vl.set(u, f), u;
}
let vl = /* @__PURE__ */ new WeakMap();
var Ut, tn, xt, jn, jr, zr, xs;
class hl {
  /**
   * @param {TemplateNode} anchor
   * @param {boolean} transition
   */
  constructor(t, n = !0) {
    /** @type {TemplateNode} */
    yt(this, "anchor");
    /** @type {Map<Batch, Key>} */
    q(this, Ut, /* @__PURE__ */ new Map());
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
    q(this, tn, /* @__PURE__ */ new Map());
    /**
     * Similar to #onscreen with respect to the keys, but contains branches that are not yet
     * in the DOM, because their insertion is deferred.
     * @type {Map<Key, Branch>}
     */
    q(this, xt, /* @__PURE__ */ new Map());
    /**
     * Keys of effects that are currently outroing
     * @type {Set<Key>}
     */
    q(this, jn, /* @__PURE__ */ new Set());
    /**
     * Whether to pause (i.e. outro) on change, or destroy immediately.
     * This is necessary for `<svelte:element>`
     */
    q(this, jr, !0);
    /**
     * @param {Batch} batch
     */
    q(this, zr, (t) => {
      if (c(this, Ut).has(t)) {
        var n = (
          /** @type {Key} */
          c(this, Ut).get(t)
        ), r = c(this, tn).get(n);
        if (r)
          ms(r), c(this, jn).delete(n);
        else {
          var s = c(this, xt).get(n);
          s && (ms(s.effect), c(this, tn).set(n, s.effect), c(this, xt).delete(n), s.fragment.lastChild.remove(), this.anchor.before(s.fragment), r = s.effect);
        }
        for (const [a, o] of c(this, Ut)) {
          if (c(this, Ut).delete(a), a === t)
            break;
          const l = c(this, xt).get(o);
          l && (pt(l.effect), c(this, xt).delete(o));
        }
        for (const [a, o] of c(this, tn)) {
          if (a === n || c(this, jn).has(a)) continue;
          const l = () => {
            if (Array.from(c(this, Ut).values()).includes(a)) {
              var f = document.createDocumentFragment();
              gi(o, f), f.append(fn()), c(this, xt).set(a, { effect: o, fragment: f });
            } else
              pt(o);
            c(this, jn).delete(a), c(this, tn).delete(a);
          };
          c(this, jr) || !r ? (c(this, jn).add(a), qn(o, l, !1)) : l();
        }
      }
    });
    /**
     * @param {Batch} batch
     */
    q(this, xs, (t) => {
      c(this, Ut).delete(t);
      const n = Array.from(c(this, Ut).values());
      for (const [r, s] of c(this, xt))
        n.includes(r) || (pt(s.effect), c(this, xt).delete(r));
    });
    this.anchor = t, Y(this, jr, n);
  }
  /**
   *
   * @param {any} key
   * @param {null | ((target: TemplateNode) => void)} fn
   */
  ensure(t, n) {
    var r = (
      /** @type {Batch} */
      F
    ), s = _a();
    if (n && !c(this, tn).has(t) && !c(this, xt).has(t))
      if (s) {
        var a = document.createDocumentFragment(), o = fn();
        a.append(o), c(this, xt).set(t, {
          effect: Nt(() => n(o)),
          fragment: a
        });
      } else
        c(this, tn).set(
          t,
          Nt(() => n(this.anchor))
        );
    if (c(this, Ut).set(r, t), s) {
      for (const [l, u] of c(this, tn))
        l === t ? r.unskip_effect(u) : r.skip_effect(u);
      for (const [l, u] of c(this, xt))
        l === t ? r.unskip_effect(u.effect) : r.skip_effect(u.effect);
      r.oncommit(c(this, zr)), r.ondiscard(c(this, xs));
    } else
      c(this, zr).call(this, r);
  }
}
Ut = new WeakMap(), tn = new WeakMap(), xt = new WeakMap(), jn = new WeakMap(), jr = new WeakMap(), zr = new WeakMap(), xs = new WeakMap();
function W(e, t, n = !1) {
  var r = new hl(e), s = n ? ar : 0;
  function a(o, l) {
    r.ensure(o, l);
  }
  pi(() => {
    var o = !1;
    t((l, u = 0) => {
      o = !0, a(u, l);
    }), o || a(-1, null);
  }, s);
}
function pl(e, t, n) {
  for (var r = [], s = t.length, a, o = t.length, l = 0; l < s; l++) {
    let x = t[l];
    qn(
      x,
      () => {
        if (a) {
          if (a.pending.delete(x), a.done.add(x), a.pending.size === 0) {
            var h = (
              /** @type {Set<EachOutroGroup>} */
              e.outrogroups
            );
            ri(e, ks(a.done)), h.delete(a), h.size === 0 && (e.outrogroups = null);
          }
        } else
          o -= 1;
      },
      !1
    );
  }
  if (o === 0) {
    var u = r.length === 0 && n !== null;
    if (u) {
      var f = (
        /** @type {Element} */
        n
      ), p = (
        /** @type {Element} */
        f.parentNode
      );
      Go(p), p.append(f), e.items.clear();
    }
    ri(e, t, !u);
  } else
    a = {
      pending: new Set(t),
      done: /* @__PURE__ */ new Set()
    }, (e.outrogroups ?? (e.outrogroups = /* @__PURE__ */ new Set())).add(a);
}
function ri(e, t, n = !0) {
  var r;
  if (e.pending.size > 0) {
    r = /* @__PURE__ */ new Set();
    for (const o of e.pending.values())
      for (const l of o)
        r.add(
          /** @type {EachItem} */
          e.items.get(l).e
        );
  }
  for (var s = 0; s < t.length; s++) {
    var a = t[s];
    if (r != null && r.has(a)) {
      a.f |= nn;
      const o = document.createDocumentFragment();
      gi(a, o);
    } else
      pt(t[s], n);
  }
}
var Li;
function Ye(e, t, n, r, s, a = null) {
  var o = e, l = /* @__PURE__ */ new Map(), u = (t & Wi) !== 0;
  if (u) {
    var f = (
      /** @type {Element} */
      e
    );
    o = f.appendChild(fn());
  }
  var p = null, x = /* @__PURE__ */ ra(() => {
    var $ = n();
    return (
      /** @type {V[]} */
      oi($) ? $ : $ == null ? [] : ks($)
    );
  }), h, m = /* @__PURE__ */ new Map(), y = !0;
  function T($) {
    J.effect.f & Tt || (J.pending.delete($), J.fallback = p, _l(J, h, o, t, r), p !== null && (h.length === 0 ? p.f & nn ? (p.f ^= nn, Ar(p, null, o)) : ms(p) : qn(p, () => {
      p = null;
    })));
  }
  function w($) {
    J.pending.delete($);
  }
  var M = pi(() => {
    h = /** @type {V[]} */
    i(x);
    for (var $ = h.length, se = /* @__PURE__ */ new Set(), X = (
      /** @type {Batch} */
      F
    ), S = _a(), k = 0; k < $; k += 1) {
      var H = h[k], O = r(H, k), G = y ? null : l.get(O);
      G ? (G.v && lr(G.v, H), G.i && lr(G.i, k), S && X.unskip_effect(G.e)) : (G = gl(
        l,
        y ? o : Li ?? (Li = fn()),
        H,
        O,
        k,
        s,
        t,
        n
      ), y || (G.e.f |= nn), l.set(O, G)), se.add(O);
    }
    if ($ === 0 && a && !p && (y ? p = Nt(() => a(o)) : (p = Nt(() => a(Li ?? (Li = fn()))), p.f |= nn)), $ > se.size && Qa(), !y)
      if (m.set(X, se), S) {
        for (const [C, ne] of l)
          se.has(C) || X.skip_effect(ne.e);
        X.oncommit(T), X.ondiscard(w);
      } else
        T(X);
    i(x);
  }), J = { effect: M, items: l, pending: m, outrogroups: null, fallback: p };
  y = !1;
}
function xr(e) {
  for (; e !== null && !(e.f & Vt); )
    e = e.next;
  return e;
}
function _l(e, t, n, r, s) {
  var G, C, ne, pe, I, z, ie, de, Fe;
  var a = (r & co) !== 0, o = t.length, l = e.items, u = xr(e.effect.first), f, p = null, x, h = [], m = [], y, T, w, M;
  if (a)
    for (M = 0; M < o; M += 1)
      y = t[M], T = s(y, M), w = /** @type {EachItem} */
      l.get(T).e, w.f & nn || ((C = (G = w.nodes) == null ? void 0 : G.a) == null || C.measure(), (x ?? (x = /* @__PURE__ */ new Set())).add(w));
  for (M = 0; M < o; M += 1) {
    if (y = t[M], T = s(y, M), w = /** @type {EachItem} */
    l.get(T).e, e.outrogroups !== null)
      for (const we of e.outrogroups)
        we.pending.delete(w), we.done.delete(w);
    if (w.f & st && (ms(w), a && ((pe = (ne = w.nodes) == null ? void 0 : ne.a) == null || pe.unfix(), (x ?? (x = /* @__PURE__ */ new Set())).delete(w))), w.f & nn)
      if (w.f ^= nn, w === u)
        Ar(w, null, n);
      else {
        var J = p ? p.next : u;
        w === e.effect.last && (e.effect.last = w.prev), w.prev && (w.prev.next = w.next), w.next && (w.next.prev = w.prev), mn(e, p, w), mn(e, w, J), Ar(w, J, n), p = w, h = [], m = [], u = xr(p.next);
        continue;
      }
    if (w !== u) {
      if (f !== void 0 && f.has(w)) {
        if (h.length < m.length) {
          var $ = m[0], se;
          p = $.prev;
          var X = h[0], S = h[h.length - 1];
          for (se = 0; se < h.length; se += 1)
            Ar(h[se], $, n);
          for (se = 0; se < m.length; se += 1)
            f.delete(m[se]);
          mn(e, X.prev, S.next), mn(e, p, X), mn(e, S, $), u = $, p = S, M -= 1, h = [], m = [];
        } else
          f.delete(w), Ar(w, u, n), mn(e, w.prev, w.next), mn(e, w, p === null ? e.effect.first : p.next), mn(e, p, w), p = w;
        continue;
      }
      for (h = [], m = []; u !== null && u !== w; )
        (f ?? (f = /* @__PURE__ */ new Set())).add(u), m.push(u), u = xr(u.next);
      if (u === null)
        continue;
    }
    w.f & nn || h.push(w), p = w, u = xr(w.next);
  }
  if (e.outrogroups !== null) {
    for (const we of e.outrogroups)
      we.pending.size === 0 && (ri(e, ks(we.done)), (I = e.outrogroups) == null || I.delete(we));
    e.outrogroups.size === 0 && (e.outrogroups = null);
  }
  if (u !== null || f !== void 0) {
    var k = [];
    if (f !== void 0)
      for (w of f)
        w.f & st || k.push(w);
    for (; u !== null; )
      !(u.f & st) && u !== e.fallback && k.push(u), u = xr(u.next);
    var H = k.length;
    if (H > 0) {
      var O = r & Wi && o === 0 ? n : null;
      if (a) {
        for (M = 0; M < H; M += 1)
          (ie = (z = k[M].nodes) == null ? void 0 : z.a) == null || ie.measure();
        for (M = 0; M < H; M += 1)
          (Fe = (de = k[M].nodes) == null ? void 0 : de.a) == null || Fe.fix();
      }
      pl(e, k, O);
    }
  }
  a && kn(() => {
    var we, at;
    if (x !== void 0)
      for (w of x)
        (at = (we = w.nodes) == null ? void 0 : we.a) == null || at.apply();
  });
}
function gl(e, t, n, r, s, a, o, l) {
  var u = o & lo ? o & fo ? Pn(n) : /* @__PURE__ */ Bo(n, !1, !1) : null, f = o & uo ? Pn(s) : null;
  return {
    v: u,
    i: f,
    e: Nt(() => (a(t, u ?? n, f ?? s, l), () => {
      e.delete(r);
    }))
  };
}
function Ar(e, t, n) {
  if (e.nodes)
    for (var r = e.nodes.start, s = e.nodes.end, a = t && !(t.f & nn) ? (
      /** @type {EffectNodes} */
      t.nodes.start
    ) : n; r !== null; ) {
      var o = (
        /** @type {TemplateNode} */
        /* @__PURE__ */ Ur(r)
      );
      if (a.before(r), r === s)
        return;
      r = o;
    }
}
function mn(e, t, n) {
  t === null ? e.effect.first = n : t.next = n, n === null ? e.effect.last = t : n.prev = t;
}
function Ca(e) {
  var t, n, r = "";
  if (typeof e == "string" || typeof e == "number") r += e;
  else if (typeof e == "object") if (Array.isArray(e)) {
    var s = e.length;
    for (t = 0; t < s; t++) e[t] && (n = Ca(e[t])) && (r && (r += " "), r += n);
  } else for (n in e) e[n] && (r && (r += " "), r += n);
  return r;
}
function ml() {
  for (var e, t, n = 0, r = "", s = arguments.length; n < s; n++) (e = arguments[n]) && (t = Ca(e)) && (r && (r += " "), r += t);
  return r;
}
function yl(e) {
  return typeof e == "object" ? ml(e) : e ?? "";
}
const Mi = [...` 	
\r\f \v\uFEFF`];
function wl(e, t, n) {
  var r = e == null ? "" : "" + e;
  if (t && (r = r ? r + " " + t : t), n) {
    for (var s of Object.keys(n))
      if (n[s])
        r = r ? r + " " + s : s;
      else if (r.length)
        for (var a = s.length, o = 0; (o = r.indexOf(s, o)) >= 0; ) {
          var l = o + a;
          (o === 0 || Mi.includes(r[o - 1])) && (l === r.length || Mi.includes(r[l])) ? r = (o === 0 ? "" : r.substring(0, o)) + r.substring(l + 1) : o = l;
        }
  }
  return r === "" ? null : r;
}
function Ci(e, t = !1) {
  var n = t ? " !important;" : ";", r = "";
  for (var s of Object.keys(e)) {
    var a = e[s];
    a != null && a !== "" && (r += " " + s + ": " + a + n);
  }
  return r;
}
function bl(e, t) {
  if (t) {
    var n = "", r, s;
    return Array.isArray(t) ? (r = t[0], s = t[1]) : r = t, r && (n += Ci(r)), s && (n += Ci(s, !0)), n = n.trim(), n === "" ? null : n;
  }
  return String(e);
}
function Se(e, t, n, r, s, a) {
  var o = (
    /** @type {any} */
    e[Gs]
  );
  if (o !== n || o === void 0) {
    var l = wl(n, r, a);
    l == null ? e.removeAttribute("class") : e.className = l, e[Gs] = n;
  } else if (a && s !== a)
    for (var u in a) {
      var f = !!a[u];
      (s == null || f !== !!s[u]) && e.classList.toggle(u, f);
    }
  return a;
}
function zs(e, t = {}, n, r) {
  for (var s in n) {
    var a = n[s];
    t[s] !== a && (n[s] == null ? e.style.removeProperty(s) : e.style.setProperty(s, a, r));
  }
}
function Dr(e, t, n, r) {
  var s = (
    /** @type {any} */
    e[Ws]
  );
  if (s !== t) {
    var a = bl(t, r);
    a == null ? e.removeAttribute("style") : e.style.cssText = a, e[Ws] = t;
  } else r && (Array.isArray(r) ? (zs(e, n == null ? void 0 : n[0], r[0]), zs(e, n == null ? void 0 : n[1], r[1], "important")) : zs(e, n, r));
  return r;
}
function Da(e, t, n = !1) {
  if (e.multiple) {
    if (t == null)
      return;
    if (!oi(t))
      return bo();
    for (var r of e.options)
      r.selected = t.includes(Lr(r));
    return;
  }
  for (r of e.options) {
    var s = Lr(r);
    if (Ho(s, t)) {
      r.selected = !0;
      return;
    }
  }
  (!n || t !== void 0) && (e.selectedIndex = -1);
}
function xl(e) {
  var t = new MutationObserver(() => {
    Da(e, e.__value);
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
  }), hi(() => {
    t.disconnect();
  });
}
function Us(e, t, n = t) {
  var r = /* @__PURE__ */ new WeakSet(), s = !0;
  fi(e, "change", (a) => {
    var o = a ? "[selected]" : ":checked", l;
    if (e.multiple)
      l = [].map.call(e.querySelectorAll(o), Lr);
    else {
      var u = e.querySelector(o) ?? // will fall back to first non-disabled option if no option is selected
      e.querySelector("option:not([disabled])");
      l = u && Lr(u);
    }
    n(l), e.__value = l, F !== null && r.add(F);
  }), ma(() => {
    var a = t();
    if (e === document.activeElement) {
      var o = (
        /** @type {Batch} */
        F
      );
      if (r.has(o))
        return;
    }
    if (Da(e, a, s), s && a === void 0) {
      var l = e.querySelector(":checked");
      l !== null && (a = Lr(l), n(a));
    }
    e.__value = a, s = !1;
  }), xl(e);
}
function Lr(e) {
  return "__value" in e ? e.__value : e.value;
}
const Sl = Symbol("is custom element"), Tl = Symbol("is html"), kl = Xa ? "progress" : "PROGRESS";
function si(e, t) {
  var n = mi(e);
  n.value === (n.value = // treat null and undefined the same for the initial value
  t ?? void 0) || // @ts-expect-error
  // `progress` elements always need their value set when it's `0`
  e.value === t && (t !== 0 || e.nodeName !== kl) || (e.value = t ?? "");
}
function Gn(e, t) {
  var n = mi(e);
  n.checked !== (n.checked = // treat null and undefined the same for the initial value
  t ?? void 0) && (e.checked = t);
}
function me(e, t, n, r) {
  var s = mi(e);
  s[t] !== (s[t] = n) && (t === "loading" && (e[Ja] = n), n == null ? e.removeAttribute(t) : typeof n != "string" && El(e).includes(t) ? e[t] = n : e.setAttribute(t, n));
}
function mi(e) {
  return (
    /** @type {Record<string | symbol, unknown>} **/
    /** @type {any} */
    e[ss] ?? (e[ss] = {
      [Sl]: e.nodeName.includes("-"),
      [Tl]: e.namespaceURI === yo
    })
  );
}
var Di = /* @__PURE__ */ new Map();
function El(e) {
  var t = e.getAttribute("is") || e.nodeName, n = Di.get(t);
  if (n) return n;
  Di.set(t, n = []);
  for (var r, s = e, a = Element.prototype; a !== s; ) {
    r = $a(s);
    for (var o in r)
      r[o].set && // better safe than sorry, we don't want spread attributes to mess with HTML content
      o !== "innerHTML" && o !== "textContent" && o !== "innerText" && n.push(o);
    s = Vi(s);
  }
  return n;
}
function St(e, t, n = t) {
  var r = /* @__PURE__ */ new WeakSet();
  fi(e, "input", async (s) => {
    var a = s ? e.defaultValue : e.value;
    if (a = qs(e) ? $s(a) : a, n(a), F !== null && r.add(F), await sl(), a !== (a = t())) {
      var o = e.selectionStart, l = e.selectionEnd, u = e.value.length;
      if (e.value = a ?? "", l !== null) {
        var f = e.value.length;
        o === l && l === u && f > u ? (e.selectionStart = f, e.selectionEnd = f) : (e.selectionStart = o, e.selectionEnd = Math.min(l, f));
      }
    }
  }), // If we are hydrating and the value has since changed,
  // then use the updated value from the input instead.
  // If defaultValue is set, then value == defaultValue
  // TODO Svelte 6: remove input.value check and set to empty string?
  gn(t) == null && e.value && (n(qs(e) ? $s(e.value) : e.value), F !== null && r.add(F)), Is(() => {
    var s = t();
    if (e === document.activeElement) {
      var a = (
        /** @type {Batch} */
        F
      );
      if (r.has(a))
        return;
    }
    qs(e) && s === $s(e.value) || e.type === "date" && !s && !e.value || s !== e.value && (e.value = s ?? "");
  });
}
function Al(e, t, n = t) {
  fi(e, "change", (r) => {
    var s = r ? e.defaultChecked : e.checked;
    n(s);
  }), // If we are hydrating and the value has since changed,
  // then use the update value from the input instead.
  // If defaultChecked is set, then checked == defaultChecked
  gn(t) == null && n(e.checked), Is(() => {
    var r = t();
    e.checked = !!r;
  });
}
function qs(e) {
  var t = e.type;
  return t === "number" || t === "range";
}
function $s(e) {
  return e === "" ? null : +e;
}
function Bs(e, t) {
  return e === t || (e == null ? void 0 : e[zn]) === t;
}
function Pl(e = {}, t, n, r) {
  var s = (
    /** @type {ComponentContext} */
    it.r
  ), a = (
    /** @type {Effect} */
    ee
  );
  return ma(() => {
    var o, l;
    return Is(() => {
      o = l, l = [], gn(() => {
        Bs(n(...l), e) || (t(e, ...l), o && Bs(n(...o), e) && t(null, ...o));
      });
    }), () => {
      let u = a;
      for (; u !== s && u.parent !== null && u.parent.f & Ys; )
        u = u.parent;
      const f = () => {
        l && Bs(n(...l), e) && t(null, ...l);
      }, p = u.teardown;
      u.teardown = () => {
        f(), p == null || p();
      };
    };
  }), e;
}
function Sn(e, t, n, r) {
  var se;
  var s = !0, a = (n & po) !== 0, o = (n & _o) !== 0, l = (
    /** @type {V} */
    r
  ), u = !0, f = (
    /** @type {Derived<V> | undefined} */
    void 0
  ), p = () => o && s ? (f ?? (f = /* @__PURE__ */ Mr(
    /** @type {() => V} */
    r
  )), i(f)) : (u && (u = !1, l = o ? gn(
    /** @type {() => V} */
    r
  ) : (
    /** @type {V} */
    r
  )), l);
  let x;
  if (a) {
    var h = zn in e || Wa in e;
    x = ((se = Jn(e, t)) == null ? void 0 : se.set) ?? (h && t in e ? (X) => e[t] = X : void 0);
  }
  var m, y = !1;
  a ? [m, y] = Eo(() => (
    /** @type {V} */
    e[t]
  )) : m = /** @type {V} */
  e[t], m === void 0 && r !== void 0 && (m = p(), x && (ro(), x(m)));
  var T;
  if (T = () => {
    var X = (
      /** @type {V} */
      e[t]
    );
    return X === void 0 ? p() : (u = !0, X);
  }, !(n & ho))
    return T;
  if (x) {
    var w = e.$$legacy;
    return (
      /** @type {() => V} */
      function(X, S) {
        return arguments.length > 0 ? ((!S || w || y) && x(S ? T() : X), X) : T();
      }
    );
  }
  var M = !1, J = (n & vo ? Mr : ra)(() => (M = !1, T()));
  a && i(J);
  var $ = (
    /** @type {Effect} */
    ee
  );
  return (
    /** @type {() => V} */
    function(X, S) {
      if (arguments.length > 0) {
        const k = S ? i(J) : a ? rt(X) : X;
        return v(J, k), M = !0, l !== void 0 && (l = k), X;
      }
      return pn && M || $.f & Tt ? J.v : i(J);
    }
  );
}
const Il = "5";
var Bi;
typeof window < "u" && ((Bi = window.__svelte ?? (window.__svelte = {})).v ?? (Bi.v = /* @__PURE__ */ new Set())).add(Il);
var Ll = ["forEach", "isDisjointFrom", "isSubsetOf", "isSupersetOf"], Ml = ["difference", "intersection", "symmetricDifference", "union"], Ni = !1, sr, qt, bn, Ss, dr, Na, Oa;
const Ts = class Ts extends Set {
  /**
   * @param {Iterable<T> | null | undefined} [value]
   */
  constructor(n) {
    super();
    q(this, dr);
    /** @type {Map<T, Source<boolean>>} */
    q(this, sr, /* @__PURE__ */ new Map());
    q(this, qt, /* @__PURE__ */ P(0));
    q(this, bn, /* @__PURE__ */ P(0));
    q(this, Ss, hn || -1);
    if (n) {
      for (var r of n)
        super.add(r);
      c(this, bn).v = super.size;
    }
    Ni || re(this, dr, Oa).call(this);
  }
  /** @param {T} value */
  has(n) {
    var r = super.has(n), s = c(this, sr), a = s.get(n);
    if (a === void 0) {
      if (!r)
        return i(c(this, qt)), !1;
      a = re(this, dr, Na).call(this, !0), s.set(n, a);
    }
    return i(a), r;
  }
  /** @param {T} value */
  add(n) {
    return super.has(n) || (super.add(n), v(c(this, bn), super.size), En(c(this, qt))), this;
  }
  /** @param {T} value */
  delete(n) {
    var r = super.delete(n), s = c(this, sr), a = s.get(n);
    return a !== void 0 && (s.delete(n), v(a, !1)), r && (v(c(this, bn), super.size), En(c(this, qt))), r;
  }
  clear() {
    if (super.size !== 0) {
      super.clear();
      var n = c(this, sr);
      for (var r of n.values())
        v(r, !1);
      n.clear(), v(c(this, bn), 0), En(c(this, qt));
    }
  }
  keys() {
    return this.values();
  }
  values() {
    return i(c(this, qt)), super.values();
  }
  entries() {
    return i(c(this, qt)), super.entries();
  }
  [Symbol.iterator]() {
    return this.keys();
  }
  get size() {
    return i(c(this, bn));
  }
};
sr = new WeakMap(), qt = new WeakMap(), bn = new WeakMap(), Ss = new WeakMap(), dr = new WeakSet(), /**
 * If the source is being created inside the same reaction as the SvelteSet instance,
 * we use `state` so that it will not be a dependency of the reaction. Otherwise we
 * use `source` so it will be.
 *
 * @template T
 * @param {T} value
 * @returns {Source<T>}
 */
Na = function(n) {
  return hn === c(this, Ss) ? /* @__PURE__ */ P(n) : Pn(n);
}, // We init as part of the first instance so that we can treeshake this class
Oa = function() {
  Ni = !0;
  var n = Ts.prototype, r = Set.prototype;
  for (const s of Ll)
    n[s] = function(...a) {
      return i(c(this, qt)), r[s].apply(this, a);
    };
  for (const s of Ml)
    n[s] = function(...a) {
      i(c(this, qt));
      var o = (
        /** @type {Set<T>} */
        r[s].apply(this, a)
      );
      return new Ts(o);
    };
};
let Nr = Ts;
function Cl(e) {
  if (!e) return null;
  const t = e.trim();
  if (/^\d+$/.test(t))
    return parseInt(t);
  const n = t.match(/thesession\.org\/tunes\/(\d+)/i);
  return n ? parseInt(n[1]) : null;
}
const Dl = {
  alpha: {
    asc: (e, t) => (e.tune_name || "").localeCompare(t.tune_name || ""),
    desc: (e, t) => (t.tune_name || "").localeCompare(e.tune_name || "")
  },
  session: {
    asc: (e, t) => (e.play_count || 0) - (t.play_count || 0),
    desc: (e, t) => (t.play_count || 0) - (e.play_count || 0)
  },
  everywhere: {
    asc: (e, t) => (e.tunebook_count || 0) - (t.tunebook_count || 0),
    desc: (e, t) => (t.tunebook_count || 0) - (e.tunebook_count || 0)
  }
}, Nl = ["", "all", "not on list", "want to learn", "learning", "learned"];
function Ol(e, t, n, r) {
  var u;
  const s = typeof window < "u" ? window.TunebookStatus : null, a = typeof window < "u" ? window.AccentUtils : null, o = e.filter((f) => {
    if (t.search) {
      const p = Cl(t.search), x = f.tune_name || "", h = a ? a.includes(x, t.search) : x.toLowerCase().includes(t.search), m = p && f.tune_id === p;
      if (!h && !m) return !1;
    }
    return !(t.type && f.tune_type !== t.type || t.mystatus && t.mystatus !== "all" && s && s.isLoaded() && s.statusFor(f.tune_id, r) !== t.mystatus);
  }), l = (u = Dl[n.type]) == null ? void 0 : u[n.dir];
  return l && o.sort(l), o;
}
function Rl(e, t) {
  return e < t ? `Showing ${e} of ${t} tunes` : `${t} tune${t !== 1 ? "s" : ""}`;
}
function Fl(e, t) {
  const n = {
    filters: { search: "", type: "", mystatus: "" },
    rawSearch: "",
    myStatusInstrument: "all",
    sort: { type: "session", dir: "desc" }
  }, r = e.get("search");
  r && (n.filters.search = r.toLowerCase().trim(), n.rawSearch = r);
  const s = e.get("type");
  s && (n.filters.type = s);
  const a = e.get("mystatus");
  if (a && t && Nl.includes(a)) {
    n.filters.mystatus = a;
    const o = e.get("myinst");
    o && (n.myStatusInstrument = o);
  }
  return e.has("sortType") && (n.sort.type = e.get("sortType")), e.has("sortDir") && (n.sort.dir = e.get("sortDir")), n;
}
function jl(e, t, n, r) {
  return t.search ? e.set("search", t.search) : e.delete("search"), t.type ? e.set("type", t.type) : e.delete("type"), t.mystatus ? e.set("mystatus", t.mystatus) : e.delete("mystatus"), t.mystatus && r !== "all" ? e.set("myinst", r) : e.delete("myinst"), n.type !== "session" || n.dir !== "desc" ? (e.set("sortType", n.type), e.set("sortDir", n.dir)) : (e.delete("sortType"), e.delete("sortDir")), e;
}
function Oi(e) {
  return e.replace(/\/(tunes|people|logs)(\/\d+)?$/, "").replace(/\/$/, "");
}
function ii(e) {
  if (!e) return "";
  const t = e.split(":");
  let n = parseInt(t[0]);
  const r = t[1], s = n >= 12 ? "pm" : "am";
  return n = n > 12 ? n - 12 : n === 0 ? 12 : n, `${n}:${r}${s}`;
}
function zl(e, t) {
  return ii(e) + "-" + ii(t);
}
function Ul(e) {
  return e.start_time && e.end_time ? zl(e.start_time, e.end_time) : e.start_time ? ii(e.start_time) + " - ?" : "";
}
function Vs(e) {
  return e.tune_count || 0;
}
function ql(e) {
  return (e.tune_count || 0) === 0;
}
function $l(e) {
  return e.multiple_on_date ? e.session_instance_id : e.date;
}
function Bl(e) {
  return new Date(e).toLocaleDateString("en-US", {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric"
  });
}
function Vl(e) {
  return e.replace(/[‘’]/g, "'").replace(/[“”]/g, '"');
}
function Hl(e) {
  if (!e || e.trim() === "") return null;
  if (e = e.trim(), /^\d+$/.test(e))
    return parseInt(e);
  const t = e.match(/thesession\.org\/(members|sessions)\/(\d+)/);
  return t ? parseInt(t[2]) : null;
}
function Yl(e, t, n) {
  let r = e;
  return t === "regulars" && (r = r.filter((s) => s.is_regular)), n && (r = r.filter((s) => {
    const a = `${s.first_name} ${s.last_name}`.toLowerCase(), o = s.instruments ? s.instruments.join(" ").toLowerCase() : "";
    return a.includes(n) || o.includes(n);
  })), r;
}
var Gl = /* @__PURE__ */ E('<a class="filter-panel-toggle" id="add-session-tune-btn" title="Add tune" style="text-decoration: none; font-size: 24px; font-weight: 300; line-height: 1;">+</a>'), Ri = /* @__PURE__ */ E("<option> </option>"), Wl = /* @__PURE__ */ E('<div class="filter-panel-row"><select id="mystatus-filter" class="filter-panel-select" title="My tunebook status"><option>My Tunebook: off</option><option>Show My Status</option><option>Not On My List</option><option>Want To Learn</option><option>Learning</option><option>Learned</option></select> <select id="mystatus-inst" class="filter-panel-select" title="Instrument"><option>All Instruments</option><!></select></div>'), Jl = /* @__PURE__ */ E('<button id="clear-filters-btn" class="filter-panel-clear-btn">Clear Filters</button>'), Xl = /* @__PURE__ */ E('<div class="selection-buttons"><button id="select-tunes-btn" class="selection-btn"> </button> <button id="copy-to-btn" class="selection-btn primary">And Copy To...</button></div>'), Zl = /* @__PURE__ */ E('<div id="filter-panel"><div class="filter-panel-row"><select id="type-filter" class="filter-panel-select" title="Tune type"><option>All Tune Types</option><!></select></div> <div class="filter-panel-row"><div class="filter-button-group"><button data-sort="alpha">a-z</button> <button data-sort="session">session</button> <button data-sort="everywhere">everywhere</button></div> <button id="sort-direction-toggle" class="filter-sort-direction-btn" title="Toggle sort direction"><span id="sort-direction-icon"> </span></button></div> <!> <div class="filter-panel-actions"><!></div> <!></div>'), Ql = /* @__PURE__ */ E('<a class="btn btn-primary" style="padding: 12px 24px; background-color: var(--primary); color: white; text-decoration: none; border-radius: 4px; display: inline-block;">Add Tune</a>'), Kl = /* @__PURE__ */ E('<div style="padding: 40px 20px; text-align: center; color: var(--text-muted, #6c757d);"><p style="margin-bottom: 20px;"> </p> <!></div>'), eu = /* @__PURE__ */ E("<span> </span>"), tu = /* @__PURE__ */ E('<span class="tune-type"> </span>'), Fi = /* @__PURE__ */ E('<span class="tune-count-badge"> </span>'), nu = /* @__PURE__ */ E('<div><div class="tune-row-header"><input type="checkbox" class="tune-select-checkbox"/> <h3 class="tune-name"> </h3></div> <div class="tune-meta"><!> <!> <!></div></div>'), ru = /* @__PURE__ */ E('<p style="color: var(--text-muted);">Loading destinations...</p>'), su = /* @__PURE__ */ E('<p style="color: #dc3545;">Failed to load destinations. Please try again.</p>'), iu = /* @__PURE__ */ E('<label><input type="radio" name="learn_status"/> </label>'), au = /* @__PURE__ */ E('<div><input type="radio" name="destination"/> <span> </span></div>'), ou = /* @__PURE__ */ E('<div><input type="radio" name="destination" value="my_tunes"/> <span>My Tunes</span> <div id="my-tunes-status-options"></div></div> <!>', 1), lu = /* @__PURE__ */ E('<div id="copy-modal-step-1"><h3 id="copy-modal-title"> </h3> <div class="copy-modal-destinations" id="copy-destinations"><!></div> <div class="copy-modal-actions"><button class="selection-btn">Cancel</button> <button id="copy-next-btn" class="selection-btn primary">Next</button></div></div>'), uu = /* @__PURE__ */ E('<div id="copy-warning" class="copy-modal-warning"> </div>'), cu = /* @__PURE__ */ E('<div id="copy-modal-step-2"><h3 id="copy-confirm-title">Confirm Copy</h3> <p id="copy-confirm-message"> </p> <!> <div class="copy-modal-actions"><button class="selection-btn">Back</button> <button id="copy-confirm-btn" class="selection-btn primary"> </button></div></div>'), du = /* @__PURE__ */ E('<div id="copy-modal-overlay"><div class="copy-modal"><!></div></div>'), fu = /* @__PURE__ */ E('<div id="tunes-tab"><div class="tunes-container"><div class="filters-container"><div class="filter-top-row"><input type="text" id="tune-search" class="filter-search-input" placeholder="Search" autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false"/> <!> <button id="filter-panel-toggle" title="Show filters"><svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="4" y1="21" x2="4" y2="14"></line><line x1="4" y1="10" x2="4" y2="3"></line><line x1="12" y1="21" x2="12" y2="12"></line><line x1="12" y1="8" x2="12" y2="3"></line><line x1="20" y1="21" x2="20" y2="16"></line><line x1="20" y1="12" x2="20" y2="3"></line><line x1="1" y1="14" x2="7" y2="14"></line><line x1="9" y1="8" x2="15" y2="8"></line><line x1="17" y1="16" x2="23" y2="16"></line></svg></button></div> <!></div> <div class="results-count"><span id="results-count-text"> </span> <div id="select-all-row"><input type="checkbox" id="select-all-checkbox" class="tune-select-checkbox"/> <label for="select-all-checkbox" id="select-all-label">Select all</label> <span id="deselect-link" class="deselect-link">(Clear)</span></div></div> <div class="tunes-list" id="tunes-list"><!></div></div>  <!></div>');
function vu(e, t) {
  hr(t, !0);
  let n = Sn(t, "tunes", 19, () => []), r = Sn(t, "totalTunesCount", 3, 0), s = Sn(t, "hasMoreTunes", 3, !1), a = Sn(t, "deepLinkTuneId", 3, null);
  const o = t.session.path, l = t.permissions.is_logged_in, u = (_, A) => window.showMessage && window.showMessage(_, A);
  let f = /* @__PURE__ */ P(rt([...n()])), p = /* @__PURE__ */ P(!s()), x = /* @__PURE__ */ P(!1), h = null;
  const m = Fl(new URLSearchParams(window.location.search), l);
  let y = rt(m.filters), T = /* @__PURE__ */ P(rt(m.rawSearch)), w = rt(m.sort), M = /* @__PURE__ */ P(rt(m.myStatusInstrument)), J = /* @__PURE__ */ P(0), $ = /* @__PURE__ */ P(!1), se = /* @__PURE__ */ P(rt(
    []
    // shown only for 2+ instrument players
  )), X = /* @__PURE__ */ P(!1);
  const S = new Nr();
  let k = /* @__PURE__ */ P(!1), H = /* @__PURE__ */ P(
    ""
    // '', 'opening', 'closing'
  );
  const O = /* @__PURE__ */ he(() => (i(
    J
    // re-filter/re-color once the tunebook loads
  ), Ol(i(f), y, w, i(M)))), G = /* @__PURE__ */ he(() => [
    ...new Set(i(f).map((_) => _.tune_type).filter(Boolean))
  ].sort()), C = /* @__PURE__ */ he(() => !!(y.type || y.mystatus)), ne = /* @__PURE__ */ he(() => i(O).length > 0 && i(O).every((_) => S.has(_.tune_id))), pe = /* @__PURE__ */ he(() => i($) ? "Loading your tunebook…" : i(x) ? `Loading all tunes... (${i(f).length}/${r()})` : Rl(i(O).length, i(f).length)), I = /* @__PURE__ */ he(() => !!y.mystatus && i(se).length > 0);
  function z(_) {
    i(J);
    const A = window.TunebookStatus;
    if (!y.mystatus || !A || !A.isLoaded()) return null;
    const B = A.statusFor(_.tune_id, i(M));
    return { status: B, cls: A.classFor(B) };
  }
  let ie = !1;
  Vn(() => {
    const _ = jl(new URLSearchParams(window.location.search), y, w, i(M));
    if (!ie) {
      ie = !0;
      return;
    }
    const A = _.toString(), B = window.location.pathname + (A ? "?" + A : "");
    window.history.replaceState({}, "", B);
  });
  function de() {
    i(p) || i(x) || (v(x, !0), fetch(`/api/sessions/${o}/tunes/remaining`).then((_) => _.json()).then((_) => {
      if (_.success && _.tunes) {
        if (v(f, [...i(f), ..._.tunes], !0), v(p, !0), h) {
          const A = i(f).find((B) => B.tune_id === h);
          A && setTimeout(() => Je(A), 100), h = null;
        }
      } else
        throw new Error(_.message || "Failed to load remaining tunes");
    }).catch((_) => {
      console.error("Error loading remaining tunes:", _), v(p, !0), h = null;
    }).finally(() => {
      v(x, !1);
    }));
  }
  Vn(() => {
    gn(() => {
      if (i(p) || setTimeout(de, 100), y.mystatus && Ue(), Ms(), Cs(), a()) {
        const _ = i(f).find((A) => A.tune_id === a());
        _ ? setTimeout(() => Je(_), 100) : i(p) || (h = a(), de());
      }
    });
  });
  let Fe;
  function we() {
    clearTimeout(Fe), Fe = setTimeout(
      () => {
        y.search = i(T).toLowerCase().trim();
      },
      300
    );
  }
  function at() {
    i(k) ? (v(H, "closing"), setTimeout(
      () => {
        v(k, !1), v(H, "");
      },
      300
    )) : (v(k, !0), v(H, "opening"), setTimeout(() => v(H, ""), 300));
  }
  function ot(_) {
    if (w.type === _) {
      w.dir = w.dir === "asc" ? "desc" : "asc";
      return;
    }
    w.type = _, w.dir = _ === "session" || _ === "everywhere" ? "desc" : "asc";
  }
  function Ce() {
    y.type = "", y.mystatus = "", v(M, "all");
  }
  function Ue() {
    if (!y.mystatus) return;
    const _ = window.TunebookStatus;
    if (_ && _.isLoaded()) {
      Ze(), Ti(J);
      return;
    }
    _ && (v($, !0), _.load().then(() => {
      v($, !1), Ze(), Ti(J);
    }).catch(() => {
      v($, !1), y.mystatus = "";
    }));
  }
  function Ze() {
    const _ = window.TunebookStatus.getInstruments() || [];
    if (_.length < 2) {
      v(se, [], !0);
      return;
    }
    v(se, _.map((A) => A.instrument), !0), ["all", ...i(se)].includes(i(M)) || v(M, "all");
  }
  function Je(_) {
    window.TuneDetailModal.show({
      context: "session",
      tuneId: _.tune_id,
      apiEndpoint: `/api/sessions/${o}/tunes/${_.tune_id}`,
      onSave() {
        window.location.reload();
      },
      additionalData: {
        sessionPath: o,
        tuneName: _.tune_name,
        tuneType: _.tune_type,
        isUserLoggedIn: l,
        isSessionAdmin: t.permissions.is_session_admin
      }
    });
  }
  function kt(_) {
    if (i(X)) {
      Et(_.tune_id);
      return;
    }
    Je(_);
  }
  function Et(_) {
    S.has(_) ? S.delete(_) : S.add(_);
  }
  function Ft() {
    v(X, !i(X)), i(X) || S.clear();
  }
  function je(_) {
    _.stopPropagation(), i(ne) ? i(O).forEach((A) => S.delete(A.tune_id)) : i(O).forEach((A) => S.add(A.tune_id));
  }
  function fe() {
    S.clear();
  }
  let be = /* @__PURE__ */ P(!1), lt = /* @__PURE__ */ P(1), At = /* @__PURE__ */ P(
    null
    // fetched once, cached
  ), Ht = /* @__PURE__ */ P(!1), Yt = /* @__PURE__ */ P(!1), ke = /* @__PURE__ */ P(null), Pt = /* @__PURE__ */ P("want to learn"), Gt = /* @__PURE__ */ P(!1);
  const Br = [
    ["want to learn", "Want to Learn"],
    ["learning", "Learning"],
    ["learned", "Learned"]
  ];
  async function Vr() {
    if (S.size !== 0 && (v(lt, 1), v(ke, null), v(be, !0), i(At) === null && !i(Ht))) {
      v(Ht, !0), v(Yt, !1);
      try {
        const A = await (await fetch("/api/user/admin-sessions")).json();
        v(
          At,
          A.success ? A.sessions.filter((B) => B.path !== o) : [],
          !0
        );
      } catch {
        v(Yt, !0);
      }
      v(Ht, !1);
    }
  }
  const Hr = /* @__PURE__ */ he(() => {
    let _;
    if (i(ke) === "my_tunes")
      _ = `My Tunes (as "${i(Pt)}")`;
    else if (i(ke)) {
      const B = i(ke).replace("session:", ""), Ae = (i(At) || []).find((j) => j.path === B);
      _ = Ae ? Ae.name : B;
    } else
      return "";
    const A = S.size;
    return `${A} tune${A !== 1 ? "s" : ""} will be copied to ${_}. Proceed?`;
  }), _r = /* @__PURE__ */ he(() => {
    const _ = i(O).filter((B) => S.has(B.tune_id)).length, A = S.size;
    return _ !== A && (y.search || y.type) ? `Warning: This will copy all ${A} selected tunes, not just the ${_} selected tunes visible right now with your filters and searches enabled!` : "";
  });
  async function Ls() {
    if (!(!i(ke) || S.size === 0)) {
      v(Gt, !0);
      try {
        const _ = { tune_ids: Array.from(S) };
        i(ke) === "my_tunes" ? (_.destination_type = "my_tunes", _.learn_status = i(Pt)) : (_.destination_type = "session", _.destination_session_path = i(ke).replace("session:", ""));
        const B = await (await fetch("/api/tunes/copy", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(_)
        })).json();
        B.success ? (sessionStorage.setItem("copyTunesMessage", B.message), window.location.href = B.redirect_url) : (u(B.error || "Failed to copy tunes", "error"), v(Gt, !1));
      } catch {
        u("An error occurred while copying tunes", "error"), v(Gt, !1);
      }
    }
  }
  function Yr(_) {
    window.SessionTuneAddPane && (_.preventDefault(), window.SessionTuneAddPane.open({
      sessionPath: o,
      query: i(T).trim(),
      onAdded(A, B) {
        window.location.href = "/sessions/" + o + "/tunes?show=" + A + "&added=" + encodeURIComponent(B || "");
      },
      onAlready(A) {
        window.location.href = "/sessions/" + o + "/tunes?show=" + A + "&already=1";
      }
    }));
  }
  function Ms() {
    const _ = new URLSearchParams(window.location.search);
    _.has("added") ? u(`Successfully added "${_.get("added")}" to the session!`, "success") : _.has("already") && u("This tune is already on the session list", "info");
  }
  function Gr() {
    const _ = new URLSearchParams(window.location.search);
    _.delete("show"), _.delete("added"), _.delete("already");
    const A = _.toString(), B = A ? `${window.location.pathname}?${A}` : window.location.pathname;
    window.history.replaceState({}, "", B);
  }
  let Wr = !1;
  function Cs() {
    if (Wr) return;
    const _ = new URLSearchParams(window.location.search), A = _.has("show"), B = _.has("added"), Ae = _.has("already");
    if (!(A || B || Ae)) return;
    Wr = !0;
    const j = A ? _.get("show") : null;
    let ce = 0;
    const _e = 30, oe = () => {
      if (ce++, j) {
        const ae = document.querySelector(`[data-tune-id="${j}"]`);
        if (ae) {
          ae.scrollIntoView({ behavior: "instant", block: "end" });
          const Ne = window.innerHeight * 0.33;
          window.scrollBy({ top: Ne, behavior: "instant" }), setTimeout(
            () => {
              const $e = Date.now(), le = 3e3, xe = () => {
                const U = Math.min((Date.now() - $e) / le, 1), K = 0.8 * (1 - U);
                ae.style.backgroundColor = `rgba(255, 243, 205, ${K})`, U < 1 ? requestAnimationFrame(xe) : ae.style.backgroundColor = "";
              };
              requestAnimationFrame(xe);
            },
            100
          ), Gr();
          return;
        }
      }
      ce < _e ? setTimeout(oe, 100) : Gr();
    };
    oe();
  }
  const Ds = (_) => _.charAt(0).toUpperCase() + _.slice(1);
  var gr = fu();
  let mr;
  var Jr = d(gr), yr = d(Jr), Xr = d(yr), wr = d(Xr), Zr = g(wr, 2);
  {
    var L = (_) => {
      var A = Gl();
      R(() => me(A, "href", `/sessions/${o ?? ""}/tunes/add`)), N("click", A, Yr), b(_, A);
    };
    W(Zr, (_) => {
      l && _(L);
    });
  }
  var D = g(Zr, 2);
  let Z;
  var qe = g(Xr, 2);
  {
    var ve = (_) => {
      var A = Zl(), B = d(A), Ae = d(B), j = d(Ae);
      j.value = j.__value = "";
      var ce = g(j);
      Ye(ce, 16, () => i(G), (Me) => Me, (Me, Ke) => {
        var et = Ri(), tt = d(et), ze = {};
        R(
          (mt) => {
            V(tt, mt), ze !== (ze = Ke) && (et.value = (et.__value = Ke) ?? "");
          },
          [() => Ds(Ke)]
        ), b(Me, et);
      });
      var _e = g(B, 2), oe = d(_e), ae = d(oe);
      let Ne;
      var $e = g(ae, 2);
      let le;
      var xe = g($e, 2);
      let U;
      var K = g(oe, 2), Be = d(K), gt = d(Be), Ve = g(_e, 2);
      {
        var dt = (Me) => {
          var Ke = Wl(), et = d(Ke), tt = d(et);
          tt.value = tt.__value = "";
          var ze = g(tt);
          ze.value = ze.__value = "all";
          var mt = g(ze);
          mt.value = mt.__value = "not on list";
          var Qt = g(mt);
          Qt.value = Qt.__value = "want to learn";
          var on = g(Qt);
          on.value = on.__value = "learning";
          var In = g(on);
          In.value = In.__value = "learned";
          var Kt = g(et, 2);
          let es;
          var br = d(Kt);
          br.value = br.__value = "all";
          var Ra = g(br);
          Ye(Ra, 16, () => i(se), (Ln) => Ln, (Ln, Ns) => {
            var ts = Ri(), Fa = d(ts), yi = {};
            R(() => {
              V(Fa, Ns), yi !== (yi = Ns) && (ts.value = (ts.__value = Ns) ?? "");
            }), b(Ln, ts);
          }), R(() => es = Dr(Kt, "", es, { display: i(I) ? null : "none" })), N("change", et, Ue), Us(et, () => y.mystatus, (Ln) => y.mystatus = Ln), Us(Kt, () => i(M), (Ln) => v(M, Ln)), b(Me, Ke);
        };
        W(Ve, (Me) => {
          l && Me(dt);
        });
      }
      var te = g(Ve, 2), ge = d(te);
      {
        var Xe = (Me) => {
          var Ke = Jl();
          N("click", Ke, Ce), b(Me, Ke);
        };
        W(ge, (Me) => {
          i(C) && Me(Xe);
        });
      }
      var Qr = g(te, 2);
      {
        var Kr = (Me) => {
          var Ke = Xl(), et = d(Ke), tt = d(et), ze = g(et, 2);
          R(() => {
            V(tt, i(X) ? "Cancel Selection" : "Select Tunes..."), ze.disabled = S.size === 0;
          }), N("click", et, Ft), N("click", ze, Vr), b(Me, Ke);
        };
        W(Qr, (Me) => {
          l && Me(Kr);
        });
      }
      R(() => {
        Se(A, 1, `filter-panel ${i(H) ?? ""}`), Ne = Se(ae, 1, "filter-sort-btn", null, Ne, { active: w.type === "alpha" }), le = Se($e, 1, "filter-sort-btn", null, le, { active: w.type === "session" }), U = Se(xe, 1, "filter-sort-btn", null, U, { active: w.type === "everywhere" }), V(gt, w.dir === "desc" ? "↓" : "↑");
      }), Us(Ae, () => y.type, (Me) => y.type = Me), N("click", ae, () => ot("alpha")), N("click", $e, () => ot("session")), N("click", xe, () => ot("everywhere")), N("click", K, () => w.dir = w.dir === "asc" ? "desc" : "asc"), b(_, A);
    };
    W(qe, (_) => {
      i(k) && _(ve);
    });
  }
  var Ie = g(yr, 2), De = d(Ie), ut = d(De), It = g(De, 2);
  let Wt;
  var Le = d(It), Qe = g(Le, 4);
  let _t;
  var Jt = g(Ie, 2), ye = d(Jt);
  {
    var ct = (_) => {
      var A = Kl(), B = d(A), Ae = d(B), j = g(B, 2);
      {
        var ce = (_e) => {
          var oe = Ql();
          R((ae) => me(oe, "href", `/sessions/${o ?? ""}/tunes/add?q=${ae ?? ""}`), [() => encodeURIComponent(y.search)]), N("click", oe, Yr), b(_e, oe);
        };
        W(j, (_e) => {
          l && _e(ce);
        });
      }
      R(() => V(Ae, `No tunes found matching "${y.search ?? ""}"`)), b(_, A);
    }, Xt = (_) => {
      var A = cr(), B = vn(A);
      Ye(B, 17, () => i(O), (Ae) => Ae.tune_id, (Ae, j) => {
        const ce = /* @__PURE__ */ he(() => z(i(j)));
        var _e = nu(), oe = d(_e), ae = d(oe), Ne = g(ae, 2), $e = d(Ne), le = g(oe, 2), xe = d(le);
        {
          var U = (te) => {
            var ge = eu(), Xe = d(ge);
            R(() => {
              Se(ge, 1, `ls-chip ${i(ce).cls ?? ""}`), V(Xe, i(ce).status);
            }), b(te, ge);
          };
          W(xe, (te) => {
            i(ce) && te(U);
          });
        }
        var K = g(xe, 2);
        {
          var Be = (te) => {
            var ge = tu(), Xe = d(ge);
            R(() => V(Xe, i(j).tune_type)), b(te, ge);
          };
          W(K, (te) => {
            i(j).tune_type && te(Be);
          });
        }
        var gt = g(K, 2);
        {
          var Ve = (te) => {
            var ge = Fi(), Xe = d(ge);
            R(() => V(Xe, i(j).play_count || 0)), b(te, ge);
          }, dt = (te) => {
            var ge = Fi(), Xe = d(ge);
            R(() => V(Xe, i(j).tunebook_count || 0)), b(te, ge);
          };
          W(gt, (te) => {
            w.type === "session" ? te(Ve) : w.type === "everywhere" && te(dt, 1);
          });
        }
        R(
          (te) => {
            Se(_e, 1, `tune-row${i(X) ? " selection-mode" : ""}${i(ce) ? " " + i(ce).cls : ""}`), me(_e, "data-tune-id", i(j).tune_id), me(ae, "data-tune-id", i(j).tune_id), Gn(ae, te), V($e, i(j).tune_name || "Unknown");
          },
          [() => S.has(i(j).tune_id)]
        ), N("click", _e, () => kt(i(j))), N("click", ae, (te) => {
          te.stopPropagation(), Et(i(j).tune_id);
        }), b(Ae, _e);
      }), b(_, A);
    };
    W(ye, (_) => {
      i(O).length === 0 && y.search ? _(ct) : _(Xt, -1);
    });
  }
  var Zt = g(Jr, 2);
  {
    var Ee = (_) => {
      var A = du();
      let B;
      var Ae = d(A), j = d(Ae);
      {
        var ce = (oe) => {
          var ae = lu(), Ne = d(ae), $e = d(Ne), le = g(Ne, 2), xe = d(le);
          {
            var U = (te) => {
              var ge = ru();
              b(te, ge);
            }, K = (te) => {
              var ge = su();
              b(te, ge);
            }, Be = (te) => {
              var ge = ou(), Xe = vn(ge);
              let Qr;
              var Kr = d(Xe), Me = g(Kr, 4);
              let Ke;
              Ye(Me, 21, () => Br, ([tt, ze]) => tt, (tt, ze) => {
                var mt = /* @__PURE__ */ he(() => Yi(i(ze), 2));
                let Qt = () => i(mt)[0], on = () => i(mt)[1];
                var In = iu(), Kt = d(In), es = g(Kt);
                R(() => {
                  si(Kt, Qt()), Gn(Kt, i(Pt) === Qt()), V(es, ` ${on() ?? ""}`);
                }), N("click", Kt, (br) => {
                  br.stopPropagation(), v(Pt, Qt(), !0);
                }), b(tt, In);
              });
              var et = g(Xe, 2);
              Ye(et, 17, () => i(At) || [], (tt) => tt.path, (tt, ze) => {
                var mt = au();
                let Qt;
                var on = d(mt), In = g(on, 2), Kt = d(In);
                R(() => {
                  Qt = Se(mt, 1, "copy-destination-option", null, Qt, {
                    selected: i(ke) === "session:" + i(ze).path
                  }), si(on, "session:" + i(ze).path), Gn(on, i(ke) === "session:" + i(ze).path), V(Kt, i(ze).name);
                }), N("click", mt, () => v(ke, "session:" + i(ze).path)), b(tt, mt);
              }), R(() => {
                Qr = Se(Xe, 1, "copy-destination-option", null, Qr, { selected: i(ke) === "my_tunes" }), Gn(Kr, i(ke) === "my_tunes"), Ke = Se(Me, 1, "my-tunes-status-options", null, Ke, { visible: i(ke) === "my_tunes" });
              }), N("click", Xe, () => v(ke, "my_tunes")), b(te, ge);
            };
            W(xe, (te) => {
              i(Ht) ? te(U) : i(Yt) ? te(K, 1) : te(Be, -1);
            });
          }
          var gt = g(le, 2), Ve = d(gt), dt = g(Ve, 2);
          R(() => {
            V($e, `Copy the ${S.size ?? ""} selected tune${S.size !== 1 ? "s" : ""} to:`), dt.disabled = !i(ke);
          }), N("click", Ve, () => v(be, !1)), N("click", dt, () => v(lt, 2)), b(oe, ae);
        }, _e = (oe) => {
          var ae = cu(), Ne = g(d(ae), 2), $e = d(Ne), le = g(Ne, 2);
          {
            var xe = (Ve) => {
              var dt = uu(), te = d(dt);
              R(() => V(te, i(_r))), b(Ve, dt);
            };
            W(le, (Ve) => {
              i(_r) && Ve(xe);
            });
          }
          var U = g(le, 2), K = d(U), Be = g(K, 2), gt = d(Be);
          R(() => {
            V($e, i(Hr)), Be.disabled = i(Gt), V(gt, i(Gt) ? "Copying..." : "Copy Them!");
          }), N("click", K, () => v(lt, 1)), N("click", Be, Ls), b(oe, ae);
        };
        W(j, (oe) => {
          i(lt) === 1 ? oe(ce) : oe(_e, -1);
        });
      }
      R(() => B = Se(A, 1, "copy-modal-overlay", null, B, { hidden: !i(be) })), N("click", A, (oe) => {
        oe.target === oe.currentTarget && v(be, !1);
      }), b(_, A);
    };
    W(Zt, (_) => {
      l && _(Ee);
    });
  }
  R(() => {
    mr = Se(gr, 1, "tab-content", null, mr, { active: t.active }), Z = Se(D, 1, "filter-panel-toggle", null, Z, { active: i(k) || i(C) }), V(ut, i(pe)), Wt = Se(It, 1, "select-all-row", null, Wt, { visible: i(X) }), Gn(Le, i(ne)), _t = Dr(Qe, "", _t, { display: S.size > 0 ? "inline" : "none" });
  }), N("input", wr, we), St(wr, () => i(T), (_) => v(T, _)), N("click", D, at), N("click", Le, je), N("click", Qe, fe), b(e, gr), pr();
}
$r(["input", "click", "change"]);
const ji = (e, t = ds) => {
  var n = cr(), r = vn(n);
  {
    var s = (o) => {
      var l = _u(), u = d(l);
      R((f, p) => V(u, `(${f ?? ""} tune${p ?? ""} logged)`), [
        () => Vs(t()),
        () => Vs(t()) !== 1 ? "s" : ""
      ]), b(o, l);
    }, a = /* @__PURE__ */ he(() => Vs(t()) > 0);
    W(r, (o) => {
      i(a) && o(s);
    });
  }
  b(e, n);
};
var hu = /* @__PURE__ */ E('<span class="session-instance-link"><span> </span><span class="active-now-badge"></span></span>'), pu = /* @__PURE__ */ E("<a><!></a>"), _u = /* @__PURE__ */ E('<span class="log-tune-count"> </span>'), gu = /* @__PURE__ */ E('<div style="text-align: center; padding: 40px;"><p style="color: var(--danger, #dc3545);">Error loading logs. Please <a href="#reload" style="color: var(--primary);">refresh the page</a>.</p></div>'), mu = /* @__PURE__ */ E('<div style="text-align: center; padding: 40px; color: var(--disabled-text);"><p>Loading logs...</p></div>'), zi = /* @__PURE__ */ E('<span class="year-add-link" id="add-session-btn">Add</span>'), yu = /* @__PURE__ */ E('<tr class="year-content-row"><td class="instance-location-cell"><!></td><td class="instance-time-cell"> </td></tr>'), wu = /* @__PURE__ */ E('<tbody class="year-section"><tr class="year-header-row"><td colspan="2" class="year-header-cell"><div class="year-header"><div class="year-header-left"><span class="year-toggle"> </span> <h3 class="year-title"> </h3> <!></div></div></td></tr><!></tbody>'), bu = /* @__PURE__ */ E('<div class="past-instances"><table class="instances-table"></table></div>'), xu = /* @__PURE__ */ E('<div class="past-instances"><p><a href="#add" id="add-first-session-btn" style="color: var(--primary); text-decoration: none;">Add your first session</a></p></div>'), Su = /* @__PURE__ */ E('<tr class="year-content-row"><td class="instance-date-cell"><!><!></td></tr>'), Tu = /* @__PURE__ */ E('<tbody class="year-section"><tr class="year-header-row"><td class="year-header-cell"><div class="year-header"><div class="year-header-left"><span class="year-toggle"> </span> <h3 class="year-title"> </h3> <!> <a href="#view" class="year-view-link"> </a></div></div></td></tr><!></tbody>'), ku = /* @__PURE__ */ E('<table class="instances-table"></table>'), Eu = /* @__PURE__ */ E('<span class="year-add-link" id="add-session-btn" style="margin-left: 15px; font-size: 0.6em;">Add</span>'), Au = /* @__PURE__ */ E('<li style="margin-bottom: 8px;"><!><!></li>'), Pu = /* @__PURE__ */ E('<div style="padding-left: 10px;"><h3> <!></h3> <ul style="list-style: none; padding: 0;"></ul></div>'), Iu = /* @__PURE__ */ E('<div class="past-instances"><!></div>'), Lu = /* @__PURE__ */ E('<div class="past-instances"><p><a href="#add" id="add-session-btn" style="color: var(--primary); text-decoration: none;">Add your first log</a></p></div>'), Mu = /* @__PURE__ */ E('<div id="logs-tab" style="padding-left: 10px;"><!></div>');
function Cu(e, t) {
  hr(t, !0);
  const n = (S, k = ds, H = ds) => {
    var O = pu(), G = d(O);
    {
      var C = (I) => {
        var z = hu(), ie = d(z), de = d(ie);
        R(() => V(de, H())), b(I, z);
      }, ne = /* @__PURE__ */ he(() => i(f).includes(k().session_instance_id)), pe = (I) => {
        var z = cl();
        R(() => V(z, H())), b(I, z);
      };
      W(G, (I) => {
        i(ne) ? I(C) : I(pe, -1);
      });
    }
    R(
      (I, z) => {
        me(O, "href", `/sessions/${r ?? ""}/${I ?? ""}`), me(O, "data-instance-id", k().session_instance_id), Se(O, 1, z);
      },
      [
        () => $l(k()),
        () => yl(ql(k()) ? "empty-log" : "")
      ]
    ), b(S, O);
  }, r = t.session.path;
  let s = /* @__PURE__ */ P(!1), a = /* @__PURE__ */ P(!1), o = /* @__PURE__ */ P(!1), l = /* @__PURE__ */ P(null);
  const u = new Nr();
  let f = /* @__PURE__ */ P(rt([]));
  Vn(() => {
    gn(() => {
      fetch(`/api/session/${t.session.session_id}/active_instance`).then((S) => S.json()).then((S) => {
        S.success && S.active_instance_ids && S.active_instance_ids.length > 0 && v(f, S.active_instance_ids, !0);
      }).catch((S) => {
        console.error("Error fetching active instances:", S);
      });
    });
  }), Vn(() => {
    t.active && !i(s) && !i(a) && p();
  });
  function p() {
    v(a, !0), v(o, !1), fetch(`/api/sessions/${r}/logs`).then((S) => S.json()).then((S) => {
      if (S.success)
        v(l, S, !0), v(s, !0);
      else
        throw new Error(S.message || "Failed to load logs");
    }).catch((S) => {
      console.error("Error loading logs:", S), v(o, !0);
    }).finally(() => {
      v(a, !1);
    });
  }
  function x(S) {
    u.has(S) ? u.delete(S) : u.add(S);
  }
  const h = /* @__PURE__ */ he(() => i(l) && (i(l).session_type || "regular") === "festival");
  function m(S) {
    S.preventDefault(), t.onAddInstance();
  }
  var y = Mu();
  let T;
  var w = d(y);
  {
    var M = (S) => {
      var k = gu(), H = d(k), O = g(d(H));
      N("click", O, (G) => {
        G.preventDefault(), window.location.reload();
      }), b(S, k);
    }, J = (S) => {
      var k = mu();
      b(S, k);
    }, $ = (S) => {
      var k = cr(), H = vn(k);
      {
        var O = (C) => {
          var ne = bu(), pe = d(ne);
          Ye(pe, 22, () => i(l).sorted_days, (I) => I, (I, z, ie) => {
            var de = wu(), Fe = d(de), we = d(Fe), at = d(we), ot = d(at), Ce = d(ot), Ue = d(Ce), Ze = g(Ce, 2), Je = d(Ze), kt = g(Ze, 2);
            {
              var Et = (je) => {
                var fe = zi();
                R(() => me(fe, "data-year", z)), N("click", fe, m), b(je, fe);
              };
              W(kt, (je) => {
                i(ie) === 0 && t.isLoggedIn && je(Et);
              });
            }
            var Ft = g(Fe);
            Ye(Ft, 17, () => i(l).instances_by_day[z], (je) => je.session_instance_id, (je, fe) => {
              var be = yu();
              let lt;
              var At = d(be), Ht = d(At);
              n(Ht, () => i(fe), () => i(fe).location_override || t.session.location_name);
              var Yt = g(At), ke = d(Yt);
              R(
                (Pt, Gt) => {
                  me(be, "data-year", z), lt = Dr(be, "", lt, Pt), V(ke, Gt);
                },
                [
                  () => ({ display: u.has(String(z)) ? "none" : null }),
                  () => Ul(i(fe))
                ]
              ), b(je, be);
            }), R(
              (je, fe) => {
                me(at, "data-year", z), me(Ce, "data-year", z), V(Ue, je), V(Je, fe);
              },
              [
                () => u.has(String(z)) ? "▶" : "▼",
                () => Bl(i(l).instances_by_day[z][0].date)
              ]
            ), N("click", Ce, () => x(String(z))), b(I, de);
          }), b(C, ne);
        }, G = (C) => {
          var ne = xu(), pe = d(ne), I = d(pe);
          N("click", I, m), b(C, ne);
        };
        W(H, (C) => {
          i(l).sorted_days && i(l).sorted_days.length > 0 ? C(O) : C(G, -1);
        });
      }
      b(S, k);
    }, se = (S) => {
      var k = Iu(), H = d(k);
      {
        var O = (C) => {
          var ne = ku();
          Ye(ne, 22, () => i(l).sorted_years, (pe) => pe, (pe, I, z) => {
            var ie = Tu(), de = d(ie), Fe = d(de), we = d(Fe), at = d(we), ot = d(at), Ce = d(ot), Ue = g(ot, 2), Ze = d(Ue), Je = g(Ue, 2);
            {
              var kt = (fe) => {
                var be = zi();
                R(() => me(be, "data-year", I)), N("click", be, m), b(fe, be);
              };
              W(Je, (fe) => {
                i(z) === 0 && t.isLoggedIn && fe(kt);
              });
            }
            var Et = g(Je, 2), Ft = d(Et), je = g(de);
            Ye(je, 17, () => i(l).instances_by_year[I], (fe) => fe.session_instance_id, (fe, be) => {
              var lt = Su();
              let At;
              var Ht = d(lt), Yt = d(Ht);
              n(Yt, () => i(be), () => i(be).date);
              var ke = g(Yt);
              ji(ke, () => i(be)), R(
                (Pt) => {
                  me(lt, "data-year", I), At = Dr(lt, "", At, Pt);
                },
                [
                  () => ({ display: u.has(String(I)) ? "none" : null })
                ]
              ), b(fe, lt);
            }), R(
              (fe) => {
                me(we, "data-year", I), me(ot, "data-year", I), V(Ce, fe), V(Ze, I), me(Et, "data-year", I), V(Ft, `view ${i(l).instances_by_year[I].length ?? ""} log${i(l).instances_by_year[I].length !== 1 ? "s" : ""}`);
              },
              [() => u.has(String(I)) ? "▶" : "▼"]
            ), N("click", ot, () => x(String(I))), b(pe, ie);
          }), b(C, ne);
        }, G = (C) => {
          var ne = cr(), pe = vn(ne);
          Ye(pe, 16, () => i(l).sorted_years, (I) => I, (I, z) => {
            var ie = Pu(), de = d(ie), Fe = d(de), we = g(Fe);
            {
              var at = (Ce) => {
                var Ue = Eu();
                R(() => me(Ue, "data-year", z)), N("click", Ue, m), b(Ce, Ue);
              };
              W(we, (Ce) => {
                t.isLoggedIn && Ce(at);
              });
            }
            var ot = g(de, 2);
            Ye(ot, 21, () => i(l).instances_by_year[z], (Ce) => Ce.session_instance_id, (Ce, Ue) => {
              var Ze = Au(), Je = d(Ze);
              n(Je, () => i(Ue), () => i(Ue).date);
              var kt = g(Je);
              ji(kt, () => i(Ue)), b(Ce, Ze);
            }), R(() => V(Fe, z)), b(I, ie);
          }), b(C, ne);
        };
        W(H, (C) => {
          i(l).sorted_years.length > 1 ? C(O) : C(G, -1);
        });
      }
      b(S, k);
    }, X = (S) => {
      var k = Lu(), H = d(k), O = d(H);
      N("click", O, m), b(S, k);
    };
    W(w, (S) => {
      i(o) ? S(M) : i(s) ? i(h) ? S($, 2) : i(l).sorted_years && i(l).sorted_years.length > 0 ? S(se, 3) : S(X, -1) : S(J, 1);
    });
  }
  R(() => T = Se(y, 1, "tab-content", null, T, { active: t.active })), b(e, y), pr();
}
$r(["click"]);
var Du = /* @__PURE__ */ E('<button id="people-filter-btn" class="people-filter-btn"> </button>'), Nu = /* @__PURE__ */ E('<div style="padding: 40px 20px; text-align: center; color: var(--text-muted, #6c757d);"><i class="loading-dots">Loading people...</i></div>'), Ou = /* @__PURE__ */ E('<div style="padding: 40px 20px; text-align: center; color: var(--text-muted, #6c757d);"><p> </p></div>'), Ru = /* @__PURE__ */ E('<button style="margin-top: 16px; padding: 10px 20px; background-color: var(--primary); color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 14px;">Add Someone To This Session</button>'), Fu = /* @__PURE__ */ E('<div style="padding: 40px 20px; text-align: center; color: var(--text-muted, #6c757d);"><p> </p> <!></div>'), ju = /* @__PURE__ */ E('<div class="person-row"><div><i class="fa fa-user-circle"></i></div> <div class="person-info"><div class="person-name"> </div> <div class="person-instruments"> </div></div> <div class="person-meta"><span class="person-attendance-badge"> </span></div></div>'), zu = /* @__PURE__ */ E('<div style="padding: 40px 20px; text-align: center;"><i class="loading-dots">Loading...</i></div>'), Uu = /* @__PURE__ */ E('<div style="padding: 40px 20px; text-align: center; color: var(--text-muted);"><p>Failed to load person details</p></div>'), qu = /* @__PURE__ */ E('<div style="margin-bottom: 16px;"><a href="/me" class="person-detail-link">View my profile</a></div>'), $u = /* @__PURE__ */ E('<div style="margin-bottom: 16px;"><a class="person-detail-link">Common Tunes?</a></div>'), Bu = /* @__PURE__ */ E('<a target="_blank" class="person-detail-link">View on TheSession.org</a>'), Vu = /* @__PURE__ */ E('<span style="color: var(--text-muted);">Not linked</span>'), Hu = /* @__PURE__ */ E('<span class="person-instrument-badge"> </span>'), Yu = /* @__PURE__ */ E('<div class="person-instruments-list"></div>'), Gu = /* @__PURE__ */ E('<span style="color: var(--text-muted);">No instruments listed</span>'), Wu = /* @__PURE__ */ E('<tr><td><a class="person-detail-link"> </a></td></tr>'), Ju = /* @__PURE__ */ E('<table class="attendance-table"><thead><tr><th>Date</th></tr></thead><tbody></tbody></table>'), Xu = /* @__PURE__ */ E('<p style="color: var(--text-muted); margin-top: 12px;">No sessions attended yet</p>'), Zu = /* @__PURE__ */ E('<h2 class="person-detail-title"> </h2> <!> <!> <div class="person-detail-location"> </div> <div class="person-detail-section"><h3>TheSession.org</h3> <!></div> <div class="person-detail-section"><h3>Instruments</h3> <!></div> <div class="person-detail-section"><h3>Sessions Attended</h3> <!></div>', 1), Qu = /* @__PURE__ */ E('<div id="person-detail-modal" style="display: flex;"><div class="modal-dialog"><div id="person-detail-content"><button class="modal-close-btn" title="Close">&times;</button> <!></div></div></div>'), Ku = /* @__PURE__ */ E('<div class="search-result-details"> </div>'), ec = /* @__PURE__ */ E('<div class="search-result-instruments"> </div>'), tc = /* @__PURE__ */ E('<div class="search-result-spinner"></div>'), nc = /* @__PURE__ */ E('<div class="search-result-row"><div class="search-result-content"><div class="search-result-name"> </div> <!> <!></div> <!></div>'), rc = /* @__PURE__ */ E('<div class="search-no-results"> </div>'), sc = /* @__PURE__ */ E('<div id="search-person-modal" style="display: flex;"><div class="modal-dialog"><div style="padding: 20px;"><button class="modal-close-btn" title="Close">&times;</button> <h2 style="margin: 0 32px 20px 0; color: var(--text-color); font-size: 20px; font-weight: 600;">Add Person to Session</h2> <p style="margin: 0 0 16px 0; color: var(--secondary-text); font-size: 14px;">Search people who are members of other sessions, or add someone new.</p> <input type="text" id="search-person-input" class="search-person-input" placeholder="Search by name..." autocomplete="off"/> <div class="search-results-container" id="search-results-container"><!></div> <div class="search-person-actions"><button class="add-person-btn-cancel">Cancel</button> <button class="add-person-btn-save">Add New Person</button></div></div></div></div>'), ic = /* @__PURE__ */ E('<div class="instrument-checkbox-item"><input type="checkbox"/> <label> </label></div>'), ac = /* @__PURE__ */ E('<div class="add-person-form-group"><div class="instrument-checkbox-item"><input type="checkbox" id="add-person-is-regular"/> <label for="add-person-is-regular">Regular?</label></div></div>'), oc = /* @__PURE__ */ E('<div id="add-person-modal" style="display: flex;"><div class="modal-dialog"><div style="padding: 20px;"><button class="modal-close-btn" title="Close">&times;</button> <h2 style="margin: 0 32px 20px 0; color: var(--text-color); font-size: 20px; font-weight: 600;">Add Person to Session</h2> <div class="add-person-form-group"><label for="add-person-first-name">First Name *</label> <input type="text" id="add-person-first-name" required=""/></div> <div class="add-person-form-group"><label for="add-person-last-name">Last Name *</label> <input type="text" id="add-person-last-name" required=""/></div> <div class="add-person-form-group"><label for="add-person-email">Email (optional)</label> <input type="email" id="add-person-email"/></div> <div class="add-person-form-group"><label>Instruments</label> <div class="instruments-checkboxes" id="add-person-instruments"></div> <input type="text" id="add-person-other-instrument" placeholder="Other instrument(s)..." style="margin-top: 8px;"/></div> <div class="add-person-form-group"><label for="add-person-thesession">TheSession.org ID or URL (optional)</label> <input type="text" id="add-person-thesession" placeholder="e.g. 12345 or thesession.org URL"/></div> <!> <div class="add-person-actions"><button class="add-person-btn-cancel">Cancel</button> <button class="add-person-btn-save"> </button></div></div></div></div>'), lc = /* @__PURE__ */ E('<div id="people-tab"><div class="people-container"><div class="people-controls"><input type="text" id="people-search-box" class="people-search-box" placeholder="Search people..."/> <!> <button class="people-add-btn">Add</button></div> <div class="people-list" id="people-list"><!></div></div> <!> <!> <!></div>');
function uc(e, t) {
  hr(t, !0);
  let n = Sn(t, "canonicalInstruments", 19, () => []), r = Sn(t, "currentUserId", 3, null), s = Sn(t, "initialPersonId", 3, null), a = /* @__PURE__ */ P(rt([])), o = /* @__PURE__ */ P(!1), l = /* @__PURE__ */ P(""), u = /* @__PURE__ */ P(
    "all"
    // 'all' | 'regulars'
  ), f = /* @__PURE__ */ P("");
  const p = /* @__PURE__ */ he(() => Vl(i(f).toLowerCase().trim())), x = /* @__PURE__ */ he(() => Yl(i(a), i(u), i(p)));
  let h = !1;
  Vn(() => {
    t.active && !h && (h = !0, m());
  });
  function m() {
    fetch(`/api/sessions/${t.sessionPath}/people`).then((L) => L.json()).then((L) => {
      L.success ? (v(a, L.people, !0), v(o, !0), v(l, "")) : (v(l, `Failed to load people: ${L.message || "Unknown error"}`), v(o, !0));
    }).catch((L) => {
      console.error("Error loading people:", L), v(l, "Error loading people"), v(o, !0);
    });
  }
  function y() {
    v(u, i(u) === "regulars" ? "all" : "regulars", !0);
  }
  let T = /* @__PURE__ */ P(!1), w = /* @__PURE__ */ P(!1), M = /* @__PURE__ */ P(!1), J = /* @__PURE__ */ P(!1), $ = /* @__PURE__ */ P(!1), se = /* @__PURE__ */ P(!1);
  function X() {
    v(M, !0), setTimeout(() => v(J, !0), 10);
  }
  function S() {
    v(J, !1), setTimeout(() => v(M, !1), 300);
  }
  function k() {
    v(se, !1), setTimeout(() => v($, !1), 300);
  }
  let H = 0, O = /* @__PURE__ */ P(!1), G = /* @__PURE__ */ P(!1), C = /* @__PURE__ */ P(null);
  function ne(L) {
    let D = window.location.pathname;
    D = D.replace(/\/people\/\d+$/, "").replace(/\/(tunes|logs|people)$/, ""), window.history.pushState({}, "", `${D}/people/${L}`), v(O, !0), v(G, !1), v(C, null), v(T, !0), setTimeout(() => v(w, !0), 10), H = Date.now(), fetch(`/api/sessions/${t.sessionPath}/people/${L}`).then((Z) => Z.json()).then((Z) => {
      v(O, !1), Z.success ? v(C, Z.person, !0) : v(G, !0);
    }).catch((Z) => {
      console.error("Error loading person details:", Z), v(O, !1), v(G, !0);
    });
  }
  function pe() {
    const L = window.location.pathname.replace(/\/people\/\d+$/, "/people");
    window.history.pushState({}, "", L), v(w, !1), setTimeout(() => v(T, !1), 300);
  }
  const I = (L) => {
    const D = [];
    return L.city && D.push(L.city), L.state && D.push(L.state), L.country && D.push(L.country), D;
  };
  let z = /* @__PURE__ */ P(""), ie = /* @__PURE__ */ P(
    null
    // null until a search ran
  ), de = /* @__PURE__ */ P("Type to search for existing people"), Fe = /* @__PURE__ */ P(null), we = null;
  function at() {
    v(z, ""), v(ie, null), v(de, "Type to search for existing people"), X();
  }
  function ot() {
    we && clearTimeout(we), we = setTimeout(() => Ce(), 1e3);
  }
  function Ce() {
    const L = i(z).trim();
    if (L.length === 0) {
      v(ie, null), v(de, "Type to search for existing people");
      return;
    }
    if (L.length < 2) {
      v(ie, null), v(de, "Type at least 2 characters to search");
      return;
    }
    v(ie, null), v(de, "Searching..."), fetch(`/api/sessions/${t.sessionPath}/people/search?q=${encodeURIComponent(L)}`).then((D) => D.json()).then((D) => {
      D.success ? (v(ie, D.people, !0), D.people.length === 0 && v(de, "No matching people found")) : v(de, `Error: ${D.message}`);
    }).catch((D) => {
      console.error("Search error:", D), v(de, "Error searching people");
    });
  }
  function Ue(L) {
    v(Fe, L, !0);
    const D = t.sessionType === "festival";
    fetch(`/api/sessions/${t.sessionPath}/people/add-existing`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ person_id: L, is_regular: D })
    }).then((Z) => Z.json()).then((Z) => {
      v(Fe, null), Z.success ? (S(), v(a, [], !0), m()) : alert("Failed to add person: " + (Z.message || "Unknown error"));
    }).catch((Z) => {
      console.error("Error adding person:", Z), v(Fe, null), alert("Error adding person");
    });
  }
  let Ze = /* @__PURE__ */ P(""), Je = /* @__PURE__ */ P(""), kt = /* @__PURE__ */ P(""), Et = /* @__PURE__ */ P(""), Ft = /* @__PURE__ */ P(""), je = /* @__PURE__ */ P(!1);
  const fe = new Nr();
  let be = /* @__PURE__ */ P(!1);
  function lt() {
    S(), setTimeout(
      () => {
        v(Ze, ""), v(Je, ""), v(kt, ""), v(Et, ""), v(Ft, ""), v(je, !1), fe.clear(), v($, !0), setTimeout(() => v(se, !0), 10);
      },
      350
    );
  }
  function At() {
    const L = i(Ze).trim(), D = i(Je).trim();
    if (!L || !D) {
      alert("First name and last name are required");
      return;
    }
    const Z = [...fe];
    i(Ft).trim() && i(Ft).split(",").forEach((ve) => {
      const Ie = ve.trim();
      Ie && Z.push(Ie);
    });
    const qe = t.sessionType === "festival" ? !0 : i(je);
    v(be, !0), fetch(`/api/sessions/${t.sessionPath}/people/add`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        first_name: L,
        last_name: D,
        email: i(kt).trim() || null,
        instruments: Z,
        thesession_user_id: Hl(i(Et)),
        is_regular: qe
      })
    }).then((ve) => ve.json()).then((ve) => {
      ve.success ? (k(), v(a, [], !0), m()) : alert("Failed to add person: " + (ve.message || "Unknown error"));
    }).catch((ve) => {
      console.error("Error adding person:", ve), alert("Error adding person");
    }).finally(() => {
      v(be, !1);
    });
  }
  Vn(() => {
    gn(() => {
      s() && setTimeout(() => ne(s()), 100);
    });
  });
  function Ht(L) {
    if (L.key === "Escape") {
      if (i($)) {
        k();
        return;
      }
      if (i(M)) {
        S();
        return;
      }
      i(T) && pe();
    }
  }
  function Yt(L) {
    Date.now() - H < 500 || L.target === L.currentTarget && pe();
  }
  var ke = { showPersonDetail: ne }, Pt = lc();
  Ma("keydown", _s, Ht);
  let Gt;
  var Br = d(Pt), Vr = d(Br), Hr = d(Vr), _r = g(Hr, 2);
  {
    var Ls = (L) => {
      var D = Du(), Z = d(D);
      R(() => V(Z, i(u) === "regulars" ? "Regulars" : "All")), N("click", D, y), b(L, D);
    };
    W(_r, (L) => {
      t.sessionType !== "festival" && L(Ls);
    });
  }
  var Yr = g(_r, 2), Ms = g(Vr, 2), Gr = d(Ms);
  {
    var Wr = (L) => {
      var D = Nu();
      b(L, D);
    }, Cs = (L) => {
      var D = Ou(), Z = d(D), qe = d(Z);
      R(() => V(qe, i(l))), b(L, D);
    }, Ds = (L) => {
      var D = Fu(), Z = d(D), qe = d(Z), ve = g(Z, 2);
      {
        var Ie = (De) => {
          var ut = Ru();
          N("click", ut, at), b(De, ut);
        };
        W(ve, (De) => {
          i(p) && De(Ie);
        });
      }
      R(() => V(qe, i(p) ? "No people found matching your search" : i(u) === "regulars" ? "No regulars in this session yet" : "No people in this session yet")), b(L, D);
    }, gr = (L) => {
      var D = cr(), Z = vn(D);
      Ye(Z, 17, () => i(x), (qe) => qe.person_id, (qe, ve) => {
        var Ie = ju(), De = d(Ie), ut = g(De, 2), It = d(ut), Wt = d(It), Le = g(It, 2), Qe = d(Le), _t = g(ut, 2), Jt = d(_t), ye = d(Jt);
        R(
          (ct) => {
            Se(De, 1, `person-icon ${i(ve).has_user_account ? "has-account" : "no-account"}`), V(Wt, `${i(ve).first_name ?? ""} ${i(ve).last_name ?? ""}`), V(Qe, ct), V(ye, i(ve).attendance_count || 0);
          },
          [
            () => i(ve).instruments && i(ve).instruments.length > 0 ? i(ve).instruments.join(", ") : "No instruments listed"
          ]
        ), N("click", Ie, () => ne(i(ve).person_id)), b(qe, Ie);
      }), b(L, D);
    };
    W(Gr, (L) => {
      i(o) ? i(l) ? L(Cs, 1) : i(x).length === 0 ? L(Ds, 2) : L(gr, -1) : L(Wr);
    });
  }
  var mr = g(Br, 2);
  {
    var Jr = (L) => {
      var D = Qu();
      let Z;
      var qe = d(D), ve = d(qe), Ie = d(ve), De = g(Ie, 2);
      {
        var ut = (Le) => {
          var Qe = zu();
          b(Le, Qe);
        }, It = (Le) => {
          var Qe = Uu();
          b(Le, Qe);
        }, Wt = (Le) => {
          var Qe = Zu(), _t = vn(Qe), Jt = d(_t), ye = g(_t, 2);
          {
            var ct = (U) => {
              var K = qu();
              b(U, K);
            };
            W(ye, (U) => {
              i(C).person_id === r() && U(ct);
            });
          }
          var Xt = g(ye, 2);
          {
            var Zt = (U) => {
              var K = $u(), Be = d(K);
              R(() => me(Be, "href", `/me/and/${i(C).person_id ?? ""}`)), b(U, K);
            };
            W(Xt, (U) => {
              i(C).has_user_account && i(C).person_id !== r() && U(Zt);
            });
          }
          var Ee = g(Xt, 2), _ = d(Ee), A = g(Ee, 2), B = g(d(A), 2);
          {
            var Ae = (U) => {
              var K = Bu();
              R(() => me(K, "href", `https://thesession.org/members/${i(C).thesession_user_id ?? ""}`)), b(U, K);
            }, j = (U) => {
              var K = Vu();
              b(U, K);
            };
            W(B, (U) => {
              i(C).thesession_user_id ? U(Ae) : U(j, -1);
            });
          }
          var ce = g(A, 2), _e = g(d(ce), 2);
          {
            var oe = (U) => {
              var K = Yu();
              Ye(K, 20, () => i(C).instruments, (Be) => Be, (Be, gt) => {
                var Ve = Hu(), dt = d(Ve);
                R(() => V(dt, gt)), b(Be, Ve);
              }), b(U, K);
            }, ae = (U) => {
              var K = Gu();
              b(U, K);
            };
            W(_e, (U) => {
              i(C).instruments && i(C).instruments.length > 0 ? U(oe) : U(ae, -1);
            });
          }
          var Ne = g(ce, 2), $e = g(d(Ne), 2);
          {
            var le = (U) => {
              var K = Ju(), Be = g(d(K));
              Ye(Be, 21, () => i(C).attended_instances, (gt) => gt.date, (gt, Ve) => {
                var dt = Wu(), te = d(dt), ge = d(te), Xe = d(ge);
                R(() => {
                  me(ge, "href", `/sessions/${t.sessionPath ?? ""}/${i(Ve).date ?? ""}`), V(Xe, i(Ve).date);
                }), b(gt, dt);
              }), b(U, K);
            }, xe = (U) => {
              var K = Xu();
              b(U, K);
            };
            W($e, (U) => {
              i(C).attended_instances && i(C).attended_instances.length > 0 ? U(le) : U(xe, -1);
            });
          }
          R(
            (U) => {
              V(Jt, `${i(C).first_name ?? ""} ${i(C).last_name ?? ""}`), V(_, U);
            },
            [
              () => I(i(C)).length > 0 ? I(i(C)).join(", ") : "No location specified"
            ]
          ), b(Le, Qe);
        };
        W(De, (Le) => {
          i(O) ? Le(ut) : i(G) || !i(C) ? Le(It, 1) : Le(Wt, -1);
        });
      }
      R(() => Z = Se(D, 1, "modal-overlay", null, Z, { show: i(w) })), N("click", D, Yt), N("click", Ie, pe), b(L, D);
    };
    W(mr, (L) => {
      i(T) && L(Jr);
    });
  }
  var yr = g(mr, 2);
  {
    var Xr = (L) => {
      var D = sc();
      let Z;
      var qe = d(D), ve = d(qe), Ie = d(ve), De = g(Ie, 6), ut = g(De, 2), It = d(ut);
      {
        var Wt = (ye) => {
          var ct = cr(), Xt = vn(ct);
          Ye(Xt, 17, () => i(ie), (Zt) => Zt.person_id, (Zt, Ee) => {
            var _ = nc(), A = d(_), B = d(A), Ae = d(B), j = g(B, 2);
            {
              var ce = (le) => {
                var xe = Ku(), U = d(xe);
                R((K) => V(U, K), [
                  () => [
                    i(Ee).city,
                    i(Ee).state,
                    i(Ee).country
                  ].filter(Boolean).join(", ")
                ]), b(le, xe);
              }, _e = /* @__PURE__ */ he(() => [
                i(Ee).city,
                i(Ee).state,
                i(Ee).country
              ].filter(Boolean).length > 0);
              W(j, (le) => {
                i(_e) && le(ce);
              });
            }
            var oe = g(j, 2);
            {
              var ae = (le) => {
                var xe = ec(), U = d(xe);
                R((K) => V(U, K), [() => i(Ee).instruments.join(", ")]), b(le, xe);
              };
              W(oe, (le) => {
                i(Ee).instruments && i(Ee).instruments.length > 0 && le(ae);
              });
            }
            var Ne = g(A, 2);
            {
              var $e = (le) => {
                var xe = tc();
                b(le, xe);
              };
              W(Ne, (le) => {
                i(Fe) === i(Ee).person_id && le($e);
              });
            }
            R(() => {
              me(_, "data-person-id", i(Ee).person_id), V(Ae, `${i(Ee).first_name ?? ""} ${i(Ee).last_name ?? ""}`);
            }), N("click", _, () => Ue(i(Ee).person_id)), b(Zt, _);
          }), b(ye, ct);
        }, Le = (ye) => {
          var ct = rc(), Xt = d(ct);
          R(() => V(Xt, i(de))), b(ye, ct);
        };
        W(It, (ye) => {
          i(ie) && i(ie).length > 0 ? ye(Wt) : ye(Le, -1);
        });
      }
      var Qe = g(ut, 2), _t = d(Qe), Jt = g(_t, 2);
      R(() => Z = Se(D, 1, "modal-overlay", null, Z, { show: i(J) })), N("click", D, (ye) => {
        ye.target === ye.currentTarget && S();
      }), N("click", Ie, S), N("input", De, ot), N("keydown", De, (ye) => {
        ye.key === "Enter" && (ye.preventDefault(), Ce());
      }), St(De, () => i(z), (ye) => v(z, ye)), N("click", _t, S), N("click", Jt, lt), b(L, D);
    };
    W(yr, (L) => {
      i(M) && L(Xr);
    });
  }
  var wr = g(yr, 2);
  {
    var Zr = (L) => {
      var D = oc();
      let Z;
      var qe = d(D), ve = d(qe), Ie = d(ve), De = g(Ie, 4), ut = g(d(De), 2), It = g(De, 2), Wt = g(d(It), 2), Le = g(It, 2), Qe = g(d(Le), 2), _t = g(Le, 2), Jt = g(d(_t), 2);
      Ye(Jt, 22, n, (j) => j, (j, ce, _e) => {
        var oe = ic(), ae = d(oe), Ne = g(ae, 2), $e = d(Ne);
        R(
          (le) => {
            me(ae, "id", `add-person-inst-${i(_e) + 1}`), si(ae, ce), Gn(ae, le), me(Ne, "for", `add-person-inst-${i(_e) + 1}`), V($e, ce);
          },
          [() => fe.has(ce)]
        ), N("change", ae, (le) => {
          le.target.checked ? fe.add(ce) : fe.delete(ce);
        }), b(j, oe);
      });
      var ye = g(Jt, 2), ct = g(_t, 2), Xt = g(d(ct), 2), Zt = g(ct, 2);
      {
        var Ee = (j) => {
          var ce = ac(), _e = d(ce), oe = d(_e);
          Al(oe, () => i(je), (ae) => v(je, ae)), b(j, ce);
        };
        W(Zt, (j) => {
          t.sessionType !== "festival" && j(Ee);
        });
      }
      var _ = g(Zt, 2), A = d(_), B = g(A, 2), Ae = d(B);
      R(() => {
        Z = Se(D, 1, "modal-overlay", null, Z, { show: i(se) }), B.disabled = i(be), V(Ae, i(be) ? "Adding..." : "Add Person");
      }), N("click", D, (j) => {
        j.target === j.currentTarget && k();
      }), N("click", Ie, k), St(ut, () => i(Ze), (j) => v(Ze, j)), St(Wt, () => i(Je), (j) => v(Je, j)), St(Qe, () => i(kt), (j) => v(kt, j)), St(ye, () => i(Ft), (j) => v(Ft, j)), St(Xt, () => i(Et), (j) => v(Et, j)), N("click", A, k), N("click", B, At), b(L, D);
    };
    W(wr, (L) => {
      i($) && L(Zr);
    });
  }
  return R(() => Gt = Se(Pt, 1, "tab-content", null, Gt, { active: t.active })), St(Hr, () => i(f), (L) => v(f, L)), N("click", Yr, at), b(e, Pt), pr(ke);
}
$r(["click", "input", "keydown", "change"]);
var cc = /* @__PURE__ */ E('<div id="add-session-instance-modal"><div class="modal-content"><div class="modal-header"><h3>Add Session Instance</h3></div> <div class="modal-body"><label for="session-date-input">Session Date:</label> <input type="date" id="session-date-input" required=""/> <div style="margin-top: 16px; display: grid; grid-template-columns: 1fr 1fr; gap: 16px;"><div><label for="session-start-time-input">Start Time:</label> <input type="time" id="session-start-time-input"/></div> <div><label for="session-end-time-input">End Time:</label> <input type="time" id="session-end-time-input"/></div></div> <label for="session-location-input" style="margin-top: 16px;">Location:</label> <input type="text" id="session-location-input"/> <label for="session-comments-input" style="margin-top: 16px;">Comments:</label> <textarea id="session-comments-input" placeholder="Notes about this session" rows="3" style="resize: vertical;"></textarea></div> <div class="modal-footer"><button type="button" class="btn-secondary" id="add-session-cancel-btn">Cancel</button> <button type="button" class="btn-primary" id="add-session-confirm-btn">Add Session</button></div></div></div>');
function dc(e, t) {
  hr(t, !0);
  let n = /* @__PURE__ */ P(!1), r = /* @__PURE__ */ P(""), s = /* @__PURE__ */ P(""), a = /* @__PURE__ */ P(""), o = /* @__PURE__ */ P(""), l = /* @__PURE__ */ P("");
  const u = (I, z) => window.showMessage && window.showMessage(I, z);
  async function f() {
    v(r, (/* @__PURE__ */ new Date()).toISOString().split("T")[0], !0), v(s, ""), v(a, ""), v(o, ""), v(l, ""), v(n, !0), document.body.classList.add("modal-open");
    try {
      const z = await (await fetch(`/api/sessions/${t.sessionPath}/next_instance_suggestion`)).json();
      z.success && (v(r, z.date || i(r), !0), v(s, z.start_time || "", !0), v(a, z.end_time || "", !0));
    } catch (I) {
      console.error("Failed to get next session suggestion:", I);
    }
  }
  function p() {
    v(n, !1), document.body.classList.remove("modal-open");
  }
  function x() {
    const I = i(r).trim();
    if (!I) {
      u("Please enter a session date", "error");
      return;
    }
    const z = { date: I };
    i(s).trim() && (z.start_time = i(s).trim()), i(a).trim() && (z.end_time = i(a).trim()), i(o).trim() && (z.location = i(o).trim()), i(l).trim() && (z.comments = i(l).trim()), fetch(`/api/sessions/${t.sessionPath}/add_instance`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(z)
    }).then((ie) => ie.json()).then((ie) => {
      if (ie.success) {
        u(ie.message), p();
        const de = ie.session_instance_id || I;
        window.location.href = `/sessions/${t.sessionPath}/${de}?edit=true`;
      } else
        u(ie.message, "error");
    }).catch((ie) => {
      u("Failed to add session instance", "error"), console.error("Error:", ie);
    });
  }
  function h(I) {
    if (I.key !== "Escape") return;
    const z = document.getElementById("tune-detail-modal");
    z && z.style.display === "flex" || i(n) && p();
  }
  var m = { open: f, close: p }, y = cc();
  Ma("keydown", _s, h);
  let T, w;
  var M = d(y), J = g(d(M), 2), $ = g(d(J), 2), se = g($, 2), X = d(se), S = g(d(X), 2), k = g(X, 2), H = g(d(k), 2), O = g(se, 4), G = g(O, 4), C = g(J, 2), ne = d(C), pe = g(ne, 2);
  return R(() => {
    T = Se(y, 1, "modal-overlay", null, T, { show: i(n) }), w = Dr(y, "", w, { display: i(n) ? "flex" : "none" }), me(O, "placeholder", `The usual: ${t.locationName ?? ""}`);
  }), N("click", y, (I) => {
    I.target === I.currentTarget && p();
  }), N("keydown", $, (I) => {
    I.key === "Enter" && i(n) && x();
  }), St($, () => i(r), (I) => v(r, I)), St(S, () => i(s), (I) => v(s, I)), St(H, () => i(a), (I) => v(a, I)), St(O, () => i(o), (I) => v(o, I)), St(G, () => i(l), (I) => v(l, I)), N("click", ne, p), N("click", pe, x), b(e, y), pr(m);
}
$r(["click", "keydown"]);
var fc = /* @__PURE__ */ E("<button> </button>"), vc = /* @__PURE__ */ E('<div class="tabs-container"><div class="tab-buttons"></div> <!> <!> <!></div> <!>', 1);
function hc(e, t) {
  hr(t, !0);
  let n = Sn(t, "ctx", 19, () => ({}));
  const r = t.pageData.session, s = t.pageData.permissions, a = r.path, o = r.session_type === "festival", l = t.pageData.default_tab, u = s.is_logged_in && s.is_session_member, f = (() => {
    const k = o ? [["logs", "Sessions"], ["tunes", "Tunes"]] : [["tunes", "Tunes"], ["logs", "Logs"]];
    return u && k.push(["people", "People"]), k;
  })();
  let p = /* @__PURE__ */ P(rt(n().activeTab || l));
  function x(k) {
    v(p, k, !0);
    const H = `${Oi(window.location.pathname)}/${k}`;
    window.history.pushState({}, "", H);
  }
  let h = /* @__PURE__ */ P(null);
  const m = () => i(h) && i(h).open(), y = (k, H) => window.showMessage && window.showMessage(k, H);
  Vn(() => {
    gn(() => {
      if (!n().activeTab && l) {
        const G = Oi(window.location.pathname);
        window.history.replaceState({}, "", `${G}/${l}${window.location.search}`);
      }
      const k = sessionStorage.getItem("copyTunesMessage");
      k && (sessionStorage.removeItem("copyTunesMessage"), y(k, "success"));
      const H = document.querySelector(".message");
      H && setTimeout(() => H.classList.add("show"), 10);
      const O = document.getElementById("join-session-link");
      O && O.addEventListener("click", function(G) {
        G.preventDefault(), O.style.pointerEvents = "none", O.textContent = "Joining...", fetch(`/api/sessions/${a}/join`, {
          method: "POST",
          headers: { "Content-Type": "application/json" }
        }).then((C) => C.json()).then((C) => {
          C.success ? (y("You have been added to this session!", "success"), setTimeout(
            () => {
              window.location.href = window.location.pathname.replace(/\/(tunes|logs)$/, "") + "/people";
            },
            1500
          )) : (y(C.message || "Failed to join session", "error"), O.style.pointerEvents = "", O.textContent = "Yes, Add Me");
        }).catch(() => {
          y("An error occurred. Please try again.", "error"), O.style.pointerEvents = "", O.textContent = "Yes, Add Me";
        });
      });
    });
  });
  var T = vc(), w = vn(T), M = d(w);
  Ye(M, 21, () => f, ([k, H]) => k, (k, H) => {
    var O = /* @__PURE__ */ he(() => Yi(i(H), 2));
    let G = () => i(O)[0], C = () => i(O)[1];
    var ne = fc();
    let pe;
    var I = d(ne);
    R(() => {
      pe = Se(ne, 1, "tab-button", null, pe, { active: i(p) === G() }), me(ne, "data-tab", G()), V(I, C());
    }), N("click", ne, () => x(G())), b(k, ne);
  });
  var J = g(M, 2);
  {
    let k = /* @__PURE__ */ he(() => i(p) === "tunes"), H = /* @__PURE__ */ he(() => t.pageData.tunes || []), O = /* @__PURE__ */ he(() => t.pageData.total_tunes_count || 0), G = /* @__PURE__ */ he(() => !!t.pageData.has_more_tunes), C = /* @__PURE__ */ he(() => n().tuneId || null);
    vu(J, {
      get active() {
        return i(k);
      },
      get session() {
        return r;
      },
      get permissions() {
        return s;
      },
      get tunes() {
        return i(H);
      },
      get totalTunesCount() {
        return i(O);
      },
      get hasMoreTunes() {
        return i(G);
      },
      get deepLinkTuneId() {
        return i(C);
      }
    });
  }
  var $ = g(J, 2);
  {
    let k = /* @__PURE__ */ he(() => i(p) === "logs");
    Cu($, {
      get active() {
        return i(k);
      },
      get session() {
        return r;
      },
      get isLoggedIn() {
        return s.is_logged_in;
      },
      onAddInstance: m
    });
  }
  var se = g($, 2);
  {
    var X = (k) => {
      {
        let H = /* @__PURE__ */ he(() => i(p) === "people"), O = /* @__PURE__ */ he(() => n().canonicalInstruments || []), G = /* @__PURE__ */ he(() => n().currentUserPersonId ?? null), C = /* @__PURE__ */ he(() => n().personId || null);
        uc(k, {
          get active() {
            return i(H);
          },
          get sessionPath() {
            return a;
          },
          get sessionType() {
            return r.session_type;
          },
          get canonicalInstruments() {
            return i(O);
          },
          get currentUserId() {
            return i(G);
          },
          get initialPersonId() {
            return i(C);
          }
        });
      }
    };
    W(se, (k) => {
      u && k(X);
    });
  }
  var S = g(w, 2);
  Pl(
    dc(S, {
      get sessionPath() {
        return a;
      },
      get locationName() {
        return r.location_name;
      }
    }),
    (k) => v(h, k, !0),
    () => i(h)
  ), b(e, T), pr();
}
$r(["click"]);
const Ui = document.getElementById("session-detail-root");
Ui && window.__PAGE_DATA__ && dl(hc, {
  target: Ui,
  props: {
    pageData: window.__PAGE_DATA__,
    ctx: window.__PAGE_CTX__ || {}
  }
});
