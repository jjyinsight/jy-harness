---
name: phased-dev
description: 5단계(Clarify → Context → Plan → Generate → Evaluate) 파이프라인으로 새 프로젝트나 큰 기능을 단계별로 진행한다. 각 단계는 전담 서브에이전트가 실행하고 결과를 아티팩트 파일로 다음 단계에 인계. 사용자가 "단계별로", "phased", "phase", "체계적으로", "처음부터 짜줘" 같은 요청을 하거나 빈/새 프로젝트에서 작업을 시작할 때 트리거.
---

# Phased Development (Pipeline)

5단계 파이프라인. 각 단계는 **전담 서브에이전트**가 실행하고, 결과를 `.phased-dev/artifacts/NN-<phase>.md` **아티팩트**로 남겨 다음 단계의 입력이 된다. 메인(이 SKILL을 읽는 에이전트)은 오케스트레이터일 뿐이며 직접 코드를 만들지 않는다.

## 파이프라인 한눈에 보기

| # | 단계 | 서브에이전트 | 입력 아티팩트 | 출력 아티팩트 |
|---|---|---|---|---|
| 1 | Clarify  | `phased-clarify`  | (사용자 요청) | `.phased-dev/artifacts/01-clarify.md` |
| 2 | Context  | `phased-context`  | 01 | `.phased-dev/artifacts/02-context.md` |
| 3 | Plan     | `phased-plan`     | 01, 02 | `plans/phases/**` + `03-plan.md` |
| 4 | Generate | `phased-generate` × N | 01, 02, task 파일 | (코드 변경) + `04-generate.md` 누적 |
| 5 | Evaluate | `phased-evaluate` | 01, 02, 04 | `.phased-dev/artifacts/05-evaluate.md` |

각 서브에이전트는 이 plugin의 `agents/phased-*.md`에 정의되어 있으며 plugin 설치 시 Claude Code가 자동으로 등록한다.

## 메인 오케스트레이터의 의무

1. **선언만 하고 위임**: 각 단계의 일은 서브에이전트에게 맡긴다. 직접 Clarify 질문을 묻거나, 직접 task 코드를 짜지 마라.
2. **단계 간 게이트**: 다음 단계로 가기 전에 이전 단계 아티팩트의 검증을 통과해야 한다 (`run_phases.py validate <phase>`).
3. **사용자 승인 게이트**: Plan 직후, Generate 페이즈 단위 종료 직후에는 사용자에게 보고하고 진행 여부를 확인한다.
4. **상태는 파일이 사실**: 진행 상태는 아티팩트 파일과 task frontmatter가 진실. 메모리에 의존하지 마라.

## 전체 흐름

### 0. Bootstrap

플러그인 설치 후 새 프로젝트에서 처음 사용할 때 한 번만. 메인 에이전트는 plugin 설치 위치에서 러너 스크립트를 찾아 `init`을 실행한다.

**Linux / macOS**:
```bash
RUNNER=$(find "$HOME/.claude/plugins" -name run_phases.py -path "*phased-dev*" 2>/dev/null | head -1)
python "$RUNNER" init
```

**Windows PowerShell**:
```powershell
$Runner = Get-ChildItem "$env:USERPROFILE\.claude\plugins" -Recurse -Filter run_phases.py -ErrorAction SilentlyContinue | Where-Object { $_.FullName -like "*phased-dev*" } | Select-Object -First 1 -ExpandProperty FullName
python $Runner init
```

이 명령이 `.phased-dev/artifacts/`, `plans/phases/`를 만들고 러너를 `.phased-dev/run_phases.py`로 프로젝트에 복사한다. **이후 모든 호출은 `python .phased-dev/run_phases.py …`** (프로젝트 안 사본).

플러그인 업데이트 후엔 다시 한 번 부트스트랩을 돌리면 새 버전 러너가 프로젝트로 갱신 복사된다.

### 1. Clarify
```
Agent(
  subagent_type="phased-clarify",
  description="Clarify requirements",
  prompt="""사용자의 초기 요청은 다음과 같다:
<<사용자 요청 원문>>

이 요청에 대해 Clarify 단계를 수행하고 .phased-dev/artifacts/01-clarify.md를 작성하라.
"""
)
```
서브에이전트가 사용자에게 직접 `AskUserQuestion`을 띄운다. 끝나면 메인은:
```
python .phased-dev/run_phases.py validate clarify
```
실패면 서브에이전트를 재호출(보강 지시).

