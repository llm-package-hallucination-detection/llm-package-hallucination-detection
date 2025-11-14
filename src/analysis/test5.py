import pandas as pd
import requests
from collections import defaultdict
import re
import time
from typing import Optional, Tuple, Dict, Set
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# --- 설정 ---
FILE_NAME = 'progress_checkpoint_marin.csv'
OUTPUT_FILENAME = 'FINAL_verified_libraries_v7.csv'
SAVE_INTERVAL = 50
REQUEST_DELAY = 0.1  # NPM API Rate Limit 대응 (100ms 대기)
MAX_WORKERS = 5  # 병렬 처리 시 사용할 워커 수

# --- 키워드 사전 (확장) ---
NODE_BUILTINS = {
    'fs', 'path', 'http', 'https', 'os', 'events', 'stream', 'crypto', 'util',
    'assert', 'url', 'zlib', 'child_process', 'process', 'buffer', 'net',
    'dns', 'dgram', 'tls', 'readline', 'repl', 'vm', 'querystring',
    'string_decoder', 'timers', 'tty', 'worker_threads', 'cluster'
}

JS_KEYWORDS = {
    'Promise', 'fetch', 'target', 'event', 'console', 'JSON', 'Date', 'Math',
    'Array', 'Object', 'String', 'Number', 'Boolean', 'Map', 'Set', 'Symbol',
    'Proxy', 'Reflect', 'Error', 'RegExp', 'Function', 'Window', 'Document',
    'Element', 'Node', 'Event', 'XMLHttpRequest', 'WebSocket', 'localStorage',
    'sessionStorage', 'setTimeout', 'setInterval', 'requestAnimationFrame'
}

# NPM에는 존재하지만 일반적으로 키워드로 잘못 인식되는 것들
COMMON_FALSE_POSITIVES = {
    'test', 'example', 'demo', 'main', 'index', 'app', 'component',
    'service', 'controller', 'model', 'view', 'helper', 'utils', 'config'
}


class NPMVerifier:
    """NPM 패키지 검증 클래스 (재시도 로직 포함)"""
    
    def __init__(self):
        # Retry 전략 설정
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        
        self.session = requests.Session()
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        
        # 캐시 (중복 요청 방지)
        self.cache: Dict[str, bool] = {}
    
    def verify_npm_package(self, name: str) -> Tuple[bool, str]:
        """
        NPM 패키지 존재 확인
        
        Returns:
            (존재 여부, 상태 메시지)
        """
        # 캐시 확인
        if name in self.cache:
            return self.cache[name], 'Cached'
        
        url = f"https://registry.npmjs.org/{name.lower()}"
        
        try:
            time.sleep(REQUEST_DELAY)  # Rate limiting
            response = self.session.get(url, timeout=5)
            
            exists = response.status_code == 200
            self.cache[name] = exists
            
            if exists:
                return True, 'Verified'
            else:
                return False, f'Not Found (HTTP {response.status_code})'
                
        except requests.Timeout:
            return False, 'Timeout'
        except requests.RequestException as e:
            return False, f'Network Error: {type(e).__name__}'


def normalize_and_validate_name(name: str) -> Optional[str]:
    """
    패키지 이름 정규화 및 검증 (개선 버전)
    """
    if not name or not isinstance(name, str):
        return None

    # 공백 및 따옴표 제거
    cleaned = name.strip().strip('`\'"')
    
    # 기본 필터링
    if not cleaned or len(cleaned) > 214:  # NPM 최대 길이
        return None
    
    # 명백히 잘못된 패턴
    invalid_patterns = [
        r'^\d+$',  # 순수 숫자
        r'^[.\-_/]',  # 특수문자로 시작
        r'[()[\];{}]',  # 코드 구문
        r'\s',  # 공백
        r'[<>]',  # HTML 태그
        r'^https?://',  # URL
    ]
    
    for pattern in invalid_patterns:
        if re.search(pattern, cleaned):
            return None
    
    # NPM 규칙: 소문자, 숫자, 하이픈, 언더스코어(비권장), 점, @(스코프), /(스코프 구분)
    if not re.match(r'^(@[a-z0-9-~][a-z0-9-._~]*/)?[a-z0-9-~][a-z0-9-._~]*$', cleaned, re.IGNORECASE):
        return None
    
    return cleaned


