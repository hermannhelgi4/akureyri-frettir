#!/usr/bin/env python3
"""Sækir fréttir úr RSS-veitum, síar landsmiðla eftir Akureyri og býr til news.json."""
import json, re, html, time, urllib.request, urllib.robotparser, urllib.error
from urllib.parse import urlparse
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone

# local=True  -> allar fréttir koma inn (miðill er bara á Akureyri)
# local=False -> aðeins fréttir sem tengjast Akureyri (sía hér fyrir neðan)
FEEDS = [
    # Fréttamiðlar (cat = flokkur í appinu)
    {"name": "Akureyri.net", "url": "https://www.akureyri.net/feed", "local": True, "cat": "Fréttamiðlar"},
    {"name": "Kaffið", "url": "https://www.kaffid.is/feed", "local": True, "cat": "Fréttamiðlar"},
    {"name": "Vikudagur", "url": "https://www.vikudagur.is/feed", "local": True, "cat": "Fréttamiðlar"},
    {"name": "mbl.is", "url": "https://www.mbl.is/feeds/innlent/", "local": False, "cat": "Fréttamiðlar"},
    {"name": "RÚV", "url": "https://www.ruv.is/rss/frettir", "local": False, "cat": "Fréttamiðlar"},
    {"name": "Vísir", "url": "https://www.visir.is/rss/allt", "local": False, "cat": "Fréttamiðlar"},
    # Fleiri veitur hjá landsmiðlum til að auka líkurnar á að Akureyri-fréttir náist.
    # Slóðirnar merktar (óstaðfest) eru giskaðar eftir sniði hinna; ef þær bila er þeim bara sleppt.
    {"name": "mbl.is", "url": "https://www.mbl.is/feeds/nyjast/", "local": False, "cat": "Fréttamiðlar"},
    {"name": "mbl.is", "url": "https://www.mbl.is/feeds/200milur/", "local": False, "cat": "Fréttamiðlar"},  # (óstaðfest)
    {"name": "mbl.is", "url": "https://www.mbl.is/feeds/sport/", "local": False, "cat": "Fréttamiðlar"},  # (óstaðfest)
    {"name": "mbl.is", "url": "https://www.mbl.is/feeds/menning/", "local": False, "cat": "Fréttamiðlar"},  # (óstaðfest)
    {"name": "RÚV", "url": "https://www.ruv.is/rss/innlent", "local": False, "cat": "Fréttamiðlar"},  # (óstaðfest)
    {"name": "RÚV", "url": "https://www.ruv.is/rss/ithrottir", "local": False, "cat": "Fréttamiðlar"},  # (óstaðfest)
    {"name": "RÚV", "url": "https://www.ruv.is/rss/menning-og-daegurmal", "local": False, "cat": "Fréttamiðlar"},  # (óstaðfest)
    # Nýir fréttavefir og SBA (veituslóðir giskaðar, ef þær bila er þeim sleppt)
    {"name": "Trölli.is", "url": "https://trolli.is/feed", "local": True, "cat": "Fréttamiðlar"},
    {"name": "Dal.is", "url": "https://dal.is/feed", "local": True, "cat": "Fréttamiðlar"},
    {"name": "SBA-Norðurleið", "url": "https://www.sba.is/feed", "local": True, "cat": "Fyrirtæki & félög"},
    # Nærsveitarfélög (max 10 svo fundargerðir kaffæri ekki öðru). Dalvíkurbyggð er ekki með veitu; Dal.is fjallar um Dalvík.
    {"name": "Fjallabyggð", "url": "https://www.fjallabyggd.is/is/moya/feed", "local": True, "cat": "Nærsveitir", "max": 10},
    {"name": "Eyjafjarðarsveit", "url": "https://www.esveit.is/feed", "local": True, "cat": "Nærsveitir", "max": 10},
    {"name": "Hörgársveit", "url": "https://www.horgarsveit.is/feed", "local": True, "cat": "Nærsveitir", "max": 10},
    {"name": "Grýtubakkahreppur", "url": "https://www.grenivik.is/feed", "local": True, "cat": "Nærsveitir", "max": 10},
    {"name": "Svalbarðsstrandarhreppur", "url": "https://www.svalbardsstrond.is/feed", "local": True, "cat": "Nærsveitir", "max": 10},
    # Bærinn
    {"name": "Akureyrarbær", "url": "https://www.akureyri.is/feed.xml", "local": True, "cat": "Bærinn"},
    {"name": "Norðurorka", "url": "https://www.no.is/is/feed", "local": True, "cat": "Bærinn"},
    {"name": "Vistorka", "url": "https://www.vistorka.is/is/moya/feed", "local": True, "cat": "Bærinn"},
    # Menntun
    {"name": "Háskólinn á Akureyri", "url": "https://www.unak.is/is/feed", "local": True, "cat": "Menntun"},
    {"name": "Menntaskólinn á Akureyri", "url": "https://www.ma.is/is/feed", "local": True, "cat": "Menntun"},
    {"name": "VMA", "url": "https://www.vma.is/is/feed", "local": True, "cat": "Menntun"},
    # Menning
    {"name": "Menningarfélag Akureyrar", "url": "https://www.mak.is/is/feed", "local": True, "cat": "Menning"},
    {"name": "Listasafnið á Akureyri", "url": "https://www.listak.is/is/feed", "local": True, "cat": "Menning"},
    {"name": "Minjasafnið á Akureyri", "url": "https://www.minjasafnid.is/is/feed", "local": True, "cat": "Menning"},
    {"name": "Visit Akureyri", "url": "https://www.visitakureyri.is/is/feed", "local": True, "cat": "Menning"},
    # Íþróttir og útivist
    {"name": "KA", "url": "https://www.ka.is/is/feed", "local": True, "cat": "Íþróttir"},
    {"name": "Þór", "url": "https://www.thorsport.is/is/feed", "local": True, "cat": "Íþróttir"},
    {"name": "Skautafélag Akureyrar", "url": "https://www.sasport.is/is/feed", "local": True, "cat": "Íþróttir"},
    {"name": "Hlíðarfjall", "url": "https://www.hlidarfjall.is/is/feed", "local": True, "cat": "Íþróttir"},
    # Fyrirtæki og félög
    {"name": "Samherji", "url": "https://www.samherji.is/is/moya/feed", "local": True, "cat": "Fyrirtæki & félög"},
    {"name": "Kjarnafæði Norðlenska", "url": "https://www.kn.is/feed/rss2", "local": True, "cat": "Fyrirtæki & félög"},
    {"name": "Norlandair", "url": "https://www.norlandair.is/is/feed", "local": True, "cat": "Fyrirtæki & félög"},
    {"name": "Glerártorg", "url": "https://www.glerartorg.is/is/feed", "local": True, "cat": "Fyrirtæki & félög"},
    {"name": "Eining-Iðja", "url": "https://www.ein.is/is/feed", "local": True, "cat": "Fyrirtæki & félög", "max": 5},
]
CAT_BY_SOURCE = {f["name"]: f["cat"] for f in FEEDS}
MAX_BY_SOURCE = {f["name"]: f.get("max", 30) for f in FEEDS}

