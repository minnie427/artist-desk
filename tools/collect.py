#!/usr/bin/env python3
"""이현정 공모 모음 수집기: 여러 모음 사이트에서 공모를 가져와 작가 기준으로 거르고 feed 항목으로 만든다.
사용: python3 -I collect.py OUT_DIR   →  OUT_DIR/feed.json, OUT_DIR/stats.json
"""
import json, re, sys, os, hashlib, html, datetime, subprocess, urllib.request

OUT = sys.argv[1] if len(sys.argv) > 1 else "."
os.makedirs(OUT, exist_ok=True)
KST = datetime.timezone(datetime.timedelta(hours=9))
NOW = datetime.datetime.now(KST)
TODAY = NOW.date()
MIN_DL = TODAY + datetime.timedelta(days=2)
MAX_DL = TODAY + datetime.timedelta(days=200)

def get(url, timeout=40):
    r = subprocess.run(["curl", "-s", "-L", "-m", str(timeout), "-A", "Mozilla/5.0 (Macintosh) LHJ-record/1.0", url], capture_output=True)
    return r.stdout.decode("utf-8", "ignore")

def clean(s):
    s = html.unescape(re.sub(r"<[^>]+>", " ", s or ""))
    return re.sub(r"\s+", " ", s).strip()

def hid(url):
    return "f-" + hashlib.sha1(url.encode()).hexdigest()[:14]

def money(text):
    m = re.search(r"\$\s?(\d{1,3}(?:\.\d\d)?)(?![\d,])\s*(?:USD\s*)?(?:non-refundable\s*)?(?:entry|application|submission|jury|jurying)?\s*fee|fees?\b[^.$]{0,60}?\$\s?(\d{1,3}(?:\.\d\d)?)(?![\d,])|\$\s?(\d{1,3})(?![\d,])\s*(?:for|per) (?:each|one|up to|\d)", text, re.I)
    if m: return float(m.group(1) or m.group(2) or m.group(3)), "USD"
    m = re.search(r"€\s?(\d{1,3})|(\d{1,3})\s?(?:EUR|euro)", text, re.I)
    if m: return float(m.group(1) or m.group(2)), "EUR"
    m = re.search(r"£\s?(\d{1,3})", text)
    if m: return float(m.group(1)), "GBP"
    return None, None

def prize(text):
    m = re.findall(r"\$\s?(\d{1,3}(?:,\d{3})+|\d{4,6})", text)
    vals = [int(x.replace(",", "")) for x in m]
    return max(vals) if vals else None

# ---- 거르는 기준 (작가님 기준을 코드로 옮긴 것) ----
NOT_VISUAL = re.compile(r"\b(poetry|poem|prose|fiction|non-?fiction|essay|writing|writers?|literary|chapbook|manuscript|screenplay|playwright|playwriting|film festival|short film|music|songwriting|dance|theat(er|re)|podcast|scholarships?|workshop|class(es)?|course|storytelling|interview|membership|conference|reading period|emergency grants?|high school|middle school|novella|anthology|cryptid|members only|new member|arts education|mobility|journal \w+ submissions)\b", re.I)
NARROW_MEDIUM = re.compile(r"\b(ceramic|clay|pottery|glass|jewelry|fiber art|quilt|textile|wood ?turn|furniture|sculpture only|photograph(y|ic)|photo contest|camera|film photography|printmaking only|book arts?|call for photography|photography competition)\b", re.I)
BOOTH = re.compile(r"\b(art fair|festival|art show & sale|booth|vendor|craft fair|market|street fair)\b", re.I)
RESIDENCY = re.compile(r"\b(residenc(y|ies)|artist[- ]in[- ]residence|fellowship)\b", re.I)
RESTRICT = re.compile(r"\b(residents? of|living in|based in|artists from|open to (artists )?(in|from) (the )?(state|county|city)|within \d+ miles|regional (artists|showcase)|students?|undergraduate|graduate students|youth|teens?|under (the age of )?\d\d|aged? \d\d ?(-|to) ?\d\d|emerging artists?|bipoc only|women only)\b", re.I)
COMMISSION = re.compile(r"\b(commission|mural|public art|rfq|rfp|request for qualifications|request for proposals)\b", re.I)
GOOD = re.compile(r"\b(abstract|painting|paint|works? on paper|paper|mixed media|ink|drawing|2d|contemporary|open theme|all media|any media|all mediums)\b", re.I)
ONLINE = re.compile(r"\b(online|virtual|digital exhibition|on-?line gallery|web exhibition|vr exhibition|ol)\b", re.I)
INTL = re.compile(r"\b(international|worldwide|world-?wide|global|all countries|any country|artists from around the world|open to all artists)\b", re.I)

