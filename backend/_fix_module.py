import requests
BASE='http://localhost:8000/api/v1'
def api(m,p,t,d=None):
    h={'Authorization':f'Bearer {t}','Content-Type':'application/json'}
    if m=='post': return requests.post(f'{BASE}{p}',headers=h,json=d)
    if m=='patch': return requests.patch(f'{BASE}{p}',headers=h,json=d)
    if m=='put': return requests.put(f'{BASE}{p}',headers=h,json=d)
r=requests.post(f'{BASE}/auth/login',json={'username':'admin','password':'Passw0rd!'})
a_tok=r.json()['access_token']
r=requests.post(f'{BASE}/auth/login',json={'username':'teacher_wang','password':'Teach123!'})
t_tok=r.json()['access_token']
r=api('post','/experiments/modules',a_tok,{'name':'NumPy \u56fe\u50cf\u5904\u7406\u5165\u95e8','description':'\u4f7f\u7528 NumPy \u52a0\u8f7d\u548c\u64cd\u4f5c\u56fe\u50cf\u6570\u636e\uff0c\u5b66\u4e60\u6570\u7ec4\u5207\u7247\u3001\u53d8\u6362\u548c\u57fa\u672c\u7684\u56fe\u50cf\u5904\u7406\u6280\u672f\u3002\u5305\u542b\u6e10\u53d8\u751f\u6210\u3001\u5706\u5f62\u63a9\u7801\u7b49\u52a8\u624b\u5b9e\u9a8c\u3002','status':'published'})
print('module:',r.status_code,r.json().get('id','?'))
mid=r.json()['id']
r=api('post','/studio/templates',a_tok,{'name':'\u56fe\u50cf\u5904\u7406 Notebook','description':'NumPy \u56fe\u50cf\u5904\u7406\u4ea4\u4e92\u5b9e\u9a8c','module_id':mid})
print('template:',r.status_code,r.json().get('id','?'))
tid=r.json()['id']
cells=[
    {'id':'m1','type':'markdown','source':'# NumPy \u56fe\u50cf\u5904\u7406\u5165\u95e8\n\n\u56fe\u50cf\u672c\u8d28\u4e0a\u662f\u4e00\u4e2a\u4e09\u7ef4\u6570\u7ec4\uff08\u9ad8\u5ea6 x \u5bbd\u5ea6 x \u901a\u9053\uff09\u3002\u5728\u672c\u5b9e\u9a8c\u4e2d\uff0c\u4f60\u5c06\u5b66\u4e60\u5982\u4f55\u4f7f\u7528 NumPy \u5904\u7406\u56fe\u50cf\u6570\u636e\u3002','order':0,'student_editable':False,'source_hidden':False},
    {'id':'c1','type':'code','source':'import numpy as np\n\n# \u521b\u5efa\u4e00\u4e2a\u7b80\u5355\u7684 100x100 \u7684 RGB \u56fe\u50cf\nimg = np.zeros((100, 100, 3), dtype=np.uint8)\nprint(f\"\u56fe\u50cf\u5f62\u72b6: {img.shape}\")\nprint(f\"\u6570\u636e\u7c7b\u578b: {img.dtype}\")','order':1,'student_editable':True,'source_hidden':False},
    {'id':'m2','type':'markdown','source':'## \u521b\u5efa\u6e10\u53d8\u56fe\u50cf\n\n\u4f7f\u7528 NumPy \u7684\u5e7f\u64ad\u673a\u5236\u8f7b\u677e\u521b\u5efa\u6e10\u53d8\u6548\u679c\u3002','order':2,'student_editable':False,'source_hidden':False},
    {'id':'c2','type':'code','source':'# \u521b\u5efa\u6c34\u5e73\u6e10\u53d8\nx = np.linspace(0, 255, 100).astype(np.uint8)\ngradient = np.tile(x, (100, 1))\nimg_rgb = np.stack([gradient, np.zeros_like(gradient), 255 - gradient], axis=-1)\nprint(f\"\u6e10\u53d8\u56fe\u50cf\u5f62\u72b6: {img_rgb.shape}\")','order':3,'student_editable':True,'source_hidden':False},
    {'id':'c3','type':'code','source':'# \u7ec3\u4e60\uff1a\u521b\u5efa\u5706\u5f62\u63a9\u7801\nh, w = 100, 100\nY, X = np.ogrid[:h, :w]\ncenter = (50, 50)\ndist = np.sqrt((X - center[0])**2 + (Y - center[1])**2)\nmask = (dist <= 40).astype(np.uint8) * 255\nprint(f\"\u5706\u5f62\u63a9\u7801\u5df2\u521b\u5efa\uff0c\u767d\u8272\u50cf\u7d20\u6570: {np.sum(mask == 255)}\")','order':4,'student_editable':True,'source_hidden':False},
]
api('put',f'/studio/templates/{tid}/draft',a_tok,{'draft_revision':1,'cells':cells})
api('post',f'/studio/templates/{tid}/publish',a_tok)
api('patch',f'/experiments/modules/{mid}',a_tok,{'template_id':tid,'status':'published'})
print('Experiment module ready:', mid)
