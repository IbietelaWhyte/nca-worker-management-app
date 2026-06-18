import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import { supabase } from '@/lib/supabaseClient'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { PasswordInput } from '@/components/ui/password-input'
import { Alert, AlertDescription } from '@/components/ui/alert'

export default function LoginPage() {
    const { signIn } = useAuth()
    const navigate = useNavigate()

    const [mode, setMode] = useState('signin') // 'signin' | 'forgot'
    const [email, setEmail] = useState('')
    const [password, setPassword] = useState('')
    const [error, setError] = useState(null)
    const [loading, setLoading] = useState(false)
    const [resetSent, setResetSent] = useState(false)

    const handleSubmit = async e => {
        e.preventDefault()
        setError(null)
        setLoading(true)
        try {
            await signIn(email, password)
            navigate('/')
        } catch (err) {
            setError(err.message)
        } finally {
            setLoading(false)
        }
    }

    const handleForgotSubmit = async e => {
        e.preventDefault()
        setError(null)
        setLoading(true)
        try {
            await supabase.auth.resetPasswordForEmail(email, {
                redirectTo: `${window.location.origin}/reset-password`,
            })
            // Neutral confirmation regardless of whether the email exists (avoids enumeration).
            setResetSent(true)
        } catch (err) {
            // Surface only unexpected/transport errors; never confirm/deny account existence.
            setError(err.message ?? 'Something went wrong. Please try again.')
        } finally {
            setLoading(false)
        }
    }

    const switchMode = next => {
        setMode(next)
        setError(null)
        setResetSent(false)
        setPassword('')
    }

    return (
        <div className="min-h-screen flex items-center justify-center bg-background">
            <div className="w-full max-w-sm space-y-6 p-8 border rounded-lg shadow-sm">
                <div className="space-y-2">
                    <h1 className="text-2xl font-bold">NCA Worker Management</h1>
                    <p className="text-muted-foreground text-sm">
                        {mode === 'signin' ? 'Sign in to your account' : 'Reset your password'}
                    </p>
                </div>

                {mode === 'signin' ? (
                    <form onSubmit={handleSubmit} className="space-y-4">
                        <div className="space-y-2">
                            <Label htmlFor="email">Email</Label>
                            <Input
                                id="email"
                                type="email"
                                autoComplete="email"
                                value={email}
                                onChange={e => setEmail(e.target.value)}
                                placeholder="you@example.com"
                            />
                        </div>

                        <div className="space-y-2">
                            <div className="flex items-center justify-between">
                                <Label htmlFor="password">Password</Label>
                                <button
                                    type="button"
                                    onClick={() => switchMode('forgot')}
                                    className="text-xs text-muted-foreground hover:text-foreground underline underline-offset-2"
                                >
                                    Forgot password?
                                </button>
                            </div>
                            <PasswordInput
                                id="password"
                                autoComplete="current-password"
                                value={password}
                                onChange={e => setPassword(e.target.value)}
                                placeholder="••••••••"
                            />
                        </div>

                        {error && <p className="text-sm text-destructive">{error}</p>}

                        <Button type="submit" disabled={loading} className="w-full">
                            {loading ? 'Signing in...' : 'Sign in'}
                        </Button>
                    </form>
                ) : resetSent ? (
                    <div className="space-y-4">
                        <Alert>
                            <AlertDescription>
                                If an account exists for that email, a password reset link is on its
                                way. Check your inbox.
                            </AlertDescription>
                        </Alert>
                        <Button
                            variant="outline"
                            className="w-full"
                            onClick={() => switchMode('signin')}
                        >
                            Back to sign in
                        </Button>
                    </div>
                ) : (
                    <form onSubmit={handleForgotSubmit} className="space-y-4">
                        <div className="space-y-2">
                            <Label htmlFor="reset_email">Email</Label>
                            <Input
                                id="reset_email"
                                type="email"
                                autoComplete="email"
                                value={email}
                                onChange={e => setEmail(e.target.value)}
                                placeholder="you@example.com"
                            />
                            <p className="text-xs text-muted-foreground">
                                We&apos;ll email you a link to reset your password.
                            </p>
                        </div>

                        {error && <p className="text-sm text-destructive">{error}</p>}

                        <Button type="submit" disabled={loading || !email} className="w-full">
                            {loading ? 'Sending...' : 'Send reset link'}
                        </Button>
                        <button
                            type="button"
                            onClick={() => switchMode('signin')}
                            className="w-full text-xs text-muted-foreground hover:text-foreground underline underline-offset-2"
                        >
                            Back to sign in
                        </button>
                    </form>
                )}
            </div>
        </div>
    )
}