def judge(it):
    """flags = 앱에 보이는 표시, drop = 빼는 이유(있으면 피드에서 뺌)"""
    t = (it["title"] + " " + it.get("desc", "")).lower()
    flags, drop = [], None
    if NOT_VISUAL.search(t) and not GOOD.search(it["title"]): drop = "시각예술 아님"
    elif NARROW_MEDIUM.search(it["title"]) and not GOOD.search(it["title"]): drop = "회화를 받지 않는 매체 전용"
    elif BOOTH.search(t) and it.get("kind") in ("아트페어·판매", None) : drop = "부스·페어(작가 부담 큼)"
    elif RESIDENCY.search(it["title"]): drop = "레지던시형"
    elif COMMISSION.search(it["title"]): drop = "커미션·공공미술(제안서형)"
    elif RESTRICT.search(t): drop = "나이·거주지·학생 제한"
    if not drop and it["region"] == "국내":
        tt = it["title"] + " " + it.get("desc", "")
        if re.search(r"입주|레지던시|창작스튜디오|창작공간", it["title"]): drop = "레지던시형"
        elif re.search(r"신진|영 ?코리안|젊은|청년|만\s?\d\d세\s?이하|\d\d세 이하|대학생|청소년|어린이|학생", it["title"]): drop = "나이·신진·학생 제한"
        elif re.search(r"웹툰|만화|레진|캐릭터|이모티콘|디자인|굿즈|영상|사진|활용 공모", it["title"]): drop = "회화 공모 아님"
        elif re.search(r"대관|참가비|부스", tt): drop = "대관·부스(작가 부담 큼)"
    if drop: return flags, drop
    if it["region"] == "국내":
        if re.search(r"서울", it["title"] + it.get("org", "")): flags.append("서울")
        if re.search(r"충청|충남|충북|경상|경남|경북|전라|전남|전북|강원|제주|부산|대구|광주|울산|대전|영천|포항|창원", it["title"] + it.get("org", "")): flags.append("지방 · 실물 운반")
    if it.get("online"): flags.append("디지털 응모·온라인 전시")
    elif it["region"] == "해외": flags.append("선정 시 실물 배송")
    if it.get("intl"): flags.append("국제 공모")
    if it.get("feeAmount") is None and it.get("free"): flags.append("응모비 없음")
    elif it.get("feeAmount") and it["feeAmount"] > 60 and it.get("feeCur") in ("USD", "EUR", "GBP"): flags.append("응모비 높음")
    if it.get("prize"): flags.append("상금 $" + format(it["prize"], ","))
    return flags, None

def score(it):
    s = 0
    if it["region"] == "국내":
        s += 4
        if re.search(r"미술관|재단|문화원|시립|도립|국립|협회|미술대전|정부|청사", it["title"] + it.get("org", "")): s += 1
        if re.search(r"회화|한국화|평면|개인전|전시 지원|여성작가", it["title"]): s += 1
        if re.search(r"충청|충남|충북|경상|경남|경북|전라|전남|전북|강원|제주|부산|대구|광주|울산|대전|영천|포항|창원", it["title"] + it.get("org", "")): s -= 2
    if it.get("online"): s += 3
    if it.get("intl"): s += 2
    if it.get("prize"): s += 1 + (1 if it["prize"] >= 2000 else 0)
    if GOOD.search(it["title"] + " " + it.get("desc", "")): s += 1
    if it.get("feeAmount") and it["feeAmount"] > 60: s -= 2
    if it["region"] == "해외" and not it.get("online") and not it.get("intl"): s -= 2
    return s

