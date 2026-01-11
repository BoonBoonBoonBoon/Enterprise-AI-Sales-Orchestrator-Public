import os
from urllib.parse import urlparse
from dotenv import load_dotenv
import redis
import ssl as _ssl

load_dotenv()
url = os.environ.get('REDIS_URL')
print('redis-py version:', redis.__version__)
print('OpenSSL:', _ssl.OPENSSL_VERSION)
print('REDIS_URL:', url)

def try_connect(u, **kwargs):
    try:
        r = redis.from_url(u, decode_responses=True, **kwargs)
        return r.ping()
    except Exception as e:
        print('Connect failed:', type(e).__name__, e)
        return None

print('\nTrying from_url as-is...')
print('PING:', try_connect(url))

parsed = urlparse(url)
host = parsed.hostname
port = parsed.port
user = parsed.username
pwd = parsed.password

print('\nTrying explicit TLS...')
try:
    r = redis.Redis(host=host, port=port, username=user, password=pwd, ssl=True)
    print('PING (ssl=True):', r.ping())
except Exception as e:
    print('TLS explicit failed:', type(e).__name__, e)

print('\nTrying explicit non-TLS...')
try:
    r = redis.Redis(host=host, port=port, username=user, password=pwd, ssl=False)
    print('PING (ssl=False):', r.ping())
except Exception as e:
    print('Non-TLS explicit failed:', type(e).__name__, e)
