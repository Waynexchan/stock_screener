# Project Logic

## GitHub Safety

Never commit private workflow data or credentials.

Keep these files and folders local only:

- Raw jobs and applied-job history
- Tracker files and tracker backups
- Generated output, data, cache, and logs
- CVs, cover letters, PDFs, and Word documents
- API exports such as `jobs/api_jobs.csv`
- Credential files and token files
- `.env` and any `*.env` file
- Runtime stock screener reports and universe caches

Commit only:

- Source code
- Documentation
- `README.md`
- `requirements.txt`
- Safe fake examples under `examples/`

Private local files should be removed from Git tracking with `git rm --cached`, not deleted from disk.