def grade(s):
    return "상" if s >= 6 else ("중" if s >= 3 else "하")

ITEMS, STATS = [], {}

def add(src, it):
    it["source"] = src
    it["id"] = hid(it["url"])
    dl = it.get("deadline")
    if not dl: STATS[src]["날짜 없음"] = STATS[src].get("날짜 없음", 0) + 1; return
    d = datetime.date.fromisoformat(dl)
    if d < MIN_DL or d > MAX_DL: STATS[src]["기간 밖"] = STATS[src].get("기간 밖", 0) + 1; return
    flags, drop = judge(it)
    STATS[src]["읽음"] = STATS[src].get("읽음", 0)
    if drop:
        STATS[src].setdefault("뺀 이유", {}); STATS[src]["뺀 이유"][drop] = STATS[src]["뺀 이유"].get(drop, 0) + 1
        return
    it["flags"] = flags
    it["score"] = score(it); it["grade"] = grade(it["score"])
    it["desc"] = (it.get("desc") or "")[:400]
    ITEMS.append(it)
    STATS[src]["통과"] = STATS[src].get("통과", 0) + 1

def run(src, fn):
    STATS[src] = {}
    try:
        n = fn()
        STATS[src]["가져옴"] = n
    except Exception as e:
        STATS[src]["오류"] = str(e)[:200]

# ---- 1) EntryThingy 공개 피드 (미국 중심 + 국제·온라인) ----
def entrythingy():
    d = json.loads(get("https://www.entrythingy.com/calls.json", 60))["items"]
    for x in d:
        e = x.get("_entrythingy", {})
        ct = e.get("call_type") or ""
        loc = e.get("location") or ""
        text = x.get("title", "") + " " + x.get("content_text", "")
        online = ct == "Online Exhibit" or bool(re.search(r"\bonline\b|\bvirtual\b", loc, re.I)) or e.get("state") == "OL"
        kind = {"Art Fair": "아트페어·판매", "Festival": "아트페어·판매", "Online Exhibit": "온라인 공모", "Juried Exhibition": "미술대전·어워드", "Museum Show": "전시 공모", "Gallery Exhibit": "전시 공모"}.get(ct, "전시 공모")
        fee = e.get("entry_fee")
        add("EntryThingy", {
            "title": x.get("title", "").strip(), "org": e.get("organization_name") or "", "url": x.get("url"),
            "deadline": (e.get("deadline") or "")[:10] or None, "region": "해외", "where": loc or "확인 필요",
            "online": online, "intl": bool(INTL.search(text)), "kind": kind,
            "feeAmount": float(fee) if fee else None, "feeCur": "USD" if fee else None, "free": bool(e.get("is_free")),
            "fee": ("$" + ("%g" % float(fee))) if fee else ("무료" if e.get("is_free") else "확인 필요"),
            "desc": x.get("content_text", ""), "prize": None,
        })
    return len(d)

