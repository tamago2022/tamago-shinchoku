import subprocess

r = subprocess.run(['git', 'ls-remote', 'https://github.com/tamago2022/tamago-shinchoku.git', 'gh-pages'],
                    capture_output=True, text=True, timeout=30)
print(r.stdout)
print(r.stderr[:500])
