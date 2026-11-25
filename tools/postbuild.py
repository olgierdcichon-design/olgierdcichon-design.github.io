#!/usr/bin/env python3
"""SEO / migration post-processing for the SLOY static export.

Usage (from the repository root, on a fresh `next build` export):
    python3 tools/postbuild.py .            # staging: pages carry noindex
    python3 tools/postbuild.py . --live     # production: no noindex

What it does (all edits keep the existing design):
  * Product JSON-LD: adds offers (price, PLN, availability), sku, brand,
    return policy.
  * Category pages /oswietlenie/, /meble/, /dodatki/ (clones of /kolekcja/
    with filtered items and SEO texts carried over from Shopify collections).
  * Legal pages /regulamin/ (full text), /polityka-prywatnosci/, /cookies/,
    /odstapienie-od-umowy/ (content moved from Shopify).
  * Cookie consent + Google Analytics 4 (only on sloy.pl).
  * noindex on every page while staging (removed by tools/go_live.py).
  * sitemap.xml update.
The .htaccess with 301 redirects is a static file kept in the repo root.
"""
import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from nextpage import Page, all_routes, find_element, jesc  # noqa: E402
import collection as col  # noqa: E402
from content import El, parse, to_html, flight_json, esc  # noqa: E402

GA_ID = 'G-R2WHKJCEG4'
STAMP = '.sloy-postbuild'

# Shopify vendors that are real brands (others such as "SLOY", "Unknown" skipped)
BRANDS = {
    'fotele-hestra-tord-bjorklund-ikea-postmodernizm-1991': 'IKEA',
    'niebieska-lampka-artemide-microlight-ernesto-gismondi': 'Artemide',
    'pomaranczowa-lampka-artemide-microlight-ernesto-gismondi': 'Artemide',
    'lampa-podlogowa-richard-sapper-tizio-terra-artemide-wlochy-1972': 'Artemide',
    'lampa-biurkowa-haba-szlaban-kolejowy-niemcy-lata-90': 'HABA',
    'sofa-vico-magistretti-veranda-portovenere-cassina-wlochy-1989': 'Cassina',
    'sofa-vico-magistretti-veranda-3-osobowa-cassina-wlochy-1984': 'Cassina',
    'sofa-veranda-vico-magistretti-cassina-wlochy-1983': 'Cassina',
    'siedzisko-lowland-patricia-urquiola-moroso-wlochy-lata-2000': 'Moroso',
    'pufa-sushi-donut-edward-van-vliet-moroso-blue-edition': 'Moroso',
    '2-kinkiety-lumina-emi-tommaso-cimini-wlochy-lata-80': 'Lumina',
    'stolik-kawowy-albert-busch-alburette-wzor-lisci-niemcy-lata-60': 'Alburette',
    'stolik-kawowy-albert-busch-alburette-niemcy-lata-60': 'Alburette',
    'lampa-podlogowa-ettore-sottsass-id-s-zumtobel-staff-austria-1987': 'Zumtobel Staff',
    'zestaw-krzesla-lord-yo-stol-lord-yi-philippe-starck-driade-wlochy-lata-90': 'Driade',
    'stolik-kawowy-waterfall-fredrikson-stallard-driade': 'Driade',
    'lampka-nocna-heico-w-ksztalcie-misia-niemcy-lata-80': 'Heico',
    'lampka-heico-w-ksztalcie-krowy-niemcy-lata-80': 'Heico',
    'lampa-stolowa-kot-z-klebkiem-welny-heico-niemcy-lata-80': 'Heico',
    'lampka-nocna-mis-heico-pomaranczowa-lata-80': 'Heico',
    'talerz-okolicznosciowy-kaiser-pfalzbau-ludwigshafen-niemcy-1968': 'Kaiser',
    'fotel-zen-claude-brisson-ligne-roset-francja-lata-80': 'Ligne Roset',
    'fotel-zen-claude-brisson-ligne-roset-francja-1984': 'Ligne Roset',
    '2-kinkiety-ceramiczne-pan-leuchten-fat-lava-lata-70': 'Pan Leuchten',
    'bialo-szary-kinkiet-ceramiczny-ufo-pan-leuchten-niemcy-lata-70': 'Pan Leuchten',
    'kinkiet-ceramiczny-pan-leuchten-fat-lava-new-old-stock': 'Pan Leuchten',
    'kinkiet-ceramiczny-lampa-ufo-pan-leuchten-lata-70': 'Pan Leuchten',
    'azurowa-patera-ceramiczna-vallauris-francja-lata-50': 'Vallauris',
    'wazon-soholm-maria-philippi-seria-nordlys-dania-lata-60': 'Søholm',
    'fob-sosnowiec-dog-tray-poland-1970s-1980s': 'FOB Sosnowiec',
    'pottestuen-keramik-desk-organizer-frederikshavn-denmark-1960s': 'Pottestuen Keramik',
    'messow-blue-gummy-bear-floor-lamp-1970s-germany': 'Messow',
    'lampka-nocna-mis-messow-zielona-lata-80': 'Messow',
    'lampa-podlogowa-mis-messow-zielona-lata-80': 'Messow',
    'vintage-modular-vinyl-record-holder-zzg-veritas-poland-1970s': 'ZZG Veritas',
    'brutalistyczna-plaskorzezba-dantoft-dunska-rzezba-ze-szkla-i-metalu': 'Dantoft',
    'lampa-stolowa-energy-light-samuel-parker-slamp-wlochy': 'Slamp',
    'skarbonka-skotten-czerwona-stig-lindberg-szwecja-1961': 'Gustavsberg',
    'skarbonka-skotten-niebieska-stig-lindberg-szwecja-1961': 'Gustavsberg',
    'waga-kuchenna-skladana-soehnle-bezowa': 'Soehnle',
    'organizer-na-biurko-herlitz-big-butler-niemcy-lata-80-90': 'Herlitz',
    'wazon-optyczny-bullet-nr-914-rudolf-schrotter-sklo-union-rosice': 'Sklo Union',
    'talerz-kamionkowy-brutalistyczny-axella-dania-lata-70': 'Axella',
    'swiecznik-erik-hoglund-bo-svensk-szwecja-lata-60': 'Boda',
    'taca-psychodeliczna-elite-trays-wielka-brytania-lata-70-80': 'Elite Trays',
    'stojak-na-plyty-winylowe-odeon-szwecja-lata-60-70': 'Odeon',
}

