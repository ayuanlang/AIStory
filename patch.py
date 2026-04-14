def read_lines():
    with open('backend/app/api/endpoints.py', 'r', encoding='utf-8') as f:
        lines = f.readlines()
        print(''.join(lines[4770:5250]))

read_lines()
