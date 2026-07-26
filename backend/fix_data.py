"""Fix test data: better questions, experiments, start judge worker"""
import requests, subprocess, sys

BASE = 'http://localhost:8000/api/v1'

def api(method, path, token, data=None):
    h = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    if method == 'post':
        return requests.post(f'{BASE}{path}', headers=h, json=data)
    elif method == 'put':
        return requests.put(f'{BASE}{path}', headers=h, json=data)
    elif method == 'patch':
        return requests.patch(f'{BASE}{path}', headers=h, json=data)
    elif method == 'delete':
        return requests.delete(f'{BASE}{path}', headers=h)
    return requests.get(f'{BASE}{path}', headers=h)

# Login
r = requests.post(f'{BASE}/auth/login', json={'username':'teacher_wang','password':'Teach123!'})
t_tok = r.json()['access_token']
r = requests.post(f'{BASE}/auth/login', json={'username':'student_xiao','password':'Study123!'})
s_tok = r.json()['access_token']

# 1. Delete old assignment questions and recreate with full descriptions
print('Fixing assignment questions...')
assignments = api('get', '/assignments', t_tok).json()['items']
for a in assignments:
    qs = api('get', f'/assignments/{a["id"]}/questions', t_tok).json()['items']
    for q in qs:
        api('delete', f'/assignments/{a['id']}/questions/{q['id']}', t_tok)
    # Create proper questions
    api('post', f'/assignments/{a['id']}/questions', t_tok, {
        'title': '两数之和',
        'description': '## 题目要求\n\n编写函数 `add(a, b)`，接收两个整数参数，返回它们的和。\n\n### 输入\n- `a`: int, 第一个整数\n- `b`: int, 第二个整数\n\n### 输出\n- 返回 int，即 a + b 的结果\n\n### 示例\n```python\n>>> add(1, 2)\n3\n>>> add(-5, 3)\n-2\n>>> add(0, 0)\n0\n```\n\n### 提示\n直接使用 Python 的 `+` 运算符即可。',
        'function_name': 'add',
        'signature': 'def add(a, b):',
        'starter_code': 'def add(a, b):\n    # 在这里编写代码\n    pass',
        'hidden_tests': 'def test_basic():\n    assert add(1, 2) == 3\n    assert add(-5, 3) == -2\n    assert add(0, 0) == 0\n\ndef test_large():\n    assert add(1000, 2000) == 3000\n    assert add(-100, 100) == 0',
    })
    api('post', f'/assignments/{a['id']}/questions', t_tok, {
        'title': '列表最大值',
        'description': '## 题目要求\n\n编写函数 `max_of_list(nums)`，接收一个非空整数列表，返回其中的最大值。\n\n### 输入\n- `nums`: list[int], 一个非空的整数列表\n\n### 输出\n- 返回 int，列表中的最大元素\n\n### 示例\n```python\n>>> max_of_list([1, 5, 3, 9, 2])\n9\n>>> max_of_list([-1, -5, -3])\n-1\n>>> max_of_list([42])\n42\n```\n\n### 提示\n可以使用 Python 内置函数 `max()`，也可以自己写循环遍历列表。',
        'function_name': 'max_of_list',
        'signature': 'def max_of_list(nums):',
        'starter_code': 'def max_of_list(nums):\n    # 在这里编写代码\n    pass',
        'hidden_tests': 'def test_basic():\n    assert max_of_list([1, 5, 3, 9, 2]) == 9\n    assert max_of_list([-1, -5, -3]) == -1\n    assert max_of_list([42]) == 42\n\ndef test_duplicates():\n    assert max_of_list([7, 7, 3, 7]) == 7\n    assert max_of_list([0]) == 0',
    })
print('Questions updated with full descriptions')

# 2. Create experiment module with template
print('Creating experiment module...')
r = api('post', '/experiments/modules', t_tok, {'name': 'NumPy 实验：图像处理入门', 'description': '使用 NumPy 加载和操作图像数据，学习数组切片、变换和基本的图像处理技术。', 'status': 'published'})
if r.status_code == 201:
    mid = r.json()['id']
    # Create template for this module
    r = api('post', '/studio/templates', t_tok, {'name': '图像处理 Notebook', 'description': 'NumPy 图像处理交互实验', 'module_id': mid})
    if r.status_code == 201:
        tid = r.json()['id']
        cells = [
            {'id': 'md1', 'type': 'markdown', 'source': '# NumPy 图像处理入门\n\n在本实验中，你将学习如何使用 NumPy 处理图像数据。图像本质上是一个三维数组（高度 x 宽度 x 通道）。', 'order': 0, 'student_editable': False, 'source_hidden': False},
            {'id': 'c1', 'type': 'code', 'source': 'import numpy as np\nfrom PIL import Image\n\n# 创建一个简单的 100x100 的 RGB 图像\nimg = np.zeros((100, 100, 3), dtype=np.uint8)\nprint(f"图像形状: {img.shape}")\nprint(f"数据类型: {img.dtype}")', 'order': 1, 'student_editable': True, 'source_hidden': False},
            {'id': 'md2', 'type': 'markdown', 'source': '## 创建渐变图像\n\n使用 NumPy 的广播机制，我们可以轻松创建渐变效果。', 'order': 2, 'student_editable': False, 'source_hidden': False},
            {'id': 'c2', 'type': 'code', 'source': '# 创建水平渐变\nx = np.linspace(0, 255, 100).astype(np.uint8)\ngradient = np.tile(x, (100, 1))\n\n# 转换为 RGB\nimg_rgb = np.stack([gradient, np.zeros_like(gradient), 255 - gradient], axis=-1)\nprint(f"渐变图像形状: {img_rgb.shape}")\nprint("创建成功！")', 'order': 3, 'student_editable': True, 'source_hidden': False},
            {'id': 'c3', 'type': 'code', 'source': '# 练习：创建一个圆形掩码\n# 提示：使用 np.ogrid 和距离公式\nh, w = 100, 100\nY, X = np.ogrid[:h, :w]\ncenter = (h//2, w//2)\ndist = np.sqrt((X - center[1])**2 + (Y - center[0])**2)\nmask = (dist <= 40).astype(np.uint8) * 255\nprint(f"圆形掩码已创建")\nprint(f"白色像素数: {np.sum(mask == 255)}")', 'order': 4, 'student_editable': True, 'source_hidden': False},
        ]
        api('put', f'/studio/templates/{tid}/draft', t_tok, {'draft_revision': 1, 'cells': cells})
        api('post', f'/studio/templates/{tid}/publish', t_tok)
        api('patch', f'/experiments/modules/{mid}', t_tok, {'template_id': tid})
        print(f'Experiment module created with {len(cells)} cells')
else:
    print('Module create failed:', r.status_code, r.text[:200])

# 3. Start judge worker
print('Starting judge worker...')
subprocess.Popen(
    [sys.executable, '-m', 'app.worker.judge_worker'],
    cwd='C:/Users/zxk/Documents/DAI Experiment Platform/backend',
    creationflags=subprocess.CREATE_NEW_CONSOLE
)
print('Judge worker started in new window')

print()
print('=== Done ===')
print('1. Assignment questions: full descriptions with examples')
print('2. Experiment module: NumPy image processing with 5 cells')
print('3. Judge worker: running (submit code now works)')
print('4. Student view: http://localhost:5173/student/assignments')
print('5. Experiments: http://localhost:5173/student/experiments')
