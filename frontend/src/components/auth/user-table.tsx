"use client"

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"

interface User {
  id: string
  email: string
  full_name: string | null
  role: string
  is_active: boolean
  created_at: string
}

interface UserTableProps {
  users: User[]
  onDeactivate: (id: string) => void
  onDelete: (id: string) => void
}

/**
 * Component to display a list of users in a structured table format.
 * Includes visual status indicators and action buttons for administrative tasks.
 */
export function UserTable({ users, onDeactivate, onDelete }: UserTableProps) {
  // Manual date formatting to avoid external dependencies
  const formatDate = (dateString: string) => {
    try {
      const date = new Date(dateString)
      const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
      return `${months[date.getMonth()]} ${date.getDate()}, ${date.getFullYear()}`
    } catch (e) {
      return "Invalid date"
    }
  }

  return (
    <div className="rounded-md border border-neutral-200 dark:border-neutral-800">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
            <TableHead>Email</TableHead>
            <TableHead>Role</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Created At</TableHead>
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {users.map((user) => (
            <TableRow key={user.id}>
              <TableCell className="font-medium">{user.full_name || "—"}</TableCell>
              <TableCell>{user.email}</TableCell>
              <TableCell>
                <Badge 
                  variant="outline"
                  className={user.role === 'admin' 
                    ? "border-purple-200 text-purple-700 bg-purple-50 dark:border-purple-800 dark:text-purple-300 dark:bg-purple-950" 
                    : "border-blue-200 text-blue-700 bg-blue-50 dark:border-blue-800 dark:text-blue-300 dark:bg-blue-950"}
                >
                  {user.role}
                </Badge>
              </TableCell>
              <TableCell>
                <Badge 
                  variant={user.is_active ? "default" : "secondary"}
                  className={user.is_active 
                    ? "bg-green-600 hover:bg-green-600 text-white dark:bg-green-700" 
                    : "bg-neutral-200 text-neutral-600 dark:bg-neutral-800 dark:text-neutral-400"}
                >
                  {user.is_active ? "Active" : "Inactive"}
                </Badge>
              </TableCell>
              <TableCell>{formatDate(user.created_at)}</TableCell>
              <TableCell className="text-right space-x-2">
                {user.is_active && (
                  <Button 
                    variant="outline" 
                    size="sm" 
                    onClick={() => onDeactivate(user.id)}
                    className="h-8 text-xs"
                  >
                    Deactivate
                  </Button>
                )}
                <Button 
                  variant="destructive" 
                  size="sm" 
                  onClick={() => onDelete(user.id)}
                  className="h-8 text-xs"
                >
                  Delete
                </Button>
              </TableCell>
            </TableRow>
          ))}
          {users.length === 0 && (
            <TableRow>
              <TableCell colSpan={6} className="text-center py-10 text-neutral-500">
                No users found.
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  )
}
