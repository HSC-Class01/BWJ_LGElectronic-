import io, json, os, re, zipfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
CFG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
KEY = os.environ.get("DART_API_KEY")
RAW = ROOT / "data" / "raw"
PROC = ROOT / "data" / "processed"
LEGACY = ROOT / "legacy"
RAW.mkdir(parents=True, exist_ok=True)
PROC.mkdir(parents=True, exist_ok=True)
BASE = CFG["dart_base_url"]
STOCK = CFG["stock_code"]
START = max(2015, int(CFG.get("start_year", 2015)))
CODES = CFG["report_codes"]
KST = timezone(timedelta(hours=9))

if not KEY:
    raise RuntimeError("DART_API_KEY 환경변수가 없습니다.")

def api(endpoint, params):
    p = dict(params)
    p["crtfc_key"] = KEY
    r = requests.get(f"{BASE}/{endpoint}", params=p, timeout=60)
    r.raise_for_status()
    data = r.json() if endpoint.endswith(".json") else None
    if data is not None and str(data.get("status")) != "000":
        raise RuntimeError(f"{endpoint}: {data.get('status')} {data.get('message')}")
    return r if data is None else data

def resolve_corp():
    r = api("corpCode.xml", {})
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        xml = z.read("CORPCODE.xml").decode("utf-8")
    for m in re.finditer(r"<list>(.*?)</list>", xml, re.S):
        block = m.group(1)
        stock = re.search(r"<stock_code>(.*?)</stock_code>", block, re.S)
        if stock and stock.group(1).strip() == STOCK:
            corp = re.search(r"<corp_code>(.*?)</corp_code>", block, re.S)
            name = re.search(r"<corp_name>(.*?)</corp_name>", block, re.S)
            return corp.group(1).strip(), name.group(1).strip()
    raise RuntimeError("LG전자(066570) corp_code를 찾지 못했습니다.")

def period_name(code):
    return {"11011":"annual", "11012":"half_year", "11013":"quarterly_q1", "11014":"quarterly_q3"}[code]

def fetch_financials(corp, year, code):
    data = api("fnlttSinglAcntAll.json", {
        "corp_code": corp, "bsns_year": str(year),
        "reprt_code": code, "fs_div": CFG.get("default_basis", "CFS")
    })
    df = pd.DataFrame(data.get("list", []))
    if not df.empty:
        df.to_csv(RAW / f"{STOCK}_{year}_{period_name(code)}_CFS.csv",
                  index=False, encoding="utf-8-sig")
    return df

def num(v):
    if v is None or str(v).strip() in ("", "-", "nan", "None"):
        return None
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None

MAP = {
 "revenue":["매출액","수익(매출액)","영업수익"],
 "operating_income":["영업이익","영업이익(손실)","영업손익"],
 "pretax_income":["법인세차감전순이익","법인세비용차감전순이익"],
 "net_income":["당기순이익","당기순이익(손실)"],
 "assets":["자산총계"], "current_assets":["유동자산"],
 "cash":["현금및현금성자산","현금 및 현금성자산"],
 "inventory":["재고자산"], "liabilities":["부채총계"],
 "current_liabilities":["유동부채"], "equity":["자본총계"],
 "controlling_equity":["지배기업의 소유주에게 귀속되는 자본","지배기업 소유주지분"]
}

def pick(df, names):
    if df.empty or "account_nm" not in df.columns:
        return None, None
    for name in names:
        x = df[df["account_nm"].astype(str).str.strip() == name]
        if not x.empty:
            row = x.iloc[0]
            return num(row.get("thstrm_amount")), num(row.get("frmtrm_amount"))
    return None, None

def pct(a, b):
    return None if a is None or b in (None, 0) else a / b * 100

def snapshot(df, year, code):
    pairs = {k: pick(df, n) for k, n in MAP.items()}
    cur = {k:v[0] for k,v in pairs.items()}
    prior = {k:v[1] for k,v in pairs.items()}
    avg_assets = ((cur["assets"] + prior["assets"]) / 2
                  if cur["assets"] is not None and prior["assets"] is not None else cur["assets"])
    ce, pe = cur["controlling_equity"] or cur["equity"], prior["controlling_equity"] or prior["equity"]
    avg_eq = (ce + pe) / 2 if ce is not None and pe is not None else ce
    ratios = {
      "operating_margin": pct(cur["operating_income"], cur["revenue"]),
      "net_margin": pct(cur["net_income"], cur["revenue"]),
      "current_ratio": pct(cur["current_assets"], cur["current_liabilities"]),
      "debt_to_equity": pct(cur["liabilities"], cur["equity"]),
      "equity_ratio": pct(cur["equity"], cur["assets"]),
      "cash_ratio": pct(cur["cash"], cur["current_liabilities"]),
      "roa": pct(cur["net_income"], avg_assets),
      "roe": pct(cur["net_income"], avg_eq),
      "revenue_growth": pct(cur["revenue"] - prior["revenue"], abs(prior["revenue"]))
          if cur["revenue"] is not None and prior["revenue"] not in (None,0) else None,
      "operating_income_growth": pct(cur["operating_income"] - prior["operating_income"], abs(prior["operating_income"]))
          if cur["operating_income"] is not None and prior["operating_income"] not in (None,0) else None
    }
    return {"year":year, "period":period_name(code), "report_code":code,
            "fs_div":CFG.get("default_basis","CFS"), "values":cur,
            "prior_values":prior, "ratios":ratios}

def load_legacy():
    p = LEGACY / "legacy_financials.csv"
    if not p.exists():
        return []
    try:
        return pd.read_csv(p).to_dict("records")
    except Exception:
        return []

def main():
    corp, name = resolve_corp()
    records = []
    now = datetime.now(KST)
    for year in range(START, now.year + 1):
        for code in CODES.values():
            try:
                df = fetch_financials(corp, year, code)
                if not df.empty:
                    records.append(snapshot(df, year, code))
            except RuntimeError as e:
                if "013" not in str(e):
                    print(f"WARN {year} {code}: {e}")
    annual = [r for r in records if r["period"] == "annual"]
    half = [r for r in records if r["period"] == "half_year"]
    quarterly = [r for r in records if r["period"].startswith("quarterly")]
    legacy = load_legacy()
    out = {
      "company": name, "company_en": CFG["company_name_en"], "stock_code": STOCK,
      "corp_code": corp, "generated_at": now.isoformat(),
      "api_coverage": "2015-present",
      "legacy_coverage": "2010-2014 when legacy/legacy_financials.csv is supplied",
      "annual": annual, "half_year": half, "quarterly": quarterly, "legacy": legacy
    }
    (PROC/"dashboard.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    (PROC/"last_update.json").write_text(
      json.dumps({"updated_at":now.isoformat(),"records":len(records),"legacy_records":len(legacy)},
                 ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status":"ok","records":len(records),"legacy_records":len(legacy)}, ensure_ascii=False))

if __name__ == "__main__":
    main()
