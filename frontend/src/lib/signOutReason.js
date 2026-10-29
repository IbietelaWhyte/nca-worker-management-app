import { supabase } from '@/lib/supabaseClient'

/**
 * Why the last sign-out happened, for the login page to explain. In memory, not storage: it only
 * has to survive the client-side redirect to /login, and it must not greet somebody next week.
 *
 * A module rather than React state because the 401 handler in api/client.js sets it from outside
 * any component.
 */

let reason = null

/** @param {'idle'|'expired'|null} next */
export const setSignOutReason = next => {
    reason = next
}

/** The reason, once: reading it clears it, so a refresh of the login page does not repeat it. */
export const takeSignOutReason = () => {
    const taken = reason
    reason = null
    return taken
}

let signingOut = null

/**
 * End this browser's session only and record why. `scope: 'local'` because idling at one
 * computer should not sign somebody out on their phone; the global default stays behind the
 * explicit Sign out button. Other tabs follow, since supabase-js broadcasts the sign-out.
 *
 * Several requests can 401 together; they share one sign-out rather than racing.
 *
 * @param {'idle'|'expired'|null} why Null when the person chose to sign out: nothing to explain.
 */
export const signOutHere = async why => {
    if (signingOut) return signingOut
    setSignOutReason(why)
    signingOut = supabase.auth
        .signOut({ scope: 'local' })
        .catch(() => {
            // The local session is cleared even when the network call fails; nothing to do.
        })
        .finally(() => {
            signingOut = null
        })
    return signingOut
}
