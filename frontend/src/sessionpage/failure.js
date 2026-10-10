// Toast a failed action in the page's language (spec 057). The kit's toastFailure
// builds its sentence from an English fragment ("Couldn't " + what), which cannot be
// translated whole, so the callers here pass the two finished sentences instead:
// the one for a failure the server explained without words of its own, and the one
// for a failure that never reached it. A ServerError's own message still wins.
import { toast, ServerError } from '../lib/index.js'

export function toastFailed(error, tryAgain, checkConnection) {
  if (error) console.error(tryAgain, error)
  const message = error instanceof ServerError ? error.message || tryAgain : checkConnection
  toast(message, 'error')
}
