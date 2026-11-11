# Artist Desk

작가가 공모를 찾고, 지원을 관리하고, 작품·이력·자료를 쌓아 가는 작가 워크스페이스.

- **화면**: GitHub Pages (이 저장소의 `index.html`)
- **데이터·로그인**: Supabase — 구글 로그인, 작가 워크스페이스별 접근 규칙(RLS)
- **자동 탐색**: Claude 예약 작업이 Supabase 커넥터로 `docs` 표에 직접 기록

> 공개 저장소예요. 작가 데이터·이메일·비밀 키는 올리지 않아요. `config.js`의 Supabase 공개 키(anon key)는 접근 규칙으로 보호돼요.

## 파일
| 파일 | 하는 일 |
|---|---|
| `index.html` | 앱 화면 전체 (claude.ai 앱 V20에서 옮김) |
| `shim.js` | 로그인 화면 + 화면 코드의 데이터 요청을 Supabase로 연결 |
| `config.js` | Supabase 주소·공개 키·워크스페이스 이름 |
| `supabase/schema.sql` | 표·접근 규칙·실시간 알림 |
| `supabase/setup_workspace.sql` | 첫 워크스페이스와 사용자 등록 |
| `tools/import_from_artifact.py` | claude.ai 앱 기록 → 가져오기 SQL |

## 데이터 구조 (v1)
- `workspaces` 작가 한 명 = 하나 · `members` 들어올 수 있는 구글 이메일과 권한(owner·admin·artist·viewer)
- `docs` 모든 기록을 (워크스페이스, 컬렉션, 문서 id, JSON)으로 — claude.ai 앱과 같은 구조라 화면 코드를 그대로 씀. 고칠 때마다 버전·고친 사람이 남고, 지운 기록은 `docs_trash`에 보관.
- 다음 단계: 공모 정보(여러 작가 공유)와 작가별 지원 기록을 다른 표로 나누기.

## 설치 순서
1. Supabase 새 프로젝트 (지역: Northeast Asia (Seoul))
2. SQL 편집기에서 `supabase/schema.sql` 실행 → `setup_workspace.sql`(소유자 이메일 채워서) 실행
3. Authentication → Providers → Google 켜기 (구글 클라우드 OAuth 클라이언트 ID·비밀번호), Authentication → URL Configuration 에 사이트 주소 추가
4. `config.js`에 프로젝트 주소와 anon 공개 키 넣기
5. GitHub 저장소 Settings → Pages → Deploy from a branch → `main` / `/ (root)`
6. claude.ai 앱 기록 가져오기: `tools/import_from_artifact.py`로 만든 SQL 실행
