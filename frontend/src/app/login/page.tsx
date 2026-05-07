import { Metadata } from "next"
import { LoginForm } from "@/components/auth/login-form"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

export const metadata: Metadata = {
  title: "Login | AuditChain",
  description: "Sign in to your AuditChain account",
}

export default function LoginPage() {
  return (
    <div className="container relative min-h-screen flex flex-col items-center justify-center lg:px-0">
      <div className="mx-auto flex w-full flex-col justify-center space-y-6 sm:w-[400px]">
        <div className="flex flex-col space-y-2 text-center">
          <h1 className="text-3xl font-bold tracking-tight text-neutral-900 dark:text-neutral-50">
            AuditChain
          </h1>
          <p className="text-sm text-neutral-500 dark:text-neutral-400">
            Forensic audit platform powered by AI
          </p>
        </div>
        
        <Card className="border-neutral-200 dark:border-neutral-800 shadow-lg">
          <CardHeader className="space-y-1">
            <CardTitle className="text-xl text-center">Sign In</CardTitle>
            <CardDescription className="text-center">
              Enter your credentials to access the platform
            </CardDescription>
          </CardHeader>
          <CardContent>
            <LoginForm />
          </CardContent>
        </Card>
        
        <p className="px-8 text-center text-xs text-neutral-500 dark:text-neutral-400">
          Secure access via encrypted JWT tokens.
        </p>
      </div>
    </div>
  )
}
