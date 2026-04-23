-- ============================================================
-- Update RLS Policies for assistant_hod Role
-- This must be in a separate migration after the enum value is added
-- ============================================================

-- Update RLS policy to include assistant_hod for availability viewing
drop policy if exists "Admins and department heads can view all availability" on public.availability;
create policy "Admins and department heads can view all availability"
    on public.availability for select
    using (
        public.has_app_role('admin')
        or public.has_app_role('hod')
        or public.has_app_role('assistant_hod')
    );

-- Note: All other permissions for HOD use the is_hod() function which checks
-- departments.hod_id, not the app_role. Assistant HODs will need to be set
-- as HOD of a department to manage it, or we rely on API-level permissions.
