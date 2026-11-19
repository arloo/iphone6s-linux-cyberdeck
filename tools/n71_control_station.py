#!/usr/bin/env python3
"""Read-only N71 Cyberdeck LAN control station.

No shell-execution endpoint, inbound terminal, credentials, device identifiers,
raw log tails, SSH ports or private content exposed. Restrict to Mint + local
Dell IPs, bind only on Dell's specific LAN interface. No third-party deps.
"""
import argparse
from datetime import datetime, timezone
import html
import stat
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.parse import urlsplit

REPO = Path.home() / "Documenti/iphone6s-linux-cyberdeck-public"
EVENTS = Path.home() / ".local/share/cyberdeck/control-station/events.jsonl"
SETUP = Path.home() / ".local/share/cyberdeck/control-station/setup-mint.sh"
MINT_IP = os.environ.get("N71_MINT_IP", "")
HOST_IP = os.environ.get("N71_HOST_IP", "127.0.0.1")
PORT = 8765
ALLOWED = {"127.0.0.1", HOST_IP} | ({MINT_IP} if MINT_IP else set())
CACHE = None
CACHE_AT = 0

PAGE = r"""<!doctype html>
<html lang="it"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CYBERDECK // CONTROL STATION</title>
<style>
:root {color-scheme:dark;--bg:#090e16;--panel:#111a28;--border:#25334b;--fg:#d9e8f1;--muted:#8ca5b6;--green:#68eac0;--amber:#ffcf7d;--blue:#86b9ff}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 80% 5%,#15263a,transparent 55%),var(--bg);color:var(--fg);font:15px/1.5 ui-monospace,SFMono-Regular,Consolas,monospace}
main{max-width:1540px;padding:26px 32px 45px;margin:auto}header{display:flex;align-items:flex-start;justify-content:space-between;gap:24px;border-bottom:1px solid var(--border);padding-bottom:22px;margin-bottom:26px;flex-wrap:wrap}
h1{font-size:29px;letter-spacing:.08em;margin:0;font-weight:700}h2{font-size:14px;text-transform:uppercase;letter-spacing:.13em;margin:0 0 14px;color:var(--blue)}
.small{font-size:12px;color:var(--muted)}.subtitle{color:var(--muted);margin-top:7px}.live{display:inline-flex;align-items:center;gap:8px;color:var(--green);font-size:13px}.dot{background:var(--green);border-radius:50%;width:8px;height:8px;box-shadow:0 0 12px #68eac070}
.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px}section{min-width:0;background:linear-gradient(165deg,#132034 0%,var(--panel) 100%);border:1px solid var(--border);border-radius:14px;padding:21px;box-shadow:0 7px 25px #0003}
.wide{grid-column:span 2}.stat{font-size:29px;letter-spacing:-.025em;font-weight:700;margin:6px 0 10px;color:var(--green)}.line{display:flex;justify-content:space-between;gap:15px;padding:7px 0;border-bottom:1px solid #213045}.line:last-child{border:0}.line span:first-child{color:var(--muted)}.line strong{text-align:right;overflow-wrap:anywhere}
.note{font-size:12px;color:var(--muted);margin-top:14px}.warn{color:var(--amber)!important}.good{color:var(--green)}.pill{border:1px solid var(--border);padding:3px 10px;border-radius:99px;font-size:12px;white-space:nowrap}
ol{margin:0;padding-left:24px}li{padding:8px 0;border-bottom:1px solid #213045}li:last-child{border:0}
footer{padding-top:25px;font-size:12px;color:var(--muted)}button{background:transparent;color:var(--fg);border:1px solid #42607b;border-radius:8px;padding:8px 12px;font:inherit;cursor:pointer}
@media(max-width:1050px){.grid{grid-template-columns:repeat(2,minmax(0,1fr))}.wide{grid-column:span 2}}@media(max-width:680px){main{padding:16px}.grid{grid-template-columns:1fr}.wide{grid-column:span 1}h1{font-size:21px}.stat{font-size:24px}}
</style></head>
<body><main><header>
<div><h1>CYBERDECK <span class="good">//</span> CONTROL STATION</h1>
<div class="subtitle">N71 • Apple A9 • Linux Development Lab — Dell XPS host / Mint monitor</div>
<div class="subtitle"><a href="/setup" style="color:#68eac0">Configura accesso SSH a Mint · Apri comandi da copiare</a>
· <a href="/usb" style="color:#ffcf7d">Prepara installer Debian su USB · Un comando</a></div></div>
<div style="text-align:right"><div class="live"><span class="dot"></span><span id="connection">CONNESSIONE INIZIALE</span></div>
<div class="small" id="now">—</div><button id="refresh" type="button">Aggiorna ora</button></div></header>
<div class="grid">
<section><h2>DELL XPS · HOST</h2><div class="stat" id="hostState">—</div>
<div class="line"><span>Uptime</span><strong id="uptime">—</strong></div>
<div class="line"><span>Load (1m / 5m)</span><strong id="load">—</strong></div>
<div class="line"><span>RAM disponibile</span><strong id="memory">—</strong></div>
<div class="line"><span>LAN</span><strong id="hostIP">—</strong></div>
<div class="note">Telemetria minima, senza accesso remoto ai comandi.</div></section>
<section><h2>IPHONE 6S · USB</h2><div class="stat" id="phoneState">—</div>
<div class="line"><span>Stato collegamento</span><strong id="usbMode">—</strong></div>
<div class="line"><span>Linux USB</span><strong id="linuxUSB">—</strong></div>
<div class="line"><span>Ricarica / percentuale</span><strong id="battery">—</strong></div>
<div class="note">Se sul caricatore esterno, la batteria non è leggibile dal Dell. Non indica un guasto.</div></section>
<section><h2>MINT · MONITOR</h2><div class="stat" id="mintState">—</div>
<div class="line"><span>IP previsto</span><strong id="mintIP">—</strong></div>
<div class="line"><span>Controllo LAN</span><strong id="mintPing">—</strong></div>
<div class="line"><span>Interfaccia</span><strong>Web read-only</strong></div>
<div class="note">La postazione Mint visualizza la dashboard; il Dell raccoglie i dati.</div></section>
<section><h2>GIT · DEVELOPMENT</h2><div class="stat" id="gitBranch" style="font-size:21px">—</div>
<div class="line"><span>Ultimo commit</span><strong id="gitCommit">—</strong></div>
<div class="line"><span>Working tree</span><strong id="gitDirty">—</strong></div>
<div class="line"><span>Build in esecuzione</span><strong id="build">—</strong></div>
<div class="note">Solo metadati del repository pubblico, non i contenuti dei file.</div></section>
<section><h2>SERVIZI E SUPERVISIONE</h2>
<div class="line"><span>Briefing timer</span><strong id="brief">—</strong></div>
<div class="line"><span>USB mux</span><strong id="usbmux">—</strong></div>
<div class="line"><span>Control Station</span><strong class="good">ONLINE</strong></div>
<div class="line"><span>Ultimo campionamento</span><strong id="sample">—</strong></div>
<div class="note">Il monitor rimane disponibile quando Mint è acceso e il Dell è raggiungibile.</div></section>
<section><h2>STATO DEL PROGETTO</h2>
<div class="line"><span>Touch + interfaccia</span><strong class="good">Provati su Linux</strong></div>
<div class="line"><span>Wi-Fi + Bluetooth</span><strong class="good">Provati su Linux</strong></div>
<div class="line"><span>Charging 500 mA</span><strong class="warn">Pronto / non attivo</strong></div>
<div class="line"><span>NVMe NAND</span><strong class="warn">DMA cleanup aperto</strong></div>
<div class="note">Checkpoint tecnico, non è uno stato letto dinamicamente da NAND.</div></section>
<section class="wide"><h2>ATTIVITÀ · COMMIT RECENTI</h2><ol id="commits"><li>Caricamento...</li></ol></section>
<section><h2>EVENTI DI LABORATORIO</h2><ol id="events"><li>Caricamento...</li></ol>
<div class="note">Eventi annotati esplicitamente dal Dell; non cattura schermi o conversazioni.</div></section>
</div><footer>CYBERDECK CONTROL STATION · LAN autorizzata · solo lettura · accesso limitato a Mint + Dell · nessuna API di esecuzione comandi · refresh 5 secondi</footer>
</main><script>
"use strict";
function set(id,value){document.getElementById(id).textContent=String(value===null||value===undefined?"—":value);}
function listing(id,rows){const ul=document.getElementById(id);ul.replaceChildren();for(const value of rows){const li=document.createElement("li");li.textContent=String(value);ul.append(li);}if(!rows.length){const li=document.createElement("li");li.textContent="Nessun evento recente";ul.append(li);}}
let inflight=false;
async function refresh(){
if(inflight)return;inflight=true;const controller=new AbortController();const timeout=setTimeout(()=>controller.abort(),4500);
try{
const response=await fetch("/api/status",{cache:"no-store",signal:controller.signal});
if(!response.ok)throw Error("HTTP "+response.status);
const x=await response.json();
set("connection","LIVE / AGGIORNATO");set("now",new Date().toLocaleString("it-IT"));
set("hostState","ONLINE");set("uptime",x.host.uptime);set("load",x.host.load);set("memory",x.host.memory_mib+" MiB");set("hostIP",x.host.ip);
set("phoneState",x.phone.state);set("usbMode",x.phone.detail);set("linuxUSB",x.phone.linux_usb?"Attivo":"Non collegato");set("battery",x.phone.battery);
set("mintState",x.mint.online?"LAN OK":"Non raggiungibile");set("mintIP",x.mint.ip);set("mintPing",x.mint.online?x.mint.latency:"Offline");
set("gitBranch",x.git.branch);set("gitCommit",x.git.commit);set("gitDirty",x.git.clean?"Pulito":"Modifiche locali");set("build",x.host.build);
set("brief",x.services.briefing);set("usbmux",x.services.usbmuxd);set("sample",x.timestamp);
listing("commits",x.git.recent);listing("events",x.events);
}catch(e){set("connection","OFFLINE / DATI NON DISPONIBILI");set("now",new Date().toLocaleString("it-IT"));}
finally{clearTimeout(timeout);inflight=false;}
}
document.getElementById("refresh").addEventListener("click",refresh);
refresh();setInterval(refresh,5000);
</script></body></html>"""