# ---- 2) artshow.com 심사전 목록 (온라인 공모·해외·추천) ----
MON = {m: i for i, m in enumerate(["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"], 1)}
def artshow():
    n = 0
    for page, online_page in [("NA", True), ("Outside", False), ("index", None), ("Northeast", False), ("West", False), ("South", False), ("Midwest", False)]:
        h = get("https://artshow.com/juriedshows/%s.html" % page)
        for m in re.finditer(r'<div class="col-md-3 col-sm-4 listing col-centered" data-endDate="(\d+)/(\d+)/(\d{4})">(.*?)<ul class="share-buttons">', h, re.S):
            mo, da, yr, body = m.groups(); n += 1
            region_txt = clean((re.search(r'<div class="region">(.*?)</div>', body, re.S) or [None, ""])[1]) if re.search(r'<div class="region">', body) else ""
            title = clean((re.search(r'<span class="OppTitle">(.*?)</span>', body, re.S) or [None, ""])[1]) if re.search(r'OppTitle', body) else ""
            links = re.findall(r'<a href="([^"]+)"[^>]*>More info</a>', body)
            orgm = re.search(r'by <a href="[^"]+"[^>]*>(.*?)</a>', body)
            text = clean(body)
            fa, fc = money(text)
            online = bool(online_page) or bool(re.search(r"\bonline\b|virtual", region_txt + " " + text[:300], re.I))
            add("Artshow", {
                "title": title, "org": clean(orgm.group(1)) if orgm else "", "url": links[0] if links else "https://artshow.com/juriedshows/%s.html" % page,
                "deadline": "%s-%02d-%02d" % (yr, int(mo), int(da)), "region": "해외", "where": region_txt.replace("Call for Artists", "").strip() or ("온라인" if online else "확인 필요"),
                "online": online, "intl": bool(INTL.search(region_txt + " " + text)), "kind": "온라인 공모" if online else "미술대전·어워드",
                "feeAmount": fa, "feeCur": fc, "free": bool(re.search(r"no (entry )?fee|free to enter|free entry", text, re.I)),
                "fee": ({"USD": "$", "EUR": "€", "GBP": "£"}.get(fc, "") + ("%g" % fa)) if fa else "확인 필요", "desc": text[:400], "prize": prize(text),
            })
    return n

# ---- 3) CaFÉ 첫 화면 (최근 열린 공모) ----
def cafe():
    h = get("https://artist.callforentry.org/festivals.php", 60)
    h = h.replace('\\"', '"').replace("\\u003c", "<").replace("\\u003e", ">").replace("\\u0026", "&")
    n = 0
    for m in re.finditer(r'\{"id":"(\d+)","name":"(.*?)","applyUrl".*?"city":(null|"[^"]*").*?"state":(null|"[^"]*").*?"type":"([A-Z_]+)".*?"applicationDeadline":(null|"[^"]*").*?"providerName":(null|"[^"]*").*?"eligibilityLocation":(null|"[^"]*")', h, re.S):
        cid, name, city, state, typ, dl, prov, elig = m.groups(); n += 1
        q = lambda v: (v or "null").strip('"') if v != "null" else ""
        elig = q(elig); online = "ONLINE" in typ or "online" in name.lower()
        add("CaFÉ", {
            "title": clean(name), "org": q(prov), "url": "https://artist.callforentry.org/festivals_unique_info.php?ID=" + cid,
            "deadline": q(dl)[:10] or None, "region": "해외", "where": ", ".join([x for x in [q(city), q(state)] if x]) or "미국",
            "online": online, "intl": elig.lower().startswith("international"), "kind": "아트페어·판매" if typ in ("FAIR", "FESTIVAL") else "전시 공모",
            "feeAmount": None, "feeCur": None, "free": False, "fee": "확인 필요", "desc": "자격: " + (elig or "확인 필요") + " · 형식: " + typ, "prize": None,
        })
    return n

