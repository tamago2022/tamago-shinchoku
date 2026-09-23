import subprocess

r = subprocess.run(['ps', '-p', '19363', '-o', 'pid,etime,command'], capture_output=True, text=True)
print(r.stdout)
print(r.stderr)
