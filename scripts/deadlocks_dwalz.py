"""Captura e leitura dos deadlocks do DW-ALZ (quem trava quem), usando Extended Events do próprio Azure SQL.

Uso (PowerShell, na pasta do backend):
    .venv\\Scripts\\python.exe scripts\\deadlocks_dwalz.py criar            # só MOSTRA o que faria
    .venv\\Scripts\\python.exe scripts\\deadlocks_dwalz.py criar --confirmo  # cria e liga a captura
    .venv\\Scripts\\python.exe scripts\\deadlocks_dwalz.py ler              # resume os deadlocks capturados (só leitura)
    .venv\\Scripts\\python.exe scripts\\deadlocks_dwalz.py remover --confirmo  # para e apaga a captura
    .venv\\Scripts\\python.exe scripts\\deadlocks_dwalz.py teste            # testa a leitura com um deadlock de exemplo

O que a captura escreve no banco: só a DEFINIÇÃO de uma sessão de eventos (nome `regente_deadlocks`) e um buffer de
até 4 MB em memória com os últimos deadlocks. Nenhuma tabela é criada, nenhum dado é gravado em disco e nenhuma
tabela do sistema é alterada. O evento só dispara quando um deadlock acontece. `remover` apaga tudo.

Usa o login do `az` (Entra), como o DatabaseStatus. Precisa ser administrador do banco.
"""
import re
import struct
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import Counter

SERVER = "alzbdsqlbi.database.windows.net"
DATABASE = "DW-ALZ"
SESSION = "regente_deadlocks"
AZ = r"C:\Users\tharles.cunha\azcli\Scripts\az.bat"

SQL_CRIAR = f"""
IF NOT EXISTS (SELECT 1 FROM sys.database_event_sessions WHERE name = '{SESSION}')
    CREATE EVENT SESSION [{SESSION}] ON DATABASE
    ADD EVENT sqlserver.database_xml_deadlock_report
    ADD TARGET package0.ring_buffer (SET max_memory = 4096)   -- KB: no máximo 4 MB em memória
    WITH (MAX_MEMORY = 4096 KB, EVENT_RETENTION_MODE = ALLOW_SINGLE_EVENT_LOSS, MAX_DISPATCH_LATENCY = 5 SECONDS,
          MEMORY_PARTITION_MODE = NONE, TRACK_CAUSALITY = OFF, STARTUP_STATE = OFF);
"""
SQL_LIGAR = f"ALTER EVENT SESSION [{SESSION}] ON DATABASE STATE = START;"
SQL_PARAR = f"ALTER EVENT SESSION [{SESSION}] ON DATABASE STATE = STOP;"
SQL_APAGAR = f"DROP EVENT SESSION [{SESSION}] ON DATABASE;"
SQL_LER = f"""
SELECT CAST(t.target_data AS nvarchar(max)) AS dados
FROM sys.dm_xe_database_session_targets t
JOIN sys.dm_xe_database_sessions s ON s.address = t.event_session_address
WHERE s.name = '{SESSION}' AND t.target_name = 'ring_buffer'
"""
SQL_EXISTE = f"SELECT CASE WHEN EXISTS (SELECT 1 FROM sys.database_event_sessions WHERE name='{SESSION}') THEN 1 ELSE 0 END"


def conectar():
    import pyodbc

    out = subprocess.run(
        [AZ, "account", "get-access-token", "--resource", "https://database.windows.net/", "--query", "accessToken", "-o", "tsv"],
        capture_output=True, text=True, timeout=90,
    )
    if out.returncode != 0:
        sys.exit("az falhou: " + (out.stderr or "")[:300])
    tok = out.stdout.strip().encode("utf-16-le")
    return pyodbc.connect(
        f"DRIVER={{ODBC Driver 18 for SQL Server}};SERVER={SERVER};DATABASE={DATABASE};Encrypt=yes;TrustServerCertificate=no;APP=Regente-deadlocks",
        attrs_before={1256: struct.pack(f"<I{len(tok)}s", len(tok), tok)},
        autocommit=True,
    )


# ------------------------------------------------------------------ leitura do XML dos deadlocks
def _sql_resumido(texto, limite=110):
    t = re.sub(r"\s+", " ", texto or "").strip()
    t = re.sub(r"^\(@P\d+ [^)]*\)", "", t).strip()  # tira a declaração de parâmetros do SQLAlchemy
    t = re.sub(r"\bSELECT\b.*?\bFROM\b", "SELECT ... FROM", t, count=1, flags=re.I) if len(t) > limite else t
    return t[:limite]


def interpretar(dados_xml):
    """Lê o buffer de eventos e devolve uma lista de deadlocks já resumidos."""
    raiz = ET.fromstring(dados_xml)
    achados = []
    for ev in raiz.iter("event"):
        if ev.get("name") not in ("database_xml_deadlock_report", "xml_deadlock_report"):
            continue
        dl = ev.find(".//deadlock")
        if dl is None:
            continue
        vitimas = {v.get("id") for v in dl.iter("victimProcess")}
        procs = {}
        for p in dl.iter("process"):
            texto = (p.findtext("inputbuf") or "").strip()
            procs[p.get("id")] = {
                "spid": p.get("spid"), "login": p.get("loginname"), "app": p.get("clientapp"), "host": p.get("hostname"),
                "isolamento": p.get("isolationlevel"), "espera": p.get("waitresource"), "sql": _sql_resumido(texto),
                "vitima": p.get("id") in vitimas,
            }
        recursos = []
        lista = dl.find("resource-list")
        for r in (list(lista) if lista is not None else []):
            recursos.append({
                "tipo": r.tag, "objeto": (r.get("objectname") or "").split(".")[-1], "indice": r.get("indexname"), "modo": r.get("mode"),
                "donos": [(o.get("id"), o.get("mode")) for o in r.iter("owner")],
                "esperando": [(w.get("id"), w.get("mode")) for w in r.iter("waiter")],
            })
        achados.append({"quando": ev.get("timestamp"), "processos": procs, "recursos": recursos})
    return achados


