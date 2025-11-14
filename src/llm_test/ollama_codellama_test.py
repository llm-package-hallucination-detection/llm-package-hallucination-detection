# ollama_codelama7b_runner.py
# - Ollama (localhost:11434) /api/chat 기반
# - 진행 재개(progress CSV), 중간 저장(SAVE_INTERVAL), 청크 처리(CHUNK_SIZE)
# - Together API 의존 제거, 로컬 LLM 테스트용
# - 타임아웃 개선 및 재시도 로직 강화

import os, time, sys, json, math, re
import pandas as pd
import requests

# ====== 경로/설정 ======
INPUT_CSV     = r"C:\Users\dj021\OneDrive\바탕 화면\2025 2학기\융보프\paper_prompts_expanded_v2.csv"
OUTPUT_CSV    = r"C:\Users\dj021\OneDrive\바탕 화면\2025 2학기\융보프\paper_prompts_expanded_v2_out_ollama_codellama7b.csv"
PROGRESS_CSV  = r"progress_checkpoint_ollama_codellama7b.csv"

MODEL_NAME    = "codellama:7b"   # Ollama 모델 이름 (사전에 pull 필요)
BASE_URL      = "http://localhost:11434/api/chat"
TIMEOUT       = 180              # 180초로 증가
SAVE_INTERVAL = 10               # N행마다 중간 저장
CHUNK_SIZE    = 100              # CSV 읽기 청크 크기
TEMPERATURE   = 0.0
TOP_P         = 0.9
MAX_RETRY     = 5
REQUEST_DELAY = 0.5              # 각 요청 사이에 0.5초 대기

# ====== 유틸 ======
def count_rows_precisely(csv_path: str, chunksize: int = 200_000) -> int:
    total = 0
    for ch in pd.read_csv(csv_path, dtype=str, low_memory=False, chunksize=chunksize):
        total += len(ch)
    return total

def load_progress():
    """이전 진행상황 로드(있으면)"""
    if os.path.exists(PROGRESS_CSV):
        try:
            df = pd.read_csv(PROGRESS_CSV, dtype=str, low_memory=False)
            print(f"✓ 이전 진행상황 발견: {len(df)} 행 이미 처리됨")
            return df
        except Exception as e:
            print(f"⚠ 진행상황 로드 실패: {e}")
    return pd.DataFrame()

def save_progress(df, is_final=False):
    """중간/최종 저장 (원자적 저장 권장)"""
    try:
        df.to_csv(PROGRESS_CSV, index=False, encoding="utf-8-sig")
        if is_final:
            df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
            print(f"✓ 최종 결과 저장: {OUTPUT_CSV}")
        else:
            print(f"  → 중간 저장 완료 ({len(df)} 행)")
    except Exception as e:
        print(f"⚠ 저장 실패: {e}")

def get_processed_indices(progress_df):
    """이미 처리된 행의 인덱스 집합 반환"""
    if progress_df.empty:
        return set()
    if 'original_index' in progress_df.columns:
        return set(progress_df['original_index'].astype(int))
    return set()

# ====== Ollama 호출 ======
def ollama_chat(system_prompt: str, user_prompt: str):
    """
    Ollama /api/chat 호출 (개선된 재시도 로직)
    반환: content, err_msg, latency_sec, prompt_tokens_approx, completion_tokens_approx, total_tokens_approx
    - Ollama 응답의 prompt_eval_count, eval_count를 토큰 근사로 사용
    """
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_prompt or ""},
            {"role": "user",   "content": user_prompt or ""},
        ],
        "stream": False,
        "options": {
            "temperature": TEMPERATURE,
            "top_p": TOP_P,
            "num_predict": 2048  # 최대 토큰 수 명시적 설정
        }
    }

    last_err = ""
    for attempt in range(1, MAX_RETRY + 1):
        t0 = time.perf_counter()
        try:
            r = requests.post(BASE_URL, json=payload, timeout=TIMEOUT)
            latency = time.perf_counter() - t0
            r.raise_for_status()
            data = r.json()

            # /api/chat (stream=false) 포맷:
            # { "message": {"role":"assistant","content":"..."},
            #   "model":"...", "created_at":"...", "done":true,
            #   "eval_count": N, "prompt_eval_count": M, ... }
            msg = (data.get("message") or {})
            content = (msg.get("content") or "").strip()

            prompt_tok = data.get("prompt_eval_count")
            compl_tok  = data.get("eval_count")
            # 근사 total
            total_tok  = (prompt_tok or 0) + (compl_tok or 0)

            return content, "", latency, int(prompt_tok or 0), int(compl_tok or 0), int(total_tok or 0)

        except requests.exceptions.ReadTimeout:
            last_err = f"ReadTimeout after {TIMEOUT}s"
            wait_time = min(5 * attempt, 30)  # 5초 → 10초 → 15초 → 20초 → 25초
            print(f"    -> Timeout (Attempt {attempt}/{MAX_RETRY}), waiting {wait_time}s...")
            time.sleep(wait_time)
            
        except Exception as e:
            # 에러 메시지 구성
            last_err = f"{type(e).__name__}: {e}"
            # 서버 반응 텍스트 일부 남기기
            try:
                if hasattr(e, "response") and e.response is not None:
                    last_err += f" | Server: {e.response.text[:200]}"
            except Exception:
                pass

            wait_time = min(3 * attempt, 20)
            print(f"    -> Ollama Error (Attempt {attempt}/{MAX_RETRY}): {last_err}")
            print(f"       Waiting {wait_time}s before retry...")
            time.sleep(wait_time)

    # 실패 시
    return "", last_err, None, None, None, None

