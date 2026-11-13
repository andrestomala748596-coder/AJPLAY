# AJPLAY per-client IPTV catalog

## Current Supabase assignment verified

- Client: ANDY
- Client UUID: `19790397-8b78-401e-8c68-f226372e4a9a`
- Active assigned servers: 1
- Server: SERVIDOR 1
- Server UUID: `6c05c1b3-2f91-48b4-80e8-ca0b68d12d16`

The workflow default is configured for this existing client. The builder reads only the server list supplied in GitHub Actions secret `AJPLAY_SERVERS_JSON`; do not add invented servers to complete a sample.

## Required GitHub Actions configuration

Repository secret `AJPLAY_SERVERS_JSON`: JSON array with the actual client and assigned server connection data. Keep endpoint credentials here only, never in source control.

Repository secret `CATALOG_WRITE_TOKEN`: must match the Cloudflare Worker secret with the same name.

Repository variable `AJPLAY_WORKER_URL`: deployed Worker URL.

The current workflow has been committed, but these Actions secrets/variables have not been configured through the available GitHub connection.

## Provider API calls

Only:
- `get_vod_categories`
- `get_vod_streams`

Never:
- `get_vod_info`
- `get_info`
- per-title detail lookups

Original category and stream objects are retained as returned, including duplicates, titles, years, provider IDs, and `container_extension`. No title/year normalization or deduplication is performed.

## Storage layout

Each server catalog is stored independently in Cloudflare Workers KV under:
`client:{client_id}:server:{server_id}:catalog:v1`

A client with three assigned servers will get three separate values. The current ANDY assignment has one server, so it will publish one catalog.

## Temporary files and publication

Downloads are written to a Python temporary directory. Both category and stream listing calls must succeed for a server before its JSON is uploaded. The temporary directory is removed automatically when the process exits.

## Security and app integration

Provider credentials are not included in catalog JSON. Worker read and write access is token protected. Before production app use, integrate read authorization with AJPLAY's existing authenticated client/device session rather than shipping a shared read token in the APK.
