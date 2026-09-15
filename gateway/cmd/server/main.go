package main

import (
	"context"
	"log"
	"net"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	satellitev1 "github.com/Agent-Multiverse-Lab/agent-stack/gateway/api/gen"
	"github.com/Agent-Multiverse-Lab/agent-stack/gateway/internal/catalog"
	"github.com/Agent-Multiverse-Lab/agent-stack/gateway/internal/grpcserver"
	"github.com/jackc/pgx/v5/pgxpool"
	"google.golang.org/grpc"
)

func main() {
	databaseURL := requiredEnv("DATABASE_URL")
	grpcAddress := envOrDefault("GATEWAY_GRPC_ADDRESS", ":50051")
	healthAddress := envOrDefault("GATEWAY_HEALTH_ADDRESS", ":8080")
	sharedToken := requiredEnv("GATEWAY_SHARED_TOKEN")

	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()

	pool, err := pgxpool.New(ctx, databaseURL)
	if err != nil {
		log.Fatalf("configure database: %v", err)
	}
	defer pool.Close()
	if err := pool.Ping(ctx); err != nil {
		log.Fatalf("connect database: %v", err)
	}

	listener, err := net.Listen("tcp", grpcAddress)
	if err != nil {
		log.Fatalf("listen gRPC: %v", err)
	}
	grpcServer := grpc.NewServer(
		grpc.UnaryInterceptor(grpcserver.AuthInterceptor(sharedToken)),
	)
	satellitev1.RegisterSatelliteCatalogServiceServer(
		grpcServer,
		grpcserver.New(catalog.NewService(catalog.NewStore(pool))),
	)

	healthServer := &http.Server{
		Addr:              healthAddress,
		ReadHeaderTimeout: 5 * time.Second,
		Handler: http.HandlerFunc(func(writer http.ResponseWriter, request *http.Request) {
			if request.URL.Path != "/health" {
				http.NotFound(writer, request)
				return
			}
			if err := pool.Ping(request.Context()); err != nil {
				http.Error(writer, "database unavailable", http.StatusServiceUnavailable)
				return
			}
			writer.WriteHeader(http.StatusNoContent)
		}),
	}

	go func() {
		log.Printf("satellite catalog gRPC listening on %s", grpcAddress)
		if err := grpcServer.Serve(listener); err != nil {
			log.Printf("gRPC server stopped: %v", err)
			stop()
		}
	}()
	go func() {
		if err := healthServer.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Printf("health server stopped: %v", err)
			stop()
		}
	}()

	<-ctx.Done()
	grpcServer.GracefulStop()
	shutdownCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	_ = healthServer.Shutdown(shutdownCtx)
}

func requiredEnv(name string) string {
	value := os.Getenv(name)
	if value == "" {
		log.Fatalf("missing required environment variable %s", name)
	}
	return value
}

func envOrDefault(name, fallback string) string {
	if value := os.Getenv(name); value != "" {
		return value
	}
	return fallback
}
