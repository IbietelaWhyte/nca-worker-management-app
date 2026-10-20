-- ============================================================
-- Migration: Remove direct writes to availability
--
-- "Workers can manage their own availability" let a signed-in worker insert, update and delete
-- their own availability rows straight through PostgREST with the public anon key. That skipped
-- every rule the API enforces on the same writes: the cut-off that closes a date
-- (settings.availability_notice_days), and the inversion that only ever records "cannot serve"
-- (see CLAUDE.md, Availability). It only reached the worker's own answers, so the harm was
-- limited, but the rules exist because a rota is planned off those answers.
--
-- The app never touches this table through supabase-js — the signed-in page and the texted link
-- both go through the API on the service role — so the policy is dropped rather than narrowed.
-- It cannot be narrowed in place anyway: a policy's command cannot be altered, and a
-- `with check (false)` on a FOR ALL policy would still allow DELETE, which is judged by USING.
-- ============================================================

drop policy "Workers can manage their own availability" on public.availability;
