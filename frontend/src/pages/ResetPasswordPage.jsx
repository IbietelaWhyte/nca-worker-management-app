import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { authLinkType, supabase } from '@/lib/supabaseClient'
import { PASSWORD_RULE, passwordProblem } from '@/lib/password'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { PasswordInput } from '@/components/ui/password-input'
import { Alert, AlertDescription } from '@/components/ui/alert'
import BrandMark from '@/components/layout/BrandMark'

// An invite lands here too: it is the same "choose a password without knowing the current one"
// step, just a first password rather than a replacement, so only the wording differs.
const isInvite = authLinkType === 'invite'

// status: 'checking' (resolving the recovery session) | 'ready' (can set a new password)
//         | 'no-session' (link missing/expired) | 'done' (password updated)
export default function ResetPasswordPage() {
    const navigate = useNavigate()
    const [status, setStatus] = useState('checking')
    const [password, setPassword] = useState('')
    const [confirm, setConfirm] = useState('')
    const [error, setError] = useState(null)
    const [saving, setSaving] = useState(false)

    useEffect(() => {
        // Only a session that arrived through a reset or invite link may set a password here
        // without the current one. Any signed-in session used to be enough, so somebody at an unattended,
        // signed-in browser could take the account over; changing a password while signed in is
        // the Account page's job, which asks for the current password.
        const {
            data: { subscription },
        } = supabase.auth.onAuthStateChange((event, session) => {
            if (event === 'PASSWORD_RECOVERY' || (session && authLinkType)) setStatus('ready')
        })

        // Cover the case where the URL was already processed before we subscribed.
        supabase.auth.getSession().then(({ data: { session } }) => {
            setStatus(prev =>
                prev === 'ready' ? prev : session && authLinkType ? 'ready' : 'no-session'
            )
        })

        return () => subscription.unsubscribe()
    }, [])

    const handleSubmit = async e => {
        e.preventDefault()
        setError(null)

        const problem = passwordProblem(password)
        if (problem) {
            setError(problem)
            return
        }
        if (password !== confirm) {
            setError('Passwords do not match')
            return
        }

        setSaving(true)
        try {
            const { error: updateError } = await supabase.auth.updateUser({ password })
            if (updateError) throw updateError
            setStatus('done')
            // Drop the temporary recovery session so the user signs in fresh.
            await supabase.auth.signOut()
        } catch (err) {
            setError(err.message ?? 'Failed to reset password. The link may have expired.')
        } finally {
            setSaving(false)
        }
    }

    return (
        <div className="min-h-dvh flex items-center justify-center bg-muted p-4">
            <div className="w-full max-w-sm space-y-6 rounded-2xl border bg-card p-8 shadow-md">
                <div className="space-y-4">
                    <BrandMark />
                    <div className="space-y-1">
                        <h1 className="text-2xl font-bold">
                            {isInvite ? 'Welcome' : 'Reset password'}
                        </h1>
                        <p className="text-muted-foreground text-sm">
                            {isInvite
                                ? 'Choose a password to finish setting up your account.'
                                : 'Choose a new password.'}
                        </p>
                    </div>
                </div>

                {status === 'checking' && (
                    <p className="text-sm text-muted-foreground">Verifying your link...</p>
                )}

                {status === 'no-session' && (
                    <div className="space-y-4">
                        <Alert variant="destructive">
                            <AlertDescription>
                                This link is invalid or has expired. If it was an invite, ask your
                                administrator to send a new one; for a password reset, request
                                another from the sign-in page. To change your password while signed
                                in, use your Account page.
                            </AlertDescription>
                        </Alert>
                        <Button
                            variant="outline"
                            className="w-full"
                            onClick={() => navigate('/login')}
                        >
                            Back to sign in
                        </Button>
                    </div>
                )}

                {status === 'done' && (
                    <div className="space-y-4">
                        <Alert>
                            <AlertDescription>
                                {isInvite
                                    ? 'Your password is set. You can now sign in with your email and new password.'
                                    : 'Your password has been reset. You can now sign in with your new password.'}
                            </AlertDescription>
                        </Alert>
                        <Button className="w-full" onClick={() => navigate('/login')}>
                            Go to sign in
                        </Button>
                    </div>
                )}

                {status === 'ready' && (
                    <form onSubmit={handleSubmit} className="space-y-4">
                        <div className="space-y-2">
                            <Label htmlFor="new_password">
                                {isInvite ? 'Password' : 'New password'}
                            </Label>
                            <PasswordInput
                                id="new_password"
                                autoComplete="new-password"
                                value={password}
                                onChange={e => setPassword(e.target.value)}
                            />
                            <p className="text-xs text-muted-foreground">{PASSWORD_RULE}</p>
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="confirm_password">
                                {isInvite ? 'Confirm password' : 'Confirm new password'}
                            </Label>
                            <PasswordInput
                                id="confirm_password"
                                autoComplete="new-password"
                                value={confirm}
                                onChange={e => setConfirm(e.target.value)}
                            />
                        </div>

                        {error && <p className="text-sm text-destructive">{error}</p>}

                        <Button
                            type="submit"
                            disabled={saving || !password || !confirm}
                            className="w-full"
                        >
                            {saving ? 'Saving...' : isInvite ? 'Set password' : 'Reset password'}
                        </Button>
                    </form>
                )}
            </div>
        </div>
    )
}
