-- ============================================================
-- Migration: Role requirements per subteam
--
-- Generation filled each subteam to its staffing band by fairness alone, with no
-- notion of a worker's department role, so a Children's Church class could come
-- out as three Helpers and no Teacher. A head can now say "at least 1 Teacher and
-- 2 Helpers on every rota" for a subteam, and the planner fills those first.
--
-- Each count is a MINIMUM. Slots left over, up to the subteam's maximum, still go
-- to whoever is next in line whatever their role, and the existing fewest/most
-- band is unchanged. A count of 0 is simply no row.
--
-- Two rules a constraint here cannot express live in SubteamService:
--   * the role must belong to the subteam's own department;
--   * the minimums together may not exceed the subteam's maximum.
--
-- Requirements steer generation only. They are not stamped onto schedules, so
-- changing them never relabels a rota already made.
-- ============================================================

create table public.subteam_role_requirements (
    subteam_id         uuid not null references public.subteams(id) on delete cascade,
    department_role_id uuid not null references public.department_roles(id) on delete cascade,
    min_count          smallint not null check (min_count >= 1),

    -- Non-partial, so it is also a legal ON CONFLICT target for the replace-all upsert.
    primary key (subteam_id, department_role_id)
);

comment on table public.subteam_role_requirements is
    'At least min_count workers holding department_role_id on every rota generated for subteam_id.';

-- Read and written only through the API, which bypasses RLS. Enabled with no policy so
-- the publishable key can neither read nor write it.
alter table public.subteam_role_requirements enable row level security;
