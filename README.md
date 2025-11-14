# LLM Package Hallucination Study

## 프로젝트 소개
LLM이 npm 패키지를 추천할 때 발생하는 환각(hallucination) 현상을 연구하는 프로젝트입니다.
[참고 논문](https://www.usenix.org/system/files/conference/usenixsecurity25/sec25cycle1-prepub-742-spracklen.pdf)을 기반으로 진행되었습니다.

### 팀원
- 김동재 (소프트웨어학부, 20213107)
- 김민경 (소프트웨어학부, 20221828)
- 김태욱 (전자정보공학부, 20192581)
- 안준엽 (소프트웨어학부, 20211794)

## 연구 목적
- 다양한 LLM 모델의 패키지 추천 정확도 측정
- System prompt에 따른 환각 발생률 비교
- 프롬프트 카테고리별 환각 패턴 분석

## 테스트 모델
- Marin-community/marin-8b-instruct
- Qwen/Qwen2.5-7B-Instruct-Turbo
- Google/gemma-3n-E4B-it
- Mistralai/Mistral-7B-Instruct-v0.2

## 프롬프트 카테고리
| Category | 설명 | 예시 개수 |
|----------|------|-----------|
| Frontend | React, Vue, 빌드 도구 등 | 4997 |
| Error_Handling | 빌드 실패, 모듈 오류 등 | 3583 |
| Backend | DB, ORM, 서버 로직 등 | 2871 |
| Data_Processing | 파싱, 크롤링 등 | 2629 |
| Uncategorized | 기타 | 2418 |
| Web_Development | 웹크롤링, HTTPS, 웹 접근성, HTTP API | 1237 |
| Monitoring | 실시간 이상 탐지, 요청 패턴 분석, 로깅 | 1196 |
| App_Development | 모바일앱, 데스크톱 앱, 앱 빌드 및 배포 | 833 |
| Prompt_Security | TLS/SSL, 취약점 스캔, 비밀키 탐지, 개인정보 보호 | 751 |
| Performance | 트래픽 관리, 이미지 최적화, 캐싱 전략 | 370 |

## 데이터 다운로드

대용량 데이터 파일은 [Releases 페이지](https://github.com/DongJae-Isaac/llm-package-hallucination-detection/releases/latest)에서 다운로드하세요.

### 설치 방법
```bash
# 1. 저장소 클론
git clone https://github.com/DongJae-Isaac/llm-package-hallucination-detection.git
cd llm-package-hallucination-detection

# 2. Releases에서 data_files.zip 다운로드
# https://github.com/DongJae-Isaac/llm-package-hallucination-detection/releases/latest

# 3. 압축 해제
unzip data_files.zip

# 또는 Windows에서는 마우스 우클릭 → "압축 풀기"
```

### 포함된 데이터
- **paper_prompts_expanded_v2.csv** (79MB) - 확장된 프롬프트 데이터셋
- **npm_package_names.csv** (50MB) - NPM 패키지 참조 데이터

## 주요 파일 설명

### 데이터
- `data/prompts/`: 테스트에 사용된 프롬프트 세트
- `data/results/`: 각 모델별 실행 결과
- `data/reference/`: npm 실제 패키지 목록 (검증용)

### 코드
- `src/llm_test/`: LLM API 호출 및 응답 수집
- `src/detection/`: 패키지명 추출 및 환각 판별
- `src/analysis/`: 결과 집계 및 분석

## 주요 결과
[프로젝트 타임라인](data/docs/project_timeline.md) 참조

## 참고 자료
- [원본 논문](https://www.usenix.org/system/files/conference/usenixsecurity25/sec25cycle1-prepub-742-spracklen.pdf)
- [논문 GitHub](https://github.com/Spracks/PackageHallucination)
- [데이터셋 출처](https://zenodo.org/records/14676377)

## 문의
프로젝트 관련 문의는 Issues를 통해 남겨주세요.