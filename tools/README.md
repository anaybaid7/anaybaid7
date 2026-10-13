# How this profile works

Everything you read on the profile comes from `content.yaml`. The scripts in
here turn it into images and write the root `README.md`.

| File | Job |
|---|---|
| `content.yaml` | All the words, numbers, links and colors |
| `tools/build.py` | Draws every card in 4 versions (desktop/phone, dark/light) |
| `tools/live.py` | Pulls recent repos and contributions from the GitHub API for the "Lately" panel |
| `tools/readme.py` | Writes `README.md` with `<picture>` tags that pick the right version |
| `.github/workflows/build.yml` | Runs all three on every edit and every 6 hours, then commits |

## Changing something

1. Edit `content.yaml` (the pencil icon on github.com works fine)
2. Commit
3. The Action rebuilds and commits the new images within about a minute

Wrap text in `**double stars**` to make it bold and bright. Colors are
`red`, `amber`, `teal`, `sky`, `pink`. `jobs_shown` and `projects_shown`
control how many sit above the collapsed "Earlier roles" and "More projects".

## Running it locally

```bash
pip install -r requirements.txt
make
```

Set `GITHUB_TOKEN` to refresh the live panel locally too, otherwise it reuses
`data/live.json`.
