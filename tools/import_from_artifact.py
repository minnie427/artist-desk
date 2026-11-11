"""claude.ai 앱(ArtifactData)에서 내려받은 기록을 Supabase docs 표에 넣는 SQL로 바꾼다.

사용: python3 tools/import_from_artifact.py <내려받은 폴더> <워크스페이스 slug> > data/import.sql
  - 폴더 구조: <폴더>/<컬렉션>/<문서id>.json  (ArtifactData list/get 의 out_dir 형식)
  - 결과 SQL은 작가 데이터라 저장소에 올리지 않는다 (data/ 는 .gitignore)
"""
import json, os, sys

src, slug = sys.argv[1], sys.argv[2]
print("-- Artist Desk 가져오기 · workspace=%s" % slug)
print("begin;")
n = 0
for coll in sorted(os.listdir(src)):
    d = os.path.join(src, coll)
    if not os.path.isdir(d):
        continue
    for f in sorted(os.listdir(d)):
        if not f.endswith(".json"):
            continue
        doc_id = f[:-5]
        data = json.dumps(json.load(open(os.path.join(d, f), encoding="utf-8")), ensure_ascii=False)
        tag = "$d%d$" % n
        while tag in data:
            tag = "$d%dx$" % n
        print("insert into public.docs (workspace_id, coll, id, data) select w.id, %s, %s, %s%s%s::jsonb from public.workspaces w where w.slug = %s "
              "on conflict (workspace_id, coll, id) do update set data = excluded.data;" % (
                  "'" + coll.replace("'", "''") + "'", "'" + doc_id.replace("'", "''") + "'", tag, data, tag, "'" + slug + "'"))
        n += 1
print("commit;")
print("-- %d건" % n, file=sys.stderr)
