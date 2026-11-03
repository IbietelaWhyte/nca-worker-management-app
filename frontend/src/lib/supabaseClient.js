import { createClient } from '@supabase/supabase-js'

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL
// The publishable key (sb_publishable_...), which maps to the anon role: RLS is what limits it.
const supabasePublishableKey = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY

// Which emailed link this page load came from — 'recovery' (a password reset) or 'invite' (an
// admin's invite to set a first password) — or null. Read before createClient, which strips the
// token fragment (#access_token=...&type=recovery) once it has processed it — after that, a
// session from a link and an ordinary signed-in one look the same. This module is loaded by
// AuthContext at start-up, so it runs while the fragment is still there.
const linkType = new URLSearchParams(window.location.hash.slice(1)).get('type')
export const authLinkType = linkType === 'recovery' || linkType === 'invite' ? linkType : null

export const supabase = createClient(supabaseUrl, supabasePublishableKey)
