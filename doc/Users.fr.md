# Gestion des accès

Les accès protégés sont gérés par les variables d'environnement :

```.env
AUTH_MODE=none | internal | external
ALLOW_ANONYMOUS_ACCESS=false
```

## None

Lorsque `AUTH_MODE` est défini sur `none`, aucune authentification n'est requise et toutes les fonctionnalités sont accessibles. L'identité virtuelle `local` porte le groupe `ADMIN`; la hiérarchie des rôles lui donne également les droits `EDITOR` et `VIEWER`. `/health` reste public.

En développement local, utilisez `FLASK_ENV=development`. En production, définir explicitement `AUTH_MODE=none` exige aussi `ALLOW_ANONYMOUS_ACCESS=true`; cette option est une confirmation consciente de l'absence d'authentification.

## Internal

Lorsque `AUTH_MODE` est défini sur `internal`, l'authentification interne est utilisée. Les groupes historiques `ADMIN`, `EDITOR` et `VIEWER` sont créés au démarrage; `EDITOR` correspond au niveau métier `EDITOR` et `VIEWER` au niveau `VIEWER`. La hiérarchie est `ADMIN > EDITOR > VIEWER` : `ADMIN` inclut `EDITOR`, qui inclut `VIEWER`. Un premier utilisateur disposant des droits d'administration est créé à partir des variables suivantes :

```.env
ADMIN_USERNAME=admin
ADMIN_PASSWORD=choose-a-strong-password
SECRET_KEY=replace-with-a-random-secret
```

`ADMIN_PASSWORD` est requis uniquement lors de la création effective du compte initial; il n'est ni réappliqué ni utilisé pour changer le mot de passe au redémarrage. Le bootstrap ne restaure pas le groupe `ADMIN` si un administrateur l'a retiré. `SECRET_KEY` doit être personnalisé avant d'activer ce mode.
`SECRET_KEY` doit être aléatoire, contenir au moins 32 caractères et rester identique entre les workers et les redémarrages. Le mot de passe est stocké sous forme de hash. Les connexions utilisent une session GeoReforge persistée en base.

Les échecs de connexion (compte inconnu, identifiants incomplets ou mot de passe incorrect) ont un délai uniforme de cinq secondes. Après six échecs consécutifs, le compte est verrouillé durablement. Le verrouillage n'a pas de route de déverrouillage ADMIN en V0 ; la méthode de service prévue pour un futur parcours ADMIN existe, et le déverrouillage actuel nécessite une intervention explicite en base. Un changement de mot de passe ou la désactivation d'un compte révoque ses sessions existantes.

## External

Dans le cas où `AUTH_MODE` est défini sur `external`, l'authentification externe est déléguée à un fournisseur d'identité externe, propre à l'architecture à laquelle l'application est intégrée.

Afin de fournir au système les informations nécessaires à l'authentification externe, les variables d'environnement suivantes doivent être configurées :

```.env
OIDC_ISSUER=
OIDC_CLIENT_ID=
OIDC_CLIENT_SECRET=
OIDC_REDIRECT_URI=https://georeforge.example.com/auth/callback
SECRET_KEY=replace-with-a-random-secret-of-at-least-32-characters
ENFORCE_SECURE_CONNECTION=true
```

L'URI de redirection doit pointer vers `/auth/callback`. La clé doit être aléatoire, persistante et partagée entre tous les workers. GeoReforge persiste une session locale après le retour du fournisseur. Les groupes OIDC nommés `ADMIN`, `EDITOR` et `VIEWER` sont associés aux groupes GeoReforge correspondants.

Les requêtes réseau OIDC ont un délai maximal de 10 secondes. Un compte local désactivé est refusé au callback sans synchronisation de groupes ni création de session; une panne réseau du fournisseur renvoie une erreur JSON 503 générique.

En V0, l'attribution de ces groupes dépend de la configuration et de la confiance accordée au fournisseur d'identité ; GeoReforge ne vérifie pas que le claim de groupes est réservé aux administrateurs. Les changements de groupes côté fournisseur ne sont pris en compte qu'à la prochaine connexion, et une session locale déjà créée peut rester valide jusqu'à son expiration (12 heures). Le durcissement du contrat OIDC, la validation de la source des groupes et la fraîcheur des droits sont prévus pour V1.

Au démarrage, GeoReforge mémorise le mode d'authentification et l'issuer. Un changement de mode ou d'issuer purge intégralement les comptes, groupes, associations, états de login, identités et sessions. Une base ancienne sans marqueur adopte le contexte configuré lors de sa première initialisation; les comptes existants sont conservés et leur provenance est migrée sans inventer de claims OIDC. Prévoir une sauvegarde avant tout changement de mode ou d'issuer.

## Connexion HTTPS et cookies

`ENFORCE_SECURE_CONNECTION` vaut `false` par défaut pour permettre le développement local en HTTP. En production derrière un proxy TLS, définissez-le à `true` : les requêtes HTTP reçoivent une réponse 403 sans redirection, sauf `/health` pour les sondes. Les cookies Flask et GeoReforge utilisent alors `Secure`; ils ont toujours `HttpOnly`, `SameSite=Lax` et `Path=/`. Les noms des deux cookies doivent être valides et distincts.

Le proxy TLS doit définir ou remplacer `X-Forwarded-Proto` par le protocole réellement utilisé par le client. Gunicorn ne doit faire confiance qu'aux adresses des proxies réels : configurez `FORWARDED_ALLOW_IPS` selon la topologie, sans valeur générique telle que `*`. Ne faites pas confiance à un en-tête transmis directement par un client.

## API et sessions

- `GET /auth/me` retourne l'identité courante; en mode `none`, il s'agit de l'administrateur virtuel `local`.
- `POST /auth/login` accepte `username` et `password` au format JSON en mode `internal`.
- `GET /auth/login` démarre la redirection OIDC en mode `external`.
- `POST /auth/logout` révoque la session courante.

La protection CSRF de Flask est active pour les requêtes POST. Appelez d'abord `GET /auth/csrf`, puis envoyez le jeton retourné dans l'en-tête `X-CSRFToken` avec la requête de connexion ou de déconnexion.

Les erreurs d'authentification, d'autorisation et de CSRF sont renvoyées en JSON. Toutes les réponses sous `/auth/`, y compris les erreurs et celles qui posent ou suppriment un cookie, utilisent `Cache-Control: no-store`.

## Administration des catalogues de zones

Les administrateurs peuvent supprimer une version construite ou toutes les versions d'un catalogue. La suppression est définitive : l'écran de confirmation propose un snapshot YAML à télécharger et exige une confirmation explicite avant l'opération. Les sources géographiques ne sont pas supprimées.

Le YAML d'une version contient sa définition importable ainsi qu'un snapshot complet des données `GeoForged` et `GeoForgedItem`. L'export du catalogue regroupe toutes ses versions. Un administrateur peut restaurer un snapshot depuis le catalogue ; les sources référencées doivent encore exister dans la base cible. Les identifiants techniques des lignes sont régénérés à la restauration. Le compteur de version est conservé après suppression pour éviter de réutiliser un numéro.
