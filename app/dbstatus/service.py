"""
Database Status dentro do Regente: monitoramento de bancos Azure SQL (somente leitura).

Portado do projeto DatabaseStatus (server.py). O que mudou para rodar no servidor:
- token: identidade gerenciada do app (App Service) em vez do `az` de uma pessoa; sem ela, usa o `az` (uso local);
- pasta do histórico de uso (SQLite) configurável e sem WAL em disco de rede;
- o servidor HTTP próprio saiu: as rotas (ROUTES) são servidas pelo FastAPI, só para administradores.

Descobre sozinho os servidores/bancos que a identidade enxerga, lê métricas do Azure Monitor (REST) e, direto
dos bancos, DMVs e Query Store com token Entra. Nenhuma alteração é feita nos bancos.
"""
import json, os, re, shutil, sqlite3, struct, subprocess, sys, threading, time, math, traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError

import pyodbc

# (sem mexer em pyodbc.pooling: é global do processo e o Regente usa o mesmo pyodbc)

ON_APP_SERVICE = bool(os.environ.get("WEBSITE_SITE_NAME"))
ARM = "https://management.azure.com"
POOL = ThreadPoolExecutor(max_workers=12)

# ----------------------------------------------------------------- tokens
_tok = {}
_tok_lock = threading.Lock()


def _az_cmd():
    return os.environ.get("AZ_CMD") or shutil.which("az") or "az"


def _msi_token(resource):
    """Token da identidade gerenciada (App Service). None fora do Azure."""
    endpoint, header = os.environ.get("IDENTITY_ENDPOINT"), os.environ.get("IDENTITY_HEADER")
    if not endpoint or not header:
        return None
    from urllib.parse import quote
    req = Request(f"{endpoint}?resource={quote(resource, safe='')}&api-version=2019-08-01",
                  headers={"X-IDENTITY-HEADER": header})
    with urlopen(req, timeout=30) as r:
        d = json.loads(r.read().decode("utf-8"))
    return d["access_token"], float(d.get("expires_on") or 0)


def get_token(resource):
    with _tok_lock:
        t = _tok.get(resource)
        if t and t[1] > time.time():
            return t[0]
        msi = _msi_token(resource)
        if msi:
            tok, exp = msi
            # renova 5 min antes de vencer; no máximo 45 min de cache
            _tok[resource] = (tok, min(exp - 300, time.time() + 45 * 60) if exp else time.time() + 30 * 60)
            return tok
        out = subprocess.run(
            [_az_cmd(), "account", "get-access-token", "--resource", resource, "--query", "accessToken", "-o", "tsv"],
            capture_output=True, text=True, timeout=60,
        )
        if out.returncode != 0:
            raise RuntimeError("az falhou: " + (out.stderr or "")[:300])
        tok = out.stdout.strip()
        _tok[resource] = (tok, time.time() + 45 * 60)
        return tok


def arm_get(path, retries=3):
    url = path if path.startswith("http") else ARM + path
    for i in range(retries):
        req = Request(url, headers={"Authorization": "Bearer " + get_token(ARM + "/")})
        try:
            with urlopen(req, timeout=40) as r:
                return json.loads(r.read().decode("utf-8"))
        except HTTPError as e:
            if e.code in (429, 503) and i < retries - 1:
                time.sleep(1.5 * (i + 1))
                continue
            body = e.read().decode("utf-8", "ignore")[:300]
            raise RuntimeError(f"ARM {e.code}: {body}")


# ------------------------------------------------------------------ cache
_cache = {}
_cache_lock = threading.Lock()


def cached(key, ttl, fn):
    now = time.time()
    with _cache_lock:
        c = _cache.get(key)
        if c and c[0] > now:
            return c[1]
    val = fn()
    with _cache_lock:
        _cache[key] = (now + ttl, val)
    return val


# -------------------------------------------------------------- discovery
_inflight = set()


def cached_swr(key, ttl, fn, stale=3600):
    """Cache que, vencido, devolve o valor antigo na hora e atualiza em segundo plano (tela nunca espera)."""
    now = time.time()
    with _cache_lock:
        c = _cache.get(key)
    if c and c[0] > now:
        return c[1]
    if c and c[0] + stale > now:
        with _cache_lock:
            if key in _inflight:
                return c[1]
            _inflight.add(key)

        def bg():
            try:
                v = fn()
                with _cache_lock:
                    _cache[key] = (time.time() + ttl, v)
            except Exception:
                pass
            finally:
                with _cache_lock:
                    _inflight.discard(key)
        threading.Thread(target=bg, daemon=True).start()
        return c[1]
    val = fn()
    with _cache_lock:
        _cache[key] = (time.time() + ttl, val)
    return val


def discover():
    dbs = []
    subs = [s for s in arm_get("/subscriptions?api-version=2020-01-01")["value"] if s.get("state") == "Enabled"]
    for sub in subs:
        sid = sub["subscriptionId"]
        servers = arm_get(f"/subscriptions/{sid}/providers/Microsoft.Sql/servers?api-version=2021-11-01")["value"]
        for sv in servers:
            rg = sv["id"].split("/")[4]
            fqdn = sv["properties"].get("fullyQualifiedDomainName", sv["name"] + ".database.windows.net")
            lst = arm_get(f"{sv['id']}/databases?api-version=2021-11-01")["value"]
            for d in lst:
                if d["name"] == "master":
                    continue
                sku = d.get("sku") or {}
                p = d.get("properties", {})
                tier = sku.get("tier") or ""
                dtu_model = tier in ("Basic", "Standard", "Premium")
                dbs.append({
                    "id": d["id"], "server": sv["name"], "fqdn": fqdn, "name": d["name"], "rg": rg,
                    "sub": sub.get("displayName", sid), "location": d.get("location"),
                    "sku": sku.get("name"), "tier": tier, "capacity": sku.get("capacity"),
                    "dtuModel": dtu_model, "dtuLimit": sku.get("capacity") if dtu_model else None,
                    "maxSizeBytes": p.get("maxSizeBytes"), "state": p.get("status"),
                    "pool": (p.get("elasticPoolId") or "").split("/")[-1] or None,
                    "zr": p.get("zoneRedundant"),
                })
    dbs.sort(key=lambda x: (x["server"], x["name"].lower()))
    return dbs


_last_dbs = []


def databases():
    """Lista de bancos (descoberta automatica). Falha passageira nao zera a lista."""
    global _last_dbs
    with _cache_lock:
        c = _cache.get("dbs")
        if c and c[0] > time.time():
            return c[1]
    try:
        dbs = discover()
    except Exception:
        dbs = []
    if dbs:
        _last_dbs = dbs
        with _cache_lock:
            _cache["dbs"] = (time.time() + 120, dbs)
        return dbs
    return _last_dbs


def find_db(server, name):
    for d in databases():
        if d["server"] == server and d["name"] == name:
            return d
    raise KeyError(f"banco nao encontrado: {server}/{name}")


