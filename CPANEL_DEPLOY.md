# cPanel Deployment Runbook

This project is a Django application prepared for the Pars Web Server cPanel Python application feature. Keep the current Liara site available until the new copy passes the checks below.

## Readiness items to resolve

- The project pins Django 4.2.20. Django 4.2 security support ended on April 7, 2026. Upgrade to a supported release, preferably Django 5.2 LTS, and check every pinned Django add-on before public launch.
- Django's system check reports that django-ckeditor bundles CKEditor 4.22.1, which is unsupported and has unfixed security issues. Move to a supported editor or licensed CKEditor 4 LTS before exposing the admin editor publicly.
- A previously committed email app password was removed from the current settings file. Rotate that credential because older Git history may still contain it.
- The existing database archive was created on September 22, 2026. It is a staging snapshot only. Take a fresh database and media backup during the final cutover.
- The SQL archive was produced by MySQL 9.0.1. Confirm the cPanel MySQL server version accepts its `utf8mb4_0900_ai_ci` collation and MySQL 9 dump syntax before importing it.
- `requirements.txt` includes `mysqlclient` and WeasyPrint. Ask the host whether the Python application environment has the MySQL build libraries and the Cairo, Pango, and GDK libraries listed in `apt-packages.txt`.
- Confirm the hosting plan has enough disk space for the virtual environment, source assets, collected static files, and uploaded media.

## Create the cPanel application

1. In cPanel, open Software, then Setup Python App, and create an application for `keshtazar.ir`.
2. Use Python 3.12 if it is available. Set an application root such as `keshtazar_app` outside the domain document root.
3. Upload the project files into the application root. Do not upload `.git/`, `.idea/`, `.env`, `.venv/`, `media/`, or `staticfiles/`. Media files are copied to `PUBLIC_ROOT/media` in a later step.
4. Keep the supplied `passenger_wsgi.py` in the application root. Pars Web Server documents that the startup file and entry point are created by Setup Python App and that the application must be restarted after changes.
5. Copy the virtual environment activation command shown in the Setup Python App page. Use that exact command in Terminal before installing packages.

All commands and messages in this runbook use ASCII text for terminals that cannot display Persian characters.

## Install Python packages

From the application root, activate the cPanel virtual environment and run:

```sh
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If `mysqlclient` fails to build, ask the host to provide its MySQL development headers for the selected Python version. If WeasyPrint fails to import, ask the host to provide the native libraries listed in `apt-packages.txt`. That file was used by the Liara container and is not an install script for shared cPanel hosting.

## Set application variables

Use the environment variable section in Setup Python App. Do not upload the local `.env` file. Use `.env.example` as the list of variable names and configure these values in cPanel:

- `DJANGO_SECRET_KEY`: generate a new production key with `python -c "import secrets; print(secrets.token_urlsafe(64))"`.
- `DJANGO_DEBUG`: `False`.
- `DJANGO_ALLOWED_HOSTS`: `keshtazar.ir,www.keshtazar.ir`.
- `CSRF_TRUSTED_ORIGINS`: `https://keshtazar.ir,https://www.keshtazar.ir,https://sep.shaparak.ir`. Add a preview origin here if testing on a separate hostname.
- `SECURE_SSL_REDIRECT`: `True` after the domain has a working SSL certificate.
- `PUBLIC_ROOT`: the absolute Document Root shown in cPanel for `keshtazar.ir`, commonly `/home/CPANEL_USER/public_html`. Replace `CPANEL_USER` with the actual cPanel account name. Collected static files go to `PUBLIC_ROOT/static`; uploads go to `PUBLIC_ROOT/media`.
- `MYSQL_DATABASE`, `MYSQL_USER`, and `MYSQL_PASSWORD`: use the exact cPanel database and user names, including the cPanel account prefix.
- `MYSQL_HOST` and `MYSQL_PORT`: use the values supplied by the host. The default host is `localhost` and the default port is `3306`.
- `API_KAVENEGAR`, `SEP_TERMINAL`, and `SEP_PASSWORD`: use the live production credentials.
- `ZARINPAL_MERCHANT_ID` and `ZARINPAL_SANDBOX_MERCHANT_ID`: set the values required by the configured payment flow.
- `STATIC_ROOT`: optional override. By default collected files go to `PUBLIC_ROOT/static`.
- `MEDIA_ROOT`: optional override. By default uploads go to `PUBLIC_ROOT/media`.

If Setup Python App has no environment variable controls, create a new server-side `.env` in the application root with these values. Keep the application root outside the domain document root and restrict the file to the cPanel account user.

Enable the SSL certificate before setting `SECURE_SSL_REDIRECT=True`. Confirm that HTTP requests reach Django with the correct HTTPS scheme to avoid redirect loops.

## Create and restore the MySQL database

1. In cPanel, create a MySQL database and database user. Grant the user all privileges on that database.
2. Run `mysql --version` and confirm the server version with the host. The current archive is a MySQL 9.0.1 dump and uses `utf8mb4_0900_ai_ci`.
3. For a staging restore, upload the archive through File Manager and give it an ASCII name such as `database.tar.gz`. Extract it in the application root:

```sh
tar -xzf database.tar.gz
```

4. The archive contains `goofy_pike.sql`. Prepare an import file that preserves the dump collation but removes the Liara database name:

```sh
python scripts/prepare_mysql_dump.py goofy_pike.sql cpanel_database.sql
```

5. Import the prepared file into the cPanel database. Replace the example names with the values shown in cPanel:

```sh
mysql -u CPANEL_PREFIX_USER -p CPANEL_PREFIX_DATABASE < cpanel_database.sql
```

The preparation script creates a new output file and never edits the source dump. It removes only the `CREATE DATABASE` and `USE` statements so MySQL imports into the database selected in the command.

If the destination server is older than the dump format or rejects the collation, stop and ask the host for a compatible MySQL export/import path. Do not change the collation or charset without testing a restored copy first.

## Prepare static files and media

Run these commands after the application variables and database are set:

```sh
python manage.py check
python manage.py migrate --plan
python manage.py migrate --noinput
python manage.py collectstatic --noinput
```

WhiteNoise serves collected files under `/static/`; `collectstatic` writes them into `PUBLIC_ROOT/static`. Uploaded files are stored in `PUBLIC_ROOT/media`. Keep the media directory writable by the application user. A domain attached to Setup Python App may proxy requests to the Python app instead of serving files from its document root. Test `/media/` through the temporary hostname before cutover; if the app proxy intercepts it, ask the host for its supported way to serve that path. Do not expose the application root or virtual environment under `public_html`.

Copy the complete current Liara media directory, including CKEditor uploads, into the target `MEDIA_ROOT`. The local `media/` folder is not proof that it contains the latest production uploads.

## Verify before DNS cutover

- Test the site using a temporary hostname or provider preview URL.
- Check the home page, product pages, account login and OTP flow, admin login, image and CKEditor uploads, static CSS and JavaScript, sitemap, and checkout callback.
- Confirm live SMS, payment token, payment verification, and outbound HTTPS requests work from the cPanel server.
- Confirm logs contain ASCII output and no OTP, payment token, API key, or customer payment payload.
- Take a fresh database and media backup, freeze writes on Liara, restore the final snapshot, and repeat migrations and static collection.
- Change DNS only after the target site passes. Keep Liara and its data available for rollback until orders and payments are verified on the new host.
- Restart the Python application from Setup Python App after each deployment or environment change.

## Rollback

Keep the old Liara application running during the migration window. If the new site fails, point DNS back to Liara and restore writes there. Do not delete the old database or media until the new host has been verified.
