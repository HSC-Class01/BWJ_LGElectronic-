# LG전자 DART Financial Agent

LG전자(066570) OpenDART 기반 재무데이터 자동 수집 및 GitHub Pages 대시보드입니다.

[![Dashboard](https://img.shields.io/badge/%F0%9F%94%97%20%EB%8C%80%EC%8B%9C%EB%B3%B4%EB%93%9C%20%EB%B0%94%EB%A1%9C%EA%B0%80%EA%B8%B0-1f6feb?style=for-the-badge)](https://hsc-class01.github.io/BWJ_LGElectronic-/)

## 구성
- OpenDART API: 2015년 이후 정기보고서 자동 수집
- 사업보고서 / 반기보고서 / 1분기 / 3분기
- 연결재무제표(CFS) 기준
- 주요 재무수치 및 재무비율 계산
- Annual / Half-year / Quarterly 표 제공
- 국내 비교기업 표 제공
- GitHub Actions 월 1회 자동 업데이트
- GitHub Pages: `/docs`

## API Key
Repository → Settings → Secrets and variables → Actions → New repository secret에서 `DART_API_KEY`를 등록하세요.

## Pages
Settings → Pages → Deploy from a branch → `main` → `/docs`.

## 2010–2014
OpenDART 공식 재무제표 API의 문서상 제공 범위가 2015년 이후이므로, 2010–2014는 `legacy/legacy_financials.csv`에 원문 확인값을 입력하면 대시보드에 통합합니다.

## 국내 비교기업
삼성전자(005930), LG디스플레이(034220), LG이노텍(011070), 삼성전기(009150), SK하이닉스(000660). 비교기업은 분석 편의를 위한 기업군이며 순위나 투자등급을 의미하지 않습니다.

Source: Financial Supervisory Service OpenDART.
