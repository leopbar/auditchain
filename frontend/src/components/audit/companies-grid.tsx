"use client";

import { useState } from "react";
import { CompanyCard } from "@/components/audit/company-card";
import { AddCompanyCard } from "@/components/audit/add-company-card";
import { AddCompanyModal } from "@/components/audit/add-company-modal";
import type { Company } from "@/types/audit";
import { motion, AnimatePresence } from "framer-motion";

interface CompaniesGridProps {
  companies: Company[];
}

/**
 * A client-side component to manage the companies grid and the add company flow.
 */
export function CompaniesGrid({ companies }: CompaniesGridProps) {
  const [modalOpen, setModalOpen] = useState(false);

  return (
    <>
      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        <AnimatePresence mode="popLayout">
          {companies.map((company, index) => (
            <motion.div
              key={company.cik}
              layout
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: index * 0.05 }}
              className="h-full w-full"
            >
              <CompanyCard company={company} />
            </motion.div>
          ))}

          {/* Always add the "Add Company" card at the end */}
          <motion.div
            layout
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: companies.length * 0.05 }}
            className="h-full w-full min-h-[200px]"
          >
            <AddCompanyCard onClick={() => setModalOpen(true)} />
          </motion.div>
        </AnimatePresence>
      </div>

      <AddCompanyModal open={modalOpen} onOpenChange={setModalOpen} />
    </>
  );
}