def usb_writer_html():
    """Read-only, copyable single-command handoff for owner-authenticated Mint GUI."""
    return """<!doctype html><html lang="it"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CYBERDECK // Installer USB Debian</title><style>
:root{color-scheme:dark}body{margin:auto;max-width:940px;background:#08121c;color:#e6f3fa;font:16px/1.5 system-ui,sans-serif;padding:32px}
a{color:#93c7ff}.box{padding:22px;border:1px solid #2c4862;border-radius:12px;background:#102236}h1{font-size:26px}p{color:#aec1cf}
textarea{box-sizing:border-box;width:100%;min-height:130px;padding:15px;background:#061421;color:#b9f8df;border:1px solid #46657c;border-radius:9px;font:14px/1.7 ui-monospace,monospace}
button{margin-top:12px;padding:12px 20px;background:#65e0b4;color:#0b241d;font-weight:bold;border:none;border-radius:7px;cursor:pointer}
li{margin:9px 0}.warn{color:#ffd898}
</style></head><body>
<a href="/">← Torna alla Control Station</a>
<h1>Debian 13.7 · Scrittura USB protetta</h1>
<p>Supporto identificato: <b>Kingston DataTraveler /dev/sdc, 29 GiB</b>.
La ISO è già stata autenticata e verificata. Il controllo preliminare ha dato esito positivo.</p>
<div class="box"><p class="warn"><b>Attenzione:</b> questa operazione cancellerà soltanto la chiavetta USB Kingston.
Lo script controlla modello, vendor, capacità e identificatore fisico prima di scrivere.
I dischi SATA Toshiba e Seagate sono esclusi.</p>
<label for="cmd">Comando unico da incollare nella Konsole di Mint</label>
<textarea id="cmd" readonly spellcheck="false">sudo bash /home/victor/Downloads/Debian-13.7-verified/write-installer-verified.sh --write</textarea>
<button type="button" id="copy">Copia comando</button><span id="status" role="status"></span>
</div>
<ol><li>Fai clic su «Copia comando» e apri Konsole sul computer Mint.</li>
<li>Incolla con <b>Ctrl+Shift+V</b> e premi Invio.</li>
<li>Inserisci <b>solo in Konsole</b> la password sudo di victor.</li>
<li>Attendi il messaggio <b>DEBIAN13_7_INSTALLER_USB_SUCCESS_AND_READBACK_VERIFIED</b>.</li>
</ol>
<p>Se la copia automatica è bloccata dal browser, seleziona il testo con Ctrl+A, premi Ctrl+C e incollalo in Konsole.
Non scollegare la chiavetta durante la scrittura e la verifica.</p>
<script>
document.getElementById("copy").addEventListener("click",async()=>{
const x=document.getElementById("cmd"),s=document.getElementById("status");
x.focus();x.select();let ok=false;
try{if(navigator.clipboard&&isSecureContext){await navigator.clipboard.writeText(x.value);ok=true;}}catch(e){}
if(!ok){try{ok=document.execCommand("copy");}catch(e){}}
s.textContent=ok?" Copiato!":" Testo selezionato: premi Ctrl+C.";
});
</script></body></html>""".encode("utf-8")

