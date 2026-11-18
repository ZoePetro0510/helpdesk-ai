"""Integration tests use their own database (helpdesk_test), never the demo data.

This runs before any test module imports the app, so the app's engine is created with the test URL.
"""

import os

if os.getenv("RUN_INTEGRATION"):
    from sqlalchemy import create_engine, text

    main_url = os.environ["DATABASE_URL"]
    test_url = main_url.rsplit("/", 1)[0] + "/helpdesk_test"
    os.environ["DATABASE_URL"] = test_url

    admin = create_engine(main_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        if not conn.scalar(text("SELECT 1 FROM pg_database WHERE datname = 'helpdesk_test'")):
            conn.execute(text("CREATE DATABASE helpdesk_test"))
    admin.dispose()
