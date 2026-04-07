-- Confirmation tokens for worker schedule assignment confirmation via SMS links.
-- Each assignment gets at most one active token (enforced by the unique constraint).
-- Tokens expire 48 hours after creation and are single-use (used_at tracks consumption).

create table public.confirmation_tokens (
    id              uuid primary key default gen_random_uuid(),
    worker_id       uuid not null references public.workers(id) on delete cascade,
    assignment_id   uuid not null references public.schedule_assignments(id) on delete cascade,
    expires_at      timestamptz not null,
    used_at         timestamptz,
    created_at      timestamptz not null default now(),

    -- One active token per assignment at a time
    constraint unique_assignment_token unique (assignment_id)
);

create index idx_confirmation_tokens_assignment on public.confirmation_tokens (assignment_id);
create index idx_confirmation_tokens_expires_at on public.confirmation_tokens (expires_at);

-- RLS: tokens are only accessible via the service role (used by the backend).
-- Public confirmation endpoint uses the service-role client, not anon.
alter table public.confirmation_tokens enable row level security;

-- No policies needed for anon/authenticated users — backend uses service role key.