CATEGORIES = [
    dict(route='oswietlenie', cat='Oświetlenie', h1='Oświetlenie',
         title='Oświetlenie vintage designerskie – Artemide, space age, lampy włoskie | SLOY',
         desc='Oświetlenie vintage od kultowych projektantów. Lampy podłogowe, biurkowe, kinkiety Artemide '
              'i Lumina. Space age, modernizm z połowy XX wieku. Lata 70. i 90. XX wieku. Testowane elektrycznie.',
         lead='Lampy podłogowe, biurkowe i kinkiety od kultowych projektantów: Artemide, Lumina, Pan Leuchten. '
              'Space age i modernizm z drugiej połowy XX wieku. Każdą lampę testujemy elektrycznie.'),
    dict(route='meble', cat='Meble', h1='Meble',
         title='Designerskie meble vintage – mid-century modern, space age, postmodernizm | SLOY',
         desc='Wyselekcjonowane meble vintage od kultowych projektantów. Sofy w stylu mid-century modern, '
              'fotele space age, stoły postmodernistyczne. Cassina, Moroso, Ligne Roset, Driade.',
         lead='Sofy, fotele i stoliki od kultowych projektantów i manufaktur: Cassina, Moroso, Ligne Roset, '
              'Driade. Mid-century modern, space age i postmodernizm.'),
    dict(route='dodatki', cat='Dodatki', h1='Dodatki',
         title='Dodatki vintage – ceramika fat lava, brutalizm, przedmioty kolekcjonerskie | SLOY',
         desc='Przedmioty vintage i kolekcjonerskie. Zachodnioniemiecka ceramika fat lava, brutalizm, '
              'skandynawskie szkło i ceramika, pamiątki z PRL. Lata 60. i 70. XX wieku, starannie wyselekcjonowane.',
         lead='Ceramika fat lava, brutalistyczne szkło i metal, skandynawska ceramika i drobiazgi z PRL. '
              'Przedmioty z historią, które od razu zmieniają wnętrze.'),
]

