# AJPLAY Catalog Worker

Worker API for private catalog JSON in R2.

## Routes
- `GET /health`: readiness/configuration status.
- `GET /v1/catalog/{userId}`: reads the user's JSON catalog.
- `PUT /v1/catalog/{userId}`: validates an array JSON and publishes it to R2.

## Required R2 binding
The binding in `wrangler.toml` is named `CATALOGS` and points to the private bucket `ajplay-catalogs`.

## Required Worker secrets
Set two different high-entropy secrets:
- `CATALOG_READ_TOKEN`
- `CATALOG_WRITE_TOKEN`

Do not put these values in this repository. The write token is for GitHub Actions only. The read token must be provisioned to the Android client through a secure authenticated channel; never hard-code it in the APK.

## Deploy after enabling R2
From this directory, install Wrangler and deploy:
```bash
npx wrangler deploy
```

After deployment, test `/health`; it must report both storage and auth configured. Test unauthorized GET/PUT returns 401, authorized GET of an absent catalog returns 404, and authorized PUT followed by GET returns identical JSON content.

The Worker currently has a test CORS policy. Replace the wildcard origin with the exact approved app origins if browser clients are added. Android native HTTP clients do not use browser CORS enforcement.
