create trigger profiles_updated_at before update on profiles for each row execute function set_updated_at();
create trigger properties_updated_at before update on properties for each row execute function set_updated_at();
create trigger property_addresses_updated_at before update on property_addresses for each row execute function set_updated_at();
create trigger property_memberships_updated_at before update on property_memberships for each row execute function set_updated_at();
create trigger price_adjustments_updated_at before update on price_adjustments for each row execute function set_updated_at();
create trigger bills_updated_at before update on bills for each row execute function set_updated_at();
create trigger solar_assessments_updated_at before update on solar_assessments for each row execute function set_updated_at();
create trigger solar_installations_updated_at before update on solar_installations for each row execute function set_updated_at();
create trigger pricing_contracts_updated_at before update on pricing_contracts for each row execute function set_updated_at();
create trigger lease_requests_updated_at before update on lease_requests for each row execute function set_updated_at();
create trigger proposals_updated_at before update on proposals for each row execute function set_updated_at();
create trigger contracts_updated_at before update on contracts for each row execute function set_updated_at();

create trigger audit_energy_tariffs after insert or update or delete on energy_tariffs for each row execute function audit_row_change();
create trigger audit_price_adjustments after insert or update or delete on price_adjustments for each row execute function audit_row_change();
create trigger audit_lease_requests after insert or update or delete on lease_requests for each row execute function audit_row_change();
create trigger audit_contracts after insert or update or delete on contracts for each row execute function audit_row_change();
create trigger audit_energy_control_settings after insert or update or delete on energy_control_settings for each row execute function audit_row_change();
create trigger audit_energy_control_commands after insert or update or delete on energy_control_commands for each row execute function audit_row_change();
