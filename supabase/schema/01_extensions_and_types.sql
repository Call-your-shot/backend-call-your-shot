create extension if not exists "pgcrypto";

create type property_member_role as enum ('tenant', 'landlord', 'agent');
create type membership_status as enum ('invited', 'active', 'inactive');
create type meter_type as enum ('electricity', 'solar', 'hybrid');
create type meter_status as enum ('active', 'inactive');
create type energy_reading_source as enum ('mock', 'meter_api', 'manual', 'simulation');
create type adjustment_status as enum ('draft', 'pending', 'approved', 'rejected', 'applied');
create type bill_status as enum ('draft', 'issued', 'paid', 'overdue', 'cancelled');
create type solar_assessment_status as enum ('draft', 'completed', 'review_required');
create type lease_request_status as enum ('submitted', 'under_review', 'approved', 'rejected', 'cancelled');
create type proposal_type as enum ('solar', 'energy_price', 'ppa', 'lease');
create type proposal_status as enum ('draft', 'sent', 'accepted', 'rejected', 'expired');
create type contract_type as enum ('ppa', 'lease_amendment', 'energy_agreement');
create type contract_status as enum ('draft', 'review', 'sent', 'signed', 'cancelled');
create type energy_control_mode as enum ('automatic', 'self_consumption', 'backup', 'manual');
create type control_command_status as enum ('queued', 'sent', 'acknowledged', 'failed', 'cancelled');

