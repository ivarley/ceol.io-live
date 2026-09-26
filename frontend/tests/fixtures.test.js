// One generic runner for every `<module>.fixtures.json` (spec 052 §B5). The live
// logger's client rules have to be reimplemented in Swift and agree with this code
// exactly, so the cases live in plain JSON that both runners read: Vitest here, the
// Swift test package there. This file is deliberately dumb — it maps a case's named
// `input` onto the function's `params`, calls it, and compares the JSON of the result.
// Anything smarter it did would be one more thing the Swift runner has to copy.
//
// File shape (see any fixtures file's _readme for what the module decides):
//   functions.<name>.params     argument names, in call order. An input key that is
//                               absent means "argument not passed" (its default applies).
//   functions.<name>.mapParams  params that are a JS Map, written as [[key, value], ...]
//   functions.<name>.returns    "map": the result is a Map, compared as [[key, value], ...]
//                               in insertion order
//   functions.<name>.harness    "clock": stateful on the wall clock — see nextTs
//   functions.<name>.cases      [{ name, input, expected, note? }], or
//                               [{ name, input, throws: true }] for a call that must
//                               refuse (throw in JS; a Swift port throws too)
//   constants                   exported values, compared exactly
//   _not_fixtured               export name -> why it has no cases

import { describe, it, expect, vi } from 'vitest'

import * as logstate from '../src/logstate.js'
import * as fracindex from '../src/fracindex.js'
import * as abcquery from '../src/shared/abcquery.js'
import * as segments from '../src/shared/segments.js'
import * as offline from '../src/offline.js'
import * as namematch from '../src/tunesheet/namematch.js'

import logstateFx from '../src/logstate.fixtures.json'
import fracindexFx from '../src/fracindex.fixtures.json'
import abcqueryFx from '../src/shared/abcquery.fixtures.json'
import segmentsFx from '../src/shared/segments.fixtures.json'
import offlineFx from '../src/offline.fixtures.json'
import namematchFx from '../src/tunesheet/namematch.fixtures.json'

const MODULES = [
  { name: 'logstate', mod: logstate, fx: logstateFx, load: () => import('../src/logstate.js') },
  { name: 'fracindex', mod: fracindex, fx: fracindexFx },
  { name: 'shared/abcquery', mod: abcquery, fx: abcqueryFx },
  { name: 'shared/segments', mod: segments, fx: segmentsFx },
  { name: 'offline', mod: offline, fx: offlineFx },
  { name: 'tunesheet/namematch', mod: namematch, fx: namematchFx },
]

// What a non-JS runner would see: Maps as entry lists, undefined properties gone.
function toJson(value, spec) {
  const v = spec.returns === 'map' ? [...value.entries()] : value
  return v === undefined ? null : JSON.parse(JSON.stringify(v))
}

function argsFor(spec, input) {
  const params = spec.params || []
  const maps = new Set(spec.mapParams || [])
  // Trailing absent inputs are not passed at all, so JS defaults apply.
  let n = params.length
  while (n > 0 && !(params[n - 1] in input)) n--
  return params.slice(0, n).map((p) => (maps.has(p) ? new Map(input[p]) : structuredClone(input[p])))
}

// nextTs keeps its high-water mark in module state and reads Date.now(). Each case
// gets a fresh module (counter at 0) and a scripted clock: input.clock[i] is the wall
// clock at call i, expected[i] is what call i returns.
async function runClockCase(load, fnName, c) {
  vi.resetModules()
  const fresh = await load()
  const clock = [...c.input.clock]
  const spy = vi.spyOn(Date, 'now').mockImplementation(() => clock.shift())
  try {
    return c.input.clock.map(() => fresh[fnName]())
  } finally {
    spy.mockRestore()
  }
}

for (const { name, mod, fx, load } of MODULES) {
  describe(`${name}.fixtures.json`, () => {
    for (const [fnName, spec] of Object.entries(fx.functions || {})) {
      describe(fnName, () => {
        for (const c of spec.cases) {
          it(c.name, async () => {
            if (c.throws) {
              expect(() => mod[fnName](...argsFor(spec, c.input))).toThrow()
              return
            }
            const actual =
              spec.harness === 'clock'
                ? await runClockCase(load, fnName, c)
                : toJson(mod[fnName](...argsFor(spec, c.input)), spec)
            expect(actual).toEqual(c.expected)
          })
        }
      })
    }

    for (const [constName, value] of Object.entries(fx.constants || {})) {
      it(`constant ${constName}`, () => expect(mod[constName]).toBe(value))
    }

    // The guard: a new export cannot silently skip the fixtures. Every export is
    // fixtured, a pinned constant, or listed in _not_fixtured with a reason — and every
    // name the file mentions really is an export, so a rename can't leave a stale entry.
    it('covers every export', () => {
      const functions = fx.functions || {}
      const constants = fx.constants || {}
      const skipped = fx._not_fixtured || {}
      const unaccounted = Object.keys(mod).filter(
        (k) => !(k in functions) && !(k in constants) && !(k in skipped)
      )
      expect(unaccounted, `add cases, a constant, or a _not_fixtured reason for: ${unaccounted}`).toEqual([])
      const stale = [...Object.keys(functions), ...Object.keys(constants), ...Object.keys(skipped)].filter(
        (k) => !(k in mod)
      )
      expect(stale).toEqual([])
      for (const [fnName, spec] of Object.entries(functions)) {
        expect(typeof mod[fnName], fnName).toBe('function')
        expect(spec.cases.length, `${fnName} has no cases`).toBeGreaterThan(0)
      }
      for (const [k, why] of Object.entries(skipped)) expect(why, k).toMatch(/\S/)
    })
  })
}
