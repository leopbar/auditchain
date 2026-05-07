"use client"

import * as React from "react"
import { useEffect, useState } from "react"
import { Plus, Users } from "lucide-react"
import { toast } from "sonner"

import { UserTable } from "@/components/auth/user-table"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

/**
 * Administrative page for managing platform users.
 * Allows admins to view the user list, create new accounts, and deactive/delete existing ones.
 */
export default function UserManagementPage() {
  const [users, setUsers] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [isDialogOpen, setIsDialogOpen] = useState(false)
  
  // Form state for creating a new user
  const [formData, setFormData] = useState({
    full_name: "",
    email: "",
    password: "",
    role: "viewer",
  })

  // Fetch the user list from the backend
  async function fetchUsers() {
    try {
      const response = await fetch("http://localhost:8000/api/admin/users", {
        credentials: "include",
      })
      if (response.ok) {
        const data = await response.json()
        setUsers(data)
      } else {
        toast.error("Failed to fetch users.")
      }
    } catch (err) {
      console.error("Fetch users error:", err)
      toast.error("Network error while fetching users.")
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    fetchUsers()
  }, [])

  // Handle new user creation
  async function handleAddUser(e: React.FormEvent) {
    e.preventDefault()
    try {
      const response = await fetch("http://localhost:8000/api/admin/users", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(formData),
        credentials: "include",
      })

      if (response.ok) {
        toast.success("User created successfully.")
        setIsDialogOpen(false)
        setFormData({ full_name: "", email: "", password: "", role: "viewer" })
        fetchUsers()
      } else {
        const err = await response.json()
        toast.error(err.detail || "Failed to create user.")
      }
    } catch (err) {
      toast.error("Something went wrong.")
    }
  }

  // Handle user deactivation
  async function handleDeactivate(id: string) {
    try {
      const response = await fetch(`http://localhost:8000/api/admin/users/${id}/deactivate`, {
        method: "DELETE",
        credentials: "include",
      })
      if (response.ok) {
        toast.success("User account deactivated.")
        fetchUsers()
      } else {
        toast.error("Failed to deactivate user.")
      }
    } catch (err) {
      toast.error("Action failed.")
    }
  }

  // Handle user deletion
  async function handleDelete(id: string) {
    if (!window.confirm("Are you sure you want to permanently delete this user? This action cannot be undone.")) return

    try {
      const response = await fetch(`http://localhost:8000/api/admin/users/${id}`, {
        method: "DELETE",
        credentials: "include",
      })
      if (response.ok) {
        toast.success("User permanently deleted.")
        fetchUsers()
      } else {
        toast.error("Failed to delete user.")
      }
    } catch (err) {
      toast.error("Action failed.")
    }
  }

  return (
    <div className="container mx-auto py-10 px-6 space-y-8">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <Users className="h-6 w-6 text-neutral-900 dark:text-neutral-50" />
            <h1 className="text-3xl font-bold tracking-tight">User Management</h1>
          </div>
          <p className="text-neutral-500 dark:text-neutral-400">
            Control platform access, manage user roles, and monitor account status.
          </p>
        </div>

        <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
          <DialogTrigger asChild>
            <Button className="w-full sm:w-auto">
              <Plus className="mr-2 h-4 w-4" />
              Add User
            </Button>
          </DialogTrigger>
          <DialogContent className="sm:max-w-[425px]">
            <form onSubmit={handleAddUser}>
              <DialogHeader>
                <DialogTitle>Add New User</DialogTitle>
                <DialogDescription>
                  Enter account details below. Password will be securely hashed on the server.
                </DialogDescription>
              </DialogHeader>
              <div className="grid gap-4 py-4">
                <div className="grid gap-2">
                  <Label htmlFor="name">Full Name</Label>
                  <Input 
                    id="name" 
                    placeholder="John Doe"
                    value={formData.full_name} 
                    onChange={(e) => setFormData({...formData, full_name: e.target.value})} 
                    required 
                  />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="email">Email Address</Label>
                  <Input 
                    id="email" 
                    type="email" 
                    placeholder="john@example.com"
                    value={formData.email} 
                    onChange={(e) => setFormData({...formData, email: e.target.value})} 
                    required 
                  />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="password">Temporary Password</Label>
                  <Input 
                    id="password" 
                    type="password" 
                    value={formData.password} 
                    onChange={(e) => setFormData({...formData, password: e.target.value})} 
                    required 
                  />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="role">Access Level</Label>
                  <Select 
                    value={formData.role} 
                    onValueChange={(val) => setFormData({...formData, role: val})}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select role" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="viewer">Viewer (Read-only)</SelectItem>
                      <SelectItem value="admin">Administrator (Full access)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <DialogFooter>
                <Button type="submit" className="w-full">Create Account</Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      <UserTable 
        users={users} 
        onDeactivate={handleDeactivate} 
        onDelete={handleDelete} 
      />
    </div>
  )
}