def resumir(achados):
    if not achados:
        return "Nenhum deadlock capturado ainda."
    linhas = [f"{len(achados)} deadlock(s) capturado(s) (do mais antigo ao mais novo: {achados[0]['quando']} a {achados[-1]['quando']})\n"]
    padroes, recursos = Counter(), Counter()
    for d in achados:
        sqls = sorted({p["sql"] for p in d["processos"].values()})
        vit = next((p["sql"] for p in d["processos"].values() if p["vitima"]), "?")
        padroes[(" <-> ".join(sqls), vit)] += 1
        for r in d["recursos"]:
            recursos[(r["tipo"], r["objeto"], r["indice"], r["modo"])] += 1
    linhas.append("PADRÕES (quem se trava), do mais frequente:")
    for (par, vit), n in padroes.most_common(8):
        linhas.append(f"  {n:4}x  {par}\n         cancelada (vítima): {vit}")
    linhas.append("\nO QUE ESTAVA TRAVADO (recurso):")
    for (tipo, obj, idx, modo), n in recursos.most_common(8):
        linhas.append(f"  {n:4}x  {tipo} em {obj}.{idx} (modo {modo})")
    ex = achados[-1]
    linhas.append("\nÚLTIMO DEADLOCK, em detalhe:")
    for pid, p in ex["processos"].items():
        linhas.append(f"  {'VÍTIMA ' if p['vitima'] else 'segue  '} spid={p['spid']} {p['login']}@{p['host']} ({p['app']}) isolamento={p['isolamento']}")
        linhas.append(f"          esperava: {p['espera']}\n          SQL: {p['sql']}")
    return "\n".join(linhas)


EXEMPLO = """<RingBufferTarget><event name="xml_deadlock_report" timestamp="2026-11-04T23:00:00.000Z"><data name="xml_report"><value>
<deadlock><victim-list><victimProcess id="p1"/></victim-list><process-list>
<process id="p1" spid="55" loginname="orkaflow_user" clientapp="Python" hostname="API" isolationlevel="serializable (4)" waitresource="KEY: 5:72057 (a1)">
<inputbuf>(@P1 int,@P2 varchar(10)) SELECT tasks.id, tasks.status FROM tasks WITH (UPDLOCK, ROWLOCK, HOLDLOCK) WHERE tasks.automation_id = @P1 AND tasks.status IN (@P2)</inputbuf></process>
<process id="p2" spid="61" loginname="orkaflow_user" clientapp="Python" hostname="WORKERS" isolationlevel="serializable (4)" waitresource="KEY: 5:72057 (b2)">
<inputbuf>(@P1 int) UPDATE tasks SET status='READY', runner_id=@P1 WHERE tasks.id = @P1</inputbuf></process>
</process-list><resource-list>
<keylock objectname="DW-ALZ.orkaflow.tasks" indexname="ix_tasks_automation_id" mode="U"><owner-list><owner id="p2" mode="U"/></owner-list><waiter-list><waiter id="p1" mode="U"/></waiter-list></keylock>
<keylock objectname="DW-ALZ.orkaflow.tasks" indexname="pk_tasks" mode="X"><owner-list><owner id="p1" mode="X"/></owner-list><waiter-list><waiter id="p2" mode="U"/></waiter-list></keylock>
</resource-list></deadlock></value></data></event></RingBufferTarget>"""


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    confirmo = "--confirmo" in sys.argv

    if cmd == "teste":
        achados = interpretar(EXEMPLO)
        assert len(achados) == 1 and len(achados[0]["processos"]) == 2 and len(achados[0]["recursos"]) == 2
        assert sum(p["vitima"] for p in achados[0]["processos"].values()) == 1
        print(resumir(achados))
        print("\nteste OK")
    elif cmd == "criar":
        print("VAI EXECUTAR em", f"{SERVER}/{DATABASE}:\n", SQL_CRIAR, "\n", SQL_LIGAR)
        if not confirmo:
            print("\n(simulação: nada foi feito. Rode de novo com --confirmo para criar e ligar.)")
            return
        cur = conectar().cursor()
        cur.execute(SQL_CRIAR)
        cur.execute(SQL_LIGAR)
        print("captura criada e ligada. Daqui a uns 20 minutos rode: ler")
    elif cmd == "ler":
        cur = conectar().cursor()
        cur.execute(SQL_EXISTE)
        if not cur.fetchone()[0]:
            print("A captura não existe (rode: criar --confirmo).")
            return
        cur.execute(SQL_LER)
        linha = cur.fetchone()
        print(resumir(interpretar(linha[0])) if linha and linha[0] else "A captura existe, mas ainda não está ligada ou não tem dados.")
    elif cmd == "remover":
        print("VAI EXECUTAR:", SQL_PARAR, SQL_APAGAR)
        if not confirmo:
            print("\n(simulação: nada foi feito. Rode de novo com --confirmo.)")
            return
        cur = conectar().cursor()
        try:
            cur.execute(SQL_PARAR)
        except Exception:
            pass
        cur.execute(SQL_APAGAR)
        print("captura removida.")
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
