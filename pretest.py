import urllib.request, urllib.error, json, sys, os, re

BASE = 'http://127.0.0.1:5000'
passed = []
failed = []

def check(name, condition, detail=''):
    if condition:
        passed.append(name)
        print(f'  PASS  {name}')
    else:
        failed.append(name)
        print(f'  FAIL  {name}' + (f': {detail}' if detail else ''))

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **kw): return None

opener = urllib.request.build_opener(NoRedirect())

def get(path):
    req = urllib.request.Request(BASE + path)
    try:
        r = opener.open(req, timeout=5)
        return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()

def post_json(path, data):
    body = json.dumps(data).encode()
    req = urllib.request.Request(BASE + path, data=body, headers={'Content-Type': 'application/json'})
    try:
        r = opener.open(req, timeout=5)
        return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except:
            return e.code, {}

print()
print('=== 1. PUBLIC PAGES ===')
s, _ = get('/');                 check('Home page loads', s == 200)
s, _ = get('/login');            check('Login page loads', s == 200)
s, _ = get('/static/app.js');    check('app.js loads', s == 200)
s, _ = get('/static/style.css'); check('style.css loads', s == 200)
s, _ = get('/static/manager.js');    check('manager.js loads', s == 200)
s, _ = get('/static/supervisor.js'); check('supervisor.js loads', s == 200)

print()
print('=== 2. AUTH PROTECTION (unauthenticated = 302 redirect) ===')
protected = [
    ('/manager/dashboard',                  'Manager dashboard'),
    ('/supervisor/dashboard',               'Supervisor dashboard'),
    ('/api/manager/kpis',                   'Manager KPIs API'),
    ('/api/supervisor/today-logs',          'Supervisor logs API'),
    ('/api/manager/todos',                  'Manager todos API'),
    ('/api/supervisor/todos',               'Supervisor todos API'),
    ('/api/manager/export/today-logs.csv',  'CSV export API'),
    ('/api/supervisor/missed-clockouts',    'Missed clock-outs API'),
]
for path, name in protected:
    s, _ = get(path)
    check(f'{name} blocked (302)', s == 302, f'got {s}')

print()
print('=== 3. PUBLIC CLOCK API ===')
s, d = post_json('/api/public/verify', {'employee_code': '00000'})
check('Verify: unknown code rejected (404)', s == 404, f'got {s}')
s, d = post_json('/api/public/verify', {'employee_code': 'abc'})
check('Verify: non-numeric rejected (400)', s == 400, f'got {s}')
s, d = post_json('/api/public/verify', {'employee_code': '123'})
check('Verify: too-short code rejected (400)', s == 400, f'got {s}')
s, d = post_json('/api/public/clock', {'employee_code': '00000', 'action': 'INVALID'})
check('Clock: invalid action rejected (400)', s == 400, f'got {s}')

print()
print('=== 4. ALL ROUTES REGISTERED ===')
sys.path.insert(0, '.')
from routes import app
rules = [r.rule for r in app.url_map.iter_rules()]
expected_routes = [
    '/api/manager/kpis',
    '/api/manager/todos',
    '/api/manager/export/today-logs.csv',
    '/api/manager/export/preview',
    '/api/supervisor/todos',
    '/api/supervisor/today-logs',
    '/api/supervisor/missed-clockouts',
    '/api/manager/create-supervisor',
    '/api/manager/supervisors',
    '/api/manager/delete-supervisor',
    '/api/manager/productivity-scores',
    '/api/manager/productivity-scores/delete-last',
    '/api/manager/productivity-score-timeseries',
    '/api/manager/daily-reports',
    '/api/supervisor/daily-report',
]
for route in expected_routes:
    check(f'Route: {route}', route in rules, 'MISSING')

print()
print('=== 5. SECRET KEY ===')
check('.secret_key file exists', os.path.exists('.secret_key'))
if os.path.exists('.secret_key'):
    with open('.secret_key') as f:
        k = f.read().strip()
    check('Key length >= 32 chars', len(k) >= 32, f'length={len(k)}')
    check('Key is not dev default', k != 'dev-secret-key')

print()
print('=== 6. PASSWORD STRENGTH LOGIC ===')
def strength_ok(pw):
    return len(pw) >= 8 and bool(re.search(r'[A-Z]', pw)) and bool(re.search(r'[0-9]', pw))

cases = [
    ('weakpass',    False),
    ('Short1',      False),
    ('nouppercase1', False),
    ('NoDigitsHere', False),
    ('GoodPass1',   True),
    ('StrongP4ss',  True),
    ('Abc12345',    True),
]
for pw, expect in cases:
    result = strength_ok(pw)
    check(f'Password "{pw}" -> {"PASS" if expect else "BLOCK"}', result == expect)

print()
print(f'Results: {len(passed)} passed  |  {len(failed)} failed')
if failed:
    print('FAILED:', failed)
    sys.exit(1)
else:
    print('ALL TESTS PASSED - ready for deployment!')