# ---- 4) 공모전코리아 미술 분야 (국내) ----
ART_KR = re.compile(r"미술|회화|그림|작가|전시|한국화|서양화|수묵|공모전|아트|드로잉|일러스트")
BAD_KR = re.compile(r"청소년|초등|중학|고등|학생|대학생|어린이|UCC|영상|웹툰|캐릭터|로고|디자인|포스터|사진|네이밍|슬로건|굿즈|이모티콘|마스코트|캘리그라피|그리기 대회|사생대회")
def contestkorea():
    n = 0
    for pg in range(1, 6):
        h = get("https://www.contestkorea.com/sub/list.php?int_gbn=1&Txt_bcode=030610001&Txt_sortkey=a.int_sort&Txt_sortword=desc&page=%d" % pg)
        for body in h.split('<div class="title">')[1:]:
            body = body.split('<div class="title">')[0][:4000]; n += 1
            a = re.search(r'href="([^"]*str_no=\d+)"[^>]*>.*?<span class="txt">(.*?)</span>', body, re.S)
            if not a: continue
            title = clean(a.group(2)); text = clean(body)
            rng = re.search(r"접수\s*\.?\s*(\d\d)\.(\d\d)\s*~\s*(\d\d)\.(\d\d)", text)
            if not rng: continue
            em, ed = int(rng.group(3)), int(rng.group(4))
            yr = TODAY.year + (1 if em < TODAY.month - 1 else 0)
            org = re.search(r"주최\s*\.?\s*(.*?)\s*대상", text)
            target = re.search(r"대상\s*\.?\s*(.*?)\s*접수", text)
            tgt = target.group(1) if target else ""
            if not ART_KR.search(title) or BAD_KR.search(title) or ("일반인" not in tgt and "누구나" not in tgt):
                STATS["공모전코리아"].setdefault("뺀 이유", {}); STATS["공모전코리아"]["뺀 이유"]["작가 대상 아님·미술 외"] = STATS["공모전코리아"]["뺀 이유"].get("작가 대상 아님·미술 외", 0) + 1
                continue
            url = a.group(1); url = url if url.startswith("http") else "https://www.contestkorea.com/sub/" + url.lstrip("./")
            add("공모전코리아", {
                "title": title, "org": org.group(1).strip(" .") if org else "", "url": url,
                "deadline": "%d-%02d-%02d" % (yr, em, ed), "region": "국내", "where": "국내", "online": False, "intl": False,
                "kind": "미술대전·어워드", "feeAmount": None, "feeCur": None, "free": False, "fee": "확인 필요",
                "desc": "대상: " + tgt, "prize": None,
            })
    return n


# ---- 5) ArtRabbit 작가 기회 (국제·영국) ----
MONTHS = {m: i for i, m in enumerate(["january","february","march","april","may","june","july","august","september","october","november","december"], 1)}
def artrabbit():
    h = get("https://www.artrabbit.com/artist-opportunities", 60)
    n = 0
    for blk in h.split('<div class="artopp" data-d="')[1:]:
        n += 1
        dd = blk[:8]
        typ = clean((re.search(r'<h3[^>]*>(.*?)</h3>', blk, re.S) or [None, ""])[1]) if re.search(r'<h3', blk) else ""
        tm = re.search(r'<h2[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', blk, re.S)
        if not tm: continue
        body = clean(blk)
        dl = re.search(r"Deadline (\d{1,2}) (\w+) (\d{4})", body)
        deadline = "%s-%02d-%02d" % (dl.group(3), MONTHS.get(dl.group(2).lower(), 0), int(dl.group(1))) if dl and MONTHS.get(dl.group(2).lower()) else (dd[:4] + "-" + dd[4:6] + "-" + dd[6:8] if dd.isdigit() else None)
        org = re.search(r"Organiser: (.*?)(?: Locations:|$)", body)
        loc = re.search(r"Locations: (.*?)(?: Apply|$)", body)
        apply_ = re.search(r'href=([^ >]+) target="_blank" class="b_submit', blk)
        fee_txt = re.search(r"Entry Fee:\s*(.*?)(?: Deadline|$)", body)
        fa, fc = money("fee " + (fee_txt.group(1) if fee_txt else ""))
        free = bool(re.search(r"free|no fee|£0|\$0", fee_txt.group(1), re.I)) if fee_txt else False
        locs = loc.group(1) if loc else ""
        if re.search(r"Professional Development|Job|Course|Education", typ, re.I): continue
        online = bool(re.search(r"\bonline\b|virtual|digital", body[:600], re.I))
        url = (apply_.group(1).strip('"') if apply_ else None) or ("https://www.artrabbit.com" + tm.group(1) if tm.group(1).startswith("/") else tm.group(1))
        add("ArtRabbit", {
            "title": clean(tm.group(2)), "org": org.group(1).strip() if org else "", "url": url, "deadline": deadline,
            "region": "해외", "where": locs or "확인 필요", "online": online, "intl": "International" in locs or bool(INTL.search(body)),
            "kind": "미술대전·어워드" if re.search(r"prize|award|competition", typ + tm.group(2), re.I) else ("지원사업" if re.search(r"grant|fund", typ, re.I) else "전시 공모"),
            "feeAmount": fa, "feeCur": fc, "free": free, "fee": (fee_txt.group(1).strip()[:30] if fee_txt else "확인 필요"),
            "desc": body[:400], "prize": prize(body),
        })
    return n

