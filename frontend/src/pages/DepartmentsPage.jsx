import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useDepartments } from '@/hooks/useDepartments'
import DepartmentForm from '@/components/departments/DepartmentForm'
import { Button } from '@/components/ui/button'
import { Alert } from '@/components/ui/alert'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from '@/components/ui/table'
import { Plus, Pencil, Trash2, ChevronRight } from 'lucide-react'

export default function DepartmentsPage() {
    const navigate = useNavigate()
    const { departments, loading, error, addDepartment, editDepartment, removeDepartment } =
        useDepartments()

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
    }

    const handleDelete = async dept => {
        if (!confirm(`Delete "${dept.name}"? This cannot be undone.`)) return
        await removeDepartment(dept.id)
    }

    if (loading) {
        return (
            <div className="flex items-center justify-center h-64">
                <p className="text-muted-foreground">Loading departments...</p>
            </div>
        )
    }

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold">Departments</h2>
                    <p className="text-muted-foreground text-sm mt-1">
                        {departments.length} total departments
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

            {!error && departments.length === 0 && (
                <div className="flex flex-col items-center justify-center h-64 border rounded-lg">
                    <p className="text-muted-foreground">No departments yet</p>
                    <Button variant="outline" className="mt-4" onClick={handleOpenCreate}>
                        Add your first department
                    </Button>
                </div>
            )}

            {departments.length > 0 && (
                <div className="border rounded-lg overflow-hidden">
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>Name</TableHead>
                                <TableHead>Description</TableHead>
                                <TableHead>Workers/Slot</TableHead>
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
                                    <TableCell>{dept.workers_per_slot}</TableCell>
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
                                                onClick={() => navigate(`/departments/${dept.id}`)}
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