LEGAL = [
    dict(route='regulamin', file='regulamin.md', h1='Regulamin sklepu', nav='Regulamin sklepu',
         title='Regulamin sklepu | SLOY',
         desc='Regulamin sklepu internetowego SLOY: zamówienia, płatności, dostawa, odstąpienie od umowy i reklamacje.'),
    dict(route='polityka-prywatnosci', file='polityka-prywatnosci.md', h1='Polityka prywatności',
         nav='Polityka prywatności', title='Polityka prywatności (RODO) | SLOY',
         desc='Informacja o ochronie danych osobowych (RODO) w sklepie SLOY: administrator, cele przetwarzania, Twoje prawa.'),
    dict(route='cookies', file='cookies.md', h1='Pliki cookie', nav='Pliki cookie',
         title='Pliki cookie | SLOY',
         desc='Jakich plików cookie używa sloy.pl, w jakim celu i jak zmienić swoją zgodę.'),
    dict(route='odstapienie-od-umowy', file='odstapienie-od-umowy.md', h1='Odstąpienie od umowy i reklamacje',
         nav='Odstąpienie i reklamacje', title='Formularz odstąpienia od umowy i reklamacji | SLOY',
         desc='Wzór formularza odstąpienia od umowy oraz formularz zgłoszenia reklamacji w sklepie SLOY.'),
]

COMPANY = ('Optiwriting Sp. z o. o., ul. Zygmunta Augusta 5/2, 31-504 Kraków. KRS 0001055905, '
           'NIP 6751787340, REGON 526268913. Magazyn: ul. Przewóz 34 (wjazd od ul. Myśliwskiej), 30-716 Kraków.')


def log(*a):
    print('[postbuild]', *a)


# ------------------------------------------------------------------ helpers
def lots_span(text):
    i = text.find('"lots":[')
    if i < 0:
        return None
    i += len('"lots":')
    return i, find_element(text, i)


def replace_meta(p, old_title, new_title, old_desc, new_desc, old_canon, new_canon):
    for o, n in ((old_title, new_title), (old_desc, new_desc), (old_canon, new_canon)):
        p.fsub('"' + jesc(o) + '"', '"' + jesc(n) + '"')
    p.hsub('<title>' + esc(old_title) + '</title>', '<title>' + esc(new_title) + '</title>')
    p.hsub('content="' + esc(old_title) + '"', 'content="' + esc(new_title) + '"', count=None)
    p.hsub('content="' + esc(old_desc) + '"', 'content="' + esc(new_desc) + '"', count=None)
    p.hsub('href="' + old_canon + '"', 'href="' + new_canon + '"')


def clone_route(root, src, dst):
    """Copy page dir src -> dst renaming the route segment in payload + file names."""
    sdir, ddir = os.path.join(root, src), os.path.join(root, dst)
    if os.path.exists(ddir):
        shutil.rmtree(ddir)
    os.makedirs(ddir)
    for name in os.listdir(sdir):
        if os.path.isfile(os.path.join(sdir, name)):
            shutil.copy(os.path.join(sdir, name), os.path.join(ddir, name.replace(f'__next.{src}.', f'__next.{dst}.')))
    p = Page(root, dst)
    p.fsub(f'"s":"{src}"', f'"s":"{dst}"')
    p.fsub(f'"c":["","{src}",""]', f'"c":["","{dst}",""]')
    return p


