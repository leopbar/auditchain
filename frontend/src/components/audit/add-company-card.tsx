"use client";

import { Plus } from "lucide-react";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface AddCompanyCardProps {
  onClick: () => void;
  className?: string;
}

/**
 * A placeholder card that triggers the "Add Company" modal.
 * Styled to match the existing CompanyCard but with a dashed border.
 */
export function AddCompanyCard({ onClick, className }: AddCompanyCardProps) {
  return (
    <Card
      onClick={onClick}
      className={cn(
        "group relative h-full flex flex-col items-center justify-center p-8",
        "border-2 border-dashed border-neutral-200 bg-transparent",
        "hover:border-neutral-400 hover:bg-neutral-50 transition-all duration-300",
        "cursor-pointer overflow-hidden",
        className
      )}
    >
      <div className="flex flex-col items-center text-center space-y-4">
        <div className="p-4 rounded-full bg-neutral-100 text-neutral-400 group-hover:bg-neutral-200 group-hover:text-neutral-600 transition-colors duration-300">
          <Plus className="w-8 h-8" />
        </div>
        <div className="space-y-1">
          <h3 className="text-xl font-bold text-neutral-800 tracking-tight">
            Add Company
          </h3>
          <p className="text-sm text-neutral-500 max-w-[200px]">
            Audit any SEC-registered company by entering its CIK or ticker.
          </p>
        </div>
      </div>

      {/* Subtle bottom accent that appears on hover */}
      <div className="absolute bottom-0 left-0 right-0 h-1 bg-neutral-100 group-hover:bg-neutral-400 transition-colors duration-300" />
    </Card>
  );
}
