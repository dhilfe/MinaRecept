# Branching & release-flöde (main = prod)

## Princip
- **`main`** = produktion / release-klar kod
- **`stage`** = integration (allt ska passera här först)

## Flöde
1. Skapa feature-branch från `stage`:
   - `git checkout stage && git pull`
   - `git checkout -b feature/<namn>`
2. Öppna PR: **feature → stage**
   - CI måste vara grön
3. När du vill släppa:
   - Öppna PR: **stage → main**
   - Kör en snabb smoke-test
   - Merge
4. (Rekommenderat) Tagga release:
   - `git tag v1.0.0 && git push origin v1.0.0`

## Branch protection (rekommenderat)
### `stage`
- Require pull request before merging
- Require status checks to pass: **`CI / test`**
- Require branches to be up to date before merging
- (Valfritt) Block direct pushes

### `main`
- Require pull request before merging
- Require status checks to pass: **`CI / test`**
- Require branches to be up to date before merging
- Include administrators
- (Rekommenderat) Tillåt bara merge via PR från `stage`