# ------------------------------------------------------------------ products
def patch_products(root):
    n = 0
    for route in all_routes(root):
        if not route.startswith('lot/'):
            continue
        p = Page(root, route)
        slug = route.split('/', 1)[1]
        span = None
        i = p.inline.find('"lot":{"id"')
        assert i >= 0, route
        s = i + len('"lot":')
        # find matching brace
        depth, k, in_str = 0, s, False
        while True:
            ch = p.inline[k]
            if in_str:
                if ch == '\\':
                    k += 2
                    continue
                if ch == '"':
                    in_str = False
            elif ch == '"':
                in_str = True
            elif ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    break
            k += 1
        lot = json.loads(p.inline[s:k + 1])
        m = re.search(r'<script type="application/ld\+json">(\{"@context":"https://schema\.org","@type":"Product".*?)</script>', p.html)
        old = m.group(1)
        ld = json.loads(old)
        url = f'https://sloy.pl/lot/{slug}/'
        ld['url'] = url
        if lot.get('sku'):
            ld['sku'] = lot['sku']
        if slug in BRANDS:
            ld['brand'] = {'@type': 'Brand', 'name': BRANDS[slug]}
        if lot.get('category'):
            ld['category'] = lot['category']
        if lot.get('price') is not None:
            ld['offers'] = {
                '@type': 'Offer', 'url': url, 'priceCurrency': 'PLN', 'price': lot['price'],
                'availability': 'https://schema.org/InStock' if lot['status'] == 'dostepny' else 'https://schema.org/SoldOut',
                'itemCondition': 'https://schema.org/UsedCondition',
                'seller': {'@type': 'Organization', 'name': 'SLOY'},
                'hasMerchantReturnPolicy': {
                    '@type': 'MerchantReturnPolicy', 'applicableCountry': 'PL',
                    'returnPolicyCategory': 'https://schema.org/MerchantReturnFiniteReturnWindow',
                    'merchantReturnDays': 14, 'returnMethod': 'https://schema.org/ReturnByMail',
                    'returnFees': 'https://schema.org/ReturnShippingFees'},
            }
        new = json.dumps(ld, ensure_ascii=False, separators=(',', ':'))
        p.hsub('>' + old + '<', '>' + new + '<')
        p.fsub(jesc(old), jesc(new))
        p.save()
        n += 1
    log('product JSON-LD updated:', n)


# ------------------------------------------------------------------ categories
def card_map(root):
    cards = {}
    for route in ('kolekcja', 'archiwum'):
        h = Page(root, route).html
        for m in re.finditer(r'<a class="card[^"]*"[^>]*href="/lot/([^/]+)/".*?</a>', h, re.S):
            cards.setdefault(m.group(1), m.group(0))
    return cards


def validate_port(root):
    for route in ('kolekcja', 'archiwum'):
        p = Page(root, route)
        a, b = lots_span(p.inline)
        lots = json.loads(p.inline[a:b])
        h = p.html
        axis = h[h.index('<div class="axis"'):h.index('<p class="axis__legend"')]
        # style attributes may be serialized differently (e.g. "background: rgb(...)"),
        # React does not compare attributes on hydration, so compare structure + text only
        nost = lambda s: re.sub(r' style="[^"]*"', '', s)
        assert nost(axis) == nost(col.axis_html(lots)), 'axis port mismatch on ' + route
        order = re.findall(r'<a class="card[^"]*"[^>]*href="/lot/([^/]+)/"', h[h.index('<div class="grid">'):])
        assert order == [l['slug'] for l in col.mix_order(lots)], 'order port mismatch on ' + route


