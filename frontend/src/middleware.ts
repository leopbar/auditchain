import { NextResponse, type NextRequest } from 'next/server';

/**
 * Middleware for route protection and token refresh logic.
 * 
 * Logic:
 * 1. Exclude static files and /login.
 * 2. Check for access_token cookie.
 * 3. If missing, attempt to refresh via backend (using refresh_token cookie).
 * 4. Verify admin permissions for /admin routes.
 */

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const accessToken = request.cookies.get('access_token')?.value;

  // 1. Redirect to / if already logged in and trying to access /login
  if (pathname === '/login' && accessToken) {
    return NextResponse.redirect(new URL('/', request.url));
  }

  // Allow /login to pass through
  if (pathname === '/login') {
    return NextResponse.next();
  }

  // 2. Check if user is authenticated
  if (!accessToken) {
    // Attempt to refresh the token via backend
    try {
      // In production Docker, the backend is reachable via internal service name
      const backendUrl = process.env.INTERNAL_API_URL || 'http://localhost:8000';
      const refreshResponse = await fetch(`${backendUrl}/auth/refresh`, {
        method: 'POST',
        headers: {
          'Cookie': request.headers.get('cookie') || '',
        },
      });

      if (refreshResponse.ok) {
        // Refresh was successful, let the request proceed 
        // Note: The backend refresh endpoint sets the new access_token cookie in the response
        return NextResponse.next();
      }
    } catch (error) {
      console.error('Middleware refresh failed:', error);
    }

    // If refresh fails or token is missing, redirect to login
    return NextResponse.redirect(new URL('/login', request.url));
  }

  // 3. Admin Route Protection
  if (pathname.startsWith('/admin')) {
    const payload = decodeJwt(accessToken);
    if (!payload || payload.role !== 'admin') {
      console.warn(`Unauthorized admin access attempt to ${pathname} by role: ${payload?.role}`);
      return NextResponse.redirect(new URL('/', request.url));
    }
  }

  return NextResponse.next();
}

/**
 * Manually decode JWT payload in Edge Runtime (where atob is available but Node libs are not).
 */
function decodeJwt(token: string) {
  try {
    const payloadBase64 = token.split('.')[1];
    const decodedPayload = atob(payloadBase64.replace(/-/g, '+').replace(/_/g, '/'));
    return JSON.parse(decodedPayload);
  } catch (e) {
    return null;
  }
}

// Configure matcher to exclude static assets
export const config = {
  matcher: [
    /*
     * Match all request paths except for the ones starting with:
     * - api (API routes)
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     */
    '/((?!api|_next/static|_next/image|favicon.ico).*)',
  ],
};
