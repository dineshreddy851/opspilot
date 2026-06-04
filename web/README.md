# OpsPilot Web

This dependency-light TypeScript interface uses Cognito Hosted UI with
Authorization Code + PKCE. It calls only the authenticated OpsPilot API.

Terraform uploads `static/index.html`, `static/styles.css`, and `src/main.ts`
to the private website bucket. Terraform also generates `config.js` containing
public deployment values such as the API URL and Cognito app client ID.

For a local preview:

```bash
cd web
npm install
npm run build
python3 -m http.server 3000 --directory dist
```

The browser stores only the OAuth PKCE verifier, state, short-lived access
token, and expiry in `sessionStorage`. It never receives AWS credentials or
approval callback secrets.
