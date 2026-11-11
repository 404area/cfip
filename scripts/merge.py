#!/usr/bin/env python3
"""合并各线路测速结果为混合列表（v2 执行单 S1）。
--preview：只写到 --outdir（Action artifact / job summary），绝不写仓库 out/。"""
import argparse, glob, json, os, re, sys, datetime as dt
CARRIERS = ['电信', '联通', '移动']
REGIONS = ['美国','香港','日本','新加坡','韩国','台湾','英国','德国','荷兰','法国','澳大利亚','加拿大','其他']
ASN = {
 '电信': {4134,4809,4812,4811,4813,4816,23724,134774,136190,140292,137693},
 '联通': {4837,4808,17621,17622,17623,17816,9929,10099,135061,136958},
 '移动': {9808,56048,24400,24547,24444,24445,56040,56041,56042,56043,56044,56045,56046,56047,132525,134810},
}
LINE = re.compile(r'^\s*([0-9.]+|\[[0-9a-fA-F:]+\]):(\d+)#(电信|联通|移动)-([^-#]+)-(\d+)\s*$')
TZ = dt.timezone(dt.timedelta(hours=8))
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', default='.'); ap.add_argument('--outdir', default='preview')
    ap.add_argument('--preview', action='store_true'); ap.add_argument('--max-age-h', type=float, default=36)
    ap.add_argument('--cap', type=int, default=16)
    a = ap.parse_args()
    if not a.preview:
        sys.exit('S1 只允许 --preview；正式写 out/all.txt 属于 S5，需另批')
    now = dt.datetime.now(TZ); rep = {'generated': now.isoformat(timespec='minutes'), 'carriers': {}, 'files': {}}
    out_lines = []
    for c in CARRIERS:
        st_path = os.path.join(a.repo, 'out', '_status', f'{c}.json')
        info = {'included': False}
        try:
            st = json.load(open(st_path, encoding='utf-8'))
            upd = dt.datetime.fromisoformat(st['updated']); age = (now - upd).total_seconds() / 3600
            info.update(updated=st['updated'], age_h=round(age, 1), asn=st.get('asn'))
            if age > a.max_age_h: info['reason'] = f'超过 {a.max_age_h:g}h 未更新'
            elif int(st.get('asn') or 0) not in ASN[c]: info['reason'] = f"ASN {st.get('asn')} 不在 {c} 白名单"
            else: info['included'] = True
        except FileNotFoundError: info['reason'] = '无 _status 文件'
        except Exception as e: info['reason'] = f'status 解析失败: {e.__class__.__name__}'
        files = sorted(glob.glob(os.path.join(a.repo, 'out', f'{c}-*.txt')),
                       key=lambda p: (REGIONS.index(os.path.basename(p)[len(c)+1:-4]) if os.path.basename(p)[len(c)+1:-4] in REGIONS else 99, p))
        for p in files:
            name = os.path.basename(p); good = []; bad = 0
            for l in open(p, encoding='utf-8', errors='replace'):
                if not l.strip(): continue
                m = LINE.match(l)
                if m and m.group(3) == c: good.append(l.strip())
                else: bad += 1
            rep['files'][name] = {'lines': len(good), 'bad': bad, 'taken': min(len(good), a.cap) if info['included'] else 0}
            if info['included']: out_lines += good[:a.cap]
        rep['carriers'][c] = info
    rep['merged_lines'] = len(out_lines)
    os.makedirs(a.outdir, exist_ok=True)
    open(os.path.join(a.outdir, 'preview-all.txt'), 'w', encoding='utf-8').write('\n'.join(out_lines) + ('\n' if out_lines else ''))
    json.dump(rep, open(os.path.join(a.outdir, 'preview-status.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    md = ['## cfip merge 预览（不提交仓库）', f"生成时间 {rep['generated']} CST；合并结果 {len(out_lines)} 行；out/all.txt 未改动", '',
          '| 线路 | 纳入 | 更新时间 | ASN | 原因 |', '|---|---|---|---|---|']
    for c, i in rep['carriers'].items():
        md.append(f"| {c} | {'是' if i['included'] else '否'} | {i.get('updated','-')} | {i.get('asn','-')} | {i.get('reason','')} |")
    md += ['', '| 文件 | 有效行 | 格式不符 | 预览取用 |', '|---|---|---|---|']
    for n, f in rep['files'].items(): md.append(f"| {n} | {f['lines']} | {f['bad']} | {f['taken']} |")
    s = '\n'.join(md) + '\n'
    open(os.path.join(a.outdir, 'summary.md'), 'w', encoding='utf-8').write(s)
    if os.environ.get('GITHUB_STEP_SUMMARY'): open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8').write(s)
    print(s)
if __name__ == '__main__': main()
