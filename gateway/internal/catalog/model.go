package catalog

import "time"

type BBox struct {
	West  float64
	South float64
	East  float64
	North float64
}

func (b BBox) Valid() bool {
	return b.West >= -180 && b.East <= 180 && b.South >= -90 && b.North <= 90 && b.West < b.East && b.South < b.North
}

type Source struct {
	ID       string
	Name     string
	Provider string
}

type SearchFilter struct {
	ProjectID        string
	BBox             BBox
	AcquiredFrom     time.Time
	AcquiredTo       time.Time
	SourceIDs        []string
	CollectionIDs    []string
	Satellites       []string
	Sensors          []string
	ProcessingLevels []string
	MaxCloudCover    *float64
	Limit            int
	Offset           int
}

type Scene struct {
	ID                   string
	SourceID             string
	CollectionID         string
	ProviderSceneID      string
	Satellite            string
	Sensor               string
	ProcessingLevel      string
	AcquiredAt           time.Time
	BBox                 BBox
	CloudCover           *float64
	CRS                  string
	GroundSampleDistance *float64
	Version              string
	QualityBlocked       bool
	QualityCodes         []string
	FootprintWKT         string
	MetadataJSON         string
	Assets               []Asset
}

type Asset struct {
	ID           string
	Role         string
	Band         string
	ObjectRef    string
	ContentType  string
	Checksum     string
	SizeBytes    int64
	QualityCodes []string
}
