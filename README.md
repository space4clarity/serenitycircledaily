# Serenity Circle Daily

An independent daily blog about addiction recovery and sobriety, compiled as
original commentary on two selected book passages per post.

Public site: https://space4clarity.github.io/serenitycircledaily/

## Daily workflow

1. Read the selected sources from the local Calibre library without modifying it.
2. Select two relevant, unused passages around a daily theme.
3. Use the signed-in Codex CLI to write 500–700 words of original reflection,
   a small optional invitation, and an open question.
4. Verify two short quotations against the source, reject duplicate quotes/topics,
   and obtain a separate AI review of grounding, originality, and safety.
5. Publish one post per America/Denver calendar day and update the archive, bookshelf,
   homepage, and RSS feed. Failed checks stop publication. AI checks are imperfect.

The first source comes from addiction-recovery literature; the second comes from
books about self-compassion, family patterns, or relationships. The library is
deliberately curated in `.automation/catalog.json`; unrelated Calibre books are
never automatically added. All authors and locators are attributed in each post.
Source metadata comes from the local editions and is not a claim of author endorsement.

The essays are reflections, not clinical advice, copied readings, or replacements
for the books. No ebooks, cover images, full source passages, or private Calibre
paths are uploaded to GitHub. Only original prose, bibliographic metadata, and
one verified 6–20-word quotation per source appear publicly.

## Local requirements

Python 3.11+, PyMuPDF, BeautifulSoup4, timezone data (`tzdata` on Windows), Node.js,
Git, and Codex CLI authenticated with the existing account. Generation uses that
account's allowance. No new paid API service is configured.

Set `.automation/private.json` locally (ignored by Git) to:

```json
{"calibre_library":"ABSOLUTE_PATH_TO_CALIBRE_LIBRARY"}
```

```powershell
python .automation/daily.py --index-library
python .automation/daily.py
python .automation/daily.py --check
python .automation/daily.py --publish
```

Cached ebook text and source/review logs stay in ignored `.automation/cache/` and
`.automation/runs/`. The public history contains only post data and short quotations.
The Codex generator runs with shell, apps, plugins, browser, and computer-use tools
disabled, in a read-only sandbox. The Python runner controls Git publication.

## Scheduling

```powershell
powershell -NoProfile -File .automation/install-schedule.ps1 -Time 08:47
```

The **Serenity Circle Daily** Windows task runs at 08:47 in the Windows system
timezone and at sign-in, under the current user's limited-privilege interactive
identity. The computer must be on and signed in. Missed runs start when available;
failures retry twice, 20 minutes apart. The schedule is separate from Daily Reading.
Expired account access or exhausted Codex usage requires restoring that access.

```powershell
Get-ScheduledTaskInfo -TaskName 'Serenity Circle Daily'
Disable-ScheduledTask -TaskName 'Serenity Circle Daily'
```

The runner pulls only when its checkout is clean and never force-pushes. A failed
push retries without generating a second post on the same day. Rendering failures
restore the previous pages and history. Keep unrelated site edits in another checkout.
