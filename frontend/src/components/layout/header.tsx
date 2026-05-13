"use client"

import * as React from "react"
import { useEffect, useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { ShieldCheck, Users, LogOut } from "lucide-react"
import { Button } from "@/components/ui/button"
import { API_BASE_URL } from "@/lib/api/client"
import { useInactivityLogout } from "@/hooks/use-inactivity-logout"

/**
 * Global application header.
 * Displays the logo, administrative links, and session controls.
 */
export function Header() {
  const router = useRouter()
  const [isAdmin, setIsAdmin] = useState(false)
  const [user, setUser] = useState<{ email: string; full_name: string | null } | null>(null)

  // Handle session termination (defined before useInactivityLogout so it can be passed in)
  const handleLogout = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/auth/logout`, {
        method: "POST",
        credentials: "include",
      })
      if (response.ok) {
        router.push("/login")
        router.refresh()
      }
    } catch (e) {
      console.error("Logout error:", e)
    }
  }

  useInactivityLogout(handleLogout)

  // Check user session and role on mount
  useEffect(() => {
    async function checkAuth() {
      try {
        const response = await fetch(`${API_BASE_URL}/auth/me`, {
          credentials: "include",
        })
        if (response.ok) {
          const userData = await response.json()
          setUser(userData)
          setIsAdmin(userData.role === "admin")
        }
      } catch (e) {
        // Silently fail: user is either not logged in or server is unreachable
      }
    }
    checkAuth()
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

          {user ? (
            <div className="flex items-center gap-4">
              <div className="hidden md:block text-right">
                <p className="text-xs font-medium text-neutral-900 dark:text-neutral-50">
                  {user.full_name || user.email}
                </p>
                <p className="text-[10px] text-neutral-500">Active Session</p>
              </div>
              <Button 
                variant="ghost" 
                size="icon" 
                onClick={handleLogout}
                className="text-neutral-500 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-950/30"
                title="Logout"
              >
                <LogOut className="w-5 h-5" />
              </Button>
            </div>
          ) : (
            <div className="text-xs text-neutral-500 hidden sm:block">
              Powered by 5 specialized AI agents
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
