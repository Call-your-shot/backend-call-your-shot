export type Json = string | number | boolean | null | { [key: string]: Json | undefined } | Json[];

type Table<Row, Insert = Partial<Row>, Update = Partial<Row>> = {
  Row: Row;
  Insert: Insert;
  Update: Update;
  Relationships: [];
};

export type PropertyRole = "tenant" | "landlord" | "agent";
export type MembershipStatus = "invited" | "active" | "inactive";
export type ManagementRole = Extract<PropertyRole, "landlord" | "agent">;

export interface PropertyRow {
  id: string;
  name: string;
  address_line_1: string;
  address_line_2: string | null;
  suburb: string;
  state: string;
  postcode: string;
  country: string;
  latitude: number | null;
  longitude: number | null;
  timezone: string;
  roof_area_m2: number | null;
  usable_roof_area_m2: number | null;
  created_at: string;
  updated_at: string;
}

export interface MembershipRow {
  id: string;
  property_id: string;
  user_id: string;
  role: PropertyRole;
  status: MembershipStatus;
  starts_at: string | null;
  ends_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface EnergyReadingRow {
  id: string;
  property_id: string;
  meter_id: string | null;
  interval_start: string;
  interval_end: string;
  consumption_kwh: number;
  solar_generation_kwh: number;
  grid_import_kwh: number;
  grid_export_kwh: number;
  battery_soc_pct: number | null;
  source: "mock" | "meter_api" | "manual" | "simulation";
  created_at: string;
}

export interface TariffRow {
  id: string;
  property_id: string | null;
  name: string;
  usage_rate_per_kwh: number;
  feed_in_rate_per_kwh: number;
  daily_supply_charge: number;
  currency: string;
  valid_from: string;
  valid_to: string | null;
  created_by: string | null;
  created_at: string;
}

export interface BillRow {
  id: string;
  property_id: string;
  tenant_user_id: string | null;
  tariff_id: string;
  period_start: string;
  period_end: string;
  consumption_kwh: number;
  solar_generation_kwh: number;
  grid_import_kwh: number;
  grid_export_kwh: number;
  usage_cost: number;
  supply_cost: number;
  solar_credit: number;
  total_amount: number;
  estimated_savings: number;
  carbon_avoided_kg: number | null;
  status: "draft" | "issued" | "paid" | "overdue" | "cancelled";
  created_at: string;
  updated_at: string;
}

export type Database = {
  public: {
    Tables: {
      profiles: Table<{ id: string; full_name: string; phone: string | null; avatar_url: string | null; created_at: string; updated_at: string }>;
      properties: Table<PropertyRow>;
      property_memberships: Table<MembershipRow>;
      meters: Table<{ id: string; property_id: string; external_meter_id: string | null; meter_type: "electricity" | "solar" | "hybrid"; provider: string; status: "active" | "inactive"; metadata: Json; created_at: string }>;
      energy_readings: Table<EnergyReadingRow>;
      energy_tariffs: Table<TariffRow>;
      price_adjustments: Table<{ id: string; property_id: string; previous_tariff_id: string | null; proposed_usage_rate: number | null; proposed_feed_in_rate: number | null; proposed_daily_charge: number | null; reason: string | null; effective_from: string; status: "draft" | "pending" | "approved" | "rejected" | "applied"; created_by: string; approved_by: string | null; created_at: string; updated_at: string }>;
      bills: Table<BillRow>;
      solar_assessments: Table<{ id: string; property_id: string; image_path: string | null; image_source: string | null; roof_area_m2: number | null; usable_roof_area_m2: number; estimated_panel_count: number; estimated_system_kw: number; estimated_annual_generation_kwh: number; estimated_installation_cost: number; estimated_annual_savings: number; estimated_payback_years: number; estimated_roi_pct: number; estimated_carbon_reduction_kg_year: number; assumptions: Json; status: "draft" | "completed" | "review_required"; created_by: string; created_at: string; updated_at: string }>;
      solar_products: Table<{ id: string; manufacturer: string; model: string; panel_power_w: number; panel_area_m2: number; unit_cost: number | null; warranty_years: number | null; efficiency_pct: number | null; metadata: Json; active: boolean; created_at: string }>;
      lease_requests: Table<{ id: string; property_id: string; tenant_user_id: string; request_type: string; message: string; status: "submitted" | "under_review" | "approved" | "rejected" | "cancelled"; reviewed_by: string | null; review_notes: string | null; created_at: string; updated_at: string }>;
      proposals: Table<{ id: string; property_id: string; proposal_type: "solar" | "energy_price" | "ppa" | "lease"; title: string; description: string; proposed_by: string; recipient_user_id: string | null; status: "draft" | "sent" | "accepted" | "rejected" | "expired"; financial_summary: Json; terms: Json; valid_until: string | null; created_at: string; updated_at: string }>;
      contracts: Table<{ id: string; property_id: string; proposal_id: string | null; contract_type: "ppa" | "lease_amendment" | "energy_agreement"; tenant_user_id: string | null; landlord_user_id: string | null; agent_user_id: string | null; status: "draft" | "review" | "sent" | "signed" | "cancelled"; effective_from: string | null; effective_to: string | null; terms: Json; document_path: string | null; created_by: string; created_at: string; updated_at: string }>;
      energy_control_settings: Table<{ id: string; property_id: string; mode: "automatic" | "self_consumption" | "backup" | "manual"; battery_min_reserve_pct: number; allow_grid_export: boolean; max_grid_import_kw: number | null; updated_by: string | null; updated_at: string }>;
      energy_control_commands: Table<{ id: string; property_id: string; command_type: string; payload: Json; status: "queued" | "sent" | "acknowledged" | "failed" | "cancelled"; requested_by: string; requested_at: string; processed_at: string | null; response: Json | null }>;
      audit_logs: Table<{ id: string; property_id: string | null; actor_user_id: string | null; action: string; entity_type: string; entity_id: string | null; before_data: Json | null; after_data: Json | null; created_at: string }>;
    };
    Views: Record<string, never>;
    Functions: {
      has_property_role: { Args: { target_property_id: string; allowed_roles: PropertyRole[] }; Returns: boolean };
      is_property_member: { Args: { target_property_id: string }; Returns: boolean };
    };
    Enums: {
      property_member_role: PropertyRole;
      membership_status: MembershipStatus;
    };
    CompositeTypes: Record<string, never>;
  };
};
