# v1.3.1 update-loading repair

- Full backend suite: **86 tests passed**.
- Full frontend suite: **93 tests passed**.
- New regressions prove the HTML and complete relative JavaScript graph use `/static/v1.3.1/`, every required module resolves, static/auth/HTML responses prevent cache reuse, and health/OpenAPI report the current version.
- Compatibility tests reproduce old permissions and missing Overview/Used registry entries, then verify visible recovery instead of silent page hiding, the fresh reload URL, authorized navigation, and authentication/error handling.
- Independent repair review found no important or security issue.
- All v1.3 ledger, category, history, theme, and workspace behavior remains present. No new database migration is introduced by this repair.

See `UPDATE-v1.3.1.md` for installation and the fresh browser URL. Visual browser verification remains unavailable; the module graph, DOM/HTTP workflows, and contrast checks are covered by automated checks.
