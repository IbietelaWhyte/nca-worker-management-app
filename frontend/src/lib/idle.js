/**
 * The shared "last activity" clock behind idle sign-out. Pure and React-free, like lib/rota.js.
 *
 * Kept in localStorage rather than in a timer so that every tab of the app reads the same clock
 * (activity in one keeps them all alive) and so that a laptop that slept, or a tab the browser
 * throttled in the background, is judged by the time that really passed when it wakes. This is
 * the app's second localStorage key, after lib/rotaOrder.js.
 *
 * Storage can be missing or throw (private windows, blocked site data), so every access is
 * guarded and falls back to an in-memory value: the timer still works, just for this tab alone.
 */

export const LAST_ACTIVITY_KEY = 'nca:last-activity'

const minutes = Number.parseFloat(import.meta.env.VITE_IDLE_TIMEOUT_MINUTES)
/** How long without activity before sign-out. Overridable per deployment; 30 minutes otherwise. */
export const IDLE_TIMEOUT_MS = (Number.isFinite(minutes) && minutes > 0 ? minutes : 30) * 60_000
/** How long before sign-out the "Still there?" warning appears. Never more than half the limit. */
export const WARN_BEFORE_MS = Math.min(60_000, IDLE_TIMEOUT_MS / 2)

let inMemory = Date.now()

/** When anybody last did anything in this browser, in epoch ms. */
export function readLastActivity() {
    try {
        const stored = Number(window.localStorage.getItem(LAST_ACTIVITY_KEY))
        if (Number.isFinite(stored) && stored > 0) return stored
    } catch {
        // Storage unavailable; the in-memory value below is the clock.
    }
    return inMemory
}

/** Record activity now. Fails silently to the in-memory clock. */
export function recordActivity(now = Date.now()) {
    inMemory = now
    try {
        window.localStorage.setItem(LAST_ACTIVITY_KEY, String(now))
    } catch {
        // Storage unavailable or full; this tab still keeps time.
    }
}

/**
 * Where a session stands.
 *
 * @param {number} lastActivity Epoch ms of the last activity.
 * @param {number} now Epoch ms.
 * @returns {{phase: 'active'|'warning'|'expired', secondsLeft: number}}
 */
export function idlePhase(lastActivity, now) {
    const left = IDLE_TIMEOUT_MS - (now - lastActivity)
    if (left <= 0) return { phase: 'expired', secondsLeft: 0 }
    if (left <= WARN_BEFORE_MS) return { phase: 'warning', secondsLeft: Math.ceil(left / 1000) }
    return { phase: 'active', secondsLeft: Math.ceil(left / 1000) }
}

/** "30 minutes" for messages that name the limit. */
export const describeTimeout = () => {
    const mins = Math.round(IDLE_TIMEOUT_MS / 60_000)
    return `${mins} ${mins === 1 ? 'minute' : 'minutes'}`
}
