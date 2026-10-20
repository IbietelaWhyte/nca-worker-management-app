-- ============================================================
-- Migration: Restrict direct access to workers
--
-- The anon key and project URL ship in the SPA, so anybody can call PostgREST directly, and RLS
-- is the only thing guarding that path. Two policies from the initial schema were too wide:
--
--   * "Workers can view all active workers" named no role, so it applied to anon as well:
--     anyone holding the public anon key could list every active worker's name, phone number
--     and email, without signing in. Signed-in workers could read everybody's too.
--   * "Workers can update their own profile" let a worker rewrite their own row — email,
--     phone, is_active — around the API's validation. The backend matches a login to its
--     worker by email, so changing it detached the account.
--
-- The app never reads or writes `workers` through supabase-js; every read and write goes through
-- the API on the service role, which bypasses RLS. So the select policy is narrowed to the
-- caller's own row (which current_worker_id() and the policies joining workers on
-- `w.auth_user_id = auth.uid()` still need) and the update policy is removed.
-- ============================================================

alter policy "Workers can view all active workers"
    on public.workers
    to authenticated
    using (auth_user_id = auth.uid());

alter policy "Workers can view all active workers"
    on public.workers
    rename to "Workers can view their own profile";

drop policy "Workers can update their own profile" on public.workers;
