import { useState } from 'react'
import { importWorkersCsv } from '@/api/departments'
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
    DialogFooter,
} from '@/components/ui/dialog'
import { Button, buttonVariants } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Alert, AlertDescription } from '@/components/ui/alert'
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from '@/components/ui/table'
import { AlertTriangle, Check, CheckCircle2, Copy, Download, Upload } from 'lucide-react'

const plural = (count, noun) => `${count} ${noun}${count === 1 ? '' : 's'}`

/** Rows that block the import and must be fixed in the spreadsheet before re-uploading. */
function ErrorReport({ rows }) {
    const [copied, setCopied] = useState(false)

    const handleCopy = async () => {
        const text = rows.map(r => `Line ${r.line_number} — ${r.field}: ${r.error}`).join('\n')
        try {
            await navigator.clipboard.writeText(text)
            setCopied(true)
            setTimeout(() => setCopied(false), 2000)
        } catch {
            // Clipboard access can be blocked; the table below is still readable.
        }
    }

    return (
        <div className="space-y-2">
            <div className="flex items-center justify-between gap-2">
                <p className="text-sm font-medium text-destructive">
                    {plural(rows.length, 'row')} to fix
                </p>
                <Button variant="ghost" size="sm" onClick={handleCopy}>
                    {copied ? (
                        <Check size={14} className="mr-2" />
                    ) : (
                        <Copy size={14} className="mr-2" />
                    )}
                    {copied ? 'Copied' : 'Copy errors'}
                </Button>
            </div>
            <div className="border border-destructive/40 rounded-md max-h-56 overflow-y-auto">
                <Table>
                    <TableHeader>
                        <TableRow>
                            <TableHead className="w-16">Line</TableHead>
                            <TableHead className="w-28">Column</TableHead>
                            <TableHead>Problem</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {rows.map(row => (
                            <TableRow key={row.line_number}>
                                <TableCell className="text-muted-foreground">
                                    {row.line_number}
                                </TableCell>
                                <TableCell className="font-mono text-xs">
                                    {row.field ?? '—'}
                                </TableCell>
                                <TableCell>{row.error}</TableCell>
                            </TableRow>
                        ))}
                    </TableBody>
                </Table>
            </div>
        </div>
    )
}

/** Rows matching someone already in the system — not a mistake, just nothing to do. */
function DuplicateReport({ rows }) {
    return (
        <div className="space-y-2">
            <p className="text-sm font-medium">
                {plural(rows.length, 'row')} already in the system
            </p>
            <div className="border rounded-md max-h-48 overflow-y-auto">
                <Table>
                    <TableHeader>
                        <TableRow>
                            <TableHead className="w-16">Line</TableHead>
                            <TableHead>Name</TableHead>
                            <TableHead>Status</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {rows.map(row => (
                            <TableRow key={row.line_number}>
                                <TableCell className="text-muted-foreground">
                                    {row.line_number}
                                </TableCell>
                                <TableCell>{row.name ?? row.email ?? '—'}</TableCell>
                                <TableCell className="text-muted-foreground text-xs">
                                    {row.status === 'duplicate_inactive'
                                        ? 'Deactivated — reactivate them instead of re-importing'
                                        : 'Already added'}
                                </TableCell>
                            </TableRow>
                        ))}
                    </TableBody>
                </Table>
            </div>
        </div>
    )
}

/** Rows that will be created, shown so the count can be confirmed before anything is written. */
function ReadyReport({ rows, committed, blocked }) {
    // "Ready to import" would be a lie while errors elsewhere in the file are holding it back.
    const heading = committed
        ? `${plural(rows.length, 'worker')} imported`
        : blocked
          ? `${plural(rows.length, 'row')} with no problems — these will import once the errors above are fixed`
          : `${plural(rows.length, 'worker')} ready to import`

    return (
        <div className="space-y-2">
            <p className="text-sm font-medium">{heading}</p>
            <div className="border rounded-md max-h-56 overflow-y-auto">
                <Table>
                    <TableHeader>
                        <TableRow>
                            <TableHead className="w-16">Line</TableHead>
                            <TableHead>Name</TableHead>
                            <TableHead>Email</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {rows.map(row => (
                            <TableRow key={row.line_number}>
                                <TableCell className="text-muted-foreground">
                                    {row.line_number}
                                </TableCell>
                                <TableCell>{row.name ?? '—'}</TableCell>
                                <TableCell className="text-muted-foreground">
                                    {row.email ?? '—'}
                                </TableCell>
                            </TableRow>
                        ))}
                    </TableBody>
                </Table>
            </div>
        </div>
    )
}

