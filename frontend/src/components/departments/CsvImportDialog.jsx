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
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription } from '@/components/ui/alert'
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from '@/components/ui/table'
import { Download, Upload } from 'lucide-react'

const STATUS_BADGE = {
    valid: { variant: 'default', label: 'Will import' },
    created: { variant: 'default', label: 'Imported' },
    skipped_duplicate: { variant: 'secondary', label: 'Skipped' },
    error: { variant: 'destructive', label: 'Error' },
}

function StatusBadge({ status }) {
    const { variant, label } = STATUS_BADGE[status] ?? { variant: 'outline', label: status }
    return <Badge variant={variant}>{label}</Badge>
}

function ResultTable({ results }) {
    return (
        <div className="border rounded-md max-h-72 overflow-y-auto">
            <Table>
                <TableHeader>
                    <TableRow>
                        <TableHead className="w-12">#</TableHead>
                        <TableHead>Name</TableHead>
                        <TableHead>Email</TableHead>
                        <TableHead>Status</TableHead>
                    </TableRow>
                </TableHeader>
                <TableBody>
                    {results.map(row => (
                        <TableRow key={row.row_number}>
                            <TableCell className="text-muted-foreground">
                                {row.row_number}
                            </TableCell>
                            <TableCell>{row.name ?? '—'}</TableCell>
                            <TableCell className="text-muted-foreground">
                                {row.email ?? '—'}
                            </TableCell>
                            <TableCell>
                                <div className="flex flex-col gap-0.5">
                                    <StatusBadge status={row.status} />
                                    {row.error && (
                                        <span className="text-xs text-muted-foreground">
                                            {row.error}
                                        </span>
                                    )}
                                </div>
                            </TableCell>
                        </TableRow>
                    ))}
                </TableBody>
            </Table>
        </div>
    )
}

export default function CsvImportDialog({ open, onOpenChange, departmentId, onImported }) {
    const [file, setFile] = useState(null)
    const [preview, setPreview] = useState(null)
    const [committed, setCommitted] = useState(null)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState(null)

    const reset = () => {
        setFile(null)
        setPreview(null)
        setCommitted(null)
        setError(null)
        setLoading(false)
    }

    const handleOpenChange = next => {
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
            const response = await importWorkersCsv(departmentId, file, { dryRun: false })
            setCommitted(response.data)
            onImported?.()
        } catch (err) {
            setError(err.response?.data?.detail ?? 'Import failed')
        } finally {
            setLoading(false)
        }
    }

    const report = committed ?? preview

    return (
        <Dialog open={open} onOpenChange={handleOpenChange}>
            <DialogContent className="sm:max-w-2xl">
                <DialogHeader>
                    <DialogTitle>Import Workers from CSV</DialogTitle>
                    <DialogDescription>
                        Upload a CSV with columns <code>first_name, last_name, email, phone</code>.
                        New workers are created and added to this department; existing workers and
                        invalid rows are skipped.
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
                        <div className="space-y-3">
                            <p className="text-sm text-muted-foreground">
                                {committed
                                    ? `Imported ${report.created} of ${report.total_rows} rows.`
                                    : `${report.valid} of ${report.total_rows} rows ready to import.`}
                                {report.skipped_duplicate > 0 &&
                                    ` ${report.skipped_duplicate} skipped.`}
                                {report.errors > 0 && ` ${report.errors} with errors.`}
                            </p>
                            <ResultTable results={report.results} />
                        </div>
                    )}
                </div>

                <DialogFooter>
                    <Button variant="outline" onClick={() => handleOpenChange(false)}>
                        {committed ? 'Done' : 'Cancel'}
                    </Button>
                    {!committed && (
                        <Button
                            onClick={handleImport}
                            disabled={loading || !preview || preview.valid === 0}
                        >
                            <Upload size={16} className="mr-2" />
                            Import {preview?.valid ?? 0} worker{preview?.valid === 1 ? '' : 's'}
                        </Button>
                    )}
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
