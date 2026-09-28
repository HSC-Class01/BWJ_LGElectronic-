# AUSTEM DART Financial Agent

㈜오스템(AUSTEM) 사업보고서의 OpenDART 데이터를 자동 수집하고, 주요 재무수치·재무비율을 계산하여 GitHub에 저장하고 GitHub Pages 대시보드로 보여주는 프로젝트입니다.

## 현재 설정

- 분석대상: ㈜오스템 / AUSTEM
- 종목코드: `036560`
- 기준 보고서: 사업보고서(연간), `reprt_code=11011`
- 최근 확인된 보고서: 2025 사업연도, 2026-03-19 제출
- 기본 분석 기준: **연결 기준**
- 원천: OpenDART API
- 자동 업데이트: GitHub Actions
- 대시보드: GitHub Pages
- API Key: GitHub Actions Repository Secret `DART_API_KEY`

> 참고: 이 ZIP은 사용자가 지정할 GitHub 저장소 URL을 아직 알 수 없으므로 `GITHUB_REPO_URL`은 placeholder로 남겨두었습니다. 저장소를 만든 뒤 파일을 업로드하고 README의 API 설정을 진행하면 됩니다.

## 프로젝트 구조

```text
.
├─ .github/workflows/
│  ├─ update.yml          # DART 데이터 자동 업데이트
│  └─ pages.yml           # GitHub Pages 배포
├─ src/
│  └─ dart_agent.py       # OpenDART 수집/분석 agent
├─ data/
│  ├─ raw/                # 원본 DART 파일
│  └─ processed/          # 대시보드용 JSON/CSV
├─ docs/
│  └─ index.html          # GitHub Pages dashboard
├─ config.json
├─ requirements.txt
└─ README.md
```

## 1. OpenDART API Key 발급

OpenDART에서 인증키를 발급합니다.

공식 사이트: https://opendart.fss.or.kr/

발급한 40자리 인증키를 GitHub에 직접 코드로 넣지 마세요.

GitHub 저장소에서:

`Settings` → `Secrets and variables` → `Actions` → `New repository secret`

- Name: `DART_API_KEY`
- Secret: 발급받은 OpenDART 인증키

GitHub Actions는 workflow에서 이 secret을 환경변수로 받아 사용합니다.

## 2. GitHub에 업로드

GitHub에서 새 repository를 만든 뒤 이 ZIP의 파일을 repository에 올립니다.

예:
```text
GITHUB_REPO_URL = https://github.com/사용자명/저장소명
```

이 값은 문서상의 placeholder일 뿐이며 코드 실행에는 직접 필요하지 않습니다.

## 3. 최초 실행

Actions 탭 → `Update DART Financial Data` → `Run workflow`

실행되면:

1. OpenDART 기업코드 ZIP을 내려받음
2. 종목코드 `036560`으로 오스템 corp_code를 찾음
3. 최근 사업보고서를 탐색
4. 원본 공시문서(document.xml)를 저장
5. 연결/별도 재무제표 데이터를 저장
6. 주요 재무수치를 표준화
7. 재무비율 계산
8. `data/processed/dashboard.json` 생성
9. Git commit/push

## 4. 자동 업데이트

`.github/workflows/update.yml`은 매일 KST 07:30에 실행되도록 설정되어 있습니다.

또한 수동 `workflow_dispatch` 실행도 가능합니다.

DART에 새 사업보고서가 등록되면 다음 실행에서 최신 연간 보고서를 자동으로 찾아 데이터가 갱신됩니다.

## 5. Dashboard

`docs/index.html`은 정적 GitHub Pages dashboard입니다.

표시 항목:
- 매출액
- 영업이익
- 법인세차감전순이익
- 당기순이익
- 자산총계
- 부채총계
- 자본총계
- 현금및현금성자산
- 유동자산 / 유동부채
- 재고자산
- 주요 재무비율
- 전년 대비 증감률
- 연결/별도 구분
- 사업연도 및 보고서 접수번호

### GitHub Pages 활성화

Repository → `Settings` → `Pages` → Source를 `GitHub Actions`로 선택합니다.

`pages.yml`이 `docs/`를 GitHub Pages artifact로 배포합니다.

## 6. 분석 기준

기본 dashboard는 연결 기준을 중심으로 합니다. 원본에는 별도 기준도 함께 저장합니다.

계산 재무비율:

- 영업이익률 = 영업이익 / 매출액
- 순이익률 = 당기순이익 / 매출액
- 유동비율 = 유동자산 / 유동부채
- 부채비율 = 부채총계 / 자본총계
- 자기자본비율 = 자본총계 / 자산총계
- ROA = 당기순이익 / 평균자산
- ROE = 지배기업 귀속 당기순이익 / 평균 지배기업 자본
- 현금비율 = 현금및현금성자산 / 유동부채
- 매출증가율 = (당기 매출액 - 전기 매출액) / 전기 매출액
- 영업이익증가율 = (당기 영업이익 - 전기 영업이익) / |전기 영업이익|

0으로 나누는 경우 해당 비율은 null 처리합니다.

## 7. 2025년 사업보고서 검증값

첨부된 2025 사업보고서 기준으로 연결 영업실적은 다음과 같습니다.

| 항목 | 2025 |
|---|---:|
| 매출액 | 128,549 백만원 |
| 영업이익 | 4,148 백만원 |
| 법인세차감전순이익 | 1,815 백만원 |
| 당기순이익 | 803 백만원 |

연결 재무상태표의 주요 수치는 자산총계 131,603백만원, 부채총계 65,311백만원, 자본총계 66,292백만원입니다.

실제 API 실행값을 최종 데이터로 사용하며, 위 숫자는 첨부 사업보고서와의 sanity check용입니다.

## 8. 데이터 출처

OpenDART는 DART 공시 원문과 주요 재무계정/전체 재무제표 데이터를 API로 제공합니다.

- OpenDART: https://opendart.fss.or.kr/
- 단일회사 전체 재무제표 API: `fnlttSinglAcntAll`
- 공시 원문 API: `document`
- 공시검색 API: `list`

## 주의

이 프로젝트는 공시 데이터를 자동 수집하고 산술적 재무비율을 계산합니다. 투자 판단이나 기업가치 판단을 자동으로 내리지 않습니다.
