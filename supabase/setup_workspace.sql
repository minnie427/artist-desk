-- 첫 작가 워크스페이스와 사용자 등록 (Supabase SQL 편집기나 Claude 커넥터로 한 번 실행)
-- 이메일은 저장소에 올리지 않도록 실행할 때 직접 채운다.
insert into public.workspaces (slug, name) values ('leehyunjung', '이현정') on conflict (slug) do nothing;
insert into public.members (workspace_id, email, role)
select id, :'owner_email', 'owner' from public.workspaces where slug = 'leehyunjung'
on conflict do nothing;
-- 작가님 계정 (확인 후 실행)
-- insert into public.members (workspace_id, email, role) select id, '작가님 구글 이메일', 'artist' from public.workspaces where slug = 'leehyunjung' on conflict do nothing;
