export interface MapPlace {
  id: string
  name: string
  category: string
  description: string
  coordinate: [number, number]
}

// Deliberately local, illustrative fixtures. Never presented as catalog results.
export const examplePlaces: MapPlace[] = [
  { id: "lakeside", name: "Lakeside observation point", category: "Waterfront", description: "Compare the lake edge and the surrounding urban fabric.", coordinate: [120.157, 30.253] },
  { id: "island", name: "Gushan observation point", category: "Landscape", description: "Explore the relationship between green space, water and the city.", coordinate: [120.137, 30.251] },
  { id: "south", name: "South shore observation point", category: "Landscape", description: "A different perspective on the southern shoreline.", coordinate: [120.148, 30.235] },
]

export function parseCoordinate(query: string): [number, number] | null {
  const match = query.trim().match(/^(-?\d+(?:\.\d+)?)\s*[,，]\s*(-?\d+(?:\.\d+)?)$/)
  if (!match) return null
  const longitude = Number(match[1])
  const latitude = Number(match[2])
  return Math.abs(longitude) <= 180 && Math.abs(latitude) <= 85
    ? [longitude, latitude]
    : null
}

export function formatCoordinate(coordinate: [number, number]) {
  const [longitude, latitude] = coordinate
  return `${Math.abs(latitude).toFixed(4)}° ${latitude < 0 ? "S" : "N"} · ${Math.abs(longitude).toFixed(4)}° ${longitude < 0 ? "W" : "E"}`
}
