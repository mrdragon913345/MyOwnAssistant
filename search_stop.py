import os
for root, dirs, files in os.walk('bot'):
    for file in files:
        if file.endswith('.py'):
            try:
                for i, line in enumerate(open(os.path.join(root, file), encoding='utf-8')):
                    if 'stop_current' in line:
                        print(f"{root}/{file}:{i+1}: {line.strip()}")
            except:
                pass
