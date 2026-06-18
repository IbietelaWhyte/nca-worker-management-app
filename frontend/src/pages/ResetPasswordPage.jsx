import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { supabase } from '@/lib/supabaseClient'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { PasswordInput } from '@/components/ui/password-input'
import { Alert, AlertDescription } from '@/components/ui/alert'

const MIN_PASSWORD_LENGTH = 8

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
        // supabase-js parses the recovery token from the URL and emits PASSWORD_RECOVERY.
        const {
            data: { subscription },
        } = supabase.auth.onAuthStateChange((event, session) => {
            if (event === 'PASSWORD_RECOVERY' || session) setStatus('ready')
        })

        // Cover the case where the URL was already processed before we subscribed.
        supabase.auth.getSession().then(({ data: { session } }) => {
            setStatus(prev => (prev === 'ready' ? prev : session ? 'ready' : 'no-session'))
        })

        return () => subscription.unsubscribe()
    }, [])

    const handleSubmit = async e => {
        e.preventDefault()
        setError(null)

        if (password.length < MIN_PASSWORD_LENGTH) {
            setError(`Password must be at least ${MIN_PASSWORD_LENGTH} characters`)
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
        <div className="min-h-screen flex items-center justify-center bg-background">
            <div className="w-full max-w-sm space-y-6 p-8 border rounded-lg shadow-sm">
                <div className="space-y-2">
                    <h1 className="text-2xl font-bold">Reset password</h1>
                    <p className="text-muted-foreground text-sm">Choose a new password.</p>
                </div>

                {status === 'checking' && (
                    <p className="text-sm text-muted-foreground">Verifying your reset link...</p>
                )}

                {status === 'no-session' && (
                    <div className="space-y-4">
                        <Alert variant="destructive">
                            <AlertDescription>
                                This password reset link is invalid or has expired. Please request a
                                new one.
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
                                Your password has been reset. You can now sign in with your new
                                password.
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
                            <Label htmlFor="new_password">New password</Label>
                            <PasswordInput
                                id="new_password"
                                autoComplete="new-password"
                                value={password}
                                onChange={e => setPassword(e.target.value)}
                            />
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="confirm_password">Confirm new password</Label>
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
                            {saving ? 'Resetting...' : 'Reset password'}
                        </Button>
                    </form>
                )}
            </div>
        </div>
    )
}
