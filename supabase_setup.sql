create table positions (
  id bigint generated always as identity primary key,
  user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  coin text not null,
  side text not null check (side in ('LONG','SHORT')),
  entry numeric not null,
  size numeric not null,
  stop numeric,
  tp numeric,
  note text,
  status text not null default 'open',
  close_price numeric,
  opened_at timestamptz not null default now(),
  closed_at timestamptz
);
alter table positions enable row level security;
create policy "own rows only" on positions for all
  using (auth.uid() = user_id) with check (auth.uid() = user_id);
