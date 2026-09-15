# Satellite Data Platform Architecture

## 1. Responsibility

卫星数据平台负责多来源影像目录的统一查询，不拥有 Agent Run，也不执行影像算法。

行为规格入口：[Satellite Imagery Catalog Spec](../spec/data-platform/satellite-imagery-catalog/spec.md)。

## 2. Runtime topology

```text
SatelliteAgent
  -> Python gRPC client/tool
     -> Go gateway
        -> PostgreSQL/PostGIS catalog
        -> bounded MinIO object references

SatelliteAgent
  -> configured MCP tools
     -> image processing services
```

## 3. Ownership

- Alembic owns the satellite catalog schema.
- `gateway/` owns catalog validation, spatial query, pagination and gRPC mapping.
- PostgreSQL/PostGIS owns sources, collections, scenes and scene assets.
- MinIO owns raster, band, mask and preview objects; the catalog stores bucket/key-style references.
- `SatelliteAgent` owns source selection and processing orchestration, not database access.

## 4. Invariants

- Every search has a WGS84 bbox, RFC3339 time range, project scope and bounded limit.
- Model-controlled arguments cannot provide project identity or Gateway credentials.
- Gateway startup never creates or migrates tables.
- Large raster bytes never enter gRPC catalog responses or Agent context.
