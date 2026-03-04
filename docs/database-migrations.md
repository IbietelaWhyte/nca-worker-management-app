# Database Migrations

## Commands

```sh
# Creating a new migration
supabase migration new $MIGRATION_NAME

# Apply a migration to local instance
supabase migration up

# To push a migration
supabase db push

# If a database migratino fails
supabase migration repair --status reverted $MIGRATION_ID

# To reset and reapply migrations and populate with seed data
supabase db reset

```

## Documentation 
https://supabase.com/docs/guides/deployment/database-migrations