# ---- 6) Artquest 기회 목록 (영국 중심, 국제 공모 일부) ----
def artquest():
    n = 0
    for pg in range(1, 4):
        h = get("https://www.artquest.org.uk/opportunities/" + ("page/%d/" % pg if pg > 1 else ""))
        for blk in h.split('<div class="landing-page-item  pt-opportunity">')[1:]:
            n += 1
            tm = re.search(r'<h5[^>]*><a href="([^"]+)">(.*?)</a>', blk, re.S)
            dm = re.search(r"Deadline: </strong>(\d\d)/(\d\d)/(\d{4})", blk)
            if not tm or not dm: continue
            body = clean(blk.split('<div class="lp-extra">')[0])
            web = re.search(r'class="website"><a target="_blank" href="([^"]+)"', blk)
            fa, fc = money(body)
            add("Artquest", {
                "title": clean(tm.group(2)), "org": "", "url": web.group(1) if web else tm.group(1), "deadline": "%s-%s-%s" % (dm.group(3), dm.group(2), dm.group(1)),
                "region": "해외", "where": "영국" if not INTL.search(body) else "영국·국제", "online": bool(ONLINE.search(body)), "intl": bool(INTL.search(body)),
                "kind": "미술대전·어워드" if re.search(r"prize|award", tm.group(2), re.I) else "전시 공모",
                "feeAmount": fa, "feeCur": fc, "free": bool(re.search(r"free to enter|no (entry )?fee", body, re.I)), "fee": "확인 필요" if not fa else "%s%g" % ({"USD": "$", "EUR": "€", "GBP": "£"}.get(fc, ""), fa),
                "desc": body[:400], "prize": prize(body),
            })
    return n

# ---- 7) callforartists.com (ArtJobs 국제 공모 목록) ----
def callforartists():
    n = 0
    for pg in range(0, 4):
        h = get("https://www.callforartists.com/" + ("?page=%d" % pg if pg else ""))
        for row in re.findall(r'<tr\s+class="(?:odd|even)[^"]*">(.*?)</tr>', h, re.S):
            cat = re.search(r'views-field-field-category-addapost">(.*?)</td>', row, re.S)
            tm = re.search(r'opencalltitle">\s*<strong><a href="([^"]+)">(.*?)</a></strong>(.*?)</td>', row, re.S)
            dm = re.search(r'content="(\d{4}-\d\d-\d\d)T', row)
            if not tm or not dm: continue
            n += 1
            parts = [clean(x) for x in re.split(r"<p>", cat.group(1))] if cat else []
            ctype, org, loc = (parts + ["", "", ""])[:3]
            if re.search(r"Literary|Film|Dance|Design|Workshop|Publishing|News|Photography|Public Art", ctype): continue
            desc = clean(tm.group(3))
            add("CallForArtists", {
                "title": clean(tm.group(2)), "org": org, "url": "https://www.callforartists.com" + tm.group(1), "deadline": dm.group(1),
                "region": "해외", "where": loc or "확인 필요", "online": bool(ONLINE.search(tm.group(2) + " " + desc + " " + loc)), "intl": loc.lower() == "international" or bool(INTL.search(desc)),
                "kind": "미술대전·어워드" if re.search(r"Award|Prize|Competition", ctype + tm.group(2)) else "전시 공모",
                "feeAmount": None, "feeCur": None, "free": "Not for profit" in row, "fee": "확인 필요", "desc": (ctype + " · " + desc)[:400], "prize": prize(desc),
            })
    return n

