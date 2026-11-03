/**
 * The password rule, mirrored from the Supabase auth policy so a person hears what is wrong
 * before submitting rather than after. Pure and React-free, like lib/idle.js.
 *
 * Supabase is the enforcer — production's policy is set in the dashboard, the local stack's in
 * supabase/config.toml (minimum_password_length, password_requirements) — so change them together.
 * A password this accepts and Supabase refuses still fails safely, with Supabase's own message.
 */

export const MIN_PASSWORD_LENGTH = 10

// GoTrue's symbol set for lower_upper_letters_digits_symbols. Anything outside it (a space, an
// accented letter, a pound sign) is allowed in a password but does not count as the symbol.
const SYMBOLS = '!@#$%^&*()_+-=[]{};\'\\:"|<>?,./`~'

export const PASSWORD_RULE = `At least ${MIN_PASSWORD_LENGTH} characters, with a lowercase letter, an uppercase letter, a number and a symbol (such as ! ? # or @).`

/**
 * What is wrong with a password, in words a volunteer can act on, or null when it passes.
 * @param {string} password
 * @returns {string | null}
 */
export function passwordProblem(password) {
    const missing = []
    if (!/[a-z]/.test(password)) missing.push('a lowercase letter')
    if (!/[A-Z]/.test(password)) missing.push('an uppercase letter')
    if (!/[0-9]/.test(password)) missing.push('a number')
    if (![...password].some(ch => SYMBOLS.includes(ch)))
        missing.push('a symbol (such as ! ? # or @)')

    const short = password.length < MIN_PASSWORD_LENGTH
    if (!short && missing.length === 0) return null

    const parts = []
    if (short) parts.push(`be at least ${MIN_PASSWORD_LENGTH} characters long`)
    if (missing.length) parts.push(`include ${joinWithAnd(missing)}`)
    return `Your password needs to ${parts.join(' and ')}.`
}

function joinWithAnd(items) {
    if (items.length === 1) return items[0]
    return `${items.slice(0, -1).join(', ')} and ${items[items.length - 1]}`
}
