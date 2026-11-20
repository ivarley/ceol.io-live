// Dragging a tune in the live logger (spec 029 §F): when a finger's press on the grab
// bar becomes a drag, and how fast the list scrolls while a drag is held near its top
// or bottom. The iPhone app has the same figures (NightEditing.swift, DragScroll).

/** A finger must rest on the grab bar this long before the tune lifts. */
export const DRAG_HOLD_MS = 250
/** Moving further than this before then is a scroll, not a drag (px). */
export const DRAG_HOLD_SLOP = 10

/** The band inside the list's top and bottom edges where a held drag scrolls it (px). */
export const EDGE_ZONE = 56
/** Scroll speed at the band's inner edge, and the most it ever is (px per second). */
export const SCROLL_MIN = 60
export const SCROLL_MAX = 540

/**
 * Where the pointer is against the list's edges: {edge: 'top' | 'bottom' | null,
 * depth: 0..1}, depth being how far into the band it is (1 at the list's edge and
 * anywhere beyond it).
 */
export function edgeZone(y, rect, zone = EDGE_ZONE) {
  const z = Math.min(zone, (rect.bottom - rect.top) / 3)
  if (z <= 0) return { edge: null, depth: 0 }
  if (y < rect.top + z) return { edge: 'top', depth: Math.min(1, (rect.top + z - y) / z) }
  if (y > rect.bottom - z) return { edge: 'bottom', depth: Math.min(1, (y - (rect.bottom - z)) / z) }
  return { edge: null, depth: 0 }
}

/** Pixels per second at that depth: slow at first, never over SCROLL_MAX. */
export function scrollSpeed(depth) {
  const d = Math.max(0, Math.min(1, depth))
  return SCROLL_MIN + (SCROLL_MAX - SCROLL_MIN) * d * d
}
