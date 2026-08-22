-- Add invite_token and invite_url to proposals table for landlord sharing & acceptance flow
alter table proposals
  add column if not exists invite_token text unique,
  add column if not exists invite_url text;
