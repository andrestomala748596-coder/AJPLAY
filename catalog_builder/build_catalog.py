import json
import os
import sys
import tempfile
from pathlib import Path

import requests

TIMEOUT = (15, 120)


def source_servers(client_id):
    source_url = os.environ["CATALOG_SOURCE_URL"].rstrip("/")
    source_token = os.environ["AJPLAY_CATALOG_SOURCE_TOKEN"]
    response = requests.get(
        f"{source_url}/functions/v1/catalog-source",
        params={"client_id": client_id},
        headers={
            "Authorization": f"Bearer {source_token}",
            "apikey": os.environ["SUPABASE_ANON_KEY"],
            "Accept": "application/json",
        },
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("ok"):
        raise RuntimeError(payload.get("error", "Supabase no devolvió los servidores"))
    servers = payload.get("servers", [])
    if not servers:
        raise RuntimeError("El cliente no tiene servidores activos asignados")
    return servers


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
    servers = source_servers(client_id)

    # Prepare and validate all assigned server catalogs before publishing.
    prepared = []
    with tempfile.TemporaryDirectory(prefix="ajplay_catalog_") as temp:
        temp_dir = Path(temp)
        for server in servers:
            server_id = str(server["id"])
            base_url = str(server["base_url"]).rstrip("/")
            username = str(server["username"])
            password = str(server["password"])
            if not all((base_url, username, password)):
                raise RuntimeError(f"El servidor {server_id} no tiene credenciales completas")

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

        # Publish only after every server was extracted successfully.
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

    print(f"Proceso terminado. Servidores publicados: {len(prepared)}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
