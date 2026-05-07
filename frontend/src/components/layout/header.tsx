"use client"

import * as React from "react"
import { useEffect, useState } from "react"
import Link from "next/link"
import { ShieldCheck, Users } from "lucide-react"

/**
 * Global application header.
 * Displays the logo and conditionally renders administrative links based on user role.
 */
export function Header() {
  const [isAdmin, setIsAdmin] = useState(false)

  // Check user role on mount to conditionally show admin links
  useEffect(() => {
    async function checkRole() {
      try {
        const response = await fetch("http://localhost:8000/auth/me", {
          credentials: "include",
        })
        if (response.ok) {
          const user = await response.json()
          setIsAdmin(user.role === "admin")
        }
      } catch (e) {
        // Silently fail: user is either not logged in or server is unreachable
      }
    }
    checkRole()
  }, [])

  return (
    <header className="border-b border-neutral-200 bg-white sticky top-0 z-40 dark:bg-neutral-950 dark:border-neutral-800">
      <div className="container mx-auto px-6 py-4 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-3 hover:opacity-80 transition-opacity">
          <div className="w-9 h-9 rounded-lg bg-neutral-900 flex items-center justify-center dark:bg-neutral-50">
            <ShieldCheck className="w-5 h-5 text-white dark:text-neutral-900" />
          </div>
          <div>
            <h1 className="text-base font-semibold text-neutral-900 dark:text-neutral-50">AuditChain</h1>
            <p className="text-xs text-neutral-500">Multi-agent SEC fraud detection</p>
          </div>
        </Link>
        
        <div className="flex items-center gap-6">
          {isAdmin && (
            <Link 
              href="/admin/users" 
              className="flex items-center gap-2 text-sm font-medium text-neutral-600 hover:text-neutral-900 dark:text-neutral-400 dark:hover:text-neutral-50 transition-colors"
            >
              <Users className="w-4 h-4" />
              User Management
            </Link>
          )}
          <div className="text-xs text-neutral-500 hidden sm:block">
            Powered by 5 specialized AI agents
          </div>
        </div>
      </div>
    </header>
  );
}
