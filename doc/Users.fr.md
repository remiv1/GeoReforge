# Gestion des accès

Les accès protégés sont gérés par les variables d'environnement :

```.env
AUTH_MODE=none | internal | external
```

## None

Lorsque `AUTH_MODE` est défini sur `none`, aucune authentification n'est requise pour accéder à l'application et toutes les fonctionnalités sont disponibles pour l'ensemble des utilisateurs ayant accès à l'interface utilisateur.

## Internal

Lorsque `AUTH_MODE` est défini sur `internal`, l'authentification interne est utilisée. Les groupes `ADMIN`, `EDITOR` et `VIEWER` sont créés au démarrage. Un premier utilisateur disposant des droits d'administration est créé à partir des variables suivantes :

```.env
ADMIN_USERNAME=admin
ADMIN_PASSWORD=choose-a-strong-password
SECRET_KEY=replace-with-a-random-secret
```

`ADMIN_PASSWORD` et `SECRET_KEY` doivent être personnalisés avant d'activer ce mode. Le mot de passe est stocké sous forme de hash. Les connexions utilisent une session GeoReforge persistée en base.

## External

Dans le cas où `AUTH_MODE` est défini sur `external`, l'authentification externe est déléguée à un fournisseur d'identité externe, propre à l'architecture à laquelle l'application est intégrée.

Afin de fournir au système les informations nécessaires à l'authentification externe, les variables d'environnement suivantes doivent être configurées :

```.env
OIDC_ISSUER=
OIDC_CLIENT_ID=
OIDC_CLIENT_SECRET=
OIDC_REDIRECT_URI=https://georeforge.example.com/auth/callback
SECRET_KEY=replace-with-a-random-secret
AUTH_COOKIE_SECURE=true
```

L'URI de redirection doit pointer vers `/auth/callback`. `SECRET_KEY` doit être personnalisé; définissez `AUTH_COOKIE_SECURE=true` lorsque l'application est servie en HTTPS. GeoReforge persiste une session locale après le retour du fournisseur. Les groupes OIDC nommés `ADMIN`, `EDITOR` et `VIEWER` sont associés aux groupes GeoReforge correspondants.

## API et sessions

- `GET /auth/me` retourne l'identité courante; en mode `none`, il s'agit de l'administrateur virtuel `local`.
- `POST /auth/login` accepte `username` et `password` au format JSON en mode `internal`.
- `GET /auth/login` démarre la redirection OIDC en mode `external`.
- `POST /auth/logout` révoque la session courante.

La protection CSRF de Flask est active pour les requêtes POST. Appelez d'abord `GET /auth/csrf`, puis envoyez le jeton retourné dans l'en-tête `X-CSRFToken` avec la requête de connexion ou de déconnexion.
