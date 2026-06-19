import { f as AuthApiError, h as isAuthError, m as isAuthApiError, n as createAuthClient$1, p as AuthError, t as NeonAuthAdapterCore } from "./adapter-core-D4V1J06B-Bke6b8c5.js";
//#region node_modules/@neondatabase/auth/dist/supabase-adapter-BbSvEBy0.mjs
/**
* Internal implementation class - use BetterAuthVanillaAdapter factory function instead
*/
var BetterAuthVanillaAdapterImpl = class extends NeonAuthAdapterCore {
	_betterAuth;
	constructor(betterAuthClientOptions) {
		super(betterAuthClientOptions);
		this._betterAuth = createAuthClient$1(this.betterAuthOptions);
	}
	getBetterAuthInstance() {
		return this._betterAuth;
	}
};
/**
* Factory function that returns an adapter builder.
* The builder is called by createClient/createAuthClient with the URL.
*
* @param options - Optional adapter configuration (baseURL is injected separately)
* @returns A builder function that creates the adapter instance
*
* @example
* ```typescript
* const client = createClient({
*   auth: {
*     url: 'https://auth.example.com',
*     adapter: BetterAuthVanillaAdapter(),
*   },
*   dataApi: { url: 'https://data-api.example.com' },
* });
* ```
*/
function BetterAuthVanillaAdapter(options) {
	return (url, fetchOptions) => new BetterAuthVanillaAdapterImpl({
		baseURL: url,
		...options,
		fetchOptions: {
			...options?.fetchOptions,
			headers: {
				...options?.fetchOptions?.headers,
				...fetchOptions?.headers
			}
		}
	});
}
//#endregion
//#region node_modules/@neondatabase/auth/dist/neon-auth-BEYvHA5c.mjs
/**
* Create a NeonAuth instance that exposes the appropriate API based on the adapter.
*
* @param url - The auth service URL (e.g., 'https://auth.example.com')
* @param config - Configuration with adapter builder
* @returns NeonAuth instance with the adapter's API exposed directly
*
* @example SupabaseAuthAdapter - Supabase-compatible API
* ```typescript
* import { createAuthClient, SupabaseAuthAdapter } from '@neondatabase/auth';
*
* const auth = createAuthClient('https://auth.example.com', {
*   adapter: SupabaseAuthAdapter(),
* });
*
* // Supabase-compatible methods
* await auth.signInWithPassword({ email, password });
* await auth.getSession();
* ```
*
* @example BetterAuthVanillaAdapter - Direct Better Auth API
* ```typescript
* import { createAuthClient, BetterAuthVanillaAdapter } from '@neondatabase/auth';
*
* const auth = createAuthClient('https://auth.example.com', {
*   adapter: BetterAuthVanillaAdapter(),
* });
*
* // Direct Better Auth API access
* await auth.signIn.email({ email, password });
* await auth.signUp.email({ email, password, name: 'John' });
* await auth.getSession();
* ```
*
* @example BetterAuthReactAdapter - Better Auth with React hooks
* ```typescript
* import { createAuthClient, BetterAuthReactAdapter } from '@neondatabase/auth';
*
* const auth = createAuthClient('https://auth.example.com', {
*   adapter: BetterAuthReactAdapter(),
* });
*
* // Direct Better Auth API with React hooks
* await auth.signIn.email({ email, password });
* const session = auth.useSession(); // React hook
* ```
*/
function createInternalNeonAuth(url, config) {
	const adapterBuilder = config?.adapter ?? BetterAuthVanillaAdapter();
	const { fetchOptions } = config ?? {};
	const adapter = adapterBuilder(url, fetchOptions);
	const allowAnonymous = config?.allowAnonymous ?? false;
	if (!(typeof adapter.initialize === "function")) return {
		getJWTToken: () => adapter.getJWTToken(allowAnonymous),
		adapter: adapter.getBetterAuthInstance()
	};
	return {
		getJWTToken: () => adapter.getJWTToken(allowAnonymous),
		adapter
	};
}
function createAuthClient(url, config) {
	return createInternalNeonAuth(url, config).adapter;
}
//#endregion
export { AuthApiError, AuthError, createAuthClient, createInternalNeonAuth, isAuthApiError, isAuthError };

//# sourceMappingURL=@neondatabase_neon-js_auth.js.map