export default function CsvImportDialog({ open, onOpenChange, departmentId, onImported }) {
    const [file, setFile] = useState(null)
    const [preview, setPreview] = useState(null)
    const [committed, setCommitted] = useState(null)
    const [skipDuplicates, setSkipDuplicates] = useState(false)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState(null)

    const reset = () => {
        setFile(null)
        setPreview(null)
        setCommitted(null)
        setSkipDuplicates(false)
        setError(null)
        setLoading(false)
    }

    const handleOpenChange = next => {
        // Don't let the dialog be dismissed mid-write; the report is the only record of what landed.
        if (loading) return
        if (!next) reset()
        onOpenChange(next)
    }

    const handleFileSelect = async event => {
        const selected = event.target.files?.[0]
        if (!selected) return
        setFile(selected)
        setError(null)
        setPreview(null)
        setCommitted(null)
        setSkipDuplicates(false)
        setLoading(true)
        try {
            const response = await importWorkersCsv(departmentId, selected, { dryRun: true })
            setPreview(response.data)
        } catch (err) {
            setError(err.response?.data?.detail ?? 'Failed to read the CSV file')
        } finally {
            setLoading(false)
        }
    }

    const handleImport = async () => {
        if (!file) return
        setLoading(true)
        setError(null)
        try {
            const response = await importWorkersCsv(departmentId, file, {
                dryRun: false,
                skipDuplicates,
            })
            setCommitted(response.data)
            onImported?.()
        } catch (err) {
            setError(err.response?.data?.detail ?? 'Import failed')
        } finally {
            setLoading(false)
        }
    }

    const report = committed ?? preview
    const rowsWith = (...statuses) => report?.results.filter(r => statuses.includes(r.status)) ?? []
    const errorRows = rowsWith('error')
    const duplicateRows = rowsWith('duplicate', 'duplicate_inactive')
    const readyRows = rowsWith('valid', 'created')

    const duplicatesBlocking = errorRows.length === 0 && duplicateRows.length > 0
    const nothingToImport = report && readyRows.length === 0 && errorRows.length === 0
    const canImport =
        !loading && !!preview && readyRows.length > 0 && (!duplicatesBlocking || skipDuplicates)

    return (
        <Dialog open={open} onOpenChange={handleOpenChange}>
            <DialogContent className="sm:max-w-2xl">
                <DialogHeader>
                    <DialogTitle>Import Workers from CSV</DialogTitle>
                    <DialogDescription>
                        Upload a CSV with the columns{' '}
                        <code>first_name, last_name, email, phone</code>. Every row must have all
                        four — if any row has a problem, nothing is imported until you fix it. Phone
                        numbers can be written any way you like.
                    </DialogDescription>
                </DialogHeader>

                <div className="space-y-4">
                    <div className="flex items-center justify-between gap-2">
                        <Input
                            type="file"
                            accept=".csv,text/csv"
                            onChange={handleFileSelect}
                            disabled={loading}
                            className="max-w-xs"
                        />
                        <a
                            href="/worker-import-sample.csv"
                            download
                            className={buttonVariants({ variant: 'ghost', size: 'sm' })}
                        >
                            <Download size={16} className="mr-2" /> Sample CSV
                        </a>
                    </div>

                    {error && (
                        <Alert variant="destructive">
                            <AlertDescription>{error}</AlertDescription>
                        </Alert>
                    )}

                    {loading && <p className="text-sm text-muted-foreground">Processing…</p>}

                    {report && (
                        <div className="space-y-4">
                            {committed ? (
                                <Alert>
                                    <CheckCircle2 size={16} />
                                    <AlertDescription>
                                        Imported {plural(report.created, 'worker')} into this
                                        department.
                                    </AlertDescription>
                                </Alert>
                            ) : errorRows.length > 0 ? (
                                <Alert variant="destructive">
                                    <AlertTriangle size={16} />
                                    <AlertDescription>
                                        Nothing was imported. Fix {plural(errorRows.length, 'row')}{' '}
                                        in your spreadsheet and upload it again.
                                    </AlertDescription>
                                </Alert>
                            ) : nothingToImport ? (
                                <Alert>
                                    <CheckCircle2 size={16} />
                                    <AlertDescription>
                                        All {plural(report.total_rows, 'row')} are already in the
                                        system — there is nothing to import.
                                    </AlertDescription>
                                </Alert>
                            ) : null}

                            {errorRows.length > 0 && <ErrorReport rows={errorRows} />}
                            {duplicateRows.length > 0 && <DuplicateReport rows={duplicateRows} />}
                            {readyRows.length > 0 && (
                                <ReadyReport
                                    rows={readyRows}
                                    committed={!!committed}
                                    blocked={errorRows.length > 0}
                                />
                            )}

                            {!committed && duplicatesBlocking && readyRows.length > 0 && (
                                <div className="flex items-start gap-2 rounded-md border p-3">
                                    <Checkbox
                                        id="skip-duplicates"
                                        checked={skipDuplicates}
                                        onCheckedChange={value => setSkipDuplicates(value === true)}
                                        disabled={loading}
                                    />
                                    <Label
                                        htmlFor="skip-duplicates"
                                        className="text-sm font-normal leading-snug"
                                    >
                                        Skip the {plural(duplicateRows.length, 'worker')} already in
                                        the system and import the other {readyRows.length}.
                                    </Label>
                                </div>
                            )}
                        </div>
                    )}
                </div>

                <DialogFooter>
                    <Button
                        variant="outline"
                        onClick={() => handleOpenChange(false)}
                        disabled={loading}
                    >
                        {committed ? 'Done' : 'Cancel'}
                    </Button>
                    {!committed && (
                        <Button onClick={handleImport} disabled={!canImport}>
                            <Upload size={16} className="mr-2" />
                            Import {plural(readyRows.length, 'worker')}
                        </Button>
                    )}
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