# Stofnar orða (án beygingarendinga) sem sýna að frétt tengist Akureyri.
KEYWORDS = [
    "akureyr", "eyjafj", "eyjafirð", "hlíðarfj", "vaðlaheið", "dalvík", "hrísey",
    "grímsey", "grenivík", "hörgársveit", "fjallabyggð", "siglufj", "ólafsfj",
    "þór/ka", "ka/þór", "norðurorka", "samherj", "kjarnaskóg",
]

class Redirect308(urllib.request.HTTPRedirectHandler):
    def http_error_308(self, req, fp, code, msg, headers):
        return self.http_error_302(req, fp, 302, msg, headers)


OPENER = urllib.request.build_opener(Redirect308)
UA = {"User-Agent": "Mozilla/5.0 (Akureyri-frettir prototype)"}
NS = {
    "content": "http://purl.org/rss/1.0/modules/content/",
    "atom": "http://www.w3.org/2005/Atom",
}
IMG_EXT = re.compile(r"\.(jpe?g|png|webp|gif)(\?|$)", re.I)


def clean(text):
    text = html.unescape(re.sub(r"<[^>]+>", " ", text or ""))
    text = text.replace("\u00ad", "").replace("\u200b", "")  # falin bandstrik (Vísir)
    return re.sub(r"\s+", " ", text).strip()


def short(text):
    t = clean(text)[:300]
    return t if len(t) > 3 else ""  # sleppir útdrætti sem er bara strik


def parse_date(s):
    if not s:
        return None
    try:
        dt = parsedate_to_datetime(s)
    except Exception:
        try:
            dt = datetime.fromisoformat(s.strip().replace("Z", "+00:00"))
        except Exception:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def find_image(item, raw_html):
    for el in item.iter():
        name = el.tag.split("}")[-1] if isinstance(el.tag, str) else ""
        if name not in ("enclosure", "content", "thumbnail", "link"):
            continue
        typ = el.get("type") or ""
        url = el.get("url") or (el.get("href") if typ.startswith("image") else None)
        if url and (typ.startswith("image") or el.get("medium") == "image"
                    or name == "thumbnail" or IMG_EXT.search(url)):
            return url
    m = re.search(r'<img[^>]+src=["\']([^"\']+)', raw_html or "")
    return m.group(1) if m else None


def og_image(url):
    """Til vara: sækir mynd af sjálfri fréttasíðunni (og:image)."""
    try:
        req = urllib.request.Request(url, headers=UA)
        with OPENER.open(req, timeout=10) as r:
            head = r.read(300000).decode("utf-8", "ignore")
    except Exception:
        return None
    for pat in (r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)',
                r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']'):
        m = re.search(pat, head, re.I)
        if m:
            return html.unescape(m.group(1))
    return None


def parse_feed(root):
    items = []
    for it in root.iter("item"):  # RSS
        raw = (it.findtext("content:encoded", namespaces=NS) or "") + (it.findtext("description") or "")
        items.append({
            "title": clean(it.findtext("title")),
            "link": (it.findtext("link") or "").strip(),
            "summary": short(it.findtext("description")),
            "date": parse_date(it.findtext("pubDate")),
            "image": find_image(it, raw),
        })
    for en in root.iter("{%s}entry" % NS["atom"]):  # Atom
        link_el = en.find("atom:link", NS)
        raw = (en.findtext("atom:content", namespaces=NS) or "") + (en.findtext("atom:summary", namespaces=NS) or "")
        items.append({
            "title": clean(en.findtext("atom:title", namespaces=NS)),
            "link": link_el.get("href") if link_el is not None else "",
            "summary": short(en.findtext("atom:summary", namespaces=NS)),
            "date": parse_date(en.findtext("atom:updated", namespaces=NS) or en.findtext("atom:published", namespaces=NS)),
            "image": find_image(en, raw),
        })
    return items


def about_akureyri(item):
    text = (item["title"] + " " + item["summary"]).lower()
    return any(k in text for k in KEYWORDS)


