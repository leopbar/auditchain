"use client"

import * as React from "react"
import { useEffect, useState } from "react"
import { DollarSign, RefreshCw, ArrowLeft } from "lucide-react"
import { useRouter } from "next/navigation"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { API_BASE_URL } from "@/lib/api/client"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"

interface ModelPrice {
  model_name: string
  input_cost_per_1m: number
  output_cost_per_1m: number
  source: string | null
  updated_at: string | null
}

interface PriceChange {
  model_name: string
  old_input_per_1m: number | null
  old_output_per_1m: number | null
  new_input_per_1m: number
  new_output_per_1m: number
}

interface RefreshResponse {
  status: string
  message: string
  changes: PriceChange[]
  source_url: string | null
  prices: ModelPrice[]
}

interface RefreshResult {
  status: string
  message: string
  changes: PriceChange[]
}

const usd = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 2,
  maximumFractionDigits: 4,
})

function formatDate(value: string | null): string {
  if (!value) return "—"
  try {
    const date = new Date(value)
    const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    return `${months[date.getMonth()]} ${date.getDate()}, ${date.getFullYear()}`
  } catch {
    return "Invalid date"
  }
}

/**
 * Administrative page for LLM token pricing.
 *
 * Token counts are measured by the API; the per-token price is published by
 * OpenAI (no official API), so prices are stored locally and can be refreshed
 * by scraping OpenAI's pricing page. If a refresh fails, existing prices are
 * kept and the admin is told — no fabricated numbers.
 */
export default function ModelPricingPage() {
  const router = useRouter()
  const [prices, setPrices] = useState<ModelPrice[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [result, setResult] = useState<RefreshResult | null>(null)
  const [dialogOpen, setDialogOpen] = useState(false)

  useEffect(() => {
    let cancelled = false

    async function load() {
      try {
        const response = await fetch(`${API_BASE_URL}/api/admin/pricing`, {
          credentials: "include",
        })
        if (cancelled) return
        if (response.ok) {
          const data = await response.json()
          if (!cancelled) setPrices(data.prices ?? [])
        } else {
          toast.error("Failed to load prices.")
        }
      } catch (err) {
        console.error("Fetch prices error:", err)
        toast.error("Network error while loading prices.")
      } finally {
        if (!cancelled) setIsLoading(false)
      }
    }

    load()
    return () => {
      cancelled = true
    }
  }, [])

  async function handleRefresh() {
    setIsRefreshing(true)
    try {
      const response = await fetch(`${API_BASE_URL}/api/admin/pricing/refresh`, {
        method: "POST",
        credentials: "include",
      })

      if (!response.ok) {
        setResult({
          status: "error",
          message:
            "Update failed: the server could not be reached. Please contact the administrator.",
          changes: [],
        })
        setDialogOpen(true)
        return
      }

      const data: RefreshResponse = await response.json()
      setPrices(data.prices ?? [])
      setResult({
        status: data.status,
        message: data.message,
        changes: data.changes ?? [],
      })
      setDialogOpen(true)
    } catch (err) {
      console.error("Refresh prices error:", err)
      setResult({
        status: "error",
        message:
          "Update failed: a network error occurred. Please contact the administrator.",
        changes: [],
      })
      setDialogOpen(true)
    } finally {
      setIsRefreshing(false)
    }
  }

  const isError = result?.status === "error"
  const dialogTitle = isError ? "Update failed" : "Update completed"

  return (
    <div className="container mx-auto py-10 px-6 space-y-8">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="space-y-1">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => router.push("/")}
            className="mb-2 h-8 text-neutral-500 hover:text-neutral-900 -ml-2"
          >
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Dashboard
          </Button>
          <div className="flex items-center gap-2">
            <DollarSign className="h-6 w-6 text-neutral-900 dark:text-neutral-50" />
            <h1 className="text-3xl font-bold tracking-tight">Model Pricing</h1>
          </div>
          <p className="text-neutral-500 dark:text-neutral-400 max-w-2xl">
            Per-model token prices (USD per 1M tokens) used to compute audit cost.
            OpenAI has no pricing API, so values are refreshed by reading OpenAI&apos;s
            public pricing page. If a refresh fails, current prices are kept.
          </p>
        </div>

        <Button
          onClick={handleRefresh}
          disabled={isRefreshing}
          className="w-full sm:w-auto"
        >
          <RefreshCw className={`mr-2 h-4 w-4 ${isRefreshing ? "animate-spin" : ""}`} />
          {isRefreshing ? "Updating from OpenAI…" : "Update prices from OpenAI"}
        </Button>
      </div>

      <div className="rounded-md border border-neutral-200 dark:border-neutral-800">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Model</TableHead>
              <TableHead className="text-right">Input / 1M tokens</TableHead>
              <TableHead className="text-right">Output / 1M tokens</TableHead>
              <TableHead>Source</TableHead>
              <TableHead>Updated</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {prices.map((price) => (
              <TableRow key={price.model_name}>
                <TableCell className="font-medium">{price.model_name}</TableCell>
                <TableCell className="text-right tabular-nums">
                  {usd.format(price.input_cost_per_1m)}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {usd.format(price.output_cost_per_1m)}
                </TableCell>
                <TableCell className="text-neutral-500 text-sm">
                  {price.source || "—"}
                </TableCell>
                <TableCell className="text-neutral-500 text-sm">
                  {formatDate(price.updated_at)}
                </TableCell>
              </TableRow>
            ))}
            {!isLoading && prices.length === 0 && (
              <TableRow>
                <TableCell colSpan={5} className="text-center py-10 text-neutral-500">
                  No prices configured.
                </TableCell>
              </TableRow>
            )}
            {isLoading && (
              <TableRow>
                <TableCell colSpan={5} className="text-center py-10 text-neutral-500">
                  Loading prices…
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-[480px]">
          <DialogHeader>
            <DialogTitle>{dialogTitle}</DialogTitle>
            <DialogDescription>{result?.message}</DialogDescription>
          </DialogHeader>

          {result && result.changes.length > 0 && (
            <div className="space-y-2 rounded-md border border-neutral-200 dark:border-neutral-800 p-3 max-h-60 overflow-y-auto">
              {result.changes.map((c) => (
                <div key={c.model_name} className="text-sm">
                  <span className="font-medium">{c.model_name}</span>
                  <div className="text-neutral-500 tabular-nums">
                    input:{" "}
                    {c.old_input_per_1m != null ? usd.format(c.old_input_per_1m) : "—"}{" "}
                    → {usd.format(c.new_input_per_1m)} · output:{" "}
                    {c.old_output_per_1m != null ? usd.format(c.old_output_per_1m) : "—"}{" "}
                    → {usd.format(c.new_output_per_1m)}
                  </div>
                </div>
              ))}
            </div>
          )}

          <DialogFooter>
            <Button onClick={() => setDialogOpen(false)}>OK</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