def extract_keywords_from_response(response: str) -> Set[str]:
    """
    응답 텍스트에서 키워드 추출 (개선 버전)
    """
    if not response or not isinstance(response, str):
        return set()
    
    response = response.strip()
    
    # 무효한 응답 필터링
    invalid_responses = ['none', 'n/a', 'null', 'undefined', '-', '']
    if response.lower() in invalid_responses:
        return set()
    
    keywords = set()
    
    # 쉼표로 구분된 경우
    if ',' in response:
        parts = response.split(',')
    # 세미콜론으로 구분된 경우
    elif ';' in response:
        parts = response.split(';')
    # 줄바꿈으로 구분된 경우
    elif '\n' in response:
        parts = response.split('\n')
    # 단일 키워드
    else:
        parts = [response]
    
    for part in parts:
        cleaned = normalize_and_validate_name(part)
        if cleaned:
            keywords.add(cleaned)
    
    return keywords


def classify_package(name: str, verifier: NPMVerifier) -> Tuple[str, str]:
    """
    패키지 분류 (개선 버전)
    
    Returns:
        (분류, 상세 정보)
    """
    name_lower = name.lower()
    
    # 1. Node.js 내장 모듈
    if name_lower in NODE_BUILTINS:
        return 'Built-in Module', 'Node.js Core'
    
    # 2. JavaScript 키워드/개념
    if name in JS_KEYWORDS:
        return 'JS Keyword/Concept', 'JavaScript Built-in'
    
    # 3. 일반적인 오탐
    if name_lower in COMMON_FALSE_POSITIVES:
        # NPM에 실제로 있는지 확인
        exists, status = verifier.verify_npm_package(extract_root_package(name))
        if exists:
            return 'NPM Package (Common Word)', status
        else:
            return 'False Positive', 'Common word but not NPM package'
    
    # 4. NPM 패키지 검증
    root_package = extract_root_package(name)
    exists, status = verifier.verify_npm_package(root_package)
    
    if exists:
        return 'NPM Package', status
    else:
        return 'Unknown/Invalid', status


def extract_root_package(name: str) -> str:
    """
    스코프 패키지에서 루트 패키지명 추출
    
    Examples:
        '@angular/common/http' -> '@angular/common'
        'lodash/get' -> 'lodash'
    """
    if name.startswith('@'):
        parts = name.split('/')
        if len(parts) >= 2:
            return f"{parts[0]}/{parts[1]}"
        return name
    else:
        return name.split('/')[0]


def analyze_csv(file_path: str) -> pd.DataFrame:
    """CSV 파일 분석 메인 함수"""
    
    print(f"📂 파일 로드 중: {file_path}")
    df = pd.read_csv(file_path)
    print(f"✅ {len(df)} 행 로드 완료\n")
    
    # 코드 블록이 없는 응답만 선택
    non_code_df = df[
        ~df['response_prompt'].str.contains('```', na=True) &
        df['response_prompt'].notna()
    ]
    
    print(f"🔍 분석 대상: {len(non_code_df)} 행 (코드 블록 제외)")
    
    # 키워드 추출
    keyword_locations: Dict[str, Set[int]] = defaultdict(set)
    
    for index, row in non_code_df.iterrows():
        response = row['response_prompt']
        keywords = extract_keywords_from_response(response)
        
        for keyword in keywords:
            line_number = index + 2  # CSV 헤더 포함
            keyword_locations[keyword].add(line_number)
    
    if not keyword_locations:
        print("⚠️ 추출된 키워드가 없습니다.")
        return pd.DataFrame()
    
    print(f"📊 추출된 고유 키워드: {len(keyword_locations)}개\n")
    
    # 데이터프레임 생성
    data = []
    for keyword, lines in keyword_locations.items():
        data.append({
            'keyword': keyword,
            'occurrence_count': len(lines),
            'line_numbers': sorted(list(lines))
        })
    
    result_df = pd.DataFrame(data).sort_values('occurrence_count', ascending=False)
    return result_df