HTML = """<!DOCTYPE html><html lang="is"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Akureyri í fréttum</title><style>
:root{--bg:#f5f7fa;--card:#fff;--tx:#14202b;--mu:#64748b;--ac:#0b6e99;--bd:#e2e8f0}
@media(prefers-color-scheme:dark){:root{--bg:#0e1620;--card:#16212d;--tx:#e8eef4;--mu:#94a3b8;--ac:#5cc0e8;--bd:#25323f}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--tx);font-family:system-ui,sans-serif}
header,main,.chips{max-width:720px;margin:0 auto;padding:0 16px}header{padding-top:20px}h1{margin:0;font-size:24px}.sub{color:var(--mu);font-size:14px}
.chips{display:flex;gap:8px;overflow-x:auto;padding:12px 16px}.chip{border:1px solid var(--bd);background:var(--card);color:var(--tx);padding:7px 14px;border-radius:999px;font-size:14px;white-space:nowrap;cursor:pointer}.chip.on{background:var(--ac);color:#fff;border-color:var(--ac)}
[hidden]{display:none!important}body{padding-bottom:64px}main{display:grid;gap:10px;padding-bottom:40px}.tabbar{position:fixed;bottom:0;left:0;right:0;z-index:5;display:flex;background:var(--card);border-top:1px solid var(--bd);padding-bottom:env(safe-area-inset-bottom,0px)}.tabbar button{flex:1;padding:13px 8px;border:0;background:none;color:var(--mu);font-size:14px;cursor:pointer}.tabbar button.on{color:var(--ac);font-weight:700;box-shadow:inset 0 2px 0 var(--ac)}.evwrap{max-width:720px;margin:0 auto;padding:0 16px 40px}#evlist{display:grid;gap:10px}.evh{margin:14px 0 0;font-size:14px;color:var(--mu);font-weight:600}.tags{margin-top:6px;display:flex;gap:6px;flex-wrap:wrap}.tag{font-size:11px;padding:2px 8px;border-radius:6px;border:1px solid var(--bd);color:var(--mu)}.wrap{max-width:720px;margin:0 auto}.wrap main{max-width:none;margin:0;padding:0 16px 40px}aside{display:none}.strip{max-width:720px;margin:0 auto;padding:0 16px 6px}.strip h3{margin:0 0 6px;font-size:13px;color:var(--mu);font-weight:600}.strip .row{display:flex;gap:8px;overflow-x:auto;padding-bottom:4px}.strip a{flex:0 0 140px;background:var(--card);border:1px solid var(--bd);border-radius:12px;padding:8px 10px;text-decoration:none;color:inherit;font-size:12px;line-height:1.3}.strip b{color:var(--ac);margin-right:4px}.strip small{display:block;color:var(--mu);font-size:11px;margin-top:4px}.strip .t{display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.top{background:var(--card);border:1px solid var(--bd);border-radius:14px;padding:12px 14px;position:sticky;top:12px}.top h3{margin:0 0 8px;font-size:15px}.top ol{margin:0;padding:0;list-style:none;counter-reset:n}.top li{counter-increment:n;border-top:1px solid var(--bd)}.top li:first-child{border-top:0}.top a{display:flex;gap:8px;padding:8px 0;text-decoration:none;color:inherit;font-size:13px;line-height:1.3}.top a:before{content:counter(n);color:var(--ac);font-weight:700;min-width:14px}.top a:hover{color:var(--ac)}.top small{display:block;color:var(--mu);font-size:11px;margin-top:2px}.top .none{color:var(--mu);font-size:12px;margin:0 0 6px}
@media(min-width:900px){body{padding-bottom:0}.evwrap{max-width:1040px}#evlist{max-width:720px}.tabbar{position:static;max-width:1040px;margin:8px auto 0;padding:0 16px;background:none;border:0}.tabbar button{flex:none;padding:10px 18px;border-bottom:2px solid transparent;box-shadow:none}.tabbar button.on{border-bottom-color:var(--ac);box-shadow:none}header,.chips,.wrap{max-width:1040px}.wrap{display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:16px;padding:0 16px}.wrap main{padding:0 0 40px}aside{display:block}.chip.mest{display:none}.strip{display:none}}
a.item{display:flex;gap:12px;background:var(--card);border:1px solid var(--bd);border-radius:14px;padding:10px;text-decoration:none;color:inherit}a.item:hover{border-color:var(--ac)}
.img{flex:0 0 96px;height:96px;border-radius:10px;background:var(--ac);color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:13px;overflow:hidden;text-align:center}.img img{width:100%;height:100%;object-fit:cover}
.body{min-width:0;flex:1}.meta{font-size:12px;color:var(--mu);margin-bottom:4px}.src{color:var(--ac);font-weight:700}
h2{font-size:16px;margin:0 0 4px;line-height:1.3}p{margin:0;font-size:13px;color:var(--mu);display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
</style></head><body><header><h1>Akureyri í fréttum</h1><div class="sub" id="upd"></div></header><nav class="tabbar"><button data-v="news" class="on" onclick="setView('news')">Fréttir</button><button data-v="ev" onclick="setView('ev')">Viðburðir</button></nav><div id="viewNews"><div class="chips" id="chips"></div><div class="strip" id="strip"></div><div class="wrap"><main id="list"></main><aside><div class="top" id="top"></div></aside></div></div><div id="viewEv" hidden><div class="chips" id="evchips"></div><div class="evwrap"><div id="evlist"></div></div></div>
<script>
const NEWS=__DATA__;const EVENTS=__EVENTS__;let evSrc="Allt";const API="__API__";let TOP=[];let cur="Allt";NEWS.forEach(n=>{n.category=n.category||"Fréttamiðlar"});const ORDER=["Fréttamiðlar","Nærsveitir","Bærinn","Menntun","Menning","Íþróttir","Fyrirtæki & félög"];
function ago(d){if(!d)return"";const m=(Date.now()-new Date(d))/6e4;if(m<60)return"fyrir "+Math.max(1,Math.round(m))+" mín.";if(m<1440)return"fyrir "+Math.round(m/60)+" klst.";return"fyrir "+Math.round(m/1440)+" d."}
function track(n){if(!API)return;try{const k="c:"+n.link;if(!localStorage.getItem(k)){localStorage.setItem(k,"1");fetch(API+"/click",{method:"POST",body:n.link,keepalive:true})}}catch(e){}}
function strip(){const t=document.getElementById("strip");t.innerHTML="";if(cur==="Mest lesið")return;let L=TOP.map(k=>NEWS.find(n=>n.link===k)).filter(Boolean).slice(0,5);const real=L.length>0;if(!real)L=NEWS.slice(0,5);t.appendChild(el("h3","",real?"Mest lesið":"Mest lesið (nýjustu í bili)"));const r=el("div","row");L.forEach((n,i)=>{const a=el("a","");a.href=n.link;a.target="_blank";a.rel="noopener";a.onclick=()=>track(n);const x=el("div","t");x.appendChild(el("b","",String(i+1)));x.appendChild(document.createTextNode(n.title));a.appendChild(x);a.appendChild(el("small","",n.source));r.appendChild(a)});t.appendChild(r)}
function side(){const t=document.getElementById("top");t.innerHTML="";t.appendChild(el("h3","","Mest lesið"));let L=TOP.map(k=>NEWS.find(n=>n.link===k)).filter(Boolean).slice(0,5);if(!L.length){L=NEWS.slice(0,5);t.appendChild(el("div","none","Enn fáir smellir – nýjustu fréttir í bili."))}const o=document.createElement("ol");L.forEach(n=>{const li=document.createElement("li");const a=el("a","");a.href=n.link;a.target="_blank";a.rel="noopener";a.onclick=()=>track(n);const d=document.createElement("div");d.appendChild(document.createTextNode(n.title));d.appendChild(el("small","",n.source));a.appendChild(d);li.appendChild(a);o.appendChild(li)});t.appendChild(o)}
function el(t,c,x){const e=document.createElement(t);if(c)e.className=c;if(x)e.textContent=x;return e}
function render(){const names=["Allt","Mest lesið",...ORDER.filter(c=>NEWS.some(n=>n.category===c))];const ch=document.getElementById("chips");ch.innerHTML="";
strip();names.forEach(n=>{const b=el("button","chip"+(n===cur?" on":"")+(n==="Mest lesið"?" mest":""),n);b.onclick=()=>{cur=n;render()};ch.appendChild(b)});
const l=document.getElementById("list");l.innerHTML="";
let LIST=NEWS.filter(n=>cur==="Allt"||n.category===cur);if(cur==="Mest lesið"){LIST=TOP.map(k=>NEWS.find(n=>n.link===k)).filter(Boolean);if(!LIST.length){LIST=NEWS.slice(0,10);l.appendChild(el("div","sub","Enn er ekki nóg af smellum – hér eru nýjustu fréttir á meðan."))}}
LIST.forEach(n=>{const a=el("a","item");a.href=n.link;a.target="_blank";a.rel="noopener";a.onclick=()=>track(n);
const im=el("div","img");if(n.image){const i=document.createElement("img");i.src=n.image;i.loading="lazy";i.referrerPolicy="no-referrer";i.onerror=()=>{i.remove();im.textContent=n.source};im.appendChild(i)}else im.textContent=n.source;
const b=el("div","body");const m=el("div","meta");m.appendChild(el("span","src",n.source));m.appendChild(document.createTextNode(" · "+ago(n.date)));
b.append(m,el("h2","",n.title));if(n.summary&&n.summary.length>3)b.append(el("p","",n.summary));a.append(im,b);l.appendChild(a)})}
function pd(s){const p=s.split("-");return new Date(+p[0],+p[1]-1,+p[2])}
const DAYS=["sun","mán","þri","mið","fim","fös","lau"],MON=["jan","feb","mar","apr","maí","jún","júl","ágú","sep","okt","nóv","des"];
function fd(d){return d.getDate()+". "+MON[d.getMonth()]}
function setView(v){document.getElementById("viewNews").hidden=(v!=="news");document.getElementById("viewEv").hidden=(v!=="ev");document.querySelectorAll(".tabbar button").forEach(b=>b.classList.toggle("on",b.dataset.v===v));if(v==="ev")renderEv();window.scrollTo(0,0)}
function renderEv(){const n0=new Date(),t=new Date(n0.getFullYear(),n0.getMonth(),n0.getDate()),box=document.getElementById("evlist"),ch=document.getElementById("evchips");
const all=EVENTS.filter(e=>pd(e.end)>=t);const srcs=["Allt",...new Set(all.map(e=>e.source))];ch.innerHTML="";
srcs.forEach(s=>{const b=el("button","chip"+(s===evSrc?" on":""),s);b.onclick=()=>{evSrc=s;renderEv()};ch.appendChild(b)});
box.innerHTML="";const L=all.filter(e=>evSrc==="Allt"||e.source===evSrc).sort((a,b)=>a.start<b.start?-1:a.start>b.start?1:((a.time||"")<(b.time||"")?-1:1));
if(!L.length){box.appendChild(el("div","sub","Engir viðburðir fundust."));return}
let last="";L.forEach(e=>{const s=pd(e.start),ongoing=s<t,key=ongoing?"gangi":e.start;
if(key!==last){last=key;let h="Í gangi";if(!ongoing){const diff=Math.round((s-t)/864e5);h=(diff===0?"Í dag · ":diff===1?"Á morgun · ":"")+DAYS[s.getDay()]+". "+fd(s)+(s.getFullYear()!==t.getFullYear()?" "+s.getFullYear():"")}box.appendChild(el("h3","evh",h))}
const a=el("a","item");a.href=e.link;a.target="_blank";a.rel="noopener";
const im=el("div","img");if(e.image){const i=document.createElement("img");i.src=e.image;i.loading="lazy";i.referrerPolicy="no-referrer";i.onerror=()=>{i.remove();im.textContent=fd(s)};im.appendChild(i)}else im.textContent=fd(s);
const b=el("div","body"),m=el("div","meta");m.appendChild(el("span","src",e.source));let when=e.time?"kl. "+e.time:"";if(e.end!==e.start)when+=(when?" · ":"")+fd(s)+" – "+fd(pd(e.end));if(when)m.appendChild(document.createTextNode(" · "+when));
b.append(m,el("h2","",e.title));if(e.note){const tg=el("div","tags");e.note.split(" · ").forEach(x=>tg.appendChild(el("span","tag",x)));b.appendChild(tg)}
a.append(im,b);box.appendChild(a)})}
document.getElementById("upd").textContent="Uppfært __TIME__";render();side();strip();if(API)fetch(API+"/top").then(r=>r.json()).then(t=>{TOP=t;side();strip();if(cur==="Mest lesið")render()}).catch(()=>{});
</script></body></html>"""


