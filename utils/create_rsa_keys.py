import os
import subprocess
from Crypto.PublicKey import RSA

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "oj.settings")
import django
django.setup()
from django.conf import settings

private_key_path = os.path.join(settings.DATA_DIR, "config", "private_key.pem")
public_key_path = os.path.join(settings.DATA_DIR, "config", "public_key.pem")

os.makedirs(os.path.dirname(private_key_path), exist_ok=True)
os.makedirs(os.path.dirname(public_key_path), exist_ok=True)

key = RSA.generate(2048)

with open(private_key_path, 'wb') as f:
    f.write(key.export_key('PEM'))

public_key = key.publickey()
with open(public_key_path, 'wb') as f:
    f.write(public_key.export_key('PEM'))

os.chmod(private_key_path, 0o644)
os.chmod(public_key_path, 0o644)

if os.path.isfile(private_key_path) and os.path.isfile(public_key_path):
    print(f"Keys have been successfully generated.\nPrivate Key: {private_key_path}\nPublic Key: {public_key_path}")
else:
    print("Error in generating keys.")
    exit(1)

