import io
import json
import os
import re
import zipfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
API_KEY = os.environ.get("DART_API_KEY")

RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
RAW.mkdir(parents=True, exist_ok=True)
PROCESSED.mkdir(parents=True, exist_ok=True)

if not API_KEY:
    raise RuntimeError("DART_API_KEY 환경변수가 없습니다.")

BASE = CONFIG["dart_base_url"]
STOCK_CODE = CONFIG["stock_code"]
REPORT_CODE = CONFIG["report_code"]

KST = timezone(timedelta(hours=9))


def api_get(endpoint, params):
    params = dict(params)
    params["crtfc_key"] = API_KEY
    url = f"{BASE}/{endpoint}"
    r = requests.get(url, params=params, timeout=60)
    r.raise_for_status()
    return r


def json_api(endpoint, params):
    data = api_get(endpoint, params).json()
    if str(data.get("status")) != "000":
        raise RuntimeError(f"{endpoint}: {data.get('status')} {data.get('message')}")
    return data


def resolve_corp_code():
    # OpenDART corpCode API returns a ZIP containing CORPCODE.xml.
    r = api_get("corpCode.xml", {})
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        xml = z.read("CORPCODE.xml").decode("utf-8")
    rows = re.findall(
        r"<list>.*?<corp_code>(.*?)</corp_code>.*?<corp_name>(.*?)</corp_name>.*?"
        r"<stock_code>(.*?)</stock_code>.*?</list>",
        xml,
        flags=re.S,
    )
    for corp_code, corp_name, stock_code in rows:
        if stock_code.strip() == STOCK_CODE:
            return corp_code.strip(), corp_name.strip()
    raise RuntimeError(f"stock_code={STOCK_CODE}에 해당하는 corp_code를 찾지 못했습니다.")


def find_latest_annual_report(corp_code):
    now = datetime.now(KST)
    start_year = now.year - 2
    data = json_api(
        "list.json",
        {
            "corp_code": corp_code,
            "bgn_de": f"{start_year}0101",
            "end_de": now.strftime("%Y%m%d"),
            "pblntf_ty": "A",
            "page_count": 100,
        },
    )
    candidates = []
    for item in data.get("list", []):
        report_nm = item.get("report_nm", "")
        # Annual report names normally contain "사업보고서".
        if "사업보고서" in report_nm:
            candidates.append(item)
    if not candidates:
        raise RuntimeError("최근 사업보고서를 찾지 못했습니다.")
    candidates.sort(key=lambda x: x.get("rcept_dt", ""), reverse=True)
    return candidates[0]


def download_original_document(rcept_no):
    r = api_get("document.xml", {"rcept_no": rcept_no})
    # document.xml is a binary ZIP response despite the .xml endpoint name.
    out = RAW / f"{rcept_no}_original.zip"
    out.write_bytes(r.content)
    return out


def fetch_financials(corp_code, bsns_year, fs_div):
    data = json_api(
        "fnlttSinglAcntAll.json",
        {
            "corp_code": corp_code,
            "bsns_year": str(bsns_year),
            "reprt_code": REPORT_CODE,
            "fs_div": fs_div,
        },
    )
    rows = data.get("list", [])
    df = pd.DataFrame(rows)
    if not df.empty:
        df.to_csv(
            RAW / f"{STOCK_CODE}_{bsns_year}_{REPORT_CODE}_{fs_div}_financials.csv",
            index=False,
            encoding="utf-8-sig",
        )
    return df


