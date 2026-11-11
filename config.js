// Artist Desk 공개 설정 — 여기 들어가는 값은 공개돼도 괜찮은 값만 (Supabase 공개 키는 접근 규칙으로 보호돼요)
window.DESK_CONFIG = {
  supabaseUrl: "",        // 예: https://xxxx.supabase.co
  supabaseAnonKey: "",    // Supabase 프로젝트 설정 → API → anon public key
  workspace: "leehyunjung" // 작가 워크스페이스 이름 (주소 ?ws=이름 으로 바꿀 수 있음)
};
