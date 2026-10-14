# Access Management

Protected access is configured through environment variables:

```.env
AUTH_MODE=none | internal | external
```

## None

When `AUTH_MODE` is set to `none`, no authentication is required to access the application, and all features are available to everyone who can access the user interface.

## Internal

When `AUTH_MODE` is set to `internal`, internal authentication is used. The `ADMIN`, `EDITOR`, and `VIEWER` groups are created at startup. An initial administrator is created from the following variables:

```.env
ADMIN_USERNAME=admin
ADMIN_PASSWORD=choose-a-strong-password
SECRET_KEY=replace-with-a-random-secret
```

Set both `ADMIN_PASSWORD` and `SECRET_KEY` before enabling this mode. The password is stored as a secure hash. Logins use a GeoReforge session persisted in the database.

## External

When `AUTH_MODE` is set to `external`, authentication is delegated to an external identity provider specific to the architecture into which the application is integrated.

To provide the system with the information required for external authentication, configure the following environment variables:

```.env
OIDC_ISSUER=
OIDC_CLIENT_ID=
OIDC_CLIENT_SECRET=
OIDC_REDIRECT_URI=https://georeforge.example.com/auth/callback
SECRET_KEY=replace-with-a-random-secret
AUTH_COOKIE_SECURE=true
```

The redirect URI must point to `/auth/callback`. Set a custom `SECRET_KEY`; set `AUTH_COOKIE_SECURE=true` when the application is served over HTTPS. GeoReforge persists a local session after the identity provider redirects back. OIDC groups named `ADMIN`, `EDITOR`, or `VIEWER` are mapped to the corresponding GeoReforge groups.

## API and Sessions

- `GET /auth/me` returns the current identity; in `none` mode, this is the virtual `local` administrator.
- `POST /auth/login` accepts JSON `username` and `password` in `internal` mode.
- `GET /auth/login` starts the OIDC redirect in `external` mode.
- `POST /auth/logout` revokes the current session.

Flask CSRF protection is enabled for POST requests. Call `GET /auth/csrf` first, then send the returned token in the `X-CSRFToken` header with login or logout requests.