def setup_html():
    """Render a local read-only owner-provisioning snippet, never execute it."""
    if SETUP.is_symlink() or not SETUP.is_file():
        return None
    info=SETUP.stat()
    if info.st_uid != os.getuid() or info.st_mode & 0o077 or info.st_size > 30000:
        return None
    command=html.escape(SETUP.read_text(encoding="utf-8"),quote=True)
    page="""<!doctype html><html lang="it"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CYBERDECK // Configura Mint</title><style>
:root{color-scheme:dark}body{background:#09121c;color:#e0eef5;font:15px/1.5 system-ui,sans-serif;margin:auto;padding:30px;max-width:1020px}
a{color:#9bcaff}h1{font-size:27px}p{color:#a5bfce}
textarea{width:100%;height:63vh;box-sizing:border-box;background:#111f2e;color:#e2f9ed;border:1px solid #34526b;border-radius:12px;padding:18px;font:14px/1.5 ui-monospace,Consolas,monospace;resize:vertical}
button{background:#60dab0;color:#0a2120;font-weight:700;border:0;border-radius:8px;padding:11px 16px;cursor:pointer}
#result{color:#96c7ff;margin-left:12px}code{color:#9ee4cc}
</style></head><body>
<a href="/">← Dashboard</a><h1>CYBERDECK // Setup Linux Mint</h1>
<p>Apri Konsole su Mint come utente <code>victor</code>, premi «Copia tutti i comandi» e incolla il blocco.
Il browser non esegue nulla; la password sudo rimane sul computer Mint. Il collegamento SSH è limitato al Dell.</p>
<p><button id="copy" type="button">Copia tutti i comandi</button><span id="result" role="status"></span></p>
<textarea id="commands" aria-label="Comandi SSH da eseguire su Mint" readonly spellcheck="false">""" + command + """</textarea>
<p>Se il pulsante non copia (restrizioni del browser su HTTP): fai clic nel riquadro, poi <strong>Ctrl+A</strong>, <strong>Ctrl+C</strong>, infine incolla in Konsole con <strong>Ctrl+Shift+V</strong>.</p>
<script>
document.getElementById("copy").addEventListener("click", async () => {
 const field=document.getElementById("commands"); const result=document.getElementById("result");
 field.focus();field.select();
 let copied=false;
 try {if(navigator.clipboard && window.isSecureContext){await navigator.clipboard.writeText(field.value);copied=true;}}
 catch(e){}
 if(!copied){try{copied=document.execCommand("copy");}catch(e){}}
 result.textContent=copied?"Copiato. Incolla in Konsole con Ctrl+Shift+V.":"Testo selezionato: premi Ctrl+C, poi Ctrl+Shift+V in Konsole.";
});
</script></body></html>"""
    return page.encode("utf-8")

