# SANITIZE: before you push

Your prompts never live in the repo: `von-shadow` writes to `~/.local/share/von-shadow/`
(or `VON_SHADOW_HOME`). The eval scripts ship synthetic cases only.

## Never commit

- Anything from `~/.local/share/von-shadow/` (queue, predictions, labels contain prompt text)
- Real agent results or transcripts used for private evals
- Real emails, paths, client names, secrets

## 30-second check

```bash
git status
grep -rInE '(@[a-z0-9.-]+\.[a-z]{2,}|/Users/[a-z]+/|sk-[A-Za-z0-9]{8}|AKIA[0-9A-Z]{16})' \
  --exclude-dir=.git --exclude-dir=.venv . || echo "clean"
```
