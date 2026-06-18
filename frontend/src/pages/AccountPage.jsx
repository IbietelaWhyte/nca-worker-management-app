import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import { getMyProfile, updateMyProfile, changePassword, deleteMyAccount } from '@/api/account'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { PasswordInput } from '@/components/ui/password-input'
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog'
import { AlertTriangle } from 'lucide-react'

const MIN_PASSWORD_LENGTH = 8

function Section({ title, description, children }) {
    return (
        <section className="border rounded-lg p-6 space-y-4">
            <div className="space-y-1">
                <h2 className="text-lg font-semibold">{title}</h2>
                {description && <p className="text-sm text-muted-foreground">{description}</p>}
            </div>
            {children}
        </section>
    )
}

function errorDetail(err, fallback) {
    return err.response?.data?.detail ?? err.message ?? fallback
}

export default function AccountPage() {
    const { signOut } = useAuth()
    const navigate = useNavigate()

    // --- Profile ---
    const [profile, setProfile] = useState({ first_name: '', last_name: '', phone: '', email: '' })
    const [profileLoading, setProfileLoading] = useState(true)
    const [profileSaving, setProfileSaving] = useState(false)
    const [profileError, setProfileError] = useState(null)
    const [profileSuccess, setProfileSuccess] = useState(false)

    useEffect(() => {
        const load = async () => {
            try {
                const { data } = await getMyProfile()
                setProfile({
                    first_name: data.first_name ?? '',
                    last_name: data.last_name ?? '',
                    phone: data.phone ?? '',
                    email: data.email ?? '',
                })
            } catch (err) {
                setProfileError(errorDetail(err, 'Failed to load your profile'))
            } finally {
                setProfileLoading(false)
            }
        }
        load()
    }, [])

    const handleProfileSubmit = async e => {
        e.preventDefault()
        setProfileError(null)
        setProfileSuccess(false)
        setProfileSaving(true)
        try {
            await updateMyProfile({
                first_name: profile.first_name,
                last_name: profile.last_name,
                phone: profile.phone,
            })
            setProfileSuccess(true)
        } catch (err) {
            setProfileError(errorDetail(err, 'Failed to update your profile'))
        } finally {
            setProfileSaving(false)
        }
    }

    // --- Password ---
    const [passwords, setPasswords] = useState({ current: '', next: '', confirm: '' })
    const [passwordSaving, setPasswordSaving] = useState(false)
    const [passwordError, setPasswordError] = useState(null)
    const [passwordSuccess, setPasswordSuccess] = useState(false)

    const handlePasswordSubmit = async e => {
        e.preventDefault()
        setPasswordError(null)
        setPasswordSuccess(false)

        if (passwords.next.length < MIN_PASSWORD_LENGTH) {
            setPasswordError(`New password must be at least ${MIN_PASSWORD_LENGTH} characters`)
            return
        }
        if (passwords.next !== passwords.confirm) {
            setPasswordError('New password and confirmation do not match')
            return
        }

        setPasswordSaving(true)
        try {
            await changePassword({
                current_password: passwords.current,
                new_password: passwords.next,
            })
            setPasswordSuccess(true)
            setPasswords({ current: '', next: '', confirm: '' })
        } catch (err) {
            setPasswordError(errorDetail(err, 'Failed to change your password'))
        } finally {
            setPasswordSaving(false)
        }
    }

    // --- Delete ---
    const [deleteOpen, setDeleteOpen] = useState(false)
    const [deleting, setDeleting] = useState(false)
    const [deleteError, setDeleteError] = useState(null)

    const handleDelete = async () => {
        setDeleteError(null)
        setDeleting(true)
        try {
            await deleteMyAccount()
            await signOut()
            navigate('/login')
        } catch (err) {
            setDeleteError(errorDetail(err, 'Failed to delete your account'))
            setDeleting(false)
        }
    }

    return (
        <div className="max-w-2xl space-y-6">
            <div>
                <h1 className="text-2xl font-bold">Account</h1>
                <p className="text-muted-foreground text-sm mt-1">
                    Manage your profile, password, and account.
                </p>
            </div>

            {/* Profile */}
            <Section title="Profile" description="Update your name and phone number.">
                {profileLoading ? (
                    <p className="text-sm text-muted-foreground">Loading...</p>
                ) : (
                    <form onSubmit={handleProfileSubmit} className="space-y-4">
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <Label htmlFor="first_name">First name</Label>
                                <Input
                                    id="first_name"
                                    value={profile.first_name}
                                    onChange={e =>
                                        setProfile(p => ({ ...p, first_name: e.target.value }))
                                    }
                                />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="last_name">Last name</Label>
                                <Input
                                    id="last_name"
                                    value={profile.last_name}
                                    onChange={e =>
                                        setProfile(p => ({ ...p, last_name: e.target.value }))
                                    }
                                />
                            </div>
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="phone">Phone</Label>
                            <Input
                                id="phone"
                                value={profile.phone}
                                onChange={e => setProfile(p => ({ ...p, phone: e.target.value }))}
                            />
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="email">Email</Label>
                            <Input id="email" value={profile.email} disabled />
                            <p className="text-xs text-muted-foreground">
                                Email is your login identity and can&apos;t be changed here.
                            </p>
                        </div>

                        {profileError && (
                            <Alert variant="destructive">
                                <AlertDescription>{profileError}</AlertDescription>
                            </Alert>
                        )}
                        {profileSuccess && (
                            <Alert>
                                <AlertDescription>Profile updated.</AlertDescription>
                            </Alert>
                        )}

                        <Button type="submit" disabled={profileSaving}>
                            {profileSaving ? 'Saving...' : 'Save changes'}
                        </Button>
                    </form>
                )}
            </Section>

            {/* Password */}
            <Section
                title="Change password"
                description="Enter your current password, then a new one."
            >
                <form onSubmit={handlePasswordSubmit} className="space-y-4">
                    <div className="space-y-2">
                        <Label htmlFor="current_password">Current password</Label>
                        <PasswordInput
                            id="current_password"
                            autoComplete="current-password"
                            value={passwords.current}
                            onChange={e => setPasswords(p => ({ ...p, current: e.target.value }))}
                        />
                    </div>
                    <div className="space-y-2">
                        <Label htmlFor="new_password">New password</Label>
                        <PasswordInput
                            id="new_password"
                            autoComplete="new-password"
                            value={passwords.next}
                            onChange={e => setPasswords(p => ({ ...p, next: e.target.value }))}
                        />
                    </div>
                    <div className="space-y-2">
                        <Label htmlFor="confirm_password">Confirm new password</Label>
                        <PasswordInput
                            id="confirm_password"
                            autoComplete="new-password"
                            value={passwords.confirm}
                            onChange={e => setPasswords(p => ({ ...p, confirm: e.target.value }))}
                        />
                    </div>

                    {passwordError && (
                        <Alert variant="destructive">
                            <AlertDescription>{passwordError}</AlertDescription>
                        </Alert>
                    )}
                    {passwordSuccess && (
                        <Alert>
                            <AlertDescription>Password changed.</AlertDescription>
                        </Alert>
                    )}

                    <Button
                        type="submit"
                        disabled={
                            passwordSaving ||
                            !passwords.current ||
                            !passwords.next ||
                            !passwords.confirm
                        }
                    >
                        {passwordSaving ? 'Changing...' : 'Change password'}
                    </Button>
                </form>
            </Section>

            {/* Danger zone */}
            <Section
                title="Delete account"
                description="Deactivate your account and permanently revoke your access. Your scheduling history is preserved, but you won't be able to sign in again."
            >
                <Button
                    className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                    onClick={() => {
                        setDeleteError(null)
                        setDeleteOpen(true)
                    }}
                >
                    Delete my account
                </Button>
            </Section>

            <Dialog open={deleteOpen} onOpenChange={open => !deleting && setDeleteOpen(open)}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle className="flex items-center gap-2">
                            <AlertTriangle size={18} className="text-destructive" />
                            Delete your account?
                        </DialogTitle>
                        <DialogDescription>
                            This revokes your login immediately and signs you out. This can&apos;t
                            be undone by you — an administrator would have to restore your access.
                        </DialogDescription>
                    </DialogHeader>

                    {deleteError && (
                        <Alert variant="destructive">
                            <AlertDescription>{deleteError}</AlertDescription>
                        </Alert>
                    )}

                    <DialogFooter>
                        <Button
                            variant="outline"
                            onClick={() => setDeleteOpen(false)}
                            disabled={deleting}
                        >
                            Cancel
                        </Button>
                        <Button
                            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                            onClick={handleDelete}
                            disabled={deleting}
                        >
                            {deleting ? 'Deleting...' : 'Delete account'}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    )
}
