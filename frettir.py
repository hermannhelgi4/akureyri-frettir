#!/usr/bin/env python3
"""Sækir fréttir úr RSS-veitum, síar landsmiðla eftir Akureyri og býr til news.json."""
import json, re, html, time, urllib.parse, urllib.request, urllib.robotparser, urllib.error
from urllib.parse import urlparse
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
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
MAX_BY_SOURCE["Fótbolti.net"] = 15
MAX_AGE_DAYS = 90  # fréttir eldri en þetta (í dögum) eru ekki sýndar
CAT_BY_SOURCE["Fótbolti.net"] = "Íþróttir"

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
.wx{display:flex;gap:6px;margin:10px 0 2px}.wxc{display:block;flex:1 1 0;max-width:96px;text-decoration:none;color:var(--tx);background:var(--card);border:1px solid var(--bd);border-radius:10px;padding:6px 4px;text-align:center;font-size:12px;line-height:1.3}.wxc.now{border-color:var(--ac)}.wxd{color:var(--mu);font-size:11px;font-weight:600}.wxt{font-size:16px;font-weight:700;white-space:nowrap}.hot{color:#d93025}.cold{color:#1a73e8}.wxw{color:var(--mu);font-size:11px;white-space:nowrap}.wxa{display:inline-block;color:var(--ac)}
[hidden]{display:none!important}body{padding-bottom:64px}main{display:grid;gap:10px;padding-bottom:40px}.tabbar{position:fixed;bottom:0;left:0;right:0;z-index:5;display:flex;background:var(--card);border-top:1px solid var(--bd);padding-bottom:env(safe-area-inset-bottom,0px)}.tabbar button{flex:1;padding:13px 8px;border:0;background:none;color:var(--mu);font-size:14px;cursor:pointer}.tabbar button.on{color:var(--ac);font-weight:700;box-shadow:inset 0 2px 0 var(--ac)}.evwrap{max-width:720px;margin:0 auto;padding:0 16px 40px}#evlist{display:grid;gap:10px}.evh{margin:14px 0 0;font-size:14px;color:var(--mu);font-weight:600}.tags{margin-top:6px;display:flex;gap:6px;flex-wrap:wrap}.tag.free{border-color:var(--ac);color:var(--ac);font-weight:600}.tag{font-size:11px;padding:2px 8px;border-radius:6px;border:1px solid var(--bd);color:var(--mu)}.wrap{max-width:720px;margin:0 auto}.wrap main{max-width:none;margin:0;padding:0 16px 40px}aside{display:none}.strip{max-width:720px;margin:0 auto;padding:0 16px 6px}.strip h3{margin:0 0 6px;font-size:13px;color:var(--mu);font-weight:600}.strip .row{display:flex;gap:8px;overflow-x:auto;padding-bottom:4px}.strip a{flex:0 0 140px;background:var(--card);border:1px solid var(--bd);border-radius:12px;padding:8px 10px;text-decoration:none;color:inherit;font-size:12px;line-height:1.3}.strip b{color:var(--ac);margin-right:4px}.strip small{display:block;color:var(--mu);font-size:11px;margin-top:4px}.strip .t{display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.top{background:var(--card);border:1px solid var(--bd);border-radius:14px;padding:12px 14px;position:sticky;top:12px}.top h3{margin:0 0 8px;font-size:15px}.top ol{margin:0;padding:0;list-style:none;counter-reset:n}.top li{counter-increment:n;border-top:1px solid var(--bd)}.top li:first-child{border-top:0}.top a{display:flex;gap:8px;padding:8px 0;text-decoration:none;color:inherit;font-size:13px;line-height:1.3}.top a:before{content:counter(n);color:var(--ac);font-weight:700;min-width:14px}.top a:hover{color:var(--ac)}.top small{display:block;color:var(--mu);font-size:11px;margin-top:2px}.top .none{color:var(--mu);font-size:12px;margin:0 0 6px}
@media(min-width:900px){body{padding-bottom:0}.evwrap{max-width:1040px}#evlist{max-width:720px}.tabbar{position:static;max-width:1040px;margin:8px auto 0;padding:0 16px;background:none;border:0}.tabbar button{flex:none;padding:10px 18px;border-bottom:2px solid transparent;box-shadow:none}.tabbar button.on{border-bottom-color:var(--ac);box-shadow:none}header,.chips,.wrap{max-width:1040px}.wrap{display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:16px;padding:0 16px}.wrap main{padding:0 0 40px}aside{display:block}.chip.mest{display:none}.strip{display:none}}
a.item{display:flex;gap:12px;background:var(--card);border:1px solid var(--bd);border-radius:14px;padding:10px;text-decoration:none;color:inherit}a.item:hover{border-color:var(--ac)}
.img{flex:0 0 96px;height:96px;border-radius:10px;background:var(--ac);color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:13px;overflow:hidden;text-align:center}.img img{width:100%;height:100%;object-fit:cover}
.body{min-width:0;flex:1}.meta{font-size:12px;color:var(--mu);margin-bottom:4px}.src{color:var(--ac);font-weight:700}
h2{font-size:16px;margin:0 0 4px;line-height:1.3}p{margin:0;font-size:13px;color:var(--mu);display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.ofwrap{max-width:1040px;margin:0 auto;padding:0 16px 40px}#oflist{display:grid;gap:14px;grid-template-columns:1fr}@media(min-width:600px){#oflist{grid-template-columns:1fr 1fr}}@media(min-width:900px){#oflist{grid-template-columns:repeat(3,1fr)}}
.oc{display:block;background:var(--card);border:1px solid var(--bd);border-radius:16px;overflow:hidden;cursor:pointer;text-align:left;padding:0;color:inherit;font:inherit;width:100%}.oc:hover{border-color:var(--ac)}
.oart{position:relative;height:150px;display:flex;align-items:center;justify-content:center;font-size:56px;overflow:hidden;color:#fff}.oart img{position:absolute;left:0;top:0;width:100%;height:100%;object-fit:cover}
.ocat{position:absolute;left:10px;top:10px;z-index:1;background:rgba(0,0,0,.55);color:#fff;font-size:11px;padding:3px 9px;border-radius:999px;font-weight:600}
.obody{padding:12px 14px 14px}.obiz{font-size:12px;color:var(--ac);font-weight:700}.otxt{font-size:18px;font-weight:700;line-height:1.25;margin:3px 0 8px}
.opill{display:inline-block;font-size:11px;padding:3px 9px;border-radius:999px;border:1px solid var(--bd);color:var(--mu)}.opill.ok{background:#16a34a;border-color:#16a34a;color:#fff;font-weight:600}
.omodal{position:fixed;left:0;top:0;right:0;bottom:0;z-index:20;background:rgba(10,15,22,.72);display:flex;align-items:flex-end;justify-content:center}
@media(min-width:600px){.omodal{align-items:center;padding:20px}}
.ocard{background:var(--card);width:100%;max-width:420px;border-radius:22px 22px 0 0;overflow-y:auto;max-height:92vh;position:relative}@media(min-width:600px){.ocard{border-radius:22px}}
.ocard .oart{height:210px;font-size:80px}.ox{position:absolute;right:12px;top:12px;z-index:2;width:36px;height:36px;border-radius:50%;border:0;background:rgba(0,0,0,.55);color:#fff;font-size:20px;cursor:pointer}
.ocb{padding:18px 20px 22px}.ocb .obiz{font-size:14px}.ocb .otxt{font-size:26px;margin:4px 0 12px}
.ostat{border-radius:12px;padding:12px 14px;font-weight:700;font-size:15px;margin-bottom:12px;background:var(--bg);color:var(--mu)}.ostat.ok{background:#16a34a;color:#fff}
.odet{font-size:14px;line-height:1.45;margin:0 0 10px}.orow{font-size:13px;color:var(--mu);margin:4px 0}.oclock{font-size:12px;color:var(--mu);text-align:center;margin-top:14px;border-top:1px dashed var(--bd);padding-top:10px}

.spwrap{max-width:720px;margin:0 auto;padding:0 16px 40px}
.sprow{display:grid;grid-template-columns:54px 1fr auto;gap:10px;align-items:center;background:var(--card);border:1px solid var(--bd);border-radius:12px;padding:10px 12px;margin-top:8px;color:inherit;text-decoration:none}
.sprow .st{font-size:13px;color:var(--mu);font-weight:600;text-align:center;line-height:1.2}
.sprow .tm{font-size:14px;font-weight:700;color:var(--tx)}
.sprow .tt{font-weight:600;font-size:15px;line-height:1.3}
.sprow .sm{font-size:12px;color:var(--mu);margin-top:3px}
.sprow .sc{font-size:18px;font-weight:800;white-space:nowrap}
.sprow .hu{font-size:11px;font-weight:700;padding:3px 8px;border-radius:999px;background:var(--bd);color:var(--mu)}
.sprow .hu.h{background:var(--ac);color:#fff}
.sprow .lastl{font-size:12px;color:var(--mu);margin-top:3px;font-style:italic}
.sptb{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--bd);border-radius:12px;overflow:hidden;font-size:14px;margin-top:8px}
.sptb th{font-size:11px;color:var(--mu);font-weight:700;text-align:right;padding:8px 6px;border-bottom:1px solid var(--bd)}
.sptb td{padding:9px 6px;text-align:right;border-bottom:1px solid var(--bd);white-space:nowrap}
.sptb tr:last-child td{border-bottom:0}
.sptb th:nth-child(2),.sptb td:nth-child(2){text-align:left;width:100%;white-space:normal}
.sptb th:first-child,.sptb td:first-child{text-align:center;color:var(--mu);width:28px}
.sptb tr.me td{background:color-mix(in srgb,var(--ac) 14%,transparent);font-weight:700}
.sptb td.pt{font-weight:800}
.sph{display:flex;justify-content:space-between;align-items:baseline;margin-top:18px;gap:8px}
.sph a{font-size:12px;color:var(--ac);text-decoration:none;white-space:nowrap}
.flwrap{max-width:720px;margin:0 auto;padding:0 16px 40px}
#fllist{display:grid;gap:12px;margin-top:8px}
.fc{background:var(--card);border:1px solid var(--bd);border-radius:16px;padding:14px 16px}
.ftop{display:flex;justify-content:space-between;align-items:flex-start;gap:10px}
.ftop .fr{font-size:20px;font-weight:800;line-height:1.2}.ftop .fo{font-size:13px;color:var(--mu);margin-top:2px}.ftop .fe{font-size:30px;line-height:1}
.fwk{display:grid;grid-template-columns:repeat(7,1fr);gap:5px;margin:12px 0 8px}
.fwk span{text-align:center;padding:8px 0;border-radius:9px;background:var(--bg);font-size:12px;font-weight:700;color:var(--mu);opacity:.7}
.fwk span.on{background:var(--ac);color:#fff;opacity:1}
.fbar{height:8px;border-radius:99px;background:var(--bd);position:relative;margin:4px 0}.fbar i{position:absolute;top:0;bottom:0;border-radius:99px;background:linear-gradient(90deg,#0b6e99,#3aa7d6)}
.fmo{display:flex;justify-content:space-between;font-size:10px;color:var(--mu)}
.fwhen{margin:10px 0 2px;font-weight:700;font-size:15px}.fs{font-size:13px;color:var(--mu);margin-top:4px}
.ffoot{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-top:12px}
.fpill{display:inline-block;white-space:nowrap;font-size:11px;font-weight:700;padding:3px 9px;border-radius:999px;background:var(--bd);color:var(--mu)}
.fpill.w{background:#fde7c4;color:#7a4a00}
.fbtn{display:inline-block;padding:9px 16px;border-radius:10px;background:var(--ac);color:#fff;text-decoration:none;font-weight:700;font-size:14px;white-space:nowrap}
.fc>.fo{font-size:13px;color:var(--mu)}.fc>.fr{font-size:20px;font-weight:800;line-height:1.2;margin:2px 0 4px}.fch{display:flex;gap:6px;margin:10px 0 2px;flex-wrap:wrap}.fnav{display:flex;align-items:center;justify-content:space-between;margin:10px 0 6px}.fnav b{font-size:16px;text-transform:capitalize}.fnav button{width:40px;height:40px;border-radius:10px;border:1px solid var(--bd);background:var(--bg);color:var(--tx);font-size:18px;cursor:pointer}.fnav button:disabled{opacity:.3;cursor:default}
.fgrid{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:4px}.fgrid .h{font-size:11px;color:var(--mu);text-align:center}.fx{aspect-ratio:1;border-radius:9px;background:var(--bg);display:flex;flex-direction:column;align-items:center;justify-content:center;font-size:13px;color:var(--mu);border:2px solid transparent}.fx.f{color:#fff;font-weight:800;cursor:pointer}.fx.past{opacity:.3;cursor:default}.fx.td{border-color:var(--ac)}.fx.sel{border-color:var(--tx)}.fx.cr{border:2px dashed var(--tx)}.fx small{font-size:9px;line-height:1;font-weight:700}
.fleg{display:flex;gap:14px;font-size:12px;color:var(--mu);margin-top:10px;flex-wrap:wrap}.fleg i{display:inline-block;width:12px;height:12px;border-radius:4px;vertical-align:-1px;margin-right:4px}.fdet{margin-top:10px;background:var(--soft,var(--bg));border-radius:12px;padding:10px 12px;font-size:14px}.fdet .fbtn{display:block;text-align:center;margin-top:10px}.fnote{font-size:12px;color:var(--mu);text-align:center;padding:4px 8px}
.tabbar{padding-bottom:calc(env(safe-area-inset-bottom,0px) + 14px)}.tabbar button{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;padding:11px 2px 8px;font-size:11px;font-weight:600}.tabbar svg{width:26px;height:26px;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}.tabbar button.on{font-weight:700}body{padding-bottom:96px}@media(min-width:900px){body{padding-bottom:0}.tabbar{padding-bottom:0}.tabbar button{flex-direction:row;gap:8px;padding:10px 18px;font-size:14px}.tabbar svg{width:20px;height:20px}}
</style></head><body><header><h1>Akureyri í fréttum</h1><div class="sub" id="upd"></div><div class="wx" id="wx"></div></header><nav class="tabbar"><button data-v="news" class="on" onclick="setView('news')"><svg viewBox="0 0 24 24"><path d="M4 5h13v14H6a2 2 0 0 1-2-2z"/><path d="M17 9h3v8a2 2 0 0 1-2 2"/><path d="M7 9h7M7 12h7M7 15h4"/></svg>Fréttir</button><button data-v="ev" onclick="setView('ev')"><svg viewBox="0 0 24 24"><rect x="4" y="5" width="16" height="15" rx="2"/><path d="M4 10h16M8 3v4M16 3v4"/></svg>Viðburðir</button><button data-v="sp" onclick="setView('sp')"><svg viewBox="0 0 24 24"><path d="M8 4h8v5a4 4 0 0 1-8 0zM8 6H5a3 3 0 0 0 3 4M16 6h3a3 3 0 0 1-3 4M12 13v4M8 20h8M10 17h4"/></svg>Íþróttir</button><button data-v="fl" onclick="setView('fl')"><svg viewBox="0 0 24 24"><path d="M17.8 19.2 16 11l3.5-3.5C21 6 21.5 4 21 3c-1-.5-3 0-4.5 1.5L13 8 4.8 6.2c-.5-.1-.9.1-1.1.5l-.3.5c-.2.5-.1 1 .3 1.3L9 12l-2 3H4l-1 1 3 2 2 3 1-1v-3l3-2 3.5 5.3c.3.4.8.5 1.3.3l.5-.2c.4-.3.6-.7.5-1.2z"/></svg>Flug</button><button data-v="of" onclick="setView('of')"><svg viewBox="0 0 24 24"><path d="M3 12V4h8l9 9-8 8z"/><circle cx="7.5" cy="8.5" r="1.2"/></svg>Tilboð</button></nav><div id="viewNews"><div class="chips" id="chips"></div><div class="strip" id="strip"></div><div class="wrap"><main id="list"></main><aside><div class="top" id="top"></div></aside></div></div><div id="viewEv" hidden><div class="chips" id="evchips"></div><div class="evwrap"><div id="evlist"></div></div></div><div id="viewSp" hidden><div class="chips" id="spchips"></div><div class="chips" id="spchips2"></div><div class="spwrap"><div id="splist"></div></div></div><div id="viewFl" hidden><div class="chips" id="flchips"></div><div class="flwrap"><div id="fllist"></div></div></div><div id="viewOf" hidden><div class="chips" id="ofchips"></div><div class="ofwrap"><div id="oflist"></div></div></div>
<script>
const WEATHER=__WEATHER__;
function wxIcon(t,night){t=(t||"").toLowerCase();const h=s=>t.indexOf(s)>=0;if(h("þrum"))return"⛈️";if(h("slydd"))return"🌨️";if(h("snjó")||h("él"))return"❄️";if(h("skúr")||h("rign"))return"🌧️";if(h("súld"))return"🌦️";if(h("þok"))return"🌫️";if(h("heiðskír"))return night?"🌙":"☀️";if(h("léttskýj"))return night?"🌙":"🌤️";if(h("hálfskýj")||h("skýjað með"))return night?"☁️":"⛅";if(h("skýj"))return"☁️";return night?"🌙":"🌡️"}
const WXD={N:0,NNA:22,NA:45,ANA:67,A:90,ASA:112,SA:135,SSA:157,S:180,SSV:202,SV:225,VSV:247,V:270,VNV:292,NV:315,NNV:337};
function wxWind(f,d){if(f===null||f===undefined)return"";const g=WXD[(d||"").toUpperCase()];const a=g===undefined?"":'<span class="wxa" style="transform:rotate('+(g+180)+'deg)">↑</span>';return a+Math.round(f)+" m/s"}
function wxT(v){return'<span class="'+(v>=0?"hot":"cold")+'">'+Math.round(v)+"°</span>"}
function wxLink(d){return"https://www.vedur.is/vedur/spar/stadaspar/nordurland_eystra/#group=15&station=3471"}
function renderWx(){const b=document.getElementById("wx");if(!WEATHER||!WEATHER.now){b.hidden=true;return}const n=WEATHER.now,DN=["Sun","Mán","Þri","Mið","Fim","Fös","Lau"];
let h='<a class="wxc now" target="_blank" rel="noopener" href="'+wxLink("")+'" title="Veðrið núna á Akureyri (mælt kl. '+WEATHER.upd+')"><div class="wxd">Núna</div><div class="wxt">'+wxIcon(n.W,n.night)+" "+(n.T===null?"–":wxT(n.T))+'</div><div class="wxw">'+wxWind(n.F,n.D)+"</div></a>";
WEATHER.days.forEach(d=>{const dt=new Date(d.date+"T12:00:00Z");h+='<a class="wxc" target="_blank" rel="noopener" href="'+wxLink(d.date)+'" title="Spá kl. 12:00"><div class="wxd">'+DN[dt.getUTCDay()]+" "+dt.getUTCDate()+"."+(dt.getUTCMonth()+1)+'</div><div class="wxt">'+wxIcon(d.W,false)+" "+wxT(d.T)+'</div><div class="wxw">'+wxWind(d.F,d.D)+"</div></a>"});
b.innerHTML=h}
const NEWS=__DATA__;const EVENTS=__EVENTS__;const OFFERS=__OFFERS__;const STAND=__STAND__;const FLIGHTS=__FLIGHTS__;let flCat="Allt";let ofCat="Allt",ofTimer=null;let spSport="",spGen="",spMode="fix";let evSrc="Allt",evSport="",evGen="",evRes=false;const API="__API__";let TOP=[];let cur="Allt";const CM={"Fréttamiðlar":"Fréttir","Nærsveitir":"Nærsveitir","Íþróttir":"Íþróttir"};NEWS.forEach(n=>{n.category=n.category||"Fréttamiðlar";n.cats=n.cats||[CM[n.category]||"Bærinn"]});const ORDER=["Fréttir","Bærinn","Nærsveitir","Íþróttir"];
function ago(d){if(!d)return"";const m=(Date.now()-new Date(d))/6e4;if(m<60)return"fyrir "+Math.max(1,Math.round(m))+" mín.";if(m<1440)return"fyrir "+Math.round(m/60)+" klst.";return"fyrir "+Math.round(m/1440)+" d."}
function track(n){if(!API)return;try{const k="c:"+n.link;if(!localStorage.getItem(k)){localStorage.setItem(k,"1");fetch(API+"/click",{method:"POST",body:n.link,keepalive:true})}}catch(e){}}
function strip(){const t=document.getElementById("strip");t.innerHTML="";if(cur==="Mest lesið")return;let L=TOP.map(k=>NEWS.find(n=>n.link===k)).filter(Boolean).slice(0,5);const real=L.length>0;if(!real)L=NEWS.slice(0,5);t.appendChild(el("h3","",real?"Mest lesið":"Mest lesið (nýjustu í bili)"));const r=el("div","row");L.forEach((n,i)=>{const a=el("a","");a.href=n.link;a.target="_blank";a.rel="noopener";a.onclick=()=>track(n);const x=el("div","t");x.appendChild(el("b","",String(i+1)));x.appendChild(document.createTextNode(n.title));a.appendChild(x);a.appendChild(el("small","",n.source));r.appendChild(a)});t.appendChild(r)}
function side(){const t=document.getElementById("top");t.innerHTML="";t.appendChild(el("h3","","Mest lesið"));let L=TOP.map(k=>NEWS.find(n=>n.link===k)).filter(Boolean).slice(0,5);if(!L.length){L=NEWS.slice(0,5);t.appendChild(el("div","none","Enn fáir smellir – nýjustu fréttir í bili."))}const o=document.createElement("ol");L.forEach(n=>{const li=document.createElement("li");const a=el("a","");a.href=n.link;a.target="_blank";a.rel="noopener";a.onclick=()=>track(n);const d=document.createElement("div");d.appendChild(document.createTextNode(n.title));d.appendChild(el("small","",n.source));a.appendChild(d);li.appendChild(a);o.appendChild(li)});t.appendChild(o)}
function el(t,c,x){const e=document.createElement(t);if(c)e.className=c;if(x)e.textContent=x;return e}
function render(){const names=["Allt","Mest lesið",...ORDER.filter(c=>NEWS.some(n=>n.cats.includes(c)))];const ch=document.getElementById("chips");ch.innerHTML="";
strip();names.forEach(n=>{const b=el("button","chip"+(n===cur?" on":"")+(n==="Mest lesið"?" mest":""),n);b.onclick=()=>{cur=n;render()};ch.appendChild(b)});
const l=document.getElementById("list");l.innerHTML="";
let LIST=NEWS.filter(n=>cur==="Allt"||n.cats.includes(cur));if(cur==="Mest lesið"){LIST=TOP.map(k=>NEWS.find(n=>n.link===k)).filter(Boolean);if(!LIST.length){LIST=NEWS.slice(0,10);l.appendChild(el("div","sub","Enn er ekki nóg af smellum – hér eru nýjustu fréttir á meðan."))}}
LIST.forEach(n=>{const a=el("a","item");a.href=n.link;a.target="_blank";a.rel="noopener";a.onclick=()=>track(n);
const im=el("div","img");if(n.image){const i=document.createElement("img");i.src=n.image;i.loading="lazy";i.referrerPolicy="no-referrer";i.onerror=()=>{i.remove();im.textContent=n.source};im.appendChild(i)}else im.textContent=n.source;
const b=el("div","body");const m=el("div","meta");m.appendChild(el("span","src",n.source));m.appendChild(document.createTextNode(" · "+ago(n.date)));
b.append(m,el("h2","",n.title));if(n.summary&&n.summary.length>3)b.append(el("p","",n.summary));a.append(im,b);l.appendChild(a)})}
function pd(s){const p=s.split("-");return new Date(+p[0],+p[1]-1,+p[2])}
const DAYS=["sun","mán","þri","mið","fim","fös","lau"],MON=["jan","feb","mar","apr","maí","jún","júl","ágú","sep","okt","nóv","des"];
function fd(d){return d.getDate()+". "+MON[d.getMonth()]}
function setView(v){closeCard();document.getElementById("viewNews").hidden=(v!=="news");document.getElementById("viewEv").hidden=(v!=="ev");document.getElementById("viewOf").hidden=(v!=="of");document.getElementById("viewSp").hidden=(v!=="sp");document.getElementById("viewFl").hidden=(v!=="fl");document.querySelectorAll(".tabbar button").forEach(b=>b.classList.toggle("on",b.dataset.v===v));if(v==="ev")renderEv();if(v==="of")renderOf();if(v==="sp")renderSp();if(v==="fl")renderFl();window.scrollTo(0,0)}
const CATS={"Kaffi":["#7a4b2a","#d9a066","☕"],"Matur":["#b4452f","#f0a35c","🍽️"],"Afþreying":["#4b3fa8","#8f7bf0","🎟️"],"Þjónusta":["#0f766e","#5eead4","✂️"],"Verslun":["#be185d","#f9a8d4","🛍️"],"Heilsa":["#166534","#86efac","💪"]};
const LONGD=["sunnudagur","mánudagur","þriðjudagur","miðvikudagur","fimmtudagur","föstudagur","laugardagur"],LONG={"sun":"sunnudaga","mán":"mánudaga","þri":"þriðjudaga","mið":"miðvikudaga","fim":"fimmtudaga","fös":"föstudaga","lau":"laugardaga"};
function art(o,cls){const c=CATS[o.category]||["#0b6e99","#5cc0e8","⭐"],d=el("div",cls);d.style.background="linear-gradient(135deg,"+c[0]+","+c[1]+")";d.appendChild(document.createTextNode(c[2]));if(o.image){const i=document.createElement("img");i.src=o.image;i.alt=o.business;i.loading="lazy";i.referrerPolicy="no-referrer";i.onerror=()=>i.remove();d.appendChild(i)}return d}
function ofState(o,t){const iso=t.getFullYear()+"-"+String(t.getMonth()+1).padStart(2,"0")+"-"+String(t.getDate()).padStart(2,"0");if(o.until&&o.until<iso)return"expired";if(o.from&&o.from>iso)return"later";if(o.days&&o.days.length&&!o.days.includes(DAYS[t.getDay()]))return"notday";return"ok"}
function daysText(o){return(o.days&&o.days.length)?"Gildir "+o.days.map(d=>LONG[d]||d).join(", "):"Gildir alla daga"}
function today0(){const n=new Date();return new Date(n.getFullYear(),n.getMonth(),n.getDate())}
function renderOf(){const t=today0(),box=document.getElementById("oflist"),ch=document.getElementById("ofchips");const all=OFFERS.filter(o=>ofState(o,t)!=="expired");
const cats=["Allt",...new Set(all.map(o=>o.category||"Annað"))];ch.innerHTML="";cats.forEach(c=>{const b=el("button","chip"+(c===ofCat?" on":""),c);b.onclick=()=>{ofCat=c;renderOf()};ch.appendChild(b)});
box.innerHTML="";const rank=o=>ofState(o,t)==="ok"?0:1;const L=all.filter(o=>ofCat==="Allt"||(o.category||"Annað")===ofCat).sort((a,b)=>rank(a)-rank(b)||a.business.localeCompare(b.business,"is"));
if(!L.length){box.appendChild(el("div","sub","Engin tilboð í þessum flokki."));return}
L.forEach(o=>{const st=ofState(o,t),c=el("button","oc");c.onclick=()=>openCard(o);const a=art(o,"oart");a.appendChild(el("span","ocat",o.category||"Annað"));
const b=el("div","obody");b.appendChild(el("div","obiz",o.business));b.appendChild(el("div","otxt",o.offer));
b.appendChild(el("span","opill"+(st==="ok"?" ok":""),st==="ok"?"Gildir í dag":st==="later"?"Hefst "+fd(pd(o.from)):daysText(o)));c.append(a,b);box.appendChild(c)})}
function closeCard(){const m=document.getElementById("ofmodal");if(m)m.remove();if(ofTimer){clearInterval(ofTimer);ofTimer=null}document.body.style.overflow=""}
function openCard(o){closeCard();const t=today0(),st=ofState(o,t);const m=el("div","omodal");m.id="ofmodal";m.onclick=e=>{if(e.target===m)closeCard()};
const c=el("div","ocard"),a=art(o,"oart"),x=el("button","ox","×");x.onclick=closeCard;x.setAttribute("aria-label","Loka");a.appendChild(x);
const b=el("div","ocb");b.appendChild(el("div","obiz",o.business));b.appendChild(el("div","otxt",o.offer));
b.appendChild(el("div","ostat"+(st==="ok"?" ok":""),st==="ok"?"✔ Gildir í dag":st==="later"?"Hefst "+fd(pd(o.from)):"Gildir ekki í dag – "+daysText(o).toLowerCase()));
if(o.details)b.appendChild(el("div","odet",o.details));b.appendChild(el("div","orow",daysText(o)));if(o.until)b.appendChild(el("div","orow","Gildir til og með "+fd(pd(o.until))));if(o.address)b.appendChild(el("div","orow","📍 "+o.address));
const ck=el("div","oclock");b.appendChild(ck);const tick=()=>{const n=new Date(),p=v=>String(v).padStart(2,"0");ck.textContent="Sýndu starfsmanni þetta kort · "+LONGD[n.getDay()]+" "+fd(n)+" kl. "+p(n.getHours())+":"+p(n.getMinutes())+":"+p(n.getSeconds())};tick();ofTimer=setInterval(tick,1000);
c.append(a,b);m.appendChild(c);document.body.appendChild(m);document.body.style.overflow="hidden"}
document.addEventListener("keydown",e=>{if(e.key==="Escape")closeCard()});
function renderEv(){const n0=new Date(),t=new Date(n0.getFullYear(),n0.getMonth(),n0.getDate()),box=document.getElementById("evlist"),ch=document.getElementById("evchips");
const KO=["Tónlist","Leiklist","Uppistand","Sýningar","Fjölskylda","Fræðsla","Íþróttir"];const all=EVENTS.filter(e=>e.source!=="Íþróttir"&&(e.res||pd(e.end)>=t));const srcs=["Allt",...KO.filter(k=>all.some(e=>e.kind===k))];ch.innerHTML="";
srcs.forEach(s=>{const b=el("button","chip"+(s===evSrc?" on":""),s);b.onclick=()=>{evSrc=s;renderEv()};ch.appendChild(b)});
const resMode=false;
box.innerHTML="";const cmp=(a,b)=>a.start<b.start?-1:a.start>b.start?1:((a.time||"")<(b.time||"")?-1:1);
const L=all.filter(e=>(evSrc==="Allt"||e.kind===evSrc)&&(resMode?!!e.res:!(e.res&&pd(e.start)<t))).sort(resMode?(a,b)=>cmp(b,a):cmp);
if(!L.length){box.appendChild(el("div","sub",resMode?"Engin úrslit síðustu daga.":"Engir viðburðir fundust."));return}
let last="";L.forEach(e=>{const s=pd(e.start),ongoing=s<t&&!e.res,key=ongoing?"gangi":e.start;
if(key!==last){last=key;let h="Í gangi";if(!ongoing){const diff=Math.round((s-t)/864e5);h=(diff===0?"Í dag · ":diff===1?"Á morgun · ":diff===-1?"Í gær · ":"")+DAYS[s.getDay()]+". "+fd(s)+(s.getFullYear()!==t.getFullYear()?" "+s.getFullYear():"")}box.appendChild(el("h3","evh",h))}
const a=el("a","item");a.href=e.link;a.target="_blank";a.rel="noopener";
const im=el("div","img");if(e.image){const i=document.createElement("img");i.src=e.image;i.loading="lazy";i.referrerPolicy="no-referrer";i.onerror=()=>{i.remove();im.textContent=fd(s)};im.appendChild(i)}else im.textContent=fd(s);
const b=el("div","body"),m=el("div","meta");m.appendChild(el("span","src",e.venue||e.sport||e.source));let when=e.time?"kl. "+e.time:"";if(e.end!==e.start)when+=(when?" · ":"")+fd(s)+" – "+fd(pd(e.end));if(when)m.appendChild(document.createTextNode(" · "+when));
b.append(m,el("h2","",e.title));if(e.res)b.appendChild(el("p","","Úrslit: "+e.res));if(e.note){const tg=el("div","tags");e.note.split(" · ").forEach(x=>tg.appendChild(el("span","tag"+(x==="Ókeypis"?" free":""),x)));b.appendChild(tg)}
a.append(im,b);box.appendChild(a)})}
function renderTab(box){const G=STAND.filter(g=>(!spSport||g.sport===spSport)&&(!spGen||g.gender===spGen));
if(!G.length){box.appendChild(el("div","sub","Engar töflur fundust."));return}
const SO=["Handbolti","Fótbolti","Körfubolti","Blak","Íshokkí"];G.sort((a,b)=>SO.indexOf(a.sport)-SO.indexOf(b.sport)||(a.gender<b.gender?-1:a.gender>b.gender?1:0));
G.forEach(g=>{const h=el("div","sph"),t=el("h3","evh",g.sport+" · "+g.gender+" · "+g.comp);t.style.margin="0";const a=el("a","","Nánar ›");a.href=g.link;a.target="_blank";a.rel="noopener";h.append(t,a);box.appendChild(h);
const anyD=g.rows.some(r=>r.d>0),anyG=g.rows.some(r=>r.g),cols=["#","Lið","L","U"].concat(anyD?["J"]:[]).concat(["T"]).concat(anyG?["Mörk"]:[]).concat(["Stig"]);
const tb=el("table","sptb"),hr=el("tr");cols.forEach(c=>hr.appendChild(el("th","",c)));tb.appendChild(hr);
g.rows.forEach(r=>{const tr=el("tr",r.me?"me":"");const v=[r.n,r.t,r.p,r.w].concat(anyD?[r.d]:[]).concat([r.l]).concat(anyG?[r.g]:[]).concat([r.pts]);v.forEach((x,i)=>{const td=el("td",i===v.length-1?"pt":"",String(x));tr.appendChild(td)});tb.appendChild(tr)});box.appendChild(tb)})}
const FLD={"mán":"mánudögum","þri":"þriðjudögum","mið":"miðvikudögum","fim":"fimmtudögum","fös":"föstudögum","lau":"laugardögum","sun":"sunnudögum"},FLO=["mán","þri","mið","fim","fös","lau","sun"];
function flDays(a){const d=FLO.filter(x=>(a||[]).includes(x)).map(x=>FLD[x]);return d.length?"Flogið á "+(d.length>1?d.slice(0,-1).join(", ")+" og "+d[d.length-1]:d[0]):""}
const FLN={"sun":0,"mán":1,"þri":2,"mið":3,"fim":4,"fös":5,"lau":6},FLCOL=["#0b6e99","#e8730c","#7c3aed","#0f766e"],FLMF=["janúar","febrúar","mars","apríl","maí","júní","júlí","ágúst","september","október","nóvember","desember"];
let flF="",flOut=null,flRet=null,flVm=null;
function flKey(d){return d.getFullYear()+"-"+d.getMonth()+"-"+d.getDate()}
function flIso(d){return d.getFullYear()+"-"+String(d.getMonth()+1).padStart(2,"0")+"-"+String(d.getDate()).padStart(2,"0")}
function flOn(f,d){return f.days.some(x=>FLN[x]===d.getDay())&&d>=pd(f.from)&&d<=pd(f.until)}
function flNext(W,t0){let d=new Date(t0);for(let i=0;i<500;i++){if(W.some(f=>flOn(f,d)))return d;d=new Date(d.getFullYear(),d.getMonth(),d.getDate()+1)}return null}
function flRange(f){const s=pd(f.start),e=pd(f.end),y=e.getFullYear();if(s.getFullYear()===y&&s.getMonth()===e.getMonth())return s.getDate()+"."+"–"+e.getDate()+". "+MON[e.getMonth()]+" "+y;return fd(s)+(s.getFullYear()!==y?" "+s.getFullYear():"")+" – "+fd(e)+" "+y}
function flSrc(f){return f.link&&f.link.indexOf("//")>0?f.link.split("//")[1].split("/")[0].replace("www.",""):""}
function flBtn(f,href,txt){const a=el("a","fbtn",txt);a.href=href;a.target="_blank";a.rel="noopener";return a}
function flTrip(f,t0){const c=el("div","fc"),top=el("div","ftop"),tt=el("div","");tt.appendChild(el("div","fr","Akureyri → "+f.to));tt.appendChild(el("div","fo",f.operator+" · leiguflug"));top.append(tt,el("div","fe",f.flag||"✈️"));c.appendChild(top);
c.appendChild(el("div","fwhen",flRange(f)));const dd=Math.round((pd(f.start)-t0)/864e5);c.appendChild(el("span","fpill"+(dd>0&&dd<=14?" w":""),dd>1?"Eftir "+dd+" daga":dd===1?"Á morgun":dd===0?"Í dag":"Ferðin er hafin"));
if(f.times)c.appendChild(el("div","fs","🕐 "+f.times));if(f.price)c.appendChild(el("div","fwhen",f.price));if(f.note)c.appendChild(el("div","fs",f.note));
const ft=el("div","ffoot");ft.appendChild(el("span","fs",flSrc(f)?"Heimild: "+flSrc(f):""));if(f.link)ft.appendChild(flBtn(f,f.link,f.linkText||"Skoða ›"));c.appendChild(ft);return c}
function flCal(W,t0){const c=el("div","fc"),sel=W.filter(f=>!flF||f.short===flF);if(!flVm)flVm=new Date(t0.getFullYear(),t0.getMonth(),1);
const last=W.reduce((m,f)=>pd(f.until)>m?pd(f.until):m,t0),lastM=new Date(last.getFullYear(),last.getMonth(),1),firstM=new Date(t0.getFullYear(),t0.getMonth(),1);
const nx=flNext(sel.length?sel:W,t0),ops=[...new Set(W.map(f=>f.operator))].join(", ");
c.appendChild(el("div","fo",ops+" · áætlunarflug"));c.appendChild(el("div","fr","Akureyri → "+W.map(f=>f.short||f.to).join(" og ")));
const nl=el("div","fs");if(nx){const fl=W.filter(f=>flOn(f,nx));nl.innerHTML="Næsta flug: <b>"+DAYS[nx.getDay()]+" "+fd(nx)+"</b> · "+fl.map(f=>f.short||f.to).join(" + ")}else nl.textContent="Engin flug framundan";c.appendChild(nl);
if(W.length>1){const ch=el("div","fch");["Allt",...W.map(f=>f.short||f.to)].forEach(x=>{const on=(x==="Allt"?!flF:x===flF),b=el("button","chip"+(on?" on":""),x);b.onclick=()=>{flF=(x==="Allt"?"":x);flOut=null;flRet=null;renderFl()};ch.appendChild(b)});c.appendChild(ch)}
const nav=el("div","fnav"),pv=el("button","",""),nm=el("button","","");pv.textContent="‹";nm.textContent="›";pv.disabled=flVm<=firstM;nm.disabled=flVm>=lastM;
pv.onclick=()=>{flVm=new Date(flVm.getFullYear(),flVm.getMonth()-1,1);renderFl()};nm.onclick=()=>{flVm=new Date(flVm.getFullYear(),flVm.getMonth()+1,1);renderFl()};
nav.append(pv,el("b","",FLMF[flVm.getMonth()]+" "+flVm.getFullYear()),nm);c.appendChild(nav);
const g=el("div","fgrid");FLO.forEach(x=>g.appendChild(el("div","h",x)));
const y=flVm.getFullYear(),m=flVm.getMonth(),st=(new Date(y,m,1).getDay()+6)%7,n=new Date(y,m+1,0).getDate();for(let i=0;i<st;i++)g.appendChild(el("div","",""));
for(let d=1;d<=n;d++){const dt=new Date(y,m,d),fl=sel.filter(f=>flOn(f,dt)),past=dt<t0,x=el("div","fx");
const isO=flOut&&flKey(flOut.d)===flKey(dt),isR=flRet&&flKey(flRet)===flKey(dt);
if(fl.length){x.classList.add("f");x.style.background=FLCOL[W.indexOf(fl[0])%FLCOL.length]}if(past)x.classList.add("past");if(flKey(dt)===flKey(t0))x.classList.add("td");if(isO||isR)x.classList.add("sel");
if(flOut&&!flRet&&dt>flOut.d&&flOn(flOut.f,dt))x.classList.add("cr");
if(isO)x.appendChild(el("small","","út"));else if(isR)x.appendChild(el("small","","heim"));x.appendChild(document.createTextNode(String(d)));
x.onclick=()=>{if(past)return;if(flOut&&flKey(flOut.d)===flKey(dt)){flOut=null;flRet=null}else if(fl.length&&(!flOut||flRet||dt<flOut.d||fl[0]!==flOut.f)){flOut={d:dt,f:fl[0]};flRet=null}else if(flOut&&!flRet&&dt>flOut.d&&flOn(flOut.f,dt)){flRet=dt}renderFl()};g.appendChild(x)}
c.appendChild(g);
const lg=el("div","fleg");W.forEach(f=>{const s=el("span","","");const i=el("i","");i.style.background=FLCOL[W.indexOf(f)%FLCOL.length];s.append(i,f.short||f.to);lg.appendChild(s)});c.appendChild(lg);
const dt=el("div","fdet");
if(flOut){const f=flOut.f;dt.innerHTML="<b>Út:</b> "+DAYS[flOut.d.getDay()]+" "+fd(flOut.d)+" · Akureyri → "+(f.short||f.to)+(flRet?"<br><b>Heim:</b> "+DAYS[flRet.getDay()]+" "+fd(flRet):"<br><span class=fs>Veldu heimferðardag á dagatalinu (merktir með brotalínu), eða bókaðu aðra leið.</span>");
const href=(flRet?f.bookRT:f.bookOW)||f.link;if(href)dt.appendChild(flBtn(f,href.replace("{dd}",flIso(flOut.d)).replace("{rd}",flRet?flIso(flRet):""),flRet?"Bóka fram og til baka á "+f.operator+" ›":"Bóka aðra leið á "+f.operator+" ›"));
dt.appendChild(el("div","fs","Tímar og verð sjást hjá "+f.operator+", og þar er hægt að breyta dögum."+(f.note?" "+f.note:"")))}
else dt.textContent="Smelltu á litaðan dag til að skoða flug og bóka.";c.appendChild(dt);return c}
function renderFl(){const n0=new Date(),t0=new Date(n0.getFullYear(),n0.getMonth(),n0.getDate()),box=document.getElementById("fllist");document.getElementById("flchips").innerHTML="";box.innerHTML="";
const W=FLIGHTS.filter(f=>f.kind==="weekly"&&pd(f.until)>=t0),blocks=[];
if(W.length){const nx=flNext(W,t0);blocks.push({d:nx||new Date(9999,0,1),n:flCal(W,t0)})}
FLIGHTS.filter(f=>f.kind!=="weekly").forEach(f=>{const e=pd(f.end);if(e<t0)return;const s=pd(f.start);blocks.push({d:s<t0?t0:s,n:flTrip(f,t0)})});
if(!blocks.length){box.appendChild(el("div","sub","Engin flug skráð."));return}
blocks.sort((a,b)=>a.d-b.d);blocks.forEach(b=>box.appendChild(b.n));
box.appendChild(el("div","fnote","Upplýsingar eru skráðar eftir heimasíðum flugfélaga og ferðaskrifstofa og geta breyst. Staðfestu alltaf tíma og verð við bókun."))}
function renderSp(){const n0=new Date(),t=new Date(n0.getFullYear(),n0.getMonth(),n0.getDate()),box=document.getElementById("splist"),c1=document.getElementById("spchips"),c2=document.getElementById("spchips2");
const all=EVENTS.filter(e=>e.source==="Íþróttir");c1.innerHTML="";c2.innerHTML="";
const sp=["Allt",...new Set(all.map(e=>e.sport))];sp.forEach(x=>{const b=el("button","chip"+((x==="Allt"?!spSport:x===spSport)?" on":""),x);b.onclick=()=>{spSport=(x==="Allt"?"":x);renderSp()};c1.appendChild(b)});
[["Næstu leikir","fix"],["Úrslit","res"],["Tafla","tab"]].forEach(a=>{const b=el("button","chip"+(spMode===a[1]?" on":""),a[0]);b.onclick=()=>{spMode=a[1];renderSp()};c2.appendChild(b)});
["Karlar","Konur"].forEach(x=>{const b=el("button","chip"+(x===spGen?" on":""),x);b.onclick=()=>{spGen=(spGen===x?"":x);renderSp()};c2.appendChild(b)});
const cmp=(a,b)=>a.start<b.start?-1:a.start>b.start?1:((a.time||"")<(b.time||"")?-1:1);
const spRes=(spMode==="res");box.innerHTML="";if(spMode==="tab"){renderTab(box);return}
const L=all.filter(e=>(!spSport||e.sport===spSport)&&(!spGen||e.gender===spGen)&&(spRes?!!e.res:!(e.res&&pd(e.start)<t))).sort(spRes?(a,b)=>cmp(b,a):cmp);
if(!L.length){box.appendChild(el("div","sub",spRes?"Engin úrslit síðustu daga.":"Engir leikir fundust."));return}
let last="";L.forEach(e=>{const s=pd(e.start);
if(e.start!==last){last=e.start;const diff=Math.round((s-t)/864e5);box.appendChild(el("h3","evh",(diff===0?"Í dag · ":diff===1?"Á morgun · ":diff===-1?"Í gær · ":"")+DAYS[s.getDay()]+". "+fd(s)+(s.getFullYear()!==t.getFullYear()?" "+s.getFullYear():"")))}
const a=el("a","sprow");a.href=e.link;a.target="_blank";a.rel="noopener";
a.appendChild(el("div","st",e.res?"Lokið":(e.time||"–")));
const mid=el("div","");mid.appendChild(el("div","tt",e.title));const parts=(e.note||"").split(" · "),home=parts[0]==="Heimaleikur";
mid.appendChild(el("div","sm",[e.sport,e.gender].filter(Boolean).join(" · ")+(parts.length>1?" · "+parts.slice(1).join(" · "):"")));
a.appendChild(mid);
if(e.res)a.appendChild(el("div","sc",e.res));else if(parts[0]==="Heimaleikur"||parts[0]==="Útileikur")a.appendChild(el("span","hu"+(home?" h":""),home?"Heima":"Úti"));else a.appendChild(el("span"));
box.appendChild(a)})}
document.getElementById("upd").textContent="Uppfært __TIME__";renderWx();if(API&&WEATHER)fetch(API+"/vedur").then(r=>r.json()).then(v=>{if(v&&v.T!==null&&v.T!==undefined){WEATHER.now.T=v.T;WEATHER.now.F=v.F;WEATHER.now.D=v.D;WEATHER.now.night=v.night;WEATHER.upd=v.time||WEATHER.upd;renderWx()}}).catch(()=>{});render();side();strip();if(API)fetch(API+"/top").then(r=>r.json()).then(t=>{TOP=t;side();strip();if(cur==="Mest lesið")render()}).catch(()=>{});
</script></body></html>"""


COUNTER_URL = "https://akureyri-smellir.hermannh2000.workers.dev"  # slóð á Cloudflare Worker (fyllt út þegar hann er tilbúinn)


# ---------- Veður ----------
WX_ID = "3471"  # Akureyri hjá Veðurstofu Íslands
WX_URL = "https://xmlweather.vedur.is/?op_w=xml&lang=is&view=xml&ids=" + WX_ID


def _wx_get(kind):
    import xml.etree.ElementTree as ET
    req = urllib.request.Request(WX_URL + "&type=" + kind, headers={"User-Agent": "Mozilla/5.0 (AkureyriFrettir)"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return ET.fromstring(r.read())


def _wx_num(el, tag):
    try:
        return float((el.findtext(tag) or "").strip().replace(",", "."))
    except ValueError:
        return None


def read_weather():
    """Veðrið núna og spá næstu 3 daga á Akureyri (Veðurstofa Íslands). Fellur aftur á gömlu skrána ef þetta bregst."""
    now_utc = datetime.utcnow()  # Ísland er á UTC allt árið
    today = now_utc.strftime("%Y-%m-%d")
    pts = []
    for f in _wx_get("forec").iter("forecast"):
        ft = (f.findtext("ftime") or "").strip().replace(" ", "T")[:19]
        if ft:
            pts.append({"t": ft, "T": _wx_num(f, "T"), "F": _wx_num(f, "F"), "R": _wx_num(f, "R"),
                        "D": (f.findtext("D") or "").strip(), "W": (f.findtext("W") or "").strip()})
    if not pts:
        raise ValueError("engin spágögn")
    pts.sort(key=lambda x: x["t"])
    cur = None
    try:
        obs = []
        for o in _wx_get("obs").iter("station"):
            tm = (o.findtext("time") or "").strip().replace(" ", "T")[:19]
            if tm and _wx_num(o, "T") is not None:
                obs.append({"t": tm, "T": _wx_num(o, "T"), "F": _wx_num(o, "F"), "R": None,
                            "D": (o.findtext("D") or "").strip(), "W": (o.findtext("W") or "").strip()})
        if obs:
            cur = max(obs, key=lambda x: x["t"])
    except Exception as e:
        print("X  Veður (mæling): %s" % e)
    nowkey = now_utc.strftime("%Y-%m-%dT%H:%M:%S")
    nxt = next((x for x in pts if x["t"] >= nowkey), pts[0])
    if cur is None:
        cur = dict(nxt)
    elif not cur.get("W"):
        cur["W"] = nxt.get("W", "")  # mælingin hefur oft ekki lýsingu, notum spána fyrir sama tíma
    days = {}
    for x in pts:
        if x["t"][:10] > today:
            days.setdefault(x["t"][:10], []).append(x)
    out = []
    for d in sorted(days)[:3]:
        mid = min(days[d], key=lambda x: abs(int(x["t"][11:13]) - 12))  # spáin kl. 12:00
        if mid["T"] is None:
            continue
        out.append({"date": d, "T": mid["T"], "F": mid["F"], "D": mid["D"], "W": mid["W"]})
    if not out:
        raise ValueError("engin dagagögn")
    return {"upd": now_utc.strftime("%d.%m %H:%M"), "now": {"T": cur["T"], "F": cur["F"], "D": cur["D"], "W": cur["W"], "night": _wx_night(now_utc)}, "days": out}


def _wx_night(t):
    """Nálgun á hvort er nótt á Akureyri (sólarris/sólsetur reiknað úr degi ársins)."""
    import math
    n = t.timetuple().tm_yday
    decl = math.radians(23.44) * math.sin(2 * math.pi * (284 + n) / 365)
    c = -math.tan(math.radians(65.68)) * math.tan(decl)
    if c >= 1:
        return True
    if c <= -1:
        return False
    half = math.degrees(math.acos(c)) / 15.0
    noon = 12 + 18.1 / 15.0
    h = t.hour + t.minute / 60.0
    return abs(h - noon) > half


def load_weather():
    try:
        w = read_weather()
        with open("weather.json", "w", encoding="utf-8") as f:
            json.dump(w, f, ensure_ascii=False, indent=1)
        print("OK Veður: %d° núna, %d dagar" % (round(w["now"]["T"] or 0), len(w["days"])))
        return w
    except Exception as e:
        print("X  Veður: %s – nota gömlu skrána" % e)
        return _load("weather.json", None)


def write_html(items, events=None, offers=None, stand=None, flights=None, weather=None):
    wxdata = json.dumps(weather, ensure_ascii=False).replace("</", "<\\/")
    fldata = json.dumps(flights or [], ensure_ascii=False).replace("</", "<\\/")
    stdata = json.dumps(stand or [], ensure_ascii=False).replace("</", "<\\/")
    ofdata = json.dumps(offers or [], ensure_ascii=False).replace("</", "<\\/")
    data = json.dumps(items, ensure_ascii=False).replace("</", "<\\/")
    evdata = json.dumps(events or [], ensure_ascii=False).replace("</", "<\\/")
    page = HTML.replace("__WEATHER__", wxdata).replace("__FLIGHTS__", fldata).replace("__STAND__", stdata).replace("__OFFERS__", ofdata).replace("__EVENTS__", evdata).replace("__DATA__", data).replace("__API__", COUNTER_URL).replace("__TIME__", datetime.now().strftime("%d.%m.%Y %H:%M"))
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(page)


DEEP_UA = {"User-Agent": "AkureyriFrettir/0.1 (+https://github.com/hermannhelgi4/akureyri-frettir)"}
DEEP_KEYWORDS = [k for k in KEYWORDS if k != "samherj"]  # Samherji kemur oft fyrir í fréttum sem eru ekki um Akureyri
DEEP_BUDGET = 200  # mest svo margar fréttasíður sóttar í hverri keyrslu
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


MAK_CATS = {"2012-2013": "Leiksýningar", "2013-2014": "Tónleikar", "midar": "Uppistand", "fyrir-born": "Fyrir börn"}  # (midar-1 = „Ýmsir viðburðir“, segir ekkert)
_MAK_TOKEN = re.compile(r"(?<![\w-])(2012-2013|2013-2014|midar-1|midar|fyrir-born)(?![\w-])")


def mak_categories(page):
    """Flokkur hvers viðburðar eins og MAK skráir hann í sjálfri síðunni (ef hann finnst): {slug: flokkur}."""
    anchors = [(m.start(), m.end(), m.group(1)) for m in re.finditer(r'href="(?:https?://[^"/]+)?/is/vidburdir/([^"/?#]+)/?"', page)]
    out, prev_end, i = {}, 0, 0
    while i < len(anchors):
        slug = anchors[i][2]
        j = i
        while j + 1 < len(anchors) and anchors[j + 1][2] == slug:
            j += 1
        lo = max(prev_end, anchors[i][0] - 800)
        sel = page.rfind("</select>", 0, anchors[i][0])
        if sel >= 0:
            lo = max(lo, sel + 9)  # flokkavalmyndin sjálf er ekki hluti af spjaldinu
        chunk = page[lo:anchors[j][1]]
        toks = set(_MAK_TOKEN.findall(chunk))
        if len(toks) == 1:
            t = next(iter(toks))
            if t in MAK_CATS:
                out[slug] = MAK_CATS[t]
        prev_end = anchors[j][1]
        i = j + 1
    return out


def read_mak(today):
    """Menningarfélag Akureyrar (Hof, Samkomuhúsið o.fl.). Dagsetning án ártals; ártal ályktað."""
    base = "https://www.mak.is/is/vidburdir"
    page = fetch_page(base)
    mak_cat = mak_categories(page)
    print("   MAK: flokkur lesinn úr síðunni fyrir %d viðburði" % len(mak_cat))
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
                       "image": img, "note": "", "cat0": mak_cat.get(slug, "")})
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
DETAIL_VER = 5  # hækkað þegar lesarinn bætir við upplýsingum, svo gömul gögn séu sótt aftur


def main_text(page):
    """Texti aðalefnis síðunnar (<main>), án valmyndar og fótar."""
    m = re.search(r"<main.*?</main>", page, re.S | re.I)
    return page_text(m.group(0) if m else page)


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


HOF_HALLS = {"hamraborg", "hamrar", "naust", "nausti", "kaldi", "setberg", "black box"}


def mak_venue(page):
    """Staður viðburðar eins og MAK skrifar hann (t.d. Hamraborg, Hamrar, Samkomuhúsið).
    Salir í Hofi fá „, Hof“ aftan við svo fólk viti hvar salurinn er."""
    m = re.search(r'<div class="location">\s*([^<]+?)\s*</div>', page)
    if not m:
        return ""
    raw = html.unescape(m.group(1)).strip()
    if raw.lower() in HOF_HALLS:
        return raw + ", Hof"
    return raw


def mak_detail(page, e, today):
    sh = showings_to_dates(mak_showings(page), date.fromisoformat(e["start"]))
    return {"showings": [[d.isoformat(), tm] for d, tm in sh], "image": _og(page), "price": parse_price(page_text(page)),
            "venue": mak_venue(page), "txt": main_text(page)[:900]}


def graeni_detail(page, e, today):
    m = re.search(r"\b\d{2}\.\d{2}\.20\d\d\s+([01]?\d|2[0-3]):([0-5]\d)\b", page_text(page))
    txt = ""
    for pat in (r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)',
                r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:description["\']'):
        md = re.search(pat, page, re.I)
        if md:
            txt = clean(html.unescape(md.group(1)))[:900]
            break
    if len(txt) < 40:  # annars lýsingin sjálf á síðunni (textinn á eftir „Kaupa miða“)
        full = main_text(page)  # aðeins aðalefni síðunnar, ekki valmynd og fótur
        i = full.find("Kaupa miða")
        if i >= 0:
            txt = full[i + 10:i + 910]
    return {"time": ("%02d:%s" % (int(m.group(1)), m.group(2))) if m else "", "image": _og(page),
            "price": parse_price(page_text(page)), "txt": txt}


# --- Miðasölur: Tix, Midix og Stubb (viðburðir á Akureyri) ---
# Staðir á Akureyri (hluti af nafni staðar eða titli). Bættu við hér ef staður vantar.
AK_PLACE = re.compile(
    r"akureyri|akureyrar|leyni bar|sjallinn|glerárkirkja|ketilkaffi|hlíðarfjall|ka-heimil|ka heimil|boginn\b|múlaberg|"
    r"pósthúsbar|kaffi ilmur|greifinn|skjaldborg|verkmenntaskól", re.I)
# Þessir viðburðir eru þegar inni frá opinberu síðunum (MAK/Hof, Samkomuhúsið) eða Græna hattinum – ekki tekið aftur
AK_SKIP = re.compile(
    r"\bhof\b|hamraborg|samkomuhús|menningarhúsið|menningarfélag|\bmak\b|\bhamrar\b|\bnaust(?:i)?\b|\bkaldi\b|setberg|black box|"
    r"græni hatturinn|graeni", re.I)
SPORT_WORDS = re.compile(r"körfubolti|handbolti|fótbolti|blak\b|íshokkí|\bdeild\b|\bbikar|\bEHF\b|úrvalsdeild|mjólkurbikar|"
                         r"\bsports\b|íþróttir", re.I)
MIDASALA = "Miðasala"
MID_DATE = re.compile(r"(\d{1,2})\.?\s+(janúar|febrúar|mars|apríl|maí|júní|júlí|ágúst|september|október|nóvember|desember)\s+(20\d\d)", re.I)
MID_SLUG = re.compile(r"-(\d{1,2})-([a-z]{3})[a-z]*-(20\d\d)(?:-\d+)?/eid/(\d+)", re.I)


def _is_ak(place, title=""):
    """Á Akureyri (eftir stað/titli) og ekki þegar inni frá MAK/Hof eða Græna hattinum."""
    hay = (place or "") + " | " + (title or "")
    if AK_SKIP.search(place or ""):
        return False
    return bool(AK_PLACE.search(hay))


def _mid_norm(title):
    return re.sub(r"\W+", "", (title or "").lower())


def read_midix(today):
    base = "https://www.midix.is/is"
    page = fetch_page(base)
    pat = re.compile(r"/eid/\d+")
    out, total = [], 0
    for g in link_groups(page, pat):
        total += 1
        text = g["text"]
        d = None
        ms = MID_SLUG.search(g["href"])
        if ms:
            try:
                d = date(int(ms.group(3)), MONTHS_EN[ms.group(2).lower()], int(ms.group(1)))
            except (ValueError, KeyError):
                d = None
        md = MID_DATE.search(text)
        if not d and md:
            try:
                d = date(int(md.group(3)), MONTHS_IS[md.group(2)[:3].lower()], int(md.group(1)))
            except (ValueError, KeyError):
                d = None
        if not d:
            continue
        if md:
            before, after = text[:md.start()], text[md.end():]
        else:
            before, after = text, ""
        price = PRICE_RE.search(after)
        venue = after[:price.start()] if price else after
        venue = clean(venue).strip(" |-–—·,.:")
        notes = []
        for raw, label in (("UPPSELT", "Uppselt"), ("FÁIR MIÐAR", "Fáir miðar"), ("NÝTT", "Nýtt")):
            if re.search(raw, before + " " + after, re.I) and label not in notes:
                notes.append(label)
        title = clean(re.sub(r"UPPSELT!?|FÁIR MIÐAR|NÝTT|Kaupa miða", " ", before, flags=re.I)).strip(" |-–—·,.:")
        if len(title) < 2 and g["imgs"]:
            title = clean(g["imgs"][0][2])
        if len(title) < 2:
            continue
        venue = re.sub(r"UPPSELT!?|FÁIR MIÐAR|NÝTT|Kaupa miða", " ", venue, flags=re.I)
        venue = clean(venue).strip(" |-–—·,.:")
        if not _is_ak(venue, title):
            continue
        if price:
            notes.append(re.sub(r"\s*kr\.?$", " kr.", price.group(0).strip(), flags=re.I))
        img = urljoin(base, g["imgs"][0][1]) if g["imgs"] and g["imgs"][0][1] else None
        out.append({"title": title[:140], "source": MIDASALA, "site": "Midix", "link": urljoin(base, g["href"]),
                    "start": d.isoformat(), "end": d.isoformat(), "time": "", "image": img,
                    "note": " · ".join(notes), "venue": venue})
    print("   Midix: %d tenglar á forsíðu, %d á Akureyri" % (total, len(out)))
    return out


_DET = {}  # sameiginlegt minni (events_detail.json) – fyllt út í collect_events
TIX_PAGES = ["https://tix.is/", "https://tix.is/collection/nytt", "https://tix.is/collection/popular",
             "https://tix.is/collection/spennandi-hatidir-a-naestunni"]
TIX_EVENT = re.compile(r"/event/(\d+)(?:/([a-z0-9\-]+))?", re.I)


TIX_CACHE = "tix_cache.json"
TIX_LOW = 20000        # elstu auðkenni sem eru skoðuð (eldri viðburðir eru liðnir eða langtímaviðburðir á forsíðu)
TIX_BUDGET = 800       # mest svo mörg auðkenni sótt í hverri keyrslu (restin kemur í næstu keyrslum)
TIX_AHEAD = 60         # leita svona langt fyrir ofan hæsta þekkta auðkenni (nýir viðburðir)


def tix_fetch(eid):
    """Sækir gögn eins viðburðar frá Tix. Skilar None ef viðburðurinn er ekki til; kastar villu ef netið bilar."""
    url = "https://tix.is/api/proxy?id=" + eid
    req = urllib.request.Request(url, headers=DEEP_UA)
    try:
        with OPENER.open(req, timeout=20) as r:
            body = r.read(3000000).decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        if e.code in (400, 404, 410, 500):
            return None
        raise
    if not body.strip():
        return None
    try:
        data = json.loads(body)
    except ValueError:
        return None
    return data if data else None


def tix_slug(name):
    t = name.lower().translate(str.maketrans({"á": "a", "ð": "d", "é": "e", "í": "i", "ó": "o", "ú": "u", "ý": "y", "ö": "o", "æ": "ae"}))
    t = t.replace("þ", "th")
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


def tix_events(eid, slug, data):
    ev = []
    for g in data if isinstance(data, list) else [data]:
        if not isinstance(g, dict):
            continue
        name = clean(g.get("Name") or "")
        slug = slug or tix_slug(name)
        link = "https://tix.is/event/%s%s" % (eid, ("/" + slug) if slug else "")
        for x in g.get("Dates") or []:
            venue = x.get("Venue") or x.get("Hall") or ""
            if not _is_ak(venue + " " + (x.get("Hall") or ""), name):
                continue
            sd = x.get("StartDate") or ""
            if len(sd) < 10:
                continue
            notes = []
            if x.get("SoldOut"):
                notes.append("Uppselt")
            lo, hi = x.get("MinPrice"), x.get("MaxPrice")
            if lo:
                fmt = lambda n: "{:,}".format(int(n)).replace(",", ".")
                notes.append((fmt(lo) + (" – " + fmt(hi) if hi and hi != lo else "")) + " kr.")
            img = g.get("EventImagePath") if g.get("HasEventImage") else (g.get("PosterImagePath") if g.get("HasPosterImage") else None)
            ev.append({"title": name[:140], "source": MIDASALA, "site": "Tix", "link": link, "start": sd[:10], "end": sd[:10],
                       "time": sd[11:16] if len(sd) >= 16 and sd[11:16] != "00:00" else "", "image": img,
                       "note": " · ".join(notes), "venue": venue, "cat0": x.get("Categories") or "", "detail": False,
                       "txt": clean(re.sub(r"<[^>]+>", " ", g.get("Description") or ""))[:400]})
    return ev


def read_tix(today):
    """Tix er ekki með lista yfir alla viðburði, svo ég fer yfir auðkennin (númerin) sjálf.
    Niðurstaða hvers númers er geymd í tix_cache.json svo aðeins ný númer og Akureyrarviðburðir eru sótt aftur."""
    cache = _load(TIX_CACHE, {})
    slugs = {}
    for url in TIX_PAGES:
        try:
            page = fetch_page(url)
        except Exception as e:
            print("   Tix %s: %s" % (url, str(e)[:100]))
            continue
        for m in TIX_EVENT.finditer(page):
            if m.group(2):
                slugs[m.group(1)] = m.group(2)
            else:
                slugs.setdefault(m.group(1), None)
    known = [int(i) for i in list(slugs) + [k for k, v in cache.items() if not v.get("miss")] if i.isdigit()]
    hi = (max(known) if known else TIX_LOW) + TIX_AHEAD
    now = time.time()

    def stale(i):
        c = cache.get(str(i))
        if not c:
            return True
        age = now - c.get("ts", 0)
        if c.get("ev"):
            return age > 12 * 3600                 # Akureyrarviðburður: sótt aftur tvisvar á dag
        if c.get("miss"):
            return age > (2 * 86400 if i > hi - 150 else 30 * 86400)  # ný númer gætu orðið til síðar
        return age > 7 * 86400                     # viðburður ekki á Akureyri: skoðaður aftur á viku fresti

    todo = [i for i in range(hi, TIX_LOW - 1, -1) if stale(i)][:TIX_BUDGET]
    allowed_ok = allowed("https://tix.is/api/proxy?id=1")
    if not allowed_ok:
        print("VIÐVÖRUN Tix: robots.txt bannar aðgang að gagnaslóðinni")
        todo = []

    def one(i):
        eid = str(i)
        try:
            data = tix_fetch(eid)
        except Exception:
            return eid, "err"
        if data is None:
            return eid, {"ts": now, "miss": 1, "ev": []}
        return eid, {"ts": now, "ev": tix_events(eid, slugs.get(eid), data)}

    res = pmap(one, todo, workers=6)
    errs = 0
    for eid, c in res:
        if c == "err":
            errs += 1
        else:
            cache[eid] = c
    out = []
    for eid, c in cache.items():
        for e in c.get("ev", []):
            out.append(e)
    # geymi aðeins það sem er nýlegt
    keep = {k: v for k, v in cache.items() if now - v.get("ts", 0) < 60 * 86400}
    with open(TIX_CACHE, "w", encoding="utf-8") as f:
        json.dump(keep, f, ensure_ascii=False)
    print("   Tix: %d númer skoðuð núna (%d villur), %d í minni, %d sýningar á Akureyri (hæsta númer %d)" % (
        len(todo), errs, len(keep), len(out), hi - TIX_AHEAD))
    return out


STUBB_PAGES = ["https://stubb.is/events?category=concerts", "https://stubb.is/events", "https://stubb.is/"]
STUBB_DATE = re.compile(r"^(\d{1,2})\s+(jan|feb|mar|apr|maí|jún|júl|ágú|sep|okt|nóv|des)\b", re.I)
STUBB_NAME_KEYS = ("name", "title", "eventName")
STUBB_DATE_KEYS = ("startDate", "start", "date", "eventDate", "startTime", "dateTime", "startsAt")


def _walk(x, found):
    if isinstance(x, dict):
        if any(isinstance(x.get(k), str) for k in STUBB_NAME_KEYS) and any(isinstance(x.get(k), str) and re.match(r"20\d\d-\d\d-\d\d", x.get(k)) for k in STUBB_DATE_KEYS):
            found.append(x)
        for v in x.values():
            _walk(v, found)
    elif isinstance(x, list):
        for v in x:
            _walk(v, found)


def read_stubb(today):
    out, seen, pages = [], set(), 0
    for url in STUBB_PAGES:
        try:
            page = fetch_page(url)
        except Exception as e:
            print("   Stubb %s: %s" % (url, str(e)[:100]))
            continue
        pages += 1
        # 1) gögn sem fylgja síðunni (__NEXT_DATA__)
        m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', page, re.S)
        if m:
            try:
                found = []
                _walk(json.loads(m.group(1)), found)
                if found:
                    print("   Stubb: %d hlutir í __NEXT_DATA__ (lyklar fyrsta: %s)" % (len(found), sorted(found[0].keys())[:20]))
                for x in found:
                    title = clean(next(x[k] for k in STUBB_NAME_KEYS if isinstance(x.get(k), str)))
                    ds = next(x[k] for k in STUBB_DATE_KEYS if isinstance(x.get(k), str) and re.match(r"20\d\d-\d\d-\d\d", x[k]))
                    ven = x.get("venue") or x.get("location") or x.get("venueName") or ""
                    if isinstance(ven, dict):
                        ven = ven.get("name") or ven.get("title") or ""
                    ven = clean(str(ven))
                    cat = " ".join(str(x.get(k) or "") for k in ("category", "categoryName", "type", "sport"))
                    if SPORT_WORDS.search(cat + " " + title) or not _is_ak(ven, title):
                        continue
                    code = x.get("slug") or x.get("id") or x.get("code") or ""
                    link = "https://stubb.is/events/%s" % code if code else "https://stubb.is/"
                    key = (link, ds[:10])
                    if key in seen:
                        continue
                    seen.add(key)
                    out.append({"title": title[:140], "source": MIDASALA, "site": "Stubb", "link": link, "start": ds[:10],
                                "end": ds[:10], "time": ds[11:16] if len(ds) >= 16 and ds[11:16] != "00:00" else "",
                                "image": x.get("image") if isinstance(x.get("image"), str) else None, "note": "", "venue": ven, "detail": False})
            except Exception as e:
                print("   Stubb: __NEXT_DATA__ las ekki (%s)" % e)
        # 2) spjöld með tengla á /events/<kóði> í HTML
        for g in link_groups(page, re.compile(r"^/events/[A-Za-z0-9]+$")):
            parts = [p.strip() for p in g["text"].split("|") if p.strip()]
            if len(parts) < 3:
                continue
            dm = None
            for i, p in enumerate(parts):
                dm = STUBB_DATE.match(p)
                if dm:
                    parts = parts[i + 1:]
                    break
            if not dm:
                continue
            parts = [p for p in parts if not re.fullmatch(r"UPPSELT!?|FÁIR MIÐAR( EFTIR)?|Frá.*|\+\d+ dagsetning\w*", p, re.I)]
            if len(parts) < 2:
                continue
            title, ven = parts[0], parts[-1]
            if SPORT_WORDS.search(" ".join(parts)) or not _is_ak(ven, title):
                continue
            d = _on_or_after(int(dm.group(1)), MONTHS_IS[dm.group(2).lower()], today)
            if not d:
                continue
            link = urljoin("https://stubb.is", g["href"])
            key = (link, d.isoformat())
            if key in seen:
                continue
            seen.add(key)
            out.append({"title": title[:140], "source": MIDASALA, "site": "Stubb", "link": link, "start": d.isoformat(),
                        "end": d.isoformat(), "time": "", "image": None, "note": "", "venue": ven, "detail": False})
    print("   Stubb: %d síður lesnar, %d viðburðir á Akureyri" % (pages, len(out)))
    return out


def read_midasala(today):
    """Tix, Midix og Stubb saman. Ef ein síða bilar helst það sem hún átti fyrir í fyrri lista."""
    old = _load("events.json", [])
    res, seen = [], set()
    for site, fn in (("Tix", read_tix), ("Midix", read_midix), ("Stubb", read_stubb)):
        try:
            found = fn(today)
        except Exception as e:
            print("X  Miðasala %s: tókst ekki (%s)" % (site, e))
            found = []
        if not found:
            held = [e for e in old if e.get("source") == MIDASALA and e.get("site") == site]
            if held:
                print("   %s: ekkert nýtt fannst, held %d eldri viðburðum" % (site, len(held)))
            found = held
        for e in found:
            key = (_mid_norm(e["title"]), e["start"])
            if key in seen:
                continue
            seen.add(key)
            res.append(e)
    return res


# (nafn, lesari á lista, lesari á síðu viðburðar, bið í sek. milli beiðna, mest margar síður í hverri keyrslu)
EVENT_SOURCES = [
    ("MAK / Hof", read_mak, mak_detail, 5, 15),  # MAK biður um 5 sek. bil (Crawl-delay)
    ("Græni hatturinn", read_graeni, graeni_detail, 1, 25),
    (MIDASALA, read_midasala, graeni_detail, 1, 20),  # Tix, Midix og Stubb (síður sóttar aðeins fyrir Midix; sama kerfi og Græni hatturinn)
]


def _load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


# ---------- Tilboð ----------
def demo_offers(today):
    u = (today + timedelta(days=90)).isoformat()
    soon = (today + timedelta(days=5)).isoformat()
    return [
        {"business": "Kaffihúsið Bylgjan (dæmi)", "category": "Kaffi", "offer": "2 fyrir 1 af kaffi", "details": "Kaupðu einn kaffibolla og fáðu annan frítt. Gildir með öllum heitum drykkjum.", "days": [], "from": "", "until": u, "image": "", "address": "Hafnarstræti 1, Akureyri"},
        {"business": "Pizzastaðurinn Eldur (dæmi)", "category": "Matur", "offer": "2 fyrir 1 af pizzum", "details": "Gildir á þriðjudögum, borðað á staðnum.", "days": ["þri"], "from": "", "until": u, "image": "", "address": "Strandgata 5, Akureyri"},
        {"business": "Bókabúðin Blaða (dæmi)", "category": "Verslun", "offer": "10% afsláttur", "details": "10% afsláttur af öllum bókum gegn framvísun kortsins.", "days": [], "from": "", "until": u, "image": "", "address": "Skipagata 3, Akureyri"},
        {"business": "Bakaríið Brauðið (dæmi)", "category": "Matur", "offer": "Frítt kaffi með bakkelsi", "details": "Frítt kaffi þegar keypt er bakkelsi. Virka daga.", "days": ["mán", "þri", "mið", "fim", "fös"], "from": "", "until": u, "image": "", "address": "Kaupvangsstræti 7, Akureyri"},
        {"business": "Keilusalurinn Kúlan (dæmi)", "category": "Afþreying", "offer": "Önnur brautin á hálfvirði", "details": "Gildir um helgar.", "days": ["lau", "sun"], "from": "", "until": u, "image": "", "address": "Glerárgata 20, Akureyri"},
        {"business": "Hárstofan Lokkur (dæmi)", "category": "Þjónusta", "offer": "15% afsláttur af klippingu", "details": "Gildir mið–fim. Pantaðu tíma fyrirfram.", "days": ["mið", "fim"], "from": "", "until": soon, "image": "", "address": "Gránufélagsgata 9, Akureyri"},
        {"business": "Líkamsræktin Kraftur (dæmi)", "category": "Heilsa", "offer": "Frítt prufukort í 3 daga", "details": "Fyrir nýja viðskiptavini. Eitt kort á mann.", "days": [], "from": "", "until": u, "image": "", "address": "Austurbyggð 2, Akureyri"},
        {"business": "Ísbúðin Frostið (dæmi)", "category": "Matur", "offer": "2 fyrir 1 af ís í brauðformi", "details": "Gildir sunnudaga.", "days": ["sun"], "from": "", "until": u, "image": "", "address": "Glerártorg, Akureyri"},
    ]


def load_offers(today):
    raw = _load("tilbod.json", None)
    if not isinstance(raw, list):
        raw = demo_offers(today)
        print("OK Tilboð: tilbod.json fannst ekki, nota dæmi")
    out = []
    for o in raw:
        if not isinstance(o, dict) or not o.get("business") or not o.get("offer"):
            continue
        c = {"business": str(o["business"]), "offer": str(o["offer"]),
             "category": o.get("category") or "Verslun", "details": o.get("details") or "",
             "days": o.get("days") if isinstance(o.get("days"), list) else [],
             "from": o.get("from") or "", "until": o.get("until") or "",
             "image": o.get("image") or "", "address": o.get("address") or ""}
        if c["until"] and c["until"] < today.isoformat():
            continue
        out.append(c)
    print("OK Tilboð: %d" % len(out))
    return out


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
                        "link": ("https://www.hsi.is/match/%s" % g["GameId"]) if g.get("GameId") else "https://www.hsi.is/tournament/%d" % tid})
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
            time.sleep(0.3)
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
        gid, sid, lid = (re.search(k + r'="(\d+)"', row) for k in ("game_id", "season_id", "league_id"))
        link = ""
        if gid and sid:  # beinn tengill á leikinn sjálfan (tölfræði leiks) á kki.is
            link = "https://www.kki.is/motamal/leikir-og-urslit/motayfirlit/Leikur?league_id=%s&season_id=%s&game_id=%s" % (
                lid.group(1) if lid else "", sid.group(1), gid.group(1))
        out.append({"link": link, "date": "%s-%s-%s" % (d.group(3), d.group(2), d.group(1)),
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
            time.sleep(0.3)
        mine = [r for r in rows if r["home"] in SPORT_TEAMS or r["away"] in SPORT_TEAMS]
        if rows:
            print("   Körfubolti deild %d (%s): %d leikir, %d hjá Þór Ak." % (lg, rows[0]["league"], len(rows), len(mine)))
        for r in mine:
            low = r["league"].lower()
            out.append({"sport": "Körfubolti", "gender": "Konur" if ("kvenna" in low or "konur" in low) else "Karlar",
                        "comp": r["league"], "date": r["date"], "time": r["time"], "home": r["home"], "away": r["away"],
                        "rh": r["rh"], "ra": r["ra"], "venue": r["venue"], "link": r.get("link") or KKI_LINK})
        time.sleep(0.3)
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
            time.sleep(0.2)
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
            time.sleep(0.2)
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


# ---------- Flug frá Akureyri ----------
# Gögnin eru handskráð í flug.json (sjá demo_flights fyrir sniðið). Flug með "until" sem er liðið hverfa sjálfkrafa.
def load_flights(today):
    """Aðeins staðfest flug. kind=weekly: fast vikuleg áætlun (dagatal). kind=trip: ein ferð með upphafs- og lokadegi."""
    raw = _load("flug.json", None)
    if not isinstance(raw, list):
        print("X  Flug: flug.json fannst ekki")
        return []
    out, skipped = [], 0
    for f in raw:
        if not isinstance(f, dict) or not f.get("to") or not f.get("operator"):
            continue
        if f.get("confirmed") is not True:
            skipped += 1
            continue
        days = f.get("days") if isinstance(f.get("days"), list) else []
        kind = f.get("kind") or ("weekly" if days and f.get("from") and f.get("until") else "trip")
        c = {"kind": kind, "to": str(f["to"]), "short": str(f.get("short") or f["to"]), "operator": str(f["operator"]), "days": days,
             "from": f.get("from") or "", "until": f.get("until") or "", "start": f.get("start") or f.get("from") or "",
             "end": f.get("end") or f.get("until") or "", "times": f.get("times") or "", "price": f.get("price") or "",
             "note": f.get("note") or "", "link": f.get("link") or "", "linkText": f.get("linkText") or "", "flag": f.get("flag") or "",
             "bookRT": f.get("bookRT") or "", "bookOW": f.get("bookOW") or ""}
        if kind == "weekly" and not (c["from"] and c["until"] and days):
            continue
        if kind != "weekly" and not (c["start"] and c["end"]):
            continue
        last = c["until"] if kind == "weekly" else c["end"]
        if last < today.isoformat():
            continue
        out.append(c)
    print("OK Flug: %d staðfest (%d óstaðfest ekki sýnd)" % (len(out), skipped))
    return out


# ---------- Stöðutöflur ----------
# Hver tafla: {sport, gender, comp, link, rows:[{n, t, p, w, d, l, g, pts, me}]}  (p=leikir, w=unnir, d=jafntefli, l=töp, g="mörk fyrir-gegn")
def srow(n, team, p, w, d, l, g, pts):
    def num(x):
        try:
            return int(str(x).strip())
        except ValueError:
            return 0
    return {"n": n, "t": team, "p": num(p), "w": num(w), "d": num(d), "l": num(l), "g": g or "", "pts": num(pts),
            "me": team in SPORT_TEAMS}


def has_mine(rows):
    return any(r["me"] for r in rows)


def stand_hsi(today):
    out = []
    for tid, gender in HSI_TOURNAMENTS:
        try:
            data = fetch_json("https://www.hsi.is/api/hsi/tournaments/%d/standings" % tid).get("data", {})
            teams = (data.get("STANDINGS") or {}).get("TEAM") or []
            if data.get("Stodutafla_Display") not in ("1", 1, None) or not teams:
                continue
            rows = [srow(i + 1, t.get("TEAM_SHORT_NAME", "").strip(), t.get("MATCHES"), t.get("HOME"), t.get("TIE"),
                         t.get("LOSE"), "%s-%s" % (t.get("GOALS", 0), t.get("GOALS_RECIEVED", 0)), t.get("POINTS"))
                    for i, t in enumerate(teams)]
            if not has_mine(rows):
                continue
            try:
                comp = (fetch_json("https://www.hsi.is/api/hsi/tournaments/%d/matches" % tid).get("data") or [{}])[0].get("TournamentName") or "Handbolti"
            except Exception:
                comp = "Handbolti"
            out.append({"sport": "Handbolti", "gender": gender, "comp": comp.strip(),
                        "link": "https://www.hsi.is/tournament/%d" % tid, "rows": rows})
        except Exception as e:
            print("X  Tafla HSÍ %d: tókst ekki (%s)" % (tid, e))
    return out


def ihi_table(page):
    """Reiknar töflu úr leikjum deildarkeppninnar: 3 stig fyrir sigur, 2/1 eftir framlengingu (fleiri en 3 lotur)."""
    text = re.sub(r"(?is)<(script|style).*?</\1>", " ", page)
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    text = re.sub(r"\s+", " ", text)
    marks = list(IHI_ROW.finditer(text))
    t = {}
    for i, mk in enumerate(marks):
        seg = text[mk.end(): marks[i + 1].start() if i + 1 < len(marks) else mk.end() + 300]
        if "completed" not in seg.lower() or "Round Robin" not in seg:
            continue
        tm = IHI_TEAMS.search(seg)
        if not tm:
            continue
        sc = IHI_SCORE.search(seg[tm.end():])
        if not sc:
            continue
        a, b = int(sc.group(1)), int(sc.group(2))
        paren = re.search(r"\(([^)]*)\)", seg[tm.end():])
        periods = len(re.findall(r"\d+\s*-\s*\d+", paren.group(1))) if paren else 3
        ot = periods > 3
        h, g = IHI_NAMES.get(tm.group(1), tm.group(1)), IHI_NAMES.get(tm.group(2), tm.group(2))
        for name in (h, g):
            t.setdefault(name, {"p": 0, "w": 0, "l": 0, "gf": 0, "ga": 0, "pts": 0})
        for name, f, ag, win in ((h, a, b, a > b), (g, b, a, b > a)):
            r = t[name]
            r["p"] += 1
            r["gf"] += f
            r["ga"] += ag
            if win:
                r["w"] += 1
                r["pts"] += 2 if ot else 3
            else:
                r["l"] += 1
                r["pts"] += 1 if ot else 0
    order = sorted(t.items(), key=lambda kv: (-kv[1]["pts"], -(kv[1]["gf"] - kv[1]["ga"]), -kv[1]["gf"], kv[0]))
    return [srow(i + 1, n, r["p"], r["w"], 0, r["l"], "%d-%d" % (r["gf"], r["ga"]), r["pts"]) for i, (n, r) in enumerate(order)]


def stand_ihi(today):
    out = []
    for tid, gender, comp in IHI_TOURNAMENTS:
        url = "https://stats.iihf.com/ihi/%d/index.html" % tid
        try:
            rows = ihi_table(fetch_page(url))
            if rows and has_mine(rows):
                out.append({"sport": "Íshokkí", "gender": gender, "comp": comp, "link": url, "rows": rows})
        except Exception as e:
            print("X  Tafla íshokkí %d: tókst ekki (%s)" % (tid, e))
    return out


def bli_table(page):
    rows = []
    parts = page.split('id="TeamName"')[1:]
    for part in parts:
        m = re.match(r">([^<]*)", part)
        if not m:
            continue
        name = html.unescape(m.group(1)).strip()
        body = re.sub(r"(?is)<(script|style).*?</\1>", " ", part[m.end(): m.end() + 2500])
        body = body.split("TeamName")[0]
        toks = html.unescape(re.sub(r"<[^>]+>", " ", body)).split()
        nums = []
        for tk in toks:
            if re.fullmatch(r"\d+", tk):
                nums.append(int(tk))
            else:
                break
        if len(nums) < 6:
            continue
        pts, played, won, lost, sw, sl = nums[:6]
        rows.append(srow(len(rows) + 1, name, played, won, 0, lost, "%d-%d" % (sw, sl), pts))
    return rows


def stand_bli(today):
    out = []
    for cid, gender, comp, pid in BLI_COMPETITIONS:
        if not pid:
            continue
        url = BLI_BASE + "CompetitionStandings.aspx?ID=%d&PID=%d" % (cid, pid)
        try:
            rows = bli_table(fetch_page(url))
            if rows and has_mine(rows):
                out.append({"sport": "Blak", "gender": gender, "comp": comp, "link": url, "rows": rows})
        except Exception as e:
            print("X  Tafla blak %s: tókst ekki (%s)" % (comp, e))
        time.sleep(0.3)
    return out


KKI_STAND = {190: ("Karlar", "Bónus deild karla"), 189: ("Konur", "Bónus deild kvenna"),
             191: ("Karlar", "1. deild karla"), 231: ("Konur", "1. deild kvenna")}


def kki_unesc(raw):
    s = re.sub(r"\\[nrt]", " ", raw)
    return re.sub(r"\\(.)", r"\1", s)


def kki_stand_url(**kw):
    base = "https://widgets.baskethotel.com/widget-service/show?&api=%s&lang=is&nnav=1&nav_object=0&hide_full_birth_date=0&flash=0" % KKI_API
    return base + "".join("&request[0][%s]=%s" % (k.replace("__", "]["), urllib.parse.quote(str(v), safe="")) for k, v in kw.items())


def kki_table(raw):
    s = kki_unesc(raw)
    rows = []
    for tr in re.split(r"<tr class=\"row\d\"", s)[1:]:
        m = re.search(r"team_name[^\"]*\">\s*([^<]*?)\s*</td>", tr)
        w = re.search(r"(\d+)<span></span>/<span></span>(\d+)</td>\s*<td>(\d+)</td>", tr)
        if not m or not w:
            continue
        won, lost = int(w.group(1)), int(w.group(2))
        rows.append(srow(len(rows) + 1, html.unescape(m.group(1)).strip(), won + lost, won, 0, lost, "", w.group(3)))
    return rows


def stand_kki(today):
    out = []
    for lg, (gender, comp) in KKI_STAND.items():
        try:
            first = kki_unesc(kki_fetch(kki_stand_url(container="view90", widget=300, param__league_id=lg)))
            season = re.search(r"season_id\s*=\s*'(\d+)'", first)
            state = re.search(r"state:\s*'([^']+)'", first)
            group = re.search(r"<option value=\"(\d+)\"", first)
            if not (season and state and group):
                print("X  Tafla KKÍ deild %d: fann ekki tímabil/state í svari" % lg)
                continue
            raw = kki_fetch(kki_stand_url(container="6-300-standings-container", widget=300, part="table", state=state.group(1),
                                          param__season_id=season.group(1), param__group_filter=group.group(1),
                                          param__showTeamLogo="", param__teamLogoSize="20x20"))
            rows = kki_table(raw)
            if rows and has_mine(rows):
                out.append({"sport": "Körfubolti", "gender": gender, "comp": comp, "link": KKI_LINK, "rows": rows})
        except Exception as e:
            print("X  Tafla KKÍ deild %d: tókst ekki (%s)" % (lg, e))
        time.sleep(0.3)
    return out


def ksi_table(page):
    for tb in re.findall(r"(?is)<table\b.*?</table>", page):
        ths = [re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", x))).strip().lower() for x in re.findall(r"(?is)<th\b.*?</th>", tb)]
        if not ths or ths[0] != "lið" or len(ths) < 8:
            continue
        rows = []
        for tr in re.findall(r"(?is)<tr\b.*?</tr>", tb):
            cells = re.findall(r"(?is)<td\b[^>]*>(.*?)</td>", tr)
            if len(cells) < 8:
                continue
            spans = [html.unescape(x).strip() for x in re.findall(r"<span[^>]*>([^<]*)</span>", cells[0])]
            spans = [x for x in spans if x]
            if len(spans) < 2:
                continue
            cl = [html.unescape(re.sub(r"<[^>]+>", "", c)).strip() for c in cells[1:]]
            rows.append(srow(len(rows) + 1, spans[-1], cl[0], cl[1], cl[2], cl[3], cl[4], cl[6]))
        if rows:
            return rows
    return []


def stand_ksi(today):
    comps = ksi_competitions(today)
    out = []
    for cid, label in comps.items():
        try:
            rows = ksi_table(fetch_page("%s/oll-mot/mot/?id=%s&banner-tab=overview" % (KSI_BASE, cid)))
        except Exception as e:
            print("X  Tafla KSÍ %s: tókst ekki (%s)" % (label, e))
            continue
        time.sleep(0.2)
        if rows and has_mine(rows):
            comp = re.sub(r"\s*\b20\d\d\b", "", label).strip()
            out.append({"sport": "Fótbolti", "gender": "Konur" if "kvenna" in label.lower() else "Karlar",
                        "comp": comp, "link": "%s/oll-mot/mot/?id=%s&banner-tab=overview" % (KSI_BASE, cid), "rows": rows})
    # þegar deildin hefur skipst í efri/neðri hluta sýnum við bara hlutann (ekki fyrri heildartöfluna)
    names = [g["comp"] for g in out]
    return [g for g in out if not any(n.startswith(g["comp"] + " - ") for n in names)]


STAND_SOURCES = [("Handbolti", stand_hsi), ("Íshokkí", stand_ihi), ("Blak", stand_bli), ("Körfubolti", stand_kki), ("Fótbolti", stand_ksi)]


def collect_standings(today):
    old = _load("standings.json", [])
    if not isinstance(old, list):
        old = []
    res = []
    for name, fn in STAND_SOURCES:
        try:
            got = fn(today)
        except Exception as e:
            print("X  Töflur %s: tókst ekki (%s)" % (name, e))
            got = []
        if not got:
            got = [g for g in old if g.get("sport") == name]
            print("   Töflur %s: engar nýjar, held í fyrri (%d)" % (name, len(got)))
        else:
            print("OK Töflur %s: %d" % (name, len(got)))
        res += got
    try:
        with open("standings.json", "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=1)
    except Exception as e:
        print("X  Töflur: gat ekki vistað (%s)" % e)
    return res


def collect_events():
    today = datetime.now(timezone.utc).date()
    old = _load("events.json", [])
    imgs = _load("events_img.json", {})
    det = _DET
    det.update(_load("events_detail.json", {}))
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

        todo = [] if detail is None else [e for e in found if e.get("detail", True) and now - _age(e) > DETAIL_TTL]
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
            v = det.get(e["link"], {}).get("venue")
            if v:
                e["venue"] = v
            if det.get(e["link"], {}).get("txt"):
                e["txt"] = det[e["link"]]["txt"]
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
    unk = set()
    for e in result:
        e["kind"] = event_kind(e)
        if not e["kind"]:
            e["kind"] = kind_default(e)  # aldrei án flokks
            unk.add(e["title"][:60])
        e.pop("txt", None)
        e.pop("detail", None)
    if unk:
        print("Viðburðir flokkaðir sjálfgefið (ekkert skýrt í titli eða lýsingu): %d – %s" % (len(unk), "; ".join(sorted(unk)[:40])))
    result.sort(key=lambda e: (e["start"], e.get("time") or ""))
    with open("events.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    with open("events_img.json", "w", encoding="utf-8") as f:
        json.dump(dict(list(imgs.items())[-1500:]), f, ensure_ascii=False)
    with open("events_detail.json", "w", encoding="utf-8") as f:
        json.dump(dict(list(det.items())[-1500:]), f, ensure_ascii=False)
    return result


FOTBOLTI_HOME = "https://fotbolti.net/"
FOTBOLTI_NAME = "Fótbolti.net"
# Þór/KA og KA/Þór fyrst (annars teldust bæði orðin sér), svo KA og Þór.
# Þór sem eiginnafn (Hlynur Þór, Þór Llorens, Þórsson) er ekki talið lið.
_TEAM_COMBO = re.compile(r"Þór ?/ ?KA|KA ?/ ?Þór")
_TEAM_KA = re.compile(r"(?<![\w/])KA(?![\w/])|(?<![\w/])KA-(?=[a-záðéíóúýþæö])")
_TEAM_THOR = re.compile(r"(?<![\w/])Þór(?:s(?!son\b|dóttir)\w*)?(?![\w/])")
_NAME_BEFORE = re.compile(r"[A-ZÁÐÉÍÓÚÝÞÆÖ][a-záðéíóúýþæö]+ $")
_NAME_AFTER = re.compile(r"^ (?!Ak\b|Akureyri)[A-ZÁÐÉÍÓÚÝÞÆÖ][a-záðéíóúýþæö]")


def team_mentions(text):
    """Telur hversu oft Þór, KA eða Þór/KA er nefnt sem lið (ekki mannsnafn)."""
    n = len(_TEAM_COMBO.findall(text))
    text = _TEAM_COMBO.sub(" ", text)
    n += len(_TEAM_KA.findall(text))
    for m in _TEAM_THOR.finditer(text):
        word = m.group(0)
        if word == "Þór":  # eintalan getur verið eiginnafn
            if _NAME_BEFORE.search(text[max(0, m.start() - 25):m.start()]):
                continue
            if _NAME_AFTER.match(text[m.end():m.end() + 20]):
                continue
        n += 1
    return n


_OTHER_CLUBS = re.compile(
    r"Breiðablik|Víking|Valur|Vals|FH\b|KR\b|Stjörn|Fram\b|ÍBV|ÍA\b|Skagamenn|Afturelding|Vestri|Fylki|HK\b|"
    r"Keflavík|Grindavík|Þrótt|Selfoss|Tindastól|Haukar|Hauka|Grótt|Njarðvík|Leikn|ÍR\b|Fjölni|Höttur|Hattar|"
    r"Aftureldingu|Víði|Völsung|Kormák|Magna|Húsavík|Ægi|Þrótti|Eyjam|Eyjak|Skagam|Garðbæ|Blik|Valsm|Fylkism|Keflvík|Grindvík|Njarðvík")


def _lead_order(lead):
    """Hvort kemur fyrst í inngangi: Akureyrarliðið eða annað lið? (til að sía viðtöl við andstæðinga)"""
    other = _OTHER_CLUBS.search(lead)
    if not other:
        return "ak"
    words = lead.split(" ")
    pos = 0
    for w in words:
        pos += len(w) + 1
        if ak_count(lead[:pos]):
            return "ak" if pos - len(w) - 1 <= other.start() else "other"
    return "other"


def judge_article(title, lead, paras, gated):
    """Strangt mat: fjallar greinin um Þór, KA eða Þór/KA (eða Akureyri)? Skilar (já/nei, ástæða).
    Viðtöl bera oft nafn viðmælanda í fyrirsögn, svo liðið er oft aðeins nefnt í inngangi."""
    if ak_count(title):
        return True, "í fyrirsögn"
    l = ak_count(lead)
    b = ak_count(" ".join(paras))
    if gated or not paras:  # áskriftargrein: aðeins útdrátturinn sést
        return (True, "í útdrætti (áskriftargrein)") if l else (False, "ekki í fyrirsögn né útdrætti")
    first = ak_count(" ".join(paras[:2]))
    n = l + b
    if n == 0:
        return False, "Þór/KA/KA/Akureyri ekki nefnt"
    others = len(_OTHER_CLUBS.findall(lead + " " + " ".join(paras)))
    if others > 2 * n:  # samantekt um margar viðureignir, ekki grein um liðið
        return False, "samantekt um mörg lið (%d nefningar á móti %d)" % (others, n)
    opponent = l >= 1 and _lead_order(lead) == "other"  # inngangur snýst um annað lið (t.d. viðtal við andstæðing)
    if l >= 1 and n >= 2 and len(paras) <= 8:
        if opponent:
            return False, "inngangur fjallar um annað lið en Þór/KA/KA (andstæðingur)"
        return True, "í inngangi stuttrar greinar/viðtals (%d nefningar)" % n
    if (l or first) and n >= 3 and not opponent:
        return True, "í upphafi og %d sinnum í texta" % n
    if n >= 6 and not opponent:
        return True, "%d sinnum í texta" % n
    return False, "nefnt %d sinnum, ekki aðalefni" % n


def _astro_unwrap(x):
    if isinstance(x, list) and len(x) == 2 and isinstance(x[0], int):
        return _astro_unwrap(x[1])
    if isinstance(x, list):
        return [_astro_unwrap(v) for v in x]
    if isinstance(x, dict):
        return {k: _astro_unwrap(v) for k, v in x.items()}
    return x


def fotbolti_article(url):
    """Les grein á fotbolti.net (gögnin eru felld inn í HTML síðunnar)."""
    req = urllib.request.Request(url, headers=UA)
    with OPENER.open(req, timeout=20) as r:
        raw = r.read(2000000).decode("utf-8", "ignore")
    m = re.search(r'props="([^"]*pageData[^"]*)"', raw)
    if not m:
        return None
    data = _astro_unwrap(json.loads(html.unescape(m.group(1))))
    a = (data.get("pageData") or {}).get("article")
    if not a:
        return None
    raw = [b.get("text") or "" for b in (a.get("body") or []) if isinstance(b, dict)]
    if not raw and a.get("bodyHtml"):
        raw = re.findall(r"<p[^>]*>(.*?)</p>", a["bodyHtml"], re.S)
    # ein „málsgrein“ hjá þeim getur innihaldið margar (aðskildar með línuskilum)
    paras = [clean(x) for r in raw for x in re.split(r"[\r\n]+", r)]
    paras = [p for p in paras if p]
    img = (a.get("heroImage") or {}).get("src") or ""
    if img.startswith("/"):
        img = "https://fotbolti.net" + img
    return {
        "title": clean(a.get("title") or ""),
        "lead": clean(a.get("lead") or a.get("seoDescription") or ""),
        "paras": paras,
        "gated": bool(a.get("gated") or a.get("isPremium")),
        "date": parse_date(a.get("publishedAt")),
        "image": img or None,
    }


FOTBOLTI_SEARCHES = ["Akureyri", "Þór", "KA", "Þór/KA"]
FOTBOLTI_DAYS = 10  # eldri greinar eru ekki teknar með


def _fotbolti_links(page):
    out = []
    for m in re.finditer(r'href="((?:https://(?:www\.)?fotbolti\.net)?/news/(\d\d)-(\d\d)-(\d{4})/[^"#?]+)"', page):
        u = m.group(1)
        if u.startswith("/"):
            u = "https://fotbolti.net" + u
        u = u.replace("://www.", "://")
        try:
            d = date(int(m.group(4)), int(m.group(3)), int(m.group(2)))
        except ValueError:
            continue
        if (datetime.now().date() - d).days > FOTBOLTI_DAYS:
            continue
        if u not in out:
            out.append(u)
    return out


def collect_fotbolti(checked, known, by_link, budget=120):
    """Finnur greinar á fotbolti.net (forsíða og leit að Akureyri, Þór, KA og Þór/KA), les hverja nýja
    grein og heldur aðeins þeim sem fjalla um liðin. Ákvörðun er geymd svo grein sé lesin einu sinni."""
    if not allowed(FOTBOLTI_HOME):
        print("X  Fótbolti.net: robots.txt leyfir ekki")
        return 0
    pages = [FOTBOLTI_HOME] + ["https://fotbolti.net/leita?search=" + urllib.parse.quote(q, safe="") for q in FOTBOLTI_SEARCHES]

    def get(u):
        try:
            req = urllib.request.Request(u, headers=UA)
            with OPENER.open(req, timeout=20) as r:
                return r.read(3000000).decode("utf-8", "ignore")
        except Exception as e:
            print("X  Fótbolti.net: tókst ekki að sækja %s (%s)" % (u, e))
            return ""

    links = []
    got = pmap(get, [u for u in pages if allowed(u)], workers=5)
    for page in got:
        for u in _fotbolti_links(page):
            if u not in links:
                links.append(u)
    key = lambda u: "fotbolti3:" + u
    todo = [u for u in links if key(u) not in checked and allowed(u)][:budget]
    print("OK Fótbolti.net: %d greinar fundnar (forsíða og leit), %d nýjar til yfirlestrar" % (len(links), len(todo)))

    def read(u):
        try:
            return fotbolti_article(u)
        except Exception as e:
            print("   X  gat ekki lesið %s (%s)" % (u, e))
            return "villa"

    arts = pmap(read, todo, workers=5)
    added = 0
    for u, art in zip(todo, arts):
        if art == "villa":
            continue
        if not art:
            print("   X  ólesanleg grein: %s" % u)
            continue
        ok, why = judge_article(art["title"], art["lead"], art["paras"], art["gated"])
        checked[key(u)] = bool(ok)
        print("   %s  %s  [%s]" % ("TEKIN  " if ok else "hafnað ", art["title"][:70], why))
        if not ok and by_link.pop(u, None) is not None:
            print("      (tekin af síðunni)")
        if ok and u not in by_link:
            by_link[u] = {
                "title": art["title"], "link": u, "summary": short(art["lead"]),
                "date": art["date"].isoformat() if art["date"] else None,
                "image": art["image"] or known.get(u) or og_image(u),
                "source": FOTBOLTI_NAME, "category": "Íþróttir",
            }
            added += 1
    print("   Fótbolti.net: %d greinar lesnar núna, %d teknar með" % (len(todo), added))
    return added


_AK_RE = re.compile(
    r"(?<!\w)(?:akureyr|eyjafj|eyjafirð|hlíðarfj|vaðlaheið|dalvík|hrísey|grímsey|grenivík|hörgársveit|"
    r"fjallabyggð|siglufj|ólafsfj|kjarnaskóg|norðurorka)\w*", re.I)
_OTHER_PLACES = re.compile(
    r"(?<!\w)(?:reykjav|kópavog|hafnarfj|garðab|keflavík|reykjanes|selfoss|ísafj|egilsst|vestmannaey|"
    r"borgarnes|akranes|grindavík|suðurnes|mosfellsb|seltjarnarn|höfuðborgarsv|húsavík|reyðarfj|neskaupst|"
    r"sauðárkr|blönduós|patreksfj|bolungarv|hveragerð|árborg)\w*", re.I)


def ak_count(text):
    """Staðarheiti á Akureyri/Eyjafirði, auk Þór, KA og Þór/KA sem lið."""
    return len(_AK_RE.findall(text)) + team_mentions(text)


def read_article_paras(url):
    """Sækir síðu og skilar málsgreinum (>40 stafir). None = tókst ekki, [] = enginn texti."""
    try:
        req = urllib.request.Request(url, headers=DEEP_UA)
        with OPENER.open(req, timeout=15) as r:
            page = r.read(600000).decode("utf-8", "ignore")
    except Exception:
        return None
    page = re.sub(r"<(nav|aside|footer|header|script|style|noscript)\b.*?</\1>", " ", page, flags=re.S | re.I)
    paras = [clean(p) for p in re.findall(r"<p[^>]*>(.*?)</p>", page, re.S | re.I)]
    return [p for p in paras if len(p) > 40]


def judge_regional(title, paras):
    """Fjallar frétt landsmiðils um Akureyri og nágrenni? Ekki nóg að það sé nefnt.
    Skilar (já/nei, ástæða)."""
    if ak_count(title):
        return True, "í fyrirsögn"
    if not paras:
        return False, "ólesanleg og ekki í fyrirsögn"
    lead = ak_count(" ".join(paras[:2]))
    body = ak_count(" ".join(paras))
    others = len(_OTHER_PLACES.findall(" ".join(paras)))
    hit_par = sum(1 for p in paras if ak_count(p))
    share = hit_par / len(paras)
    if ak_count(paras[0]) >= 1 and others == 0 and len(paras) <= 5:
        return True, "stutt frétt sem gerist á Akureyri"
    if lead >= 1 and body >= 3 and share >= 0.4 and body >= others:
        return True, "%d nefningar í %d af %d málsgreinum" % (body, hit_par, len(paras))
    return False, "nefnt %d sinnum í %d af %d málsgreinum, önnur staðarheiti %d" % (body, hit_par, len(paras), others)


def pmap(fn, items, workers=6):
    """Keyrir fn á öllum hlutum samtímis (til að spara tíma við netbeiðnir)."""
    items = list(items)
    if not items:
        return []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(fn, items))


# --- Flokkar: fréttir geta verið í fleiri en einum flokki; viðburðir fá eina tegund ---
NEWS_CAT_MAP = {"Fréttamiðlar": ["Fréttir"], "Nærsveitir": ["Nærsveitir"], "Íþróttir": ["Íþróttir"]}  # annað fer í Bæinn
SPORT_NEWS = re.compile(
    r"handbolt|fótbolt|knattspyrn|körfubolt|körfuknattleik|blak\b|blaki|íshokkí|skautahlaup|íþrótt|skíðagang|skíðamót|golfmót|"
    r"íslandsmeist|bikarmeist|bikarkeppni|landsliðs|landsliðið|úrvalsdeild|olís|bónus deild|lengjudeild|besta deild|mjólkurbikar|"
    r"powerade|sundmót|sundmeist|götuhlaup|maraþon|akureyrarhlaup|crossfit|karate|júdó|þjálfari|þjálfarinn|íþróttafélag|"
    r"íþróttamaður|íþróttakona|deildarmeist|úrslitakeppni|marki\b|mörk\b|markmann", re.I)


NEWS_EXTRA = {"Trölli.is": ["Nærsveitir"], "Dal.is": ["Nærsveitir"]}  # svæðismiðlar utan Akureyrar: bæði Fréttir og Nærsveitir


def news_cats(item):
    base = NEWS_CAT_MAP.get(item.get("category"), ["Bærinn"])[:]
    for c in NEWS_EXTRA.get(item.get("source"), []):
        if c not in base:
            base.append(c)
    if base == ["Fréttir"]:
        text = (item.get("title") or "") + " " + (item.get("summary") or "")
        if SPORT_NEWS.search(text) or team_mentions(text) > 0:
            base.append("Íþróttir")
    return base


KIND_RULES = [
    ("Uppistand", re.compile(r"uppistand|stand-?up|comedy|grínist|grínsýning|grínari|fyndn", re.I)),
    ("Fjölskylda", re.compile(r"barnasýning|barnaleik|barnatónleik|fjölskyldu|krakka|jólasvein|brúðuleik|börn|skoppa|karíus|lína langsokkur", re.I)),
    ("Fræðsla", re.compile(r"námskeið|fyrirlest|ráðstefn|vinnustofa|málþing|workshop|kennari á námskeiði", re.I)),
    ("Leiklist", re.compile(r"leikrit|leiksýning|söngleik|leikhús|leikfélag|einleik|leikstjór|leikarar|leikari|leikmynd|frumsýn|ballett|óperu|ópera|improv|dansverk|leikmuni", re.I)),
    ("Sýningar", re.compile(r"myndlistarsýning|ljósmyndasýning|málverkasýning|listsýning|opnun sýningar|sýningaropnun", re.I)),
    ("Tónlist", re.compile(r"tónleik|hljómleik|hljómsveit|kvartett|sinfón|konsert|jazz|blús|\bdj\b|trúbador|kór\b|söngkona|söngvari|söngkvartett|flytjend|efnisskrá|tónlistarfólk|tónlist|píanó|fiðl|gítar|trommu|bassa", re.I)),
]
TIX_KIND = {"tónleikar": "Tónlist", "tónlist": "Tónlist", "leikhús": "Leiklist", "leiksýning": "Leiklist", "uppistand": "Uppistand",
            "fjölskyldan": "Fjölskylda", "fyrir börn": "Fjölskylda", "námskeið": "Fræðsla", "íþróttir": "Íþróttir"}


def _kind_counts(text):
    return {kind: len(rx.findall(text or "")) for kind, rx in KIND_RULES}


def _pick(counts, strict):
    """Velur tegund aðeins ef ein er greinilega ríkjandi. Strangt (titill): ein tegund og engin önnur.
    Annars (lýsing): sú sem hefur að minnsta kosti tvöfalt fleiri orð en næsta tegund."""
    pos = sorted(((n, k) for k, n in counts.items() if n > 0), reverse=True)
    if not pos:
        return None
    if len(pos) == 1:
        return pos[0][1]
    if strict:
        return None
    return pos[0][1] if pos[0][0] >= 2 * pos[1][0] and pos[0][0] >= 2 else None


def event_kind(e):
    """Tegund viðburðar – aðeins ef hún er örugg (flokkur frá Tix, skýrt orð í titli, eða ríkjandi orð í lýsingu).
    Annars er skilað None og viðburðurinn sést bara undir „Allt“."""
    if e.get("source") == "Íþróttir" or e.get("sport"):
        return "Íþróttir"
    c = (e.get("cat0") or "").strip().lower()
    for k, v in TIX_KIND.items():
        if c.startswith(k):
            return v
    k = _pick(_kind_counts(e.get("title") or ""), True)
    if k:
        return k
    return _pick(_kind_counts(e.get("txt") or ""), False)


def kind_default(e):
    """Síðasta úrræði þegar hvorki flokkur, titill né lýsing segir til: eftir stað, annars tónlist."""
    venue = (e.get("venue") or "").lower()
    if "samkomuhús" in venue:
        return "Leiklist"
    return "Tónlist"


def main():
    t_start = time.time()
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

    nonlocal_sources = {f["name"] for f in FEEDS if not f["local"]}
    V = "v2:"  # ný og strangari sía; gamlar niðurstöður (án V) eru ekki notaðar

    def get_feed(feed):
        try:
            req = urllib.request.Request(feed["url"], headers=UA)
            with OPENER.open(req, timeout=15) as r:
                return parse_feed(ET.fromstring(r.read())), None
        except Exception as e:
            return None, e

    results = pmap(get_feed, FEEDS, workers=8)
    print("Tími: veitur sóttar á %.0f sek." % (time.time() - t_start))

    # Staðbundnir miðlar koma allir inn; landsmiðlar fara í biðröð til yfirlesturs.
    cands = {}
    for feed, (items, err) in zip(FEEDS, results):
        if items is None:
            print("X  %s: tókst ekki að sækja (%s)" % (feed["name"], err))
            continue
        kept = []
        for i in items:
            if not (i["link"] and i["title"]):
                continue
            if feed["local"]:
                kept.append(i)
            elif i["link"] not in cands:
                cands[i["link"]] = (i, feed)
        print("OK %s: %d fréttir sóttar%s" % (feed["name"], len(items), "" if feed["local"] else " (bíða yfirlesturs)"))
        for i in kept:
            i["image"] = i["image"] or known.get(i["link"])
            i["source"] = feed["name"]
            i["category"] = feed["cat"]
            i["date"] = i["date"].isoformat() if i["date"] else None
            if i["link"] not in by_link:
                new_count += 1
            by_link[i["link"]] = i

    # Hvað þarf að lesa: fyrst eldri landsmiðlafréttir á síðunni, svo nýjar (með staðarheiti í fyrirsögn/útdrætti fyrst).
    old_nl = [l for l, o in by_link.items() if o.get("source") in nonlocal_sources and V + l not in checked]
    order = sorted(cands.values(), key=lambda c: 0 if about_akureyri(c[0]) else 1)
    todo = []
    for l in old_nl + [c[0]["link"] for c in order if c[0]["link"] not in by_link and V + c[0]["link"] not in checked]:
        if l not in todo:
            todo.append(l)
    todo = [l for l in todo if allowed(l)][:budget]
    budget -= len(todo)
    t_read = time.time()
    pre = dict(zip(todo, pmap(read_article_paras, todo, workers=6)))
    print("Tími: %d fréttir lesnar á %.0f sek." % (len(todo), time.time() - t_read))

    def judge_link(link, title):
        key = V + link
        if key in checked:
            return checked[key]
        paras = pre.get(link)
        if paras is None:  # ekki sótt (tókst ekki eða enginn tími) – reynt aftur næst
            return None
        ok, why = judge_regional(title, paras)
        checked[key] = bool(ok)
        print("   %s  %s  [%s]" % ("TEKIN  " if ok else "hafnað ", title[:70], why))
        return bool(ok)

    purged = 0
    for l, o in list(by_link.items()):
        if o.get("source") in nonlocal_sources and judge_link(l, o.get("title", "")) is False:
            del by_link[l]
            purged += 1
    if purged:
        print("Strangari sía: %d eldri fréttir landsmiðla teknar af síðunni" % purged)

    accepted = {}
    for i, feed in order:
        if i["link"] in by_link:
            continue
        if judge_link(i["link"], i["title"]):
            i["image"] = i["image"] or known.get(i["link"])
            i["source"] = feed["name"]
            i["category"] = feed["cat"]
            i["date"] = i["date"].isoformat() if i["date"] else None
            by_link[i["link"]] = i
            new_count += 1
            accepted[feed["name"]] = accepted.get(feed["name"], 0) + 1
    print("Landsmiðlar: %s teknir með í þessari keyrslu" % (accepted or "engin ný frétt"))

    # Myndir sem vantar eru sóttar samtímis
    noimg = [l for l, o in by_link.items() if not o.get("image")]
    for l, im in zip(noimg, pmap(og_image, noimg, workers=6)):
        by_link[l]["image"] = im
    print("Tími: fréttir tilbúnar á %.0f sek." % (time.time() - t_start))

    try:
        new_count += collect_fotbolti(checked, known, by_link)
    except Exception as e:
        print("X  Fótbolti.net: óvænt villa (%s)" % e)

    with open("athugad.json", "w", encoding="utf-8") as f:
        json.dump(dict(list(checked.items())[-4000:]), f, ensure_ascii=False)
    print("Yfirlestur: %d síður lesnar núna, %d niðurstöður í minni." % (DEEP_BUDGET - budget, len(checked)))

    merged, per_source = [], {}
    age_cut = (date.today() - timedelta(days=MAX_AGE_DAYS)).isoformat()
    for i in sorted(by_link.values(), key=lambda i: i["date"] or "", reverse=True):
        if i["date"] and i["date"][:10] < age_cut:
            continue
        per_source[i["source"]] = per_source.get(i["source"], 0) + 1
        if per_source[i["source"]] <= MAX_BY_SOURCE.get(i["source"], 30):
            merged.append(i)
    for i in merged:
        i["cats"] = news_cats(i)
    with open("news.json", "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    def timed(name, fn):
        t0 = time.time()
        try:
            return fn(), None
        except Exception as e:
            return None, e
        finally:
            print("Tími: %s tók %.0f sek." % (name, time.time() - t0))

    # Viðburðir og töflur eru óháð hvort öðru og keyra samtímis
    with ThreadPoolExecutor(max_workers=2) as ex:
        f_ev = ex.submit(timed, "viðburðir", collect_events)
        f_st = ex.submit(timed, "töflur", lambda: collect_standings(datetime.now().date()))
        events, err = f_ev.result()
        if err is not None:
            print("X  Viðburðir: óvænt villa (%s)" % err)
            events = _load("events.json", [])
        stand, err = f_st.result()
        if err is not None:
            print("X  Töflur: óvænt villa (%s)" % err)
            stand = _load("standings.json", [])
    try:
        offers = load_offers(datetime.now().date())
    except Exception as e:
        print("X  Tilboð: villa (%s)" % e)
        offers = []
    try:
        flights = load_flights(datetime.now().date())
    except Exception as e:
        print("X  Flug: villa (%s)" % e)
        flights = []
    write_html(merged, events, offers, stand, flights, load_weather())
    print("Tími alls: %.0f sek." % (time.time() - t_start))
    print("Búið. %d fréttir í news.json (%d nýjar). Opnaðu index.html til að sjá þær." % (len(merged), new_count))


if __name__ == "__main__":
    main()
