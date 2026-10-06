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
START = 2015
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
 "revenue":["매출액","수익(매출액)","영업수익"], "gross_profit":["매출총이익"],
 "sga":["판매비와관리비","판매비 및 관리비"], "operating_income":["영업이익","영업이익(손실)","영업손익"],
 "pretax_income":["법인세차감전순이익","법인세비용차감전순이익"], "net_income":["당기순이익","당기순이익(손실)"],
 "controlling_net_income":["지배기업의 소유주에게 귀속되는 당기순이익","지배기업 소유주지분 순이익"],
 "assets":["자산총계"], "current_assets":["유동자산"], "cash":["현금및현금성자산","현금 및 현금성자산"],
 "receivables":["매출채권","매출채권 및 기타채권","매출채권및기타채권"], "inventory":["재고자산"],
 "ppe":["유형자산","유형자산(순액)"], "liabilities":["부채총계"], "current_liabilities":["유동부채"],
 "short_term_debt":["단기차입금","단기차입부채","유동성장기부채","유동성사채"], "long_term_debt":["장기차입금","장기차입부채","사채"],
 "equity":["자본총계"], "controlling_equity":["지배기업의 소유주에게 귀속되는 자본","지배기업 소유주지분"],
 "cfo":["영업활동으로 인한 현금흐름","영업활동 현금흐름"], "cfi":["투자활동으로 인한 현금흐름","투자활동 현금흐름"],
 "cff":["재무활동으로 인한 현금흐름","재무활동 현금흐름"], "ppe_capex":["유형자산의 취득","유형자산 취득"],
 "intangible_capex":["무형자산의 취득","무형자산 취득"], "interest_expense":["이자비용"],
 "depreciation":["감가상각비"], "amortization":["무형자산상각비","무형자산 상각비"]
}
BS = {"assets","current_assets","cash","receivables","inventory","ppe","liabilities","current_liabilities","short_term_debt","long_term_debt","equity","controlling_equity"}
FLOW = set(MAP) - BS

def pick(df, names, sj=None):
    if df.empty or "account_nm" not in df.columns:
        return None
    x = df
    if sj and "sj_div" in df.columns:
        y = df[df["sj_div"].astype(str).str.upper() == sj]
        if not y.empty:
            x = y
    for name in names:
        y = x[x["account_nm"].astype(str).str.strip() == name]
        if not y.empty:
            return y.iloc[0]
    for name in names:
        y = x[x["account_nm"].astype(str).str.contains(re.escape(name), na=False)]
        if not y.empty:
            return y.iloc[0]
    return None

def get_value(df, metric, field="thstrm_amount"):
    sj = "BS" if metric in BS else ("CF" if metric in {"cfo","cfi","cff","ppe_capex","intangible_capex"} else "IS")
    r = pick(df, MAP[metric], sj)
    return None if r is None else num(r.get(field))

def pct(a, b):
    return None if a is None or b in (None, 0) else a / b * 100

def snapshot(df, year, code):
    period = period_name(code)
    values = {}
    for metric in MAP:
        field = "thstrm_add_amount" if metric in FLOW and period == "half_year" else "thstrm_amount"
        values[metric] = get_value(df, metric, field)
    filing = next((str(x) for x in df.get("rcept_no", []) if str(x) != "nan"), None)
    return {"year":year, "period":period, "report_code":code, "rcept_no":filing, "values":values}

def load_legacy():
    p = LEGACY / "legacy_financials.csv"
    if not p.exists():
        return []
    try:
        return pd.read_csv(p).to_dict("records")
    except Exception:
        return []

def calc_ratios(v, prev=None):
    def pct(a,b):
        return None if a is None or b in (None,0) else a/b*100
    assets=v.get("assets"); equity=v.get("equity")
    pa=(prev or {}).get("assets"); pe=(prev or {}).get("equity")
    avg_assets=(assets+pa)/2 if assets is not None and pa is not None else assets
    avg_equity=(equity+pe)/2 if equity is not None and pe is not None else equity
    debt=(v.get("short_term_debt") or 0)+(v.get("long_term_debt") or 0)
    ebitda=None if v.get("operating_income") is None else v["operating_income"]+(v.get("depreciation") or 0)+(v.get("amortization") or 0)
    capex=abs(v.get("ppe_capex") or 0)+abs(v.get("intangible_capex") or 0)
    return {
      "gross_margin":pct(v.get("gross_profit"),v.get("revenue")),
      "operating_margin":pct(v.get("operating_income"),v.get("revenue")),
      "net_margin":pct(v.get("net_income"),v.get("revenue")),
      "current_ratio":pct(v.get("current_assets"),v.get("current_liabilities")),
      "quick_ratio":pct((v.get("cash") or 0)+(v.get("receivables") or 0),v.get("current_liabilities")),
      "debt_to_equity":pct(v.get("liabilities"),v.get("equity")),
      "equity_ratio":pct(v.get("equity"),v.get("assets")),
      "debt_to_assets":pct(debt,v.get("assets")),
      "roa":pct(v.get("net_income"),avg_assets),
      "roe":pct(v.get("controlling_net_income") or v.get("net_income"),avg_equity),
      "asset_turnover":None if avg_assets in (None,0) else v.get("revenue",0)/avg_assets,
      "cfo_to_net_income":None if v.get("cfo") is None or v.get("net_income") in (None,0) else v["cfo"]/v["net_income"],
      "interest_coverage":None if v.get("interest_expense") in (None,0) or v.get("operating_income") is None else v["operating_income"]/abs(v["interest_expense"]),
      "ebitda":ebitda,
      "fcf":None if v.get("cfo") is None else v["cfo"]-capex,
      "net_debt":debt-(v.get("cash") or 0)
    }

def main():
    corp, name = resolve_corp()
    records=[]; now=datetime.now(KST)
    for year in range(START, now.year+1):
        for code in CODES.values():
            try:
                df=fetch_financials(corp,year,code)
                if not df.empty: records.append(snapshot(df,year,code))
            except RuntimeError as e:
                if "013" not in str(e): print(f"WARN {year} {code}: {e}")
    by={(r["year"],r["period"]):r for r in records}
    for r in records:
        prev=by.get((r["year"]-1,"annual"),{}).get("values") if r["period"]=="annual" else None
        r["ratios"]=calc_ratios(r["values"],prev)
        if prev:
            for out,key in [("revenue_growth","revenue"),("operating_income_growth","operating_income")]:
                a,b=r["values"].get(key),prev.get(key)
                r["ratios"][out]=None if a is None or b in (None,0) else (a-b)/abs(b)*100
        for k in ("ebitda","fcf","net_debt"):
            r["values"][k]=r["ratios"][k]
    legacy=load_legacy()
    out={"company":name,"company_en":CFG["company_name_en"],"stock_code":STOCK,"corp_code":corp,
         "generated_at":now.isoformat(),"requested_coverage":"2010-present","api_coverage":"2015-present",
         "legacy_coverage":"2010-2014 when legacy/legacy_financials.csv is supplied",
         "annual":[r for r in records if r["period"]=="annual"],
         "half_year":[r for r in records if r["period"]=="half_year"],
         "quarterly":[r for r in records if r["period"].startswith("quarterly")],
         "legacy":legacy}
    (PROC/"dashboard.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
    (PROC/"last_update.json").write_text(json.dumps({"updated_at":now.isoformat(),"records":len(records),"legacy_records":len(legacy)},ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"status":"ok","records":len(records),"legacy_records":len(legacy)},ensure_ascii=False))

if __name__ == "__main__":
    main()
