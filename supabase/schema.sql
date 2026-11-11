-- Artist Desk · Supabase 스키마 (v1)
-- 작가 워크스페이스마다 데이터를 나누고, 등록된 이메일만 읽고 쓸 수 있게 한다.
-- 앱은 '문서 저장소' 방식(컬렉션/문서 id/JSON)으로 데이터를 다룬다 — 지금 claude.ai 앱과 같은 구조라 그대로 옮길 수 있다.

create extension if not exists pgcrypto;

-- 작가 워크스페이스 (작가 한 명 = 하나)
create table if not exists public.workspaces (
  id uuid primary key default gen_random_uuid(),
  slug text unique not null,               -- 주소에 쓰는 짧은 이름 (예: leehyunjung)
  name text not null,                      -- 화면에 보이는 이름 (예: 이현정)
  created_at timestamptz not null default now()
);

-- 누가 어느 워크스페이스에 들어올 수 있는지 (구글 로그인 이메일 기준)
create table if not exists public.members (
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  email text not null,
  role text not null check (role in ('owner', 'admin', 'artist', 'viewer')),
  created_at timestamptz not null default now(),
  primary key (workspace_id, email)
);

-- 모든 기록 (calls, tasks, events, exhibitions, settings, feed, inbox, requests, feedmarks …)
create table if not exists public.docs (
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  coll text not null,
  id text not null,
  data jsonb not null default '{}'::jsonb,
  version integer not null default 1,
  updated_at timestamptz not null default now(),
  updated_by text,
  primary key (workspace_id, coll, id)
);
create index if not exists docs_ws_coll on public.docs (workspace_id, coll);

-- 고칠 때마다 버전·시각·고친 사람을 남긴다
create or replace function public.docs_touch() returns trigger language plpgsql as $$
begin
  if tg_op = 'UPDATE' then new.version := old.version + 1; end if;
  new.updated_at := now();
  new.updated_by := coalesce(auth.jwt() ->> 'email', new.updated_by, 'system');
  return new;
end $$;
drop trigger if exists docs_touch on public.docs;
create trigger docs_touch before insert or update on public.docs for each row execute function public.docs_touch();

-- 지운 기록도 30일은 되살릴 수 있게 보관
create table if not exists public.docs_trash (
  workspace_id uuid not null,
  coll text not null,
  id text not null,
  data jsonb not null,
  deleted_at timestamptz not null default now(),
  deleted_by text
);
create or replace function public.docs_keep_deleted() returns trigger language plpgsql security definer set search_path = public as $$
begin
  insert into public.docs_trash (workspace_id, coll, id, data, deleted_by) values (old.workspace_id, old.coll, old.id, old.data, auth.jwt() ->> 'email');
  return old;
end $$;
drop trigger if exists docs_keep_deleted on public.docs;
create trigger docs_keep_deleted before delete on public.docs for each row execute function public.docs_keep_deleted();

-- 권한 확인 (RLS가 자기 자신을 다시 부르지 않게 security definer)
create or replace function public.has_role(ws uuid, roles text[]) returns boolean language sql stable security definer set search_path = public as $$
  select exists (select 1 from public.members m where m.workspace_id = ws and lower(m.email) = lower(auth.jwt() ->> 'email') and m.role = any(roles));
$$;

alter table public.workspaces enable row level security;
alter table public.members enable row level security;
alter table public.docs enable row level security;
alter table public.docs_trash enable row level security;

drop policy if exists ws_read on public.workspaces;
create policy ws_read on public.workspaces for select using (public.has_role(id, array['owner','admin','artist','viewer']));

drop policy if exists mem_read on public.members;
create policy mem_read on public.members for select using (public.has_role(workspace_id, array['owner','admin','artist','viewer']));
drop policy if exists mem_admin on public.members;
create policy mem_admin on public.members for all using (public.has_role(workspace_id, array['owner'])) with check (public.has_role(workspace_id, array['owner']));

drop policy if exists docs_read on public.docs;
create policy docs_read on public.docs for select using (public.has_role(workspace_id, array['owner','admin','artist','viewer']));
drop policy if exists docs_write on public.docs;
create policy docs_write on public.docs for insert with check (public.has_role(workspace_id, array['owner','admin','artist']));
drop policy if exists docs_update on public.docs;
create policy docs_update on public.docs for update using (public.has_role(workspace_id, array['owner','admin','artist'])) with check (public.has_role(workspace_id, array['owner','admin','artist']));
drop policy if exists docs_delete on public.docs;
create policy docs_delete on public.docs for delete using (public.has_role(workspace_id, array['owner','admin','artist']));

drop policy if exists trash_read on public.docs_trash;
create policy trash_read on public.docs_trash for select using (public.has_role(workspace_id, array['owner','admin']));

-- 일부 칸만 바꾸기 (동시에 고쳐도 서로 덮어쓰지 않게 서버에서 합친다). "__delete__": true 인 칸은 지운다.
create or replace function public.doc_patch(p_ws uuid, p_coll text, p_id text, p_patch jsonb) returns integer language plpgsql security invoker set search_path = public as $$
declare v integer; dels text[];
begin
  select coalesce(array_agg(key), '{}') into dels from jsonb_each(p_patch) where value = '{"__delete__": true}'::jsonb;
  insert into public.docs as d (workspace_id, coll, id, data) values (p_ws, p_coll, p_id, (p_patch - dels))
  on conflict (workspace_id, coll, id) do update set data = (d.data || (p_patch - dels)) - dels
  returning d.version into v;
  return v;
end $$;

-- 화면이 바로 바뀌도록 실시간 알림
do $$ begin
  begin alter publication supabase_realtime add table public.docs; exception when duplicate_object then null; end;
end $$;
alter table public.docs replica identity full;
