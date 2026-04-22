from django.db import migrations


class Migration(migrations.Migration):
    """
    Renames the DB column from client_statistic to client_status using raw SQL,
    bypassing Django's state machinery entirely (the state is already correct
    because migration 0004 was edited after it was applied).
    """

    dependencies = [
        ('clients', '0004_client_sector_statistic'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                DO $$
                BEGIN
                    IF EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'clients_client'
                          AND column_name = 'client_statistic'
                    ) THEN
                        ALTER TABLE clients_client RENAME COLUMN client_statistic TO client_status;
                    END IF;
                END $$;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
