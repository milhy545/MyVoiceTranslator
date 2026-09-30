import re

with open("interview_shield/pipeline.py", "r") as f:
    content = f.read()

# Let's just fix the specific syntax errors manually
# 1. run_simulated_live try block indentation
lines = content.split('\n')
new_lines = []
in_sim_live_try = False
in_run_live_try = False
for i, line in enumerate(lines):
    if line.startswith('        self._executor = ThreadPoolExecutor(max_workers=1)'):
        if 'def run_live' in ''.join(lines[i-6:i]):
            in_run_live_try = True
        else:
            in_sim_live_try = True
            
        new_lines.append(line)
        new_lines.append('        try:')
        continue
        
    if line.startswith('        try:'):
        # Skip the original ones we injected incorrectly
        continue
        
    if in_sim_live_try and line.startswith('        finally:'):
        in_sim_live_try = False
        new_lines.append(line)
        continue
        
    if in_run_live_try and line.startswith('        finally:'):
        in_run_live_try = False
        new_lines.append(line)
        continue

    if in_sim_live_try or in_run_live_try:
        # indent by 4 spaces
        if line.strip():
            new_lines.append('    ' + line)
        else:
            new_lines.append(line)
    else:
        new_lines.append(line)

content = '\n'.join(new_lines)
with open("interview_shield/pipeline.py", "w") as f:
    f.write(content)
