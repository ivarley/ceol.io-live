// Toast (spec 035): thin wrapper over the site-wide `window.showMessage`
// (defined by base.html) so kit components toast identically to legacy pages.
// Pages without it (the live logger's clean-slate shell) get a self-contained
// stacked container instead: top-center, auto-dismiss.

const DISMISS_MS = 3000
const HOST_ID = 'kit-toasts'

// The fallback's styles ride along in JS (this isn't a .svelte file) — injected
// once, only if the fallback is ever used.
const CSS = `
.kit-toasts {
  position: fixed;
  top: var(--sp-3, 12px);
  left: 50%;
  transform: translateX(-50%);
  z-index: var(--z-toast, 9999);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--sp-2, 8px);
  pointer-events: none;
}
.kit-toast {
  max-width: min(420px, calc(100vw - 32px));
  padding: var(--sp-2, 8px) var(--sp-4, 16px);
  border: 1px solid var(--border-color, #ddd);
  border-radius: var(--r, 8px);
  box-shadow: var(--shadow-md, 0 2px 10px rgba(0, 0, 0, 0.12));
  background: var(--dropdown-bg, #fff);
  color: var(--text-color, #252930);
  font-size: 0.95rem;
}
.kit-toast-success {
  background: var(--success-bg, #d4edda);
  border-color: var(--success-border, #c3e6cb);
  color: var(--success-text, #155724);
}
.kit-toast-error {
  background: var(--error-bg, #f8d7da);
  border-color: var(--error-border, #f5c6cb);
  color: var(--error-text, #721c24);
}
`

function ensureHost() {
  let host = document.getElementById(HOST_ID)
  if (host) return host
  if (!document.getElementById('kit-toasts-style')) {
    const style = document.createElement('style')
    style.id = 'kit-toasts-style'
    style.textContent = CSS
    document.head.appendChild(style)
  }
  host = document.createElement('div')
  host.id = HOST_ID
  host.className = 'kit-toasts'
  host.setAttribute('role', 'status')
  host.setAttribute('aria-live', 'polite')
  document.body.appendChild(host)
  return host
}

/**
 * Show an ephemeral message. type: 'success' | 'error' | 'info'.
 * Delegates to window.showMessage when the page provides it.
 */
export function toast(message, type = 'info') {
  if (typeof window !== 'undefined' && typeof window.showMessage === 'function') {
    window.showMessage(message, type)
    return
  }
  const host = ensureHost()
  const el = document.createElement('div')
  el.className = `kit-toast kit-toast-${type}`
  el.textContent = message
  host.appendChild(el)
  setTimeout(() => {
    el.remove()
    if (!host.childElementCount) host.remove()
  }, DISMISS_MS)
}
