FROM golang:1.27-alpine AS build

WORKDIR /src
COPY gateway/go.mod gateway/go.sum ./
RUN go mod download
COPY gateway/ ./
RUN CGO_ENABLED=0 go build -trimpath -o /out/satellite-gateway ./cmd/server

FROM alpine:3.22
RUN addgroup -S gateway && adduser -S gateway -G gateway
COPY --from=build /out/satellite-gateway /usr/local/bin/satellite-gateway
USER gateway
EXPOSE 50051 8080
ENTRYPOINT ["satellite-gateway"]
