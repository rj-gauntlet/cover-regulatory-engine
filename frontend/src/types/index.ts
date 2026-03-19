export interface Citation {
  section_number: string
  section_title: string
  relevant_text: string
  source_url: string
  regulation_id?: string
}

export interface Constraint {
  id: string
  category: string
  parameter: string
  rule_text: string
  value: string | null
  numeric_value: number | null
  unit: string | null
  confidence: number
  source_layer: 'deterministic_lookup' | 'computed' | 'llm_interpreted'
  determination_type: 'deterministic' | 'interpreted' | 'inferred'
  citations: Citation[]
  reasoning: string
  geometry_geojson: GeoJSON.Geometry | null
  zone_rule_id: string | null
}

export interface Parcel {
  id: string
  apn: string
  address: string | null
  zone_code: string
  zone_class: string
  height_district: string | null
  specific_plan: string | null
  overlay_zones: string[]
  lot_area_sqft: number | null
  lot_width_ft: number | null
  lot_depth_ft: number | null
  geometry_geojson: GeoJSON.Geometry | null
  building_footprints_geojson: GeoJSON.Geometry | null
  centroid_lat: number | null
  centroid_lng: number | null
  community_plan_area: string | null
}

export interface Assessment {
  id: string
  parcel: Parcel
  building_type: string
  project_inputs: Record<string, any> | null
  constraints: Constraint[]
  overall_confidence: number
  summary: string
  created_at: string
}

export interface AssessmentRequest {
  address?: string
  apn?: string
  building_type: string
  project_inputs?: Record<string, any>
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  citations?: Citation[]
  created_at: string
}

export interface FeedbackRequest {
  constraint_id?: string
  assessment_id: string
  rating: 'positive' | 'negative'
  comment?: string
}

export interface PipelineStatus {
  total_raw_sources: number
  total_regulations: number
  total_chunks: number
  total_zone_rules: number
  verified_rules: number
  total_parcels_cached: number
  total_assessments: number
  total_feedback: number
  last_ingestion: string | null
}

export interface AdminFeedback {
  id: string
  constraint_id: string | null
  assessment_id: string
  rating: 'positive' | 'negative'
  comment: string | null
  created_at: string
}

export interface ZoneRule {
  id: string
  zone_class: string
  parameter: string
  category: string
  base_value: number
  unit: string
  conditions: Record<string, any> | null
  applies_to: string[]
  section_number: string
  source_text: string
  is_verified: boolean
  notes: string | null
}

export const CATEGORY_LABELS: Record<string, string> = {
  setback: 'Setbacks',
  height: 'Height',
  far: 'Floor Area',
  density: 'Density',
  use: 'Use',
  parking: 'Parking',
  lot: 'Lot Requirements',
  adu: 'ADU / Guest House',
  coverage: 'Coverage',
  other: 'Other',
}

export const CATEGORY_ICONS: Record<string, string> = {
  setback: '↔',
  height: '↕',
  far: '□',
  density: '⊞',
  use: '✓',
  parking: '⊡',
  lot: '▢',
  adu: '⌂',
  coverage: '▣',
  other: '•',
}
