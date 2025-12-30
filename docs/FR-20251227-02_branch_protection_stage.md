# FR-20251227-02: Branch protection för `stage`

## Bakgrund

För att minska risken att trasig kod hamnar på `stage` ska vi slå på branch protection och kräva CI innan merge.

## Mål

- Blockera direkt-push till `stage` (via regler, PR-flöde)
- Kräv att GitHub Actions CI är grön innan merge

## Scope

Gäller endast repo-inställningar på GitHub (ingen kod ändras här).

## Förslag: Inställningar i GitHub UI

1) Gå till: **Settings → Branches → Branch protection rules**

2) Klicka **Add rule**

3) Branch name pattern: `stage`

4) Rekommenderade kryssrutor

- Require a pull request before merging
  - (Valfritt) Require approvals: 1
- Require status checks to pass before merging
  - Sök upp och välj status check: `CI / test` (kommer från workflow [ci.yml](.github/workflows/ci.yml))
- (Valfritt men rekommenderat) Require branches to be up to date before merging
- (Valfritt) Restrict who can push to matching branches

5) Spara

## Acceptanskriterier

- Det går inte att pusha direkt till `stage` (utan PR)
- PR till `stage` kan inte mergas om `CI / test` är röd