# ---------------------------------------------------------------- metrics
METRICS = [
    "cpu_percent", "physical_data_read_percent", "log_write_percent", "dtu_consumption_percent",
    "workers_percent", "sessions_percent", "sessions_count", "storage_percent", "storage",
    "connection_successful", "connection_failed", "connection_failed_user_error", "blocked_by_firewall",
    "deadlock", "dtu_limit", "dtu_used", "availability",
]
RANGES = {
    "live": (timedelta(hours=1), "PT1M", 20),
    "24h": (timedelta(hours=24), "PT5M", 60),
    "7d": (timedelta(days=7), "PT30M", 300),
    "15d": (timedelta(days=15), "PT1H", 300),
    "30d": (timedelta(days=30), "PT1H", 600),
}


def metric_defs(db):
    def f():
        r = arm_get(f"{db['id']}/providers/Microsoft.Insights/metricDefinitions?api-version=2018-01-01")
        return {m["name"]["value"] for m in r["value"]}
    return cached(("defs", db["id"]), 6 * 3600, f)


def iso(d):
    return d.strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_metrics(db, rng):
    delta, interval, ttl = RANGES[rng]

    def f():
        end = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        start = end - delta
        names = [n for n in METRICS if n in metric_defs(db)]
        url = (f"{db['id']}/providers/Microsoft.Insights/metrics?api-version=2018-01-01"
               f"&metricnames={','.join(names)}&timespan={iso(start)}/{iso(end)}&interval={interval}"
               f"&aggregation=Average,Maximum,Total")
        r = arm_get(url)
        per = {}
        allts = set()
        for m in r["value"]:
            ts = m.get("timeseries") or []
            data = ts[0]["data"] if ts else []
            d = {}
            for p in data:
                t = int(datetime.strptime(p["timeStamp"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp() * 1000)
                d[t] = p
                allts.add(t)
            per[m["name"]["value"]] = d
        t = sorted(allts)
        out = {}
        for name, d in per.items():
            out[name] = {
                "avg": [d.get(x, {}).get("average") for x in t],
                "max": [d.get(x, {}).get("maximum") for x in t],
                "tot": [d.get(x, {}).get("total") for x in t],
            }
        return {"t": t, "m": out, "interval": interval}
    return cached_swr(("m", db["id"], rng), ttl, f)


def pct(vals, p):
    v = sorted(x for x in vals if x is not None)
    if not v:
        return None
    k = (len(v) - 1) * p / 100.0
    lo, hi = int(math.floor(k)), int(math.ceil(k))
    return v[lo] + (v[hi] - v[lo]) * (k - lo)


def clean(v):
    return [x for x in v if x is not None]


def summarize(ser):
    res = {}
    for name, s in ser["m"].items():
        a, mx, tot = clean(s["avg"]), clean(s["max"]), clean(s["tot"])
        n = len(a)
        res[name] = {
            "avg": (sum(a) / n) if n else None,
            "p95": pct(a, 95),
            "max": max(mx) if mx else None,
            "sum": sum(tot) if tot else 0,
            "over80": (sum(1 for x in a if x >= 80) / n) if n else 0,
            "over90": (sum(1 for x in a if x >= 90) / n) if n else 0,
        }
    return res


def now_values(live):
    now, nowmax, recent = {}, {}, {}
    for name, s in live["m"].items():
        a = clean(s["avg"])[-5:]
        mx = clean(s["max"])[-5:]
        now[name] = (sum(a) / len(a)) if a else None
        nowmax[name] = max(mx) if mx else None
        tot = s["tot"][-15:]
        recent[name] = sum(x for x in tot if x) if tot else 0
    return now, nowmax, recent


# --------------------------------------------------------------- capacity
LADDER = {
    "dtu": [
        (5, "Basic", 4.90, 2), (10, "S0", 14.72, 250), (20, "S1", 29.45, 250), (50, "S2", 73.63, 250),
        (100, "S3", 147.26, 1024), (200, "S4", 294.52, 1024), (400, "S6", 589.04, 1024),
        (800, "S7", 1178.08, 1024), (1600, "S9", 2356.16, 1024), (3000, "S12", 4417.80, 1024),
    ],
    "prem": [(125, "P1", None, 1024), (250, "P2", None, 1024), (500, "P4", None, 1024),
             (1000, "P6", None, 1024), (1750, "P11", None, 4096), (4000, "P15", None, 4096)],
}


def capacity(db, ser):
    if not db["dtuModel"] or not db["dtuLimit"]:
        return {"verdict": "na", "title": "Sem recomendação automática",
                "reasons": ["Banco fora do modelo DTU (vCore/pool). Use CPU, IO e workers como referência."]}
    m = ser["m"]
    dtu = m.get("dtu_consumption_percent")
    if not dtu or len(clean(dtu["avg"])) < 6:
        return {"verdict": "na", "title": "Dados insuficientes", "reasons": ["Poucos pontos de métrica no período."]}
    cur = db["dtuLimit"]
    a = clean(dtu["avg"])
    n = len(a)
    p95, mean, mx = pct(a, 95), sum(a) / n, max(clean(dtu["max"]) or [0])
    a90, a80 = sum(1 for x in a if x >= 90) / n, sum(1 for x in a if x >= 80) / n
    ladder = LADDER["prem"] if db["tier"] == "Premium" else LADDER["dtu"]
    cur_row = next((r for r in ladder if r[0] == cur), None)
    used_gb = None
    if "storage" in m and clean(m["storage"]["max"]):
        used_gb = max(clean(m["storage"]["max"])) / 1024 ** 3
    bott = {}
    for k, label in (("cpu_percent", "CPU"), ("physical_data_read_percent", "IO de dados"), ("log_write_percent", "IO de log")):
        if k in m and clean(m[k]["avg"]):
            bott[label] = pct(m[k]["avg"], 95)
    bottleneck = max(bott, key=lambda k: bott[k] or 0) if bott else None
    needed = cur * p95 / 100.0 / 0.70

    def fits(row):
        return used_gb is None or row[3] >= used_gb * 1.15

    reasons = [f"DTU: média {mean:.0f}%, p95 {p95:.0f}%, pico {mx:.0f}%."]
    if a90 > 0:
        reasons.append(f"Ficou acima de 90% em {a90*100:.0f}% do período (acima de 80% em {a80*100:.0f}%).")
    if bottleneck and bott[bottleneck] is not None:
        reasons.append(f"Gargalo principal: {bottleneck} (p95 {bott[bottleneck]:.0f}%).")
    if used_gb is not None and cur_row:
        reasons.append(f"Armazenamento: {used_gb:.2f} GB de {cur_row[3]} GB do limite da camada.")

    verdict = "ok"
    title = "Capacidade adequada"
    target = None
    if p95 >= 80 or a90 >= 0.05 or (mx >= 100 and a80 >= 0.02):
        verdict, title = "subir", "Recomendado aumentar a capacidade"
        cands = [r for r in ladder if r[0] > cur and r[0] >= needed and fits(r)] or [r for r in ladder if r[0] > cur and fits(r)]
        target = cands[0] if cands else None
    elif p95 >= 65 or a90 > 0:
        verdict, title = "atencao", "Atenção: perto do limite"
        reasons.append("Ainda não exige upgrade, mas há pouca folga para picos.")
    elif p95 < 25 and mx < 60 and cur_row and cur > ladder[0][0]:
        cands = [r for r in ladder if r[0] < cur and cur * p95 / r[0] <= 70 and cur * mx / r[0] <= 100 and fits(r)]
        if cands:
            verdict, title, target = "reduzir", "Dá para reduzir e economizar", cands[0]
    if mx >= 100:
        reasons.append("O banco encostou em 100% de DTU: nesses momentos as consultas são limitadas (throttling).")
    res = {"verdict": verdict, "title": title, "reasons": reasons, "dtu": cur,
           "tier": cur_row[1] if cur_row else db["sku"], "stats": {"avg": mean, "p95": p95, "max": mx, "over90": a90, "over80": a80},
           "needed": needed, "bottleneck": bottleneck, "bottlenecks": bott, "usedGb": used_gb,
           "price": cur_row[2] if cur_row else None, "ladder": [{"dtu": r[0], "tier": r[1], "price": r[2], "maxGb": r[3]} for r in ladder]}
    if target:
        res["target"] = {"dtu": target[0], "tier": target[1], "price": target[2],
                         "projectedP95": cur * p95 / target[0], "projectedMax": cur * mx / target[0],
                         "cmd": f"az sql db update -g {db['rg']} -s {db['server']} -n {db['name']} --service-objective {target[1]}"}
    return res



def saturation(ser):
    """Periodos em que o banco ficou saturado (travamento em ~100%)."""
    m, t = ser["m"], ser["t"]
    d = m.get("dtu_consumption_percent") or m.get("cpu_percent")
    if not d or len(t) < 2:
        return None
    step = t[1] - t[0]
    fine = ser["interval"] in ("PT1M", "PT5M")
    flags = [((a is not None and a >= 90) if fine else (x is not None and x >= 99)) for a, x in zip(d["avg"], d["max"])]
    eps, i, n = [], 0, len(flags)
    while i < n:
        if not flags[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and (flags[j + 1] or (j + 2 < n and flags[j + 2])):
            j += 1
        eps.append((i, j))
        i = j + 1
    out = []
    for i, j in eps:
        idx = range(i, j + 1)
        def mean(k):
            v = [m[k]["avg"][x] for x in idx if k in m and m[k]["avg"][x] is not None]
            return sum(v) / len(v) if v else None
        res = {"CPU": mean("cpu_percent"), "IO de dados": mean("physical_data_read_percent"), "IO de log": mean("log_write_percent")}
        res = {k: v for k, v in res.items() if v is not None}
        culprit = max(res, key=res.get) if res else None
        mx = [d["max"][x] for x in idx if d["max"][x] is not None]
        av = [d["avg"][x] for x in idx if d["avg"][x] is not None]
        out.append({"start": t[i], "end": t[j] + step, "minutes": (j - i + 1) * step / 60000.0,
                    "peak": max(mx) if mx else None, "avg": sum(av) / len(av) if av else None,
                    "culprit": culprit, "res": res})
    total = sum(e["minutes"] for e in out)
    span = (t[-1] - t[0] + step) / 60000.0
    return {"count": len(out), "totalMin": total, "longestMin": max((e["minutes"] for e in out), default=0),
            "pct": total / span * 100 if span else 0, "fine": fine, "episodes": sorted(out, key=lambda e: -e["start"])[:60],
            "rule": "DTU médio >= 90%" if fine else "DTU encostou em 100%"}

# ------------------------------------------------------------------- SQL
def sql_conn(fqdn, dbname, timeout=12):
    tok = get_token("https://database.windows.net/")
    b = tok.encode("utf-16-le")
    st = struct.pack("<i", len(b)) + b
    c = pyodbc.connect(
        f"DRIVER={{ODBC Driver 18 for SQL Server}};SERVER={fqdn};DATABASE={dbname};Encrypt=yes;TrustServerCertificate=no;APP=DatabaseStatus;",
        attrs_before={1256: st}, timeout=timeout, autocommit=True)
    c.timeout = 40
    return c


def conv(v):
    if isinstance(v, datetime):
        return v.isoformat() + "Z"
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (bytes, bytearray)):
        return None
    return v


def rows(cur):
    cols = [c[0] for c in cur.description]
    return [{c: conv(v) for c, v in zip(cols, r)} for r in cur.fetchall()]


def q(conn, sql, params=()):
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        return rows(cur)
    except pyodbc.Error as e:
        if hasattr(conn, "broken") and is_conn_error(e):
            conn.broken = True
        raise


SNAP_RS = """SELECT TOP 4 avg_cpu_percent cpu, avg_data_io_percent io, avg_log_write_percent logw,
 avg_memory_usage_percent mem, max_worker_percent workers, max_session_percent sessions, end_time
 FROM sys.dm_db_resource_stats ORDER BY end_time DESC"""
SNAP_REQ = """SELECT COUNT(*) running, ISNULL(SUM(CASE WHEN r.blocking_session_id>0 THEN 1 ELSE 0 END),0) blocked,
 ISNULL(MAX(r.total_elapsed_time),0) max_ms
 FROM sys.dm_exec_requests r JOIN sys.dm_exec_sessions s ON s.session_id=r.session_id
 WHERE s.is_user_process=1 AND r.session_id<>@@SPID AND s.login_name<>'NT AUTHORITY\\SYSTEM' AND ISNULL(s.program_name,'')<>'DatabaseStatus'"""
SNAP_SESS = "SELECT COUNT(*) sessions, ISNULL(SUM(CASE WHEN open_transaction_count>0 AND status='sleeping' THEN 1 ELSE 0 END),0) idle_tran FROM sys.dm_exec_sessions WHERE is_user_process=1 AND ISNULL(program_name,'')<>'DatabaseStatus'"


def snapshot_one(db):
    t0 = time.time()
    try:
        def work(c):
            return q(c, SNAP_RS), q(c, SNAP_REQ)[0], q(c, SNAP_SESS)[0]
        rs, req, ses = with_conn(db, "light", work)
        n = len(rs) or 1
        avg = lambda k: sum((r[k] or 0) for r in rs) / n
        out = {"ok": True, "cpu": avg("cpu"), "io": avg("io"), "log": avg("logw"), "mem": avg("mem"),
               "workers": max((r["workers"] or 0) for r in rs) if rs else 0,
               "sessionsPct": max((r["sessions"] or 0) for r in rs) if rs else 0,
               "running": req["running"], "blocked": req["blocked"], "maxMs": req["max_ms"],
               "sessions": ses["sessions"], "idleTran": ses["idle_tran"], "asOf": rs[0]["end_time"] if rs else None}
        out["dtu"] = max(out["cpu"], out["io"], out["log"])
        out["ms"] = int((time.time() - t0) * 1000)
        return out
    except Exception as e:
        return {"ok": False, "error": str(e)[:300]}


def snapshot_all():
    def f():
        dbs = [d for d in databases() if d["state"] in (None, "Online")]
        futs = {d["id"]: POOL.submit(snapshot_one, d) for d in dbs}
        return {k: v.result() for k, v in futs.items()}
    return cached("snap", 8, f)


# --------------------------------------------------------------- endpoints
def api_databases():
    return databases()


def build_item(db, rng):
    item = dict(db)
    try:
        live = fetch_metrics(db, "live")
        now, nowmax, recent = now_values(live)
        hist = live if rng == "live" else fetch_metrics(db, rng)
        capsrc = fetch_metrics(db, "24h") if rng == "live" else hist
        st = summarize(hist)
        dtu = hist["m"].get("dtu_consumption_percent") or hist["m"].get("cpu_percent") or {"avg": [], "max": []}
        item.update({
            "now": now, "nowmax": nowmax, "recent": recent, "stats": st,
            "series": {"t": hist["t"], "avg": dtu["avg"], "max": dtu["max"]},
            "rec": capacity(db, capsrc), "sat": saturation(hist if rng != "live" else capsrc),
        })
    except Exception as e:
        item["error"] = str(e)[:300]
    return item


def api_overview(qs):
    rng = qs.get("range", ["24h"])[0]
    if rng not in RANGES:
        rng = "24h"
    dbs = databases()
    futs = [POOL.submit(build_item, d, rng) for d in dbs]
    return {"range": rng, "items": [f.result() for f in futs], "generated": iso(datetime.now(timezone.utc))}


def api_snapshot(qs):
    return snapshot_all()


def api_db(qs):
    db = find_db(qs["s"][0], qs["d"][0])
    rng = qs.get("range", ["24h"])[0]
    ser = fetch_metrics(db, rng)
    capsrc = ser if rng != "live" else fetch_metrics(db, "24h")
    return {"db": db, "range": rng, "series": ser, "stats": summarize(ser), "capacity": capacity(db, capsrc), "sat": saturation(ser)}


WAITS_EXCL = ("SLEEP_%", "BROKER_%", "XE_%", "HADR_%", "LAZYWRITER_SLEEP", "DIRTY_PAGE_POLL", "QDS_%", "SP_SERVER_DIAGNOSTICS_SLEEP",
              "SOS_WORK_DISPATCHER", "PWAIT_ALL_COMPONENTS_INITIALIZED", "CHECKPOINT_QUEUE", "REQUEST_FOR_DEADLOCK_SEARCH",
              "WAIT_XTP_%", "PARALLEL_REDO_%", "PVS_%", "DISPATCHER_QUEUE_SEMAPHORE", "FT_IFTS%", "ONDEMAND_TASK_QUEUE",
              "SQLTRACE_%", "WAITFOR", "LOGMGR_QUEUE", "XTP_%", "CLR_%", "DBMIRROR%", "PREEMPTIVE_%", "SERVER_IDLE_CHECK",
              "KSOURCE_WAKEUP", "TRACEWRITE", "WAIT_FOR_RESULTS", "CXCONSUMER", "HADR%", "SNI_%", "UCS_%", "BACKUP_%")

REQ_SQL = """SELECT r.session_id, r.status, r.command, r.wait_type, r.wait_time, r.blocking_session_id,
 r.cpu_time, r.total_elapsed_time, r.logical_reads, r.writes, r.open_transaction_count otc, s.login_name, s.host_name, s.program_name,
 SUBSTRING(t.text,(r.statement_start_offset/2)+1,((CASE r.statement_end_offset WHEN -1 THEN DATALENGTH(t.text) ELSE r.statement_end_offset END - r.statement_start_offset)/2)+1) stmt
 FROM sys.dm_exec_requests r JOIN sys.dm_exec_sessions s ON s.session_id=r.session_id
 OUTER APPLY sys.dm_exec_sql_text(r.sql_handle) t
 WHERE s.is_user_process=1 AND r.session_id<>@@SPID AND s.login_name<>'NT AUTHORITY\\SYSTEM' AND ISNULL(s.program_name,'')<>'DatabaseStatus' ORDER BY r.total_elapsed_time DESC"""
IDLE_SQL = """SELECT s.session_id, s.login_name, s.host_name, s.program_name, s.open_transaction_count otc,
 DATEDIFF(second, s.last_request_end_time, GETDATE()) idle_s, LEFT(t.text,600) last_sql
 FROM sys.dm_exec_sessions s LEFT JOIN sys.dm_exec_connections c ON c.session_id=s.session_id
 OUTER APPLY sys.dm_exec_sql_text(c.most_recent_sql_handle) t
 WHERE s.is_user_process=1 AND s.status='sleeping' AND s.open_transaction_count>0 AND ISNULL(s.program_name,'')<>'DatabaseStatus' ORDER BY idle_s DESC"""
SESS_SQL = """SELECT ISNULL(login_name,'?') login_name, ISNULL(host_name,'?') host_name, ISNULL(program_name,'?') program_name,
 COUNT(*) n, SUM(CASE WHEN status='running' THEN 1 ELSE 0 END) running, SUM(CAST(cpu_time AS bigint)) cpu_ms,
 SUM(CAST(logical_reads AS bigint)) reads, SUM(CAST(writes AS bigint)) writes
 FROM sys.dm_exec_sessions
 WHERE is_user_process=1 AND ISNULL(program_name,'')<>'DatabaseStatus' GROUP BY login_name, host_name, program_name ORDER BY cpu_ms DESC"""
RS_SQL = """SELECT end_time, avg_cpu_percent cpu, avg_data_io_percent io, avg_log_write_percent logw, avg_memory_usage_percent mem,
 max_worker_percent workers, max_session_percent sessions FROM sys.dm_db_resource_stats ORDER BY end_time"""


def api_live(qs):
    db = find_db(qs["s"][0], qs["d"][0])
    c = lease(db, "light")
    try:
        waits_where = " AND ".join(f"wait_type NOT LIKE '{w}'" for w in WAITS_EXCL)
        out = {
            "requests": q(c, REQ_SQL),
            "idleTran": q(c, IDLE_SQL),
            "sessions": q(c, SESS_SQL),
            "resource": q(c, RS_SQL),
        }
        try:
            out["waits"] = q(c, f"SELECT TOP 12 wait_type, wait_time_ms, waiting_tasks_count, signal_wait_time_ms FROM sys.dm_db_wait_stats WHERE waiting_tasks_count>0 AND {waits_where} ORDER BY wait_time_ms DESC")
        except Exception as e:
            out["waits"] = []
            out["waitsError"] = str(e)[:200]
    finally:
        c.close()
    out["asOf"] = iso(datetime.now(timezone.utc))
    return out


QS_SORT = {"cpu": "total_cpu_ms", "dur": "total_dur_ms", "reads": "total_reads", "execs": "execs", "avg": "avg_ms",
           "failed": "failed", "writes": "total_writes"}


def api_qs(qs):
    db = find_db(qs["s"][0], qs["d"][0])
    sort = QS_SORT.get(qs.get("sort", ["cpu"])[0], "total_cpu_ms")
    if "from" in qs and "to" in qs:
        where = "i.end_time >= CONVERT(datetimeoffset, ?, 127) AND i.start_time <= CONVERT(datetimeoffset, ?, 127)"
        params = (qs["from"][0], qs["to"][0])
        label = {"from": qs["from"][0], "to": qs["to"][0]}
    else:
        hours = max(1, min(int(qs.get("hours", ["24"])[0]), 24 * 30))
        where = "i.start_time >= DATEADD(hour, -?, SYSDATETIMEOFFSET())"
        params = (hours,)
        label = {"hours": hours}
    c = lease(db, "heavy")
    try:
        state = q(c, "SELECT actual_state_desc st, readonly_reason rr, current_storage_size_mb used, max_storage_size_mb mx, interval_length_minutes iv FROM sys.database_query_store_options")
        if not state or state[0]["st"] == "OFF":
            return {"enabled": False, "state": state[0] if state else None, "rows": []}
        sql = f"""SELECT TOP 30 q.query_id, MAX(qt.query_sql_text) text, SUM(rs.count_executions) execs,
 SUM(rs.avg_duration*rs.count_executions)/NULLIF(SUM(rs.count_executions),0)/1000.0 avg_ms,
 MAX(rs.max_duration)/1000.0 max_ms,
 SUM(rs.avg_cpu_time*rs.count_executions)/NULLIF(SUM(rs.count_executions),0)/1000.0 avg_cpu_ms,
 SUM(rs.avg_cpu_time*rs.count_executions)/1000.0 total_cpu_ms,
 SUM(rs.avg_duration*rs.count_executions)/1000.0 total_dur_ms,
 SUM(rs.avg_logical_io_reads*rs.count_executions) total_reads,
 SUM(rs.avg_logical_io_reads*rs.count_executions)/NULLIF(SUM(rs.count_executions),0) avg_reads,
 SUM(rs.avg_logical_io_writes*rs.count_executions) total_writes,
 SUM(CASE WHEN rs.execution_type<>0 THEN rs.count_executions ELSE 0 END) failed,
 COUNT(DISTINCT p.plan_id) plans,
 CONVERT(datetime2, SWITCHOFFSET(MAX(rs.last_execution_time),'+00:00')) last_exec
 FROM sys.query_store_query q
 JOIN sys.query_store_query_text qt ON qt.query_text_id=q.query_text_id
 JOIN sys.query_store_plan p ON p.query_id=q.query_id
 JOIN sys.query_store_runtime_stats rs ON rs.plan_id=p.plan_id
 JOIN sys.query_store_runtime_stats_interval i ON i.runtime_stats_interval_id=rs.runtime_stats_interval_id
 WHERE {where}
 GROUP BY q.query_id ORDER BY {sort} DESC"""
        data = q(c, sql, params)
        for r in data:
            r["text"] = (r["text"] or "")[:20000]
        waits = []
        try:
            waits = q(c, f"""SELECT TOP 8 ws.wait_category_desc cat, SUM(ws.total_query_wait_time_ms) ms
 FROM sys.query_store_wait_stats ws JOIN sys.query_store_runtime_stats_interval i ON i.runtime_stats_interval_id=ws.runtime_stats_interval_id
 WHERE {where} AND ws.wait_category_desc<>'Unknown' GROUP BY ws.wait_category_desc ORDER BY ms DESC""", params)
        except Exception:
            pass
        return {"enabled": True, "state": state[0], "rows": data, "sort": sort, "waits": waits, **label}
    finally:
        c.close()


IDX_SQL = """SELECT TOP 10 d.statement table_name, d.equality_columns, d.inequality_columns, d.included_columns,
 s.user_seeks, s.user_scans, s.avg_total_user_cost cost, s.avg_user_impact impact,
 s.avg_total_user_cost*s.avg_user_impact*(s.user_seeks+s.user_scans) score
 FROM sys.dm_db_missing_index_group_stats s JOIN sys.dm_db_missing_index_groups g ON g.index_group_handle=s.group_handle
 JOIN sys.dm_db_missing_index_details d ON d.index_handle=g.index_handle ORDER BY score DESC"""
SIZE_SQL = """SELECT TOP 15 s.name+'.'+t.name tbl, SUM(CASE WHEN p.index_id IN (0,1) THEN p.rows ELSE 0 END) row_count,
 SUM(a.total_pages)*8/1024.0 mb FROM sys.tables t JOIN sys.schemas s ON s.schema_id=t.schema_id
 JOIN sys.indexes i ON i.object_id=t.object_id JOIN sys.partitions p ON p.object_id=i.object_id AND p.index_id=i.index_id
 JOIN sys.allocation_units a ON a.container_id=p.partition_id GROUP BY s.name,t.name ORDER BY mb DESC"""


def api_extra(qs):
    db = find_db(qs["s"][0], qs["d"][0])
    c = lease(db, "heavy")
    out = {}
    try:
        for k, sql in (("missingIndexes", IDX_SQL), ("tables", SIZE_SQL)):
            try:
                out[k] = q(c, sql)
            except Exception as e:
                out[k] = []
                out[k + "Error"] = str(e)[:200]
    finally:
        c.close()
    return out


def api_events(qs):
    db = find_db(qs["s"][0], qs["d"][0])
    days = max(1, min(int(qs.get("days", ["7"])[0]), 30))
    c = lease(db, "heavy", "master")
    try:
        return {"rows": q(c, """SELECT TOP 200 start_time, event_type, event_subtype_desc, event_count, description
 FROM sys.event_log WHERE database_name=? AND event_type<>'connection_successful' AND start_time>=DATEADD(day,-?,GETUTCDATE())
 ORDER BY start_time DESC""", (db["name"], days))}
    except Exception as e:
        return {"rows": [], "error": str(e)[:300]}
    finally:
        c.close()


# ------------------------------------------------- conexoes reutilizadas (pool)
# Abrir uma conexao Entra no Azure SQL leva ~3 s. Em vez de abrir uma a cada chamada,
# mantemos 1 conexao "light" (leituras rapidas) e 1 "heavy" (Query Store etc.) por banco.
_pool = {}
_pool_lock = threading.Lock()
_CONN_ERR = ("08S01", "08001", "08003", "08007", "Communication link", "Connection is busy", "kill state",
             "connection is closed", "Login timeout", "TCP Provider", "terminating", "Connection timeout")


def is_conn_error(e):
    s = str(e)
    return any(x in s for x in _CONN_ERR)


class PConn:
    def __init__(self, fqdn, name):
        self.fqdn, self.name, self.conn, self.t = fqdn, name, None, 0
        self.lock = threading.Lock()

    def drop(self):
        try:
            if self.conn is not None:
                self.conn.close()
        except Exception:
            pass
        self.conn = None


class Lease:
    """Empresta a conexao do pool. close() devolve (nao fecha), a menos que tenha quebrado."""
    def __init__(self, pc):
        self.pc, self.broken = pc, False

    def cursor(self):
        try:
            return self.pc.conn.cursor()
        except Exception:
            self.broken = True
            raise

    def close(self):
        if self.broken:
            self.pc.drop()
        self.pc.lock.release()


def lease(db, kind="light", dbname=None):
    name = dbname or db["name"]
    key = (db["fqdn"], name, kind)
    with _pool_lock:
        pc = _pool.get(key)
        if pc is None:
            pc = _pool[key] = PConn(db["fqdn"], name)
    pc.lock.acquire()
    try:
        if pc.conn is None or time.time() - pc.t > 1500:
            pc.drop()
            pc.conn = sql_conn(pc.fqdn, pc.name)
            pc.t = time.time()
    except BaseException:
        pc.lock.release()
        raise
    return Lease(pc)


def with_conn(db, kind, fn, dbname=None):
    for attempt in (0, 1):
        c = lease(db, kind, dbname)
        try:
            return fn(c)
        except pyodbc.Error:
            if attempt == 0 and c.broken:
                continue
            raise
        finally:
            c.close()


# -------------------------------------------------- esquemas (schemas) do banco
SCHEMAS_SQL = "SELECT name FROM sys.schemas WHERE schema_id=1 OR (schema_id>4 AND schema_id<16384)"
_STR = re.compile(r"'(?:[^']|'')*'")
_CMT = re.compile(r"--[^\n]*|/\*.*?\*/", re.S)
_QUAL = re.compile(r"(?:\[([^\]]+)\]|\b([A-Za-z_][\w$#]*))(?=\s*\.\s*(?:\[[^\]]+\]|[A-Za-z_#@]))")
NO_SCHEMA = "(sem esquema explícito)"


def known_schemas(db):
    def f():
        return {r["name"].lower(): r["name"] for r in with_conn(db, "light", lambda c: q(c, SCHEMAS_SQL))}
    return cached(("schemas", db["id"]), 6 * 3600, f)


OBJECTS_SQL = """SELECT s.name sch, o.name obj FROM sys.objects o JOIN sys.schemas s ON s.schema_id=o.schema_id
 WHERE o.type IN ('U','V','P','FN','IF','TF','SN') AND (s.schema_id=1 OR (s.schema_id>4 AND s.schema_id<16384))"""
_UNQ = re.compile(r"\b(?:FROM|JOIN|UPDATE|INTO|EXEC(?:UTE)?|MERGE|TABLE)\s+(?:\[([^\]]+)\]|([A-Za-z_][\w$#]*))(?!\s*\.)(?!\s*\()", re.I)
_RESERVED = {"select", "where", "set", "values", "top", "distinct", "as", "on", "inner", "left", "right", "outer", "cross", "full",
             "with", "sp_executesql", "sp_prepexec", "sp_prepare", "sp_execute", "sp_unprepare", "inserted", "deleted", "dual"}


def known_objects(db):
    def f():
        m = {}
        for r in with_conn(db, "light", lambda c: q(c, OBJECTS_SQL)):
            m.setdefault(r["obj"].lower(), set()).add(r["sch"])
        return m
    return cached(("objects", db["id"]), 6 * 3600, f)


def schemas_in(text, known, objmap=None):
    """Esquemas usados pela consulta (estimativa lendo o texto SQL).
    1) nomes qualificados  esquema.tabela   2) nomes sem esquema, achados no catalogo do banco."""
    if not text:
        return set()
    t = _CMT.sub(" ", _STR.sub("''", text))
    out = set()
    for m in _QUAL.finditer(t):
        n = (m.group(1) or m.group(2) or "").lower()
        if n in known:
            out.add(known[n])
    if objmap:
        for m in _UNQ.finditer(t):
            n = (m.group(1) or m.group(2) or "").lower()
            if n and n not in _RESERVED and n in objmap:
                out |= objmap[n]
    return out


def qs_window(qs):
    if "from" in qs and "to" in qs:
        return ("i.end_time >= CONVERT(datetimeoffset, ?, 127) AND i.start_time <= CONVERT(datetimeoffset, ?, 127)",
                (qs["from"][0], qs["to"][0]))
    hours = max(1, min(int(qs.get("hours", ["24"])[0]), 24 * 30))
    return ("i.start_time >= DATEADD(hour, -?, SYSDATETIMEOFFSET())", (hours,))


def api_schemas(qs):
    """Consumo historico por esquema, a partir do Query Store (qualquer janela, inclusive um travamento)."""
    db = find_db(qs["s"][0], qs["d"][0])
    where, params = qs_window(qs)
    sql = f"""SELECT TOP 400 q.query_id, MAX(qt.query_sql_text) text, MAX(OBJECT_SCHEMA_NAME(q.object_id)) obj_schema,
 SUM(rs.count_executions) execs, SUM(rs.avg_cpu_time*rs.count_executions)/1000.0 cpu_ms,
 SUM(rs.avg_duration*rs.count_executions)/1000.0 dur_ms, SUM(rs.avg_logical_io_reads*rs.count_executions) reads,
 SUM(rs.avg_logical_io_writes*rs.count_executions) writes,
 SUM(CASE WHEN rs.execution_type<>0 THEN rs.count_executions ELSE 0 END) failed
 FROM sys.query_store_query q
 JOIN sys.query_store_query_text qt ON qt.query_text_id=q.query_text_id
 JOIN sys.query_store_plan p ON p.query_id=q.query_id
 JOIN sys.query_store_runtime_stats rs ON rs.plan_id=p.plan_id
 JOIN sys.query_store_runtime_stats_interval i ON i.runtime_stats_interval_id=rs.runtime_stats_interval_id
 WHERE {where} GROUP BY q.query_id ORDER BY cpu_ms DESC"""
    c = lease(db, "heavy")
    try:
        st = q(c, "SELECT actual_state_desc st FROM sys.database_query_store_options")
        if not st or st[0]["st"] == "OFF":
            return {"enabled": False, "rows": []}
        data = q(c, sql, params)
    finally:
        c.close()
    known = known_schemas(db)
    try:
        objmap = known_objects(db)
    except Exception:
        objmap = {}
    agg, tot = {}, {"cpu": 0.0, "dur": 0.0, "reads": 0.0, "writes": 0.0, "execs": 0.0}
    for r in data:
        sc = {r["obj_schema"]} if r["obj_schema"] else schemas_in(r["text"], known, objmap)
        if not sc:
            sc = {NO_SCHEMA}
        share = 1.0 / len(sc)
        for s in sc:
            a = agg.setdefault(s, {"schema": s, "cpuMs": 0.0, "durMs": 0.0, "reads": 0.0, "writes": 0.0, "execs": 0.0,
                                   "failed": 0.0, "queries": 0.0, "top": None})
            for k, v in (("cpuMs", r["cpu_ms"]), ("durMs", r["dur_ms"]), ("reads", r["reads"]), ("writes", r["writes"]),
                         ("execs", r["execs"]), ("failed", r["failed"])):
                a[k] += (v or 0) * share
            a["queries"] += share
            if a["top"] is None or (r["cpu_ms"] or 0) > a["top"]["cpuMs"]:
                a["top"] = {"queryId": r["query_id"], "cpuMs": r["cpu_ms"] or 0, "text": (r["text"] or "")[:20000]}
        tot["cpu"] += r["cpu_ms"] or 0
        tot["dur"] += r["dur_ms"] or 0
        tot["reads"] += r["reads"] or 0
        tot["writes"] += r["writes"] or 0
        tot["execs"] += r["execs"] or 0
    out = sorted(agg.values(), key=lambda a: -a["cpuMs"])
    for a in out:
        a["cpuPct"] = a["cpuMs"] / tot["cpu"] * 100 if tot["cpu"] else 0
        a["readsPct"] = a["reads"] / tot["reads"] * 100 if tot["reads"] else 0
    return {"enabled": True, "rows": out, "totals": tot, "analyzed": len(data), "known": sorted(known.values())}


# --------------------------------------------------- coletor de uso (usuario x esquema)
# No App Service a pasta /home é persistente (some só se o app for recriado); localmente fica em runtime/dbstatus.
_DEFAULT_DATA = "/home/dbstatus" if ON_APP_SERVICE else os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "runtime", "dbstatus")
DATA_DIR = os.environ.get("DBSTATUS_DATA_DIR") or _DEFAULT_DATA
USAGE_DB = os.path.join(DATA_DIR, "usage.db")
# WAL não é seguro em disco de rede (/home do App Service); lá usa o modo comum.
JOURNAL_MODE = "DELETE" if ON_APP_SERVICE else "WAL"
USAGE_ON = os.environ.get("USAGE_SAMPLER", "1") != "0"
USAGE_EVERY = max(10, int(os.environ.get("USAGE_INTERVAL", "30")))
USAGE_KEEP_DAYS = 31
_sq = None
_sq_lock = threading.Lock()
_prev = {}
_sampler_state = {}
SAMPLER_POOL = ThreadPoolExecutor(max_workers=4)

SESS_USAGE_SQL = """SELECT s.session_id, ISNULL(s.login_name,'?') login_name, ISNULL(s.host_name,'?') host_name,
 ISNULL(s.program_name,'?') program_name, CONVERT(varchar(30), s.login_time, 126) lt, s.cpu_time, s.logical_reads, s.writes,
 CONVERT(varchar(30), SYSDATETIME(), 126) now_s
 FROM sys.dm_exec_sessions s
 WHERE s.is_user_process=1 AND s.session_id<>@@SPID AND ISNULL(s.program_name,'')<>'DatabaseStatus'
 AND s.login_name<>'NT AUTHORITY\\SYSTEM'"""
REQ_USAGE_SQL = """SELECT ISNULL(s.login_name,'?') login_name, ISNULL(s.host_name,'?') host_name, ISNULL(s.program_name,'?') program_name,
 OBJECT_SCHEMA_NAME(t.objectid, t.dbid) obj_schema, LEFT(t.text, 4000) txt
 FROM sys.dm_exec_requests r JOIN sys.dm_exec_sessions s ON s.session_id=r.session_id
 OUTER APPLY sys.dm_exec_sql_text(r.sql_handle) t
 WHERE s.is_user_process=1 AND r.session_id<>@@SPID AND ISNULL(s.program_name,'')<>'DatabaseStatus'
 AND s.login_name<>'NT AUTHORITY\\SYSTEM'"""


def dbkey(db):
    return f"{db['server']}/{db['name']}"


def usage_init():
    global _sq
    os.makedirs(DATA_DIR, exist_ok=True)
    _sq = sqlite3.connect(USAGE_DB, timeout=30, check_same_thread=False)
    with _sq_lock:
        _sq.executescript(f"""
        PRAGMA journal_mode={JOURNAL_MODE};
        CREATE TABLE IF NOT EXISTS usage_user(ts INTEGER, db TEXT, login TEXT, host TEXT, program TEXT, cpu_ms INTEGER, reads INTEGER, writes INTEGER, sessions INTEGER);
        CREATE TABLE IF NOT EXISTS usage_req(ts INTEGER, db TEXT, login TEXT, host TEXT, program TEXT, sch TEXT, n INTEGER);
        CREATE TABLE IF NOT EXISTS usage_meta(db TEXT PRIMARY KEY, since INTEGER);
        CREATE INDEX IF NOT EXISTS ix_uu ON usage_user(db, ts);
        CREATE INDEX IF NOT EXISTS ix_ur ON usage_req(db, ts);
        """)
        _sq.commit()


def sample_db(db, ts):
    sess = with_conn(db, "light", lambda c: q(c, SESS_USAGE_SQL))
    reqs = with_conn(db, "light", lambda c: q(c, REQ_USAGE_SQL))
    try:
        known, objmap = known_schemas(db), known_objects(db)
    except Exception:
        known, objmap = {}, {}
    key = dbkey(db)
    prev = _prev.get(db["id"])
    cur, agg = {}, {}
    now_s = sess[0]["now_s"] if sess else None
    for r in sess:
        k = (r["session_id"], r["lt"])
        vals = (r["cpu_time"] or 0, r["logical_reads"] or 0, r["writes"] or 0)
        cur[k] = vals
        if prev is None:
            continue
        pv = prev["s"].get(k)
        if pv is not None:
            d = tuple(max(0, a - b) for a, b in zip(vals, pv))
        elif prev["cut"] and r["lt"] > prev["cut"]:
            d = vals  # sessao nova desde a ultima coleta: tudo que gastou e novo
        else:
            d = (0, 0, 0)
        g = agg.setdefault((r["login_name"], r["host_name"], r["program_name"]), [0, 0, 0, 0])
        g[0] += d[0]; g[1] += d[1]; g[2] += d[2]; g[3] += 1
    _prev[db["id"]] = {"s": cur, "cut": now_s or (prev or {}).get("cut")}
    rq = {}
    for r in reqs:
        sc = {r["obj_schema"]} if r["obj_schema"] else schemas_in(r["txt"], known, objmap)
        if not sc:
            sc = {NO_SCHEMA}
        for s in sc:
            k = (r["login_name"], r["host_name"], r["program_name"], s)
            rq[k] = rq.get(k, 0) + 1
    with _sq_lock:
        cu = _sq.cursor()
        cu.execute("INSERT OR IGNORE INTO usage_meta(db, since) VALUES(?,?)", (key, ts))
        for (lg, ho, pr), g in agg.items():
            if g[0] or g[1] or g[2]:
                cu.execute("INSERT INTO usage_user VALUES(?,?,?,?,?,?,?,?,?)", (ts, key, lg, ho, pr, g[0], g[1], g[2], g[3]))
        for (lg, ho, pr, sc), n in rq.items():
            cu.execute("INSERT INTO usage_req VALUES(?,?,?,?,?,?,?)", (ts, key, lg, ho, pr, sc, n))
        _sq.commit()


def sampler_loop():
    time.sleep(15)
    last_prune = 0
    while True:
        t0 = time.time()
        try:
            dbs = [d for d in databases() if d["state"] in (None, "Online")]
            futs = [(d, SAMPLER_POOL.submit(sample_db, d, int(t0))) for d in dbs]
            for d, f in futs:
                try:
                    f.result(timeout=90)
                    _sampler_state[d["id"]] = {"ok": True, "ts": int(t0)}
                except Exception as e:
                    _sampler_state[d["id"]] = {"ok": False, "ts": int(t0), "error": str(e)[:200]}
            if t0 - last_prune > 6 * 3600:
                last_prune = t0
                lim = int(t0 - USAGE_KEEP_DAYS * 86400)
                with _sq_lock:
                    _sq.execute("DELETE FROM usage_user WHERE ts<?", (lim,))
                    _sq.execute("DELETE FROM usage_req WHERE ts<?", (lim,))
                    _sq.commit()
        except Exception:
            traceback.print_exc()
        time.sleep(max(5, USAGE_EVERY - (time.time() - t0)))


def window_epoch(qs):
    if "from" in qs and "to" in qs:
        p = lambda s: datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
        return int(p(qs["from"][0])), int(p(qs["to"][0]))
    hours = max(1, min(int(qs.get("hours", ["24"])[0]), 24 * 30))
    t = int(time.time())
    return t - hours * 3600, t


def api_usage(qs):
    db = find_db(qs["s"][0], qs["d"][0])
    key = dbkey(db)
    f, t = window_epoch(qs)
    out = {"enabled": USAGE_ON, "interval": USAGE_EVERY, "from": f * 1000, "to": t * 1000,
           "sampler": _sampler_state.get(db["id"]), "users": [], "schemas": [], "timeline": {"t": [], "series": {}},
           "totals": {"cpuMs": 0, "reads": 0, "writes": 0}, "since": None}
    if _sq is None:
        return out
    bucket = max(60, int((t - f) / 60) // 60 * 60)
    with _sq_lock:
        cu = _sq.cursor()
        m = cu.execute("SELECT since FROM usage_meta WHERE db=?", (key,)).fetchone()
        urows = cu.execute("SELECT login, host, program, SUM(cpu_ms), SUM(reads), SUM(writes) FROM usage_user WHERE db=? AND ts>=? AND ts<=? GROUP BY login, host, program", (key, f, t)).fetchall()
        rrows = cu.execute("SELECT login, sch, SUM(n) FROM usage_req WHERE db=? AND ts>=? AND ts<=? GROUP BY login, sch", (key, f, t)).fetchall()
        trows = cu.execute("SELECT (ts/?)*? b, login, SUM(cpu_ms) FROM usage_user WHERE db=? AND ts>=? AND ts<=? GROUP BY b, login", (bucket, bucket, key, f, t)).fetchall()
    out["since"] = m[0] * 1000 if m else None
    mins = lambda n: n * USAGE_EVERY / 60.0
    users, schemas = {}, {}
    for lg, ho, pr, cpu, rd, wr in urows:
        u = users.setdefault(lg, {"login": lg, "cpuMs": 0, "reads": 0, "writes": 0, "activeMin": 0.0, "origins": [], "schemas": {}})
        u["cpuMs"] += cpu or 0; u["reads"] += rd or 0; u["writes"] += wr or 0
        u["origins"].append({"host": ho, "program": pr, "cpuMs": cpu or 0, "reads": rd or 0, "writes": wr or 0})
    for lg, sc, n in rrows:
        u = users.setdefault(lg, {"login": lg, "cpuMs": 0, "reads": 0, "writes": 0, "activeMin": 0.0, "origins": [], "schemas": {}})
        u["activeMin"] += mins(n); u["schemas"][sc] = u["schemas"].get(sc, 0) + mins(n)
        s = schemas.setdefault(sc, {"schema": sc, "activeMin": 0.0, "users": {}})
        s["activeMin"] += mins(n); s["users"][lg] = s["users"].get(lg, 0) + mins(n)
    tc = sum(u["cpuMs"] for u in users.values()); tr = sum(u["reads"] for u in users.values()); tw = sum(u["writes"] for u in users.values())
    ta = sum(u["activeMin"] for u in users.values())
    ul = sorted(users.values(), key=lambda u: (-u["cpuMs"], -u["activeMin"]))
    for u in ul:
        u["cpuPct"] = u["cpuMs"] / tc * 100 if tc else 0
        u["readsPct"] = u["reads"] / tr * 100 if tr else 0
        u["activePct"] = u["activeMin"] / ta * 100 if ta else 0
        u["origins"] = sorted(u["origins"], key=lambda o: -o["cpuMs"])[:8]
        u["schemas"] = sorted(({"schema": k, "activeMin": v} for k, v in u["schemas"].items()), key=lambda x: -x["activeMin"])[:8]
    sl = sorted(schemas.values(), key=lambda s: -s["activeMin"])
    for s in sl:
        s["activePct"] = s["activeMin"] / ta * 100 if ta else 0
        s["users"] = sorted(({"login": k, "activeMin": v} for k, v in s["users"].items()), key=lambda x: -x["activeMin"])[:6]
    top = [u["login"] for u in ul if u["cpuMs"] > 0][:6]
    start = f // bucket * bucket
    ts = list(range(start, t + bucket, bucket))
    idx = {b: i for i, b in enumerate(ts)}
    series = {lg: [0.0] * len(ts) for lg in top}
    if len([u for u in ul if u["cpuMs"] > 0]) > len(top):
        series["outros"] = [0.0] * len(ts)
    for b, lg, cpu in trows:
        i = idx.get(b)
        if i is None:
            continue
        k = lg if lg in top else "outros"
        if k in series:
            series[k][i] += (cpu or 0) / 1000.0
    out.update({"users": ul, "schemas": sl, "totals": {"cpuMs": tc, "reads": tr, "writes": tw, "activeMin": ta},
                "timeline": {"t": [b * 1000 for b in ts], "series": series, "bucketMin": bucket / 60}})
    return out


def memo(fn, ttl):
    def w(qs):
        key = ("route", fn.__name__, json.dumps(qs, sort_keys=True))
        return cached(key, ttl, lambda: fn(qs))
    return w


ROUTES = {
    "/api/databases": lambda qs: api_databases(),
    "/api/overview": api_overview,
    "/api/snapshot": api_snapshot,
    "/api/db": api_db,
    "/api/db/live": api_live,
    "/api/db/queries": memo(api_qs, 60),
    "/api/db/extra": memo(api_extra, 120),
    "/api/db/events": api_events,
    "/api/db/usage": api_usage,
    "/api/db/schemas": memo(api_schemas, 120),
}


_started = False
_start_lock = threading.Lock()


def start():
    """Prepara o histórico de uso e liga o coletor (uma vez por processo)."""
    global _started
    with _start_lock:
        if _started:
            return False
        usage_init()
        if USAGE_ON:
            threading.Thread(target=sampler_loop, daemon=True, name="dbstatus-sampler").start()
        _started = True
        return True
