# Private-inclusive profile statistics

This repository generates **two SVGs** without publishing repository names, paths, source code, or API tokens.

- `activity.svg`: GitHub's contribution calendar total, including anonymized private activity if enabled in GitHub profile settings; plus the restricted/private count.
- `languages.svg`: Aggregate language-byte counts across eligible public repositories owned by JenniferUgo and private JunnDigital repositories visible to a restricted token. This **is not a measure of code personally authored**.
- A numeric Grade C / A grade is deliberately not reproduced; third-party ranks are subjective and misleading.

## One-time activation (account owner only)

1. At GitHub **Settings → Developer settings → Personal access tokens → Fine-grained tokens**, create an expiring **fine-grained** token.
2. Set **Resource owner: JunnDigital**. Choose **only the private JunnDigital repositories** that you authorize for language aggregation, e.g. your actively maintained products. For repository permissions use **Contents: Read-only** and leave everything else at minimum defaults. The token may require JunnDigital organization approval.
3. On the **JenniferUgo/JenniferUgo** profile repository, navigate to **Settings → Secrets and variables → Actions → New repository secret**. Name it `STATS_PRIVATE_READ_TOKEN` and paste the token **there, never in your README, a chat, or a commit**.
4. Under **Actions → Refresh profile statistics → Run workflow**, start the first run manually. The job only publishes statistics after the private token can list at least one authorized private JunnDigital repository and read its language breakdown.
5. Inspect the public profile and the chart percentages. Weekly refreshes are scheduled for Monday 06:23 UTC. Renew the token before it expires.

## Access boundaries

The fine-grained token can **read** selected JunnDigital private repositories. It cannot write to them. The built-in GitHub Actions `GITHUB_TOKEN` writes only generated SVGs and an image block to this public **profile** repository.

The action runs only from the protected/default-branch code via schedule/manual dispatch. There is no pull-request trigger and no third-party statistics service. Review changes to the workflow and generator before merging them. Anyone who can edit the workflow on the default branch could potentially misuse a stored token, so protect access to this repository.

**Privacy:** Generated graphics reveal aggregate language composition, repository count and contribution totals. They deliberately never show private repository titles or code. GitHub's underlying contribution calendar may count events differently from commit-only badges. Development on a nondefault branch might not yet qualify as a commit contribution.

If the token cannot access the chosen repositories, the script stops and does not publish an incomplete chart. Check the selected repository scope and organization approval instead of granting broader access.