# 네오룩(neolook.com)은 robots.txt가 공모 목록 경로를 막고 있어 수집하지 않는다 (2026-11-12).

run("EntryThingy", entrythingy)
run("Artshow", artshow)
run("CaFÉ", cafe)
run("공모전코리아", contestkorea)
run("ArtRabbit", artrabbit)
run("Artquest", artquest)
run("CallForArtists", callforartists)
# 네오룩: robots.txt가 공모 목록 경로(/archives/)를 막고 있고 사이트가 "허락 받아 사용"을 요청해 2026-11-12부터 수집하지 않음 (함수는 기록용으로 남김)

# 같은 공모가 여러 곳에 올라온 경우 하나로 (제목 앞부분 + 마감일)
seen, uniq = {}, []
for it in sorted(ITEMS, key=lambda x: -x["score"]):
    k = re.sub(r"[^a-z0-9가-힣]", "", it["title"].lower())[:24]
    if k in seen:
        if it["source"] != seen[k]["source"] and it["source"] not in seen[k].get("alsoOn", []): seen[k].setdefault("alsoOn", []).append(it["source"])
        continue
    seen[k] = it; uniq.append(it)
low = [x for x in uniq if x["grade"] == "하"]
uniq = [x for x in uniq if x["grade"] != "하"]
uniq.sort(key=lambda x: (x["deadline"], -x["score"]))
for s in STATS:
    STATS[s]["피드"] = sum(1 for x in uniq if x["source"] == s)
    STATS[s]["실물·지역 한정으로 뺌"] = sum(1 for x in low if x["source"] == s)
for it in uniq:
    it["collectedAt"] = NOW.isoformat(timespec="seconds")
json.dump(uniq, open(os.path.join(OUT, "feed.json"), "w"), ensure_ascii=False, indent=0)
summary = {"runAt": NOW.isoformat(timespec="seconds"), "total": len(uniq), "lowSkipped": len(low), "read": sum(v.get("가져옴", 0) for v in STATS.values()),
           "byGrade": {g: sum(1 for x in uniq if x["grade"] == g) for g in "상중하"},
           "online": sum(1 for x in uniq if x.get("online")), "domestic": sum(1 for x in uniq if x["region"] == "국내"),
           "sources": STATS}
json.dump(summary, open(os.path.join(OUT, "stats.json"), "w"), ensure_ascii=False, indent=1)
keep = ["id","title","org","url","deadline","region","where","online","intl","kind","fee","feeAmount","feeCur","flags","grade","score","source","alsoOn","desc"]
slim = [{k: x.get(k) for k in keep if x.get(k) not in (None, [], "")} for x in uniq]
for x in slim:
    if "desc" in x: x["desc"] = x["desc"][:220]
json.dump({"runAt": summary["runAt"], "stats": {k: summary[k] for k in ["runAt","read","total","lowSkipped","byGrade","online","domestic","sources"]}, "items": slim},
          open(os.path.join(OUT, "feed_doc.json"), "w"), ensure_ascii=False)
json.dump({"runAt": summary["runAt"], "read": summary["read"], "total": summary["total"], "byGrade": summary["byGrade"], "online": summary["online"], "domestic": summary["domestic"],
           "sources": {k: {kk: vv for kk, vv in v.items() if kk in ("가져옴", "피드", "오류")} for k, v in STATS.items()}},
          open(os.path.join(OUT, "run_doc.json"), "w"), ensure_ascii=False)
print(json.dumps(summary, ensure_ascii=False, indent=1))
