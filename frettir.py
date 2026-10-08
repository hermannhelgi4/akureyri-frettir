#!/usr/bin/env python3
"""Sækir fréttir úr RSS-veitum, síar landsmiðla eftir Akureyri og býr til news.json."""
import json, re, html, urllib.request
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
    {"name": "Vísir", "url": "https://www.visir.is/rss/innlent", "local": False, "cat": "Fréttamiðlar"},  # (óstaðfest)
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
    "þór/ka", "norðurorka", "samherj", "kjarnaskóg",
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
main{display:grid;gap:10px;padding-bottom:40px}
a.item{display:flex;gap:12px;background:var(--card);border:1px solid var(--bd);border-radius:14px;padding:10px;text-decoration:none;color:inherit}a.item:hover{border-color:var(--ac)}
.img{flex:0 0 96px;height:96px;border-radius:10px;background:var(--ac);color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:13px;overflow:hidden;text-align:center}.img img{width:100%;height:100%;object-fit:cover}
.body{min-width:0;flex:1}.meta{font-size:12px;color:var(--mu);margin-bottom:4px}.src{color:var(--ac);font-weight:700}
h2{font-size:16px;margin:0 0 4px;line-height:1.3}p{margin:0;font-size:13px;color:var(--mu);display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
</style></head><body><header><h1>Akureyri í fréttum</h1><div class="sub" id="upd"></div></header><div class="chips" id="chips"></div><main id="list"></main>
<script>
const NEWS=__DATA__;let cur="Allt";NEWS.forEach(n=>{n.category=n.category||"Fréttamiðlar"});const ORDER=["Fréttamiðlar","Bærinn","Menntun","Menning","Íþróttir","Fyrirtæki & félög"];
function ago(d){if(!d)return"";const m=(Date.now()-new Date(d))/6e4;if(m<60)return"fyrir "+Math.max(1,Math.round(m))+" mín.";if(m<1440)return"fyrir "+Math.round(m/60)+" klst.";return"fyrir "+Math.round(m/1440)+" d."}
function el(t,c,x){const e=document.createElement(t);if(c)e.className=c;if(x)e.textContent=x;return e}
function render(){const names=["Allt",...ORDER.filter(c=>NEWS.some(n=>n.category===c))];const ch=document.getElementById("chips");ch.innerHTML="";
names.forEach(n=>{const b=el("button","chip"+(n===cur?" on":""),n);b.onclick=()=>{cur=n;render()};ch.appendChild(b)});
const l=document.getElementById("list");l.innerHTML="";
NEWS.filter(n=>cur==="Allt"||n.category===cur).forEach(n=>{const a=el("a","item");a.href=n.link;a.target="_blank";a.rel="noopener";
const im=el("div","img");if(n.image){const i=document.createElement("img");i.src=n.image;i.loading="lazy";i.referrerPolicy="no-referrer";i.onerror=()=>{i.remove();im.textContent=n.source};im.appendChild(i)}else im.textContent=n.source;
const b=el("div","body");const m=el("div","meta");m.appendChild(el("span","src",n.source));m.appendChild(document.createTextNode(" · "+ago(n.date)));
b.append(m,el("h2","",n.title));if(n.summary&&n.summary.length>3)b.append(el("p","",n.summary));a.append(im,b);l.appendChild(a)})}
document.getElementById("upd").textContent="Uppfært __TIME__";render();
</script></body></html>"""


def write_html(items):
    data = json.dumps(items, ensure_ascii=False).replace("</", "<\\/")
    page = HTML.replace("__DATA__", data).replace("__TIME__", datetime.now().strftime("%d.%m.%Y %H:%M"))
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(page)


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

    for feed in FEEDS:
        try:
            req = urllib.request.Request(feed["url"], headers=UA)
            with OPENER.open(req, timeout=20) as r:
                items = parse_feed(ET.fromstring(r.read()))
        except Exception as e:
            print("X  %s: tókst ekki að sækja (%s)" % (feed["name"], e))
            continue
        kept = [i for i in items if i["link"] and i["title"] and (feed["local"] or about_akureyri(i))]
        print("OK %s: %d fréttir sóttar, %d teknar með" % (feed["name"], len(items), len(kept)))
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

    merged, per_source = [], {}
    for i in sorted(by_link.values(), key=lambda i: i["date"] or "", reverse=True):
        per_source[i["source"]] = per_source.get(i["source"], 0) + 1
        if per_source[i["source"]] <= MAX_BY_SOURCE.get(i["source"], 30):
            merged.append(i)
    with open("news.json", "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    write_html(merged)
    print("Búið. %d fréttir í news.json (%d nýjar). Opnaðu index.html til að sjá þær." % (len(merged), new_count))


if __name__ == "__main__":
    main()
