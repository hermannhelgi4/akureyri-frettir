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
[hidden]{display:none!important}body{padding-bottom:64px}main{display:grid;gap:10px;padding-bottom:40px}.tabbar{position:fixed;bottom:0;left:0;right:0;z-index:5;display:flex;background:var(--card);border-top:1px solid var(--bd);padding-bottom:env(safe-area-inset-bottom,0px)}.tabbar button{flex:1;padding:13px 8px;border:0;background:none;color:var(--mu);font-size:14px;cursor:pointer}.tabbar button.on{color:var(--ac);font-weight:700;box-shadow:inset 0 2px 0 var(--ac)}.evwrap{max-width:720px;margin:0 auto;padding:0 16px 40px}#evlist{display:grid;gap:10px}.evh{margin:14px 0 0;font-size:14px;color:var(--mu);font-weight:600}.tags{margin-top:6px;display:flex;gap:6px;flex-wrap:wrap}.tag.free{border-color:var(--ac);color:var(--ac);font-weight:600}.tag{font-size:11px;padding:2px 8px;border-radius:6px;border:1px solid var(--bd);color:var(--mu)}.wrap{max-width:720px;margin:0 auto}.wrap main{max-width:none;margin:0;padding:0 16px 40px}aside{display:none}.strip{max-width:720px;margin:0 auto;padding:0 16px 6px}.strip h3{margin:0 0 6px;font-size:13px;color:var(--mu);font-weight:600}.strip .row{display:flex;gap:8px;overflow-x:auto;padding-bottom:4px}.strip a{flex:0 0 140px;background:var(--card);border:1px solid var(--bd);border-radius:12px;padding:8px 10px;text-decoration:none;color:inherit;font-size:12px;line-height:1.3}.strip b{color:var(--ac);margin-right:4px}.strip small{display:block;color:var(--mu);font-size:11px;margin-top:4px}.strip .t{display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.top{background:var(--card);border:1px solid var(--bd);border-radius:14px;padding:12px 14px;position:sticky;top:12px}.top h3{margin:0 0 8px;font-size:15px}.top ol{margin:0;padding:0;list-style:none;counter-reset:n}.top li{counter-increment:n;border-top:1px solid var(--bd)}.top li:first-child{border-top:0}.top a{display:flex;gap:8px;padding:8px 0;text-decoration:none;color:inherit;font-size:13px;line-height:1.3}.top a:before{content:counter(n);color:var(--ac);font-weight:700;min-width:14px}.top a:hover{color:var(--ac)}.top small{display:block;color:var(--mu);font-size:11px;margin-top:2px}.top .none{color:var(--mu);font-size:12px;margin:0 0 6px}
@media(min-width:900px){body{padding-bottom:0}.evwrap{max-width:1040px}#evlist{max-width:720px}.tabbar{position:static;max-width:1040px;margin:8px auto 0;padding:0 16px;background:none;border:0}.tabbar button{flex:none;padding:10px 18px;border-bottom:2px solid transparent;box-shadow:none}.tabbar button.on{border-bottom-color:var(--ac);box-shadow:none}header,.chips,.wrap{max-width:1040px}.wrap{display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:16px;padding:0 16px}.wrap main{padding:0 0 40px}aside{display:block}.chip.mest{display:none}.strip{display:none}}
a.item{display:flex;gap:12px;background:var(--card);border:1px solid var(--bd);border-radius:14px;padding:10px;text-decoration:none;color:inherit}a.item:hover{border-color:var(--ac)}
.img{flex:0 0 96px;height:96px;border-radius:10px;background:var(--ac);color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:13px;overflow:hidden;text-align:center}.img img{width:100%;height:100%;object-fit:cover}
.body{min-width:0;flex:1}.meta{font-size:12px;color:var(--mu);margin-bottom:4px}.src{color:var(--ac);font-weight:700}
h2{font-size:16px;margin:0 0 4px;line-height:1.3}p{margin:0;font-size:13px;color:var(--mu);display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
</style></head><body><header><h1>Akureyri í fréttum</h1><div class="sub" id="upd"></div></header><nav class="tabbar"><button data-v="news" class="on" onclick="setView('news')">Fréttir</button><button data-v="ev" onclick="setView('ev')">Viðburðir</button></nav><div id="viewNews"><div class="chips" id="chips"></div><div class="strip" id="strip"></div><div class="wrap"><main id="list"></main><aside><div class="top" id="top"></div></aside></div></div><div id="viewEv" hidden><div class="chips" id="evchips"></div><div class="evwrap"><div id="evlist"></div></div></div>
<script>
const NEWS=__DATA__;const EVENTS=__EVENTS__;let evSrc="Allt",evSport="",evGen="",evRes=false;const API="__API__";let TOP=[];let cur="Allt";NEWS.forEach(n=>{n.category=n.category||"Fréttamiðlar"});const ORDER=["Fréttamiðlar","Nærsveitir","Bærinn","Menntun","Menning","Íþróttir","Fyrirtæki & félög"];
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
const all=EVENTS.filter(e=>e.res||pd(e.end)>=t);const srcs=["Allt",...new Set(all.map(e=>e.source))];ch.innerHTML="";
srcs.forEach(s=>{const b=el("button","chip"+(s===evSrc?" on":""),s);b.onclick=()=>{evSrc=s;renderEv()};ch.appendChild(b)});
let c2=document.getElementById("evchips2");if(!c2){c2=el("div","chips");c2.id="evchips2";ch.after(c2)}c2.innerHTML="";c2.hidden=(evSrc!=="Íþróttir");
if(evSrc==="Íþróttir"){[...new Set(all.filter(e=>e.sport).map(e=>e.sport))].forEach(s=>{const b=el("button","chip"+(s===evSport?" on":""),s);b.onclick=()=>{evSport=(evSport===s?"":s);renderEv()};c2.appendChild(b)});
const rb=el("button","chip"+(evRes?" on":""),"Úrslit");rb.onclick=()=>{evRes=!evRes;renderEv()};c2.appendChild(rb);
["Karlar","Konur"].forEach(s=>{const b=el("button","chip"+(s===evGen?" on":""),s);b.onclick=()=>{evGen=(evGen===s?"":s);renderEv()};c2.appendChild(b)})}
const resMode=(evSrc==="Íþróttir"&&evRes);
box.innerHTML="";const cmp=(a,b)=>a.start<b.start?-1:a.start>b.start?1:((a.time||"")<(b.time||"")?-1:1);
const L=all.filter(e=>(evSrc==="Allt"||e.source===evSrc)&&(evSrc!=="Íþróttir"||((!evSport||e.sport===evSport)&&(!evGen||e.gender===evGen)))&&(resMode?!!e.res:!(e.res&&pd(e.start)<t))).sort(resMode?(a,b)=>cmp(b,a):cmp);
if(!L.length){box.appendChild(el("div","sub",resMode?"Engin úrslit síðustu daga.":"Engir viðburðir fundust."));return}
let last="";L.forEach(e=>{const s=pd(e.start),ongoing=s<t&&!e.res,key=ongoing?"gangi":e.start;
if(key!==last){last=key;let h="Í gangi";if(!ongoing){const diff=Math.round((s-t)/864e5);h=(diff===0?"Í dag · ":diff===1?"Á morgun · ":diff===-1?"Í gær · ":"")+DAYS[s.getDay()]+". "+fd(s)+(s.getFullYear()!==t.getFullYear()?" "+s.getFullYear():"")}box.appendChild(el("h3","evh",h))}
const a=el("a","item");a.href=e.link;a.target="_blank";a.rel="noopener";
const im=el("div","img");if(e.image){const i=document.createElement("img");i.src=e.image;i.loading="lazy";i.referrerPolicy="no-referrer";i.onerror=()=>{i.remove();im.textContent=fd(s)};im.appendChild(i)}else im.textContent=fd(s);
const b=el("div","body"),m=el("div","meta");m.appendChild(el("span","src",e.sport||e.source));let when=e.time?"kl. "+e.time:"";if(e.end!==e.start)when+=(when?" · ":"")+fd(s)+" – "+fd(pd(e.end));if(when)m.appendChild(document.createTextNode(" · "+when));
b.append(m,el("h2","",e.title));if(e.res)b.appendChild(el("p","","Úrslit: "+e.res));if(e.last)b.appendChild(el("p","sub","Síðast: "+e.last));if(e.note){const tg=el("div","tags");e.note.split(" · ").forEach(x=>tg.appendChild(el("span","tag"+(x==="Ókeypis"?" free":""),x)));b.appendChild(tg)}
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
DETAIL_VER = 2  # hækkað þegar lesarinn bætir við upplýsingum, svo gömul gögn séu sótt aftur


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


FREE_RE = re.compile(r"enginn\s+aðgangseyrir|ókeypis|frítt|frír\s+aðgangur|aðgangur\s+frír", re.I)
NUM = r"(\d{1,3}(?:\.\d{3})*)"
PRICE_RE = re.compile(NUM + r"(?:\s*[-–]\s*" + NUM + r")?\s*(?:kr|isk)\b", re.I)


def parse_price(text):
    """Finnur verð í texta síðu: 'Verð: 7.900 kr.', 'Verð frá - 6.900 kr.' eða 'Verð: Enginn aðgangseyrir'."""
    for m in re.finditer(r"\bVerð\b(\s*frá)?\s*[-–:]*\s*(.{0,45})", text, re.I):
        seg, fra = m.group(2), bool(m.group(1))
        if FREE_RE.search(seg):
            return "Ókeypis"
        pm = PRICE_RE.search(seg)
        if pm:
            lo, hi = pm.group(1), pm.group(2)
            if hi:
                return "%s–%s kr." % (lo, hi)
            return ("Frá %s kr." if fra else "%s kr.") % lo
    return ""


def mak_detail(page, e, today):
    sh = showings_to_dates(mak_showings(page), date.fromisoformat(e["start"]))
    return {"showings": [[d.isoformat(), tm] for d, tm in sh], "image": _og(page), "price": parse_price(page_text(page))}


def graeni_detail(page, e, today):
    m = re.search(r"\b\d{2}\.\d{2}\.20\d\d\s+([01]?\d|2[0-3]):([0-5]\d)\b", page_text(page))
    return {"time": ("%02d:%s" % (int(m.group(1)), m.group(2))) if m else "", "image": _og(page),
            "price": parse_price(page_text(page))}


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


# ---------- Íþróttaleikir ----------
# Félögin á Akureyri sem við fylgjumst með (nöfn eins og sambandið skrifar þau)
SPORT_TEAMS = {"KA", "Þór", "KA/Þór", "SA", "Þór Ak.", "Þór/KA"}
SPORT_RESULT_DAYS = 7  # úrslit eru geymd svona marga daga (sjást í Úrslit-hnappnum; leikir dagsins sjást á aðallistanum)

# HSÍ (handbolti): (mót-númer, kyn). Nafn mótsins kemur úr gögnunum sjálfum.
HSI_TOURNAMENTS = [(9142, "Karlar"), (9141, "Konur"), (9140, "Karlar"), (9143, "Konur"), (9295, "Karlar"), (9303, "Konur")]


def fetch_json(url):
    if not allowed(url):
        raise RuntimeError("robots.txt bannar aðgang að " + url)
    last = None
    for attempt in range(3):  # tómt eða bilað svar kemur stundum – reyni aftur
        try:
            req = urllib.request.Request(url, headers=DEEP_UA)
            with OPENER.open(req, timeout=20) as r:
                body = r.read(5000000).decode("utf-8", "ignore")
                status = r.status
            try:
                return json.loads(body)
            except ValueError:
                raise RuntimeError("svar er ekki JSON (staða %s, %d stafir, byrjar á: %r)" % (status, len(body), body[:120]))
        except Exception as e:
            last = e
            time.sleep(3)
    raise last


def read_hsi(today):
    """Handbolti: HSÍ býður upp á opið JSON með öllum leikjum móts."""
    out = []
    for tid, gender in HSI_TOURNAMENTS:
        try:
            data = fetch_json("https://www.hsi.is/api/hsi/tournaments/%d/matches" % tid).get("data", [])
        except Exception as e:
            print("X  HSÍ mót %d: tókst ekki (%s)" % (tid, e))
            continue
        statuses, n = set(), 0
        for g in data:
            home, away = (g.get("HomeTeamName") or "").strip(), (g.get("AwayTeamName") or "").strip()
            statuses.add(g.get("Status", ""))
            if home not in SPORT_TEAMS and away not in SPORT_TEAMS:
                continue
            dt = g.get("GameDayTime") or ""
            if len(dt) < 10:
                continue
            tm = dt[11:16] if len(dt) >= 16 and dt[11:16] != "00:00" else ""
            n += 1
            out.append({"sport": "Handbolti", "gender": gender, "comp": (g.get("TournamentName") or "").strip(),
                        "date": dt[:10], "time": tm, "home": home, "away": away,
                        "rh": (g.get("ResultHomeTeam") or "").strip(), "ra": (g.get("ResultAwayTeam") or "").strip(),
                        "venue": (g.get("StadiumName") or "").strip(),
                        "link": "https://www.hsi.is/tournament/%d" % tid})
        nm = data[0].get("TournamentName") if data else "?"
        print("   HSÍ %s: %d leikir alls, %d hjá Akureyrarliðum, stöður %s" % (nm, len(data), n, sorted(statuses)))
    return out


# Íshokkí: Íshokkísamband Íslands birtir leiki sem töflu á stats.iihf.com (mót 99 = karlar, 100 = konur)
IHI_TOURNAMENTS = [(99, "Karlar", "Toppdeild karla"), (100, "Konur", "Toppdeild kvenna")]
IHI_NAMES = {"SA": "SA", "SR": "SR", "FJO": "Fjölnir"}  # önnur skammstöfun birtist óbreytt
IHI_ROW = re.compile(r"(\d{2})\.(\d{2})\.(\d{4})\s+(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+(\d{2}:\d{2})")
IHI_TEAMS = re.compile(r"\b([A-Z][A-Z0-9]{1,3})\s+-\s+([A-Z][A-Z0-9]{1,3})\b")
IHI_SCORE = re.compile(r"\b(\d{1,2})\s+-\s+(\d{1,2})\b")


def ihi_parse(page, tid, gender, comp, link):
    """Les leikjatöfluna úr HTML síðunni (texti án merkja, hver leikur byrjar á dagsetningu og tíma)."""
    text = re.sub(r"(?is)<(script|style).*?</\1>", " ", page)
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    text = re.sub(r"\s+", " ", text)
    marks = list(IHI_ROW.finditer(text))
    out = []
    for i, mk in enumerate(marks):
        seg = text[mk.end(): marks[i + 1].start() if i + 1 < len(marks) else mk.end() + 300]
        tm = IHI_TEAMS.search(seg)
        if not tm:
            continue
        h, a = IHI_NAMES.get(tm.group(1), tm.group(1)), IHI_NAMES.get(tm.group(2), tm.group(2))
        rh = ra = ""
        if "completed" in seg.lower():
            sc = IHI_SCORE.search(seg[tm.end():])
            if sc:
                rh, ra = sc.group(1), sc.group(2)
        out.append({"sport": "Íshokkí", "gender": gender, "comp": comp,
                    "date": "%s-%s-%s" % (mk.group(3), mk.group(2), mk.group(1)), "time": mk.group(4),
                    "home": h, "away": a, "rh": rh, "ra": ra, "venue": "", "link": link})
    return out


def read_ihi(today):
    out = []
    for tid, gender, comp in IHI_TOURNAMENTS:
        url = "https://stats.iihf.com/ihi/%d/index.html" % tid
        try:
            rows = ihi_parse(fetch_page(url), tid, gender, comp, url)
        except Exception as e:
            print("X  Íshokkí mót %d: tókst ekki (%s)" % (tid, e))
            continue
        mine = [r for r in rows if r["home"] in SPORT_TEAMS or r["away"] in SPORT_TEAMS]
        print("   Íshokkí %s: %d leikir alls, %d hjá SA, lið: %s" % (
            comp, len(rows), len(mine), sorted({r["home"] for r in rows} | {r["away"] for r in rows})))
        out += mine
    return out


# Blak: Blaksamband Íslands (bli-web.dataproject.com). Hver leikur er með auðkennd svæði í HTML.
BLI_BASE = "https://bli-web.dataproject.com/"
# (mót-númer, kyn, nafn, fasa-númer eða None = finn fasana á forsíðu mótsins)
BLI_COMPETITIONS = [(142, "Karlar", "Unbrokendeild karla", 209), (143, "Konur", "Unbrokendeild kvenna", 211),
                    (151, "Karlar", "Bikarkeppni karla", None), (144, "Konur", "Kjörísbikar kvenna", None)]
BLI_DATE = re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{4})\s*-\s*(\d{1,2}):(\d{2})")


def _bli_span(chunk, suffix):
    m = re.search(r'id="[^"]*_%s"[^>]*>([^<]*)<' % suffix, chunk)
    return html.unescape(m.group(1)).strip() if m else ""


def bli_parse(page, gender, comp, link):
    starts = [m.start() for m in re.finditer(r'id="[^"]*_LB_DataOra"', page)]
    out = []
    for i, s in enumerate(starts):
        chunk = page[s: starts[i + 1] if i + 1 < len(starts) else s + 6000]
        d = BLI_DATE.search(_bli_span(chunk, "LB_DataOra"))
        home, away = _bli_span(chunk, "LBL_HomeTeamName"), _bli_span(chunk, "LBL_GuestTeamName")
        if not d or not home or not away:
            continue
        hh, mm = int(d.group(4)), d.group(5)
        out.append({"sport": "Blak", "gender": gender, "comp": comp,
                    "date": "%s-%02d-%02d" % (d.group(3), int(d.group(2)), int(d.group(1))),
                    "time": "" if (hh == 0 and mm == "00") else "%02d:%s" % (hh, mm),
                    "home": home, "away": away,
                    "rh": _bli_span(chunk, "LB_SetCasa"), "ra": _bli_span(chunk, "LB_SetOspiti"),
                    "venue": _bli_span(chunk, "LB_Palasport"), "link": link})
    return out


def read_bli(today):
    out = []
    for cid, gender, comp, pid in BLI_COMPETITIONS:
        try:
            pids = [pid] if pid else sorted({int(x) for x in re.findall(
                r"CompetitionMatches\.aspx\?ID=%d(?:&amp;|&)PID=(\d+)" % cid,
                fetch_page(BLI_BASE + "CompetitionHome.aspx?ID=%d" % cid))})
        except Exception as e:
            print("X  Blak %s: tókst ekki að finna fasa (%s)" % (comp, e))
            continue
        rows = []
        for p in pids:
            url = BLI_BASE + "CompetitionMatches.aspx?ID=%d&PID=%d" % (cid, p)
            try:
                rows += bli_parse(fetch_page(url), gender, comp, url)
            except Exception as e:
                print("X  Blak %s (fasi %d): tókst ekki (%s)" % (comp, p, e))
            time.sleep(1)
        mine = [r for r in rows if r["home"] in SPORT_TEAMS or r["away"] in SPORT_TEAMS]
        print("   Blak %s: fasar %s, %d leikir alls, %d hjá KA" % (comp, pids, len(rows), len(mine)))
        out += mine
    return out


# Körfubolti: mótayfirlit KKÍ sækir leiki úr þjónustu (baskethotel.com). Við biðjum um sömu síðu og KKÍ sjálft gerir.
KKI_API = "a0d07178160bf749eb6e5e761fc623fe42e2bb57"
KKI_STATE = "zJ9uKouyG33qaF8IIQPsd7FgE2CH/uG9vnVV9mJJEDJhOjEyOntzOjE5OiJsZWFndWVfbGlua192aXNpYmxlIjtzOjE6IjEiO3M6MTc6InRlYW1fbGlua192aXNpYmxlIjtzOjE6IjEiO3M6MTc6ImdhbWVfbGlua192aXNpYmxlIjtzOjE6IjEiO3M6MTk6InBsYXllcl9saW5rX3Zpc2libGUiO3M6MToiMSI7czoxNDoiZ2FtZV9saW5rX3R5cGUiO3M6MToiMyI7czoxNzoiZ2FtZV9saW5rX2hhbmRsZXIiO3M6MTI6Im5hdmlnYXRlR2FtZSI7czoxNDoidGVhbV9saW5rX3R5cGUiO3M6MToiMyI7czoxNzoidGVhbV9saW5rX2hhbmRsZXIiO3M6MTI6Im5hdmlnYXRlVGVhbSI7czoxOToiZGF0ZV9yYW5nZV9zZWxlY3RvciI7czoxOiIxIjtzOjIwOiJzdGFnZV9sZXZlbHNfdmlzaWJsZSI7czoxOiIyIjtzOjE3OiJzaG93X2NoYW5uZWxfbG9nbyI7czoxOiIxIjtzOjE3OiJjaGFubmVsX2xvZ29fc2l6ZSI7czo1OiI0MHg0MCI7fQ=="
KKI_CLUB = 1567  # Þór Akureyri
KKI_LEAGUES = [191, 231, 190, 189, 205, 208]  # 1. deild karla/kvenna, Bónus deild karla/kvenna, VÍS bikar karla/kvenna
KKI_LINK = "https://www.kki.is/motamal/leikir-og-urslit/motayfirlit/"
KKI_DATE = re.compile(r"(\d{2})-(\d{2})-(\d{4}) (\d{2}):(\d{2})")


def kki_url(league, page, d_from, d_to):
    return ("https://widgets.baskethotel.com/widget-service/show?&api=%s&lang=is&nnav=1&nav_object=0&hide_full_birth_date=0"
            "&flash=0&request[0][container]=6-510-container&request[0][widget]=510&request[0][part]=schedule_and_results"
            "&request[0][state]=%s&request[0][param][season_id]=&request[0][param][filter][club]=%d"
            "&request[0][param][filter][league]=%d&request[0][param][filter][dateRangeFrom]=%s"
            "&request[0][param][filter][dateRangeTo]=%s&request[0][param][page]=%d"
            % (KKI_API, KKI_STATE, KKI_CLUB, league, d_from, d_to, page))


def kki_parse(raw):
    """Svarið er JavaScript með HTML-töflu innan í streng. Hver leikur er ein röð (tr)."""
    s = re.sub(r"\\[nrt]", " ", raw)
    s = re.sub(r"\\(.)", r"\1", s)
    out = []
    for row in re.split(r"<tr class=", s)[1:]:
        d = KKI_DATE.search(row)
        teams = [html.unescape(x).strip() for x in re.findall(r"team_id=\"\d+\"[^>]*>([^<]*)</a>", row)]
        texts = [html.unescape(x).strip() for x in re.findall(r"<td>([^<]*)</td>", row)]
        if not d or len(teams) < 2 or not texts:
            continue
        sc = re.search(r"(\d+)<span></span>:<span></span>(\d+)", row)
        out.append({"date": "%s-%s-%s" % (d.group(3), d.group(2), d.group(1)),
                    "time": "%s:%s" % (d.group(4), d.group(5)) if d.group(4) + d.group(5) != "0000" else "",
                    "league": texts[0], "venue": texts[1] if len(texts) > 1 else "",
                    "home": teams[0], "away": teams[1],
                    "rh": sc.group(1) if sc else "", "ra": sc.group(2) if sc else ""})
    return out


def kki_fetch(url):
    if not allowed(url):
        raise RuntimeError("robots.txt bannar aðgang að widgets.baskethotel.com")
    req = urllib.request.Request(url, headers=dict(DEEP_UA, Referer="https://www.kki.is/"))
    with OPENER.open(req, timeout=25) as r:
        cs = r.headers.get_content_charset() or "latin-1"
        return r.read(3000000).decode(cs, "replace")


def read_kki(today):
    start_year = today.year if today.month >= 8 else today.year - 1
    d_from, d_to = "%d-08-01" % start_year, "%d-07-31" % (start_year + 1)
    out = []
    for lg in KKI_LEAGUES:
        rows = []
        for page in range(1, 6):
            try:
                got = kki_parse(kki_fetch(kki_url(lg, page, d_from, d_to)))
            except Exception as e:
                print("X  Körfubolti deild %d síða %d: tókst ekki (%s)" % (lg, page, e))
                break
            rows += got
            if len(got) < 20:
                break
            time.sleep(1)
        mine = [r for r in rows if r["home"] in SPORT_TEAMS or r["away"] in SPORT_TEAMS]
        if rows:
            print("   Körfubolti deild %d (%s): %d leikir, %d hjá Þór Ak." % (lg, rows[0]["league"], len(rows), len(mine)))
        for r in mine:
            low = r["league"].lower()
            out.append({"sport": "Körfubolti", "gender": "Konur" if ("kvenna" in low or "konur" in low) else "Karlar",
                        "comp": r["league"], "date": r["date"], "time": r["time"], "home": r["home"], "away": r["away"],
                        "rh": r["rh"], "ra": r["ra"], "venue": r["venue"], "link": KKI_LINK})
        time.sleep(1)
    return out


# Fótbolti: KSÍ. Hvert mót hefur síðu með leikjum sem eftir eru og aðra með úrslitum (bæði birt í HTML).
KSI_BASE = "https://www.ksi.is"
KSI_SEARCH = ["besta", "mj%C3%B3lkurbikar", "lengjudeild", "lengjubikar"]  # Besta, Mjólkurbikar, Lengjudeild, Lengjubikar
KSI_MONTHS = {"janúar": 1, "febrúar": 2, "mars": 3, "apríl": 4, "maí": 5, "júní": 6, "júlí": 7, "ágúst": 8,
              "september": 9, "október": 10, "nóvember": 11, "desember": 12}
KSI_DATE = re.compile(r"(?:Mán|Þri|Mið|Fim|Fös|Lau|Sun)\s+(\d{1,2})\.\s+([a-zæðöáéíóúýþ]+)\s+(\d{2}):(\d{2})")
KSI_SCORE = re.compile(r"^(\d+)\s*-\s*(\d+)$")


def ksi_date(day, month, today):
    """Dagsetningar á KSÍ hafa ekki ártal – vel það ár sem gerir dagsetninguna næsta deginum í dag."""
    best = None
    for y in (today.year - 1, today.year, today.year + 1):
        try:
            d = date(y, month, day)
        except ValueError:
            continue
        if best is None or abs((d - today).days) < abs((best - today).days):
            best = d
    return best


def ksi_parse(page, today, cid):
    marks = [m for m in re.finditer(r"<span[^>]*>\s*((?:Mán|Þri|Mið|Fim|Fös|Lau|Sun)\s+\d{1,2}\.\s+[^<\s]+\s+\d{2}:\d{2})\s*</span>", page)]
    out = []
    for i, mk in enumerate(marks):
        chunk = page[mk.start(): marks[i + 1].start() if i + 1 < len(marks) else mk.start() + 5000]
        dm = KSI_DATE.search(mk.group(1))
        mon = KSI_MONTHS.get(dm.group(2)) if dm else None
        if not mon:
            continue
        txt = re.sub(r"(?is)<(svg|script|style)\b[^>]*/>", " ", chunk)
        txt = re.sub(r"(?is)<(svg|script|style)\b.*?</\1>", " ", txt)
        toks = [html.unescape(t).strip() for t in re.sub(r"<[^>]+>", "\n", txt).split("\n")]
        toks = [re.sub(r"\s+", " ", t) for t in toks if t.strip()]
        j = next((k for k in range(1, min(len(toks), 12)) if KSI_SCORE.match(toks[k]) or toks[k] in ("-", "–")), None)
        if j is None or j < 3 or j + 1 >= len(toks):
            continue
        sc = KSI_SCORE.match(toks[j])
        d = ksi_date(int(dm.group(1)), mon, today)
        gid = re.search(r"leikur\?id=(\d+)", chunk)
        out.append({"date": d.isoformat(), "time": "" if dm.group(3) + dm.group(4) == "0000" else "%s:%s" % (dm.group(3), dm.group(4)),
                    "venue": toks[1] if j - 2 > 1 else "", "comp": toks[j - 2], "home": toks[j - 1], "away": toks[j + 1],
                    "rh": sc.group(1) if sc else "", "ra": sc.group(2) if sc else "",
                    "link": "%s/leikir-og-urslit/felagslid/leikur?id=%s" % (KSI_BASE, gid.group(1)) if gid
                    else "%s/oll-mot/mot/?id=%s&banner-tab=matches-and-results" % (KSI_BASE, cid)})
    return out


def ksi_competitions(today):
    seasons = [today.year] + ([today.year + 1] if today.month >= 10 else [])
    found = {}
    for s in seasons:
        for name in KSI_SEARCH:
            try:
                page = fetch_page("%s/oll-mot/?tab=leit&name=%s&season=%d&pageSize=50" % (KSI_BASE, name, s))
            except Exception as e:
                print("X  KSÍ leit %s %d: tókst ekki (%s)" % (name, s, e))
                continue
            for m in re.finditer(r'href="[^"]*/oll-mot/mot/?\?id=(\d+)[^"]*"[^>]*>(.*?)</a>', page, re.S):
                label = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", m.group(2)))).strip()
                # aðeins deildin sjálf, efri/neðri hluti og úrslitakeppnir – ekki riðlar Lengjubikarsins
                if label and not re.search(r"Rið(i)?ll|deild (A|B|C)\b", label) and "Umspil" not in label:
                    found[m.group(1)] = label
            time.sleep(0.5)
    return found


def read_ksi(today):
    comps = ksi_competitions(today)
    out, seen_teams = [], set()
    for cid, label in comps.items():
        rows = []
        for suffix in ("", "&toggle=results"):
            try:
                rows += ksi_parse(fetch_page("%s/oll-mot/mot/?id=%s&banner-tab=matches-and-results%s" % (KSI_BASE, cid, suffix)), today, cid)
            except Exception as e:
                print("X  KSÍ %s: tókst ekki (%s)" % (label, e))
            time.sleep(0.5)
        mine = [r for r in rows if r["home"] in SPORT_TEAMS or r["away"] in SPORT_TEAMS]
        if mine:
            print("   KSÍ %s: %d leikir alls, %d hjá KA/Þór/Þór/KA" % (label, len(rows), len(mine)))
        for r in mine:
            low = (r["comp"] or label).lower()
            out.append({"sport": "Fótbolti", "gender": "Konur" if "kvenna" in low else "Karlar",
                        "comp": re.sub(r"\s*\b20\d\d\b", "", r["comp"] or label), "date": r["date"], "time": r["time"],
                        "home": r["home"], "away": r["away"], "rh": r["rh"], "ra": r["ra"], "venue": r["venue"], "link": r["link"]})
    print("   KSÍ: %d mót skoðuð" % len(comps))
    return out


SPORT_SOURCES = [("Handbolti", read_hsi), ("Íshokkí", read_ihi), ("Blak", read_bli), ("Körfubolti", read_kki), ("Fótbolti", read_ksi)]


def collect_sports(old, today):
    matches = []
    for name, reader in SPORT_SOURCES:
        try:
            got = reader(today)
        except Exception as e:
            print("X  Íþróttir %s: tókst ekki (%s)" % (name, e))
            got = []
        if not got:
            print("VIÐVÖRUN Íþróttir %s: engir leikir, held í fyrri lista" % name)
            keep = [e for e in old if e.get("sport") == name]
            matches_old = keep
            matches.append(("old", matches_old))
            continue
        matches.append(("new", got))
    t0 = today.isoformat()
    cutoff = (today - timedelta(days=SPORT_RESULT_DAYS)).isoformat()
    events, fresh = [], []
    for kind, lst in matches:
        if kind == "old":
            events += [e for e in lst if e.get("end", "") >= cutoff]
        else:
            fresh += lst

    def played(m):
        return bool(m["rh"] and m["ra"]) and m["date"] <= t0

    def mine(m):
        return m["home"] if m["home"] in SPORT_TEAMS else m["away"]

    groups = {}
    for m in fresh:
        groups.setdefault((m["sport"], m["gender"], mine(m)), []).append(m)
    for key, lst in groups.items():
        lst.sort(key=lambda m: (m["date"], m["time"]))
        done = [m for m in lst if played(m)]
        last = ""
        if done:
            m = done[-1]
            try:
                a, b = int(m["rh"]), int(m["ra"])
                mine_home = m["home"] == key[2]
                diff = (a - b) if mine_home else (b - a)
                word = "sigur" if diff > 0 else ("tap" if diff < 0 else "jafntefli")
            except ValueError:
                word = "úrslit"
            last = "%s, %s %s–%s %s" % (word, m["home"], m["rh"], m["ra"], m["away"])
        first_up = True
        for m in lst:
            home_game = m["home"] in SPORT_TEAMS
            tags = ["Heimaleikur" if home_game else "Útileikur"]
            if m["comp"]:
                tags.append(m["comp"])
            if m["venue"]:
                tags.append(m["venue"])
            e = {"title": "%s – %s" % (m["home"], m["away"]), "source": "Íþróttir", "sport": m["sport"],
                 "gender": m["gender"], "link": m["link"], "start": m["date"], "end": m["date"],
                 "time": m["time"], "image": None, "note": " · ".join(tags)}
            if played(m):
                if m["date"] < cutoff:
                    continue
                e["res"] = "%s–%s" % (m["rh"], m["ra"])
            else:
                if m["date"] < t0:
                    continue  # leikur liðinn en engin úrslit komin
                if first_up and last:
                    e["last"] = last
                first_up = False
            events.append(e)
    # ef heilt mót (íþrótt + kyn) skilaði engu núna (t.d. tímabundin villa) held ég í síðustu þekktu leiki þess
    fresh_groups = {(m["sport"], m["gender"]) for m in fresh}
    for e in old:
        if e.get("sport") and (e["sport"], e.get("gender")) not in fresh_groups and e.get("end", "") >= cutoff:
            events.append(e)
    # sami leikur tveggja Akureyrarliða kemur úr báðum hópum – fjarlægi tvítekningar
    seen, uniq = set(), []
    for e in events:
        k = (e["sport"], e["gender"], e["title"], e["start"])
        if k in seen:
            continue
        seen.add(k)
        uniq.append(e)
    print("OK Íþróttir: %d spjöld (leikir framundan og nýleg úrslit)" % len(uniq))
    return uniq


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
        def _age(e):
            d = det.get(e["link"], {})
            return d.get("ts", 0) if d.get("v") == DETAIL_VER else 0

        todo = [e for e in found if now - _age(e) > DETAIL_TTL]
        todo.sort(key=lambda e: (_age(e), e["start"]))
        fetched = 0
        for e in todo[:cap]:
            try:
                if not allowed(e["link"]):
                    continue
                d = detail(fetch_page(e["link"]), e, today)
                d["ts"] = now
                d["v"] = DETAIL_VER
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
            parts = [x for x in (e.get("note") or "").split(" · ") if x]
            badges = [x for x in parts if "kr" not in x.lower() and x != "Ókeypis"]
            listprice = [x for x in parts if "kr" in x.lower()]
            price = det.get(e["link"], {}).get("price") or (listprice[0] if listprice else "")
            e["note"] = " · ".join(badges + ([price] if price else []))
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
    try:
        result += collect_sports(old, today)
    except Exception as e:
        print("X  Íþróttir: óvænt villa (%s)" % e)
        result += [x for x in old if x.get("sport")]
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