# ====== 메인 루프 ======
def main():
    # 총 행 수(정보용)
    try:
        total_rows = count_rows_precisely(INPUT_CSV)
    except Exception:
        total_rows = 0

    progress_df = load_progress()
    processed_indices = get_processed_indices(progress_df)
    if processed_indices:
        print(f"✓ {len(processed_indices):,} 행 건너뛰기")
        remaining = total_rows - len(processed_indices) if total_rows else "알 수 없음"
        print(f"  → 남은 행: {remaining:,}" if isinstance(remaining, int) else f"  → 남은 행: {remaining}")

    latencies = []
    prompt_tok_sum = 0
    compl_tok_sum = 0
    total_tok_sum = 0
    processed_count = len(processed_indices)

    print(f"▶ 모델 (Ollama): {MODEL_NAME}")
    print(f"▶ 입력 파일: {INPUT_CSV}")
    if total_rows:
        print(f"▶ 총 행 수(정확): {total_rows:,}")
    print(f"▶ 청크 크기: {CHUNK_SIZE} 행")
    print(f"▶ 중간 저장: 매 {SAVE_INTERVAL} 행마다")
    print(f"▶ 타임아웃: {TIMEOUT}초")
    print(f"▶ 요청 간 딜레이: {REQUEST_DELAY}초\n")

    t_begin = time.perf_counter()
    out_rows = progress_df.to_dict('records') if not progress_df.empty else []

    # 청크 단위로 읽기
    for chunk_num, chunk_df in enumerate(pd.read_csv(INPUT_CSV, dtype=str, low_memory=False, chunksize=CHUNK_SIZE), start=1):
        # 필수 컬럼 확보
        for c in ["system_prompt", "request_prompt", "system_prompt_type", "question_num", "question_t_num"]:
            if c not in chunk_df.columns:
                chunk_df[c] = ""

        # 원본 인덱스(재개용)
        chunk_df['original_index'] = chunk_df.index + (chunk_num - 1) * CHUNK_SIZE

        for idx, row in chunk_df.iterrows():
            original_idx = int(row['original_index'])

            # 이미 처리된 행은 스킵
            if original_idx in processed_indices:
                continue

            processed_count += 1
            sys_p = row.get("system_prompt", "") or ""
            usr_p = row.get("request_prompt", "") or ""

            resp, err, latency, ptok, ctok, ttok = ollama_chat(sys_p, usr_p)

            # 각 요청 후 짧은 대기 (서버 부하 감소)
            if REQUEST_DELAY > 0:
                time.sleep(REQUEST_DELAY)

            # 진행 로그
            if latency is not None:
                latencies.append(latency)
                avg = sum(latencies) / len(latencies)
                progress_pct = (processed_count / total_rows * 100) if total_rows else 0
                print(f"[{processed_count:,}/{total_rows:,}] ({progress_pct:.1f}%) | "
                      f"{latency:.2f}s | 평균 {avg:.2f}s" + (f" | ERR: {err}" if err else ""))
            else:
                print(f"[{processed_count:,}/{total_rows:,}] ERR: {err}")

            if ptok is not None: prompt_tok_sum += ptok
            if ctok is not None:  compl_tok_sum  += ctok
            if ttok is not None:  total_tok_sum  += ttok

            # 결과 행 생성
            out = {k: row.get(k, "") for k in chunk_df.columns}
            out["response_prompt"]  = resp
            out["error"]            = err
            out["latency_sec"]      = f"{latency:.4f}" if latency is not None else ""
            out["prompt_tokens"]    = ptok if ptok is not None else ""
            out["completion_tokens"]= ctok if ctok is not None else ""
            out["total_tokens"]     = ttok if ttok is not None else ""
            out_rows.append(out)

            # 중간 저장
            if processed_count % SAVE_INTERVAL == 0:
                save_progress(pd.DataFrame(out_rows), is_final=False)

    # 최종 저장
    out_df = pd.DataFrame(out_rows)
    save_progress(out_df, is_final=True)

    t_elapsed = time.perf_counter() - t_begin
    avg_sec = (sum(latencies) / len(latencies)) if latencies else 0

    print("\n========== 결과 요약 ==========")
    print(f"- 입력 토큰(근사, prompt_eval_count 합계): {prompt_tok_sum:,}")
    print(f"- 출력 토큰(근사, eval_count 합계)      : {compl_tok_sum:,}")
    print(f"- 총 토큰 합계(근사)                    : {total_tok_sum:,}")
    print(f"- 처리된 행 수                          : {processed_count:,} / {total_rows:,}")
    print(f"- 평균 처리 시간                        : {avg_sec:.2f} 초/행")
    print(f"- 총 소요 시간                          : {t_elapsed/3600:.2f} 시간 ({t_elapsed/60:.1f}분)")
    print(f"- 결과 저장                              : {OUTPUT_CSV}")
    print("================================")

if __name__ == "__main__":
    main()