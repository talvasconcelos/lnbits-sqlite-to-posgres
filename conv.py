## Python script to migrate an LNbits SQLite DB to Postgres
## All credits to @Fritz446 for the awesome work 

## pip install psycopg2 OR psycopg2-binary

import os
import sqlite3

import psycopg2

# Change these values as needed

sqfolder = "data/"
pgdb = "fast"
pguser = "postgres"
pgpswd = "postgres"
pghost = "localhost"
pgport = "5432"
pgschema = ""


def get_sqlite_cursor(sqdb) -> sqlite3:
    consq = sqlite3.connect(sqdb)
    return consq.cursor()


def get_postgres_cursor():
    conpg = psycopg2.connect(
        database=pgdb, user=pguser, password=pgpswd, host=pghost, port=pgport
    )
    return conpg.cursor()


def check_db_versions(sqdb):
    sqlite = get_sqlite_cursor(sqdb)
    dblite = dict(sqlite.execute("SELECT * FROM dbversions;").fetchall())
    del dblite["lnurlpos"]  # wrongly added?
    sqlite.close()

    postgres = get_postgres_cursor()
    postgres.execute("SELECT * FROM public.dbversions;")
    dbpost = dict(postgres.fetchall())

    for key in dblite.keys():
        if dblite[key] != dbpost[key]:
            raise Exception(
                f"sqlite database version ({dblite[key]}) of {key} doesn't match postgres database version {dbpost[key]}"
            )

    connection = postgres.connection
    postgres.close()
    connection.close()

    print("Database versions OK, converting")


def insert_to_pg(query, data):
    if len(data) == 0:
        return

    cursor = get_postgres_cursor()
    connection = cursor.connection

    for d in data:
        cursor.execute(query, d)
    connection.commit()

    cursor.close()
    connection.close()


def migrate_core(sqlite_db_file):
    sq = get_sqlite_cursor(sqlite_db_file)

    # ACCOUNTS
    res = sq.execute("SELECT * FROM accounts;")
    q = f"INSERT INTO public.accounts (id, email, pass) VALUES (%s, %s, %s);"
    insert_to_pg(q, res.fetchall())

    # WALLETS
    res = sq.execute("SELECT * FROM wallets;")
    q = f'INSERT INTO public.wallets (id, name, "user", adminkey, inkey) VALUES (%s, %s, %s, %s, %s);'
    insert_to_pg(q, res.fetchall())

    # API PAYMENTS
    res = sq.execute("SELECT * FROM apipayments;")
    q = f"""
        INSERT INTO public.apipayments(
        checking_id, amount, fee, wallet, pending, memo, "time", hash, preimage, bolt11, extra, webhook, webhook_status)
        VALUES (%s, %s, %s, %s, %s::boolean, %s, to_timestamp(%s), %s, %s, %s, %s, %s, %s);
    """
    insert_to_pg(q, res.fetchall())

    # BALANCE CHECK
    res = sq.execute("SELECT * FROM balance_check;")
    q = f"INSERT INTO public.balance_check(wallet, service, url) VALUES (%s, %s, %s);"
    insert_to_pg(q, res.fetchall())

    # BALANCE NOTIFY
    res = sq.execute("SELECT * FROM balance_notify;")
    q = f"INSERT INTO public.balance_notify(wallet, url) VALUES (%s, %s);"
    insert_to_pg(q, res.fetchall())

    # EXTENSIONS
    res = sq.execute("SELECT * FROM extensions;")
    q = f'INSERT INTO public.extensions("user", extension, active) VALUES (%s, %s, %s::boolean);'
    insert_to_pg(q, res.fetchall())

    print("Migrated: core")


