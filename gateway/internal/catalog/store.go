package catalog

import (
	"context"
	"encoding/json"
	"errors"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

var ErrNotFound = errors.New("scene not found")

type Store struct {
	pool *pgxpool.Pool
}

func NewStore(pool *pgxpool.Pool) *Store {
	return &Store{pool: pool}
}

func (s *Store) ListSources(ctx context.Context, projectID string) ([]Source, error) {
	rows, err := s.pool.Query(ctx, `
		SELECT source_id, name, provider
		FROM satellite_sources
		WHERE project_id = $1 AND is_enabled = true
		ORDER BY source_id`, projectID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var sources []Source
	for rows.Next() {
		var source Source
		if err := rows.Scan(&source.ID, &source.Name, &source.Provider); err != nil {
			return nil, err
		}
		sources = append(sources, source)
	}
	return sources, rows.Err()
}

func (s *Store) SearchScenes(ctx context.Context, filter SearchFilter) ([]Scene, error) {
	rows, err := s.pool.Query(ctx, `
		SELECT s.scene_id, s.source_id, s.collection_id, s.provider_scene_id,
		       c.satellite, c.sensor, c.processing_level, s.acquired_at,
		       s.bbox_west, s.bbox_south, s.bbox_east, s.bbox_north,
		       s.cloud_cover, s.crs, s.ground_sample_distance, s.version,
		       COALESCE((s.quality->>'blocked')::boolean, false),
		       COALESCE(s.quality->'codes', '[]'::jsonb)
		FROM satellite_scenes s
		JOIN satellite_collections c ON c.collection_id = s.collection_id
		JOIN satellite_sources src ON src.source_id = s.source_id
		WHERE src.project_id = $1 AND src.is_enabled = true
		  AND s.status = 'available'
		  AND s.acquired_at >= $2 AND s.acquired_at < $3
		  AND ST_Intersects(s.footprint, ST_MakeEnvelope($4, $5, $6, $7, 4326))
		  AND (COALESCE(cardinality($8::text[]), 0) = 0 OR s.source_id = ANY($8::text[]))
		  AND (COALESCE(cardinality($9::text[]), 0) = 0 OR s.collection_id = ANY($9::text[]))
		  AND (COALESCE(cardinality($10::text[]), 0) = 0 OR c.satellite = ANY($10::text[]))
		  AND (COALESCE(cardinality($11::text[]), 0) = 0 OR c.sensor = ANY($11::text[]))
		  AND (COALESCE(cardinality($12::text[]), 0) = 0 OR c.processing_level = ANY($12::text[]))
		  AND ($13::double precision IS NULL OR s.cloud_cover <= $13)
		ORDER BY s.acquired_at, s.scene_id
		LIMIT $14 OFFSET $15`,
		filter.ProjectID, filter.AcquiredFrom, filter.AcquiredTo,
		filter.BBox.West, filter.BBox.South, filter.BBox.East, filter.BBox.North,
		filter.SourceIDs, filter.CollectionIDs, filter.Satellites, filter.Sensors,
		filter.ProcessingLevels, filter.MaxCloudCover, filter.Limit, filter.Offset)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var scenes []Scene
	for rows.Next() {
		scene, err := scanScene(rows)
		if err != nil {
			return nil, err
		}
		scenes = append(scenes, scene)
	}
	return scenes, rows.Err()
}

func (s *Store) GetScene(ctx context.Context, projectID, sceneID string) (Scene, error) {
	row := s.pool.QueryRow(ctx, `
		SELECT s.scene_id, s.source_id, s.collection_id, s.provider_scene_id,
		       c.satellite, c.sensor, c.processing_level, s.acquired_at,
		       s.bbox_west, s.bbox_south, s.bbox_east, s.bbox_north,
		       s.cloud_cover, s.crs, s.ground_sample_distance, s.version,
		       COALESCE((s.quality->>'blocked')::boolean, false),
		       COALESCE(s.quality->'codes', '[]'::jsonb), ST_AsText(s.footprint), s.metadata
		FROM satellite_scenes s
		JOIN satellite_collections c ON c.collection_id = s.collection_id
		JOIN satellite_sources src ON src.source_id = s.source_id
		WHERE src.project_id = $1 AND s.scene_id = $2`, projectID, sceneID)

	var scene Scene
	var qualityCodesJSON, metadataJSON []byte
	err := row.Scan(
		&scene.ID, &scene.SourceID, &scene.CollectionID, &scene.ProviderSceneID,
		&scene.Satellite, &scene.Sensor, &scene.ProcessingLevel, &scene.AcquiredAt,
		&scene.BBox.West, &scene.BBox.South, &scene.BBox.East, &scene.BBox.North,
		&scene.CloudCover, &scene.CRS, &scene.GroundSampleDistance, &scene.Version,
		&scene.QualityBlocked, &qualityCodesJSON, &scene.FootprintWKT, &metadataJSON,
	)
	if errors.Is(err, pgx.ErrNoRows) {
		return Scene{}, ErrNotFound
	}
	if err != nil {
		return Scene{}, err
	}
	if err := json.Unmarshal(qualityCodesJSON, &scene.QualityCodes); err != nil {
		return Scene{}, err
	}
	scene.MetadataJSON = string(metadataJSON)

	assets, err := s.listAssets(ctx, sceneID)
	if err != nil {
		return Scene{}, err
	}
	scene.Assets = assets
	return scene, nil
}

type rowScanner interface {
	Scan(dest ...any) error
}

func scanScene(row rowScanner) (Scene, error) {
	var scene Scene
	var qualityCodesJSON []byte
	err := row.Scan(
		&scene.ID, &scene.SourceID, &scene.CollectionID, &scene.ProviderSceneID,
		&scene.Satellite, &scene.Sensor, &scene.ProcessingLevel, &scene.AcquiredAt,
		&scene.BBox.West, &scene.BBox.South, &scene.BBox.East, &scene.BBox.North,
		&scene.CloudCover, &scene.CRS, &scene.GroundSampleDistance, &scene.Version,
		&scene.QualityBlocked, &qualityCodesJSON,
	)
	if err != nil {
		return Scene{}, err
	}
	if err := json.Unmarshal(qualityCodesJSON, &scene.QualityCodes); err != nil {
		return Scene{}, err
	}
	return scene, nil
}

func (s *Store) listAssets(ctx context.Context, sceneID string) ([]Asset, error) {
	rows, err := s.pool.Query(ctx, `
		SELECT asset_id, asset_role, band, COALESCE(object_ref, ''),
		       COALESCE(content_type, ''), COALESCE(checksum, ''), COALESCE(size_bytes, 0),
		       COALESCE(metadata->'quality_codes', '[]'::jsonb)
		FROM satellite_scene_assets WHERE scene_id = $1
		ORDER BY asset_role, band, asset_id`, sceneID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var assets []Asset
	for rows.Next() {
		var asset Asset
		var qualityCodesJSON []byte
		if err := rows.Scan(&asset.ID, &asset.Role, &asset.Band, &asset.ObjectRef, &asset.ContentType, &asset.Checksum, &asset.SizeBytes, &qualityCodesJSON); err != nil {
			return nil, err
		}
		if err := json.Unmarshal(qualityCodesJSON, &asset.QualityCodes); err != nil {
			return nil, err
		}
		assets = append(assets, asset)
	}
	return assets, rows.Err()
}
