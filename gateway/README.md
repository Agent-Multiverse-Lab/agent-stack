# Satellite Catalog Gateway

Go gRPC service for bounded satellite scene discovery. It reads the schema created by
`migrate/versions/0011_satellite_catalog.py`; it never creates tables at startup.

## RPCs

- `ListSources`
- `SearchScenes` (requires WGS84 bbox and RFC3339 time range)
- `GetScene`

Every call requires `authorization: Bearer <GATEWAY_SHARED_TOKEN>` and an
`x-project-id` metadata value. Python adds these values outside model-controlled tool arguments.

## Generate protocol code

```powershell
python -m grpc_tools.protoc -Igateway/api/proto `
  --python_out=src/third_party/satellite_gateway `
  --grpc_python_out=src/third_party/satellite_gateway `
  gateway/api/proto/satellite_catalog.proto

protoc -Igateway/api/proto --go_out=gateway/api/gen --go_opt=paths=source_relative `
  --go-grpc_out=gateway/api/gen --go-grpc_opt=paths=source_relative `
  gateway/api/proto/satellite_catalog.proto
```

The Python gRPC generator emits an absolute sibling import; keep it package-relative:

```python
from . import satellite_catalog_pb2 as satellite__catalog__pb2
```

## Run

Apply the migration and load the deterministic demo catalog first:

```powershell
uv run alembic upgrade head
uv run python scripts/load_satellite_catalog_fixture.py
```

Then start through the root `docker-compose.yml`, or provide `DATABASE_URL`,
`GATEWAY_SHARED_TOKEN`, `GATEWAY_GRPC_ADDRESS`, and `GATEWAY_HEALTH_ADDRESS` directly.
