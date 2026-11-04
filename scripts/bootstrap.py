"""Create local secrets without putting their values in command output."""
from pathlib import Path
import base64
import os
import secrets

root = Path(__file__).resolve().parents[1]
destination = root / '.env'
if destination.exists():
    print('Existing .env preserved.')
else:
    owner_password = secrets.token_urlsafe(30)
    app_password = secrets.token_urlsafe(30)
    values = (root / '.env.example').read_text()
    values = values.replace('postgresql://tampak_app:CHANGE_ME', f'postgresql://tampak_app:{app_password}')
    values = values.replace('postgresql://tampak_owner:CHANGE_ME', f'postgresql://tampak_owner:{owner_password}')
    values = values.replace('TAMPAK_DB_PASSWORD=CHANGE_ME', f'TAMPAK_DB_PASSWORD={owner_password}')
    values = values.replace('TAMPAK_APP_DB_PASSWORD=CHANGE_ME', f'TAMPAK_APP_DB_PASSWORD={app_password}')
    values = values.replace('TAMPAK_MASTER_KEY=GENERATE_WITH_BOOTSTRAP', 'TAMPAK_MASTER_KEY=' + base64.urlsafe_b64encode(os.urandom(32)).decode())
    values = values.replace('TAMPAK_ADMIN_PASSWORD=GENERATE_WITH_BOOTSTRAP', 'TAMPAK_ADMIN_PASSWORD=' + secrets.token_urlsafe(24))
    values = values.replace('TAMPAK_LOCAL_UID=1000', f'TAMPAK_LOCAL_UID={os.getuid()}')
    values = values.replace('TAMPAK_LOCAL_GID=1000', f'TAMPAK_LOCAL_GID={os.getgid()}')
    destination.write_text(values)
    destination.chmod(0o600)
    print('Created private .env with database credentials, encryption key and admin password.')
(root / 'runtime').mkdir(exist_ok=True)

