import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useDepartments } from '@/hooks/useDepartments'
import { useListParams } from '@/hooks/useListParams'
import { cn } from '@/lib/utils'
import DepartmentForm from '@/components/departments/DepartmentForm'
import { Button } from '@/components/ui/button'
import { Alert } from '@/components/ui/alert'
import { Input } from '@/components/ui/input'
import { Pagination } from '@/components/ui/pagination'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from '@/components/ui/table'
import { Plus, Pencil, Trash2, ChevronRight, Search } from 'lucide-react'
import { formatSlotRange } from '@/lib/staffing'

const PAGE_SIZE = 25

export default function DepartmentsPage() {
    const navigate = useNavigate()
    const list = useListParams()
    const {
        departments,
        total,
        loading,
        error,
        refetch,
        addDepartment,
        editDepartment,
        removeDepartment,
    } = useDepartments({
        search: list.q || undefined,
        limit: PAGE_SIZE,
        offset: (list.page - 1) * PAGE_SIZE,
    })

    // A delete can empty the last page; step back rather than show "nothing here" with a total.
    const { page, setPage } = list
    useEffect(() => {
        if (!loading && total > 0 && departments.length === 0 && page > 1) {
            setPage(Math.ceil(total / PAGE_SIZE))
        }
    }, [loading, total, departments.length, page, setPage])

    const [dialogOpen, setDialogOpen] = useState(false)
    const [editingDepartment, setEditingDepartment] = useState(null)

    const handleOpenCreate = () => {
        setEditingDepartment(null)
        setDialogOpen(true)
    }

    const handleOpenEdit = dept => {
        setEditingDepartment(dept)
        setDialogOpen(true)
    }

    const handleClose = () => {
        setDialogOpen(false)
        setEditingDepartment(null)
    }

    const handleSubmit = async formData => {
        if (editingDepartment) {
            await editDepartment(editingDepartment.id, formData)
        } else {
            await addDepartment(formData)
        }
        handleClose()
        refetch()
    }

    const handleDelete = async dept => {
        if (!confirm(`Delete "${dept.name}"? This cannot be undone.`)) return
        await removeDepartment(dept.id)
        refetch()
    }

    // Only the first load replaces the page; later fetches keep the search box mounted and focused.
    if (loading && total === null) {
        return (
            <div className="flex items-center justify-center h-64">
                <p className="text-muted-foreground">Loading departments...</p>
            </div>
        )
    }

    return (
        <div className="space-y-6">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                    <h2 className="text-2xl font-bold">Departments</h2>
                    <p className="text-muted-foreground text-sm mt-1">
                        {list.q ? `${total ?? 0} matching` : `${total ?? 0} total departments`}
                    </p>
                </div>
                <Button onClick={handleOpenCreate}>
                    <Plus size={16} className="mr-2" />
                    Add Department
                </Button>
            </div>

            {error && (
                <Alert variant="destructive">
                    <p className="text-sm">{error}</p>
                </Alert>
            )}

            <div className="relative sm:max-w-sm">
                <Search
                    size={16}
                    className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
                />
                <Input
                    value={list.searchText}
                    onChange={e => list.setSearchText(e.target.value)}
                    placeholder="Search departments"
                    aria-label="Search departments"
                    className="h-11 pl-9 sm:h-9"
                />
            </div>

            {!error && !loading && departments.length === 0 && list.hasFilters && (
                <div className="flex flex-col items-center justify-center h-64 border rounded-lg">
                    <p className="text-muted-foreground">
                        No departments match &ldquo;{list.q}&rdquo;
                    </p>
                    <Button variant="outline" className="mt-4" onClick={list.clear}>
                        Clear search
                    </Button>
                </div>
            )}

            {!error && !loading && departments.length === 0 && !list.hasFilters && (
                <div className="flex flex-col items-center justify-center h-64 border rounded-lg">
                    <p className="text-muted-foreground">No departments yet</p>
                    <Button variant="outline" className="mt-4" onClick={handleOpenCreate}>
                        Add your first department
                    </Button>
                </div>
            )}

            <div
                aria-busy={loading}
                className={cn('space-y-4 transition-opacity', loading && 'opacity-60')}
            >
                {departments.length > 0 && (
                    <div className="hidden border rounded-lg overflow-hidden md:block">
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead>Name</TableHead>
                                    <TableHead>Description</TableHead>
                                    <TableHead>Per service</TableHead>
                                    <TableHead className="text-right">Actions</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {departments.map(dept => (
                                    <TableRow
                                        key={dept.id}
                                        className="cursor-pointer"
                                        onClick={() => navigate(`/departments/${dept.id}`)}
                                    >
                                        <TableCell className="font-medium">{dept.name}</TableCell>
                                        <TableCell className="text-muted-foreground">
                                            {dept.description ?? '—'}
                                        </TableCell>
                                        <TableCell>
                                            {formatSlotRange(
                                                dept.min_workers_per_slot,
                                                dept.max_workers_per_slot
                                            )}
                                        </TableCell>
                                        <TableCell className="text-right">
                                            <div
                                                className="flex justify-end gap-2"
                                                onClick={e => e.stopPropagation()}
                                            >
                                                <Button
                                                    variant="outline"
                                                    size="sm"
                                                    onClick={() => handleOpenEdit(dept)}
                                                >
                                                    <Pencil size={14} className="mr-1" />
                                                    Edit
                                                </Button>
                                                <Button
                                                    variant="outline"
                                                    size="sm"
                                                    onClick={() => handleDelete(dept)}
                                                    className="text-destructive hover:text-destructive"
                                                >
                                                    <Trash2 size={14} className="mr-1" />
                                                    Delete
                                                </Button>
                                                <Button
                                                    variant="outline"
                                                    size="sm"
                                                    onClick={() =>
                                                        navigate(`/departments/${dept.id}`)
                                                    }
                                                >
                                                    <ChevronRight size={14} />
                                                </Button>
                                            </div>
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </div>
                )}

                {/* Below md the table becomes a card per department — four columns of which one is
                three buttons will not read on a phone, and scrolling sideways hides the actions. */}
                {departments.length > 0 && (
                    <ul className="space-y-2 md:hidden">
                        {departments.map(dept => (
                            <li key={dept.id} className="rounded-lg border p-4">
                                <button
                                    type="button"
                                    onClick={() => navigate(`/departments/${dept.id}`)}
                                    className="flex w-full items-start justify-between gap-3 text-left"
                                >
                                    <div className="min-w-0">
                                        <p className="font-medium">{dept.name}</p>
                                        <p className="truncate text-sm text-muted-foreground">
                                            {dept.description ?? '—'}
                                        </p>
                                        <p className="mt-1 text-xs text-muted-foreground">
                                            {formatSlotRange(
                                                dept.min_workers_per_slot,
                                                dept.max_workers_per_slot
                                            )}{' '}
                                            per service
                                        </p>
                                    </div>
                                    <ChevronRight
                                        size={18}
                                        className="mt-1 shrink-0 text-muted-foreground"
                                    />
                                </button>
                                <div className="mt-3 flex flex-wrap gap-2">
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={() => handleOpenEdit(dept)}
                                    >
                                        <Pencil size={14} className="mr-1" />
                                        Edit
                                    </Button>
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={() => handleDelete(dept)}
                                        className="text-destructive hover:text-destructive"
                                    >
                                        <Trash2 size={14} className="mr-1" />
                                        Delete
                                    </Button>
                                </div>
                            </li>
                        ))}
                    </ul>
                )}

                <Pagination
                    page={list.page}
                    pageSize={PAGE_SIZE}
                    total={total}
                    onPageChange={list.setPage}
                />
            </div>

            <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
                <DialogContent className="sm:max-w-md">
                    <DialogHeader>
                        <DialogTitle>
                            {editingDepartment ? 'Edit Department' : 'Add Department'}
                        </DialogTitle>
                    </DialogHeader>
                    <DepartmentForm
                        initial={editingDepartment ?? undefined}
                        onSubmit={handleSubmit}
                        onCancel={handleClose}
                    />
                </DialogContent>
            </Dialog>
        </div>
    )
}
