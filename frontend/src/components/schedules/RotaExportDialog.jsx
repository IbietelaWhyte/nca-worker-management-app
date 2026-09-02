import { Fragment, useMemo, useRef, useState } from 'react'
import { format } from 'date-fns'
import { Download } from 'lucide-react'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useSubteams } from '@/hooks/useSubteams'
import { buildRota } from '@/lib/rota'

// The exported image is shared outside the app, so it is painted in fixed colours rather than
// theme tokens — it must look the same whoever produced it, in light mode or dark. The values
// are the church's own (newcovenantassembly.ca), so a rota forwarded to a WhatsApp group still
// reads as NCA. BORDER is the site's #C5C5C5 rather than the app's lighter rule: a printed or
// screenshotted grid needs the extra weight to hold its columns apart.
const INK = '#0F0F0F'
const BORDER = '#C5C5C5'
const PAPER = '#ffffff'
const HEADER_BG = '#662E91'
const HEADER_INK = '#ffffff'
const HIGHLIGHT = '#F8EDCB'

const cell = {
    border: `1px solid ${BORDER}`,
    padding: '4px 8px',
    verticalAlign: 'top',
    textAlign: 'left',
}

const slugify = value =>
    value
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-|-$/g, '')

/**
 * Export a month's rota as a shareable JPEG. What the dialog previews is the very node that gets
 * captured, so there is no second layout to keep in step.
 */
export default function RotaExportDialog({
    departmentId,
    departmentName,
    month,
    schedules,
    onClose,
}) {
    const { subteams } = useSubteams(departmentId)
    const [title, setTitle] = useState(`${departmentName} — ${format(month, 'MMMM yyyy')}`)
    const [busy, setBusy] = useState(false)
    const [error, setError] = useState(null)
    const sheetRef = useRef(null)

    const blocks = useMemo(() => buildRota(schedules, subteams), [schedules, subteams])

    const handleDownload = async () => {
        setError(null)
        setBusy(true)
        try {
            // Loaded on demand — the capture library is far larger than this page, and only
            // matters once someone actually asks for the image.
            const { domToJpeg } = await import('modern-screenshot')
            // Geist is a self-hosted variable font; capturing before it loads silently
            // substitutes a fallback face.
            await document.fonts.ready
            const dataUrl = await domToJpeg(sheetRef.current, {
                quality: 0.95,
                scale: 2,
                backgroundColor: PAPER,
            })
            const link = document.createElement('a')
            link.href = dataUrl
            link.download = `${slugify(title) || 'rota'}.jpg`
            link.click()
        } catch (err) {
            setError(err.message ?? 'Could not create the image')
        } finally {
            setBusy(false)
        }
    }

    return (
        <div className="space-y-4">
            <div className="space-y-2">
                <Label htmlFor="rota-title">Title</Label>
                <Input
                    id="rota-title"
                    value={title}
                    onChange={e => setTitle(e.target.value)}
                    placeholder="Title shown at the top of the image"
                />
            </div>

            {error && (
                <Alert variant="destructive">
                    <p className="text-sm">{error}</p>
                </Alert>
            )}

            {blocks.length === 0 ? (
                <Alert>
                    <p className="text-sm">
                        There are no schedules in {format(month, 'MMMM yyyy')} to export. Generate
                        the month first.
                    </p>
                </Alert>
            ) : (
                <div className="max-h-[55vh] overflow-auto rounded-md border">
                    <div
                        ref={sheetRef}
                        style={{ background: PAPER, padding: 16, width: 'fit-content' }}
                    >
                        <table
                            style={{
                                borderCollapse: 'collapse',
                                color: INK,
                                fontSize: 12,
                                fontFamily: 'Epilogue Variable, system-ui, sans-serif',
                            }}
                        >
                            <thead>
                                <tr>
                                    <th
                                        colSpan={3}
                                        style={{
                                            ...cell,
                                            textAlign: 'center',
                                            fontWeight: 700,
                                            padding: '8px',
                                            background: HEADER_BG,
                                            color: HEADER_INK,
                                            borderColor: HEADER_BG,
                                            letterSpacing: '0.04em',
                                            textTransform: 'uppercase',
                                        }}
                                    >
                                        {title}
                                    </th>
                                </tr>
                            </thead>
                            <tbody>
                                {blocks.map(block => (
                                    <Fragment key={block.date}>
                                        {block.rows.map((row, index) => (
                                            <tr key={row.key}>
                                                {index === 0 && (
                                                    <td
                                                        rowSpan={block.rows.length}
                                                        style={{
                                                            ...cell,
                                                            fontWeight: 700,
                                                            whiteSpace: 'nowrap',
                                                        }}
                                                    >
                                                        {block.label}
                                                    </td>
                                                )}
                                                <td
                                                    style={{
                                                        ...cell,
                                                        whiteSpace: 'nowrap',
                                                        paddingLeft: row.indented ? 24 : 8,
                                                        background: row.highlighted
                                                            ? HIGHLIGHT
                                                            : undefined,
                                                    }}
                                                >
                                                    {row.label}
                                                </td>
                                                <td
                                                    style={{
                                                        ...cell,
                                                        minWidth: 320,
                                                        background: row.highlighted
                                                            ? HIGHLIGHT
                                                            : undefined,
                                                    }}
                                                >
                                                    {row.names}
                                                </td>
                                            </tr>
                                        ))}
                                        {/* Blank spacer between dates, as on the printed rota. */}
                                        <tr>
                                            <td colSpan={3} style={{ height: 10 }} />
                                        </tr>
                                    </Fragment>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}

            <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={onClose} disabled={busy}>
                    Cancel
                </Button>
                <Button onClick={handleDownload} disabled={busy || blocks.length === 0}>
                    <Download size={16} className="mr-2" />
                    {busy ? 'Preparing…' : 'Download JPEG'}
                </Button>
            </div>
        </div>
    )
}