def verify_and_classify(df: pd.DataFrame, output_file: str) -> pd.DataFrame:
    """패키지 검증 및 분류"""
    
    if df.empty:
        return df
    
    verifier = NPMVerifier()
    total = len(df)
    
    print(f"🔬 {total}개 키워드 검증 시작...\n")
    
    df['classification'] = ''
    df['verification_status'] = ''
    
    start_time = time.time()
    
    for idx, row in df.iterrows():
        keyword = row['keyword']
        progress = idx + 1
        
        # 분류 및 검증
        classification, status = classify_package(keyword, verifier)
        
        df.at[idx, 'classification'] = classification
        df.at[idx, 'verification_status'] = status
        
        # 진행 상황 출력
        elapsed = time.time() - start_time
        avg_time = elapsed / progress
        eta = avg_time * (total - progress)
        
        print(f"[{progress}/{total}] {keyword:30} → {classification:25} "
              f"(ETA: {eta:.1f}s)")
        
        # 중간 저장
        if progress % SAVE_INTERVAL == 0:
            print(f"\n💾 중간 저장... ({progress}/{total})")
            df.to_csv(output_file, index=False, encoding='utf-8-sig')
            print()
    
    # 최종 저장
    elapsed = time.time() - start_time
    print(f"\n✅ 검증 완료! (소요 시간: {elapsed:.1f}초)")
    print(f"💾 최종 저장: {output_file}\n")
    
    df.to_csv(output_file, index=False, encoding='utf-8-sig')
    
    return df


def print_summary(df: pd.DataFrame):
    """결과 요약 출력"""
    
    if df.empty:
        print("분석 결과가 없습니다.")
        return
    
    print("\n" + "="*80)
    print("📊 분석 결과 요약")
    print("="*80)
    
    # 분류별 통계
    classification_counts = df['classification'].value_counts()
    print("\n[분류별 통계]")
    for category, count in classification_counts.items():
        percentage = (count / len(df)) * 100
        print(f"  {category:30} {count:5} ({percentage:5.1f}%)")
    
    # 상위 패키지
    print("\n[가장 많이 사용된 패키지 TOP 15]")
    top_packages = df.nlargest(15, 'occurrence_count')
    for idx, row in top_packages.iterrows():
        print(f"  {row['keyword']:30} {row['occurrence_count']:3}회  "
              f"({row['classification']})")
    
    # NPM 패키지만 필터링
    npm_only = df[df['classification'].str.contains('NPM Package', na=False)]
    print(f"\n✨ 검증된 NPM 패키지: {len(npm_only)}개")
    
    print("="*80 + "\n")


# --- 메인 실행 ---
if __name__ == "__main__":
    try:
        # 1. CSV 분석
        result_df = analyze_csv(FILE_NAME)
        
        if result_df.empty:
            print("❌ 분석할 데이터가 없습니다.")
        else:
            # 2. 검증 및 분류
            final_df = verify_and_classify(result_df, OUTPUT_FILENAME)
            
            # 3. 결과 요약
            print_summary(final_df)
            
            # 4. NPM 패키지만 별도 저장
            npm_only = final_df[
                final_df['classification'].str.contains('NPM Package', na=False)
            ]
            npm_output = OUTPUT_FILENAME.replace('.csv', '_npm_only.csv')
            npm_only.to_csv(npm_output, index=False, encoding='utf-8-sig')
            print(f"📦 NPM 패키지만 별도 저장: {npm_output}")
            
    except FileNotFoundError:
        print(f"❌ 파일을 찾을 수 없습니다: {FILE_NAME}")
    except KeyError as e:
        print(f"❌ 필수 컬럼이 없습니다: {e}")
        print("CSV 파일에 'response_prompt' 컬럼이 있는지 확인하세요.")
    except Exception as e:
        print(f"❌ 예상치 못한 오류: {e}")
        import traceback
        traceback.print_exc()