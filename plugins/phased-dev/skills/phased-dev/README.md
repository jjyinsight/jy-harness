# phased-dev (skill)

새 기능이나 새 프로젝트를 **5단계 파이프라인**으로 진행하는 Claude Code skill.
각 단계는 **전담 서브에이전트**가 격리된 컨텍스트에서 실행되고, 결과를 **아티팩트 파일**로 다음 단계에 인계합니다.

```
[사용자 요청]
   ↓
1. Clarify   ──  phased-clarify    →  .phased-dev/artifacts/01-clarify.md
   ↓
2. Context   ──  phased-context    →  .phased-dev/artifacts/02-context.md
   ↓
3. Plan      ──  phased-plan       →  plans/phases/**  +  03-plan.md
   ↓
4. Generate  ──  phased-generate × N →  코드 변경  +  04-generate.md (누적)
   ↓
5. Evaluate  ──  phased-evaluate   →  .phased-dev/artifacts/05-evaluate.md  (옵션)
```

## 빠른 시작

이 skill은 plugin으로 배포됩니다. 설치 방법은 plugin repo의 루트 README를 참고하세요.

설치 후, 어떤 프로젝트에서든 Claude Code에게 다음과 같이 말하면 자동으로 트리거됩니다:
- "phased로 X 만들어줘"
- "단계별로 X 진행해줘"
- "체계적으로 X 짜줘"

처음 트리거 시 메인 에이전트가 자동으로 부트스트랩(`.phased-dev/`와 `plans/phases/` 생성, 러너 스크립트를 프로젝트로 복사)을 수행합니다. 자세한 부트스트랩 절차는 [SKILL.md](./SKILL.md)의 "0. Bootstrap" 섹션 참고.

## 5단계 상세

| # | 단계 | 누가 | 무엇을 |
|---|---|---|---|
| 1 | Clarify  | `phased-clarify`        | `AskUserQuestion`으로 구현/UX/DB 결정을 묶어 묻고 `01-clarify.md`에 정리 |
| 2 | Context  | `phased-context`        | 기존 코드 패턴·관례 정찰, 빈 코드베이스면 즉시 skip |
| 3 | Plan     | `phased-plan`           | 페이즈/태스크 트리 + 의존성 그래프 작성. 코드는 안 짬 |
| 4 | Generate | `phased-generate` × N   | 한 호출에 task 1개만 구현. status를 done으로 마킹 |
| 5 | Evaluate | `phased-evaluate`       | typecheck/lint/build/test 실행, 보고만 (코드 수정 금지) |

각 서브에이전트는 자기 단계에 필요한 도구만 가집니다 (예: phased-context는 Read/Glob/Grep/Write만, phased-clarify는 AskUserQuestion/Read/Write만).

## 프로젝트가 만들게 되는 폴더 구조

부트스트랩 후 프로젝트 디렉토리에 다음이 생깁니다:

```
.phased-dev/
  run_phases.py                       ← 러너 사본 (부트스트랩이 plugin에서 복사)
  artifacts/
    01-clarify.md  …  05-evaluate.md  ← 단계별 산출물

plans/phases/
  01-foundation/
    README.md                         ← 페이즈 개요
    01-setup.md, 02-models.md, …      ← 개별 task (frontmatter status 추적)
  02-features/
    …
```

`.phased-dev/`와 `plans/`를 git에 커밋할지는 팀 컨벤션에 따라 결정:
- **커밋 권장**: 결정 사항·계획·진행 이력이 코드 리뷰에 함께 노출됨
- **gitignore**: 결정 이력을 별도 문서로 관리하고 싶을 때

## run_phases.py 빠른 참조

부트스트랩 이후 모두 `python .phased-dev/run_phases.py <cmd>` 로:

| 명령 | 용도 |
|---|---|
| `status`            | 파이프라인 단계 + 모든 task의 현재 상태 |
| `next`              | 다음 실행 가능한 pending task 경로 출력 |
| `run`               | 실행 가능한 / 의존성 대기 중인 task 한눈에 |
| `start <path>`      | task를 in-progress로 마킹 |
| `done <path>`       | task를 done으로 마킹 |
| `block <path>`      | task를 blocked로 마킹 |
| `reset <path>`      | task를 pending으로 되돌림 |
| `artifact <phase>`  | 특정 단계 아티팩트 경로 출력 (clarify/context/plan/generate/evaluate) |
| `validate <phase>`  | 아티팩트 존재·필수 섹션 검사 (exit 0 = OK) |

`init` 서브커맨드는 plugin 안 원본 스크립트로 부트스트랩 시 한 번만 호출됩니다.

## 자주 묻는 것

**Q. 이미 만들어진 코드베이스에도 쓸 수 있나요?**
A. 네. 2단계 Context Gather가 기존 패턴/관례를 정찰해 Plan에 반영합니다.

**Q. 5단계를 한 번에 자동 실행시킬 수 있나요?**
A. 의도적으로 막아둡니다. Plan 직후와 페이즈 종료 시 사용자 승인 게이트가 있어요. 큰 흐름이 잘못된 채 코드만 쌓이는 것을 방지하려는 장치입니다.

**Q. task 하나가 너무 크면?**
A. phased-plan에게 더 잘게 쪼개라고 재지시하거나, 해당 task를 `block`으로 막고 fix-up task를 추가하세요.

**Q. evaluate 단계가 실패하면?**
A. `05-evaluate.md`의 **권고** 섹션에 따라 해당 task를 `reset`해 phased-generate에 다시 보내거나, `plans/phases/.../99-fix-*.md` 같은 fix-up task를 추가합니다.

**Q. plugin 업데이트 후엔 뭘 해야 하나요?**
A. 부트스트랩을 한 번 더 실행하면 `.phased-dev/run_phases.py`가 새 버전으로 갱신됩니다 (서브에이전트 정의는 plugin이 자동 갱신).

**Q. 메인 에이전트가 자기가 직접 코드 짜려고 하면?**
A. SKILL.md의 "안티패턴" 섹션에 명시돼 있어요 — 메인은 오케스트레이터일 뿐, 모든 코드 변경은 phased-generate 서브에이전트가 합니다.

## 안티패턴 한 줄 요약

- 메인이 직접 `AskUserQuestion` 띄우기 → Clarify의 일
- 메인이 직접 `Edit`/`Write`로 코드 짜기 → Generate의 일
- 한 Generate 호출에 여러 task 묶어 보내기 → 격리·재시도가 깨짐
- `validate` 게이트 건너뛰고 다음 단계 진입 → 빈 입력 위에 산출물이 쌓임

자세한 동작 규칙은 [SKILL.md](./SKILL.md)에 있습니다.