def run(*args, timeout=3):
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout,
                           check=False, stdin=subprocess.DEVNULL)
        return p.stdout.strip() if p.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""

def read(name):
    try:
        return Path(name).read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return ""

def public_events():
    if EVENTS.is_symlink() or not EVENTS.exists():
        return []
    try:
        s=EVENTS.stat()
        if s.st_uid != os.getuid() or s.st_mode & 0o077 or s.st_size > 100000:
            return []
        lines=EVENTS.read_text(encoding="utf-8").splitlines()[-8:]
        out=[]
        for line in lines:
            item=json.loads(line)
            if set(item) == {"at","message"}:
                out.append((str(item["at"])[:20]+"  "+str(item["message"])[:115]))
        return out[-6:][::-1]
    except (OSError, ValueError):
        return []

def append_event(value):
    if not isinstance(value,str) or len(value)>115 or not value.strip():
        raise ValueError("Short non-sensitive message required")
    if any(ord(c)<32 or ord(c)==127 for c in value) or "\n" in value:
        raise ValueError("Control characters refused")
    EVENTS.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    if EVENTS.is_symlink():
        raise ValueError("Symlink refused")
    if EVENTS.exists() and EVENTS.stat().st_size>95000:
        raise ValueError("Activity file full; rotate manually")
    with EVENTS.open("a",encoding="utf-8") as h:
        os.chmod(EVENTS,0o600)
        h.write(json.dumps({"at":datetime.now().astimezone().strftime("%d/%m %H:%M"),
                            "message":value},ensure_ascii=False)+"\n")

