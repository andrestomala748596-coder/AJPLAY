# Per-client IPTV catalog builder

The workflow is manually dispatched with a Supabase client UUID. It expects the GitHub Actions secrets:

- `AJPLAY_SERVERS_JSON`: JSON array of client configurations. Each entry contains `client_id` and `servers`; each server has `server_id`, `base_url`, `username`, and `password`.
- `CATALOG_WRITE_TOKEN`: must match the Cloudflare Worker's `CATALOG_WRITE_TOKEN` secret.

Repository variable:
- `AJPLAY_WORKER_URL`: deployed Worker base URL.

Example structure (use real values only in GitHub Secrets, never commit this):
```json
[
  {
    "client_id": "client-uuid",
    "servers": [
      {
        "server_id": "server-uuid-1",
        "base_url": "https://provider.example",
        "username": "private-user",
        "password": "private-password"
      }
    ]
  }
]
```

## Provider calls

Only:
- `get_vod_categories`
- `get_vod_streams`

Never:
- `get_vod_info`
- `get_info`
- per-title detail lookups

The original category and stream records are preserved in JSON, including provider stream IDs, category IDs, titles, years, and `container_extension` exactly as supplied. Repeated entries are not deduplicated.

## Storage layout

Each catalog is isolated by both identifiers in Workers KV:
`client:{client_id}:server:{server_id}:catalog:v1`

Thus a client with three assigned IPTV servers receives three independent catalog values. No global shared catalog is generated.

## Temporary files

Files are created only inside Python's temporary directory. It is automatically removed when the workflow exits, including after successful uploads. A failed extraction does not publish partial data for a server; each server's JSON is uploaded only after both provider listing calls succeed.

## Security

Do not commit credentials. Store provider connection details only in Actions secrets. The Worker write token must be set as a Worker secret and the same value as a GitHub Actions secret. Client read authentication still needs to be integrated with AJPLAY's existing authenticated session before production use.
