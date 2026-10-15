# Access Management

Protected access is configured through environment variables:

```.env
AUTH_MODE=none | internal | external
ALLOW_ANONYMOUS_ACCESS=false
```

## None

When `AUTH_MODE` is set to `none`, no authentication is required and all features are available. The virtual `local` identity has the `ADMIN` group; role inheritance also gives it `EDITOR` and `VIEWER` access. `/health` remains public.

For local development, use `FLASK_ENV=development`. In production, explicitly setting `AUTH_MODE=none` also requires `ALLOW_ANONYMOUS_ACCESS=true`, a deliberate confirmation that authentication is disabled.

## Internal

When `AUTH_MODE` is set to `internal`, internal authentication is used. The historical `ADMIN`, `EDITOR`, and `VIEWER` groups are created at startup; `EDITOR` is the business `EDITOR` level and `VIEWER` is the `VIEWER` level. The hierarchy is `ADMIN > EDITOR > VIEWER`: `ADMIN` includes `EDITOR`, which includes `VIEWER`. An initial administrator is created from the following variables:

```.env
ADMIN_USERNAME=admin
ADMIN_PASSWORD=choose-a-strong-password
SECRET_KEY=replace-with-a-random-secret
```

`ADMIN_PASSWORD` is required only when the initial account must actually be created; it is not reapplied or used to change the password on restart. Bootstrap does not restore the `ADMIN` group if an administrator has removed it. Set `SECRET_KEY` before enabling this mode.
`SECRET_KEY` must be random, at least 32 characters long, persistent across restarts, and shared by all workers. The password is stored as a secure hash. Logins use a GeoReforge session persisted in the database.

Failed logins (unknown account, incomplete credentials, or incorrect password) use a uniform five-second delay. After six consecutive failures, the account is locked persistently. V0 has no ADMIN unlock route; a service method intended for a future ADMIN workflow exists, and unlocking currently requires an explicit database intervention. Changing a password or disabling an account revokes its existing sessions.

## External

When `AUTH_MODE` is set to `external`, authentication is delegated to an external identity provider specific to the architecture into which the application is integrated.

To provide the system with the information required for external authentication, configure the following environment variables:

```.env
OIDC_ISSUER=
OIDC_CLIENT_ID=
OIDC_CLIENT_SECRET=
OIDC_REDIRECT_URI=https://georeforge.example.com/auth/callback
SECRET_KEY=replace-with-a-random-secret-of-at-least-32-characters
ENFORCE_SECURE_CONNECTION=true
```

The redirect URI must point to `/auth/callback`. The key must be random, persistent, and shared by all workers. GeoReforge persists a local session after the identity provider redirects back. OIDC groups named `ADMIN`, `EDITOR`, or `VIEWER` are mapped to the corresponding GeoReforge groups.

OIDC network requests have a 10-second timeout. A disabled local account is rejected during callback without synchronizing groups or creating a session; provider network failures return a generic JSON 503 response.

In V0, assignment of these groups relies on the identity provider's configuration and trust; GeoReforge does not verify that the groups claim is restricted to administrators. Provider-side group changes are applied only on the next login, and an existing local session can remain valid until it expires (12 hours). Hardening the OIDC contract, validating the source of group claims, and improving access-right freshness are deferred to V1.

At startup, GeoReforge records the authentication mode and issuer. Changing either purges all accounts, groups, memberships, login states, identity records, and sessions. A legacy database with no context marker adopts the configured context on first initialization; existing accounts are retained and their provenance is migrated without inventing OIDC claims. Back up the database before changing mode or issuer.

## HTTPS and Cookies

`ENFORCE_SECURE_CONNECTION` defaults to `false` for local HTTP development. In production behind a TLS proxy, set it to `true`: HTTP requests receive a 403 response without a redirect, except `/health` for probes. Flask and GeoReforge cookies then use `Secure`; both always use `HttpOnly`, `SameSite=Lax`, and `Path=/`. The two cookie names must be valid and distinct.

The TLS proxy must set or replace `X-Forwarded-Proto` with the protocol actually used by the client. Gunicorn must trust only the real proxy addresses: configure `FORWARDED_ALLOW_IPS` to match the topology, not a generic value such as `*`. Never trust a header passed directly by a client.

## API and Sessions

- `GET /auth/me` returns the current identity; in `none` mode, this is the virtual `local` administrator.
- `POST /auth/login` accepts JSON `username` and `password` in `internal` mode.
- `GET /auth/login` starts the OIDC redirect in `external` mode.
- `POST /auth/logout` revokes the current session.

Flask CSRF protection is enabled for POST requests. Call `GET /auth/csrf` first, then send the returned token in the `X-CSRFToken` header with login or logout requests.

Authentication, authorization, and CSRF errors are returned as JSON. Every `/auth/` response, including errors and responses setting or deleting a cookie, uses `Cache-Control: no-store`.
