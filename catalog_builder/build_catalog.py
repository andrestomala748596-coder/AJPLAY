import json
import os
import sys
import tempfile
from pathlib import Path
from urllib.parse import urljoin

import requests

TIMEOUT = (15, 90)
MAX_RETRIES = 3


def api_get(base_url, username, password, action):
    base = base_url.rstrip("/") + "/player_api.php"
    response = requests.get(
        base,
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
    all_clients = json.loads(os.environ["AJPLAY_SERVERS_JSON"])
    client = next((c for c in all_clients if str(c["client_id"]) == client_id), None)
    if not client:
        raise RuntimeError(f"No existe configuración segura para client_id={client_id}")

    servers = client.get("servers", [])
    if not servers:
        raise RuntimeError("El cliente no tiene servidores asignados")
    prepared = []

    # Temporary files are isolated and automatically removed on exit.
    with tempfile.TemporaryDirectory(prefix="ajplay_catalog_") as temp:
        temp_dir = Path(temp)
        for server in servers:
            server_id = str(server["server_id"])
            base_url = server["base_url"]
            username = server["username"]
            password = server["password"]

            # Only category and VOD listing endpoints. Never call get_vod_info/get_info.
            categories = api_get(base_url, username, password, "get_vod_categories")
            streams = api_get(base_url, username, password, "get_vod_streams")

            # Preserve provider records exactly as returned. No title/year normalization,
            # no deduplication, no get_info and no extension rewriting.
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

        # Publish only after every assigned server was downloaded successfully.
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
                raise RuntimeError(f"Worker rechazó {server_id}: {result}")
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
