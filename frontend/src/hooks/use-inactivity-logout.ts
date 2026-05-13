"use client"

import { useEffect, useRef, useCallback } from "react"

const ACTIVITY_EVENTS = ["mousemove", "mousedown", "keydown", "scroll", "touchstart"] as const

export function useInactivityLogout(onLogout: () => void, timeoutMs = 30 * 60 * 1000) {
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const onLogoutRef = useRef(onLogout)
  onLogoutRef.current = onLogout

  const resetTimer = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => onLogoutRef.current(), timeoutMs)
  }, [timeoutMs])

  useEffect(() => {
    resetTimer()
    ACTIVITY_EVENTS.forEach((event) => window.addEventListener(event, resetTimer, { passive: true }))
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
      ACTIVITY_EVENTS.forEach((event) => window.removeEventListener(event, resetTimer))
    }
  }, [resetTimer])
}
