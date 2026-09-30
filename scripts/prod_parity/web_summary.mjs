// What the web's logstate.js makes of each captured night (see capture.py).
import { computeOrdered, segmentByBreaks, setLabel, tunesOf } from '../../frontend/src/logstate.js'
import fs from 'fs'
const dir = process.argv[2]
const out = {}
for (const f of fs.readdirSync(dir).filter((f) => f.startsWith('night_'))) {
  const b = JSON.parse(fs.readFileSync(`${dir}/${f}`))
  const ordered = computeOrdered(b.records || [])
  const segs = segmentByBreaks(ordered)
  out[b.session_instance_id] = {
    ordered: ordered.map((r) => r.session_instance_tune_id),
    sets: segs.map((s) => s.tunes.map((t) => t.session_instance_tune_id)),
    breakAfter: segs.map((s) => s.breakAfter ?? null),
    labels: segs.map((s) => setLabel(s.tunes)),
    tunes: tunesOf(ordered).length,
  }
}
fs.writeFileSync(`${dir}/web_summary.json`, JSON.stringify(out))
console.log('nights', Object.keys(out).length, 'tunes', Object.values(out).reduce((a, n) => a + n.tunes, 0))
