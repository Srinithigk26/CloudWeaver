# CloudWeaver authentication testing

Use the credentials in `/app/memory/test_credentials.md`. Verify register, login, `/api/auth/me`, logout, guarded `/api/cost/analyze`, and invalid credentials. Cookies should be httpOnly and the response must not expose `password_hash`.