# Feature Requests

Det här dokumentet används för att spåra feature requests när vi jobbar i brancher.

## Mall

- **ID:** FR-YYYYMMDD-XX
- **Titel:**
- **Beskrivning:**
- **Acceptanskriterier:**
- **Påverkar:** (vy/template/model/test)
- **Branch:**
- **Status:** (requested | in-progress | done | shipped)

---

## FR-20251224-01 – Git remote + push senare
- **Beskrivning:** Lägg till remote (GitHub/GitLab) och pusha till `main` vid senare tillfälle.
- **Acceptanskriterier:**
  - Remote tillagd.
  - `main` pushad.
- **Påverkar:** docs
- **Branch:** feature/fr-20251224-01-git-remote-todo
- **Status:** requested

---

## FR-20251224-02 – Stage-branch + CI-gate (unit + E2E)
- **Beskrivning:** Inför en `stage`-branch som alla feature-brancher mergas till först. Merge/PR mot `stage` ska trigga full unit + E2E (Playwright) och endast tillåtas om allt är grönt.
- **Acceptanskriterier:**
  - GitHub Actions-workflow körs på PR mot `stage` och på push till `stage`.
  - Workflow kör `./scripts/test_all.sh` (unit + E2E).
  - Branch protection på `stage` kräver workflow-status innan merge.
- **Påverkar:** CI, git-workflow
- **Branch:** feature/fr-20251224-02-stage-ci-gate
- **Status:** in-progress