COUNTER_URL = "https://akureyri-smellir.hermannh2000.workers.dev"  # slóð á Cloudflare Worker (fyllt út þegar hann er tilbúinn)


def write_html(items, events=None):
    data = json.dumps(items, ensure_ascii=False).replace("</", "<\\/")
    evdata = json.dumps(events or [], ensure_ascii=False).replace("</", "<\\/")
    page = HTML.replace("__EVENTS__", evdata).replace("__DATA__", data).replace("__API__", COUNTER_URL).replace("__TIME__", datetime.now().strftime("%d.%m.%Y %H:%M"))
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(page)


DEEP_UA = {"User-Agent": "AkureyriFrettir/0.1 (+https://github.com/hermannhelgi4/akureyri-frettir)"}
DEEP_KEYWORDS = [k for k in KEYWORDS if k != "samherj"]  # Samherji kemur oft fyrir í fréttum sem eru ekki um Akureyri
DEEP_BUDGET = 120  # mest svo margar fréttasíður sóttar í hverri keyrslu
_robots = {}


def allowed(url):
    """Virðir robots.txt: sækir aðeins síður sem vefurinn leyfir sjálfvirkan aðgang að."""
    u = urlparse(url)
    base = "%s://%s" % (u.scheme, u.netloc)
    rp = _robots.get(base)
    if rp is None:
        rp = urllib.robotparser.RobotFileParser()
        try:
            req = urllib.request.Request(base + "/robots.txt", headers=DEEP_UA)
            with OPENER.open(req, timeout=10) as r:
                rp.parse(r.read().decode("utf-8", "ignore").splitlines())
            rp.modified()
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                rp.disallow_all = True
            else:
                rp.allow_all = True
        except Exception:
            rp.disallow_all = True
        _robots[base] = rp
    return rp.can_fetch("AkureyriFrettir", url)


