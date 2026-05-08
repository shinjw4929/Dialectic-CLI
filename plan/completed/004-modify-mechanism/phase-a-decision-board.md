# Phase A · Decision Board — 004-modify-mechanism

## 0. 메타

- Phase ID: A
- 소속 plan: [00-plan.md](00-plan.md)
- 의존 Phase: (없음)
- 병렬 그룹: — (Phase B/C/D의 선행 단일)
- 예상 LOC: ~45 줄 추가 / ~5 줄 변경 (`outline/README.md` + `docs/dev-docs/architecture.md` 2 파일)

## 1. 목표

`outline/README.md` §0 사전 확인 + §6 결정 보드에 Q22(코드 수정 메커니즘 = A2) + Q23(데모 task = c modify 전용 신규)을 도장. **추가**: Q22가 protocol 차원 변경(메시지 스키마 신규 `kind` + 라이프사이클 R2.6/R2.7 + 어댑터 추상화)이라 ADR로 승격 — `docs/dev-docs/architecture.md` §6 ADR 표에 ADR-10 행 추가 + 헤더 "9개" → "10개" 갱신 (Documentation-Checklist:119 매핑 준수). 후속 Phase B/C/D가 인용할 단일 출처 수립.

## 2. 입력

- AS-IS:
  - `outline/README.md:26-35` (§0 사전 확인 표), `outline/README.md:37-41` (§0 표 직후 스모크 테스트 단락 + 결론 줄 — line 41 = "→ 양쪽 다 텍스트 in/out..." 결론)
  - `outline/README.md:47-69` (§6 결정 보드 ``` 코드 펜스, line 47=펜스 시작, 48-68=Q1~Q21, 68=Q21, 69=펜스 닫힘)
  - `docs/dev-docs/architecture.md:122` (헤더 "## 6. ADR — 핵심 설계 결정 9개"), `docs/dev-docs/architecture.md:126-136` (ADR 표 헤더 + 9 데이터 행 ADR-1~9), `docs/dev-docs/architecture.md:138` (표 직후 단락 "각 ADR의 더 깊은 논의는 outline/...")
- 결정 사실:
  - Q22 = A2 (search-replace 블록): LLM 응답에 `FILE: <path>\n<<<<<<< SEARCH\n...\n=======\n...\n>>>>>>> REPLACE` 텍스트 → orchestrator 정규식 추출 + SEARCH 정확 일치 검색 + REPLACE 치환. line number 의존 0.
  - Q23 = c (modify 전용 task 신규 추가): 기존 후보(`wave_difficulty` 등) 유지 + `tasks/<modify_task_id>/` 신규 task 추가. task.md 본문은 별도 후속 plan에서.
  - **Q22 ADR 승격 사유**: 메시지 스키마 신규 `kind=patch_applied` + 4 신규 `meta` 필드 + 턴 라이프사이클 R2.6/R2.7 신설 + 어댑터 추상화(텍스트 in/out 보존). 영향 폭이 ADR-1(JSONL 통신)·ADR-9([CONVERGED] K=2)와 같은 layer. Documentation-Checklist:119 "새 ADR 결정 시 architecture ADR 표 + outline 결정 보드 동시 갱신" 매핑 준수.
- 참조: `docs/dev-docs/Plans/plan-writing-guide.md` §3 (코드 블록 라벨 규칙), `docs/dev-docs/Documentation-Checklist.md` §1.7 (큰 결정·아키텍처 변경 매핑).

## 3. 출력

`outline/README.md` 변경:

### 3.1 §0 line 41 (스모크 테스트 결론 줄) 직후, line 43 (`---` 구분선) 직전에 1단락 추가

(line 41 = "→ **양쪽 다 텍스트 in/out 어댑터 작성 가능**." 결론 줄. line 42 = 빈 줄. 신규 단락은 line 41 직후 빈 줄 + 본문 + 빈 줄로 line 43 `---` 직전에 끼움.)

```markdown
# paste
**코드 수정 메커니즘 (Q22 ✅ A2)**: driver 응답에 `FILE: <path>` 헤더 + `<<<<<<< SEARCH / ======= / >>>>>>> REPLACE` 블록(이하 search-replace)을 텍스트로 명시. orchestrator가 정규식 추출 → workdir 파일에서 SEARCH 정확 일치 검색 → REPLACE 치환 → `kind=patch_applied` 메시지 append. CLI 네이티브 도구(write_file 등) 미사용 — 어댑터 추상화 일관 + line number 의존 0으로 LLM 오류 면역. 상세: §2.2 (스키마), §2.3 (R2 patches 추출 + R2.6 apply + R2.7 기록 라이프사이클), §1.4 (implementer 셀프체크).
```

### 3.2 §6 결정 보드 line 68 (Q21 행) 직후, line 69 (``` 닫힘) 직전에 Q22, Q23 추가

(line 67 = Q20, line 68 = Q21, line 69 = ``` 펜스 닫힘. Q22/Q23 두 줄은 Q21 다음 줄이자 ``` 닫힘 직전에 삽입.)