def device_state():
    usb=run("lsusb","-d","05ac:",timeout=2)
    device={"state":"ESTERNO / ASSENTE","detail":"Non collegato al Dell",
            "linux_usb":False,"battery":"Non rilevabile via USB"}
    if "05ac:4142" in usb:
        device.update(state="LINUX A9",detail="USB gadget 05ac:4142",linux_usb=True)
    elif "05ac:12a8" in usb:
        device.update(state="iOS",detail="USB Apple 05ac:12a8")
    elif "05ac:4141" in usb:
        device.update(state="PONGO",detail="USB bootloader")
    elif "05ac:1227" in usb:
        device.update(state="DFU",detail="Modalità DFU")
    return device

def status():
    uptime=read("/proc/uptime").split()
    try: secs=int(float(uptime[0]))
    except (IndexError,ValueError): secs=0
    try:
        mem=int(next(row.split()[1] for row in read("/proc/meminfo").splitlines()
                     if row.startswith("MemAvailable:")))//1024
    except (StopIteration,ValueError,IndexError): mem=0
    load=read("/proc/loadavg").split()
    processes=run("ps","-eo","comm=",timeout=2).splitlines()
    active=sum(1 for p in processes if p.strip() in
               {"make","ninja","gcc","cc1","cc1plus","clang","ld.lld","rustc","aarch64-linux-gnu-gcc"})
    ping=run("ping","-c","1","-W","1",MINT_IP,timeout=2)
    match=re.search(r"time=([0-9.]+) ms",ping)
    branch=run("git","-C",str(REPO),"branch","--show-current",timeout=2)
    commit=run("git","-C",str(REPO),"rev-parse","--short","HEAD",timeout=2)
    dirty=run("git","-C",str(REPO),"status","--porcelain",timeout=2)
    recent=run("git","-C",str(REPO),"log","-5","--format=%h %s",timeout=2)
    brief=run("systemctl","--user","is-active","n71-briefing-push.timer",timeout=2)
    usbmux=run("systemctl","is-active","usbmuxd.service",timeout=2)
    return {"timestamp":datetime.now().astimezone().strftime("%H:%M:%S"),
            "host":{"ip":HOST_IP,"uptime":str(secs//3600)+"h "+str((secs%3600)//60)+"m",
                    "load":"/".join(load[:2]),"memory_mib":mem,"build":str(active)+" processi"},
            "mint":{"ip":MINT_IP or "non configurato","online":bool(match),"latency":match.group(1)+" ms" if match else "—"},
            "phone":device_state(),
            "git":{"branch":branch or "—","commit":commit or "—",
                   "clean":not dirty,"recent":recent.splitlines()[:5]},
            "services":{"briefing":brief or "inactive","usbmuxd":usbmux or "inactive"},
            "events":public_events()}

class Dashboard(BaseHTTPRequestHandler):
    server_version="CyberdeckControl/1.0"
    sys_version=""
    def log_message(self, fmt, *args):
        pass
    def answer(self,status,content_type,payload):
        self.send_response(status)
        self.send_header("Content-Type",content_type)
        self.send_header("Cache-Control","no-store")
        self.send_header("X-Content-Type-Options","nosniff")
        self.send_header("X-Frame-Options","DENY")
        self.send_header("Referrer-Policy","no-referrer")
        self.send_header("Content-Security-Policy",
                         "default-src 'none'; script-src 'unsafe-inline'; "
                         "style-src 'unsafe-inline'; connect-src 'self'; "
                         "base-uri 'none'; frame-ancestors 'none'")
        self.send_header("Content-Length",str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)
    def do_GET(self):
        if self.client_address[0] not in ALLOWED:
            return self.answer(403,"text/plain; charset=utf-8",b"Forbidden")
        path=urlsplit(self.path).path
        if path=="/usb":
            return self.answer(200,"text/html; charset=utf-8",usb_writer_html())
        if path=="/setup":
            page=setup_html()
            return self.answer(200,"text/html; charset=utf-8",page) if page is not None else self.answer(404,"text/plain; charset=utf-8",b"Not configured")
        if path=="/":
            return self.answer(200,"text/html; charset=utf-8",PAGE.encode())
        if path=="/api/status":
            global CACHE,CACHE_AT
            if CACHE is None or time.monotonic()-CACHE_AT>3:
                CACHE=json.dumps(status(),ensure_ascii=False,separators=(",",":")).encode()
                CACHE_AT=time.monotonic()
            return self.answer(200,"application/json; charset=utf-8",CACHE)
        if path=="/healthz":
            return self.answer(200,"text/plain; charset=utf-8",b"ok")
        return self.answer(404,"text/plain; charset=utf-8",b"Not found")
    def do_POST(self):
        return self.answer(405,"text/plain; charset=utf-8",b"Method not allowed")
    do_PUT=do_POST
    do_DELETE=do_POST

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--serve",action="store_true")
    parser.add_argument("--event",type=str)
    opts=parser.parse_args()
    if bool(opts.serve)==bool(opts.event):
        parser.error("Use --serve OR --event MSG")
    if opts.event:
        append_event(opts.event)
        print("CONTROL_STATION_LOCAL_EVENT_RECORDED")
        return
    server=HTTPServer((HOST_IP,PORT),Dashboard)
    print("N71_CONTROL_STATION_READ_ONLY_LAN_IP_ALLOWLIST",flush=True)
    server.serve_forever(poll_interval=.5)

if __name__=="__main__":
    main()
