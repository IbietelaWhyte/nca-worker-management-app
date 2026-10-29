import { createContext, useContext, useEffect, useState } from 'react'
import { supabase } from '@/lib/supabaseClient'
import { signOutHere } from '@/lib/signOutReason'
import { recordActivity } from '@/lib/idle'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
    const [user, setUser] = useState(null)
    const [session, setSession] = useState(null)
    const [loading, setLoading] = useState(true)
    const role = session?.user?.app_metadata?.role ?? 'worker'
    const isAdmin = role === 'admin'
    const isDepartmentHead = role === 'hod' || role === 'assistant_hod' || role === 'admin'

    useEffect(() => {
        // Get the current session when the app first loads
        supabase.auth.getSession().then(({ data: { session } }) => {
            setSession(session)
            setUser(session?.user ?? null)
            setLoading(false)
        })

        // Listen for auth changes — login, logout, token refresh
        const {
            data: { subscription },
        } = supabase.auth.onAuthStateChange((_event, session) => {
            setSession(session)
            setUser(session?.user ?? null)
            setLoading(false)
        })

        // Cleanup the listener when the component unmounts
        return () => subscription.unsubscribe()
    }, [])

    const signIn = async (email, password) => {
        const { error } = await supabase.auth.signInWithPassword({
            email,
            password,
        })
        if (error) throw error
        // Signing in is the one moment the idle clock starts afresh. Every later page load is
        // judged against it instead, so a session left signed in on a computer and reopened the
        // next morning ends rather than getting another 30 minutes.
        recordActivity()
    }

    // The Sign out button: every session this person has, as before.
    const signOut = async () => {
        const { error } = await supabase.auth.signOut()
        if (error) throw error
    }

    const value = {
        user,
        session,
        loading,
        role,
        isAdmin,
        isDepartmentHead,
        signIn,
        signOut,
        // Idle and expired sessions: this browser only, with the reason the login page shows.
        signOutLocally: signOutHere,
    }

    return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
    const context = useContext(AuthContext)
    if (!context) {
        throw new Error('useAuth must be used within an AuthProvider')
    }
    return context
}
