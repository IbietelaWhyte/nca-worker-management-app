import { useCallback, useEffect, useRef, useState } from 'react'
import { useAuth } from '@/context/AuthContext'
import { LAST_ACTIVITY_KEY, idlePhase, readLastActivity, recordActivity } from '@/lib/idle'

// Checked this often; the warning's countdown ticks every second while it is open.
const CHECK_EVERY_MS = 15_000
// Mouse movement is the noisiest signal, so it writes at most this often.
const MOUSEMOVE_THROTTLE_MS = 15_000
const ACTIVITY_EVENTS = ['pointerdown', 'keydown', 'touchstart', 'wheel', 'scroll']

/**
 * Sign the person out of this browser after a spell with nothing happening in any tab.
 *
 * Once the warning is showing, activity in this tab does not dismiss it - a nudged mouse would
 * otherwise cancel a warning nobody read - and only Stay signed in does. Activity in another tab
 * does, through the storage event, since the person is clearly at the computer.
 *
 * @returns {{warning: boolean, secondsLeft: number, staySignedIn: () => void, signOutNow: () => void}}
 */
export function useIdleSignOut() {
    const { user, signOutLocally } = useAuth()
    // The id, not the user object: supabase-js hands back a new object on every hourly token
    // refresh, and keying on that would reset the idle clock each time - which an idle open tab
    // would never notice, and so would never be signed out.
    const userId = user?.id
    const [warning, setWarning] = useState(false)
    const [secondsLeft, setSecondsLeft] = useState(0)
    const warningRef = useRef(false)
    const lastMoveRef = useRef(0)

    const check = useCallback(() => {
        const { phase, secondsLeft: left } = idlePhase(readLastActivity(), Date.now())
        if (phase === 'expired') {
            warningRef.current = false
            setWarning(false)
            signOutLocally('idle')
            return
        }
        const warn = phase === 'warning'
        warningRef.current = warn
        setWarning(warn)
        setSecondsLeft(left)
    }, [signOutLocally])

    const staySignedIn = useCallback(() => {
        recordActivity()
        check()
    }, [check])

    useEffect(() => {
        if (!userId) return undefined
        // Judged at once, against the clock signIn started: reopening a tab long after the person
        // left signs them out rather than starting a new 30 minutes.
        check()

        const onActivity = event => {
            if (warningRef.current) return
            if (event.type === 'mousemove') {
                const now = Date.now()
                if (now - lastMoveRef.current < MOUSEMOVE_THROTTLE_MS) return
                lastMoveRef.current = now
            }
            recordActivity()
        }
        // Another tab recorded activity: the person is here, so drop this tab's warning too.
        const onStorage = event => {
            if (event.key === LAST_ACTIVITY_KEY) check()
        }
        // Coming back to a tab (or waking a laptop) is judged straight away, not on the next tick.
        const onVisible = () => {
            if (document.visibilityState === 'visible') check()
        }

        const events = [...ACTIVITY_EVENTS, 'mousemove']
        events.forEach(e => window.addEventListener(e, onActivity, { passive: true }))
        window.addEventListener('storage', onStorage)
        document.addEventListener('visibilitychange', onVisible)
        const interval = window.setInterval(check, CHECK_EVERY_MS)

        return () => {
            events.forEach(e => window.removeEventListener(e, onActivity))
            window.removeEventListener('storage', onStorage)
            document.removeEventListener('visibilitychange', onVisible)
            window.clearInterval(interval)
        }
    }, [userId, check])

    // The countdown needs a second-by-second tick, but only while the warning is up.
    useEffect(() => {
        if (!warning) return undefined
        const tick = window.setInterval(check, 1000)
        return () => window.clearInterval(tick)
    }, [warning, check])

    return {
        warning,
        secondsLeft,
        staySignedIn,
        // No reason: the person chose to leave, so the login page has nothing to explain.
        signOutNow: () => signOutLocally(null),
    }
}