def deep_check(url):
    """Les málsgreinar fréttarinnar og athugar hvort hún fjallar um Akureyri. Texti er ekki vistaður.
    True/False = niðurstaða, None = tókst ekki (reynt aftur næst)."""
    try:
        req = urllib.request.Request(url, headers=DEEP_UA)
        with OPENER.open(req, timeout=15) as r:
            page = r.read(400000).decode("utf-8", "ignore")
    except Exception:
        return None
    page = re.sub(r"<(nav|aside|footer|header|script|style|noscript)\b.*?</\1>", " ", page, flags=re.S | re.I)
    paras = [clean(p) for p in re.findall(r"<p[^>]*>(.*?)</p>", page, re.S | re.I)]
    paras = [p for p in paras if len(p) > 40]
    if not paras:
        return "ólesanleg"  # engar málsgreinar í HTML (t.d. síða teiknuð með JavaScript)
    lead = " ".join(paras[:3]).lower()
    body = " ".join(paras).lower()
    if any(k in lead for k in DEEP_KEYWORDS):
        return True
    return sum(body.count(k) for k in DEEP_KEYWORDS) >= 2


# ---------------------------------------------------------------------------
# Viðburðir: lesnir beint úr HTML á vefjum sem bjóða ekki upp á veitu.
# Hver vefur fær sinn lesara. Ef lesari finnur ekkert helst fyrri listi og viðvörun birtist í loggnum.
# ---------------------------------------------------------------------------
from html.parser import HTMLParser
from datetime import date, timedelta
from urllib.parse import urljoin

MONTHS_IS = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "maí": 5, "mai": 5, "jún": 6, "jun": 6, "júl": 7, "jul": 7,
             "ágú": 8, "agu": 8, "sep": 9, "okt": 10, "nóv": 11, "nov": 11, "des": 12}
MONTHS_EN = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7, "aug": 8,
             "sep": 9, "oct": 10, "nov": 11, "dec": 12}
_MON = r"(jan|feb|mar|apr|maí|mai|jún|jun|júl|jul|ágú|agu|sep|okt|nóv|nov|des)[a-záéíóúýþæö]*\.?"
RANGE_RE = re.compile(r"(\d{1,2})\.?\s*(?:" + _MON + r")?\s*[-–—]\s*(\d{1,2})\.?\s*" + _MON + r"(?:\s+(20\d\d))?", re.I)
SINGLE_RE = re.compile(r"(\d{1,2})\.\s*" + _MON + r"(?:\s+(20\d\d))?", re.I)
TIME_RE = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b")
BLOCK_TAGS = {"p", "div", "li", "br", "h1", "h2", "h3", "h4", "h5", "tr", "td", "section", "article", "time"}


def _on_or_after(day, mon, today, year=None):
    if year:
        return date(year, mon, day)
    for y in (today.year, today.year + 1):
        try:
            d = date(y, mon, day)
        except ValueError:
            continue
        if d >= today:
            return d
    return None


def parse_dates(text, today):
    """Finnur dagsetningu eða tímabil í texta eins og '9. okt', '9.-10. okt' eða '27. nóv - 4. des'.
    Skilar (upphaf, endir) eða None. Ártal er valið þannig að endirinn sé í dag eða síðar."""
    try:
        m = RANGE_RE.search(text)
        if m:
            d1, mo1, d2, mo2, yr = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
            m2 = MONTHS_IS[mo2.lower()]
            m1 = MONTHS_IS[mo1.lower()] if mo1 else m2
            end = _on_or_after(int(d2), m2, today, int(yr) if yr else None)
            if end is None:
                return None
            start = date(end.year, m1, int(d1))
            if start > end:
                start = date(end.year - 1, m1, int(d1))
            return start, end
        m = SINGLE_RE.search(text)
        if m:
            d = _on_or_after(int(m.group(1)), MONTHS_IS[m.group(2).lower()], today, int(m.group(3)) if m.group(3) else None)
            return (d, d) if d else None
    except (ValueError, KeyError):
        return None
    return None