def make_categories(root):
    validate_port(root)
    cards = card_map(root)
    src = Page(root, 'kolekcja')
    a, b = lots_span(src.inline)
    avail = json.loads(src.inline[a:b])
    pa = Page(root, 'archiwum')
    a2, b2 = lots_span(pa.inline)
    sold = json.loads(pa.inline[a2:b2])
    old_lead = 'Wszystko, co teraz stoi w krakowskim magazynie. Większość rzeczy mamy w pojedynczych egzemplarzach.'
    for c in CATEGORIES:
        lots = [l for l in avail if l['category'] == c['cat']]
        heading = 'przedmiotów w magazynie'
        lead = c['lead']
        if not lots:  # nothing in stock: show what we sold in this category
            lots = [l for l in sold if l['category'] == c['cat']]
            heading = 'w archiwum sprzedanych'
            lead += ' Wszystkie znalazły już nowe domy – zamów poszukiwanie, a znajdziemy podobny.'
        p = clone_route(root, 'kolekcja', c['route'])
        # --- payload
        a, b = lots_span(p.inline)
        new_lots = json.dumps(lots, ensure_ascii=False, separators=(',', ':'))
        p.fsub(p.inline[a:b] + ',"heading":"przedmiotów w magazynie"', new_lots + ',"heading":"' + jesc(heading) + '"')
        p.fsub('"data-intro":true,"children":"Kolekcja"}', '"data-intro":true,"children":"' + jesc(c['h1']) + '"}')
        p.fsub('"children":"' + jesc(old_lead) + '"', '"children":"' + jesc(lead) + '"')
        replace_meta(p, 'Kolekcja | SLOY', c['title'],
                     'Meble, oświetlenie i dodatki vintage z magazynu SLOY w Krakowie. Filtruj po dekadzie, kategorii i sposobie dostawy.',
                     c['desc'], 'https://sloy.pl/kolekcja/', f'https://sloy.pl/{c["route"]}/')
        # --- html
        p.hsub('<h1 data-split="lines" data-intro="true">Kolekcja</h1>', f'<h1 data-split="lines" data-intro="true">{esc(c["h1"])}</h1>')
        p.hsub('<p>' + esc(old_lead) + '</p>', '<p>' + esc(lead) + '</p>')
        h = p.html
        a0, a1 = h.index('<div class="axis"'), h.index('<p class="axis__legend"')
        p.html = h[:a0] + col.axis_html(lots) + h[a1:]
        h, k = re.subn(r'<p aria-live="polite"><span class="data">\d+</span> <!-- -->przedmiotów w magazynie</p>',
                       f'<p aria-live="polite"><span class="data">{len(lots)}</span> <!-- -->{esc(heading)}</p>', p.html)
        assert k == 1, 'toolbar not found'
        p.html = h
        g0 = h.index('<div class="grid">') + len('<div class="grid">')
        g1 = h.index('</div></div></div></div><!--$-->', g0)
        p.html = h[:g0] + ''.join(cards[l['slug']] for l in col.mix_order(lots)) + h[g1:]
        p.save()
        log(f'category /{c["route"]}/: {len(lots)} items')


# ------------------------------------------------------------------ legal pages
def legal_element(page):
    nav = []
    for d in LEGAL:
        props = {'className': 'link', 'href': f'/{d["route"]}/'}
        if d['route'] == page['route']:
            props['aria-current'] = 'page'
        nav.append(El('li', {}, [El('a', props, [d['nav']])]))
    with open(os.path.join(HERE, 'content', page['file']), encoding='utf-8') as f:
        blocks = parse(f.read())
    return El('div', {'className': 'page'}, [
        El('header', {'className': 'page-head'}, [
            El('h1', {}, [page['h1']]),
            El('ul', {'className': 'legal doc-nav', 'aria-label': 'Dokumenty'}, nav),
        ]),
        El('div', {'className': 'doc'}, blocks + [El('p', {'className': 'doc__company'}, [COMPANY])]),
    ])


def make_legal(root):
    tpl = Page(root, 'regulamin')
    i = tpl.inline.index('["$","div",null,{"className":"page"')
    old_el = tpl.inline[i:find_element(tpl.inline, i)]
    old_title, old_desc = 'Regulamin i prywatność | SLOY', 'Dane sprzedawcy SLOY oraz odnośniki do regulaminu, polityki prywatności i zasad zwrotu.'
    backup = os.path.join(root, '.regulamin-template')
    if os.path.exists(backup):
        shutil.rmtree(backup)
    shutil.copytree(os.path.join(root, 'regulamin'), backup)
    for page in LEGAL:
        if page['route'] == 'regulamin':
            p = Page(root, 'regulamin')
        else:
            # clone from the untouched template copy
            ddir = os.path.join(root, page['route'])
            if os.path.exists(ddir):
                shutil.rmtree(ddir)
            os.makedirs(ddir)
            for name in os.listdir(backup):
                shutil.copy(os.path.join(backup, name), os.path.join(ddir, name.replace('__next.regulamin.', f'__next.{page["route"]}.')))
            p = Page(root, page['route'])
            p.fsub('"s":"regulamin"', f'"s":"{page["route"]}"')
            p.fsub('"c":["","regulamin",""]', f'"c":["","{page["route"]}",""]')
        el = legal_element(page)
        p.fsub(old_el, flight_json(el))
        h = p.html
        m0 = h.index('<main id="main" tabindex="-1">') + len('<main id="main" tabindex="-1">')
        m1 = h.index('<!--$--><!--/$--></main>', m0)
        p.html = h[:m0] + to_html(el) + h[m1:]
        replace_meta(p, old_title, page['title'], old_desc, page['desc'],
                     'https://sloy.pl/regulamin/', f'https://sloy.pl/{page["route"]}/')
        p.save()
        log('legal page /' + page['route'] + '/')
    shutil.rmtree(backup)