```markdown
# paste
✅ Q22 코드 수정 메커니즘 = A2 (search-replace 블록). LLM 응답에 `FILE: ... <<<<<<< SEARCH / ======= / >>>>>>> REPLACE` 텍스트 → orchestrator parser 적용. line number 의존 0으로 LLM 오류 면역. parser ~30 LOC. 어댑터 텍스트 in/out 추상화 유지 (대안 C: CLI 네이티브 도구 사용 — 추상화 누수 risk로 기각). 적용 — §2.2 메시지 스키마, §2.3 턴 라이프사이클, §1.4 implementer 셀프체크, §4.6 비용
✅ Q23 데모 task에 modify 시나리오 = c (modify 전용 task 신규 추가). 기존 wave_difficulty(신규 작성) 유지 + tasks/<modify_task_id>/ (예: 기존 룰 함수 결함 수정) 별도 추가. 신규+수정 양쪽 시연. modify task 본문 작성은 별도 후속 plan — 04-§4.3 후보 표에 항목만 명시
```

### 3.3 `docs/dev-docs/architecture.md` §6 ADR 표에 ADR-10 행 추가 (line 136 ADR-9 행 직후)

```markdown
# paste
| **ADR-10** | 코드 수정 메커니즘 = search-replace 블록 (LLM 응답에 `FILE / <<<<<<< SEARCH / ======= / >>>>>>> REPLACE` 마커. orchestrator가 정규식 추출 + 정확 일치 검색 + REPLACE 치환. R2 메시지 append 시 `meta.patches` 동시 기록(P-JSONL append-only), R2.6 apply, R2.7 `kind=patch_applied` 별도 append) | line number 의존 0으로 LLM 오류 면역. 어댑터 텍스트 in/out 추상화 보존(CLI 네이티브 write_file 미사용 → 벤더 비대칭 회피). 신규 파일·기존 파일 수정 둘 다 동일 흐름 | A1 unified diff(line number 의존, LLM diff 자주 오류) / A3 full file replace(토큰 낭비) / C CLI 네이티브 도구(어댑터 추상화 누수, 세션 상태 비대칭) / D driver만 write(AgentRunner Protocol 비대칭) |
```

### 3.4 `docs/dev-docs/architecture.md:122` 헤더 갱신

기존: `## 6. ADR — 핵심 설계 결정 9개`
→ 갱신: `## 6. ADR — 핵심 설계 결정 10개`

## 4. 작업 단위

- [ ] `outline/README.md` §0 line 41 (스모크 테스트 결론 줄) 직후, line 43 `---` 구분선 직전에 §3.1 단락 추가
- [ ] `outline/README.md` §6 line 68 (Q21 행) 직후, line 69 ``` 펜스 닫힘 직전에 §3.2의 Q22, Q23 두 줄 추가
- [ ] `docs/dev-docs/architecture.md` line 136 (ADR-9 행) 직후에 §3.3의 ADR-10 행 추가
- [ ] `docs/dev-docs/architecture.md` line 122 헤더 "9개" → "10개" 갱신
- [ ] §0 단락 ↔ §6 Q22 본문 ↔ ADR-10 본문 3중 일관 검증 (메커니즘 명칭·옵션 라벨·section 인용·거부 대안 모두 동일 단어)

## 5. 검증

- `grep -n "Q22\|Q23" outline/README.md` — **최소 3행** 출현 확인 (§0 단락 "Q22 ✅ A2" 1회 + §6 결정 보드 Q22·Q23 2회)
- `grep -n "search-replace" outline/README.md` — §6 등장 (§0 단락은 SEARCH/REPLACE 블록 형식만 묘사)
- `grep -n "코드 수정 메커니즘" outline/README.md` — §0 단락 1회 확인
- `grep -n "ADR-10" docs/dev-docs/architecture.md` — §6 ADR 표 1회 출현
- `grep -n "10개" docs/dev-docs/architecture.md` — line 122 헤더 갱신 확인
- 사람 검토: §0 단락 ↔ §6 Q22 ↔ ADR-10 3중 일관 (메커니즘 명칭·거부 대안 동일 단어 사용)

## 6. 엣지케이스 / 위험 (Phase 한정)

- **Q22 Q23 번호 충돌** — `outline/README.md:68` 마지막 결정이 Q21. Q22/Q23로 진행 안전. (다른 outline 파일에 Q22 미사용 확인됨)
- **§0 표 형식 깨짐** — §0은 markdown 표(line 26-35) + 스모크 테스트 단락(line 37-41) 혼합. 표 행 추가 X — 신규 단락은 line 41 결론 줄 직후, line 43 `---` 구분선 직전에 삽입.
- **mermaid 인용 미스매치** — Q22 본문에 인용한 §2.3 R2.6/R2.7 (R2.5는 NO-OP라 제거)는 Phase B에서 작성 예정. Phase A 시점엔 아직 미존재 — 단방향 forward reference 허용 (review-plan 시점에 cross-check).
- **ADR-10 행 위치** — `architecture.md:136`이 ADR-9 행. ADR-10은 line 136 직후, line 137(빈 줄) 또는 138(단락) 직전에 삽입. 표 grid 깨지지 않도록 동일 컬럼 수(`| ID | 결정 | 이유 | 거부된 대안 |`) 유지.
- **ADR-10 거부 대안 vs Q22 거부 대안 일관** — outline/README.md §6 Q22 본문 거부 대안(C CLI 네이티브 도구) ↔ architecture.md ADR-10 거부 대안(A1/A3/C/D)이 일관해야. ADR이 더 풍부한 trade-off 명시(A1/A3까지) — 이는 의도된 차이(ADR이 결정 기록의 정통).
