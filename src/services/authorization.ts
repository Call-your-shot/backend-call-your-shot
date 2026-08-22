import type { ManagementRole, PropertyRole } from "@backend/db/database.types";

export function canManageProperty(role: PropertyRole | null): role is ManagementRole {
  return role === "landlord" || role === "agent";
}

export function canReadProperty(role: PropertyRole | null) {
  return role === "tenant" || role === "landlord" || role === "agent";
}

export function canTenantCreateLeaseRequest(role: PropertyRole | null) {
  return role === "tenant";
}

export function canIngestMeterData(authMode: string | null) {
  return authMode === "secret";
}
