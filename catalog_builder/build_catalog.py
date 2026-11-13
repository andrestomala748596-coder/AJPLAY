import json
import os
import sys
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import requests

TIMEOUT = (15, 90)


def credentials_from_server(server):
    """Accept a private endpoint_url from Supabase or explicit base_url/user/password."""
    endpoint_url = server.get("endpoint_url")
    if endpoint_url:
        parsed = urlsplit(endpoint_url)
        query = parse_qs(parsed.query)
        username = (query.get("username") or [None])[0]
        password = (query.get("password") or [None])[0]
        if not parsed.scheme or not parsed.netloc or not username or not password:
            raise RuntimeError(
                "endpoint_url inválida: debe ser una URL Xtream get.php con username y password"
            )
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        return base_url, username, password

    base_url = server.get("base_url")
    username = server.get("username")
    password = server.get("password")
    if not all((base_url, username, password)):
        raise RuntimeError("Servidor sin endpoint_url o sin base_url/username/password")
    return base_url.rstrip("/"), username, password


def api_get(base_url, username, password, action):
    response = requests.get(
        base_url.rstrip("/") + "/player_api.php",
        params={"username": username, "password": password, "action": action},
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, list):
        raise RuntimeError(f"{action}: el proveedor no devolvió una lista")
    return data


def main():
    client_id = os.environ["CLIENT_ID"]
    worker_url = os.environ["WORKER_URL"].rstrip("/")
    write_token = os.environ["CATALOG_WRITE_TOKEN"]
    config = json.loads(os.environ["AJPLAY_SERVERS_JSON"])
    clients = config.get("clients", []) if isinstance(config, dict) else config
    client = next((c for c in clients if str(c.get("client_id")) == client_id), None)
    if not client:
        raise RuntimeError(f"No existe configuración segura para client_id={client_id}")

    servers = client.get("servers", [])
    if not servers:
        raise RuntimeError("El cliente no tiene servidores asignados")

    prepared = []
    with tempfile.TemporaryDirectory(prefix="ajplay_catalog_") as temp:
        temp_dir = Path(temp)

        # Download and validate every assigned server before publishing any of them.
        for server in servers:
            server_id = str(server["server_id"])
            base_url, username, password = credentials_from_server(server)

            categories = api_get(base_url, username, password, "get_vod_categories")
            streams = api_get(base_url, username, password, "get_vod_streams")

            catalog = {
                "client_id": client_id,
                "server_id": server_id,
                "categories": categories,
                "streams": streams,
            }
            file_path = temp_dir / f"{server_id}.json"
            file_path.write_text(
                json.dumps(catalog, ensure_ascii=False, separators=(",", ":")),
                encoding="utf-8",
            )
            prepared.append((server_id, file_path, len(streams), len(categories)))

        for server_id, file_path, stream_count, category_count in prepared:
            with file_path.open("rb") as handle:
                response = requests.put(
                    f"{worker_url}/v1/catalog/{client_id}/{server_id}",
                    data=handle,
                    headers={
                        "Authorization": f"Bearer {write_token}",
                        "Content-Type": "application/json",
                    },
                    timeout=TIMEOUT,
                )
            response.raise_for_status()
            result = response.json()
            if not result.get("ok"):
                raise RuntimeError(f"Worker rechazó el servidor {server_id}")
            print(
                f"Publicado cliente={client_id} servidor={server_id} "
                f"categorias={category_count} streams={stream_count}"
            )

    print("Proceso terminado. Los archivos temporales fueron eliminados.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
