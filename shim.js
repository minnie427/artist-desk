// Artist Desk · 데이터 연결부
// 화면 코드는 claude.ai 앱 때와 같은 방식(window.claude.use("db"))으로 데이터를 다루고,
// 이 파일이 그 요청을 Supabase(구글 로그인 + 작가 워크스페이스별 접근 규칙)로 바꿔 준다.
(function () {
  const C = window.DESK_CONFIG || {};
  const qs = new URLSearchParams(location.search);
  const WS_SLUG = qs.get("ws") || C.workspace;
  const configured = !!(C.supabaseUrl && C.supabaseAnonKey && window.supabase);
  const sb = configured ? window.supabase.createClient(C.supabaseUrl, C.supabaseAnonKey, { auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true, flowType: "implicit" } }) : null;

  let wsId = null, wsName = "", me = null, role = null;
  const cache = new Map();                 // coll -> Map(id -> { data, version })
  const collL = new Map(), docL = new Map();
  const coll = (c) => { if (!cache.has(c)) cache.set(c, new Map()); return cache.get(c); };
  const emitColl = (c) => { const ls = collL.get(c); if (!ls) return; const m = coll(c); const snap = { docs: [...m.entries()].map(([id, v]) => ({ id, data: () => v.data })) }; ls.forEach((f) => { try { f(snap); } catch (e) { console.error(e); } }); };
  const emitDoc = (c, id) => { const ls = docL.get(c + "/" + id); if (!ls) return; const v = coll(c).get(id); const snap = { exists: !!v, id, data: () => (v ? v.data : undefined) }; ls.forEach((f) => { try { f(snap); } catch (e) { console.error(e); } }); };
  const put = (c, id, data, version) => { coll(c).set(id, { data, version }); emitColl(c); emitDoc(c, id); };
  const drop = (c, id) => { coll(c).delete(id); emitColl(c); emitDoc(c, id); };

  // ---------- 로그인 화면 ----------
  function gate(title, body, actions) {
    let el = document.getElementById("desk-gate");
    if (!el) { el = document.createElement("div"); el.id = "desk-gate"; document.body.appendChild(el); }
    el.innerHTML = "";
    const box = document.createElement("div"); box.className = "dg-box";
    box.innerHTML = '<div class="dg-logo">A</div><h1>Artist Desk</h1><h2></h2><p></p>';
    box.querySelector("h2").textContent = title; box.querySelector("p").textContent = body;
    (actions || []).forEach(([label, fn, primary]) => { const b = document.createElement("button"); b.type = "button"; b.className = "dg-btn" + (primary ? " primary" : ""); b.textContent = label; b.onclick = fn; box.appendChild(b); });
    el.appendChild(box);
  }
  function ungate() { const el = document.getElementById("desk-gate"); if (el) el.remove(); }
  const st = document.createElement("style");
  st.textContent = "#desk-gate{position:fixed;inset:0;z-index:100;background:var(--bg,#f4f5f2);display:grid;place-items:center;padding:24px}" +
    ".dg-box{max-width:380px;width:100%;background:var(--surface,#fff);border:1px solid var(--line,#e3e1db);border-radius:16px;padding:36px 28px 30px;display:flex;flex-direction:column;gap:10px;text-align:center;box-shadow:0 24px 60px -16px rgba(22,30,40,.18)}" +
    ".dg-logo{width:44px;height:44px;border-radius:12px;background:var(--accent,#2a3b73);color:#fff;display:grid;place-items:center;font:600 22px/1 var(--f-title,serif);margin:0 auto 4px}" +
    ".dg-box h1{font:600 26px/1.2 var(--f-title,serif);letter-spacing:-.02em;margin:4px 0 0}.dg-box h2{font-size:15px;margin:0;color:var(--ink-2,#5d5c58);font-weight:600}.dg-box p{font-size:13.5px;color:var(--ink-2,#5d5c58);margin:0 0 6px;white-space:pre-line}" +
    ".dg-in{height:44px;border-radius:10px;border:1px solid var(--line-2,#d3d1ca);padding:0 12px;font:15px/1 inherit;background:var(--surface,#fff);color:inherit}.dg-msg{font-size:13px!important;min-height:1em}" +
    ".dg-btn{height:44px;border-radius:10px;border:1px solid var(--line-2,#d3d1ca);background:var(--surface,#fff);font:600 14.5px/1 inherit;cursor:pointer}.dg-btn.primary{background:var(--accent,#2a3b73);color:#fff;border-color:var(--accent,#2a3b73)}";
  document.head.appendChild(st);

  const METHODS = C.loginMethods || ["email"];
  async function sendLink(email, msgEl, btn) {
    email = String(email || "").trim();
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) { msgEl.textContent = "이메일 주소를 확인해 주세요."; return; }
    btn.disabled = true; msgEl.textContent = "보내는 중…";
    const redirectTo = location.origin + location.pathname + location.search;
    const { error } = await sb.auth.signInWithOtp({ email, options: { emailRedirectTo: redirectTo, shouldCreateUser: true } });
    btn.disabled = false;
    msgEl.textContent = error ? "보내지 못했어요: " + error.message : email + " 로 로그인 링크를 보냈어요. 메일의 링크를 누르면 바로 들어와요. (안 보이면 스팸함도 확인해 주세요)";
  }
  function loginGate() {
    gate("작가 워크스페이스에 로그인", METHODS.includes("email") ? "등록된 이메일로 로그인 링크를 받아요." : "등록된 구글 계정으로 로그인해 주세요.", METHODS.includes("google") ? [["구글로 로그인", signIn, !METHODS.includes("email")]] : []);
    if (!METHODS.includes("email")) return;
    const box = document.querySelector("#desk-gate .dg-box");
    const inp = document.createElement("input"); inp.type = "email"; inp.placeholder = "이메일 주소"; inp.autocomplete = "email"; inp.className = "dg-in";
    const btn = document.createElement("button"); btn.type = "button"; btn.className = "dg-btn primary"; btn.textContent = "로그인 링크 받기";
    const msg = document.createElement("p"); msg.className = "dg-msg";
    btn.onclick = () => sendLink(inp.value, msg, btn);
    inp.addEventListener("keydown", (e) => { if (e.key === "Enter") sendLink(inp.value, msg, btn); });
    const first = box.querySelector(".dg-btn");
    box.insertBefore(inp, first); box.insertBefore(btn, first); box.insertBefore(msg, first);
  }
  async function signIn() {
    const redirectTo = location.origin + location.pathname + location.search;
    const { error } = await sb.auth.signInWithOAuth({ provider: "google", options: { redirectTo } });
    if (error) gate("로그인하지 못했어요", error.message, [["다시 시도", signIn, true]]);
  }
  async function signOut() { await sb.auth.signOut(); location.reload(); }

  async function loadAll() {
    const page = 1000;
    for (let from = 0; ; from += page) {
      const { data, error } = await sb.from("docs").select("coll,id,data,version").eq("workspace_id", wsId).range(from, from + page - 1);
      if (error) throw error;
      for (const r of data) coll(r.coll).set(r.id, { data: r.data, version: r.version });
      if (data.length < page) break;
    }
  }
  function subscribe() {
    sb.channel("docs-" + wsId)
      .on("postgres_changes", { event: "*", schema: "public", table: "docs", filter: "workspace_id=eq." + wsId }, (p) => {
        if (p.eventType === "DELETE") { if (p.old && p.old.coll) drop(p.old.coll, p.old.id); return; }
        const r = p.new; if (r && r.coll) put(r.coll, r.id, r.data, r.version);
      })
      .subscribe();
  }

  const ready = (async () => {
    if (!configured) { return { ok: false, why: "config" }; }
    const { data: { session } } = await sb.auth.getSession();
    if (!session) {
      loginGate();
      return new Promise(() => {}); // 로그인 화면에서 멈춤 (로그인하면 페이지가 다시 열림)
    }
    me = session.user;
    const { data: w, error: we } = await sb.from("workspaces").select("id,name").eq("slug", WS_SLUG).maybeSingle();
    if (we || !w) {
      gate("들어갈 수 있는 워크스페이스가 없어요", (me.email || "") + " 계정은 ‘" + WS_SLUG + "’ 워크스페이스에 등록되지 않았어요.\n관리자에게 이 이메일 등록을 요청해 주세요.", [["다른 계정으로 로그인", signOut, true]]);
      return new Promise(() => {});
    }
    wsId = w.id; wsName = w.name;
    const { data: m } = await sb.from("members").select("role").eq("workspace_id", wsId).ilike("email", me.email).maybeSingle();
    role = (m && m.role) || "viewer";
    await loadAll();
    subscribe();
    ungate();
    return { ok: true };
  })().catch((e) => { gate("불러오지 못했어요", String((e && e.message) || e), [["다시 시도", () => location.reload(), true]]); return new Promise(() => {}); });

  const rid = () => Array.from(crypto.getRandomValues(new Uint8Array(15)), (b) => "abcdefghijklmnopqrstuvwxyz0123456789"[b % 36]).join("").slice(0, 20);
  const split = (path) => { const i = path.lastIndexOf("/"); return [path.slice(0, i), path.slice(i + 1)]; };
  function docRef(c, id) {
    return {
      onSnapshot(cb) { const k = c + "/" + id; if (!docL.has(k)) docL.set(k, new Set()); docL.get(k).add(cb); setTimeout(() => emitDoc(c, id), 0); return () => docL.get(k).delete(cb); },
      async update(patch) {
        const { data: v, error } = await sb.rpc("doc_patch", { p_ws: wsId, p_coll: c, p_id: id, p_patch: patch });
        if (error) throw error;
        const cur = Object.assign({}, (coll(c).get(id) || {}).data || {});
        for (const [k, val] of Object.entries(patch)) { if (val && typeof val === "object" && val.__delete__ === true) delete cur[k]; else cur[k] = val; }
        put(c, id, cur, v);
      },
      async set(data) {
        const { data: r, error } = await sb.from("docs").upsert({ workspace_id: wsId, coll: c, id, data }).select("version").single();
        if (error) throw error; put(c, id, data, r && r.version);
      },
      async delete() { const { error } = await sb.from("docs").delete().match({ workspace_id: wsId, coll: c, id }); if (error) throw error; drop(c, id); }
    };
  }
  const dbApi = {
    collection(c) {
      return {
        onSnapshot(cb) { if (!collL.has(c)) collL.set(c, new Set()); collL.get(c).add(cb); setTimeout(() => emitColl(c), 0); return () => collL.get(c).delete(cb); },
        doc: (id) => docRef(c, id),
        async add(data) { const id = rid(); const { data: r, error } = await sb.from("docs").insert({ workspace_id: wsId, coll: c, id, data }).select("version").single(); if (error) throw error; put(c, id, data, r && r.version); return { id }; }
      };
    },
    doc(path) { const [c, id] = split(path); return docRef(c, id); }
  };
  const userApi = { isOwner: async () => ["owner", "admin"].includes(role), can: async (p) => p === "data.write" ? role !== "viewer" : true, email: () => me && me.email };
  const dlApi = {
    async save({ filename, data }) {
      const blob = new Blob([data], { type: /\.csv$/i.test(filename) ? "text/csv;charset=utf-8" : "application/json" });
      const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = filename; document.body.appendChild(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 500);
    }
  };

  window.DESK = { signOut, email: () => me && me.email, role: () => role, workspace: () => wsName, web: true };
  window.claude = {
    async use(name) {
      const r = await ready;
      if (!r.ok) return null;
      if (name === "db") return dbApi;
      if (name === "user") return userApi;
      if (name === "downloads") return dlApi;
      return null; // mcp(메일·캘린더·드라이브 직접 연결)는 웹앱 1차 버전에서 아직 없음
    }
  };
})();
