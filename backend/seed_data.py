"""Create test data via API"""
import requests, json
BASE = 'http://localhost:8000/api/v1'

def api(method, path, token, data=None):
    h = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    if method == 'post':
        return requests.post(f'{BASE}{path}', headers=h, json=data)
    elif method == 'put':
        return requests.put(f'{BASE}{path}', headers=h, json=data)
    elif method == 'patch':
        return requests.patch(f'{BASE}{path}', headers=h, json=data)
    return requests.get(f'{BASE}{path}', headers=h)

# Login admin
r = requests.post(f'{BASE}/auth/login', json={'username':'admin','password':'Passw0rd!'})
admin = r.json()['access_token']
print('admin logged in')

# Create teacher
r = api('post','/users',admin,{'username':'teacher_wang','password':'Teach123!','real_name':'\u738b\u8001\u5e08','role':'teacher'})
print('teacher:', r.status_code)

# Create students
r = api('post','/users',admin,{'username':'student_xiao','password':'Study123!','real_name':'\u5c0f\u660e','role':'student'})
print('student1:', r.status_code)
r = api('post','/users',admin,{'username':'student_hong','password':'Study123!','real_name':'\u5c0f\u7ea2','role':'student'})
print('student2:', r.status_code)

# Login teacher and students
r = requests.post(f'{BASE}/auth/login', json={'username':'teacher_wang','password':'Teach123!'})
t_tok = r.json()['access_token']
r = requests.post(f'{BASE}/auth/login', json={'username':'student_xiao','password':'Study123!'})
s_tok = r.json()['access_token']
r = requests.post(f'{BASE}/auth/login', json={'username':'student_hong','password':'Study123!'})
s2_tok = r.json()['access_token']

# Create course
r = api('post','/courses',t_tok,{'title':'Python \u673a\u5668\u5b66\u4e60\u5165\u95e8','description':'\u4ece\u96f6\u5f00\u59cb\u5b66\u4e60 Python \u548c\u673a\u5668\u5b66\u4e60\u57fa\u7840\uff0c\u6db5\u76d6 NumPy\u3001Pandas\u3001Scikit-learn\uff0c\u901a\u8fc7 Notebook \u5b9e\u9a8c\u548c\u8003\u8bd5\u5de9\u56fa\u6240\u5b66\u3002','status':'published'})
cid = r.json()['id']
print('course:', cid)

# Enroll
api('post',f'/courses/{cid}/enroll',s_tok)
api('post',f'/courses/{cid}/enroll',s2_tok)

# Chapters
ch1 = api('post',f'/courses/{cid}/chapters',t_tok,{'title':'Python \u57fa\u7840\u56de\u987e','order_index':0})
ch2 = api('post',f'/courses/{cid}/chapters',t_tok,{'title':'NumPy \u4e0e\u6570\u636e\u5904\u7406','order_index':1})
ch3 = api('post',f'/courses/{cid}/chapters',t_tok,{'title':'\u673a\u5668\u5b66\u4e60\u5165\u95e8','order_index':2})
print('chapters created')

# Lessons
md1 = '# Python \u6570\u636e\u7c7b\u578b\n\nPython \u662f\u52a8\u6001\u7c7b\u578b\u8bed\u8a00\uff0c\u6838\u5fc3\u6570\u636e\u7c7b\u578b\u5305\u62ec\uff1a\n\n- **int**\uff1a\u6574\u6570\uff0c\u5982 `42`\n- **float**\uff1a\u6d6e\u70b9\u6570\uff0c\u5982 `3.14`\n- **str**\uff1a\u5b57\u7b26\u4e32\uff0c\u5982 `hello`\n- **list**\uff1a\u5217\u8868\uff0c\u5982 `[1, 2, 3]`\n- **dict**\uff1a\u5b57\u5178\uff0c\u5982 `{"key": "value"}`\n\n## \u5217\u8868\u63a8\u5bfc\n\n```python\nsquares = [x**2 for x in range(10)]\n```'
md2 = '# Python \u51fd\u6570\n\n```python\ndef greet(name):\n    return f"{name}, hello!"\n```\n\n## \u88c5\u9970\u5668\n\n\u88c5\u9970\u5668\u5141\u8bb8\u5728\u4e0d\u4fee\u6539\u539f\u51fd\u6570\u7684\u60c5\u51b5\u4e0b\u589e\u52a0\u529f\u80fd\u3002'
md3 = '# Pandas \u5165\u95e8\n\nPandas \u662f Python \u4e2d\u6700\u5f3a\u5927\u7684\u6570\u636e\u5904\u7406\u5e93\u3002\n\n```python\nimport pandas as pd\ndf = pd.read_csv("data.csv")\nprint(df.head())\n```'
md4 = '# \u673a\u5668\u5b66\u4e60 Hello World\n\n\u4f7f\u7528\u9e22\u5c3e\u82b1\u6570\u636e\u96c6\u8bad\u7ec3\u7b2c\u4e00\u4e2a\u5206\u7c7b\u5668\uff1a\n\n```python\nfrom sklearn.datasets import load_iris\nfrom sklearn.ensemble import RandomForestClassifier\niris = load_iris()\nclf = RandomForestClassifier()\nclf.fit(iris.data, iris.target)\nprint(clf.score(iris.data, iris.target))\n```'

