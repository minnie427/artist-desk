# 자동 작업용 데이터 통로 (Supabase)

예약 작업(Claude)이 웹앱 데이터를 파일로 바로 읽고 쓰는 방법. 비밀값은 저장소에 없다.

1. Supabase 커넥터(execute_sql)로 30~60분짜리 토큰을 받는다.
   `select private.issue_agent_token('leehyunjung', array['feed','feedruns','calls','inbox'], 60) as t;`
2. 주소·공개 키는 `config.js`의 supabaseUrl, supabaseAnonKey.
3. 읽기: `POST {url}/rest/v1/rpc/agent_read` body `{"p_token": t, "p_colls": ["calls","settings"]}` → `{coll: {id: data}}`
4. 쓰기: `POST {url}/rest/v1/rpc/agent_write` body `{"p_token": t, "p_docs": [{"coll","id","data"}] | [{"coll","id","patch"}]}`
   - data = 문서를 통째로 바꿈, patch = 지정한 칸만 (`{"__delete__": true}`는 칸 삭제). 한 번에 500개 이하.
   - 토큰 발급 때 정한 컬렉션(scope)만 쓸 수 있다. 읽기는 워크스페이스 전체.
5. 헤더: `apikey: {anon}`, `Authorization: Bearer {anon}`, `Content-Type: application/json`.