def numeric(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    s = str(v).replace(",", "").strip()
    if s in ("", "-", "nan", "None"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def pick(df, account_names, sj_div=None):
    if df.empty:
        return None
    x = df.copy()
    if sj_div:
        x = x[x["sj_div"].astype(str).str.upper() == sj_div]
    for name in account_names:
        exact = x[x["account_nm"].astype(str).str.strip() == name]
        if not exact.empty:
            # Prefer current-period value.
            row = exact.iloc[0]
            for col in ("thstrm_amount", "thstrm_add_amount", "thstrm_dt"):
                if col in row.index:
                    val = numeric(row[col])
                    if val is not None:
                        return val
    return None


def pick_current_and_prior(df, account_names, sj_div=None):
    if df.empty:
        return None, None
    x = df.copy()
    if sj_div:
        x = x[x["sj_div"].astype(str).str.upper() == sj_div]
    for name in account_names:
        exact = x[x["account_nm"].astype(str).str.strip() == name]
        if not exact.empty:
            row = exact.iloc[0]
            cur = numeric(row.get("thstrm_amount"))
            prior = numeric(row.get("frmtrm_amount"))
            return cur, prior
    return None, None


def ratio(a, b):
    if a is None or b in (None, 0):
        return None
    return a / b


def pct(a):
    return None if a is None else a * 100.0


def build_snapshot(df_cfs, df_ofs, year, filing):
    # fnlttSinglAcntAll amounts are reported in the unit specified by the API response.
    # For this project the dashboard keeps the API unit and labels it explicitly.
    metrics = {}

    mapping = {
        "revenue": ["매출액", "수익(매출액)", "영업수익"],
        "operating_income": ["영업이익", "영업이익(손실)", "영업손익"],
        "pretax_income": ["법인세차감전순이익", "법인세비용차감전순이익"],
        "net_income": ["당기순이익", "당기순이익(손실)"],
        "assets": ["자산총계"],
        "current_assets": ["유동자산"],
        "cash": ["현금및현금성자산", "현금 및 현금성자산"],
        "inventory": ["재고자산"],
        "liabilities": ["부채총계"],
        "current_liabilities": ["유동부채"],
        "equity": ["자본총계"],
        "controlling_equity": ["지배기업의 소유주에게 귀속되는 자본", "지배기업 소유주지분"],
    }

    # CFS = consolidated, OFS = separate.
    for basis, df in (("CFS", df_cfs), ("OFS", df_ofs)):
        vals = {}
        for key, names in mapping.items():
            cur, prior = pick_current_and_prior(df, names)
            vals[key] = {"current": cur, "prior": prior}

        rev = vals["revenue"]["current"]
        op = vals["operating_income"]["current"]
        ni = vals["net_income"]["current"]
        assets = vals["assets"]["current"]
        assets_prior = vals["assets"]["prior"]
        eq = vals["equity"]["current"]
        eq_prior = vals["equity"]["prior"]
        ctrl_eq = vals["controlling_equity"]["current"]
        ctrl_eq_prior = vals["controlling_equity"]["prior"]

        ratios = {
            "operating_margin_pct": pct(ratio(op, rev)),
            "net_margin_pct": pct(ratio(ni, rev)),
            "current_ratio_pct": pct(ratio(vals["current_assets"]["current"], vals["current_liabilities"]["current"])),
            "debt_to_equity_pct": pct(ratio(vals["liabilities"]["current"], eq)),
            "equity_ratio_pct": pct(ratio(eq, assets)),
            "cash_ratio_pct": pct(ratio(vals["cash"]["current"], vals["current_liabilities"]["current"])),
            "roa_pct": pct(ratio(ni, (assets + assets_prior) / 2 if assets is not None and assets_prior is not None else assets)),
            "roe_pct": pct(ratio(
                ni,
                (ctrl_eq + ctrl_eq_prior) / 2
                if ctrl_eq is not None and ctrl_eq_prior is not None
                else (ctrl_eq if ctrl_eq is not None else eq)
            )),
            "revenue_growth_pct": pct(ratio(
                rev - vals["revenue"]["prior"],
                abs(vals["revenue"]["prior"])
            )) if rev is not None and vals["revenue"]["prior"] not in (None, 0) else None,
            "operating_income_growth_pct": pct(ratio(
                op - vals["operating_income"]["prior"],
                abs(vals["operating_income"]["prior"])
            )) if op is not None and vals["operating_income"]["prior"] not in (None, 0) else None,
        }

        metrics[basis] = {"values": vals, "ratios": ratios}

    return {
        "company": CONFIG["company_name"],
        "company_en": CONFIG["company_name_en"],
        "stock_code": STOCK_CODE,
        "business_year": int(year),
        "report_code": REPORT_CODE,
        "report_name": filing.get("report_nm"),
        "receipt_no": filing.get("rcept_no"),
        "receipt_date": filing.get("rcept_dt"),
        "basis_default": CONFIG["default_basis"],
        "source": "OpenDART",
        "source_url": f"https://opendart.fss.or.kr/",
        "metrics": metrics,
        "generated_at": datetime.now(KST).isoformat(),
    }


def main():
    corp_code, corp_name = resolve_corp_code()
    filing = find_latest_annual_report(corp_code)
    year = int(filing["rcept_dt"][:4]) - 1

    # Save metadata so the repository shows what was collected.
    metadata = {
        "corp_code": corp_code,
        "corp_name": corp_name,
        "stock_code": STOCK_CODE,
        "latest_annual_filing": filing,
    }
    (RAW / "latest_filing.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    download_original_document(filing["rcept_no"])

    # The latest annual report can be filed early in the following year.
    # The report's business year is generally filing year - 1.
    df_cfs = fetch_financials(corp_code, year, "CFS")
    df_ofs = fetch_financials(corp_code, year, "OFS")

    snapshot = build_snapshot(df_cfs, df_ofs, year, filing)

    # Append a compact history record.
    history_file = PROCESSED / "history.json"
    history = []
    if history_file.exists():
        history = json.loads(history_file.read_text(encoding="utf-8"))
    history = [h for h in history if not (
        h.get("business_year") == snapshot["business_year"]
        and h.get("receipt_no") == snapshot["receipt_no"]
    )]
    history.append(snapshot)
    history.sort(key=lambda x: (x["business_year"], x["receipt_no"]))

    (PROCESSED / "dashboard.json").write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    history_file.write_text(
        json.dumps(history, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(json.dumps({
        "status": "ok",
        "corp_code": corp_code,
        "filing": filing,
        "business_year": year,
        "dashboard": str(PROCESSED / "dashboard.json"),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
