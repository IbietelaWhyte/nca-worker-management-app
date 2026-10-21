import { createClient } from '@supabase/supabase-js'

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY

// Whether this page load came from a password-reset email. Read before createClient, which
// strips the token fragment (#access_token=...&type=recovery) once it has processed it — after
// that, a recovery session and an ordinary signed-in one look the same. This module is loaded by
// AuthContext at start-up, so it runs while the fragment is still there.
export const openedFromRecoveryLink =
    new URLSearchParams(window.location.hash.slice(1)).get('type') === 'recovery'

export const supabase = createClient(supabaseUrl, supabaseAnonKey)
