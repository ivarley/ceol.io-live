// Pure helpers for the Places admin page (spec 055).

/** The places that may be `place`'s parent: towns and metros, not `place` itself
 * and not anything inside it (that would make a cycle). `place` null = a new one. */
export function parentOptions(places, place) {
  const byId = new Map(places.map((p) => [p.place_id, p]))
  const inside = (candidate) => {
    const seen = new Set()
    let cur = candidate
    while (cur && !seen.has(cur.place_id)) {
      if (place && cur.place_id === place.place_id) return true
      seen.add(cur.place_id)
      cur = cur.parent ? byId.get(cur.parent.place_id) : null
    }
    return false
  }
  return places.filter((p) => p.kind === 'place' && !inside(p)).sort((a, b) => a.name.localeCompare(b.name))
}

/** Whether a search matches a place: name, slug, area, country or parent name. */
export function matchesPlace(place, query) {
  const q = (query || '').trim().toLowerCase()
  if (!q) return true
  return [place.name, place.slug, place.area, place.country, place.parent?.name]
    .filter(Boolean)
    .some((v) => v.toLowerCase().includes(q))
}

/** A place nothing depends on: no sessions in it, no paths under it, nothing inside. */
export function canDelete(place) {
  return !place.town_sessions && !place.paths && !place.children
}