def migrate_ext(sqlite_db_file, schema):
    sq = get_sqlite_cursor(sqlite_db_file)

    if schema == "bleskomat":
        # BLESKOMAT LNURLS
        res = sq.execute("SELECT * FROM bleskomat_lnurls;")
        q = f"""
            INSERT INTO bleskomat.bleskomat_lnurls(
            id, bleskomat, wallet, hash, tag, params, api_key_id, initial_uses, remaining_uses, created_time, updated_time)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
        """
        insert_to_pg(q, res.fetchall())

        # BLESKOMATS
        res = sq.execute("SELECT * FROM bleskomats;")
        q = f"""
            INSERT INTO bleskomat.bleskomats(
            id, wallet, api_key_id, api_key_secret, api_key_encoding, name, fiat_currency, exchange_rate_provider, fee)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
        """
        insert_to_pg(q, res.fetchall())
    elif schema == "captcha":
        # CAPTCHA
        res = sq.execute("SELECT * FROM captchas;")
        q = """
            INSERT INTO captcha.captchas(
            id, wallet, url, memo, description, amount, "time", remembers, extras)
            VALUES (%s, %s, %s, %s, %s, %s, to_timestamp(%s), %s, %s);
        """
        insert_to_pg(q, res.fetchall())
    elif schema == "withdraw":
        # WITHDRAW LINK
        res = sq.execute("SELECT * FROM withdraw_link;")
        q = """
            INSERT INTO withdraw.withdraw_link (
                id,
                wallet,
                title,
                min_withdrawable,
                max_withdrawable,
                uses,
                wait_time,
                is_unique,
                unique_hash,
                k1,
                open_time,
                used,
                usescsv
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
        """
        insert_to_pg(q, res.fetchall())
        # WITHDRAW HASH CHECK
        res = sq.execute("SELECT * FROM hash_check;")
        q = """
            INSERT INTO withdraw.hash_check (id, lnurl_id)
            VALUES (%s, %s);
        """
        insert_to_pg(q, res.fetchall())
    elif schema == "watchonly":
        # WALLETS
        res = sq.execute("SELECT * FROM wallets;")
        q = """
            INSERT INTO watchonly.wallets (
                id,
                "user",
                masterpub,
                title,
                address_no,
                balance
            )
            VALUES (%s, %s, %s, %s, %s, %s);
        """
        insert_to_pg(q, res.fetchall())
        # ADDRESSES
        res = sq.execute("SELECT * FROM addresses;")
        q = """
            INSERT INTO watchonly.addresses (id, address, wallet, amount)
            VALUES (%s, %s, %s, %s);
        """
        insert_to_pg(q, res.fetchall())
        # MEMPOOL
        res = sq.execute("SELECT * FROM mempool;")
        q = """
            INSERT INTO watchonly.mempool ("user", endpoint)
            VALUES (%s, %s);
        """
        insert_to_pg(q, res.fetchall())
    elif schema == "usermanager":
        # USERS
        res = sq.execute("SELECT * FROM users;")
        q = """
            INSERT INTO usermanager.users (id, name, admin, email, password)
            VALUES (%s, %s, %s, %s, %s);
        """
        insert_to_pg(q, res.fetchall())
        # WALLETS
        res = sq.execute("SELECT * FROM wallets;")
        q = """
            INSERT INTO usermanager.wallets (id, admin, name, "user", adminkey, inkey)
            VALUES (%s, %s, %s, %s, %s, %s);
        """
        insert_to_pg(q, res.fetchall())
    elif schema == "tpos":
        # TPOSS
        res = sq.execute("SELECT * FROM tposs;")
        q = """
            INSERT INTO tpos.tposs (id, wallet, name, currency)
            VALUES (%s, %s, %s, %s);
        """
        insert_to_pg(q, res.fetchall())
    elif schema == "tipjar":
        # TIPJARS
        res = sq.execute("SELECT * FROM TipJars;")
        q = """
            INSERT INTO tipjar.TipJars (id, name, wallet, onchain, webhook)
            VALUES (%s, %s, %s, %s, %s);
        """
        insert_to_pg(q, res.fetchall())
        # TIPS
        res = sq.execute("SELECT * FROM Tips;")
        q = """
            INSERT INTO tipjar.Tips (id, wallet, name, message, sats, tipjar)
            VALUES (%s, %s, %s, %s, %s, %s);
        """
        insert_to_pg(q, res.fetchall())
    elif schema == "subdomains":
        # DOMAIN
        res = sq.execute("SELECT * FROM domain;")
        q = """
            INSERT INTO subdomains.domain (
                id,
                wallet,
                domain,
                webhook,
                cf_token,
                cf_zone_id,
                description,
                cost,
                amountmade,
                allowed_record_types,
                time
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, to_timestamp(%s));
        """
        insert_to_pg(q, res.fetchall())
        # SUBDOMAIN
        res = sq.execute("SELECT * FROM subdomain;")
        q = """
            INSERT INTO subdomains.subdomain (
                id,
                domain,
                email,
                subdomain,
                ip,
                wallet,
                sats,
                duration,
                paid,
                record_type,
                time
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::boolen, %s, to_timestamp(%s));
        """
        insert_to_pg(q, res.fetchall())
    elif schema == "streamalerts":
        # SERVICES
        res = sq.execute("SELECT * FROM Services;")
        q = """
            INSERT INTO streamalerts.Services (
                id,
                state,
                twitchuser,
                client_id,
                client_secret,
                wallet,
                onchain,
                servicename,
                authenticated,
                token
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::boolean, %s);
        """
        insert_to_pg(q, res.fetchall())
        # DONATIONS
        res = sq.execute("SELECT * FROM Donations;")
        q = """
            INSERT INTO streamalerts.Donations (
                id,
                wallet,
                name,
                message,
                cur_code,
                sats,
                amount,
                service,
                posted,
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::boolean);
        """
        insert_to_pg(q, res.fetchall())
    else:
        print(f"Not implemented: {schema}")
        sq.close()
        return

    print(f"Migrated: {schema}")
    sq.close()


check_db_versions("data/database.sqlite3")
migrate_core("data/database.sqlite3")

files = os.listdir(sqfolder)
for file in files:
    path = f"data/{file}"
    if file.startswith("ext_"):
        schema = file.replace("ext_", "").split(".")[0]
        migrate_ext(path, schema)

