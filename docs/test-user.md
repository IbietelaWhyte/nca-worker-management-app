### To Create a Test User

```sh
curl -X POST "${SUPABASE_URL}/auth/v1/token?grant_type=password" \
  -H "apikey: ${SUPABASE_ANON_KEY}" \
  -H "Content-Type: application/json" \
  -d "{\"email\": \"${TEST_USER_EMAIL}\", \"password\": \"${TEST_USER_PASSWORD}\"}"
```