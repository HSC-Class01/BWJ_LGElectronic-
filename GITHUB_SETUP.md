# LG전자 DART Agent 설정

## 1. DART API Key
GitHub → Settings → Secrets and variables → Actions → New repository secret
- Name: `DART_API_KEY`
- Value: OpenDART에서 발급한 40자리 인증키

## 2. GitHub Pages
Settings → Pages → Deploy from a branch → `main` → `/docs`

Dashboard: https://hsc-class01.github.io/BWJ_LGElectronic-/

## 3. 자동 업데이트
매월 1일 00:00 UTC(한국시간 09:00). Actions에서 `Update LG Electronics DART data`를 수동 실행할 수도 있습니다.

## 4. 최초 실행
API Key 저장 후 Actions → `Update LG Electronics DART data` → Run workflow를 실행합니다.