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

  // 1. Redirect to / if already logged in (with valid token) and trying to access /login
  if (pathname === '/login' && accessToken) {
    const payload = decodeJwt(accessToken);
    const isExpired = !payload || (payload.exp && payload.exp * 1000 < Date.now());
    if (!isExpired) {
      return NextResponse.redirect(new URL('/', request.url));
    }
  }

  // Allow /login to pass through
  if (pathname === '/login') {
    return NextResponse.next();
  }

  // 2. Check if user is authenticated (token missing or expired)
  const tokenPayload = accessToken ? decodeJwt(accessToken) : null;
  const tokenExpired = !tokenPayload || (tokenPayload.exp && tokenPayload.exp * 1000 < Date.now());

  if (!accessToken || tokenExpired) {
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
        const setCookie = refreshResponse.headers.get('set-cookie');

        // Inject the new access_token into the request headers so server
        // components receive the refreshed token during this same render cycle
        const requestHeaders = new Headers(request.headers);
        if (setCookie) {
          const newToken = setCookie.match(/access_token=([^;]+)/)?.[1];
          if (newToken) {
            const existing = request.headers.get('cookie') || '';
            const updated = existing
              .split('; ')
              .filter(c => !c.startsWith('access_token='))
              .concat(`access_token=${newToken}`)
              .join('; ');
            requestHeaders.set('cookie', updated);
          }
        }

        const next = NextResponse.next({ request: { headers: requestHeaders } });
        // Also forward the Set-Cookie to the browser for subsequent requests
        if (setCookie) {
          next.headers.set('set-cookie', setCookie);
        }
        return next;
      }
    } catch (error) {
      console.error('Middleware refresh failed:', error);
    }

    // If refresh fails or token is missing/expired, redirect to login
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