### 2. Context
```
python .phased-dev/run_phases.py validate clarify   # 게이트
Agent(
  subagent_type="phased-context",
  description="Gather codebase context",
  prompt="""01-clarify.md를 입력으로 .phased-dev/artifacts/02-context.md를 작성하라.
빈 코드베이스로 판단되면 'empty' 상태만 적고 마무리하라.
"""
)
python .phased-dev/run_phases.py validate context
```

### 3. Plan
```
python .phased-dev/run_phases.py validate context
Agent(
  subagent_type="phased-plan",
  description="Build phase/task tree",
  prompt="""01-clarify.md와 02-context.md를 입력으로 plans/phases/ 트리와
.phased-dev/artifacts/03-plan.md 인덱스를 작성하라.
"""
)
python .phased-dev/run_phases.py validate plan
```
**여기서 사용자에게 트리 요약을 보여주고 승인 받는다.** 계획 변경 요청이 오면 서브에이전트를 재호출.

### 4. Generate (task 단위로 반복)
한 task당 한 번 호출. 절대 한 호출에 여러 task를 처리시키지 마라.

```
loop:
  task = python .phased-dev/run_phases.py next     # 다음 runnable task 경로
  if no task: break
  Agent(
    subagent_type="phased-generate",
    description=f"Implement {task}",
    prompt=f"""대상 task: {task}
참고:
  - .phased-dev/artifacts/01-clarify.md
  - .phased-dev/artifacts/02-context.md
러너: .phased-dev/run_phases.py

이 task만 구현하고 status를 done으로 마킹한 뒤 04-generate.md에 한 줄 추가하라.
"""
  )
  python .phased-dev/run_phases.py status          # 진척 확인
```

페이즈 한 개가 다 done이 되면 **사용자에게 보고하고 다음 페이즈로 갈지 확인**. 한 호출에 모든 페이즈를 자동 진행하지 마라.

#### 병렬화 (옵션)
서로 의존이 없고 같은 파일을 건드리지 않는 task들은 한 메시지에 여러 `Agent` 호출을 묶어 병렬 실행할 수 있다. 의심스러우면 순차로.

### 5. Evaluate (옵션)
```
Agent(
  subagent_type="phased-evaluate",
  description="Run typecheck/lint/build/test",
  prompt="""01-clarify.md, 02-context.md, 04-generate.md를 입력으로 검증을 수행하고
.phased-dev/artifacts/05-evaluate.md에 보고서를 작성하라.
"""
)
python .phased-dev/run_phases.py validate evaluate
```
실패 항목이 있으면 보고서의 **권고**에 따라:
- 기존 task를 `reset`하고 `phased-generate` 재호출, 또는
- 새 fix-up task를 `plans/phases/.../99-fix-*.md`로 추가하고 다시 Generate 루프.

## 게이트 / 검증 표준

각 단계의 아티팩트는 다음 조건을 충족해야 다음 단계로 갈 수 있다 (`run_phases.py validate`가 검사):

- **clarify**: `# Clarify`, `## 결정` 섹션 존재
- **context**: `# Context`, `## 코드베이스 상태` 섹션 존재
- **plan**: `# Plan`, `## 페이즈` 섹션 존재 + `plans/phases/` 트리 비어있지 않음
- **generate**: `# Generate Log` 헤더 존재 (task가 하나라도 처리되면 자동)
- **evaluate**: `# Evaluate`, `## 실행한 명령` 존재

게이트가 실패하면 메인은 해당 단계 서브에이전트를 보강 지시와 함께 재호출하고, 실패가 반복되면 사용자에게 무엇이 막혔는지 보고한다.

## 안티패턴

- 메인이 직접 `AskUserQuestion`으로 요구사항을 물어보기 → Clarify 서브에이전트의 일.
- 메인이 직접 `Edit`/`Write`로 task 구현 → Generate 서브에이전트의 일.
- 한 Generate 호출에 여러 task 묶어 보내기 → 격리·재시도가 깨진다.
- 게이트 검사 없이 다음 단계로 넘어가기 → 후속 아티팩트가 빈 입력 위에 쌓인다.
- Plan 단계 후 사용자 승인 없이 자동 Generate로 진입 → 계획 폐기 비용이 크다.
