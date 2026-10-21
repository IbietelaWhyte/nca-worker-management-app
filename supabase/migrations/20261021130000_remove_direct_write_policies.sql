-- ============================================================
-- Migration: Remove direct-write policies
--
-- Every write in this app goes through the API on the service role, which bypasses RLS: the SPA
-- uses supabase-js for sign-in and password reset only. The FOR ALL policies below therefore
-- authorised nothing the app does — but the anon key and project URL ship in the SPA, so they
-- let any signed-in head write straight through PostgREST and skip every rule the API applies:
-- the staffing ceiling and the texts sent when a rota changes, the leave overlap check, the
-- all-or-nothing membership checks, and the department scoping itself.
--
-- The sharpest of them, "HODs can manage assistant HODs in their departments", had no WITH
-- CHECK, so a head could make anybody an assistant head of their department — and assistant
-- heads hold write access across that department's schedules, leave and monthly leads.
--
-- Several were also dead: has_app_role() reads worker_app_roles, which has RLS on and no
-- policies, so every "Admins can ..." clause was always false.
--
-- Reads are untouched. Every table here keeps its own SELECT policy, so direct reads behave
-- exactly as before; a FOR ALL policy's read half only ever duplicated or widened one of them.
-- A table with RLS enabled and no write policy denies every direct write, which is the intent.
-- ============================================================

drop policy "Admins and department heads can manage availability prompts" on public.availability_prompts;
drop policy "Admins can manage assistant HOD assignments" on public.department_assistant_hods;
drop policy "HODs can manage assistant HODs in their departments" on public.department_assistant_hods;
drop policy "Admins and department heads can manage roles" on public.department_roles;
drop policy "Admins can manage departments" on public.departments;
drop policy "Admins and department heads can manage monthly leads" on public.monthly_leads;
drop policy "Admins and department heads can manage assignments" on public.schedule_assignments;
drop policy "Admins and department heads can manage schedules" on public.schedules;
drop policy "Assistant heads can manage their departments' schedules" on public.schedules;
drop policy "Admins can manage special services" on public.special_services;
drop policy "Admins and department heads can manage subteams" on public.subteams;
drop policy "Admins and department heads can manage memberships" on public.worker_departments;
drop policy "Admins and department heads can manage leave" on public.worker_leave;
drop policy "Admins can manage all workers" on public.workers;