api('post',f'/chapters/{ch1.json()["id"]}/lessons',t_tok,{'title':'Python \u6570\u636e\u7c7b\u578b\u4e0e\u5217\u8868\u63a8\u5bfc','content_type':'markdown','content':md1})
api('post',f'/chapters/{ch1.json()["id"]}/lessons',t_tok,{'title':'\u51fd\u6570\u4e0e\u88c5\u9970\u5668','content_type':'markdown','content':md2})
l3=api('post',f'/chapters/{ch2.json()["id"]}/lessons',t_tok,{'title':'NumPy \u6570\u7ec4\u57fa\u7840','content_type':'notebook','content':'\u52a8\u624b\u5b9e\u9a8c\uff1a\u521b\u5efa\u548c\u64cd\u4f5c NumPy \u6570\u7ec4'})
api('post',f'/chapters/{ch2.json()["id"]}/lessons',t_tok,{'title':'\u6570\u636e\u6e05\u6d17\u4e0e Pandas','content_type':'markdown','content':md3})
api('post',f'/chapters/{ch3.json()["id"]}/lessons',t_tok,{'title':'Scikit-learn \u521d\u63a2','content_type':'markdown','content':md4})
api('post',f'/chapters/{ch3.json()["id"]}/lessons',t_tok,{'title':'\u6a21\u578b\u8bc4\u4f30\u5b9e\u6218','content_type':'notebook','content':'\u52a8\u624b\u5b9e\u9a8c\uff1a\u8bad\u7ec3\u6a21\u578b\u5e76\u8bc4\u4f30\u6027\u80fd\u6307\u6807'})
print('lessons created')

# Create Notebook template for the NumPy lesson
r = api('post','/studio/templates',t_tok,{'name':'NumPy \u6570\u7ec4\u64cd\u4f5c','description':'\u5b66\u4e60 NumPy \u6570\u7ec4\u7684\u521b\u5efa\u3001\u5207\u7247\u548c\u8fd0\u7b97','lesson_id':l3.json()['id']})
if r.status_code == 201:
    tid = r.json()['id']
    cells = [
        {'id':'md-1','type':'markdown','source':'# NumPy \u6570\u7ec4\u57fa\u7840\n\n\u5728\u8fd9\u4e2a Notebook \u4e2d\uff0c\u4f60\u5c06\u5b66\u4e60\u5982\u4f55\u4f7f\u7528 NumPy \u521b\u5efa\u548c\u64cd\u4f5c\u6570\u7ec4\u3002','order':0,'student_editable':False,'source_hidden':False},
        {'id':'c-1','type':'code','source':'import numpy as np\nprint(f"NumPy \u7248\u672c: {np.__version__}")','order':1,'student_editable':True,'source_hidden':False},
        {'id':'md-2','type':'markdown','source':'## \u521b\u5efa\u6570\u7ec4\n\nNumPy \u63d0\u4f9b\u4e86\u591a\u79cd\u521b\u5efa\u6570\u7ec4\u7684\u65b9\u6cd5\u3002','order':2,'student_editable':False,'source_hidden':False},
        {'id':'c-2','type':'code','source':'# \u521b\u5efa\u4e00\u7ef4\u6570\u7ec4\na = np.array([1, 2, 3, 4, 5])\nprint("\u4e00\u7ef4\u6570\u7ec4:", a)\n\n# \u521b\u5efa\u5168\u96f6\u6570\u7ec4\nzeros = np.zeros((3, 4))\nprint("\u5168\u96f6\u6570\u7ec4:\\n", zeros)\n\n# \u521b\u5efa\u968f\u673a\u6570\u7ec4\nrandom_arr = np.random.randn(2, 3)\nprint("\u968f\u673a\u6570\u7ec4:\\n", random_arr)','order':3,'student_editable':True,'source_hidden':False},
        {'id':'c-3','type':'code','source':'# \u7ec3\u4e60\uff1a\u521b\u5efa\u4e00\u4e2a 3x3 \u7684\u5355\u4f4d\u77e9\u9635\n# \u7b54\u6848\u5e94\u8be5\u4f7f\u7528 np.eye(3)\npass','order':4,'student_editable':True,'source_hidden':False},
    ]
    api('put',f'/studio/templates/{tid}/draft',t_tok,{'draft_revision':1,'cells':cells})
    api('post',f'/studio/templates/{tid}/publish',t_tok)
    print('template with cells created')

