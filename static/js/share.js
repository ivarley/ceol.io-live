/* Share this page (spec 052 §B1).
 *
 * Share used to be a hamburger item, and briefly an Account row on /me. Both were
 * wrong in the same way: it acts on the page you are looking at, so it cannot live
 * on one particular page. It is a header control now, present everywhere the app
 * header is.
 *
 * What it offers, in order of usefulness at an actual session:
 *   - the QR code, which is how you hand a link to somebody across a table
 *   - Copy link, for everywhere else
 *   - the system share sheet, when the browser has one
 *
 * Deliberately vanilla: the header is rendered by base.html on pages that have no
 * Svelte bundle at all (help, error pages), so this cannot depend on one.
 */
(function () {
  'use strict'

  var dialog, qrImg, urlText, copyBtn, nativeBtn, lastFocus

  function els() {
    if (dialog) return true
    dialog = document.getElementById('share-dialog')
    if (!dialog) return false
    qrImg = document.getElementById('share-qr')
    urlText = document.getElementById('share-url')
    copyBtn = document.getElementById('share-copy')
    nativeBtn = document.getElementById('share-native')
    return true
  }

  function pageUrl() {
    return window.location.href
  }

  function open() {
    if (!els()) return
    var url = pageUrl()
    urlText.textContent = url
    // Set the QR src only now. It is a server-rendered image, and every page in the
    // app carries this button — fetching one on every page load to show it on almost
    // none of them would be a request per page for nothing.
    qrImg.src = '/api/qr?url=' + encodeURIComponent(url)
    qrImg.alt = 'QR code linking to ' + url

    // The system sheet is the better answer where it exists, but it is not on every
    // browser and never on desktop Safari/Firefox, so it is an extra button rather
    // than the whole feature.
    if (nativeBtn) nativeBtn.hidden = typeof navigator.share !== 'function'

    lastFocus = document.activeElement
    dialog.hidden = false
    document.body.classList.add('share-open')
    var first = dialog.querySelector('button, [href]')
    if (first) first.focus()
    document.addEventListener('keydown', onKey)
  }

  function close() {
    if (!dialog || dialog.hidden) return
    dialog.hidden = true
    document.body.classList.remove('share-open')
    document.removeEventListener('keydown', onKey)
    // Drop the image so reopening on another page cannot flash the previous QR.
    if (qrImg) qrImg.removeAttribute('src')
    if (lastFocus && lastFocus.focus) lastFocus.focus()
  }

  function onKey(e) {
    if (e.key === 'Escape') {
      e.preventDefault()
      close()
    }
  }

  function copy() {
    var url = pageUrl()
    var done = function () {
      var was = copyBtn.textContent
      copyBtn.textContent = 'Copied'
      setTimeout(function () {
        copyBtn.textContent = was
      }, 1600)
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(url).then(done, fallbackCopy)
    } else {
      fallbackCopy()
    }
    function fallbackCopy() {
      // execCommand is deprecated but is still the only path in a non-secure
      // context, which is exactly where local development runs.
      var ta = document.createElement('textarea')
      ta.value = url
      ta.setAttribute('readonly', '')
      ta.style.position = 'fixed'
      ta.style.opacity = '0'
      document.body.appendChild(ta)
      ta.select()
      try {
        document.execCommand('copy')
        done()
      } catch (err) {
        /* leave the URL on screen to select by hand */
      }
      document.body.removeChild(ta)
    }
  }

  function nativeShare() {
    if (typeof navigator.share !== 'function') return
    navigator
      .share({ title: document.title, url: pageUrl() })
      .then(close)
      .catch(function () {
        /* the person cancelled the sheet; leave ours open */
      })
  }

  function wire() {
    var btn = document.getElementById('share-btn')
    if (btn) btn.addEventListener('click', open)
    if (!els()) return
    dialog.addEventListener('click', function (e) {
      if (e.target === dialog || e.target.hasAttribute('data-share-close')) close()
    })
    if (copyBtn) copyBtn.addEventListener('click', copy)
    if (nativeBtn) nativeBtn.addEventListener('click', nativeShare)
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', wire)
  } else {
    wire()
  }

  // The hamburger's Share item (still the live logger's only route in) calls this.
  window.shareCurrentPage = open
})()
