-- ============================================================
-- Add assistant_hod Role to System
-- ============================================================

-- Add 'assistant_hod' to the app_role enum
-- Note: This must be done separately before using the new value
alter type public.app_role add value if not exists 'assistant_hod';

comment on type public.app_role is 'Application-level roles: admin (full access), hod (department head), assistant_hod (assistant department head), worker (basic member)';
