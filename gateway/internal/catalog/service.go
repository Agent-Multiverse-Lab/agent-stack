package catalog

import (
	"context"
	"errors"
	"strconv"
	"time"
)

var (
	ErrInvalidRequest = errors.New("invalid request")
	ErrForbidden      = errors.New("forbidden")
)

const maxPageSize = 100

type CatalogStore interface {
	ListSources(context.Context, string) ([]Source, error)
	SearchScenes(context.Context, SearchFilter) ([]Scene, error)
	GetScene(context.Context, string, string) (Scene, error)
}

type Service struct {
	store CatalogStore
}

func NewService(store CatalogStore) *Service {
	return &Service{store: store}
}

func (s *Service) ListSources(ctx context.Context, projectID string) ([]Source, error) {
	if projectID == "" {
		return nil, ErrForbidden
	}
	return s.store.ListSources(ctx, projectID)
}

func (s *Service) SearchScenes(ctx context.Context, filter SearchFilter) ([]Scene, string, error) {
	if filter.ProjectID == "" {
		return nil, "", ErrForbidden
	}
	if !filter.BBox.Valid() || filter.AcquiredFrom.IsZero() || filter.AcquiredTo.IsZero() || !filter.AcquiredFrom.Before(filter.AcquiredTo) {
		return nil, "", ErrInvalidRequest
	}
	if filter.MaxCloudCover != nil && (*filter.MaxCloudCover < 0 || *filter.MaxCloudCover > 100) {
		return nil, "", ErrInvalidRequest
	}
	if filter.Limit <= 0 {
		filter.Limit = 20
	}
	if filter.Limit > maxPageSize {
		filter.Limit = maxPageSize
	}

	queryLimit := filter.Limit
	filter.Limit++
	scenes, err := s.store.SearchScenes(ctx, filter)
	if err != nil {
		return nil, "", err
	}
	if len(scenes) <= queryLimit {
		return scenes, "", nil
	}
	return scenes[:queryLimit], strconv.Itoa(filter.Offset + queryLimit), nil
}

func (s *Service) GetScene(ctx context.Context, projectID, sceneID string) (Scene, error) {
	if projectID == "" {
		return Scene{}, ErrForbidden
	}
	if sceneID == "" {
		return Scene{}, ErrInvalidRequest
	}
	return s.store.GetScene(ctx, projectID, sceneID)
}

func ParseTimeRange(from, to string) (time.Time, time.Time, error) {
	start, err := time.Parse(time.RFC3339, from)
	if err != nil {
		return time.Time{}, time.Time{}, ErrInvalidRequest
	}
	end, err := time.Parse(time.RFC3339, to)
	if err != nil {
		return time.Time{}, time.Time{}, ErrInvalidRequest
	}
	return start.UTC(), end.UTC(), nil
}

func ParsePageToken(token string) (int, error) {
	if token == "" {
		return 0, nil
	}
	offset, err := strconv.Atoi(token)
	if err != nil || offset < 0 {
		return 0, ErrInvalidRequest
	}
	return offset, nil
}
