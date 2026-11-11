#!/usr/bin/env python3
"""生成候选池（v2 执行单 S1）。--preview：只写到 --outdir（artifact），不提交仓库。
来源：Cloudflare 官方 IPv4 段；pool/domains.txt（Joe 维护，可不存在）用 DoH 解析；
pool/public-sources.txt（可不存在，每行一个公开站点地址，只当补充）。"""
import argparse, ipaddress, json, os, re, sys, urllib.request, datetime as dt
TZ = dt.timezone(dt.timedelta(hours=8)); IP = re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b')
UA = {'User-Agent': 'cfip-pool/1'}
def get(url, t=20):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=t).read().decode('utf-8', 'replace')
def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--repo', default='.'); ap.add_argument('--outdir', default='preview')
    ap.add_argument('--preview', action='store_true'); a = ap.parse_args()
    if not a.preview: sys.exit('S1 只允许 --preview')
    os.makedirs(a.outdir, exist_ok=True); rep = {'generated': dt.datetime.now(TZ).isoformat(timespec='minutes')}
    nets = [ipaddress.ip_network(l.strip()) for l in get('https://www.cloudflare.com/ips-v4').split() if l.strip()]
    rep['cf_v4_cidrs'] = len(nets); open(f'{a.outdir}/cf-v4.txt', 'w').write('\n'.join(map(str, nets)) + '\n')
    def in_cf(ip):
        try: x = ipaddress.ip_address(ip); return any(x in n for n in nets)
        except ValueError: return False
    dom_ips = set(); doms = []
    p = os.path.join(a.repo, 'pool', 'domains.txt')
    if os.path.exists(p): doms = [l.split('#')[0].strip() for l in open(p, encoding='utf-8') if l.split('#')[0].strip()]
    for d in doms:
        try:
            req = urllib.request.Request(f'https://cloudflare-dns.com/dns-query?name={d}&type=A', headers={'accept': 'application/dns-json', **UA})
            j = json.loads(urllib.request.urlopen(req, timeout=10).read())
            dom_ips |= {x['data'] for x in j.get('Answer', []) if x.get('type') == 1 and in_cf(x['data'])}
        except Exception: pass
    rep['domains'] = len(doms); rep['domain_ips'] = len(dom_ips)
    pub = set(); src_ok = 0; srcs = []
    p = os.path.join(a.repo, 'pool', 'public-sources.txt')
    if os.path.exists(p): srcs = [l.strip() for l in open(p, encoding='utf-8') if l.strip() and not l.startswith('#')]
    for s in srcs:
        try: pub |= {ip for ip in IP.findall(get(s, 15)) if in_cf(ip)}; src_ok += 1
        except Exception: pass
    rep['public_sources'] = len(srcs); rep['public_sources_ok'] = src_ok; rep['public_ips'] = len(pub)
    cand = sorted(dom_ips) + sorted(pub - dom_ips); rep['candidates'] = len(cand)
    open(f'{a.outdir}/domain-ips.txt', 'w').write('\n'.join(sorted(dom_ips)) + '\n')
    open(f'{a.outdir}/public-all.txt', 'w').write('\n'.join(sorted(pub)) + '\n')
    open(f'{a.outdir}/candidates.txt', 'w').write('\n'.join(cand) + '\n')
    json.dump(rep, open(f'{a.outdir}/pool-status.json', 'w'), ensure_ascii=False, indent=1)
    s = ('## cfip pool 预览（不提交仓库）\n\n| 项 | 值 |\n|---|---|\n' + '\n'.join(f'| {k} | {v} |' for k, v in rep.items()) + '\n')
    if os.environ.get('GITHUB_STEP_SUMMARY'): open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8').write(s)
    print(s)
if __name__ == '__main__': main()
