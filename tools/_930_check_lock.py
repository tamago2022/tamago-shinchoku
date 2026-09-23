import subprocess, os, time

p = '/Users/mac/Desktop/tamago-shinchoku/status/.machine_status_push.lock'
if os.path.exists(p):
    with open(p) as f:
        pid = f.read().strip()
    print('lock pid', pid, 'age', time.time() - os.path.getmtime(p))
    r = subprocess.run(['ps', '-p', pid, '-o', 'pid,etime,command'], capture_output=True, text=True)
    print(r.stdout)
else:
    print('no lock')
