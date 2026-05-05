"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { motion } from "framer-motion";

interface KPICardProps {
  label: string;
  value: string | number;
  icon: LucideIcon;
  subLabel?: string;
  variant?: "default" | "success" | "warning" | "danger";
  delay?: number;
}

export function KPICard({ 
  label, 
  value, 
  icon: Icon, 
  subLabel, 
  variant = "default",
  delay = 0 
}: KPICardProps) {
  const variantStyles = {
    default: "text-muted-foreground",
    success: "text-emerald-500",
    warning: "text-amber-500",
    danger: "text-rose-500",
  };

  const bgStyles = {
    default: "bg-muted/50",
    success: "bg-emerald-500/10",
    warning: "bg-amber-500/10",
    danger: "bg-rose-500/10",
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay }}
    >
      <Card className="overflow-hidden border-none bg-card/50 backdrop-blur-sm transition-all hover:bg-card/80">
        <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
          <CardTitle className="text-sm font-medium">{label}</CardTitle>
          <div className={cn("p-2 rounded-lg", bgStyles[variant])}>
            <Icon className={cn("w-4 h-4", variantStyles[variant])} />
          </div>
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold tracking-tight">{value}</div>
          {subLabel && (
            <p className="mt-1 text-xs text-muted-foreground">
              {subLabel}
            </p>
          )}
        </CardContent>
      </Card>
    </motion.div>
  );
}
