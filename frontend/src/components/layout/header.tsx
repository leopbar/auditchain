import { ShieldCheck } from "lucide-react";

export function Header() {
  return (
    <header className="border-b border-neutral-200 bg-white sticky top-0 z-40">
      <div className="container mx-auto px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-neutral-900 flex items-center justify-center">
            <ShieldCheck className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-base font-semibold text-neutral-900">AuditChain</h1>
            <p className="text-xs text-neutral-500">Multi-agent SEC fraud detection</p>
          </div>
        </div>
        <div className="text-xs text-neutral-500 hidden sm:block">
          Powered by 5 specialized AI agents
        </div>
      </div>
    </header>
  );
}