# ------------------------------------------------------------------ head injections
CONSENT_HEAD = (
    '<link rel="stylesheet" href="/sloy-extra.css" data-sloy="extra"/>'
    '<script src="/consent.js" defer="" data-sloy="consent" data-ga="' + GA_ID + '"></script>'
)
NOINDEX = '<meta name="robots" content="noindex" data-sloy="staging"/>'


def inject_head(root, staging):
    files = []
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if not d.startswith(('.', '_next')) and d != 'tools']
        files += [os.path.join(dp, f) for f in fn if f.endswith('.html')]
    for path in files:
        with open(path, encoding='utf-8') as f:
            h = f.read()
        if 'data-sloy="consent"' not in h:
            h = h.replace('</head>', CONSENT_HEAD + '</head>', 1)
        if staging and 'name="robots"' not in h:
            h = h.replace('<meta charSet="utf-8"/>', '<meta charSet="utf-8"/>' + NOINDEX, 1)
            assert NOINDEX in h, path
        with open(path, 'w', encoding='utf-8') as f:
            f.write(h)
    log('head injections:', len(files), 'files', '(staging noindex)' if staging else '(live)')


# ------------------------------------------------------------------ misc
def patch_js(root):
    d = os.path.join(root, '_next', 'static', 'chunks')
    for name in os.listdir(d):
        path = os.path.join(d, name)
        with open(path, encoding='utf-8') as f:
            s = f.read()
        if 'https://sloy.pl/products/${e.slug}`' in s:
            s = s.replace('https://sloy.pl/products/${e.slug}`', 'https://sloy.pl/lot/${e.slug}/`')
            with open(path, 'w', encoding='utf-8') as f:
                f.write(s)
            log('JS: brief form link ->', name)


def update_sitemap(root):
    path = os.path.join(root, 'sitemap.xml')
    with open(path, encoding='utf-8') as f:
        s = f.read()
    add = [c['route'] for c in CATEGORIES] + [d['route'] for d in LEGAL if d['route'] != 'regulamin']
    entries = ''.join(f'<url>\n<loc>https://sloy.pl/{r}/</loc>\n</url>\n' for r in add if f'https://sloy.pl/{r}/' not in s)
    s = s.replace('<url>\n<loc>https://sloy.pl/lot/', entries + '<url>\n<loc>https://sloy.pl/lot/', 1)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(s)
    log('sitemap: +', len(add))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    root = os.path.abspath(args[0] if args else '.')
    live = '--live' in sys.argv
    if os.path.exists(os.path.join(root, STAMP)):
        sys.exit('postbuild already applied to this export (found %s). Run it on a fresh build.' % STAMP)
    shutil.copy(os.path.join(HERE, 'assets', 'sloy-extra.css'), os.path.join(root, 'sloy-extra.css'))
    shutil.copy(os.path.join(HERE, 'assets', 'consent.js'), os.path.join(root, 'consent.js'))
    patch_products(root)
    make_categories(root)
    make_legal(root)
    patch_js(root)
    update_sitemap(root)
    inject_head(root, staging=not live)
    with open(os.path.join(root, STAMP), 'w') as f:
        f.write('applied\n')
    log('done')


if __name__ == '__main__':
    main()
