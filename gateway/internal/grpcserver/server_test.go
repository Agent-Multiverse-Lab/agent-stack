package grpcserver

import (
	"context"
	"testing"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/metadata"
	"google.golang.org/grpc/status"
)

func TestAuthInterceptor(t *testing.T) {
	interceptor := AuthInterceptor("secret")
	handler := func(context.Context, any) (any, error) { return "ok", nil }

	_, err := interceptor(context.Background(), nil, &grpc.UnaryServerInfo{}, handler)
	if status.Code(err) != codes.Unauthenticated {
		t.Fatalf("missing credentials returned %v", err)
	}

	ctx := metadata.NewIncomingContext(
		context.Background(),
		metadata.Pairs("authorization", "Bearer secret"),
	)
	response, err := interceptor(ctx, nil, &grpc.UnaryServerInfo{}, handler)
	if err != nil || response != "ok" {
		t.Fatalf("valid credentials failed: response=%v err=%v", response, err)
	}
}