def strip_dates(text):
    text = RANGE_RE.sub(" ", text)
    text = SINGLE_RE.sub(" ", text)
    text = TIME_RE.sub(" ", text)
    text = re.sub(r"\b(kl|klukkan)\.?\b", " ", text, flags=re.I)
    return re.sub(r"\s+", " ", text).strip(" -–—·|,.:")


class _Flat(HTMLParser):
    """Flatar HTML í runu af (texti | tengill | mynd) til að auðvelt sé að finna tengla og textann í kringum þá."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.t, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("script", "style", "noscript"):
            self.skip += 1
        elif tag == "a":
            self.t.append(("a", a.get("href") or ""))
        elif tag == "img":
            self.t.append(("img", a.get("src") or a.get("data-src") or "", a.get("alt") or ""))
        if tag in BLOCK_TAGS:
            self.t.append(("t", " | "))

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript"):
            self.skip = max(0, self.skip - 1)
        elif tag == "a":
            self.t.append(("/a",))
        if tag in BLOCK_TAGS:
            self.t.append(("t", " | "))

    def handle_data(self, data):
        if not self.skip and data.strip():
            self.t.append(("t", data))


def _txt(tokens):
    return clean(" ".join(x[1] for x in tokens if x[0] == "t")).strip(" |")


def link_groups(page, href_re):
    """Skilar lista yfir tengla sem passa við mynstur: {href, text, imgs, before, after}.
    Sömu tenglar sem koma tvisvar (mynd + titill) eru sameinaðir."""
    p = _Flat()
    p.feed(page)
    toks, found = p.t, []
    i = 0
    while i < len(toks):
        if toks[i][0] == "a" and href_re.search(toks[i][1]):
            j, inside = i + 1, []
            while j < len(toks) and toks[j][0] not in ("/a", "a"):
                inside.append(toks[j])
                j += 1
            found.append({"href": toks[i][1], "i": i, "j": j, "inside": inside})
            i = j
        else:
            i += 1
    groups = []
    for f in found:
        if groups and groups[-1]["href"] == f["href"]:
            g = groups[-1]
            g["inside"] += f["inside"]
            g["j"] = f["j"]
        else:
            groups.append({"href": f["href"], "i": f["i"], "j": f["j"], "inside": list(f["inside"])})
    out = []
    for k, g in enumerate(groups):
        lo = groups[k - 1]["j"] if k else max(0, g["i"] - 40)
        hi = groups[k + 1]["i"] if k + 1 < len(groups) else min(len(toks), g["j"] + 40)
        out.append({
            "href": g["href"],
            "text": _txt(g["inside"]),
            "imgs": [x for x in g["inside"] if x[0] == "img"],
            "before": _txt(toks[max(lo, g["i"] - 40):g["i"]])[-160:],
            "after": _txt(toks[g["j"]:min(hi, g["j"] + 40)])[:160],
        })
    return out


def fetch_page(url):
    if not allowed(url):
        raise RuntimeError("robots.txt bannar aðgang að " + url)
    req = urllib.request.Request(url, headers=DEEP_UA)
    with OPENER.open(req, timeout=20) as r:
        return r.read(2000000).decode("utf-8", "ignore")


READ_MORE_RE = re.compile(r"^(?:lesa\s+meira|lesa\s+nánar|meira|nánar)\b[\s:.\-–—]*|[\s:.\-–—]*\b(?:lesa\s+meira|lesa\s+nánar)\s*$", re.I)


def clean_title(t):
    t = READ_MORE_RE.sub("", t or "")
    t = READ_MORE_RE.sub("", t)
    return t.strip(" -–—·|,.:")


def _first_part(text):
    """Fyrsti hluti texta (aðskilinn með |) sem er ekki bara dagsetning eða tími."""
    for part in text.split("|"):
        p = clean_title(strip_dates(part))
        if len(p) >= 3:
            return p
    return ""


def _slug_title(slug):
    return slug.replace("-", " ").strip().capitalize()


def read_mak(today):
    """Menningarfélag Akureyrar (Hof, Samkomuhúsið o.fl.). Dagsetning án ártals; ártal ályktað."""
    base = "https://www.mak.is/is/vidburdir"
    page = fetch_page(base)
    pat = re.compile(r"/is/vidburdir/[^/?#]+/?$")
    events, nodate = [], 0
    for g in link_groups(page, pat):
        link = urljoin(base, g["href"])
        slug = link.rstrip("/").rsplit("/", 1)[-1]
        d, src = None, ""
        for chunk in (g["text"], g["after"], g["before"]):
            d = parse_dates(chunk, today)
            if d:
                src = chunk
                break
        if not d:
            nodate += 1
            continue
        title = _first_part(g["text"])
        if len(title) < 3 and g["imgs"]:
            title = clean(g["imgs"][0][2])
        if len(title) < 3:
            title = _first_part(g["after"]) or _slug_title(slug)
        tm = TIME_RE.search(src) or TIME_RE.search(g["text"] + " " + g["after"])
        img = urljoin(base, g["imgs"][0][1]) if g["imgs"] and g["imgs"][0][1] else None
        events.append({"title": title[:140], "source": "MAK / Hof", "link": link, "start": d[0].isoformat(),
                       "end": d[1].isoformat(), "time": ("%02d:%s" % (int(tm.group(1)), tm.group(2))) if tm else "",
                       "image": img, "note": ""})
    if nodate:
        print("   VIÐVÖRUN MAK: %d tenglar án dagsetningar voru sleppt" % nodate)
    return events


def read_graeni(today):
    """Græni hatturinn. Dagsetning með ártali er í slóð hvers viðburðar."""
    base = "https://www.graenihatturinn.is/is"
    page = fetch_page(base)
    pat = re.compile(r"/is/[^/?#]+-(\d{2})-([a-z]{3})-(\d{4})/eid/(\d+)", re.I)
    badges = [("SOLD OUT", "Uppselt"), ("FÁIR MIÐAR", "Fáir miðar"), ("NEW EVENT", "Nýtt")]
    events = []
    for g in link_groups(page, pat):
        m = pat.search(g["href"])
        try:
            d = date(int(m.group(3)), MONTHS_EN[m.group(2).lower()], int(m.group(1)))
        except (ValueError, KeyError):
            continue
        link = urljoin(base, g["href"])
        text = g["text"].replace("|", " ")
        notes = []
        for raw, label in badges:
            if raw.lower() in text.lower():
                notes.append(label)
                text = re.sub(re.escape(raw), " ", text, flags=re.I)
        price = re.search(r"(\d{1,3}(?:\.\d{3})*)\s*kr", text, re.I)
        if price:
            notes.append(price.group(1) + " kr.")
        title = re.split(r"Græni hatturinn|Hafnarstræti", text)[0]
        title = re.sub(r"\d{1,2}\s+[A-Za-z]+\s+20\d\d.*$", "", title)
        title = clean(title).strip(" -–—·|,.:")
        if len(title) < 2 and g["imgs"]:
            title = clean(g["imgs"][0][2])
        if len(title) < 2:
            slug = g["href"].rstrip("/").split("/")[-3] if "/eid/" in g["href"] else g["href"]
            title = _slug_title(re.sub(r"-\d{2}-[a-z]{3}-\d{4}$", "", slug))
        img = urljoin(base, g["imgs"][0][1]) if g["imgs"] and g["imgs"][0][1] else None
        events.append({"title": title[:140], "source": "Græni hatturinn", "link": link, "start": d.isoformat(),
                       "end": d.isoformat(), "time": "", "image": img, "note": " · ".join(notes)})
    return events


# --- Upplýsingar af síðu hvers viðburðar (sýningar og tímar) ---
SHOW_RE = re.compile(r"\b(\d{1,2})\s*\.?\s*(jan|feb|mar|apr|maí|mai|jún|jun|júl|jul|ágú|agu|sep|okt|nóv|nov|des)\b\.?"
                     r"(?:\s+([01]?\d|2[0-3]):([0-5]\d))?", re.I)
DETAIL_TTL = 2 * 24 * 3600  # síða hvers viðburðar er sótt aftur í fyrsta lagi á 2ja daga fresti


def page_text(page):
    p = _Flat()
    p.feed(page)
    t = " ".join(x[1] for x in p.t if x[0] == "t")
    return re.sub(r"\s+", " ", re.sub(r"\|", " ", t)).strip()


def mak_showings(page):
    """MAK-síður eru með lista 'Dags Tími' með hverri sýningu, t.d. '09 .okt 20:00 11 .okt 20:00'."""
    t = page_text(page)
    for m in re.finditer(r"\bDags\b(.{0,1800}?)(?:\bVerð\b|Kaupa miða)", t):
        found = [(int(d), MONTHS_IS[mo.lower()], ("%02d:%s" % (int(h), mi)) if h else "")
                 for d, mo, h, mi in SHOW_RE.findall(m.group(1))]
        if found:
            return found
    return []


def showings_to_dates(showings, base):
    """Ártalið er ekki á síðunni: byrjar á ári upphafsdags og hækkar þegar mánuðir hefjast aftur."""
    out, y, prev = [], base.year, None
    for d, mo, tm in showings:
        try:
            dt = date(y, mo, d)
            if prev and dt < prev:
                y += 1
                dt = date(y, mo, d)
            elif not prev and dt < base - timedelta(days=200):
                y += 1
                dt = date(y, mo, d)
        except ValueError:
            continue
        prev = dt
        out.append((dt, tm))
    return out


def _og(page):
    for pat in (r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)',
                r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']'):
        m = re.search(pat, page, re.I)
        if m:
            return html.unescape(m.group(1))
    return ""


def mak_detail(page, e, today):
    sh = showings_to_dates(mak_showings(page), date.fromisoformat(e["start"]))
    return {"showings": [[d.isoformat(), tm] for d, tm in sh], "image": _og(page)}


def graeni_detail(page, e, today):
    m = re.search(r"\b\d{2}\.\d{2}\.20\d\d\s+([01]?\d|2[0-3]):([0-5]\d)\b", page_text(page))
    return {"time": ("%02d:%s" % (int(m.group(1)), m.group(2))) if m else "", "image": _og(page)}


# (nafn, lesari á lista, lesari á síðu viðburðar, bið í sek. milli beiðna, mest margar síður í hverri keyrslu)
EVENT_SOURCES = [
    ("MAK / Hof", read_mak, mak_detail, 5, 15),  # MAK biður um 5 sek. bil (Crawl-delay)
    ("Græni hatturinn", read_graeni, graeni_detail, 1, 25),
]


def _load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def collect_events():
    today = datetime.now(timezone.utc).date()
    old = _load("events.json", [])
    imgs = _load("events_img.json", {})
    det = _load("events_detail.json", {})
    result = []
    for name, reader, detail, wait, cap in EVENT_SOURCES:
        try:
            found = reader(today)
        except Exception as e:
            print("X  Viðburðir %s: tókst ekki að sækja (%s)" % (name, e))
            found = []
        if not found:
            print("VIÐVÖRUN Viðburðir %s: engir viðburðir fundust, held í fyrri lista" % name)
            result += [e for e in old if e.get("source") == name]
            continue
        # Sæki síðu hvers viðburðar (sýningar, tímar, mynd) – fáar í hverri keyrslu, elstu upplýsingar fyrst
        now = time.time()
        todo = [e for e in found if now - det.get(e["link"], {}).get("ts", 0) > DETAIL_TTL]
        todo.sort(key=lambda e: (det.get(e["link"], {}).get("ts", 0), e["start"]))
        fetched = 0
        for e in todo[:cap]:
            try:
                if not allowed(e["link"]):
                    continue
                d = detail(fetch_page(e["link"]), e, today)
                d["ts"] = now
                det[e["link"]] = d
                fetched += 1
            except Exception as ex:
                print("   Tókst ekki að sækja %s (%s)" % (e["link"], ex))
            time.sleep(wait)
        expanded, split = [], 0
        for e in found:
            d = det.get(e["link"], {})
            fut = [s for s in d.get("showings", []) if s[0] >= today.isoformat()]
            if fut:
                split += 1
                for iso, tm in fut:
                    expanded.append(dict(e, start=iso, end=iso, time=tm or e.get("time", "")))
                continue
            if d.get("time") and not e.get("time"):
                e["time"] = d["time"]
            expanded.append(e)
        for e in expanded:
            e["image"] = e.get("image") or det.get(e["link"], {}).get("image") or imgs.get(e["link"]) or None
        print("OK Viðburðir %s: %d viðburðir á lista, %d skiptast í sýningar, %d síður sóttar núna (%d spjöld)" % (
            name, len(found), split, fetched, len(expanded)))
        for e in expanded[:3]:
            print("   dæmi: %s – %s %s" % (e["start"], e["title"][:60], e["time"]))
        result += expanded
    result = [e for e in result if e["end"] >= today.isoformat()]
    seen, uniq = set(), []
    for e in result:
        key = (e["source"], re.sub(r"\W+", "", e["title"].lower()), e["start"], e["end"], e.get("time", ""))
        if key in seen:
            continue
        seen.add(key)
        uniq.append(e)
    result = uniq
    result.sort(key=lambda e: (e["start"], e.get("time") or ""))
    with open("events.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    with open("events_img.json", "w", encoding="utf-8") as f:
        json.dump(dict(list(imgs.items())[-1500:]), f, ensure_ascii=False)
    with open("events_detail.json", "w", encoding="utf-8") as f:
        json.dump(dict(list(det.items())[-1500:]), f, ensure_ascii=False)
    return result


def main():
    try:  # fyrri fréttir eru geymdar svo landsmiðlafréttir um Akureyri hverfi ekki
        with open("news.json", encoding="utf-8") as f:
            old = json.load(f)
    except Exception:
        old = []
    for o in old:
        o.setdefault("category", CAT_BY_SOURCE.get(o.get("source"), "Fréttamiðlar"))
    known = {o["link"]: o.get("image") for o in old}
    by_link = {o["link"]: o for o in old}
    new_count = 0
    try:
        with open("athugad.json", encoding="utf-8") as f:
            checked = json.load(f)
    except Exception:
        checked = {}
    budget = DEEP_BUDGET
    unreadable = 0

    for feed in FEEDS:
        try:
            req = urllib.request.Request(feed["url"], headers=UA)
            with OPENER.open(req, timeout=20) as r:
                items = parse_feed(ET.fromstring(r.read()))
        except Exception as e:
            print("X  %s: tókst ekki að sækja (%s)" % (feed["name"], e))
            continue
        kept, rescued = [], 0
        for i in items:
            if not (i["link"] and i["title"]):
                continue
            if feed["local"] or about_akureyri(i):
                kept.append(i)
                continue
            ok = checked.get(i["link"])
            if ok is None and budget > 0 and allowed(i["link"]):
                budget -= 1
                ok = deep_check(i["link"])
                if ok == "ólesanleg":
                    unreadable += 1
                    ok = False
                if ok is not None:
                    checked[i["link"]] = ok
                time.sleep(0.3)
            if ok:
                kept.append(i)
                rescued += 1
        print("OK %s: %d fréttir sóttar, %d teknar með%s" % (
            feed["name"], len(items), len(kept), (" (þar af %d fundnar með dýpri leit)" % rescued) if rescued else ""))
        for i in kept:
            if not i["image"]:
                i["image"] = known.get(i["link"]) or og_image(i["link"])
            i["source"] = feed["name"]
            i["category"] = feed["cat"]
            i["date"] = i["date"].isoformat() if i["date"] else None
            if i["link"] not in by_link:
                new_count += 1
            by_link[i["link"]] = i
        if not feed["local"]:
            for i in items[:2]:
                print("   dæmi: %s" % i["title"][:80])

    with open("athugad.json", "w", encoding="utf-8") as f:
        json.dump(dict(list(checked.items())[-4000:]), f, ensure_ascii=False)
    print("Dýpri leit: %d síður athugaðar núna, %d í minni. Þar af gátu %d ekki lesist (engin málsgrein í HTML)." % (
        DEEP_BUDGET - budget, len(checked), unreadable))

    merged, per_source = [], {}
    for i in sorted(by_link.values(), key=lambda i: i["date"] or "", reverse=True):
        per_source[i["source"]] = per_source.get(i["source"], 0) + 1
        if per_source[i["source"]] <= MAX_BY_SOURCE.get(i["source"], 30):
            merged.append(i)
    with open("news.json", "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    try:
        events = collect_events()
    except Exception as e:
        print("X  Viðburðir: óvænt villa (%s)" % e)
        try:
            with open("events.json", encoding="utf-8") as f:
                events = json.load(f)
        except Exception:
            events = []
    write_html(merged, events)
    print("Búið. %d fréttir í news.json (%d nýjar). Opnaðu index.html til að sjá þær." % (len(merged), new_count))


if __name__ == "__main__":
    main()
