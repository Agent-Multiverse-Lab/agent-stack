# Data Platform Architecture

## 1. Responsibility

数据平台负责多来源影像目录的统一治理、受控检索和 OGC 服务发布控制。它不拥有 Agent Run，
也不在目录 Gateway 中执行影像算法或渲染瓦片。

行为规格入口：

- [Satellite Imagery Catalog Spec](../spec/data-platform/satellite-imagery-catalog/spec.md)
- [Imagery OGC Publishing Spec](../spec/data-platform/imagery-ogc-publishing/spec.md)

## 2. Runtime topology

```text
SatelliteAgent
  -> Python gRPC client/tool
     -> Go gateway
        -> PostgreSQL/PostGIS catalog
        -> OGC publishing control plane
        -> bounded RustFS object references

SatelliteAgent
  -> configured MCP tools
     -> image processing services

OGC renderer (later phase)
  -> published service/layer/theme configuration
  -> bounded RustFS raster reads
  -> WMTS/WMS responses and tile cache
```

## 3. Ownership

- Alembic owns catalog and OGC control-plane schemas.
- `gateway/` owns catalog validation, spatial query, pagination, publication state transitions and gRPC mapping.
- PostgreSQL/PostGIS owns sources, collections, scenes, scene assets, OGC services, layers and themes.
- RustFS owns raster, band, mask and preview objects; the catalog stores bucket/key-style references.
- A later OGC renderer owns WMTS/WMS protocol responses, raster reads and tile cache; it consumes only published configuration.
- `SatelliteAgent` owns source selection, publication orchestration and processing orchestration, not database access.

## 4. Invariants

- Every search has a WGS84 bbox, RFC3339 time range, project scope and bounded limit.
- Model-controlled arguments cannot provide project identity or Gateway credentials.
- Gateway startup never creates or migrates tables.
- Large raster bytes never enter gRPC catalog responses or Agent context.
- A published layer references catalog assets; it does not duplicate raster bytes or catalog metadata.
- Mutating publication tools require human approval, while bounded discovery tools remain read-only.
