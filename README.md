# LG전자 DART Financial Agent

[![Dashboard](https://img.shields.io/badge/%F0%9F%94%97%20%EB%8C%80%EC%8B%9C%EB%B3%B4%EB%93%9C%20%EB%B0%94%EB%A1%9C%EA%B0%80%EA%B8%B0-263a8b?style=for-the-badge)](https://hsc-class01.github.io/BWJ_LGElectronic-/)

LG전자(066570)의 OpenDART 정기보고서를 수집하고 연결재무제표(CFS) 기준 주요 재무수치와 재무비율을 계산하여 GitHub Pages에서 시각화합니다.

## 주요 기능
- 사업보고서(11011), 반기보고서(11012), 1분기보고서(11013), 3분기보고서(11014) 수집
- data/raw/에 보고서별 OpenDART 원자료 CSV 저장
- 매출, 매출총이익, 판관비, 영업이익, 세전이익, 순이익, 자산, 현금, 매출채권, 재고, 부채, 차입금, 자본, CFO/CFI/CFF, CAPEX, EBITDA, FCF, 순차입금 추출
- 매출총이익률, 영업이익률, 순이익률, 유동비율, 당좌비율, 부채비율, 자기자본비율, 차입금의존도, ROA, ROE, 총자산회전율, CFO/순이익, 이자보상배율, 성장률 계산
- Dashboard: Executive Snapshot → Figures → Ratios → Annual → Half-year → Quarterly → 국내 Peer Firms
- GitHub Actions: 매월 1일 00:00 UTC(한국시간 09:00) 자동 업데이트

## 국내 Peer Firms
| 기업 | 종목코드 | 비교 목적 |
|---|---:|---|
| 삼성전자 | 005930 | 종합 전자·반도체 대형 경쟁기업 |
| SK하이닉스 | 000660 | 메모리 반도체 핵심 국내 비교기업 |
| LG디스플레이 | 034220 | 디스플레이 패널·전자부품 비교 |
| LG이노텍 | 011070 | 전자부품·카메라모듈 비교 |
| 삼성전기 | 009150 | 전자부품·MLCC 비교 |

## DART API Key
GitHub → Settings → Secrets and variables → Actions → New repository secret
- Name: DART_API_KEY
- Value: OpenDART에서 발급한 40자리 인증키

## GitHub Pages
Dashboard: https://hsc-class01.github.io/BWJ_LGElectronic-/
Settings → Pages → Deploy from a branch → main → /docs

## 2010–2014 데이터
OpenDART의 단일회사 전체 재무제표 API는 공식 개발가이드상 2015년 이후 사업연도부터 재무정보를 제공합니다. 따라서 2010–2014는 검증된 DART 원문 수치를 legacy/legacy_financials.csv로 제공했을 때만 통합합니다. 임의의 과거 수치를 생성하지 않습니다.

공식 개발가이드: https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS003&apiId=2019020