# Create assignment
r = api('post','/assignments',t_tok,{'course_id':cid,'title':'Python \u7f16\u7a0b\u7ec3\u4e60','status':'published'})
aid = r.json()['id']
api('post',f'/assignments/{aid}/questions',t_tok,{'title':'\u4e24\u6570\u4e4b\u548c','function_name':'add','hidden_tests':'def test_add():\n    assert add(1,2)==3\n    assert add(-1,1)==0'})
api('post',f'/assignments/{aid}/questions',t_tok,{'title':'\u5217\u8868\u6700\u5927\u503c','function_name':'max_of_list','hidden_tests':'def test_max():\n    assert max_of_list([1,5,3])==5\n    assert max_of_list([-1])==-1'})
print('assignment created')

# Create exam
r = api('post','/exams',t_tok,{'course_id':cid,'title':'Python \u4e0e\u673a\u5668\u5b66\u4e60\u57fa\u7840\u6d4b\u9a8c','duration_minutes':30,'start_at':'2026-01-01T00:00:00','end_at':'2026-12-31T23:59:59'})
eid = r.json()['id']
# Single choice
api('post',f'/exams/{eid}/questions',t_tok,{'question_type':'single_choice','prompt':'Python \u4e2d\uff0c\u4ee5\u4e0b\u54ea\u4e2a\u5173\u952e\u5b57\u7528\u4e8e\u5b9a\u4e49\u51fd\u6570\uff1f','options':{'A':'func','B':'def','C':'function','D':'define'},'correct_answer':{'correct':['B']},'points':5,'order_index':0})
# Multi choice
api('post',f'/exams/{eid}/questions',t_tok,{'question_type':'multi_choice','prompt':'\u4ee5\u4e0b\u54ea\u4e9b\u662f Python \u7684\u5185\u7f6e\u6570\u636e\u7c7b\u578b\uff1f\uff08\u591a\u9009\uff09','options':{'A':'list','B':'array','C':'dict','D':'tuple'},'correct_answer':{'correct':['A','C','D']},'points':10,'order_index':1})
# Code question
api('post',f'/exams/{eid}/questions',t_tok,{'question_type':'code','prompt':'\u7f16\u5199\u4e00\u4e2a\u51fd\u6570 fibonacci(n)\uff0c\u8fd4\u56de\u6590\u6ce2\u62c9\u5951\u6570\u5217\u7684\u524d n \u9879\uff08\u5217\u8868\uff09\u3002\u4f8b\u5982 fibonacci(5) \u8fd4\u56de [0,1,1,2,3]\u3002','points':20,'order_index':2,'hidden_tests':'def test_fib():\n    assert fibonacci(5)==[0,1,1,2,3]\n    assert fibonacci(1)==[0]','starter_code':'def fibonacci(n):\n    pass','correct_answer':{}})
# More single choice
api('post',f'/exams/{eid}/questions',t_tok,{'question_type':'single_choice','prompt':'Scikit-learn \u662f\u4e00\u4e2a\u4e3b\u8981\u7528\u4e8e\u4ec0\u4e48\u7684\u5e93\uff1f','options':{'A':'Web\u5f00\u53d1','B':'\u673a\u5668\u5b66\u4e60','C':'\u56fe\u50cf\u5904\u7406','D':'\u6570\u636e\u5e93\u7ba1\u7406'},'correct_answer':{'correct':['B']},'points':5,'order_index':3})
api('post',f'/exams/{eid}/questions',t_tok,{'question_type':'single_choice','prompt':'\u4ee5\u4e0b\u54ea\u79cd\u65b9\u6cd5\u53ef\u4ee5\u9632\u6b62\u6a21\u578b\u8fc7\u62df\u5408\uff1f','options':{'A':'\u589e\u52a0\u8bad\u7ec3\u8f6e\u6570','B':'\u4f7f\u7528\u66f4\u591a\u53c2\u6570','C':'\u4f7f\u7528\u6b63\u5219\u5316','D':'\u51cf\u5c11\u8bad\u7ec3\u6570\u636e'},'correct_answer':{'correct':['C']},'points':5,'order_index':4})
# Publish
api('patch',f'/exams/{eid}',t_tok,{'status':'published'})
print('exam published with 5 questions')

print()
print('='*50)
print('\u6d4b\u8bd5\u6570\u636e\u521b\u5efa\u5b8c\u6210\uff01')
print('='*50)
print('\u6559\u5e08: teacher_wang / Teach123!')
print('\u5b66\u751f1: student_xiao / Study123!')
print('\u5b66\u751f2: student_hong / Study123!')
print(f'\u8bfe\u7a0b ID: {cid}')
print(f'\u8003\u8bd5 ID: {eid}')
print(f'\u4f5c\u4e1a ID: {aid}')
print('\u524d\u7aef: http://localhost:5173')
print('Swagger: http://localhost:8000/docs')
