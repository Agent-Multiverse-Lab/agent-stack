package catalog

import (
	"context"
	"errors"
	"testing"
	"time"
)

type fakeStore struct {
	scenes []Scene
}

func (f fakeStore) ListSources(context.Context, string) ([]Source, error) {
	return []Source{{ID: "source-sentinel"}}, nil
}

func (f fakeStore) SearchScenes(_ context.Context, filter SearchFilter) ([]Scene, error) {
	if filter.Limit != 3 {
		return nil, errors.New("service must fetch one extra row for pagination")
	}
	return f.scenes, nil
}

func (f fakeStore) GetScene(_ context.Context, _, sceneID string) (Scene, error) {
	if sceneID == "missing" {
		return Scene{}, ErrNotFound
	}
	return Scene{ID: sceneID}, nil
}

func TestSearchRequiresSpatialAndTimeBounds(t *testing.T) {
	service := NewService(fakeStore{})
	_, _, err := service.SearchScenes(context.Background(), SearchFilter{ProjectID: "demo"})
	if !errors.Is(err, ErrInvalidRequest) {
		t.Fatalf("expected invalid request, got %v", err)
	}
}

func TestSearchCapsAndPaginates(t *testing.T) {
	service := NewService(fakeStore{scenes: []Scene{{ID: "one"}, {ID: "two"}, {ID: "three"}}})
	scenes, token, err := service.SearchScenes(context.Background(), SearchFilter{
		ProjectID:    "demo",
		BBox:         BBox{West: 116, South: 39, East: 117, North: 40},
		AcquiredFrom: time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC),
		AcquiredTo:   time.Date(2026, 2, 1, 0, 0, 0, 0, time.UTC),
		Limit:        2,
	})
	if err != nil {
		t.Fatal(err)
	}
	if len(scenes) != 2 || token != "2" {
		t.Fatalf("unexpected page: scenes=%d token=%q", len(scenes), token)
	}
}
