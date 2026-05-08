# phased-dev-tools

Claude Code **plugin marketplace** for the team.
현재 1개 plugin(`phased-dev`)을 호스팅합니다.

## 팀원 설치 (Claude Code 안에서)

이 repo가 GitHub에 `OWNER/phased-dev-tools` 라고 가정 (사내 GitLab 등은 아래 "다른 git 호스트" 참고).

```
/plugin marketplace add OWNER/phased-dev-tools
/plugin install phased-dev@phased-dev-tools
```

설치 확인:
```
/plugin list
```

### 다른 git 호스트 (사내 GitLab/Bitbucket/자체 git)

```
/plugin marketplace add https://gitlab.example.com/team/phased-dev-tools.git
/plugin marketplace add git@gitlab.example.com:team/phased-dev-tools.git
```

GitHub 외 호스트는 full URL 또는 SSH URL을 사용합니다.

## 자동 업데이트 (선택)

설치만 하려면 git 읽기 권한만 있으면 됩니다 (SSH 키 또는 평소 쓰던 git credential helper 그대로). **자동 업데이트**까지 받으려면 토큰을 환경변수로 설정합니다.

| Provider  | 환경변수 | 토큰 권한 |
|---|---|---|
| GitHub    | `GITHUB_TOKEN` 또는 `GH_TOKEN` | repo (read) |
| GitLab    | `GITLAB_TOKEN` | read_repository |
| Bitbucket | `BITBUCKET_TOKEN` | repository:read |

Windows PowerShell 영구 설정 예:
```powershell
[Environment]::SetEnvironmentVariable("GITHUB_TOKEN", "ghp_...", "User")
```

자동 업데이트를 끄고 싶을 때:
```bash
export DISABLE_AUTOUPDATER=1
```

## 어떤 skill인가요?

`phased-dev`는 Clarify → Context → Plan → Generate → Evaluate 5단계 파이프라인으로 새 기능·새 프로젝트 작업을 진행시키는 skill입니다. 각 단계가 격리된 서브에이전트에서 실행되어 메인 컨텍스트를 깨끗하게 유지하고, 단계 간 결과는 아티팩트 파일로 인계됩니다.

자세한 동작은 [`plugins/phased-dev/skills/phased-dev/README.md`](plugins/phased-dev/skills/phased-dev/README.md)와 [`SKILL.md`](plugins/phased-dev/skills/phased-dev/SKILL.md) 참고.

## Repo 구조

```
.claude-plugin/
  marketplace.json                       ← 마켓플레이스 카탈로그
plugins/
  phased-dev/
    .claude-plugin/plugin.json           ← 플러그인 매니페스트
    skills/phased-dev/
      SKILL.md
      README.md
      scripts/run_phases.py
    agents/
      phased-clarify.md
      phased-context.md
      phased-plan.md
      phased-generate.md
      phased-evaluate.md
README.md                                ← 이 파일
```

## 이름 변경 (배포 전 권장)

기본값:
- marketplace name: `phased-dev-tools`
- plugin name: `phased-dev`
- owner.name: `Your Team`

사내 컨벤션에 맞게:
- `.claude-plugin/marketplace.json`의 `name`, `owner.name` 갱신
- `plugins/phased-dev/.claude-plugin/plugin.json`의 `author.name` 갱신
- 변경 후엔 팀원 설치 명령도 따라 바뀝니다 (`/plugin install <plugin>@<marketplace>`).

## 새 버전 배포

1. 코드/SKILL/agent 변경
2. `plugins/phased-dev/.claude-plugin/plugin.json`의 `version` 올리기 (예: `1.0.1`)
3. commit & push
4. 팀원: 자동 업데이트(토큰 설정 시) 또는
   ```
   /plugin marketplace update phased-dev-tools
   /plugin install --force phased-dev@phased-dev-tools
   ```

## 참고 문서

- Claude Code Plugins: https://code.claude.com/docs/en/plugins.md
- Plugin Reference: https://code.claude.com/docs/en/plugins-reference.md
- Plugin Marketplaces: https://code.claude.com/docs/en/plugin-marketplaces.md
