package grpcserver

import (
	"context"
	"errors"

	satellitev1 "github.com/Agent-Multiverse-Lab/agent-stack/gateway/api/gen"
	"github.com/Agent-Multiverse-Lab/agent-stack/gateway/internal/catalog"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/metadata"
	"google.golang.org/grpc/status"
)

const projectMetadataKey = "x-project-id"

func AuthInterceptor(sharedToken string) func(context.Context, any, *grpc.UnaryServerInfo, grpc.UnaryHandler) (any, error) {
	return func(ctx context.Context, request any, _ *grpc.UnaryServerInfo, handler grpc.UnaryHandler) (any, error) {
		values := metadata.ValueFromIncomingContext(ctx, "authorization")
		if sharedToken == "" || len(values) != 1 || values[0] != "Bearer "+sharedToken {
			return nil, status.Error(codes.Unauthenticated, "invalid gateway credentials")
		}
		return handler(ctx, request)
	}
}

type Server struct {
	satellitev1.UnimplementedSatelliteCatalogServiceServer
	service *catalog.Service
}

func New(service *catalog.Service) *Server {
	return &Server{service: service}
}

func (s *Server) ListSources(ctx context.Context, _ *satellitev1.ListSourcesRequest) (*satellitev1.ListSourcesResponse, error) {
	sources, err := s.service.ListSources(ctx, projectID(ctx))
	if err != nil {
		return nil, mapError(err)
	}
	response := &satellitev1.ListSourcesResponse{}
	for _, source := range sources {
		response.Sources = append(response.Sources, &satellitev1.Source{
			SourceId: source.ID,
			Name:     source.Name,
			Provider: source.Provider,
		})
	}
	return response, nil
}

func (s *Server) SearchScenes(ctx context.Context, request *satellitev1.SearchScenesRequest) (*satellitev1.SearchScenesResponse, error) {
	if request.GetBbox() == nil {
		return nil, status.Error(codes.InvalidArgument, "bbox and time range are required")
	}
	start, end, err := catalog.ParseTimeRange(request.GetAcquiredFrom(), request.GetAcquiredTo())
	if err != nil {
		return nil, mapError(err)
	}
	offset, err := catalog.ParsePageToken(request.GetPageToken())
	if err != nil {
		return nil, mapError(err)
	}
	filter := catalog.SearchFilter{
		ProjectID: projectID(ctx),
		BBox: catalog.BBox{
			West: request.Bbox.West, South: request.Bbox.South,
			East: request.Bbox.East, North: request.Bbox.North,
		},
		AcquiredFrom: start, AcquiredTo: end,
		SourceIDs: request.SourceIds, CollectionIDs: request.CollectionIds,
		Satellites: request.Satellites, Sensors: request.Sensors,
		ProcessingLevels: request.ProcessingLevels,
		MaxCloudCover:    request.MaxCloudCover,
		Limit:            int(request.Limit), Offset: offset,
	}
	scenes, nextPageToken, err := s.service.SearchScenes(ctx, filter)
	if err != nil {
		return nil, mapError(err)
	}
	response := &satellitev1.SearchScenesResponse{NextPageToken: nextPageToken}
	for _, scene := range scenes {
		response.Scenes = append(response.Scenes, sceneSummary(scene))
	}
	return response, nil
}

func (s *Server) GetScene(ctx context.Context, request *satellitev1.GetSceneRequest) (*satellitev1.SceneDetail, error) {
	scene, err := s.service.GetScene(ctx, projectID(ctx), request.GetSceneId())
	if err != nil {
		return nil, mapError(err)
	}
	response := &satellitev1.SceneDetail{
		Scene:        sceneSummary(scene),
		FootprintWkt: scene.FootprintWKT,
		MetadataJson: scene.MetadataJSON,
	}
	for _, asset := range scene.Assets {
		response.Assets = append(response.Assets, &satellitev1.SceneAsset{
			AssetId: asset.ID, Role: asset.Role, Band: asset.Band,
			ObjectRef: asset.ObjectRef, ContentType: asset.ContentType,
			Checksum: asset.Checksum, SizeBytes: asset.SizeBytes,
			QualityCodes: asset.QualityCodes,
		})
	}
	return response, nil
}

func projectID(ctx context.Context) string {
	values := metadata.ValueFromIncomingContext(ctx, projectMetadataKey)
	if len(values) == 0 {
		return ""
	}
	return values[0]
}

func sceneSummary(scene catalog.Scene) *satellitev1.SceneSummary {
	result := &satellitev1.SceneSummary{
		SceneId: scene.ID, SourceId: scene.SourceID, CollectionId: scene.CollectionID,
		ProviderSceneId: scene.ProviderSceneID, Satellite: scene.Satellite,
		Sensor: scene.Sensor, ProcessingLevel: scene.ProcessingLevel,
		AcquiredAt: scene.AcquiredAt.UTC().Format("2006-01-02T15:04:05Z07:00"),
		Bbox: &satellitev1.BoundingBox{
			West: scene.BBox.West, South: scene.BBox.South,
			East: scene.BBox.East, North: scene.BBox.North,
		},
		CloudCover: scene.CloudCover, Crs: scene.CRS,
		GroundSampleDistance: scene.GroundSampleDistance,
		Version:              scene.Version, QualityBlocked: scene.QualityBlocked,
		QualityCodes: scene.QualityCodes,
	}
	return result
}

func mapError(err error) error {
	switch {
	case errors.Is(err, catalog.ErrInvalidRequest):
		return status.Error(codes.InvalidArgument, err.Error())
	case errors.Is(err, catalog.ErrForbidden):
		return status.Error(codes.PermissionDenied, err.Error())
	case errors.Is(err, catalog.ErrNotFound):
		return status.Error(codes.NotFound, err.Error())
	default:
		return status.Error(codes.Internal, "catalog operation failed")
	}
}
